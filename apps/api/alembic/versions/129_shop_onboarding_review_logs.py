"""P03：入驻审核日志。对照 04#ob-log。

Revision ID: 129
Revises: 128
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "129"
down_revision = "128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_onboarding_review_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("operator_name", sa.String(length=100), nullable=False, server_default="系统"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["shop_onboarding_applications.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shop_onboarding_review_logs_application_id",
        "shop_onboarding_review_logs",
        ["application_id"],
    )
    op.create_index(
        "ix_shop_onboarding_review_logs_tenant_id",
        "shop_onboarding_review_logs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_shop_onboarding_review_logs_action",
        "shop_onboarding_review_logs",
        ["action"],
    )


def downgrade() -> None:
    op.drop_index("ix_shop_onboarding_review_logs_action", table_name="shop_onboarding_review_logs")
    op.drop_index("ix_shop_onboarding_review_logs_tenant_id", table_name="shop_onboarding_review_logs")
    op.drop_index("ix_shop_onboarding_review_logs_application_id", table_name="shop_onboarding_review_logs")
    op.drop_table("shop_onboarding_review_logs")
