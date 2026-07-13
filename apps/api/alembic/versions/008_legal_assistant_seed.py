"""Seed legal AI assistant with templates and platform KB

Revision ID: 008
Revises: 007
Create Date: 2026-07-03

"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGAL_SYSTEM_ROLE = "你是一名专业的法律服务营销内容创作助手，为律师事务所及法务服务机构撰写{platform}{format}。"
LEGAL_COMPLIANCE = """1. 不得承诺「包赢官司」「100%胜诉」或暗示与司法机关有特殊关系
2. 不得提供具体个案的法律意见，营销内容仅作普法与品牌介绍
3. 必须包含免责声明（图文文末；视频脚本在最后一镜口播/字幕中体现）：{disclaimer}
4. 语气{tone}，适合有法律需求的中小企业主与个人用户
5. 直接输出正文内容，不要输出 JSON 或多余解释"""
LEGAL_DISCLAIMER = "本文仅供普法参考，不构成具体法律意见，如需法律服务请咨询执业律师"
LEGAL_WELCOME = (
    "您好，我是{assistant_name}。告诉我您想创作的法律营销主题，"
    "我会先给出几个创作方向，再帮您生成合规的普法或品牌内容。"
)

LEGAL_KB_TEXT = """【法律服务营销合规】
- 禁止 guarantee 诉讼结果，可使用「过往案例」「常见风险」等表述
- 律师姓名、执业证号在广告中需符合律协规定
- 普法内容应准确引用法律条文名称，避免过时条款

【常见服务场景】
- 企业常年法律顾问：合同审查、劳动人事、合规培训
- 诉讼仲裁代理：民商事、劳动争议、知识产权
- 创业法务：股权架构、融资协议、合规设立

【目标受众】
- 中小企业主关注用工风险、合同违约、知识产权
- 个人用户关注借贷、租赁、婚姻继承等常见问题
"""

LEGAL_TEMPLATES = [
    ("contract_review_tips", "wechat", "合同审查要点", "面向企业主介绍签约前需关注的条款与风险点"),
    ("labor_dispute_guide", "wechat", "劳动纠纷指南", "企业用工常见纠纷类型与预防建议"),
    ("startup_legal_pack", "wechat", "创业法务套餐", "创业公司应优先配置的法律服务模块"),
    ("ip_protection_intro", "wechat", "知识产权保护", "商标、专利、著作权基础科普"),
    ("lawyer_brand_story", "wechat", "律所品牌故事", "以专业团队与成功案例建立信任，避免结果承诺"),
    ("contract_review_tips", "xhs", "合同避坑笔记", "小红书风格合同签约避坑清单"),
    ("labor_rights", "xhs", "劳动权益笔记", "打工人/老板双视角劳动权益科普"),
    ("startup_legal_pack", "xhs", "创业法务种草", "创业阶段法务服务种草笔记"),
    ("legal_consult_script", "douyin", "法律咨询脚本", "30秒内普法口播分镜，强调咨询律师"),
    ("contract_myth_script", "douyin", "合同误区脚本", "常见合同认知误区短视频脚本"),
]


def upgrade() -> None:
    conn = op.get_bind()

    existing = conn.execute(sa.text("SELECT id FROM industry_packs WHERE code = 'legal'")).fetchone()
    if existing:
        return

    legal_id = uuid.uuid4()
    conn.execute(
        sa.text(
            """
            INSERT INTO industry_packs (
              id, code, name, description, system_role, compliance_rules,
              disclaimer, default_tone, welcome_message, sort_order, is_active
            ) VALUES (
              :id, 'legal', '法律服务/律所', :desc, :role, :rules,
              :disclaimer, '专业严谨', :welcome, 10, true
            )
            """
        ),
        {
            "id": str(legal_id),
            "desc": "律师事务所与法务服务机构营销专家，侧重普法与品牌内容",
            "role": LEGAL_SYSTEM_ROLE,
            "rules": LEGAL_COMPLIANCE,
            "disclaimer": LEGAL_DISCLAIMER,
            "welcome": LEGAL_WELCOME,
        },
    )

    for scene, platform, name, hint in LEGAL_TEMPLATES:
        conn.execute(
            sa.text(
                """
                INSERT INTO content_templates (
                  id, industry_code, platform, scene, name, prompt_hint, is_active
                ) VALUES (
                  :id, 'legal', :platform, :scene, :name, :hint, true
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "platform": platform,
                "scene": scene,
                "name": name,
                "hint": hint,
            },
        )

    doc_id = uuid.uuid4()
    conn.execute(
        sa.text(
            """
            INSERT INTO knowledge_documents (
              id, tenant_id, industry_code, scope, title, file_name,
              raw_text, status, chunk_count
            ) VALUES (
              :id, NULL, 'legal', 'platform', '法律行业公共 FAQ', 'legal_faq.txt',
              :text, 'parsed', :count
            )
            """
        ),
        {"id": str(doc_id), "text": LEGAL_KB_TEXT, "count": len(LEGAL_KB_TEXT.split("\n\n"))},
    )

    chunks = [p.strip() for p in LEGAL_KB_TEXT.split("\n\n") if p.strip()]
    for idx, text in enumerate(chunks):
        conn.execute(
            sa.text(
                """
                INSERT INTO knowledge_chunks (
                  id, document_id, tenant_id, industry_code, scope, chunk_index, content
                ) VALUES (
                  :id, :doc_id, NULL, 'legal', 'platform', :idx, :content
                )
                """
            ),
            {"id": str(uuid.uuid4()), "doc_id": str(doc_id), "idx": idx, "content": text},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM knowledge_chunks WHERE industry_code = 'legal' AND scope = 'platform'"))
    conn.execute(sa.text("DELETE FROM knowledge_documents WHERE industry_code = 'legal' AND scope = 'platform'"))
    conn.execute(sa.text("DELETE FROM content_templates WHERE industry_code = 'legal'"))
    conn.execute(sa.text("DELETE FROM industry_packs WHERE code = 'legal'"))
