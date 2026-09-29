from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from slidemind_api.config import Settings
from slidemind_api.db import create_database
from slidemind_api.page_routes import router as page_router
from slidemind_api.rendering import HttpRenderer
from slidemind_api.routes import router
from slidemind_api.storage import LocalStore, MinioStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessions = create_database(settings.database_url)
        app.state.engine = engine
        app.state.sessions = sessions
        app.state.settings = settings
        app.state.store = (
            LocalStore(settings.storage_root)
            if settings.storage_backend == "local"
            else MinioStore(settings)
        )
        app.state.renderer = HttpRenderer(settings.renderer_url, settings.renderer_timeout_seconds)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="SlideMind API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    app.include_router(page_router)

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "service": "slidemind-api", "version": "0.1.0"}

    @app.get("/ready", tags=["system"])
    def ready():
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT id FROM ppt_project LIMIT 1"))
        except Exception as exc:
            raise HTTPException(503, "数据库未就绪，请先执行数据库迁移") from exc
        return {"status": "ready", "database": "ok"}

    return app


app = create_app()
