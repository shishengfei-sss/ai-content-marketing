"""Knowledge chunk embeddings for hybrid RAG (v0.4 C4)

Revision ID: 019
Revises: 018
Create Date: 2026-07-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_chunks", sa.Column("embedding_json", sa.Text(), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
            op.execute(
                f"ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding vector({64})"
            )
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        try:
            op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding")
        except Exception:
            pass
    op.drop_column("knowledge_chunks", "embedding_json")
