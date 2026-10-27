"""Record which planner wrote an outline and the evidence behind each outline page."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ppt_document_instance") as batch:
        batch.add_column(sa.Column("planner", sa.String(32), nullable=True))
        batch.add_column(sa.Column("outline_warning", sa.Text(), nullable=True))
    with op.batch_alter_table("ppt_page") as batch:
        batch.add_column(sa.Column("outline_sources", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("ppt_page") as batch:
        batch.drop_column("outline_sources")
    with op.batch_alter_table("ppt_document_instance") as batch:
        batch.drop_column("outline_warning")
        batch.drop_column("planner")
