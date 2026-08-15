"""P03 入驻申请业务单号 application_no。对照 04#ob · generate_platform_number(shop_onboarding)。

Revision ID: 131
Revises: 130
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "131"
down_revision = "130"
branch_labels = None
depends_on = None


def _day_key(submitted_at) -> str:
    if submitted_at is None:
        return datetime.now(timezone.utc).strftime("%Y%m%d")
    if isinstance(submitted_at, str):
        digits = "".join(ch for ch in submitted_at[:10] if ch.isdigit())
        return (digits + "00000000")[:8]
    if hasattr(submitted_at, "strftime"):
        return submitted_at.strftime("%Y%m%d")
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def upgrade() -> None:
    op.add_column(
        "shop_onboarding_applications",
        sa.Column("application_no", sa.String(length=32), nullable=True),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, submitted_at FROM shop_onboarding_applications "
            "ORDER BY submitted_at ASC, id ASC"
        )
    ).fetchall()
    per_day: dict[str, int] = defaultdict(int)
    for rid, submitted_at in rows:
        day = _day_key(submitted_at)
        per_day[day] += 1
        code = f"OB{day}{per_day[day]:04d}"
        conn.execute(
            sa.text(
                "UPDATE shop_onboarding_applications SET application_no = :code WHERE id = :id"
            ),
            {"code": code, "id": rid},
        )
    for day, seq in per_day.items():
        existing = conn.execute(
            sa.text(
                "SELECT id, seq FROM shop_platform_number_counters "
                "WHERE entity_type = 'shop_onboarding' AND period_key = :pk AND scope_key = :sk"
            ),
            {"pk": day, "sk": day},
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
                    VALUES (:id, 'shop_onboarding', :sk, :pk, :seq)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "sk": day,
                    "pk": day,
                    "seq": seq,
                },
            )

    leftover = conn.execute(
        sa.text(
            "SELECT id FROM shop_onboarding_applications "
            "WHERE application_no IS NULL OR application_no = ''"
        )
    ).fetchall()
    for i, (rid,) in enumerate(leftover, start=1):
        conn.execute(
            sa.text(
                "UPDATE shop_onboarding_applications SET application_no = :code WHERE id = :id"
            ),
            {"code": f"OBLEGACY{i:04d}", "id": rid},
        )

    with op.batch_alter_table("shop_onboarding_applications") as batch:
        batch.alter_column(
            "application_no",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch.create_unique_constraint(
            "uq_shop_onboarding_applications_application_no",
            ["application_no"],
        )
    op.create_index(
        "ix_shop_onboarding_applications_application_no",
        "shop_onboarding_applications",
        ["application_no"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shop_onboarding_applications_application_no",
        table_name="shop_onboarding_applications",
    )
    with op.batch_alter_table("shop_onboarding_applications") as batch:
        batch.drop_constraint("uq_shop_onboarding_applications_application_no", type_="unique")
        batch.drop_column("application_no")
