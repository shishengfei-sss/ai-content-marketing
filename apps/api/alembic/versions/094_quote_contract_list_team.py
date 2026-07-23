"""094 quote/contract list_team scope for sales_manager

Revision ID: 094
Revises: 093

销售经理报价/合同可见范围：list_all → list_team（与商机/订单一致）。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "094"
down_revision: Union[str, None] = "093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_roles"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_have"))
    conn.execute(
        sa.text(
            """
            CREATE TEMP TABLE _scope094_roles AS
            SELECT id AS role_id,
                   code AS role_code,
                   replace(lower(id), '-', '') AS role_key
            FROM tenant_roles
            WHERE code IN ('admin', 'sales_manager')
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_scope094_roles_key ON _scope094_roles(role_key)"))

    for code in ("crm.quote.list_team", "crm.contract.list_team"):
        conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_have"))
        conn.execute(
            sa.text(
                """
                CREATE TEMP TABLE _scope094_have AS
                SELECT replace(lower(role_id), '-', '') AS role_key
                FROM tenant_role_permissions
                WHERE permission_code = :code
                """
            ),
            {"code": code},
        )
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_scope094_have_key ON _scope094_have(role_key)"))
        conn.execute(
            sa.text(
                """
                INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                SELECT lower(hex(randomblob(16))), r.role_id, :code
                FROM _scope094_roles r
                LEFT JOIN _scope094_have h ON h.role_key = r.role_key
                WHERE h.role_key IS NULL
                """
            ),
            {"code": code},
        )

    conn.execute(
        sa.text(
            """
            DELETE FROM tenant_role_permissions
            WHERE permission_code IN ('crm.quote.list_all', 'crm.contract.list_all')
              AND replace(lower(role_id), '-', '') IN (
                SELECT role_key FROM _scope094_roles WHERE role_code = 'sales_manager'
              )
            """
        )
    )
    conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_have"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_roles"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_roles"))
    conn.execute(
        sa.text(
            """
            CREATE TEMP TABLE _scope094_roles AS
            SELECT id AS role_id,
                   code AS role_code,
                   replace(lower(id), '-', '') AS role_key
            FROM tenant_roles
            WHERE code IN ('admin', 'sales_manager')
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_scope094_roles_key ON _scope094_roles(role_key)"))

    for code in ("crm.quote.list_all", "crm.contract.list_all"):
        conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_have"))
        conn.execute(
            sa.text(
                """
                CREATE TEMP TABLE _scope094_have AS
                SELECT replace(lower(role_id), '-', '') AS role_key
                FROM tenant_role_permissions
                WHERE permission_code = :code
                """
            ),
            {"code": code},
        )
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_scope094_have_key ON _scope094_have(role_key)"))
        conn.execute(
            sa.text(
                """
                INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                SELECT lower(hex(randomblob(16))), r.role_id, :code
                FROM _scope094_roles r
                LEFT JOIN _scope094_have h ON h.role_key = r.role_key
                WHERE r.role_code = 'sales_manager' AND h.role_key IS NULL
                """
            ),
            {"code": code},
        )

    conn.execute(
        sa.text(
            """
            DELETE FROM tenant_role_permissions
            WHERE permission_code IN ('crm.quote.list_team', 'crm.contract.list_team')
              AND replace(lower(role_id), '-', '') IN (
                SELECT role_key FROM _scope094_roles
              )
            """
        )
    )
    conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_have"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _scope094_roles"))
