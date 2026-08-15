"""113 shop service offers + slots (A07)

Revision ID: 113
Revises: 112
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "113"
down_revision: Union[str, None] = "112"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("shop_service_offers"):
        op.create_table(
            "shop_service_offers",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("shop_id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("total_times", sa.Integer(), nullable=True),
            sa.Column("valid_days", sa.Integer(), nullable=True),
            sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=True,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_shop_service_offers_tenant_id", "shop_service_offers", ["tenant_id"])
        op.create_index("ix_shop_service_offers_shop_id", "shop_service_offers", ["shop_id"])
        op.create_index("ix_shop_service_offers_status", "shop_service_offers", ["status"])

    if not insp.has_table("shop_service_slots"):
        op.create_table(
            "shop_service_slots",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("shop_id", sa.Uuid(), nullable=False),
            sa.Column("service_offer_id", sa.Uuid(), nullable=False),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("booked_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["service_offer_id"], ["shop_service_offers.id"]),
            sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_shop_service_slots_tenant_id", "shop_service_slots", ["tenant_id"])
        op.create_index("ix_shop_service_slots_shop_id", "shop_service_slots", ["shop_id"])
        op.create_index(
            "ix_shop_service_slots_service_offer_id", "shop_service_slots", ["service_offer_id"]
        )
        op.create_index("ix_shop_service_slots_start_at", "shop_service_slots", ["start_at"])
        op.create_index("ix_shop_service_slots_status", "shop_service_slots", ["status"])

    booking_cols = {c["name"] for c in insp.get_columns("shop_bookings")}
    if "slot_id" not in booking_cols:
        with op.batch_alter_table("shop_bookings") as batch:
            batch.add_column(sa.Column("slot_id", sa.Uuid(), nullable=True))
            batch.create_index("ix_shop_bookings_slot_id", ["slot_id"])
            batch.create_foreign_key(
                "fk_shop_bookings_slot_id",
                "shop_service_slots",
                ["slot_id"],
                ["id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("shop_bookings") as batch:
        batch.drop_constraint("fk_shop_bookings_slot_id", type_="foreignkey")
        batch.drop_index("ix_shop_bookings_slot_id")
        batch.drop_column("slot_id")
    op.drop_index("ix_shop_service_slots_status", table_name="shop_service_slots")
    op.drop_index("ix_shop_service_slots_start_at", table_name="shop_service_slots")
    op.drop_index("ix_shop_service_slots_service_offer_id", table_name="shop_service_slots")
    op.drop_index("ix_shop_service_slots_shop_id", table_name="shop_service_slots")
    op.drop_index("ix_shop_service_slots_tenant_id", table_name="shop_service_slots")
    op.drop_table("shop_service_slots")
    op.drop_index("ix_shop_service_offers_status", table_name="shop_service_offers")
    op.drop_index("ix_shop_service_offers_shop_id", table_name="shop_service_offers")
    op.drop_index("ix_shop_service_offers_tenant_id", table_name="shop_service_offers")
    op.drop_table("shop_service_offers")
