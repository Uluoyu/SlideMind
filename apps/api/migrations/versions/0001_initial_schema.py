"""initial_schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "ppt_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("security_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ppt_design_system",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("design_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["ppt_template.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ppt_design_system", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ppt_design_system_template_id"), ["template_id"], unique=False
        )

    op.create_table(
        "ppt_project",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["ppt_template.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ppt_asset",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("security_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["ppt_project.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ppt_asset", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ppt_asset_project_id"), ["project_id"], unique=False)

    op.create_table(
        "ppt_document",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("security_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["ppt_project.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ppt_document", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ppt_document_project_id"), ["project_id"], unique=False
        )

    op.create_table(
        "ppt_document_instance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("audience", sa.String(length=128), nullable=False),
        sa.Column("style", sa.String(length=255), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ppt_path", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["ppt_project.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ppt_document_instance", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ppt_document_instance_project_id"), ["project_id"], unique=False
        )

    op.create_table(
        "ppt_document_chunk",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON().with_variant(Vector(), "postgresql"), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["ppt_document.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    with op.batch_alter_table("ppt_document_chunk", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ppt_document_chunk_document_id"), ["document_id"], unique=False
        )

    op.create_table(
        "ppt_page",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ppt_id", sa.Integer(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("page_type", sa.String(length=64), nullable=False),
        sa.Column("page_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ppt_id"],
            ["ppt_document_instance.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ppt_id", "page_no"),
    )
    with op.batch_alter_table("ppt_page", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ppt_page_ppt_id"), ["ppt_id"], unique=False)


def downgrade():
    with op.batch_alter_table("ppt_page", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ppt_page_ppt_id"))

    op.drop_table("ppt_page")
    with op.batch_alter_table("ppt_document_chunk", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ppt_document_chunk_document_id"))

    op.drop_table("ppt_document_chunk")
    with op.batch_alter_table("ppt_document_instance", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ppt_document_instance_project_id"))

    op.drop_table("ppt_document_instance")
    with op.batch_alter_table("ppt_document", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ppt_document_project_id"))

    op.drop_table("ppt_document")
    with op.batch_alter_table("ppt_asset", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ppt_asset_project_id"))

    op.drop_table("ppt_asset")
    op.drop_table("ppt_project")
    with op.batch_alter_table("ppt_design_system", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ppt_design_system_template_id"))

    op.drop_table("ppt_design_system")
    op.drop_table("ppt_template")
