from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import select, update

from slidemind_api.contracts import DTO, DocumentView
from slidemind_api.models import Document, DocumentChunk
from slidemind_api.retrieval import DatabaseRetriever
from slidemind_api.routes import DB, project_or_404
from slidemind_common.security import allowed_levels
from slidemind_rag.contracts import RetrievalContext
from slidemind_schemas.page import SourceReference

router = APIRouter(prefix="/api/ppt/projects", tags=["knowledge"])


class SearchInput(DTO):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHit(DTO):
    chunk_id: int
    score: float
    source: SourceReference
    location: str | None


class SearchView(DTO):
    query: str
    hits: list[SearchHit]
    mode: str = "hybrid"
    warning: str | None = None


class ChunkView(DTO):
    id: int
    chunk_index: int
    page_no: int | None
    content: str
    metadata: dict


def document_for(db, request, project_id, document_id):
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
            Document.security_level.in_(
                allowed_levels(request.app.state.settings.security_clearance)
            ),
        )
    )
    if document is None:
        raise HTTPException(404, "资料不存在")
    return document


@router.post(
    "/{project_id}/documents/{document_id}/process", response_model=DocumentView, status_code=202
)
def process_document(project_id: int, document_id: int, request: Request, db: DB):
    document_for(db, request, project_id, document_id)
    db.execute(
        update(Document)
        .where(Document.id == document_id, Document.status.in_(("UPLOADED", "FAILED", "READY")))
        .values(status="QUEUED", processing_error=None, lease_token=None, lease_expires_at=None)
    )
    db.commit()
    db.expire_all()
    return document_for(db, request, project_id, document_id)


@router.post("/{project_id}/search", response_model=SearchView)
def search(project_id: int, body: SearchInput, request: Request, response: Response, db: DB):
    response.headers["Cache-Control"] = "no-store"
    project_or_404(db, project_id)
    db.rollback()
    settings = request.app.state.settings
    retriever = DatabaseRetriever(
        request.app.state.sessions,
        request.app.state.embedder,
        settings.retrieval_min_similarity,
        request.app.state.reranker,
        settings.reranker_min_score,
    )
    try:
        hits = retriever.hits(
            body.query, RetrievalContext(project_id, settings.security_clearance, body.top_k)
        )
    except Exception as exc:
        raise HTTPException(503, "资料检索暂不可用，请检查索引和向量模型后重试。") from exc
    return dict(query=body.query, hits=hits, mode=retriever.mode, warning=retriever.warning)


@router.get("/{project_id}/documents/{document_id}/chunks/{chunk_id}", response_model=ChunkView)
def source_chunk(
    project_id: int, document_id: int, chunk_id: int, request: Request, response: Response, db: DB
):
    response.headers["Cache-Control"] = "no-store"
    document = document_for(db, request, project_id, document_id)
    if document.status != "READY":
        raise HTTPException(409, "资料尚未完成索引，请等待处理完成后重新检索。")
    chunk = db.scalar(
        select(DocumentChunk).where(
            DocumentChunk.id == chunk_id, DocumentChunk.document_id == document_id
        )
    )
    if chunk is None:
        raise HTTPException(404, "原文片段不存在，请重新检索。")
    return dict(
        id=chunk.id,
        chunk_index=chunk.chunk_index,
        page_no=chunk.page_no,
        content=chunk.content,
        metadata=chunk.metadata_json,
    )
