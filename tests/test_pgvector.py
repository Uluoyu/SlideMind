"""Opt-in PostgreSQL integration. Use a disposable database with pgvector support."""

import os
import time
from uuid import uuid4

import pymupdf
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from test_ingestion import EvidenceEmbedder, upload

from slidemind_api.config import Settings
from slidemind_api.main import create_app
from slidemind_api.models import Document, DocumentChunk
from slidemind_common.security import SecurityLevel

pytestmark = pytest.mark.skipif(
    not os.environ.get("SLIDEMIND_TEST_POSTGRES_URL"),
    reason="Set SLIDEMIND_TEST_POSTGRES_URL to a disposable PostgreSQL/pgvector database",
)


@pytest.fixture
def pg_settings(tmp_path, monkeypatch):
    url = make_url(os.environ["SLIDEMIND_TEST_POSTGRES_URL"])
    engine = create_engine(url)
    schema = "phase2_" + uuid4().hex
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT to_regclass('public.alembic_version')")) is None, (
            "Use an empty disposable database: public contains an Alembic version table"
        )
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema},public"})
    monkeypatch.setenv("SLIDEMIND_DATABASE_URL", scoped.render_as_string(hide_password=False))

    def set_test_schema(connection, _):
        # PGlite's TCP adapter ignores startup options. Set and verify the schema
        # explicitly, so repeated runs cannot migrate or write public tables.
        autocommit = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SET SESSION search_path TO "{schema}", public')
                cursor.execute("SELECT current_schema()")
                assert cursor.fetchone()[0] == schema
        finally:
            connection.autocommit = autocommit

    event.listen(Engine, "connect", set_test_schema)
    try:
        command.upgrade(Config("alembic.ini"), "head")
        yield Settings(
            _env_file=None,
            database_url=str(scoped.render_as_string(hide_password=False)),
            storage_root=tmp_path / "storage",
            ingestion_enabled=False,
        )
    finally:
        event.remove(Engine, "connect", set_test_schema)
        # Only the randomly named schema created above belongs to this test.
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def pg_client(pg_settings):
    with TestClient(create_app(pg_settings, embedder=EvidenceEmbedder())) as client:
        with client.app.state.sessions() as db:
            assert db.scalar(text("SELECT current_schema()")).startswith("phase2_")
            assert db.scalar(text("SELECT count(*) FROM ppt_document")) == 0
        yield client


def test_postgres_migration_worker_vectors_scope_and_reindex(pg_client):
    base, doc = upload(pg_client)
    other_base, other_doc = upload(pg_client, "人员轨迹保密证据", level="CONFIDENTIAL")
    while pg_client.app.state.ingestor.process_next():
        pass
    with pg_client.app.state.sessions() as db:
        assert db.scalar(text("SELECT vector_dims(embedding) FROM ppt_document_chunk LIMIT 1")) == 3
        version = db.scalar(text("SELECT version()"))
        assert "PostgreSQL" in version
        # Different dimension in another project must be filtered before cosine evaluation.
        row = db.get(Document, other_doc["id"])
        row.embedding_dimensions = 2
        chunk = db.query(DocumentChunk).filter_by(document_id=row.id).one()
        chunk.embedding = [1, 0]
        db.commit()
    response = pg_client.post(f"{base}/search", json={"query": "人员轨迹"})
    assert response.status_code == 200, response.text
    assert [hit["source"]["document_id"] for hit in response.json()["hits"]] == [doc["id"]]
    old_id = response.json()["hits"][0]["chunkId"]
    pg_client.post(f"{base}/documents/{doc['id']}/process")
    pg_client.app.state.ingestor.process_next()
    assert pg_client.get(f"{base}/documents/{doc['id']}/chunks/{old_id}").status_code == 404
    pg_client.app.state.settings.security_clearance = SecurityLevel.PUBLIC
    assert pg_client.post(f"{base}/search", json={"query": "人员轨迹"}).json()["hits"] == []
    assert pg_client.post(f"{other_base}/search", json={"query": "人员轨迹"}).json()["hits"] == []


@pytest.mark.skipif(
    os.environ.get("SLIDEMIND_TEST_REMOTE_MODELS") != "1"
    or os.environ.get("SLIDEMIND_TEST_MINIO") != "1",
    reason="Enable remote models and MinIO to verify the entire PostgreSQL RAG flow",
)
def test_postgres_minio_remote_models_pdf_and_restart(pg_settings):
    settings = Settings(database_url=pg_settings.database_url, ingestion_poll_seconds=0.1)
    assert settings.storage_backend == "minio"
    assert settings.embedding_provider == "http"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 60), "Project verification")
        pdf.new_page().insert_text((50, 60), "AI违规检测准确率达到百分之九十。", fontname="china-s")
        content = pdf.tobytes()

    store, key = None, None
    try:
        with TestClient(create_app(settings)) as client:
            assert client.get("/ready").status_code == 200
            project = client.post("/api/ppt/projects", json={"name": "完整服务验收"}).json()["id"]
            base = f"/api/ppt/projects/{project}"
            uploaded = client.post(
                f"{base}/documents", files={"file": ("验收报告.pdf", content)}
            )
            assert uploaded.status_code == 201, uploaded.text
            document_id = uploaded.json()["id"]
            with client.app.state.sessions() as db:
                key = db.get(Document, document_id).storage_path
            store = client.app.state.store
            assert store.get(key) == content

            deadline = time.monotonic() + 60
            while True:
                document = client.get(f"{base}/documents").json()[0]
                assert document["status"] != "FAILED", document
                if document["status"] == "READY":
                    break
                assert time.monotonic() < deadline, document
                time.sleep(0.1)
            with client.app.state.sessions() as db:
                dimensions = db.scalar(
                    text("SELECT vector_dims(embedding) FROM ppt_document_chunk LIMIT 1")
                )
                assert dimensions == settings.embedding_dimensions
                assert db.scalar(text("SELECT current_schema()")).startswith("phase2_")

        # A new API instance must retrieve the persisted index with the actual providers.
        with TestClient(create_app(settings)) as client:
            response = client.post(f"{base}/search", json={"query": "AI违规检测准确率是多少"})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["mode"] == "hybrid-rerank" and result["warning"] is None
            hit = result["hits"][0]
            assert hit["source"]["document_id"] == document_id
            assert hit["source"]["page_no"] == 2
            assert "百分之九十" in hit["source"]["excerpt"]
            source = client.get(f"{base}/documents/{document_id}/chunks/{hit['chunkId']}")
            assert source.status_code == 200
            assert source.json()["content"] == hit["source"]["excerpt"]
            other = client.post("/api/ppt/projects", json={"name": "隔离验收"}).json()["id"]
            other_base = f"/api/ppt/projects/{other}"
            assert client.post(
                f"{other_base}/search", json={"query": "AI违规检测准确率是多少"}
            ).json()["hits"] == []
            assert client.get(
                f"{other_base}/documents/{document_id}/chunks/{hit['chunkId']}"
            ).status_code == 404
            print("Actual PostgreSQL + MinIO + remote models: PDF page 2, restart, scope OK")
    finally:
        if store is not None and key is not None:
            store.delete(key)
