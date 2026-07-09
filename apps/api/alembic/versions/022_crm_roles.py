"""022 CRM roles and permissions (v0.5 M0)

Revision ID: 022
Revises: 021
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 与 app.permissions 保持同步（迁移不可 import app）
CRM_PERMISSIONS = (
    "crm.lead.list_own",
    "crm.lead.list_team",
    "crm.lead.list_territory",
    "crm.lead.list_all",
    "crm.lead.view",
    "crm.lead.create",
    "crm.lead.edit",
    "crm.lead.assign",
    "crm.lead.convert",
    "crm.lead.delete",
    "crm.customer.list_own",
    "crm.customer.list_team",
    "crm.customer.list_territory",
    "crm.customer.list_all",
    "crm.customer.view",
    "crm.customer.create",
    "crm.customer.edit",
    "crm.customer.assign",
    "crm.customer.delete",
    "crm.task.list_own",
    "crm.task.list_team",
    "crm.task.list_territory",
    "crm.task.list_all",
    "crm.task.create",
    "crm.task.edit",
    "crm.task.assign",
    "crm.task.delete",
    "crm.campaign.list_own",
    "crm.campaign.list_team",
    "crm.campaign.list_territory",
    "crm.campaign.list_all",
    "crm.campaign.view",
    "crm.campaign.create",
    "crm.campaign.edit",
    "crm.campaign.manage",
    "crm.campaign.delete",
    "crm.org.manage",
    "crm.schema.manage",
    "crm.activity.create",
    "crm.view.save_own",
    "crm.view.manage_public",
    "crm.lead.import",
    "crm.customer.import",
)

SALES_DEFAULT = frozenset(
    {
        "preference.manage",
        "dashboard.view",
        "analytics.view",
        "crm.lead.list_own",
        "crm.lead.view",
        "crm.lead.create",
        "crm.lead.edit",
        "crm.lead.convert",
        "crm.customer.list_own",
        "crm.customer.view",
        "crm.customer.create",
        "crm.customer.edit",
        "crm.activity.create",
        "crm.task.list_own",
        "crm.task.create",
        "crm.task.edit",
        "crm.view.save_own",
        "crm.lead.import",
        "crm.customer.import",
    }
)

SALES_MANAGER_DEFAULT = SALES_DEFAULT | frozenset(
    {
        "crm.lead.list_team",
        "crm.lead.list_territory",
        "crm.customer.list_team",
        "crm.customer.list_territory",
        "crm.task.list_team",
        "crm.task.list_territory",
        "crm.lead.assign",
        "crm.customer.assign",
        "crm.task.assign",
        "crm.lead.delete",
        "crm.customer.delete",
        "crm.view.manage_public",
        "dashboard.view_all",
        "analytics.view_all",
        "team.member.view",
    }
)

MARKETING_DEFAULT = frozenset(
    {
        "preference.manage",
        "dashboard.view",
        "analytics.view",
        "content.create",
        "content.list_own",
        "content.view_own",
        "content.export",
        "content.schedule",
        "knowledge.view",
        "crm.campaign.list_own",
        "crm.campaign.view",
        "crm.campaign.create",
        "crm.campaign.edit",
        "crm.campaign.manage",
        "crm.campaign.list_all",
        "crm.lead.list_own",
        "crm.lead.view",
        "crm.lead.create",
        "crm.lead.list_all",
        "crm.view.save_own",
    }
)

NEW_ROLES = (
    ("sales", "销售", SALES_DEFAULT),
    ("sales_manager", "销售经理", SALES_MANAGER_DEFAULT),
    ("marketing", "市场运营", MARKETING_DEFAULT),
)


def _insert_permissions(conn, role_id: str, perms: frozenset[str], dialect: str) -> None:
    for perm in perms:
        if dialect == "postgresql":
            conn.execute(
                sa.text(
                    """
                    INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                    VALUES (:id, :rid, :perm)
                    ON CONFLICT (role_id, permission_code) DO NOTHING
                    """
                ),
                {"id": str(uuid.uuid4()), "rid": role_id, "perm": perm},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT OR IGNORE INTO tenant_role_permissions (id, role_id, permission_code)
                    VALUES (:id, :rid, :perm)
                    """
                ),
                {"id": str(uuid.uuid4()), "rid": role_id, "perm": perm},
            )


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        tid = str(tenant_id)
        admin_row = conn.execute(
            sa.text(
                """
                SELECT id FROM tenant_roles
                WHERE tenant_id = :tid AND code = 'admin' AND is_system = 1
                LIMIT 1
                """
            ),
            {"tid": tid},
        ).fetchone()
        if admin_row:
            admin_id = str(admin_row[0])
            for perm in CRM_PERMISSIONS:
                if dialect == "postgresql":
                    conn.execute(
                        sa.text(
                            """
                            INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                            VALUES (:id, :rid, :perm)
                            ON CONFLICT (role_id, permission_code) DO NOTHING
                            """
                        ),
                        {"id": str(uuid.uuid4()), "rid": admin_id, "perm": perm},
                    )
                else:
                    conn.execute(
                        sa.text(
                            """
                            INSERT OR IGNORE INTO tenant_role_permissions (id, role_id, permission_code)
                            VALUES (:id, :rid, :perm)
                            """
                        ),
                        {"id": str(uuid.uuid4()), "rid": admin_id, "perm": perm},
                    )

        for code, name, perms in NEW_ROLES:
            exists = conn.execute(
                sa.text(
                    """
                    SELECT id FROM tenant_roles
                    WHERE tenant_id = :tid AND code = :code
                    LIMIT 1
                    """
                ),
                {"tid": tid, "code": code},
            ).fetchone()
            if exists:
                role_id = str(exists[0])
            else:
                role_id = str(uuid.uuid4())
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO tenant_roles (id, tenant_id, code, name, is_system)
                        VALUES (:id, :tid, :code, :name, 1)
                        """
                    ),
                    {"id": role_id, "tid": tid, "code": code, "name": name},
                )
            _insert_permissions(conn, role_id, perms, dialect)


def downgrade() -> None:
    conn = op.get_bind()
    for code, _, _ in NEW_ROLES:
        rows = conn.execute(
            sa.text("SELECT id FROM tenant_roles WHERE code = :code AND is_system = 1"),
            {"code": code},
        ).fetchall()
        for (role_id,) in rows:
            conn.execute(
                sa.text("DELETE FROM tenant_role_permissions WHERE role_id = :rid"),
                {"rid": str(role_id)},
            )
        conn.execute(
            sa.text("DELETE FROM tenant_roles WHERE code = :code AND is_system = 1"),
            {"code": code},
        )
    for perm in CRM_PERMISSIONS:
        conn.execute(
            sa.text("DELETE FROM tenant_role_permissions WHERE permission_code = :perm"),
            {"perm": perm},
        )
