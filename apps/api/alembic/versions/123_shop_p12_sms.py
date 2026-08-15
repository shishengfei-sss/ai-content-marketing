"""P12 短信：签名绑定商家、模板默认领权。

Revision ID: 123
Revises: 122
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "123"
down_revision = "122"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platform_sms_signatures") as batch:
        batch.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("remark", sa.Text(), nullable=True))
        batch.add_column(sa.Column("reject_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("qualification_files", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_platform_sms_signatures_tenant_id",
            "tenants",
            ["tenant_id"],
            ["id"],
        )
        batch.create_index("ix_platform_sms_signatures_tenant_id", ["tenant_id"])

    with op.batch_alter_table("platform_sms_templates") as batch:
        batch.add_column(
            sa.Column("is_default_claim", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("content_preview", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("platform_sms_templates") as batch:
        batch.drop_column("content_preview")
        batch.drop_column("is_default_claim")
    with op.batch_alter_table("platform_sms_signatures") as batch:
        batch.drop_index("ix_platform_sms_signatures_tenant_id")
        batch.drop_constraint("fk_platform_sms_signatures_tenant_id", type_="foreignkey")
        batch.drop_column("qualification_files")
        batch.drop_column("reject_reason")
        batch.drop_column("remark")
        batch.drop_column("tenant_id")
