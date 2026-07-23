"""097 crm.deal.reopen for admin / sales_manager

Revision ID: 097
Revises: 096

主管可重开已关闭商机（赢单/输单/放弃 → open）。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "097"
down_revision: Union[str, None] = "096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERM = "crm.deal.reopen"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS _reopen097_roles"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _reopen097_have"))
    conn.execute(
        sa.text(
            """
            CREATE TEMP TABLE _reopen097_roles AS
            SELECT id AS role_id,
                   replace(lower(id), '-', '') AS role_key
            FROM tenant_roles
            WHERE code IN ('admin', 'sales_manager')
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reopen097_roles_key ON _reopen097_roles(role_key)"))
    conn.execute(
        sa.text(
            """
            CREATE TEMP TABLE _reopen097_have AS
            SELECT replace(lower(role_id), '-', '') AS role_key
            FROM tenant_role_permissions
            WHERE permission_code = :code
            """
        ),
        {"code": PERM},
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reopen097_have_key ON _reopen097_have(role_key)"))
    conn.execute(
        sa.text(
            """
            INSERT INTO tenant_role_permissions (id, role_id, permission_code)
            SELECT lower(hex(randomblob(16))), r.role_id, :code
            FROM _reopen097_roles r
            LEFT JOIN _reopen097_have h ON h.role_key = r.role_key
            WHERE h.role_key IS NULL
            """
        ),
        {"code": PERM},
    )
    conn.execute(sa.text("DROP TABLE IF EXISTS _reopen097_have"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _reopen097_roles"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM tenant_role_permissions WHERE permission_code = :code"),
        {"code": PERM},
    )
