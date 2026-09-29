"""Run an isolated API for browser tests. Each run gets a separate artifact directory."""

import os
from pathlib import Path
from uuid import uuid4

import uvicorn
from alembic import command
from alembic.config import Config

from slidemind_api.config import Settings
from slidemind_api.main import create_app

root = Path("artifacts/e2e") / uuid4().hex
root.mkdir(parents=True)
database_url = f"sqlite:///{(root / 'test.db').as_posix()}"
os.environ["SLIDEMIND_DATABASE_URL"] = database_url
command.upgrade(Config("alembic.ini"), "head")
settings = Settings(
    _env_file=None,
    database_url=database_url,
    storage_backend="local",
    storage_root=root / "storage",
)
uvicorn.run(create_app(settings), host="127.0.0.1", port=8001)
