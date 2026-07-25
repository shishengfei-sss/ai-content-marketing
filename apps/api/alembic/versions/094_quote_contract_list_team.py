"""094 quote/contract list_team scope for sales_manager

Revision ID: 094
Revises: 093

销售经理报价/合同可见范围：list_all → list_team（与商机/订单一致）。
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "094"
down_revision: Union[str, None] = "093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCOPE_ROLE_CODES = ("admin", "sales_manager")
LIST_TEAM_PERMS = ("crm.quote.list_team", "crm.contract.list_team")
LIST_ALL_PERMS = ("crm.quote.list_all", "crm.contract.list_all")


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


def _scope_roles(conn):
    return conn.execute(
        sa.text(
            """
            SELECT id, code FROM tenant_roles
            WHERE code IN ('admin', 'sales_manager')
            """
        )
    ).fetchall()


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


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    roles = _scope_roles(conn)

    for perm in LIST_TEAM_PERMS:
        have = _existing_role_keys(conn, perm)
        for role_id, _code in roles:
            if _role_key(role_id) not in have:
                _insert_permission(conn, role_id, perm, dialect)

    sales_manager_keys = {_role_key(role_id) for role_id, code in roles if code == "sales_manager"}
    for perm in LIST_ALL_PERMS:
        rows = conn.execute(
            sa.text(
                """
                SELECT id, role_id FROM tenant_role_permissions
                WHERE permission_code = :perm
                """
            ),
            {"perm": perm},
        ).fetchall()
        for perm_id, role_id in rows:
            if _role_key(role_id) in sales_manager_keys:
                conn.execute(
                    sa.text("DELETE FROM tenant_role_permissions WHERE id = :id"),
                    {"id": str(perm_id)},
                )


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    roles = _scope_roles(conn)
    scope_keys = {_role_key(role_id) for role_id, _code in roles}

    for perm in LIST_ALL_PERMS:
        have = _existing_role_keys(conn, perm)
        for role_id, code in roles:
            if code == "sales_manager" and _role_key(role_id) not in have:
                _insert_permission(conn, role_id, perm, dialect)

    for perm in LIST_TEAM_PERMS:
        rows = conn.execute(
            sa.text(
                """
                SELECT id, role_id FROM tenant_role_permissions
                WHERE permission_code = :perm
                """
            ),
            {"perm": perm},
        ).fetchall()
        for perm_id, role_id in rows:
            if _role_key(role_id) in scope_keys:
                conn.execute(
                    sa.text("DELETE FROM tenant_role_permissions WHERE id = :id"),
                    {"id": str(perm_id)},
                )
