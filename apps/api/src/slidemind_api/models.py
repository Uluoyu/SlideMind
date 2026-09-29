from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from slidemind_api.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Project(Timestamped, Base):
    __tablename__ = "ppt_project"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    template_id: Mapped[int | None] = mapped_column(ForeignKey("ppt_template.id"))


class StoredFile(Timestamped):
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(32))
    storage_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    security_level: Mapped[str] = mapped_column(String(32), default="INTERNAL")
    status: Mapped[str] = mapped_column(String(32), default="UPLOADED")


class Document(StoredFile, Base):
    __tablename__ = "ppt_document"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("ppt_project.id"), index=True)


class Asset(StoredFile, Base):
    __tablename__ = "ppt_asset"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("ppt_project.id"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Template(StoredFile, Base):
    __tablename__ = "ppt_template"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(default=1)


class DesignSystem(Timestamped, Base):
    __tablename__ = "ppt_design_system"
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("ppt_template.id"), index=True)
    design_json: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)


class DocumentChunk(Base):
    __tablename__ = "ppt_document_chunk"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("ppt_document.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    page_no: Mapped[int | None]
    chunk_index: Mapped[int]
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # No fixed dimension until an embedding model is selected.
    embedding: Mapped[list[float] | None] = mapped_column(
        JSON().with_variant(Vector(), "postgresql")
    )


class Presentation(Timestamped, Base):
    __tablename__ = "ppt_document_instance"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("ppt_project.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    page_count: Mapped[int]
    audience: Mapped[str] = mapped_column(String(128), default="")
    style: Mapped[str] = mapped_column(String(255), default="专业、简洁")
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    ppt_path: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(Text)


class Page(Timestamped, Base):
    __tablename__ = "ppt_page"
    __table_args__ = (UniqueConstraint("ppt_id", "page_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ppt_id: Mapped[int] = mapped_column(ForeignKey("ppt_document_instance.id"), index=True)
    page_no: Mapped[int]
    title: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(Text, default="")
    page_type: Mapped[str] = mapped_column(String(64), default="two_column")
    page_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    version: Mapped[int] = mapped_column(default=1)
