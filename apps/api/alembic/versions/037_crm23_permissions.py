"""037 CRM-2/3 permissions seed for existing tenants (v0.7)

Revision ID: 037
Revises: 036
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# v0.7 新增 CRM-2/3 权限码（与 app.permissions.py 保持同步；迁移不可 import app）
CRM_23_PERMISSIONS: tuple[str, ...] = (
    # 商机
    "crm.deal.list_own",
    "crm.deal.list_team",
    "crm.deal.list_territory",
    "crm.deal.list_all",
    "crm.deal.view",
    "crm.deal.create",
    "crm.deal.edit",
    "crm.deal.assign",
    "crm.deal.convert",
    "crm.deal.close",
    "crm.deal.delete",
    # 管道
    "crm.pipeline.manage",
    # 产品
    "crm.product.manage",
    # 报价
    "crm.quote.list_own",
    "crm.quote.list_all",
    "crm.quote.view",
    "crm.quote.create",
    "crm.quote.edit",
    "crm.quote.send",
    "crm.quote.accept",
    "crm.quote.delete",
    # 合同
    "crm.contract.list_own",
    "crm.contract.list_all",
    "crm.contract.view",
    "crm.contract.create",
    "crm.contract.edit",
    "crm.contract.sign",
    "crm.contract.delete",
    # 订单
    "crm.order.list_own",
    "crm.order.list_team",
    "crm.order.list_territory",
    "crm.order.list_all",
    "crm.order.view",
    "crm.order.create",
    "crm.order.edit",
    "crm.order.assign",
    "crm.order.place",
    "crm.order.convert",
    "crm.order.delete",
    # 收款
    "crm.payment.list_own",
    "crm.payment.list_team",
    "crm.payment.list_territory",
    "crm.payment.list_all",
    "crm.payment.view",
    "crm.payment.create",
    "crm.payment.edit",
    "crm.payment.confirm",
    "crm.payment.reverse",
    "crm.payment.delete",
)

# sales 在原默认集之上新增（v0.7）
SALES_NEW: frozenset[str] = frozenset(
    {
        "crm.deal.list_own",
        "crm.deal.view",
        "crm.deal.create",
        "crm.deal.edit",
        "crm.deal.convert",
        "crm.deal.close",
        "crm.quote.list_own",
        "crm.quote.view",
        "crm.quote.create",
        "crm.quote.edit",
        "crm.contract.list_own",
        "crm.contract.view",
        "crm.order.list_own",
        "crm.order.view",
        "crm.order.create",
        "crm.order.edit",
        "crm.order.place",
        "crm.order.convert",
        "crm.payment.list_own",
        "crm.payment.view",
        "crm.payment.create",
        "crm.payment.edit",
    }
)

# sales_manager 在 sales 之上新增（v0.7）
SALES_MANAGER_NEW: frozenset[str] = SALES_NEW | frozenset(
    {
        "crm.deal.list_team",
        "crm.deal.list_territory",
        "crm.deal.assign",
        "crm.deal.delete",
        "crm.quote.list_all",
        "crm.quote.send",
        "crm.quote.accept",
        "crm.quote.delete",
        "crm.contract.list_all",
        "crm.contract.create",
        "crm.contract.edit",
        "crm.contract.sign",
        "crm.contract.delete",
        "crm.order.list_team",
        "crm.order.list_territory",
        "crm.order.assign",
        "crm.order.delete",
        "crm.payment.list_team",
        "crm.payment.list_territory",
        "crm.payment.confirm",
        "crm.payment.reverse",
        "crm.payment.delete",
    }
)

# marketing 在原默认集之上新增（v0.7，只读 + 商机新建）
MARKETING_NEW: frozenset[str] = frozenset(
    {
        "crm.deal.list_own",
        "crm.deal.view",
        "crm.deal.create",
        "crm.quote.list_own",
        "crm.quote.view",
        "crm.contract.list_own",
        "crm.contract.view",
        "crm.order.list_own",
        "crm.order.view",
    }
)

NEW_ROLE_PERMS: tuple[tuple[str, frozenset[str]], ...] = (
    ("sales", SALES_NEW),
    ("sales_manager", SALES_MANAGER_NEW),
    ("marketing", MARKETING_NEW),
)


def _insert_permission(conn, role_id: str, perm: str, dialect: str) -> None:
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

        # 1) admin 角色自动获得全部新权限
        admin_row = conn.execute(
            sa.text(
                """
                SELECT id FROM tenant_roles
                WHERE tenant_id = :tid AND code = 'admin' AND is_system = true
                LIMIT 1
                """
            ),
            {"tid": tid},
        ).fetchone()
        if admin_row:
            admin_id = str(admin_row[0])
            for perm in CRM_23_PERMISSIONS:
                _insert_permission(conn, admin_id, perm, dialect)

        # 2) sales / sales_manager / marketing 角色按默认集补种
        for code, perms in NEW_ROLE_PERMS:
            role_row = conn.execute(
                sa.text(
                    """
                    SELECT id FROM tenant_roles
                    WHERE tenant_id = :tid AND code = :code
                    LIMIT 1
                    """
                ),
                {"tid": tid, "code": code},
            ).fetchone()
            if role_row:
                role_id = str(role_row[0])
                for perm in perms:
                    _insert_permission(conn, role_id, perm, dialect)


def downgrade() -> None:
    conn = op.get_bind()
    for perm in CRM_23_PERMISSIONS:
        conn.execute(
            sa.text("DELETE FROM tenant_role_permissions WHERE permission_code = :perm"),
            {"perm": perm},
        )
