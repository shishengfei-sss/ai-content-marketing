"""103 shop_admin 移除 shop.channel.write（租户级公域对接归企业管理员）

Revision ID: 103
Revises: 102
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "103"
down_revision: Union[str, None] = "102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERM = "shop.channel.write"
ROLE_CODE = "shop_admin"


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id FROM tenant_roles
            WHERE code = :code AND is_system = true
            """
        ),
        {"code": ROLE_CODE},
    ).fetchall()
    for (role_id,) in rows:
        conn.execute(
            sa.text(
                """
                DELETE FROM tenant_role_permissions
                WHERE role_id = :rid AND permission_code = :perm
                """
            ),
            {"rid": str(role_id), "perm": PERM},
        )


def downgrade() -> None:
    import uuid

    conn = op.get_bind()
    dialect = conn.dialect.name
    rows = conn.execute(
        sa.text(
            """
            SELECT id FROM tenant_roles
            WHERE code = :code AND is_system = true
            """
        ),
        {"code": ROLE_CODE},
    ).fetchall()
    for (role_id,) in rows:
        params = {"id": str(uuid.uuid4()), "rid": str(role_id), "perm": PERM}
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
