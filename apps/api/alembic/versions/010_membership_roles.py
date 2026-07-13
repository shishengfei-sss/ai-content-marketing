"""Membership, tenant roles and permissions (v0.3)

Revision ID: 010
Revises: 009
Create Date: 2026-07-06

"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALL_PERMISSIONS = (
    "content.create",
    "content.list_own",
    "content.view_own",
    "content.list_all",
    "content.view_all",
    "content.edit",
    "content.delete",
    "content.export",
    "content.schedule",
    "content.publish",
    "knowledge.view",
    "knowledge.manage",
    "preference.manage",
    "brand.manage",
    "wechat.manage",
    "llm.manage",
    "tenant.manage",
    "dashboard.view",
    "dashboard.view_all",
    "analytics.view",
    "analytics.view_all",
    "team.member.view",
    "team.member.manage",
    "team.role.manage",
)

EDITOR_DEFAULT = frozenset(
    {
        "content.create",
        "content.list_own",
        "content.view_own",
        "preference.manage",
        "dashboard.view",
        "analytics.view",
    }
)


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.add_column(sa.Column("credit_code", sa.String(18), nullable=True))

    op.create_table(
        "tenant_roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tenant_roles_tenant_code"),
    )

    op.create_table(
        "tenant_role_permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("tenant_roles.id"), nullable=False),
        sa.Column("permission_code", sa.String(80), nullable=False),
        sa.UniqueConstraint("role_id", "permission_code", name="uq_role_permission"),
    )

    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("tenant_roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )

    conn = op.get_bind()

    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        admin_role_id = uuid.uuid4().hex
        editor_role_id = uuid.uuid4().hex
        conn.execute(
            sa.text(
                """
                INSERT INTO tenant_roles (id, tenant_id, code, name, is_system)
                VALUES (:id, :tid, 'admin', '企业管理员', true)
                """
            ),
            {"id": admin_role_id, "tid": str(tenant_id)},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO tenant_roles (id, tenant_id, code, name, is_system)
                VALUES (:id, :tid, 'editor', '编辑', true)
                """
            ),
            {"id": editor_role_id, "tid": str(tenant_id)},
        )
        for perm in ALL_PERMISSIONS:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                    VALUES (:id, :rid, :code)
                    """
                ),
                {"id": uuid.uuid4().hex, "rid": admin_role_id, "code": perm},
            )
        for perm in EDITOR_DEFAULT:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO tenant_role_permissions (id, role_id, permission_code)
                    VALUES (:id, :rid, :code)
                    """
                ),
                {"id": uuid.uuid4().hex, "rid": editor_role_id, "code": perm},
            )

    users = conn.execute(
        sa.text("SELECT id, tenant_id, role FROM users WHERE role != 'platform_admin'")
    ).fetchall()
    for user_id, tenant_id, _role in users:
        admin_row = conn.execute(
            sa.text(
                """
                SELECT id FROM tenant_roles
                WHERE tenant_id = :tid AND code = 'admin' LIMIT 1
                """
            ),
            {"tid": str(tenant_id)},
        ).fetchone()
        if not admin_row:
            continue
        existing = conn.execute(
            sa.text(
                """
                SELECT id FROM tenant_memberships
                WHERE user_id = :uid AND tenant_id = :tid LIMIT 1
                """
            ),
            {"uid": str(user_id), "tid": str(tenant_id)},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO tenant_memberships (id, user_id, tenant_id, role_id, is_active)
                VALUES (:id, :uid, :tid, :rid, true)
                """
            ),
            {
                "id": uuid.uuid4().hex,
                "uid": str(user_id),
                "tid": str(tenant_id),
                "rid": str(admin_row[0]),
            },
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.drop_table("tenant_memberships")
    op.drop_table("tenant_role_permissions")
    op.drop_table("tenant_roles")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Uuid(), nullable=False)

    with op.batch_alter_table("tenants") as batch_op:
        batch_op.drop_column("credit_code")
