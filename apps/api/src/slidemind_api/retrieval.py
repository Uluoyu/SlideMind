"""Project-filtered evidence search; no model-written citations."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import select, type_coerce

from slidemind_api.models import Document, DocumentChunk
from slidemind_common.security import allowed_levels
from slidemind_rag.embeddings import validate_vectors
from slidemind_rag.rank import Candidate, rank_candidates
from slidemind_schemas.page import SourceReference


def location_for(chunk):
    metadata = chunk.metadata_json
    if chunk.page_no:
        return f"第 {chunk.page_no} 页"
    if metadata.get("location"):
        return str(metadata["location"])
    if metadata.get("paragraph_index"):
        return f"第 {metadata['paragraph_index']} 段"
    if metadata.get("table_index"):
        return f"表 {metadata['table_index']}，第 {metadata.get('row_index', 1)} 行"
    return f"片段 {chunk.chunk_index + 1}"


class DatabaseRetriever:
    def __init__(
        self, sessions, embedder, min_similarity=0.5, reranker=None, min_rerank_score=0.05
    ):
        self.sessions, self.embedder = sessions, embedder
        self.min_similarity = min_similarity
        self.reranker, self.min_rerank_score = reranker, min_rerank_score
        self.mode, self.warning = "hybrid", None

    def hits(self, query, context):
        with self.sessions() as db:
            filters = (
                Document.project_id == context.project_id,
                Document.security_level.in_(allowed_levels(context.clearance)),
                Document.status == "READY",
                Document.embedding_model == self.embedder.model_id,
                Document.embedding_dimensions == self.embedder.dimensions,
            )
            # Avoid loading a model for an empty project; no DB transaction during inference.
            if db.scalar(select(Document.id).where(*filters).limit(1)) is None:
                return []
        vector = validate_vectors([self.embedder.embed_query(query)], 1, self.embedder.dimensions)[
            0
        ]
        with self.sessions() as db:
            statement = select(DocumentChunk, Document).join(Document).where(*filters)
            # Exact pgvector cosine search for the personal corpus. Both branches filter
            # before ranking; SQLite uses the same ranking over normalized stored vectors.
            if db.bind.dialect.name == "postgresql":
                distance = type_coerce(DocumentChunk.embedding, Vector()).cosine_distance(vector)
                rows = db.execute(
                    statement.add_columns(distance.label("distance")).order_by(distance)
                ).all()
                candidates = [
                    Candidate(
                        chunk.id,
                        chunk.content,
                        list(chunk.embedding),
                        similarity=1.0 - float(value),
                    )
                    for chunk, _, value in rows
                ]
            else:
                rows = db.execute(statement).all()
                candidates = [
                    Candidate(chunk.id, chunk.content, chunk.embedding) for chunk, _ in rows
                ]
            ranked = rank_candidates(
                query,
                vector,
                candidates,
                top_k=max(20, context.top_k) if self.reranker else context.top_k,
                min_similarity=self.min_similarity,
            )
            by_id = {row[0].id: (row[0], row[1]) for row in rows}
            # Close the read transaction before the external reranker call. Only already
            # authorized chunks are sent; recheck document state before publishing below.
            db.expunge_all()
            db.rollback()
            scored = [(hit, hit.score) for hit in ranked]
            if self.reranker and ranked:
                try:
                    reranked = self.reranker.rerank(
                        query, [by_id[hit.chunk_id][0].content for hit in ranked]
                    )
                    scored = [
                        (ranked[index], score)
                        for index, score in reranked
                        if score >= self.min_rerank_score
                    ]
                    self.mode = "hybrid-rerank"
                except Exception:
                    self.warning = "重排服务暂不可用，当前显示初步检索结果。"
            # A reindex may have completed while the external service was working.
            valid_ids = set(
                db.scalars(
                    select(DocumentChunk.id)
                    .join(Document)
                    .where(*filters, DocumentChunk.id.in_([hit.chunk_id for hit, _ in scored]))
                ).all()
            )
            hits = []
            for hit, score in scored:
                if hit.chunk_id not in valid_ids:
                    continue
                chunk, document = by_id[hit.chunk_id]
                hits.append(
                    dict(
                        chunk_id=chunk.id,
                        score=score,
                        source=SourceReference(
                            document_id=document.id,
                            file_name=document.file_name,
                            page_no=chunk.page_no,
                            excerpt=chunk.content,
                        ),
                        location=location_for(chunk),
                    )
                )
                if len(hits) == context.top_k:
                    break
            return hits

    def search(self, query, context):
        return [hit["source"] for hit in self.hits(query, context)]
