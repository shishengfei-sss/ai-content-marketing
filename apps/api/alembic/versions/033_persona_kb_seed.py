"""033 persona knowledge base seed P-001..P-009

Revision ID: 033
Revises: 032
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.persona_seeds import PERSONA_KB_CHUNKS, PERSONA_KB_FILE, PERSONA_KB_TITLE, persona_raw_text


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM knowledge_documents WHERE title = :title AND scope = 'platform'"),
        {"title": PERSONA_KB_TITLE},
    ).fetchone()
    if existing:
        doc_id = existing[0]
        conn.execute(sa.text("DELETE FROM knowledge_chunks WHERE document_id = :id"), {"id": str(doc_id)})
    else:
        doc_id = uuid.uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO knowledge_documents (
                  id, tenant_id, industry_code, scope, title, file_name, raw_text, status, chunk_count
                ) VALUES (
                  :id, NULL, 'marketing', 'platform', :title, :file_name, :text, 'parsed', 0
                )
                """
            ),
            {
                "id": str(doc_id),
                "title": PERSONA_KB_TITLE,
                "file_name": PERSONA_KB_FILE,
                "text": persona_raw_text(),
            },
        )

    for idx, item in enumerate(PERSONA_KB_CHUNKS):
        conn.execute(
            sa.text(
                """
                INSERT INTO knowledge_chunks (
                  id, document_id, tenant_id, industry_code, scope, chunk_index, content
                ) VALUES (
                  :id, :doc_id, NULL, 'marketing', 'platform', :idx, :content
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "doc_id": str(doc_id),
                "idx": idx,
                "content": item["content"],
            },
        )

    conn.execute(
        sa.text("UPDATE knowledge_documents SET chunk_count = :n WHERE id = :id"),
        {"n": len(PERSONA_KB_CHUNKS), "id": str(doc_id)},
    )


def downgrade() -> None:
    conn = op.get_bind()
    doc = conn.execute(
        sa.text("SELECT id FROM knowledge_documents WHERE title = :title AND scope = 'platform'"),
        {"title": PERSONA_KB_TITLE},
    ).fetchone()
    if doc:
        conn.execute(sa.text("DELETE FROM knowledge_chunks WHERE document_id = :id"), {"id": str(doc[0])})
        conn.execute(sa.text("DELETE FROM knowledge_documents WHERE id = :id"), {"id": str(doc[0])})
