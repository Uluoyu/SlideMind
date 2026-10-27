import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from test_ingestion import EvidenceEmbedder

from slidemind_agent.planner import PlannedPage, PlanningError
from slidemind_api.main import create_app
from slidemind_api.models import DocumentChunk, Presentation

PREFIX = "/api/ppt"


class FakePlanner:
    """Model substitute: cites the first evidence id; retrieval, storage and routes are real."""

    name = "model"
    uses_evidence = True
    supports_feedback = True

    def __init__(self):
        self.requests, self.error, self.before_return = [], None, None

    def plan(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        if self.before_return:
            self.before_return()
        cited = (request.evidence[0].chunk_id,) if request.evidence else ()
        count = len(request.current_pages) + 1 if request.feedback else request.page_count
        return [PlannedPage(i, f"页面{i}", f"用途{i}", cited) for i in range(1, count + 1)]


@pytest.fixture
def planner():
    return FakePlanner()


@pytest.fixture
def model_client(settings, planner):
    with TestClient(create_app(settings, embedder=EvidenceEmbedder(), planner=planner)) as client:
        yield client


def indexed_project(client, name="项目", text="人员轨迹系统记录洁净室人员的位置。"):
    project = client.post(f"{PREFIX}/projects", json={"name": name}).json()["id"]
    if text:
        response = client.post(
            f"{PREFIX}/projects/{project}/documents",
            files={"file": ("方案.txt", text.encode())},
            data={"securityLevel": "INTERNAL"},
        )
        assert response.status_code == 201
        assert client.app.state.ingestor.process_next()
    return project


def deck(client, project, page_count=3):
    body = {
        "projectId": project,
        "title": "人员轨迹汇报",
        "pageCount": page_count,
        "requirements": ["突出人员轨迹"],
    }
    document = client.post(f"{PREFIX}/documents", json=body).json()["id"]
    return f"{PREFIX}/documents/{document}", f"?projectId={project}"


def test_model_outline_cites_project_evidence_and_confirm_rebuilds_snapshot(model_client, planner):
    project = indexed_project(model_client)
    base, scope = deck(model_client, project)
    outline = model_client.post(f"{base}/outline/generate{scope}").json()
    assert outline["planner"] == "model" and outline["warning"] is None
    assert len(outline["pages"]) == 3
    [evidence] = planner.requests[0].evidence
    assert evidence.excerpt == "人员轨迹系统记录洁净室人员的位置。"
    source = outline["pages"][0]["sources"][0]
    assert outline["pages"][0]["sourceChunkIds"] == [evidence.chunk_id]
    assert source["fileName"] == "方案.txt" and source["excerpt"] == evidence.excerpt
    # Clients echo the view back; tampered snapshots are ignored and rebuilt from ids.
    pages = outline["pages"]
    pages[0]["sources"][0]["excerpt"] = "伪造的摘录"
    confirmed = model_client.post(f"{base}/outline/confirm{scope}", json={"pages": pages})
    assert confirmed.status_code == 200
    assert confirmed.json()["pages"][0]["sources"][0]["excerpt"] == evidence.excerpt
    reread = model_client.get(f"{base}/outline{scope}").json()
    assert reread["planner"] == "model" and reread["status"] == "OUTLINE_CONFIRMED"


def test_confirm_rejects_forged_and_foreign_chunk_ids(model_client):
    own = indexed_project(model_client)
    foreign_outline_base, foreign_scope = deck(model_client, indexed_project(model_client, "外部"))
    foreign = model_client.post(f"{foreign_outline_base}/outline/generate{foreign_scope}").json()
    foreign_id = foreign["pages"][0]["sourceChunkIds"][0]
    base, scope = deck(model_client, own)
    pages = model_client.post(f"{base}/outline/generate{scope}").json()["pages"]
    for bad in (999999, foreign_id):
        tampered = [{**pages[0], "sourceChunkIds": [bad]}, *pages[1:]]
        response = model_client.post(f"{base}/outline/confirm{scope}", json={"pages": tampered})
        assert response.status_code == 422
    assert model_client.get(f"{base}{scope}").json()["status"] == "OUTLINE_GENERATED"


def test_feedback_regenerates_from_edited_outline_and_keeps_prior_sources(model_client, planner):
    project = indexed_project(model_client)
    base, scope = deck(model_client, project)
    pages = model_client.post(f"{base}/outline/generate{scope}").json()["pages"]
    edited = [{**pages[0], "title": "用户改过的标题"}, *pages[1:]]
    # Tampered snapshots in the feedback body are ignored like on confirm.
    edited[0]["sources"] = [{**edited[0]["sources"][0], "excerpt": "伪造"}]
    body = {"feedback": "增加一页 AI 违规检测", "pages": edited}
    revised = model_client.post(f"{base}/outline/generate{scope}", json=body)
    assert revised.status_code == 200
    assert len(revised.json()["pages"]) == 4
    request = planner.requests[-1]
    assert request.feedback == "增加一页 AI 违规检测"
    assert request.current_pages[0].title == "用户改过的标题"
    assert request.current_pages[0].source_ids == tuple(pages[0]["sourceChunkIds"])
    assert {e.chunk_id for e in request.evidence} >= set(pages[0]["sourceChunkIds"])
    assert all(e.excerpt != "伪造" for e in request.evidence)
    # Feedback may resize; the task's page count changes only on confirm.
    assert model_client.get(f"{base}{scope}").json()["pageCount"] == 3
    confirmed = model_client.post(
        f"{base}/outline/confirm{scope}", json={"pages": revised.json()["pages"]}
    )
    assert confirmed.status_code == 200
    assert model_client.get(f"{base}{scope}").json()["pageCount"] == 4


def test_over_cited_page_is_capped_and_stays_readable(settings, planner, monkeypatch):
    settings.chunk_size = 100
    text = "".join(f"第{i}段：人员轨迹系统在第{i}号洁净室完成部署与验收。" * 4 for i in range(25))
    with TestClient(create_app(settings, embedder=EvidenceEmbedder(), planner=planner)) as client:
        base, scope = deck(client, indexed_project(client, text=text))
        with client.app.state.sessions() as db:
            ids = tuple(db.scalars(select(DocumentChunk.id).order_by(DocumentChunk.id)).all())
        assert len(ids) > 16
        # Planners are trusted only up to the API limits: >16 real citations must not poison
        # the stored row and make the outline unreadable.
        monkeypatch.setattr(planner, "plan", lambda request: [PlannedPage(1, "页", "用途", ids)])
        outline = client.post(f"{base}/outline/generate{scope}")
        assert outline.status_code == 200
        assert outline.json()["pages"][0]["sourceChunkIds"] == list(ids[:16])
        assert client.get(f"{base}/outline{scope}").status_code == 200


def test_clearance_hides_restricted_evidence_and_rejects_its_ids(settings, planner):
    # Indexed while the workspace held CONFIDENTIAL clearance, then clearance is lowered.
    with TestClient(create_app(settings, embedder=EvidenceEmbedder(), planner=planner)) as client:
        project = client.post(f"{PREFIX}/projects", json={"name": "密级"}).json()["id"]
        response = client.post(
            f"{PREFIX}/projects/{project}/documents",
            files={"file": ("机密.txt", "人员轨迹机密方案。".encode())},
            data={"securityLevel": "CONFIDENTIAL"},
        )
        assert response.status_code == 201
        assert client.app.state.ingestor.process_next()
    settings.security_clearance = "INTERNAL"
    with TestClient(create_app(settings, embedder=EvidenceEmbedder(), planner=planner)) as client:
        base, scope = deck(client, project)
        outline = client.post(f"{base}/outline/generate{scope}").json()
        assert planner.requests[-1].evidence == []
        assert "未检索到" in outline["warning"]
        with client.app.state.sessions() as db:
            secret_id = db.scalar(select(DocumentChunk.id))
        pages = [{**outline["pages"][0], "sourceChunkIds": [secret_id]}, *outline["pages"][1:]]
        response = client.post(f"{base}/outline/confirm{scope}", json={"pages": pages})
        assert response.status_code == 422 and "第 1 页" in response.json()["detail"]


def test_feedback_requires_generated_outline_and_valid_pages(model_client):
    base, scope = deck(model_client, indexed_project(model_client))
    page = {"pageNo": 1, "title": "A", "purpose": "B"}
    body = {"feedback": "合并", "pages": [page]}
    assert model_client.post(f"{base}/outline/generate{scope}", json=body).status_code == 409
    model_client.post(f"{base}/outline/generate{scope}")
    gap = {"feedback": "合并", "pages": [{**page, "pageNo": 2}]}
    assert model_client.post(f"{base}/outline/generate{scope}", json=gap).status_code == 422
    empty = {"feedback": "", "pages": [page]}
    assert model_client.post(f"{base}/outline/generate{scope}", json=empty).status_code == 422


def test_planning_failure_is_502_and_keeps_existing_outline(model_client, planner):
    base, scope = deck(model_client, indexed_project(model_client))
    first = model_client.post(f"{base}/outline/generate{scope}").json()
    planner.error = PlanningError("大纲生成服务暂不可用，请稍后重试；当前大纲未改变。")
    response = model_client.post(f"{base}/outline/generate{scope}")
    assert response.status_code == 502 and "未改变" in response.json()["detail"]
    assert model_client.get(f"{base}/outline{scope}").json() == first


def test_empty_project_warns_and_generates_without_sources(model_client):
    base, scope = deck(model_client, indexed_project(model_client, text=""))
    outline = model_client.post(f"{base}/outline/generate{scope}").json()
    assert "未检索到" in outline["warning"]
    assert all(page["sources"] == [] for page in outline["pages"])


def test_retrieval_failure_degrades_to_warning(model_client, monkeypatch):
    base, scope = deck(model_client, indexed_project(model_client))

    def broken(*args, **kwargs):
        raise RuntimeError("embedding down")

    monkeypatch.setattr(model_client.app.state.embedder, "embed_query", broken)
    outline = model_client.post(f"{base}/outline/generate{scope}")
    assert outline.status_code == 200
    assert "检索暂不可用" in outline.json()["warning"]


def test_confirm_during_generation_discards_result(model_client, planner):
    base, scope = deck(model_client, indexed_project(model_client))
    model_client.post(f"{base}/outline/generate{scope}")
    document_id = int(base.rsplit("/", 1)[-1])

    def confirm_elsewhere():
        with model_client.app.state.sessions() as db:
            db.execute(
                update(Presentation)
                .where(Presentation.id == document_id)
                .values(status="OUTLINE_CONFIRMED")
            )
            db.commit()

    planner.before_return = confirm_elsewhere
    response = model_client.post(f"{base}/outline/generate{scope}")
    assert response.status_code == 409 and "未保存" in response.json()["detail"]


def test_local_planner_rejects_feedback_with_guidance(client):
    project = client.post(f"{PREFIX}/projects", json={"name": "本地"}).json()["id"]
    base, scope = deck(client, project)
    pages = client.post(f"{base}/outline/generate{scope}").json()["pages"]
    assert pages[0]["sources"] == [] and pages[0]["sourceChunkIds"] == []
    response = client.post(
        f"{base}/outline/generate{scope}", json={"feedback": "合并", "pages": pages}
    )
    assert response.status_code == 409 and "模型服务" in response.json()["detail"]
    assert client.get(f"{base}{scope}").json()["status"] == "OUTLINE_GENERATED"
