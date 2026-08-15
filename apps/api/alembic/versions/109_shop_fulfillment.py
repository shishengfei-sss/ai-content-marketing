"""109 shop bookings / verifications / invoices / lesson progress (M6)

Revision ID: 109
Revises: 108
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "109"
down_revision: Union[str, None] = "108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shop_stores") as batch:
        batch.add_column(
            sa.Column("allow_cross_shop_redeem", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("shop_entitlements") as batch:
        batch.add_column(sa.Column("verify_code", sa.String(length=16), nullable=True))
    op.create_index("ix_shop_entitlements_verify_code", "shop_entitlements", ["verify_code"])

    op.create_table(
        "shop_bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("service_product_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column("booked_date", sa.Date(), nullable=False),
        sa.Column("booked_time_slot", sa.String(length=32), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["entitlement_id"], ["shop_entitlements.id"]),
        sa.ForeignKeyConstraint(["service_product_id"], ["shop_products.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_bookings_tenant_id", "shop_bookings", ["tenant_id"])
    op.create_index("ix_shop_bookings_shop_id", "shop_bookings", ["shop_id"])
    op.create_index("ix_shop_bookings_buyer_id", "shop_bookings", ["buyer_id"])
    op.create_index("ix_shop_bookings_entitlement_id", "shop_bookings", ["entitlement_id"])
    op.create_index("ix_shop_bookings_status", "shop_bookings", ["status"])
    op.create_index("ix_shop_bookings_booked_date", "shop_bookings", ["booked_date"])

    op.create_table(
        "shop_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=30), nullable=False, server_default="times_card_deduct"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("verify_code", sa.String(length=16), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("deducted_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["booking_id"], ["shop_bookings.id"]),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["entitlement_id"], ["shop_entitlements.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_shop_verifications_idem"),
    )
    op.create_index("ix_shop_verifications_tenant_id", "shop_verifications", ["tenant_id"])
    op.create_index("ix_shop_verifications_shop_id", "shop_verifications", ["shop_id"])
    op.create_index("ix_shop_verifications_entitlement_id", "shop_verifications", ["entitlement_id"])
    op.create_index("ix_shop_verifications_status", "shop_verifications", ["status"])

    op.create_table(
        "shop_invoice_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_type", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("title_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("tax_no", sa.String(length=32), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("bank_account", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoice_url", sa.String(length=500), nullable=True),
        sa.Column("needs_red_flush", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_invoice_requests_tenant_id", "shop_invoice_requests", ["tenant_id"])
    op.create_index("ix_shop_invoice_requests_order_id", "shop_invoice_requests", ["order_id"])
    op.create_index("ix_shop_invoice_requests_status", "shop_invoice_requests", ["status"])

    op.create_table(
        "shop_lesson_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("position_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["entitlement_id"], ["shop_entitlements.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entitlement_id", "lesson_id", name="uq_shop_lesson_progress_ent_lesson"),
    )
    op.create_index("ix_shop_lesson_progress_tenant_id", "shop_lesson_progress", ["tenant_id"])
    op.create_index("ix_shop_lesson_progress_buyer_id", "shop_lesson_progress", ["buyer_id"])
    op.create_index("ix_shop_lesson_progress_entitlement_id", "shop_lesson_progress", ["entitlement_id"])


def downgrade() -> None:
    op.drop_table("shop_lesson_progress")
    op.drop_table("shop_invoice_requests")
    op.drop_table("shop_verifications")
    op.drop_table("shop_bookings")
    op.drop_index("ix_shop_entitlements_verify_code", table_name="shop_entitlements")
    with op.batch_alter_table("shop_entitlements") as batch:
        batch.drop_column("verify_code")
    with op.batch_alter_table("shop_stores") as batch:
        batch.drop_column("allow_cross_shop_redeem")
