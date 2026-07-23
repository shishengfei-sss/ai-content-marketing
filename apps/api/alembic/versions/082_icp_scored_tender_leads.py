"""082 ICP + 租户匹配池 L2（scored_tender_leads）

Revision ID: 082
Revises: 081
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "082"
down_revision: Union[str, None] = "081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "icp_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("target_industries", sa.JSON(), nullable=False),
        sa.Column("target_regions", sa.JSON(), nullable=False),
        sa.Column("company_size_min", sa.Integer(), nullable=True),
        sa.Column("company_size_max", sa.Integer(), nullable=True),
        sa.Column("min_budget_threshold", sa.Numeric(15, 2), nullable=True),
        sa.Column("include_keywords", sa.JSON(), nullable=False),
        sa.Column("exclude_keywords", sa.JSON(), nullable=False),
        sa.Column("weight_industry", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("weight_company_size", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("weight_region", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("weight_budget", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("weight_urgency", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_icp_configs_tenant_id"),
    )
    op.create_index("ix_icp_configs_tenant_id", "icp_configs", ["tenant_id"])

    op.create_table(
        "scored_tender_leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform_tender_lead_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("converted_lead_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["platform_tender_lead_id"], ["platform_tender_leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["converted_lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform_tender_lead_id",
            "tenant_id",
            name="uq_scored_tender_tenant_platform",
        ),
    )
    op.create_index("ix_scored_tender_leads_tenant_id", "scored_tender_leads", ["tenant_id"])
    op.create_index("ix_scored_tender_leads_status", "scored_tender_leads", ["status"])
    op.create_index("ix_scored_tender_leads_match_score", "scored_tender_leads", ["match_score"])
    op.create_index(
        "ix_scored_tender_leads_platform_id",
        "scored_tender_leads",
        ["platform_tender_lead_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_scored_tender_leads_platform_id", table_name="scored_tender_leads")
    op.drop_index("ix_scored_tender_leads_match_score", table_name="scored_tender_leads")
    op.drop_index("ix_scored_tender_leads_status", table_name="scored_tender_leads")
    op.drop_index("ix_scored_tender_leads_tenant_id", table_name="scored_tender_leads")
    op.drop_table("scored_tender_leads")
    op.drop_index("ix_icp_configs_tenant_id", table_name="icp_configs")
    op.drop_table("icp_configs")
