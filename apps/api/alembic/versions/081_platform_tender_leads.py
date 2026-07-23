"""081 平台公共招标线索池 L1（platform_tender_leads，含 source_url）

Revision ID: 081
Revises: 080
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "081"
down_revision: Union[str, None] = "080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_tender_leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("buyer_name", sa.String(length=200), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=True),
        sa.Column("quantity", sa.String(length=50), nullable=True),
        sa.Column("budget_min", sa.Numeric(15, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(15, 2), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("contact_name", sa.String(length=100), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_channel", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_tender_leads_status", "platform_tender_leads", ["status"])
    op.create_index("ix_platform_tender_leads_industry", "platform_tender_leads", ["industry"])
    op.create_index("ix_platform_tender_leads_region", "platform_tender_leads", ["region"])
    op.create_index("ix_platform_tender_leads_created_at", "platform_tender_leads", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_platform_tender_leads_created_at", table_name="platform_tender_leads")
    op.drop_index("ix_platform_tender_leads_region", table_name="platform_tender_leads")
    op.drop_index("ix_platform_tender_leads_industry", table_name="platform_tender_leads")
    op.drop_index("ix_platform_tender_leads_status", table_name="platform_tender_leads")
    op.drop_table("platform_tender_leads")
