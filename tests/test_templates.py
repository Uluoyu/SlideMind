from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import select
from test_template_design import make_template_pptx

from slidemind_api.models import DesignSystem, Template
from slidemind_common.security import SecurityLevel
from slidemind_schemas.page import SlideSize, Theme

PREFIX = "/api/ppt"


def pptx_bytes():
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/presentation.xml", "<presentation/>")
    return output.getvalue()


class RecordingRenderer:
    def __init__(self):
        self.decks = []

    def render(self, deck):
        self.decks.append(deck)
        return pptx_bytes()


def upload_template(client, data=None, name="brand.pptx", level=None):
    response = client.post(
        f"{PREFIX}/templates",
        files={"file": (name, data if data is not None else make_template_pptx())},
        data={} if level is None else {"securityLevel": level},
    )
    assert response.status_code == 201
    return response.json()


def create_deck(client, template_id=None):
    body = {"name": "模板测试"}
    if template_id is not None:
        body["templateId"] = template_id
    project = client.post(f"{PREFIX}/projects", json=body).json()["id"]
    deck = client.post(
        f"{PREFIX}/documents",
        json={"projectId": project, "title": "项目汇报", "pageCount": 2},
    ).json()["id"]
    base = f"{PREFIX}/documents/{deck}"
    scope = f"?projectId={project}"
    outline = client.post(f"{base}/outline/generate{scope}").json()
    assert (
        client.post(f"{base}/outline/confirm{scope}", json={"pages": outline["pages"]}).status_code
        == 200
    )
    client.post(f"{base}/pages/generate{scope}")
    return project, base, scope


def test_upload_parses_template_into_design_system(client):
    template = upload_template(client)
    assert template["status"] == "READY"
    assert template["processingError"] is None
    with client.app.state.sessions() as db:
        rows = db.scalars(
            select(DesignSystem).where(DesignSystem.template_id == template["id"])
        ).all()
    assert len(rows) == 1
    assert rows[0].version == 1
    assert rows[0].design_json["accent1"] == "#315C4E"
    assert rows[0].design_json["title_font"] == "微软雅黑"
    assert rows[0].design_json["slide_width_emu"] == 12192000


def test_upload_stores_file_even_when_parsing_fails(client):
    template = upload_template(client, data=b"pending parsing")
    assert template["status"] == "FAILED"
    assert template["processingError"]


def test_reprocess_bumps_versions_and_render_uses_latest_design(client):
    template = upload_template(client)
    reprocessed = client.post(f"{PREFIX}/templates/{template['id']}/process").json()
    assert reprocessed["status"] == "READY"
    with client.app.state.sessions() as db:
        record = db.get(Template, template["id"])
        # Initial 1 plus two successful processings (upload and the reprocess).
        assert record.version == 3
        rows = db.scalars(
            select(DesignSystem)
            .where(DesignSystem.template_id == template["id"])
            .order_by(DesignSystem.version)
        ).all()
        assert [row.version for row in rows] == [1, 2]
        rows[-1].design_json = {**rows[-1].design_json, "accent1": "#123456"}
        db.commit()
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    _, base, scope = create_deck(client, template_id=template["id"])
    assert client.post(f"{base}/render{scope}").status_code == 200
    assert renderer.decks[-1].theme.primary_color == "#123456"


def test_reprocess_of_failed_template_stays_failed(client):
    broken = upload_template(client, data=b"pending parsing")
    assert client.post(f"{PREFIX}/templates/{broken['id']}/process").json()["status"] == "FAILED"
    assert upload_template(client)["status"] == "READY"
    assert client.post(f"{PREFIX}/templates/999999/process").status_code == 404


def test_render_uses_template_theme_and_slide_size(client):
    template = upload_template(client, name="公司模板.pptx")
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    _, base, scope = create_deck(client, template_id=template["id"])
    result = client.post(f"{base}/render{scope}")
    assert result.status_code == 200
    deck = renderer.decks[-1]
    assert deck.theme.name == "公司模板.pptx"
    assert deck.theme.primary_color == "#315C4E"
    assert deck.theme.background_color == "#F5F5F0"
    assert deck.theme.text_color == "#182A23"
    assert deck.theme.title_font_family == "微软雅黑"
    assert deck.theme.body_font_family == "Calibri"
    assert deck.theme.footer == "SlideMind"
    assert deck.slide_size.width == 13.3333
    assert deck.slide_size.height == 7.5
    assert result.json()["themeSource"] == "template"
    assert result.json()["themeName"] == "公司模板.pptx"


def test_render_without_template_uses_defaults(client):
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    _, base, scope = create_deck(client)
    result = client.post(f"{base}/render{scope}")
    assert result.status_code == 200
    assert result.json()["themeSource"] == "default"
    assert result.json()["themeName"] == "SlideMind Starter"
    assert renderer.decks[-1].theme == Theme()
    assert renderer.decks[-1].slide_size == SlideSize()


def test_render_with_failed_template_falls_back_to_defaults(client):
    broken = upload_template(client, data=b"pending parsing")
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    _, base, scope = create_deck(client, template_id=broken["id"])
    result = client.post(f"{base}/render{scope}")
    assert result.status_code == 200
    assert result.json()["themeSource"] == "default"
    assert renderer.decks[-1].theme == Theme()


def test_render_with_corrupt_design_json_falls_back_to_defaults(client):
    template = upload_template(client)
    with client.app.state.sessions() as db:
        row = db.scalars(
            select(DesignSystem).where(DesignSystem.template_id == template["id"])
        ).one()
        row.design_json = {"schema_version": "not-a-version"}
        db.commit()
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    _, base, scope = create_deck(client, template_id=template["id"])
    result = client.post(f"{base}/render{scope}")
    assert result.status_code == 200
    assert result.json()["themeSource"] == "default"
    assert renderer.decks[-1].theme == Theme()
    assert renderer.decks[-1].slide_size == SlideSize()


def test_render_rejects_inaccessible_template_without_status_side_effects(client, settings):
    template = upload_template(client)
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    _, base, scope = create_deck(client, template_id=template["id"])
    settings.security_clearance = SecurityLevel.PUBLIC
    assert client.post(f"{base}/render{scope}").status_code == 403
    assert client.get(f"{base}{scope}").json()["status"] == "DESIGN_GENERATED"
    assert renderer.decks == []


def test_project_template_association_lifecycle(client, settings):
    project = client.post(f"{PREFIX}/projects", json={"name": "品牌项目"}).json()["id"]
    first = upload_template(client)
    second = upload_template(client, name="second.pptx")
    path = f"{PREFIX}/projects/{project}/template"
    linked = client.post(path, json={"templateId": first["id"]})
    assert linked.status_code == 200
    assert linked.json()["templateId"] == first["id"]
    changed = client.post(path, json={"templateId": second["id"]})
    assert changed.json()["templateId"] == second["id"]
    cleared = client.post(path, json={"templateId": None})
    assert cleared.status_code == 200
    assert cleared.json()["templateId"] is None
    assert client.post(path, json={"templateId": 99999}).status_code == 404
    restricted = upload_template(client, name="secret.pptx", level="CONFIDENTIAL")
    settings.security_clearance = SecurityLevel.PUBLIC
    assert client.post(path, json={"templateId": restricted["id"]}).status_code == 404
    assert client.post(f"{PREFIX}/templates/{restricted['id']}/process").status_code == 404
