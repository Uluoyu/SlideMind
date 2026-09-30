from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from slidemind_api.config import Settings
from slidemind_api.db import create_database
from slidemind_api.ingestion import Ingestor
from slidemind_api.knowledge_routes import router as knowledge_router
from slidemind_api.page_routes import router as page_router
from slidemind_api.rendering import HttpRenderer
from slidemind_api.routes import router
from slidemind_api.storage import LocalStore, MinioStore
from slidemind_rag.embeddings import FastEmbedder
from slidemind_rag.remote import HttpEmbedder, HttpReranker


def create_app(settings: Settings | None = None, *, embedder=None) -> FastAPI:
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
        app.state.embedder = embedder or (
            HttpEmbedder(
                settings.embedding_url,
                settings.embedding_model,
                settings.embedding_dimensions,
                query_instruction=settings.embedding_query_instruction,
                revision=settings.embedding_revision,
                timeout=settings.embedding_timeout_seconds,
                api_key=settings.embedding_api_key.get_secret_value(),
            )
            if settings.embedding_provider == "http"
            else FastEmbedder(
                settings.embedding_model, settings.embedding_cache_dir, settings.embedding_threads
            )
        )
        app.state.reranker = (
            HttpReranker(
                settings.reranker_url,
                settings.reranker_model,
                input_format=settings.reranker_input_format,
                timeout=settings.reranker_timeout_seconds,
                api_key=settings.reranker_api_key.get_secret_value(),
            )
            if settings.reranker_url
            else None
        )
        app.state.ingestor = Ingestor(sessions, app.state.store, app.state.embedder, settings)
        if settings.ingestion_enabled:
            app.state.ingestor.start()
        try:
            yield
        finally:
            app.state.ingestor.stop()
            if embedder is None and isinstance(app.state.embedder, HttpEmbedder):
                app.state.embedder.close()
            if app.state.reranker:
                app.state.reranker.close()
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
    app.include_router(knowledge_router)

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
