"""knowledge, templates, brand, export

Revision ID: 004
Revises: 003
Create Date: 2026-07-02

"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FINANCE_TEMPLATES = [
    ("tax_deadline_reminder", "wechat", "报税截止提醒", "提醒企业主在申报截止日前完成报税，语气紧迫但不恐吓"),
    ("bookkeeping_intro", "wechat", "代理记账介绍", "介绍代理记账服务价值与流程"),
    ("small_company_register", "wechat", "新公司注册指南", "新公司注册与记账报税入门"),
    ("case_penalty_story", "wechat", "税务处罚案例", "以案例说明合规记账的重要性"),
    ("vat_intro", "wechat", "增值税基础知识", "面向小白的增值税科普"),
    ("invoice_management", "wechat", "发票管理要点", "发票开具、保管、认证注意事项"),
    ("tax_planning_tips", "wechat", "合法节税建议", "合规前提下的税务筹划常识"),
    ("annual_report_reminder", "wechat", "年报提醒", "工商年报与税务年报时间节点"),
    ("social_insurance", "wechat", "社保公积金", "企业社保开户与缴纳要点"),
    ("freelancer_tax", "wechat", "自由职业者报税", "个体户与自由职业者税务处理"),
    ("export_tax_rebate", "wechat", "出口退税简介", "出口企业退税基础流程"),
    ("high_tech_preferential", "wechat", "高新税收优惠", "高新技术企业认定与优惠"),
    ("invoice_electronic", "wechat", "全电发票", "全电发票推广与使用指南"),
    ("cost_control_tips", "wechat", "成本控制", "小微企业成本与费用管理建议"),
    ("financial_health_check", "wechat", "财税健康体检", "企业财税风险自检清单"),
    ("bookkeeping_intro", "xhs", "代理记账种草", "小红书风格，短句+emoji+话题标签"),
    ("tax_deadline_reminder", "xhs", "报税提醒笔记", "小红书笔记风格报税提醒"),
    ("small_company_register", "xhs", "注册避坑", "新公司注册避坑指南笔记"),
    ("case_penalty_story", "xhs", "处罚案例故事", "故事化税务处罚案例"),
    ("bookkeeping_intro", "douyin", "代账服务脚本", "15-30秒口播分镜脚本"),
    ("tax_deadline_reminder", "douyin", "报税提醒脚本", "报税截止短视频脚本"),
    ("small_company_register", "douyin", "注册指南脚本", "注册流程短视频脚本"),
]

PLATFORM_KB_TEXT = """【小规模纳税人】增值税征收率一般为1%或3%（以最新政策为准），季度销售额未超限额可享免征政策。

【代理记账】一般包括：原始凭证整理、记账、报税、财务报表、年度汇算清缴咨询等。

【申报节点】增值税按月或按季申报；企业所得税按季预缴、年度汇算清缴；个人所得税通常按月代扣代缴。

【发票管理】取得发票应及时入账；虚开发票、隐匿收入属于严重违法行为。

【新设公司】领取营业执照后30日内应办理税务登记（现为自动登记），并按期申报即使无收入也需零申报。

【社保】企业应为职工依法缴纳社会保险，未缴可能面临补缴与滞纳金。

【风险提示】请勿相信「保证不被查」「百分百节税」等承诺，应选择正规持牌机构。"""


def upgrade() -> None:
    op.create_table(
        "industry_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "content_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("industry_code", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("scene", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("prompt_hint", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_templates_lookup", "content_templates", ["industry_code", "platform", "scene"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("industry_code", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("file_name", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="parsed"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("industry_code", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_scope", "knowledge_chunks", ["industry_code", "scope", "tenant_id"])

    op.create_table(
        "tenant_brand_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("company_display_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("tone", sa.String(length=100), nullable=False, server_default="专业亲切"),
        sa.Column("cta_text", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("sample_snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )

    op.create_table(
        "user_prompt_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("global_instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "export_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("export_type", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=300), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    industry_table = sa.table(
        "industry_packs",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    template_table = sa.table(
        "content_templates",
        sa.column("id", sa.Uuid()),
        sa.column("industry_code", sa.String()),
        sa.column("platform", sa.String()),
        sa.column("scene", sa.String()),
        sa.column("name", sa.String()),
        sa.column("prompt_hint", sa.Text()),
        sa.column("is_active", sa.Boolean()),
    )
    industry_id = uuid.uuid4()
    op.bulk_insert(
        industry_table,
        [{"id": industry_id, "code": "finance", "name": "代理记账/财税", "is_active": True}],
    )

    template_rows = []
    for scene, platform, name, hint in FINANCE_TEMPLATES:
        template_rows.append(
            {
                "id": uuid.uuid4(),
                "industry_code": "finance",
                "platform": platform,
                "scene": scene,
                "name": name,
                "prompt_hint": hint,
                "is_active": True,
            }
        )
    op.bulk_insert(template_table, template_rows)

    doc_id = uuid.uuid4()
    doc_table = sa.table(
        "knowledge_documents",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("industry_code", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("title", sa.String()),
        sa.column("file_name", sa.String()),
        sa.column("raw_text", sa.Text()),
        sa.column("status", sa.String()),
        sa.column("chunk_count", sa.Integer()),
    )
    op.bulk_insert(
        doc_table,
        [
            {
                "id": doc_id,
                "tenant_id": None,
                "industry_code": "finance",
                "scope": "platform",
                "title": "财税行业公共 FAQ",
                "file_name": "finance_faq.txt",
                "raw_text": PLATFORM_KB_TEXT,
                "status": "parsed",
                "chunk_count": 0,
            }
        ],
    )

    chunks = [p.strip() for p in PLATFORM_KB_TEXT.split("\n\n") if p.strip()]
    chunk_table = sa.table(
        "knowledge_chunks",
        sa.column("id", sa.Uuid()),
        sa.column("document_id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("industry_code", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("chunk_index", sa.Integer()),
        sa.column("content", sa.Text()),
    )
    op.bulk_insert(
        chunk_table,
        [
            {
                "id": uuid.uuid4(),
                "document_id": doc_id,
                "tenant_id": None,
                "industry_code": "finance",
                "scope": "platform",
                "chunk_index": idx,
                "content": text,
            }
            for idx, text in enumerate(chunks)
        ],
    )
    op.execute(sa.text(f"UPDATE knowledge_documents SET chunk_count = {len(chunks)} WHERE id = '{doc_id}'"))


def downgrade() -> None:
    op.drop_table("export_records")
    op.drop_table("user_prompt_profiles")
    op.drop_table("tenant_brand_profiles")
    op.drop_index("ix_knowledge_chunks_scope", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_index("ix_content_templates_lookup", table_name="content_templates")
    op.drop_table("content_templates")
    op.drop_table("industry_packs")
