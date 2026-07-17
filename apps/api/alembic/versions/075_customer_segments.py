"""075 customer_segments (v1.0 P1)

Revision ID: 075
Revises: 074
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "075"
down_revision: Union[str, None] = "074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("estimated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_segments_tenant_id", "customer_segments", ["tenant_id"])
    # FK for campaign.target_segment_id (column added in 074 without FK to avoid order issue)
    with op.batch_alter_table("marketing_campaigns") as batch:
        batch.create_foreign_key(
            "fk_marketing_campaigns_target_segment_id",
            "customer_segments",
            ["target_segment_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("marketing_campaigns") as batch:
        batch.drop_constraint("fk_marketing_campaigns_target_segment_id", type_="foreignkey")
    op.drop_index("ix_customer_segments_tenant_id", table_name="customer_segments")
    op.drop_table("customer_segments")
