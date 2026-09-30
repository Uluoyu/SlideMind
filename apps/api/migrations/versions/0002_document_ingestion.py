"""Persist document indexing state and recoverable processing leases."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ppt_document") as batch:
        batch.add_column(sa.Column("processing_error", sa.Text(), nullable=True))
        batch.add_column(sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("embedding_model", sa.String(255), nullable=True))
        batch.add_column(sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("lease_token", sa.String(64), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
        batch.create_index("ix_document_processing", ["status", "lease_expires_at"])
    if op.get_bind().dialect.name == "sqlite":
        # Retired source URLs must not alias newly indexed chunks when a row is deleted.
        with op.batch_alter_table(
            "ppt_document_chunk", recreate="always", table_kwargs={"sqlite_autoincrement": True}
        ):
            pass


def downgrade():
    with op.batch_alter_table("ppt_document") as batch:
        batch.drop_index("ix_document_processing")
        for name in (
            "attempts",
            "lease_expires_at",
            "lease_token",
            "embedding_dimensions",
            "embedding_model",
            "processed_at",
            "chunk_count",
            "processing_error",
        ):
            batch.drop_column(name)
