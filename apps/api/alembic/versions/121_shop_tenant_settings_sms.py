"""A15-S 短信领权：shop_tenant_settings + 平台签名/模板骨架。

Revision ID: 121
Revises: 120
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "121"
down_revision = "120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_sms_signatures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("content", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="approved"),
        sa.Column("provider_sig_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "platform_sms_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False, server_default="claim_link"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="approved"),
        sa.Column("signature_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["signature_id"], ["platform_sms_signatures.id"]),
    )
    op.create_table(
        "shop_tenant_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sms_signature_id", sa.Uuid(), nullable=True),
        sa.Column("claim_template_id", sa.Uuid(), nullable=True),
        sa.Column("claim_landing_base", sa.String(length=500), nullable=True),
        sa.Column("claim_expire_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("domain_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("domain_verified_base", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sms_signature_id"], ["platform_sms_signatures.id"]),
        sa.ForeignKeyConstraint(["claim_template_id"], ["platform_sms_templates.id"]),
        sa.UniqueConstraint("tenant_id", name="uq_shop_tenant_settings_tenant"),
    )
    op.create_index("ix_shop_tenant_settings_tenant_id", "shop_tenant_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("shop_tenant_settings")
    op.drop_table("platform_sms_templates")
    op.drop_table("platform_sms_signatures")
