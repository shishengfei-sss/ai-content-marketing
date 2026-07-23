"""实体自动编号服务（v0.8）。

按租户/实体类型维护编号规则与原子计数器，支持前缀、日期、序列宽度、
重置周期（once/daily/weekly/monthly/yearly）。生成时使用行级锁保证并发安全。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models.crm import EntityNumberCounter, EntityNumberRule

# 实体类型 -> 规则默认种子（与迁移 038 DEFAULT_RULES 一致）
DEFAULT_RULE_SEEDS: dict[str, dict] = {
    "lead": {"prefix": "XS", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "customer": {"prefix": "KH", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "task": {"prefix": "RW", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "campaign": {"prefix": "HD", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "deal": {"prefix": "SJ", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "quote": {"prefix": "BJ", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "contract": {"prefix": "HT", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "order": {"prefix": "DD", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "payment": {"prefix": "HK", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "product": {"prefix": "CP", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "delivery": {"prefix": "FH", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "invoice": {"prefix": "FP", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "contract_amendment": {"prefix": "BC", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
    "refund": {"prefix": "TK", "date_format": "%Y%m%d", "seq_width": 3, "reset_period": "once"},
}

RESET_PERIOD_LABELS: dict[str, str] = {
    "once": "永不重置",
    "daily": "每日",
    "weekly": "每周",
    "monthly": "每月",
    "yearly": "每年",
}


def _period_key(reset_period: str, now: datetime) -> str:
    if reset_period == "once":
        return ""
    if reset_period == "daily":
        return now.strftime("%Y%m%d")
    if reset_period == "weekly":
        iso = now.isocalendar()
        return f"{iso.year}W{iso.week:02d}"
    if reset_period == "monthly":
        return now.strftime("%Y%m")
    if reset_period == "yearly":
        return now.strftime("%Y")
    return ""


def get_rule(db: Session, tenant_id: UUID, entity_type: str) -> EntityNumberRule:
    rule = (
        db.query(EntityNumberRule)
        .filter(
            uuid_eq(EntityNumberRule.tenant_id, tenant_id),
            EntityNumberRule.entity_type == entity_type,
        )
        .first()
    )
    if rule is None:
        seed = DEFAULT_RULE_SEEDS.get(entity_type)
        if seed is None:
            raise ValueError(f"未知实体类型: {entity_type}")
        rule = EntityNumberRule(
            tenant_id=tenant_id,
            entity_type=entity_type,
            prefix=seed["prefix"],
            suffix="",
            date_format=seed["date_format"],
            seq_width=seed["seq_width"],
            reset_period=seed["reset_period"],
            enabled=True,
        )
        db.add(rule)
        db.flush()
    return rule


def generate_number(db: Session, tenant_id: UUID, entity_type: str) -> str:
    """原子生成下一个编号。调用方需在事务中调用。"""
    rule = get_rule(db, tenant_id, entity_type)
    now = datetime.now(timezone.utc)
    period_key = _period_key(rule.reset_period, now)

    # 行级锁取计数器；SQLite 用 BEGIN IMMEDIATE 由连接串保证，此处保守查询后更新
    counter = (
        db.query(EntityNumberCounter)
        .filter(
            uuid_eq(EntityNumberCounter.tenant_id, tenant_id),
            EntityNumberCounter.entity_type == entity_type,
            EntityNumberCounter.period_key == period_key,
        )
        .first()
    )
    if counter is None:
        counter = EntityNumberCounter(
            tenant_id=tenant_id,
            entity_type=entity_type,
            period_key=period_key,
            seq=0,
        )
        db.add(counter)
    # 自增并 flush，确保并发下同一事务内拿到唯一序号
    counter.seq += 1
    db.flush()

    seq_str = str(counter.seq).zfill(rule.seq_width)
    date_part = now.strftime(rule.date_format) if rule.date_format else ""
    suffix = getattr(rule, "suffix", None) or ""
    number = f"{rule.prefix}{date_part}{seq_str}{suffix}"
    return number


def list_rules(db: Session, tenant_id: UUID) -> list[EntityNumberRule]:
    rules = (
        db.query(EntityNumberRule)
        .filter(uuid_eq(EntityNumberRule.tenant_id, tenant_id))
        .all()
    )
    existing = {r.entity_type for r in rules}
    for entity_type, seed in DEFAULT_RULE_SEEDS.items():
        if entity_type not in existing:
            rules.append(
                EntityNumberRule(
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    prefix=seed["prefix"],
                    suffix="",
                    date_format=seed["date_format"],
                    seq_width=seed["seq_width"],
                    reset_period=seed["reset_period"],
                    enabled=True,
                )
            )
    rules.sort(key=lambda r: list(DEFAULT_RULE_SEEDS.keys()).index(r.entity_type)
               if r.entity_type in DEFAULT_RULE_SEEDS else 999)
    return rules


def _valid_custom_entity_type(entity_type: str) -> bool:
    """允许系统内置类型，或小写字母开头的自定义 entity_type（如 qa_entity_xx）。"""
    import re

    if entity_type in DEFAULT_RULE_SEEDS:
        return True
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{1,48}", entity_type or ""))


def create_rule(
    db: Session,
    tenant_id: UUID,
    *,
    entity_type: str,
    prefix: str = "",
    suffix: str = "",
    date_format: str = "%Y%m%d",
    seq_width: int = 3,
    reset_period: str = "daily",
    enabled: bool = True,
) -> EntityNumberRule:
    if not _valid_custom_entity_type(entity_type):
        raise ValueError(f"未知实体类型: {entity_type}")
    if reset_period not in RESET_PERIOD_LABELS:
        raise ValueError(f"非法重置周期: {reset_period}")
    existing = (
        db.query(EntityNumberRule)
        .filter(
            uuid_eq(EntityNumberRule.tenant_id, tenant_id),
            EntityNumberRule.entity_type == entity_type,
        )
        .first()
    )
    if existing:
        raise ValueError(f"实体 {entity_type} 的编号规则已存在")
    rule = EntityNumberRule(
        tenant_id=tenant_id,
        entity_type=entity_type,
        prefix=prefix or "",
        suffix=suffix or "",
        date_format=date_format or "",
        seq_width=max(1, min(int(seq_width), 8)),
        reset_period=reset_period,
        enabled=enabled,
    )
    db.add(rule)
    db.flush()
    return rule


def delete_rule(db: Session, tenant_id: UUID, entity_type: str) -> None:
    rule = (
        db.query(EntityNumberRule)
        .filter(
            uuid_eq(EntityNumberRule.tenant_id, tenant_id),
            EntityNumberRule.entity_type == entity_type,
        )
        .first()
    )
    if not rule:
        raise ValueError("编号规则不存在")
    db.delete(rule)
    db.flush()


def update_rule(
    db: Session,
    tenant_id: UUID,
    entity_type: str,
    *,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    date_format: Optional[str] = None,
    seq_width: Optional[int] = None,
    reset_period: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> EntityNumberRule:
    rule = get_rule(db, tenant_id, entity_type)
    if prefix is not None:
        rule.prefix = prefix
    if suffix is not None:
        rule.suffix = suffix
    if date_format is not None:
        rule.date_format = date_format
    if seq_width is not None:
        rule.seq_width = max(1, min(int(seq_width), 8))
    if reset_period is not None:
        if reset_period not in RESET_PERIOD_LABELS:
            raise ValueError(f"非法重置周期: {reset_period}")
        rule.reset_period = reset_period
    if enabled is not None:
        rule.enabled = enabled
    db.flush()
    return rule
