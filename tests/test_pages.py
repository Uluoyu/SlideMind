from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Event
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from slidemind_api.main import create_app
from slidemind_api.models import Page
from slidemind_api.rendering import HttpRenderer, RenderInputTooLarge
from slidemind_common.security import SecurityLevel
from slidemind_schemas.page import DeckSpec, PageSpec

PREFIX = "/api/ppt"


def create_deck(client, confirm=True, page_count=2):
    project = client.post(f"{PREFIX}/projects", json={"name": "页面测试"}).json()["id"]
    deck = client.post(
        f"{PREFIX}/documents",
        json={"projectId": project, "title": "项目汇报", "pageCount": page_count},
    ).json()["id"]
    base = f"{PREFIX}/documents/{deck}"
    scope = f"?projectId={project}"
    if confirm:
        outline = client.post(f"{base}/outline/generate{scope}").json()
        assert (
            client.post(
                f"{base}/outline/confirm{scope}", json={"pages": outline["pages"]}
            ).status_code
            == 200
        )
    return project, base, scope


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


def test_pages_require_confirmation_and_project_scope(client):
    _, base, scope = create_deck(client, confirm=False)
    assert client.post(f"{base}/pages/generate{scope}").status_code == 409
    assert client.post(f"{base}/render{scope}").status_code == 409
    assert client.post(f"{base}/pages/generate?projectId=99999").status_code == 404
    assert client.get(f"{base}/pages?projectId=99999").status_code == 404
    assert client.get(f"{base}/download{scope}").status_code == 409


def test_generate_edit_restart_and_optimistic_version(client, settings):
    _, base, scope = create_deck(client)
    generated = client.post(f"{base}/pages/generate{scope}")
    assert generated.status_code == 200
    assert generated.json()["status"] == "DESIGN_GENERATED"
    first = generated.json()["pages"][0]
    assert first["pageJson"]["title"] == "项目汇报"
    second = generated.json()["pages"][1]
    assert second["pageJson"]["content"][0]["sources"] == []
    edited = {**second["pageJson"], "title": "经过确认的结论"}
    body = {"version": second["version"], "page": edited}
    saved = client.post(f"{base}/pages/2{scope}", json=body)
    assert saved.status_code == 200
    assert saved.json()["version"] == second["version"] + 1
    assert client.post(f"{base}/pages/2{scope}", json=body).status_code == 409
    regenerated = client.post(f"{base}/pages/generate{scope}").json()
    assert regenerated["pages"][1]["pageJson"]["title"] == "经过确认的结论"
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"{base}/pages{scope}").json()["pages"][1] == saved.json()
    assert (
        client.post(
            f"{base}/pages/2{scope}",
            json={"version": saved.json()["version"], "page": {**edited, "page_no": 1}},
        ).status_code
        == 422
    )


def test_single_page_generation_and_render_requires_all_pages(client):
    _, base, scope = create_deck(client)
    assert client.post(f"{base}/pages/1/generate{scope}").status_code == 200
    assert client.post(f"{base}/render{scope}").status_code == 409
    assert client.post(f"{base}/pages/1/generate{scope}").status_code == 409
    assert client.post(f"{base}/pages/3/generate{scope}").status_code == 404
    assert client.post(f"{base}/pages/2/generate{scope}").status_code == 200
    assert client.get(f"{base}{scope}").json()["status"] == "DESIGN_GENERATED"


def test_render_download_restart_and_edit_invalidates_export(client, settings):
    _, base, scope = create_deck(client)
    client.post(f"{base}/pages/generate{scope}")
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    result = client.post(f"{base}/render{scope}")
    assert result.status_code == 200
    assert result.json()["status"] == "COMPLETED"
    assert "pptPath" not in result.json()
    assert renderer.decks[0].pages[0].title == "项目汇报"
    with TestClient(create_app(settings)) as restarted:
        download = restarted.get(result.json()["downloadUrl"])
        assert download.status_code == 200
        assert download.content == pptx_bytes()
        assert "presentationml" in download.headers["content-type"]
    assert client.get(f"{base}/download?projectId=99999").status_code == 404
    page = client.get(f"{base}/pages{scope}").json()["pages"][0]
    assert (
        client.post(
            f"{base}/pages/1{scope}", json={"version": page["version"], "page": page["pageJson"]}
        ).status_code
        == 200
    )
    assert client.get(f"{base}/download{scope}").status_code == 409
    assert client.get(f"{base}{scope}").json()["status"] == "DESIGN_GENERATED"


def test_render_failure_preserves_pages_and_can_retry(client):
    _, base, scope = create_deck(client)
    before = client.post(f"{base}/pages/generate{scope}").json()["pages"]

    class BrokenRenderer:
        def render(self, deck):
            raise OSError("connection failed")

    client.app.state.renderer = BrokenRenderer()
    assert client.post(f"{base}/render{scope}").status_code == 503
    assert client.get(f"{base}{scope}").json()["status"] == "FAILED"
    assert client.get(f"{base}/pages{scope}").json()["pages"] == before
    client.app.state.renderer = RecordingRenderer()
    assert client.post(f"{base}/render{scope}").status_code == 200


def test_render_rejects_invalid_artifact_and_storage_failure(client, monkeypatch):
    _, base, scope = create_deck(client)
    client.post(f"{base}/pages/generate{scope}")
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    monkeypatch.setattr(renderer, "render", lambda deck: b"not a presentation")
    assert client.post(f"{base}/render{scope}").status_code == 503
    assert client.get(f"{base}/download{scope}").status_code == 409
    client.app.state.renderer = RecordingRenderer()

    def fail(*args):
        raise OSError("unavailable")

    monkeypatch.setattr(client.app.state.store, "put", fail)
    assert client.post(f"{base}/render{scope}").status_code == 503
    assert client.get(f"{base}/download{scope}").status_code == 409


def test_sources_are_scoped_and_rechecked_on_read_render_and_download(client, settings):
    project, base, scope = create_deck(client)
    other, _, _ = create_deck(client)
    foreign = client.post(
        f"{PREFIX}/projects/{other}/documents", files={"file": ("other.md", b"other")}
    ).json()["id"]
    private = client.post(
        f"{PREFIX}/projects/{project}/documents",
        files={"file": ("private.md", b"evidence")},
        data={"securityLevel": "CONFIDENTIAL"},
    ).json()["id"]
    page = client.post(f"{base}/pages/generate{scope}").json()["pages"][1]
    spec = page["pageJson"]
    reference = {"document_id": foreign, "file_name": "other.md", "excerpt": "other"}
    spec["content"][0]["sources"] = [reference]
    assert (
        client.post(
            f"{base}/pages/2{scope}", json={"version": page["version"], "page": spec}
        ).status_code
        == 422
    )
    spec["content"][0]["sources"] = [
        {"document_id": private, "file_name": "private.md", "excerpt": "evidence"}
    ]
    assert (
        client.post(
            f"{base}/pages/2{scope}", json={"version": page["version"], "page": spec}
        ).status_code
        == 200
    )
    client.app.state.renderer = RecordingRenderer()
    assert client.post(f"{base}/render{scope}").status_code == 200
    settings.security_clearance = SecurityLevel.PUBLIC
    assert client.get(f"{base}/pages{scope}").status_code == 403
    assert client.post(f"{base}/render{scope}").status_code == 403
    assert client.get(f"{base}/download{scope}").status_code == 403


def test_oversized_valid_deck_is_rejected_before_rendering(client):
    project, base, scope = create_deck(client, page_count=5)
    client.post(f"{base}/pages/generate{scope}")
    document = client.post(
        f"{PREFIX}/projects/{project}/documents", files={"file": ("report.md", b"evidence")}
    ).json()["id"]
    reference = {"document_id": document, "file_name": "report.md", "excerpt": "证" * 2000}
    specs = []
    with client.app.state.sessions() as db:
        for page in db.scalars(select(Page).where(Page.ppt_id == int(base.rsplit("/", 1)[-1]))):
            spec = {
                **page.page_json,
                "content": [{"title": "证据", "text": "项目事实", "sources": [reference] * 20}] * 4,
            }
            page.page_json = PageSpec.model_validate(spec).model_dump()
            specs.append(PageSpec.model_validate(spec))
        db.commit()
    with pytest.raises(RenderInputTooLarge, match="2 MiB"):
        # This must fail before attempting any network connection.
        HttpRenderer("http://127.0.0.1:1", 1).render(DeckSpec(title="Large", pages=specs))
    renderer = RecordingRenderer()
    client.app.state.renderer = renderer
    response = client.post(f"{base}/render{scope}")
    assert response.status_code == 422
    assert "2 MiB" in response.json()["detail"]
    assert renderer.decks == []
    assert client.get(f"{base}{scope}").json()["status"] == "DESIGN_GENERATED"


def test_edit_racing_with_render_never_publishes_stale_export(client):
    _, base, scope = create_deck(client)
    page = client.post(f"{base}/pages/generate{scope}").json()["pages"][0]
    started, release, editing = Event(), Event(), Event()

    class WaitingRenderer:
        def render(self, deck):
            started.set()
            assert release.wait(5), "test did not release the renderer"
            return pptx_bytes()

    def observe_update(connection, cursor, statement, parameters, context, executemany):
        if started.is_set() and statement.startswith("UPDATE ppt_document_instance"):
            editing.set()

    client.app.state.renderer = WaitingRenderer()
    engine = client.app.state.engine
    event.listen(engine, "before_cursor_execute", observe_update)
    edit = {"version": page["version"], "page": {**page["pageJson"], "title": "修改后的标题"}}
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            rendering = pool.submit(client.post, f"{base}/render{scope}")
            assert started.wait(3)
            saving = pool.submit(client.post, f"{base}/pages/1{scope}", json=edit)
            try:
                assert editing.wait(3)
            finally:
                release.set()
            assert rendering.result(timeout=5).status_code == 200
            assert saving.result(timeout=5).status_code == 409
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", observe_update)
    assert client.get(f"{base}/download{scope}").status_code == 200
    assert client.post(f"{base}/pages/1{scope}", json=edit).status_code == 200
    assert client.get(f"{base}/download{scope}").status_code == 409
