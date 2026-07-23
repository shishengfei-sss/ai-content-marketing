"""093 qa fixes: tenant active, lead icp_score, persona packs

Revision ID: 093
Revises: 092

- tenants.is_active：平台可禁用/启用租户
- leads.icp_score：线索 ICP 匹配分
- industry_packs 种子 P-001～P-009（营销顾问人格）
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "093"
down_revision: Union[str, None] = "092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERSONAS = [
    ("P-001", "温暖顾问型", "焦虑不安、缺乏信心、初次咨询"),
    ("P-002", "强势推进型", "犹豫不决、反复纠结"),
    ("P-003", "小白友好型", "缺乏领域知识"),
    ("P-004", "专业顾问型", "有一定认知、看重专业度"),
    ("P-005", "朋友闲聊型", "关系导向、喜欢轻松沟通"),
    ("P-006", "效率导向型", "时间紧、要结论"),
    ("P-007", "谨慎合规型", "关注风险与合规"),
    ("P-008", "价值挖掘型", "需要被看见痛点与价值"),
    ("P-009", "陪跑教练型", "长期跟进、需要陪伴"),
]


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("leads", sa.Column("icp_score", sa.Integer(), nullable=True))

    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(sa.text("SELECT code FROM industry_packs")).fetchall()
    }
    for i, (code, name, desc) in enumerate(PERSONAS):
        if code in existing:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO industry_packs
                (id, code, name, description, system_role, compliance_rules, disclaimer,
                 default_tone, welcome_message, sort_order, is_active)
                VALUES
                (:id, :code, :name, :description, :system_role, :compliance_rules, :disclaimer,
                 :default_tone, :welcome_message, :sort_order, true)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "code": code,
                "name": name,
                "description": desc,
                "system_role": f"你是营销顾问人格【{name}】，按该人格风格协助用户创作与沟通。",
                "compliance_rules": "内容必须合规，不得夸大承诺或误导用户。",
                "disclaimer": "本文仅供参考，具体以相关部门最新规定为准",
                "default_tone": "专业亲切",
                "welcome_message": f"你好，我是{name}顾问，可以直接告诉我你的需求。",
                "sort_order": 100 + i,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    codes = ", ".join(f"'{c}'" for c, _, _ in PERSONAS)
    conn.execute(sa.text(f"DELETE FROM industry_packs WHERE code IN ({codes})"))
    op.drop_column("leads", "icp_score")
    op.drop_column("tenants", "is_active")
