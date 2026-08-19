"""138 shop_lessons.content_body for article lessons

Revision ID: 138
Revises: 137
"""

from alembic import op
import sqlalchemy as sa

revision = "138"
down_revision = "137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop_lessons",
        sa.Column("content_body", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shop_lessons", "content_body")
