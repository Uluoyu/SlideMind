"""Small persistent queue: claim with a lease, publish chunks atomically."""

import logging
from datetime import timedelta
from io import BytesIO
from threading import Event, Thread
from uuid import uuid4

from sqlalchemy import and_, delete, or_, select, update

from slidemind_api.models import Document, DocumentChunk, utcnow
from slidemind_common.security import allowed_levels
from slidemind_parser.chunking import chunk_sections
from slidemind_parser.parsers import parse_document
from slidemind_rag.embeddings import validate_vectors

logger = logging.getLogger(__name__)
ACTIVE = ("PARSING", "INDEXING")


class Ingestor:
    def __init__(self, sessions, store, embedder, settings):
        self.sessions, self.store = sessions, store
        self.embedder, self.settings = embedder, settings
        self._stop = Event()
        self._thread = None
        self._active_claim = None

    def start(self):
        self._thread = Thread(target=self._run, name="document-ingestion", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._active_claim:
            try:
                self._release(*self._active_claim)
            except Exception:
                # If the database is unavailable, the persisted lease still expires.
                logger.exception("Could not release processing lease during shutdown")
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.is_set():
            try:
                if self.process_next():
                    continue
            except Exception:
                logger.exception("Document queue temporarily unavailable")
            self._stop.wait(self.settings.ingestion_poll_seconds)

    def _eligible(self):
        return and_(
            Document.security_level.in_(allowed_levels(self.settings.security_clearance)),
            or_(
                Document.status.in_(("QUEUED", "UPLOADED")),
                and_(
                    Document.status.in_(ACTIVE),
                    or_(Document.lease_expires_at < utcnow(), Document.lease_expires_at.is_(None)),
                ),
            ),
        )

    def _claim(self):
        with self.sessions() as db:
            document_id = db.scalar(
                select(Document.id).where(self._eligible()).order_by(Document.id).limit(1)
            )
            if document_id is None:
                return None
            token = uuid4().hex
            claimed = db.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    self._eligible(),
                )
                .values(
                    status="PARSING",
                    lease_token=token,
                    processing_error=None,
                    lease_expires_at=utcnow()
                    + timedelta(seconds=self.settings.ingestion_lease_seconds),
                    attempts=Document.attempts + 1,
                )
            )
            db.commit()
            if not claimed.rowcount:
                return None
            return db.get(Document, document_id), token

    def _owned(self, document_id, token):
        return (
            Document.id == document_id,
            Document.lease_token == token,
            Document.status.in_(ACTIVE),
        )

    def _renew(self, document_id, token, finished):
        while not finished.wait(self.settings.ingestion_lease_seconds / 3):
            if self._stop.is_set():
                return
            try:
                with self.sessions() as db:
                    updated = db.execute(
                        update(Document)
                        .where(*self._owned(document_id, token))
                        .values(
                            lease_expires_at=utcnow()
                            + timedelta(seconds=self.settings.ingestion_lease_seconds)
                        )
                    )
                    db.commit()
                    if not updated.rowcount:
                        return
            except Exception:
                logger.exception("Could not renew document processing lease")

    def process_next(self):
        if self._stop.is_set():
            return False
        claimed = self._claim()
        if claimed is None:
            return False
        document, token = claimed
        self._active_claim = (document.id, token)
        if self._stop.is_set():
            self._release(document.id, token)
            self._active_claim = None
            return True
        finished = Event()
        heartbeat = Thread(target=self._renew, args=(document.id, token, finished), daemon=True)
        heartbeat.start()
        stage = "parse"
        try:
            sections = parse_document(
                BytesIO(self.store.get(document.storage_path)), document.file_type
            )
            chunks = chunk_sections(sections, max_chars=self.settings.chunk_size, overlap=60)
            if not chunks or len(chunks) > 10000:
                raise ValueError("文档没有可索引文本，或内容过多，请拆分后上传。")
            with self.sessions() as db:
                result = db.execute(
                    update(Document)
                    .where(*self._owned(document.id, token))
                    .values(status="INDEXING")
                )
                db.commit()
                if not result.rowcount:
                    return True
            stage = "embed"
            vectors = []
            model_id, dimensions = self.embedder.model_id, self.embedder.dimensions
            for start in range(0, len(chunks), 32):
                if self._stop.is_set():
                    self._release(document.id, token)
                    return True
                with self.sessions() as db:
                    if (
                        db.scalar(select(Document.id).where(*self._owned(document.id, token)))
                        is None
                    ):
                        return True
                batch = chunks[start : start + 32]
                vectors.extend(
                    validate_vectors(
                        self.embedder.embed([chunk.text for chunk in batch]), len(batch), dimensions
                    )
                )
            if self._stop.is_set():
                self._release(document.id, token)
                return True
            # A worker whose lease was superseded cannot publish or erase another index.
            with self.sessions() as db:
                result = db.execute(
                    update(Document)
                    .where(*self._owned(document.id, token))
                    .values(
                        status="READY",
                        processing_error=None,
                        chunk_count=len(chunks),
                        processed_at=utcnow(),
                        embedding_model=model_id,
                        embedding_dimensions=dimensions,
                        lease_token=None,
                        lease_expires_at=None,
                    )
                )
                if not result.rowcount:
                    db.rollback()
                    return True
                db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
                db.add_all(
                    DocumentChunk(
                        document_id=document.id,
                        content=chunk.text,
                        page_no=chunk.page_no,
                        chunk_index=index,
                        metadata_json=chunk.metadata,
                        embedding=vectors[index],
                    )
                    for index, chunk in enumerate(chunks)
                )
                db.commit()
        except Exception as exc:
            if self._stop.is_set():
                self._release(document.id, token)
                return True
            if stage == "parse" and isinstance(exc, ValueError):
                logger.warning("Document %s could not be parsed: %s", document.id, exc)
            else:
                logger.exception("Document %s processing failed at %s", document.id, stage)
            message = (
                str(exc)[:500]
                if stage == "parse" and isinstance(exc, ValueError)
                else "文档读取失败，请检查文件后重试。"
                if stage == "parse"
                else "资料索引失败，请检查向量模型是否可用后重试。"
            )
            with self.sessions() as db:
                db.execute(
                    update(Document)
                    .where(*self._owned(document.id, token))
                    .values(
                        status="FAILED",
                        processing_error=message,
                        lease_token=None,
                        lease_expires_at=None,
                    )
                )
                db.commit()
        finally:
            self._active_claim = None
            finished.set()
            heartbeat.join(timeout=1)
        return True

    def _release(self, document_id, token):
        with self.sessions() as db:
            db.execute(
                update(Document)
                .where(*self._owned(document_id, token))
                .values(status="QUEUED", lease_token=None, lease_expires_at=None)
            )
            db.commit()
