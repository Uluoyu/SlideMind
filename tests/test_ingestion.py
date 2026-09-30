from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from slidemind_api.main import create_app
from slidemind_api.models import Document, DocumentChunk


class EvidenceEmbedder:
    """Small external-model substitute; storage, workers and retrieval stay real."""

    dimensions = 3
    model_id = "test-evidence-v1"

    def embed(self, texts):
        return [[1.0, 0.0, 0.0] if "轨迹" in t else [0.0, 1.0, 0.0] for t in texts]

    def embed_query(self, query):
        return self.embed([query])[0]


@pytest.fixture
def rag_client(settings):
    settings.ingestion_enabled = False
    with TestClient(create_app(settings, embedder=EvidenceEmbedder())) as client:
        yield client


def upload(client, text="人员轨迹系统记录洁净室人员的位置。", name="方案.txt", level="INTERNAL"):
    project = client.post("/api/ppt/projects", json={"name": name}).json()["id"]
    base = f"/api/ppt/projects/{project}"
    response = client.post(
        f"{base}/documents",
        files={"file": (name, text.encode())},
        data={"securityLevel": level},
    )
    assert response.status_code == 201
    return base, response.json()


def test_upload_process_search_and_source_survive_restart(rag_client, settings):
    base, doc = upload(rag_client)
    assert doc["status"] == "QUEUED"
    assert rag_client.app.state.ingestor.process_next()
    ready = rag_client.get(f"{base}/documents").json()[0]
    assert ready["status"] == "READY"
    assert ready["chunkCount"] == 1
    assert ready["processedAt"]
    response = rag_client.post(f"{base}/search", json={"query": "人员轨迹"})
    assert response.status_code == 200
    hit = response.json()["hits"][0]
    assert hit["source"]["document_id"] == doc["id"]
    assert hit["source"]["excerpt"] == "人员轨迹系统记录洁净室人员的位置。"
    source_path = f"{base}/documents/{doc['id']}/chunks/{hit['chunkId']}"
    assert rag_client.get(source_path).json()["content"] == hit["source"]["excerpt"]
    with TestClient(create_app(settings, embedder=EvidenceEmbedder())) as restarted:
        assert restarted.get(source_path).json()["content"] == hit["source"]["excerpt"]
        assert restarted.post(f"{base}/search", json={"query": "人员轨迹"}).json()["hits"]


def test_pending_retry_is_idempotent_and_reindex_replaces_chunks(rag_client):
    base, doc = upload(rag_client)
    process = f"{base}/documents/{doc['id']}/process"
    for _ in range(2):
        assert rag_client.post(process).status_code == 202
    assert rag_client.app.state.ingestor.process_next()
    assert not rag_client.app.state.ingestor.process_next()
    assert rag_client.post(process).status_code == 202
    assert rag_client.post(f"{base}/search", json={"query": "轨迹"}).json()["hits"] == []
    assert rag_client.app.state.ingestor.process_next()
    with rag_client.app.state.sessions() as db:
        assert len(db.scalars(select(DocumentChunk)).all()) == 1
        assert db.get(Document, doc["id"]).attempts == 2


def test_failed_parse_and_model_can_retry_without_partial_index(rag_client, monkeypatch):
    base, doc = upload(rag_client, name="损坏.pdf")
    rag_client.app.state.ingestor.process_next()
    failed = rag_client.get(f"{base}/documents").json()[0]
    assert failed["status"] == "FAILED"
    assert failed["processingError"]
    assert failed["chunkCount"] == 0
    assert rag_client.post(f"{base}/documents/{doc['id']}/process").status_code == 202
    assert rag_client.app.state.ingestor.process_next()
    assert rag_client.get(f"{base}/documents").json()[0]["status"] == "FAILED"

    base, doc = upload(rag_client)
    with monkeypatch.context() as patch:
        patch.setattr(rag_client.app.state.embedder, "embed", lambda texts: [[float("nan")] * 3])
        rag_client.app.state.ingestor.process_next()
    assert rag_client.get(f"{base}/documents").json()[0]["status"] == "FAILED"
    with rag_client.app.state.sessions() as db:
        assert db.scalars(select(DocumentChunk)).all() == []
    rag_client.post(f"{base}/documents/{doc['id']}/process")
    rag_client.app.state.ingestor.process_next()
    assert rag_client.get(f"{base}/documents").json()[0]["status"] == "READY"


def test_expired_job_recovers_and_live_lease_is_not_stolen(rag_client):
    base, doc = upload(rag_client)
    with rag_client.app.state.sessions() as db:
        row = db.get(Document, doc["id"])
        row.status = "INDEXING"
        row.lease_token = "interrupted-worker"
        row.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        db.commit()
    assert not rag_client.app.state.ingestor.process_next()
    with rag_client.app.state.sessions() as db:
        db.get(Document, doc["id"]).lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert rag_client.app.state.ingestor.process_next()
    assert rag_client.get(f"{base}/documents").json()[0]["status"] == "READY"


def test_project_clearance_filters_search_details_and_retries(rag_client):
    base, doc = upload(rag_client)
    secret_base, secret = upload(rag_client, "人员轨迹绝密测试数据", level="CONFIDENTIAL")
    # Another file in the same project exercises clearance before ranking.
    hidden = rag_client.post(
        f"{base}/documents",
        files={"file": ("机密.txt", "人员轨迹机密".encode())},
        data={"securityLevel": "CONFIDENTIAL"},
    ).json()
    while rag_client.app.state.ingestor.process_next():
        pass
    hit = rag_client.post(f"{base}/search", json={"query": "人员轨迹"}).json()["hits"][0]
    wrong_source = f"{secret_base}/documents/{doc['id']}/chunks/{hit['chunkId']}"
    assert rag_client.get(wrong_source).status_code == 404
    assert rag_client.post(f"{base}/documents/{secret['id']}/process").status_code == 404
    from slidemind_common.security import SecurityLevel

    rag_client.app.state.settings.security_clearance = SecurityLevel.INTERNAL
    hits = rag_client.post(f"{base}/search", json={"query": "人员轨迹"}).json()["hits"]
    assert [h["source"]["document_id"] for h in hits] == [doc["id"]]
    assert rag_client.post(f"{base}/documents/{hidden['id']}/process").status_code == 404
    assert rag_client.post(f"{secret_base}/search", json={"query": "人员轨迹"}).json()["hits"] == []


def test_search_validation_no_match_and_model_version_filter(rag_client):
    base, doc = upload(rag_client)
    rag_client.app.state.ingestor.process_next()
    assert rag_client.post(f"{base}/search", json={"query": "   "}).status_code == 422
    assert rag_client.post(f"{base}/search", json={"query": "a", "topK": 100}).status_code == 422
    assert rag_client.post(f"{base}/search", json={"query": "海洋珊瑚"}).json()["hits"] == []
    rag_client.app.state.embedder.model_id = "different-model-version"
    assert rag_client.post(f"{base}/search", json={"query": "人员轨迹"}).json()["hits"] == []


def test_reranker_only_receives_authorized_candidates_and_failure_is_visible(rag_client):
    base, doc = upload(rag_client)
    upload(rag_client, "人员轨迹其他项目机密内容")
    while rag_client.app.state.ingestor.process_next():
        pass

    class Reranker:
        def rerank(self, query, documents):
            assert documents == ["人员轨迹系统记录洁净室人员的位置。"]
            return [(0, 0.97)]

        def close(self):
            pass

    rag_client.app.state.reranker = Reranker()
    result = rag_client.post(f"{base}/search", json={"query": "人员轨迹"})
    assert result.json()["mode"] == "hybrid-rerank"
    assert result.json()["hits"][0]["score"] == 0.97
    assert result.headers["cache-control"] == "no-store"

    def fail(query, documents):
        raise OSError("unavailable")

    rag_client.app.state.reranker.rerank = fail
    result = rag_client.post(f"{base}/search", json={"query": "人员轨迹"}).json()
    assert result["mode"] == "hybrid"
    assert result["warning"]
    assert result["hits"][0]["source"]["document_id"] == doc["id"]


def test_reindex_during_reranking_does_not_publish_old_chunks(rag_client):
    base, doc = upload(rag_client)
    rag_client.app.state.ingestor.process_next()
    with rag_client.app.state.sessions() as db:
        old_id = db.scalar(select(DocumentChunk.id))

    class ReindexingReranker:
        def rerank(self, query, documents):
            rag_client.post(f"{base}/documents/{doc['id']}/process")
            rag_client.app.state.ingestor.process_next()
            return [(0, 0.99)]

        def close(self):
            pass

    rag_client.app.state.reranker = ReindexingReranker()
    result = rag_client.post(f"{base}/search", json={"query": "人员轨迹"})
    assert result.json()["hits"] == []
    assert rag_client.get(f"{base}/documents/{doc['id']}/chunks/{old_id}").status_code == 404


def test_shutdown_during_model_request_requeues_the_owned_job(rag_client, monkeypatch):
    base, doc = upload(rag_client)
    worker = rag_client.app.state.ingestor

    def interrupted(texts):
        worker.stop()
        raise OSError("HTTP client closed during shutdown")

    monkeypatch.setattr(rag_client.app.state.embedder, "embed", interrupted)
    assert worker.process_next()
    row = rag_client.get(f"{base}/documents").json()[0]
    assert row["status"] == "QUEUED"
    assert row["processingError"] is None
    with rag_client.app.state.sessions() as db:
        assert db.get(Document, doc["id"]).lease_token is None
        assert db.scalars(select(DocumentChunk)).all() == []


def test_superseded_worker_stops_sending_embedding_batches(rag_client, monkeypatch):
    _, doc = upload(rag_client, "人员轨迹证据。" * 2000)
    transmitted = []
    provider = rag_client.app.state.embedder
    original_embed = provider.embed

    def replaced(texts):
        transmitted.append(texts)
        with rag_client.app.state.sessions() as db:
            row = db.get(Document, doc["id"])
            row.status = "READY"
            row.lease_token = "replacement-worker"
            db.commit()
        return original_embed(texts)

    monkeypatch.setattr(provider, "embed", replaced)
    assert rag_client.app.state.ingestor.process_next()
    assert len(transmitted) == 1
    with rag_client.app.state.sessions() as db:
        row = db.get(Document, doc["id"])
        assert row.status == "READY" and row.lease_token == "replacement-worker"
