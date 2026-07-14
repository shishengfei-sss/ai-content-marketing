"""038 entity auto-numbering: columns + rules/counters tables + seed + backfill (v0.8)

Revision ID: 038
Revises: 037
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 9 实体编号规则默认种子：prefix / date_format / seq_width / reset_period
# reset_period: once=永不 | daily=每日 | weekly=每周 | monthly=每月 | yearly=每年
DEFAULT_RULES: tuple[tuple[str, str, str, int, str], ...] = (
    ("lead", "XS", "%Y%m%d", 3, "once"),
    ("customer", "KH", "%Y%m%d", 3, "once"),
    ("task", "RW", "%Y%m%d", 3, "once"),
    ("campaign", "HD", "%Y%m%d", 3, "once"),
    ("deal", "SJ", "%Y%m%d", 3, "once"),
    ("quote", "BJ", "%Y%m%d", 3, "once"),
    ("contract", "HT", "%Y%m%d", 3, "once"),
    ("order", "DD", "%Y%m%d", 3, "once"),
    ("payment", "HK", "%Y%m%d", 3, "once"),
    ("product", "CP", "%Y%m%d", 3, "once"),
)

# 5 个新加编号列的实体（列名, 表名, 前缀）
NEW_NUMBER_ENTITIES: tuple[tuple[str, str, str], ...] = (
    ("lead_number", "leads", "XS"),
    ("customer_number", "customers", "KH"),
    ("task_number", "crm_tasks", "RW"),
    ("campaign_number", "marketing_campaigns", "HD"),
    ("deal_number", "deals", "SJ"),
)

# 4 个已有编号列的实体（列名, 表名）——仅补唯一索引
EXISTING_NUMBER_ENTITIES: tuple[tuple[str, str], ...] = (
    ("quote_number", "quotes"),
    ("contract_number", "contracts"),
    ("order_number", "orders"),
    ("payment_number", "payments"),
)


def _dialect() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    conn = op.get_bind()
    dialect = _dialect()

    # 1) 5 个新编号列 + 普通索引
    for col, table, _ in NEW_NUMBER_ENTITIES:
        op.add_column(table, sa.Column(col, sa.String(length=50), nullable=True))
        op.create_index(f"ix_{table}_{col}", table, [col])

    # 2) 9 实体 (tenant_id, number) 唯一索引（NULL 允许重复，两种方言均支持）
    for col, table, _ in NEW_NUMBER_ENTITIES:
        op.create_index(
            f"uq_{table}_tenant_{col}", table, ["tenant_id", col], unique=True
        )
    for col, table in EXISTING_NUMBER_ENTITIES:
        op.create_index(
            f"uq_{table}_tenant_{col}", table, ["tenant_id", col], unique=True
        )

    # 3) 规则表 + 计数器表
    op.create_table(
        "entity_number_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("prefix", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("date_format", sa.String(length=20), nullable=False, server_default="%Y%m%d"),
        sa.Column("seq_width", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("reset_period", sa.String(length=10), nullable=False, server_default="daily"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "entity_type", name="uq_number_rules_tenant_entity"
        ),
    )
    op.create_table(
        "entity_number_counters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("period_key", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "entity_type", "period_key",
            name="uq_number_counters_tenant_entity_period",
        ),
    )

    # 4) 默认规则种子（按租户）
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        tid = str(tenant_id)
        for entity_type, prefix, date_fmt, seq_w, reset in DEFAULT_RULES:
            if dialect == "postgresql":
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO entity_number_rules
                            (id, tenant_id, entity_type, prefix, date_format, seq_width, reset_period, enabled)
                        VALUES (:id, :tid, :et, :pf, :df, :sw, :rp, true)
                        ON CONFLICT (tenant_id, entity_type) DO NOTHING
                        """
                    ),
                    {
                        "id": uuid.uuid4().hex,
                        "tid": tid,
                        "et": entity_type,
                        "pf": prefix,
                        "df": date_fmt,
                        "sw": seq_w,
                        "rp": reset,
                    },
                )
            else:
                conn.execute(
                    sa.text(
                        """
                        INSERT OR IGNORE INTO entity_number_rules
                            (id, tenant_id, entity_type, prefix, date_format, seq_width, reset_period, enabled)
                        VALUES (:id, :tid, :et, :pf, :df, :sw, :rp, 1)
                        """
                    ),
                    {
                        "id": uuid.uuid4().hex,
                        "tid": tid,
                        "et": entity_type,
                        "pf": prefix,
                        "df": date_fmt,
                        "sw": seq_w,
                        "rp": reset,
                    },
                )

    # 5) 存量回填：为 5 个新编号列的已有行分配编号（prefix + 6 位序号）
    for col, table, prefix in NEW_NUMBER_ENTITIES:
        rows = conn.execute(
            sa.text(f"SELECT id, tenant_id FROM {table} WHERE {col} IS NULL ORDER BY created_at")
        ).fetchall()
        per_tenant_seq: dict[str, int] = {}
        for rid, tenant_id in rows:
            tid = str(tenant_id)
            seq = per_tenant_seq.get(tid, 0) + 1
            per_tenant_seq[tid] = seq
            number = f"{prefix}{seq:06d}"
            conn.execute(
                sa.text(f"UPDATE {table} SET {col} = :num WHERE id = :rid"),
                {"num": number, "rid": str(rid)},
            )


def downgrade() -> None:
    op.drop_table("entity_number_counters")
    op.drop_table("entity_number_rules")

    for col, table, _ in NEW_NUMBER_ENTITIES:
        op.drop_index(f"uq_{table}_tenant_{col}", table_name=table)
    for col, table in EXISTING_NUMBER_ENTITIES:
        op.drop_index(f"uq_{table}_tenant_{col}", table_name=table)

    for col, table, _ in NEW_NUMBER_ENTITIES:
        op.drop_index(f"ix_{table}_{col}", table_name=table)
        op.drop_column(table, col)
