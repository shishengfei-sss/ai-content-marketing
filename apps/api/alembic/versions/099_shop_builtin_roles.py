"""099 shop builtin roles seed + users.platform_shop_role (content acquisition shop Phase1)

Revision ID: 099
Revises: 098
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "099"
down_revision: Union[str, None] = "098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SHOP_BUILTIN_ROLES: tuple[tuple[str, str, frozenset[str]], ...] = (
    (
        "shop_admin",
        "店铺管理员",
        frozenset(
            {
                "shop.analytics.read",
                "shop.buyer.list_all",
                "shop.buyer.view",
                "shop.channel.map",
                "shop.channel.read",
                "shop.content.read",
                "shop.content.write",
                "shop.entitlement.list_all",
                "shop.entitlement.revoke",
                "shop.entitlement.view",
                "shop.invoice.list_all",
                "shop.invoice.process",
                "shop.invoice.view",
                "shop.order.close",
                "shop.order.export",
                "shop.order.list_all",
                "shop.order.list_own",
                "shop.order.refund",
                "shop.order.resend_notify",
                "shop.order.view",
                "shop.product.delete",
                "shop.product.publish",
                "shop.product.read",
                "shop.product.submit_review",
                "shop.product.write",
                "shop.redemption.execute",
                "shop.redemption.list_all",
                "shop.redemption.list_own",
                "shop.redemption.read",
                "shop.settings.read",
                "shop.settings.write",
                "shop.store.manage",
                "shop.store.settings.read",
                "shop.store.settings.write",
                "shop.subscription.usage.read",
            }
        ),
    ),
    (
        "shop_content",
        "内容运营",
        frozenset(
            {
                "shop.analytics.read",
                "shop.content.read",
                "shop.content.write",
                "shop.product.delete",
                "shop.product.publish",
                "shop.product.read",
                "shop.product.submit_review",
                "shop.product.write",
                "shop.subscription.usage.read",
            }
        ),
    ),
    (
        "shop_support",
        "客服",
        frozenset(
            {
                "shop.analytics.read",
                "shop.buyer.list_all",
                "shop.buyer.view",
                "shop.content.read",
                "shop.entitlement.list_all",
                "shop.entitlement.revoke",
                "shop.entitlement.view",
                "shop.invoice.list_all",
                "shop.invoice.process",
                "shop.invoice.view",
                "shop.order.export",
                "shop.order.list_all",
                "shop.order.refund",
                "shop.order.resend_notify",
                "shop.order.view",
                "shop.product.read",
                "shop.redemption.read",
                "shop.subscription.usage.read",
            }
        ),
    ),
    (
        "shop_clerk",
        "店员",
        frozenset(
            {
                "shop.redemption.execute",
                "shop.redemption.list_own",
                "shop.redemption.read",
            }
        ),
    ),
)


def _insert_permissions(conn, role_id: str, perms: frozenset[str], dialect: str) -> None:
    for perm in perms:
        params = {"id": str(uuid.uuid4()), "rid": role_id, "perm": perm}
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

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("platform_shop_role", sa.String(length=50), nullable=True))

    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        tid = str(tenant_id)
        for code, name, perms in SHOP_BUILTIN_ROLES:
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
                        VALUES (:id, :tid, :code, :name, true)
                        """
                    ),
                    {"id": role_id, "tid": tid, "code": code, "name": name},
                )
            _insert_permissions(conn, role_id, perms, dialect)


def downgrade() -> None:
    conn = op.get_bind()
    for code, _, _ in SHOP_BUILTIN_ROLES:
        rows = conn.execute(
            sa.text("SELECT id FROM tenant_roles WHERE code = :code AND is_system = true"),
            {"code": code},
        ).fetchall()
        for (role_id,) in rows:
            conn.execute(
                sa.text("DELETE FROM tenant_role_permissions WHERE role_id = :rid"),
                {"rid": str(role_id)},
            )
        conn.execute(
            sa.text("DELETE FROM tenant_roles WHERE code = :code AND is_system = true"),
            {"code": code},
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("platform_shop_role")
