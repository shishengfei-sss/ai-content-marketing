"""Extend industry_packs as configurable AI assistants

Revision ID: 007
Revises: 006
Create Date: 2026-07-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FINANCE_SYSTEM_ROLE = (
    "你是一名专业的财税营销内容创作助手，为代理记账公司撰写{platform}{format}。"
)
FINANCE_COMPLIANCE = """1. 内容必须合规，不得承诺「保证不被查」「零风险」等表述
2. 必须包含免责声明（图文文末；视频脚本在最后一镜口播/字幕中体现）：{disclaimer}
3. 语气专业、亲切，适合中小企业主阅读
4. 直接输出正文内容，不要输出 JSON 或多余解释"""
FINANCE_DISCLAIMER = "本文仅供参考，具体政策以税务机关最新规定为准"
FINANCE_WELCOME = (
    "您好，我是{assistant_name}。直接告诉我您想创作什么，或点击下方快捷选题开始——"
    "我会帮您生成符合行业合规要求的营销内容。"
)


def upgrade() -> None:
    with op.batch_alter_table("industry_packs") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("system_role", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("compliance_rules", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("disclaimer", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("default_tone", sa.String(length=100), nullable=False, server_default="专业亲切")
        )
        batch_op.add_column(sa.Column("welcome_message", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE industry_packs SET
              description = :desc,
              system_role = :role,
              compliance_rules = :rules,
              disclaimer = :disclaimer,
              welcome_message = :welcome,
              sort_order = 0
            WHERE code = 'finance'
            """
        ),
        {
            "desc": "代理记账/财税行业专家，熟悉报税、注册与合规营销话术",
            "role": FINANCE_SYSTEM_ROLE,
            "rules": FINANCE_COMPLIANCE,
            "disclaimer": FINANCE_DISCLAIMER,
            "welcome": FINANCE_WELCOME,
        },
    )


def downgrade() -> None:
    with op.batch_alter_table("industry_packs") as batch_op:
        batch_op.drop_column("sort_order")
        batch_op.drop_column("welcome_message")
        batch_op.drop_column("default_tone")
        batch_op.drop_column("disclaimer")
        batch_op.drop_column("compliance_rules")
        batch_op.drop_column("system_role")
        batch_op.drop_column("description")
