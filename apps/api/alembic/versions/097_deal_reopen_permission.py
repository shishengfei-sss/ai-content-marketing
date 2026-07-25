"""097 crm.deal.reopen for admin / sales_manager

Revision ID: 097
Revises: 096

主管可重开已关闭商机（赢单/输单/放弃 → open）。
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "097"
down_revision: Union[str, None] = "096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERM = "crm.deal.reopen"
SCOPE_ROLE_CODES = ("admin", "sales_manager")


def _role_key(role_id) -> str:
    return str(role_id).replace("-", "").lower()


def _insert_permission(conn, role_id, perm: str, dialect: str) -> None:
    params = {"id": str(uuid.uuid4()), "rid": str(role_id), "perm": perm}
    if dialect == "postgresql":
        conn.execute(
            sa.text(
                """
                INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                VALUES (:id, :rid, :perm)
                ON CONFLICT (role_id, permission_code) DO NOTHING
                """
            ),
            params,
        )
    else:
        conn.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO tenant_role_permissions (id, role_id, permission_code)
                VALUES (:id, :rid, :perm)
                """
            ),
            params,
        )


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    roles = conn.execute(
        sa.text(
            """
            SELECT id FROM tenant_roles
            WHERE code IN ('admin', 'sales_manager')
            """
        )
    ).fetchall()
    have = _existing_role_keys(conn, PERM)
    for (role_id,) in roles:
        if _role_key(role_id) not in have:
            _insert_permission(conn, role_id, PERM, dialect)


def _existing_role_keys(conn, perm: str) -> set[str]:
    rows = conn.execute(
        sa.text(
            """
            SELECT role_id FROM tenant_role_permissions
            WHERE permission_code = :perm
            """
        ),
        {"perm": perm},
    ).fetchall()
    return {_role_key(role_id) for (role_id,) in rows}


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM tenant_role_permissions WHERE permission_code = :code"),
        {"code": PERM},
    )
