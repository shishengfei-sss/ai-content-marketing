"""Unique tenant name platform-wide

Revision ID: 011
Revises: 010
Create Date: 2026-07-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dup_names = conn.execute(
        sa.text("SELECT name FROM tenants GROUP BY name HAVING COUNT(*) > 1")
    ).fetchall()
    for (name,) in dup_names:
        rows = conn.execute(
            sa.text(
                "SELECT id FROM tenants WHERE name = :name ORDER BY created_at ASC, id ASC"
            ),
            {"name": name},
        ).fetchall()
        for idx, (tenant_id,) in enumerate(rows[1:], start=2):
            conn.execute(
                sa.text("UPDATE tenants SET name = :new_name WHERE id = :id"),
                {"new_name": f"{name} ({idx})", "id": tenant_id},
            )

    op.create_index("uq_tenants_name", "tenants", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_tenants_name", table_name="tenants")
