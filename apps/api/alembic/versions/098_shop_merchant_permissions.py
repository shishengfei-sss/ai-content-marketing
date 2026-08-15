"""098 shop.* merchant permissions for existing admin roles (content acquisition shop Phase1)

Revision ID: 098
Revises: 097
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "098"
down_revision: Union[str, None] = "097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 与 app.permissions.SHOP_MERCHANT_PERMISSIONS 保持同步（迁移不可 import app）
SHOP_MERCHANT_PERMISSIONS: tuple[str, ...] = (
    "shop.analytics.read",
    "shop.buyer.list_all",
    "shop.buyer.view",
    "shop.channel.map",
    "shop.channel.read",
    "shop.channel.write",
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
    "shop.role.manage",
    "shop.settings.read",
    "shop.settings.write",
    "shop.store.manage",
    "shop.store.settings.read",
    "shop.store.settings.write",
    "shop.subscription.usage.read",
)


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


def _existing_admin_role_keys(conn, perm: str) -> set[str]:
    rows = conn.execute(
        sa.text(
            """
            SELECT trp.role_id
            FROM tenant_role_permissions trp
            JOIN tenant_roles tr ON tr.id = trp.role_id
            WHERE tr.code = 'admin' AND trp.permission_code = :perm
            """
        ),
        {"perm": perm},
    ).fetchall()
    return {_role_key(role_id) for (role_id,) in rows}


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    admin_roles = conn.execute(
        sa.text("SELECT id FROM tenant_roles WHERE code = 'admin'")
    ).fetchall()
    for perm in SHOP_MERCHANT_PERMISSIONS:
        have = _existing_admin_role_keys(conn, perm)
        for (role_id,) in admin_roles:
            if _role_key(role_id) not in have:
                _insert_permission(conn, role_id, perm, dialect)


def downgrade() -> None:
    conn = op.get_bind()
    for perm in SHOP_MERCHANT_PERMISSIONS:
        conn.execute(
            sa.text("DELETE FROM tenant_role_permissions WHERE permission_code = :perm"),
            {"perm": perm},
        )
