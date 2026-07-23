"""085 平台招标 L1 销售跟进增强字段

Revision ID: 085
Revises: 084
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "085"
down_revision: Union[str, None] = "084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("platform_tender_leads", sa.Column("project_no", sa.String(length=100), nullable=True))
    op.add_column("platform_tender_leads", sa.Column("published_at", sa.Date(), nullable=True))
    op.add_column(
        "platform_tender_leads", sa.Column("procurement_method", sa.String(length=50), nullable=True)
    )
    op.add_column("platform_tender_leads", sa.Column("agent_name", sa.String(length=200), nullable=True))
    op.add_column(
        "platform_tender_leads", sa.Column("buyer_address", sa.String(length=200), nullable=True)
    )
    op.add_column("platform_tender_leads", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("platform_tender_leads", sa.Column("bid_open_date", sa.Date(), nullable=True))
    op.add_column("platform_tender_leads", sa.Column("sme_preference", sa.Boolean(), nullable=True))
    op.add_column("platform_tender_leads", sa.Column("qualification_summary", sa.Text(), nullable=True))
    op.add_column(
        "platform_tender_leads", sa.Column("max_price_limit", sa.Numeric(15, 2), nullable=True)
    )
    op.create_index("ix_platform_tender_leads_project_no", "platform_tender_leads", ["project_no"])
    op.create_index("ix_platform_tender_leads_published_at", "platform_tender_leads", ["published_at"])
    op.create_index("ix_platform_tender_leads_deadline", "platform_tender_leads", ["deadline"])


def downgrade() -> None:
    op.drop_index("ix_platform_tender_leads_deadline", table_name="platform_tender_leads")
    op.drop_index("ix_platform_tender_leads_published_at", table_name="platform_tender_leads")
    op.drop_index("ix_platform_tender_leads_project_no", table_name="platform_tender_leads")
    op.drop_column("platform_tender_leads", "max_price_limit")
    op.drop_column("platform_tender_leads", "qualification_summary")
    op.drop_column("platform_tender_leads", "sme_preference")
    op.drop_column("platform_tender_leads", "bid_open_date")
    op.drop_column("platform_tender_leads", "category")
    op.drop_column("platform_tender_leads", "buyer_address")
    op.drop_column("platform_tender_leads", "agent_name")
    op.drop_column("platform_tender_leads", "procurement_method")
    op.drop_column("platform_tender_leads", "published_at")
    op.drop_column("platform_tender_leads", "project_no")
