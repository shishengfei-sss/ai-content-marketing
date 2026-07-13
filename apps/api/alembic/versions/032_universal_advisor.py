"""032 universal marketing advisor — seed marketing pack, deactivate finance/legal

Revision ID: 032
Revises: 031
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MARKETING_SYSTEM_ROLE = (
    "你是面向中小企业与营销人员的【通用营销创作顾问】，"
    "帮助用户在{platform}平台创作{format}类营销内容。"
    "用户可自述任意行业题材；优先依据租户知识库与用户提供要点，不得编造数据与案例。"
)
MARKETING_COMPLIANCE = """1. 内容必须合规，不得夸大承诺（如「保证涨粉」「零风险」「100%有效」等）
2. 必须包含免责声明（图文文末；视频脚本在最后一镜口播/字幕中体现）：{disclaimer}
3. 语气{tone}，专业但不装，适合目标受众阅读
4. 直接输出正文内容，不要输出 JSON 或多余解释
5. 不代用户发布；引导用户在界面确认后自行发布"""
MARKETING_DISCLAIMER = "本文仅供参考，具体以平台规则与相关部门最新规定为准"
MARKETING_WELCOME = """你好！我是小营，你的 AI 营销创作顾问。我可以帮你：
1. 理清选题与受众（任意行业/题材）
2. 生成 3～5 个创作方向
3. 撰写公众号 / 小红书 / 抖音稿件或脚本
4. 合规自检与发布前确认
你想从哪开始？也可以直接说：平台 + 想写的主题。"""

MARKETING_TEMPLATES = [
    ("brand_intro", "wechat", "品牌介绍", "介绍企业/品牌定位、核心价值与服务特色"),
    ("product_promo", "wechat", "产品促销", "活动促销、限时优惠、转化导向"),
    ("knowledge_tips", "wechat", "知识科普", "行业知识科普，建立专业信任"),
    ("customer_case", "wechat", "客户案例", "客户成功案例故事化呈现"),
    ("holiday_marketing", "wechat", "节日热点", "结合节假日/热点的营销内容"),
    ("event_invite", "wechat", "活动邀约", "线下/线上活动报名邀约"),
    ("service_faq", "wechat", "服务答疑", "常见疑问解答型内容"),
    ("team_culture", "wechat", "团队文化", "团队故事、文化价值观"),
    ("new_launch", "wechat", "新品上新", "新品/新服务发布"),
    ("user_testimonial", "wechat", "用户口碑", "用户评价与口碑传播"),
    ("industry_insight", "wechat", "行业洞察", "趋势观点、深度解读"),
    ("local_life", "wechat", "本地生活", "本地门店、生活服务种草"),
    ("brand_intro", "xhs", "品牌种草", "小红书风格品牌笔记，短句+话题标签"),
    ("product_promo", "xhs", "促销笔记", "小红书促销转化笔记"),
    ("knowledge_tips", "xhs", "干货笔记", "小红书干货科普笔记"),
    ("customer_case", "xhs", "案例笔记", "小红书案例故事笔记"),
    ("holiday_marketing", "xhs", "热点笔记", "节日/热点营销笔记"),
    ("brand_intro", "douyin", "品牌口播", "15-30秒品牌介绍短视频脚本"),
    ("product_promo", "douyin", "促销脚本", "短视频促销转化脚本"),
    ("knowledge_tips", "douyin", "科普脚本", "短视频知识科普脚本"),
]

PLATFORM_MARKETING_KB = """【通用营销合规】不得使用「保证涨粉」「百分百转化」「零风险」等绝对化承诺；不得编造客户案例、数据、联系方式。

【公众号】标题吸引但不标题党；正文结构清晰；文末可引导关注/私信，不自动发布。

【小红书】笔记口语化、分段短；合理使用话题标签；避免硬广堆砌。

【抖音】口播脚本分镜清晰；前 3 秒抓住注意力；总时长建议 15～60 秒。

【知识库原则】业务卖点优先来自租户知识库；无检索结果时诚实说明并请用户补充要点，禁止编造价格、地址、电话。"""


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("UPDATE industry_packs SET is_active = false WHERE code IN ('finance', 'legal')")
    )

    existing = conn.execute(
        sa.text("SELECT id FROM industry_packs WHERE code = 'marketing'")
    ).fetchone()
    if existing:
        conn.execute(
            sa.text(
                """
                UPDATE industry_packs SET
                  name = :name,
                  description = :desc,
                  system_role = :role,
                  compliance_rules = :rules,
                  disclaimer = :disclaimer,
                  welcome_message = :welcome,
                  default_tone = '专业亲切',
                  sort_order = 0,
                  is_active = true
                WHERE code = 'marketing'
                """
            ),
            {
                "name": "小营 · 营销创作顾问",
                "desc": "通用营销创作顾问，支持任意题材与多平台内容生成",
                "role": MARKETING_SYSTEM_ROLE,
                "rules": MARKETING_COMPLIANCE,
                "disclaimer": MARKETING_DISCLAIMER,
                "welcome": MARKETING_WELCOME,
            },
        )
    else:
        conn.execute(
            sa.text(
                """
                INSERT INTO industry_packs (
                  id, code, name, description, system_role, compliance_rules,
                  disclaimer, default_tone, welcome_message, sort_order, is_active
                ) VALUES (
                  :id, 'marketing', :name, :desc, :role, :rules,
                  :disclaimer, '专业亲切', :welcome, 0, true
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "name": "小营 · 营销创作顾问",
                "desc": "通用营销创作顾问，支持任意题材与多平台内容生成",
                "role": MARKETING_SYSTEM_ROLE,
                "rules": MARKETING_COMPLIANCE,
                "disclaimer": MARKETING_DISCLAIMER,
                "welcome": MARKETING_WELCOME,
            },
        )

    for scene, platform, name, hint in MARKETING_TEMPLATES:
        row = conn.execute(
            sa.text(
                """
                SELECT id FROM content_templates
                WHERE industry_code = 'marketing' AND platform = :platform AND scene = :scene
                """
            ),
            {"platform": platform, "scene": scene},
        ).fetchone()
        if row:
            conn.execute(
                sa.text(
                    """
                    UPDATE content_templates SET name = :name, prompt_hint = :hint, is_active = true
                    WHERE industry_code = 'marketing' AND platform = :platform AND scene = :scene
                    """
                ),
                {"name": name, "hint": hint, "platform": platform, "scene": scene},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO content_templates (
                      id, industry_code, platform, scene, name, prompt_hint, is_active
                    ) VALUES (
                      :id, 'marketing', :platform, :scene, :name, :hint, true
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

    doc = conn.execute(
        sa.text(
            "SELECT id FROM knowledge_documents WHERE industry_code = 'marketing' AND scope = 'platform'"
        )
    ).fetchone()
    if not doc:
        doc_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO knowledge_documents (
                  id, tenant_id, industry_code, scope, title, file_name, raw_text, status, chunk_count
                ) VALUES (
                  :id, NULL, 'marketing', 'platform', '通用营销合规与平台写法', 'marketing_guide.txt',
                  :text, 'parsed', 0
                )
                """
            ),
            {"id": doc_id, "text": PLATFORM_MARKETING_KB},
        )
        chunks = [p.strip() for p in PLATFORM_MARKETING_KB.split("\n\n") if p.strip()]
        for idx, text in enumerate(chunks):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO knowledge_chunks (
                      id, document_id, tenant_id, industry_code, scope, chunk_index, content
                    ) VALUES (
                      :id, :doc_id, NULL, 'marketing', 'platform', :idx, :content
                    )
                    """
                ),
                {"id": str(uuid.uuid4()), "doc_id": doc_id, "idx": idx, "content": text},
            )
        conn.execute(
            sa.text("UPDATE knowledge_documents SET chunk_count = :n WHERE id = :id"),
            {"n": len(chunks), "id": doc_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM knowledge_chunks WHERE industry_code = 'marketing'"))
    conn.execute(sa.text("DELETE FROM knowledge_documents WHERE industry_code = 'marketing'"))
    conn.execute(sa.text("DELETE FROM content_templates WHERE industry_code = 'marketing'"))
    conn.execute(sa.text("DELETE FROM industry_packs WHERE code = 'marketing'"))
    conn.execute(
        sa.text("UPDATE industry_packs SET is_active = true WHERE code IN ('finance', 'legal')")
    )
