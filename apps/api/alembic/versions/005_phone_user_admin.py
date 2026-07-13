"""phone auth, user is_active, platform admin seed

Revision ID: 005
Revises: 004
Create Date: 2026-07-03

"""

from typing import Sequence, Union
import uuid

import bcrypt
import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123456"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        batch_op.alter_column("email", existing_type=sa.String(255), nullable=True)

    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    conn = op.get_bind()
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO tenants (id, name, industry_code) VALUES (:tid, :name, 'finance')"
        ),
        {"tid": tenant_id, "name": "平台管理"},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO users (id, tenant_id, email, phone, hashed_password, display_name, role, is_active)
            VALUES (:uid, :tid, NULL, :phone, :pwd, '平台管理员', 'platform_admin', true)
            """
        ),
        {
            "uid": user_id,
            "tid": tenant_id,
            "phone": ADMIN_PHONE,
            "pwd": _hash_password(ADMIN_PASSWORD),
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM users WHERE phone = :phone"), {"phone": ADMIN_PHONE})
    conn.execute(sa.text("DELETE FROM tenants WHERE name = '平台管理'"))

    op.drop_index("ix_users_phone", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("phone")
        batch_op.alter_column("email", existing_type=sa.String(255), nullable=False)
