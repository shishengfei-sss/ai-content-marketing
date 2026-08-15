"""平台业务编码规则（P04-E / P08-F）。

Revision ID: 118
Revises: 117
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "118"
down_revision = "117"
branch_labels = None
depends_on = None

# entity_type, prefix, date_format, seq_width, reset_period, inherit_parent_code, separator, enabled
SEEDS = [
    ("shop_merchant", "SH", "%Y%m%d", 4, "once", False, ".", True),
    ("shop_onboarding", "OB", "%Y%m%d", 4, "daily", False, ".", True),
    ("renewal_application", "RF", "%Y%m%d", 4, "daily", False, ".", True),
    ("service_log", "SV", "%Y%m%d", 4, "daily", False, ".", True),
    ("shop_category", "cat.", "", 3, "once", True, ".", True),
    ("shop_plan", "PL", "", 3, "once", False, ".", True),
    ("shop_plan_feature", "PF", "", 3, "once", False, ".", True),
    ("shop_subscription", "DY", "%Y%m%d", 4, "daily", False, ".", True),
    ("settlement_batch", "JS", "%G%V", 4, "weekly", False, ".", True),
    ("shop_store", "DP", "", 4, "once", False, ".", True),
    ("moderation_case", "WG", "%Y%m%d", 4, "daily", False, ".", True),
]


def upgrade() -> None:
    op.create_table(
        "shop_platform_number_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("prefix", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("suffix", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("date_format", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("seq_width", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("reset_period", sa.String(length=10), nullable=False, server_default="once"),
        sa.Column("inherit_parent_code", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("separator", sa.String(length=4), nullable=False, server_default="."),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("entity_type", name="uq_shop_platform_number_rules_entity"),
    )
    op.create_table(
        "shop_platform_number_counters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("period_key", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "entity_type",
            "scope_key",
            "period_key",
            name="uq_shop_platform_number_counters_scope",
        ),
    )
    op.create_index(
        "ix_shop_platform_number_counters_entity_type",
        "shop_platform_number_counters",
        ["entity_type"],
    )

    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    for s in SEEDS:
        conn.execute(
            sa.text(
                """
                INSERT INTO shop_platform_number_rules
                (id, entity_type, prefix, suffix, date_format, seq_width, reset_period,
                 inherit_parent_code, separator, enabled, created_at, updated_at)
                VALUES
                (:id, :entity_type, :prefix, '', :date_format, :seq_width, :reset_period,
                 :inherit_parent_code, :separator, :enabled, :now, :now)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "entity_type": s[0],
                "prefix": s[1],
                "date_format": s[2],
                "seq_width": s[3],
                "reset_period": s[4],
                "inherit_parent_code": bool(s[5]),
                "separator": s[6],
                "enabled": bool(s[7]),
                "now": now,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_shop_platform_number_counters_entity_type", table_name="shop_platform_number_counters")
    op.drop_table("shop_platform_number_counters")
    op.drop_table("shop_platform_number_rules")
