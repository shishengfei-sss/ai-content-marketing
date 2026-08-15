"""101 onboarding fields + shop_stores (content acquisition shop Phase1)

Revision ID: 101
Revises: 100
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "101"
down_revision: Union[str, None] = "100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shop_onboarding_applications") as batch_op:
        batch_op.add_column(sa.Column("id_no", sa.String(length=18), nullable=True))
        batch_op.add_column(sa.Column("unified_social_credit_code", sa.String(length=18), nullable=True))
        batch_op.add_column(sa.Column("legal_rep_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("bank_account_info", sa.JSON(), nullable=False, server_default="{}"))

    with op.batch_alter_table("shop_merchant_accounts") as batch_op:
        batch_op.add_column(sa.Column("id_no", sa.String(length=18), nullable=True))
        batch_op.add_column(sa.Column("unified_social_credit_code", sa.String(length=18), nullable=True))
        batch_op.add_column(sa.Column("legal_rep_name", sa.String(length=100), nullable=True))

    op.create_table(
        "shop_stores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("slug", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("wx_mp_app_id", sa.String(length=64), nullable=True),
        sa.Column("default_category_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["shop_merchant_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_shop_stores_tenant_slug"),
    )
    op.create_index("ix_shop_stores_tenant_id", "shop_stores", ["tenant_id"])
    op.create_index("ix_shop_stores_merchant_id", "shop_stores", ["merchant_id"])
    op.create_index("ix_shop_stores_status", "shop_stores", ["status"])

    _seed_demo_stores()


def _seed_demo_stores() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT id, tenant_id, display_name FROM shop_merchant_accounts ORDER BY created_at LIMIT 1"
        )
    ).fetchone()
    if not row:
        return
    mid, tid, name = row
    conn.execute(
        sa.text(
            """
            INSERT INTO shop_stores (id, tenant_id, merchant_id, name, slug, status)
            VALUES (:id, :tid, :mid, :name, :slug, 'active')
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tid": str(tid),
            "mid": str(mid),
            "name": f"{name}旗舰店",
            "slug": "main",
        },
    )


def downgrade() -> None:
    op.drop_index("ix_shop_stores_status", table_name="shop_stores")
    op.drop_index("ix_shop_stores_merchant_id", table_name="shop_stores")
    op.drop_index("ix_shop_stores_tenant_id", table_name="shop_stores")
    op.drop_table("shop_stores")
    with op.batch_alter_table("shop_merchant_accounts") as batch_op:
        batch_op.drop_column("legal_rep_name")
        batch_op.drop_column("unified_social_credit_code")
        batch_op.drop_column("id_no")
    with op.batch_alter_table("shop_onboarding_applications") as batch_op:
        batch_op.drop_column("bank_account_info")
        batch_op.drop_column("legal_rep_name")
        batch_op.drop_column("unified_social_credit_code")
        batch_op.drop_column("id_no")
