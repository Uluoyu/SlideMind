import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from slidemind_api.config import Settings
from slidemind_api.main import create_app


@pytest.fixture
def settings(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("SLIDEMIND_DATABASE_URL", database_url)
    command.upgrade(Config("alembic.ini"), "head")
    return Settings(
        _env_file=None,
        database_url=database_url,
        storage_root=tmp_path / "storage",
        storage_backend="local",
        max_upload_mb=1,
        security_clearance="CONFIDENTIAL",
        ingestion_enabled=False,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
