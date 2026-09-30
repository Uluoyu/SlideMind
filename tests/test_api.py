from fastapi.testclient import TestClient
from sqlalchemy import select

from slidemind_api.main import create_app
from slidemind_api.models import Document
from slidemind_common.security import SecurityLevel

PREFIX = "/api/ppt"


def project(client, name="Test project"):
    response = client.post(f"{PREFIX}/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_project_and_file_survive_restart(client, settings):
    project_id = project(client)
    other = project(client, "Other project")
    path = f"{PREFIX}/projects/{project_id}/documents"
    response = client.post(path, files={"file": ("../report.md", b"Source evidence", "text/plain")})
    assert response.status_code == 201
    assert response.json()["status"] == "QUEUED"
    assert response.json()["fileName"] == "report.md"
    assert "storagePath" not in response.json()
    with client.app.state.sessions() as db:
        document = db.scalar(select(Document))
        assert (settings.storage_root / document.storage_path).read_bytes() == b"Source evidence"
    assert client.get(f"{PREFIX}/projects/{other}/documents").json() == []
    with TestClient(create_app(settings)) as restarted:
        assert len(restarted.get(path).json()) == 1
        assert len(restarted.get(f"{PREFIX}/projects").json()) == 2


def test_upload_validation_and_security(client, settings):
    project_id = project(client)
    path = f"{PREFIX}/projects/{project_id}/documents"
    for name, content, status in [
        ("run.exe", b"binary", 415),
        ("empty.md", b"", 422),
        ("large.txt", b"x" * (1024 * 1024 + 1), 413),
    ]:
        assert client.post(path, files={"file": (name, content)}).status_code == status
    assert (
        client.post(
            path, files={"file": ("secret.txt", b"secret")}, data={"securityLevel": "TOP_SECRET"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            path,
            files={"file": ("internal.txt", b"private")},
            data={"securityLevel": "CONFIDENTIAL"},
        ).status_code
        == 201
    )
    settings.security_clearance = SecurityLevel.PUBLIC
    assert client.get(path).json() == []
    assert (
        client.post(
            f"{PREFIX}/projects/99999/documents", files={"file": ("file.txt", b"text")}
        ).status_code
        == 404
    )


def test_assets_and_templates_are_separate(client):
    project_id = project(client)
    assert (
        client.post(
            f"{PREFIX}/projects/{project_id}/assets",
            files={"file": ("screen.png", b"pending image parsing")},
        ).status_code
        == 201
    )
    template = client.post(
        f"{PREFIX}/templates", files={"file": ("brand.pptx", b"pending parsing")}
    )
    assert template.status_code == 201
    linked = client.post(
        f"{PREFIX}/projects", json={"name": "Brand", "templateId": template.json()["id"]}
    )
    assert linked.status_code == 201
    assert client.get(f"{PREFIX}/projects/{project_id}/documents").json() == []
    assert (
        client.post(f"{PREFIX}/projects", json={"name": "Invalid", "templateId": 99999}).status_code
        == 404
    )


def test_outline_confirmation_and_project_scope(client):
    first = project(client)
    second = project(client, "Other")
    response = client.post(
        f"{PREFIX}/documents",
        json={
            "projectId": first,
            "title": "Project review",
            "pageCount": 4,
            "requirements": ["Key milestone"],
        },
    )
    assert response.status_code == 201
    document_id = response.json()["id"]
    base = f"{PREFIX}/documents/{document_id}"
    scope = f"?projectId={first}"
    page = {"pageNo": 1, "title": "A", "purpose": "B"}
    assert client.post(f"{base}/outline/confirm{scope}", json={"pages": [page]}).status_code == 409
    assert client.get(f"{base}?projectId={second}").status_code == 404
    assert client.post(f"{base}/outline/generate?projectId={second}").status_code == 404
    generated = client.post(f"{base}/outline/generate{scope}")
    assert generated.status_code == 200
    assert generated.json()["planner"] == "local-scaffold"
    assert len(generated.json()["pages"]) == 4
    assert generated.json()["pages"][1]["title"] == "Key milestone"
    assert len(client.post(f"{base}/outline/generate{scope}").json()["pages"]) == 4
    invalid = {"pages": [{**page, "pageNo": 2}]}
    assert client.post(f"{base}/outline/confirm{scope}", json=invalid).status_code == 422
    confirmed = client.post(f"{base}/outline/confirm{scope}", json={"pages": [page]})
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "OUTLINE_CONFIRMED"
    assert client.get(f"{base}{scope}").json()["pageCount"] == 1
    assert client.post(f"{base}/outline/generate{scope}").status_code == 409
    assert client.get(f"{base}/outline{scope}").json()["pages"][0]["title"] == "A"


def test_storage_failure_is_not_reported_as_success(client, monkeypatch):
    project_id = project(client)

    def fail(*args):
        raise OSError("Storage unavailable")

    monkeypatch.setattr(client.app.state.store, "put", fail)
    path = f"{PREFIX}/projects/{project_id}/documents"
    assert client.post(path, files={"file": ("file.txt", b"text")}).status_code == 503
    assert client.get(path).json() == []


def test_health_and_request_validation(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200
    assert client.post(f"{PREFIX}/projects", json={"name": "  "}).status_code == 422
    assert (
        client.post(
            f"{PREFIX}/documents", json={"projectId": 9999, "title": "X", "pageCount": 0}
        ).status_code
        == 422
    )
    assert client.get("/openapi.json").status_code == 200
