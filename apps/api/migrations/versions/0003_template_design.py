"""Persist template parsing failures surfaced to the uploader."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ppt_template") as batch:
        batch.add_column(sa.Column("processing_error", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("ppt_template") as batch:
        batch.drop_column("processing_error")
