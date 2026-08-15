"""P02 商家业务编码 merchant_no。对照 04#platform-code-rule · generate_platform_number(shop_merchant)。

Revision ID: 132
Revises: 131
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "132"
down_revision = "131"
branch_labels = None
depends_on = None


def _day_key(approved_at) -> str:
    if approved_at is None:
        return datetime.now(timezone.utc).strftime("%Y%m%d")
    if isinstance(approved_at, str):
        digits = "".join(ch for ch in approved_at[:10] if ch.isdigit())
        return (digits + "00000000")[:8]
    if hasattr(approved_at, "strftime"):
        return approved_at.strftime("%Y%m%d")
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def upgrade() -> None:
    op.add_column(
        "shop_merchant_accounts",
        sa.Column("merchant_no", sa.String(length=32), nullable=True),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, onboarding_approved_at, created_at FROM shop_merchant_accounts "
            "ORDER BY onboarding_approved_at ASC, created_at ASC, id ASC"
        )
    ).fetchall()
    seq = 0
    for rid, approved_at, created_at in rows:
        seq += 1
        day = _day_key(approved_at or created_at)
        code = f"SH{day}{seq:04d}"
        conn.execute(
            sa.text("UPDATE shop_merchant_accounts SET merchant_no = :code WHERE id = :id"),
            {"code": code, "id": rid},
        )
    if seq:
        existing = conn.execute(
            sa.text(
                "SELECT id, seq FROM shop_platform_number_counters "
                "WHERE entity_type = 'shop_merchant' AND period_key = :pk AND scope_key = :sk"
            ),
            {"pk": "", "sk": "__global__"},
        ).fetchone()
        if existing:
            if int(existing[1] or 0) < seq:
                conn.execute(
                    sa.text("UPDATE shop_platform_number_counters SET seq = :seq WHERE id = :id"),
                    {"seq": seq, "id": existing[0]},
                )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO shop_platform_number_counters
                    (id, entity_type, scope_key, period_key, seq)
                    VALUES (:id, 'shop_merchant', :sk, :pk, :seq)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "sk": "__global__",
                    "pk": "",
                    "seq": seq,
                },
            )

    leftover = conn.execute(
        sa.text(
            "SELECT id FROM shop_merchant_accounts "
            "WHERE merchant_no IS NULL OR merchant_no = ''"
        )
    ).fetchall()
    for i, (rid,) in enumerate(leftover, start=1):
        conn.execute(
            sa.text("UPDATE shop_merchant_accounts SET merchant_no = :code WHERE id = :id"),
            {"code": f"SHLEGACY{i:04d}", "id": rid},
        )

    with op.batch_alter_table("shop_merchant_accounts") as batch:
        batch.alter_column(
            "merchant_no",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch.create_unique_constraint(
            "uq_shop_merchant_accounts_merchant_no",
            ["merchant_no"],
        )
    op.create_index(
        "ix_shop_merchant_accounts_merchant_no",
        "shop_merchant_accounts",
        ["merchant_no"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shop_merchant_accounts_merchant_no",
        table_name="shop_merchant_accounts",
    )
    with op.batch_alter_table("shop_merchant_accounts") as batch:
        batch.drop_constraint("uq_shop_merchant_accounts_merchant_no", type_="unique")
        batch.drop_column("merchant_no")
