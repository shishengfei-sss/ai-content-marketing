"""074 campaign_channel_executions + campaign budget (v1.0 P1)

Revision ID: 074
Revises: 073
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "074"
down_revision: Union[str, None] = "073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("marketing_campaigns", sa.Column("budget", sa.Numeric(14, 2), nullable=True))
    op.add_column(
        "marketing_campaigns",
        sa.Column("spent", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "marketing_campaigns",
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
    )
    op.add_column("marketing_campaigns", sa.Column("target_segment_id", sa.Uuid(), nullable=True))

    op.create_table(
        "campaign_channel_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("content_type", sa.String(length=20), nullable=False, server_default="post"),
        sa.Column("content_url", sa.String(length=500), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_channel_executions_tenant_id", "campaign_channel_executions", ["tenant_id"])
    op.create_index("ix_campaign_channel_executions_campaign_id", "campaign_channel_executions", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_campaign_channel_executions_campaign_id", table_name="campaign_channel_executions")
    op.drop_index("ix_campaign_channel_executions_tenant_id", table_name="campaign_channel_executions")
    op.drop_table("campaign_channel_executions")
    op.drop_column("marketing_campaigns", "target_segment_id")
    op.drop_column("marketing_campaigns", "currency")
    op.drop_column("marketing_campaigns", "spent")
    op.drop_column("marketing_campaigns", "budget")
