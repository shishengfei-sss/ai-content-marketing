"""Platform LLM config and tenant usage quota

Revision ID: 009
Revises: 008
Create Date: 2026-07-04

"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_llm_config",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="deepseek"),
        sa.Column("base_url", sa.String(500), nullable=False, server_default="https://api.deepseek.com"),
        sa.Column("model", sa.String(100), nullable=False, server_default="deepseek-chat"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("timeout_sec", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("default_free_quota", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )

    op.create_table(
        "tenant_llm_usage",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_limit", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )

    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT id FROM platform_llm_config LIMIT 1")).fetchone()
    if not existing:
        conn.execute(
            sa.text(
                """
                INSERT INTO platform_llm_config (
                  id, provider, base_url, model, api_key_encrypted,
                  timeout_sec, default_free_quota, is_active
                ) VALUES (
                  :id, 'deepseek', 'https://api.deepseek.com', 'deepseek-chat', '',
                  60, 100, 1
                )
                """
            ),
            {"id": uuid.uuid4().hex},
        )


def downgrade() -> None:
    op.drop_table("tenant_llm_usage")
    op.drop_table("platform_llm_config")
