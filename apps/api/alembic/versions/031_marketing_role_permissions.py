"""031 sync marketing role default permissions with app.permissions

Revision ID: 031
Revises: 030
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 022 初版遗漏；与 app.permissions.MARKETING_DEFAULT_PERMISSIONS 对齐
MARKETING_PERMISSIONS_TO_ENSURE = (
    "crm.lead.edit",
    "crm.lead.convert",
    "crm.customer.list_own",
    "crm.customer.view",
)


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    roles = conn.execute(
        sa.text(
            """
            SELECT id FROM tenant_roles
            WHERE code = 'marketing' AND is_system = true
            """
        )
    ).fetchall()
    for (role_id,) in roles:
        rid = str(role_id)
        for perm in MARKETING_PERMISSIONS_TO_ENSURE:
            if dialect == "postgresql":
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                        VALUES (:id, :rid, :perm)
                        ON CONFLICT (role_id, permission_code) DO NOTHING
                        """
                    ),
                    {"id": str(uuid.uuid4()), "rid": rid, "perm": perm},
                )
            else:
                conn.execute(
                    sa.text(
                        """
                        INSERT OR IGNORE INTO tenant_role_permissions (id, role_id, permission_code)
                        VALUES (:id, :rid, :perm)
                        """
                    ),
                    {"id": str(uuid.uuid4()), "rid": rid, "perm": perm},
                )


def downgrade() -> None:
    conn = op.get_bind()
    for perm in MARKETING_PERMISSIONS_TO_ENSURE:
        conn.execute(
            sa.text(
                """
                DELETE FROM tenant_role_permissions
                WHERE permission_code = :perm
                  AND role_id IN (
                    SELECT id FROM tenant_roles
                    WHERE code = 'marketing' AND is_system = true
                  )
                """
            ),
            {"perm": perm},
        )
