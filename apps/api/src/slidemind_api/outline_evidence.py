"""Project evidence for the outline planner, and server-side resolution of outline citations."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from slidemind_agent.planner import Evidence
from slidemind_api.models import Document, DocumentChunk
from slidemind_api.retrieval import DatabaseRetriever, location_for
from slidemind_common.security import allowed_levels
from slidemind_rag.contracts import RetrievalContext

logger = logging.getLogger(__name__)

MAX_EVIDENCE = 8
MAX_PRIOR_EVIDENCE = 16  # citations carried over from the edited outline on feedback
PER_QUERY = 5
EXCERPT_CHARS = 400
NO_EVIDENCE = "未检索到可用的项目资料，大纲仅依据需求生成；请上传资料或在页面阶段补充来源。"
RETRIEVAL_FAILED = "资料检索暂不可用，大纲仅依据需求生成；可稍后重新生成。"


def gather_evidence(
    app_state, project_id: int, queries: list[str]
) -> tuple[list[Evidence], str | None]:
    """Search each query, keep the best-scoring distinct chunks. Never raises."""
    settings = app_state.settings
    retriever = DatabaseRetriever(
        app_state.sessions,
        app_state.embedder,
        settings.retrieval_min_similarity,
        app_state.reranker,
        settings.reranker_min_score,
    )
    context = RetrievalContext(project_id, settings.security_clearance, PER_QUERY)
    best: dict[int, tuple[float, Evidence]] = {}
    try:
        for query in dict.fromkeys(q.strip()[:500] for q in queries if q.strip()):
            for hit in retriever.hits(query, context):
                source = hit["source"]
                item = Evidence(
                    hit["chunk_id"],
                    source.file_name,
                    hit["location"],
                    source.excerpt[:EXCERPT_CHARS],
                )
                if hit["chunk_id"] not in best or hit["score"] > best[hit["chunk_id"]][0]:
                    best[hit["chunk_id"]] = (hit["score"], item)
    except Exception:
        logger.exception("Outline evidence retrieval failed for project %s", project_id)
        return [], RETRIEVAL_FAILED
    ranked = sorted(best.values(), key=lambda pair: (-pair[0], pair[1].chunk_id))
    evidence = [item for _, item in ranked[:MAX_EVIDENCE]]
    return evidence, (None if evidence else NO_EVIDENCE)


def resolve_sources(db: Session, project_id: int, clearance, chunk_ids) -> dict[int, dict]:
    """Snapshot authorized chunks by id; ids outside the project/clearance are omitted."""
    ids = set(chunk_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document)
        .where(
            DocumentChunk.id.in_(ids),
            Document.project_id == project_id,
            Document.security_level.in_(allowed_levels(clearance)),
            Document.status == "READY",
        )
    ).all()
    return {
        chunk.id: dict(
            chunk_id=chunk.id,
            document_id=document.id,
            file_name=document.file_name,
            page_no=chunk.page_no,
            location=location_for(chunk),
            excerpt=chunk.content[:EXCERPT_CHARS],
        )
        for chunk, document in rows
    }
