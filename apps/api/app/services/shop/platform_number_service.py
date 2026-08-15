"""平台业务编码（P04-E / P08-F）。对照 04-数据模型 #platform-code-rule。

与 CRM number_service 同构；平台单例（无 tenant_id）。
shop_category 支持 inherit_parent_code + parent_id 作用域。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import User
from app.models.shop import (
    ShopMerchantAccount,
    ShopMerchantSubscription,
    ShopOnboardingApplication,
    ShopPlanFeature,
    ShopPlatformCategory,
    ShopPlatformNumberCounter,
    ShopPlatformNumberRule,
    ShopSubscriptionPlan,
)

RESET_PERIOD_LABELS: dict[str, str] = {
    "once": "永不重置",
    "daily": "每日",
    "weekly": "每周",
    "monthly": "每月",
    "yearly": "每年",
}

ENTITY_LABELS: dict[str, str] = {
    "shop_merchant": "商家",
    "shop_onboarding": "入驻申请",
    "renewal_application": "续费申请",
    "service_log": "服务记录",
    "shop_category": "平台类目",
    "shop_plan": "套餐模板",
    "shop_plan_feature": "功能字典",
    "shop_subscription": "开通/订阅单",
    "settlement_batch": "结算批次",
    "shop_store": "店铺",
    "moderation_case": "违规工单",
}

DEFAULT_RULE_SEEDS: dict[str, dict] = {
    "shop_merchant": {
        "prefix": "SH",
        "date_format": "%Y%m%d",
        "seq_width": 4,
        "reset_period": "once",
        "inherit_parent_code": False,
    },
    "shop_onboarding": {
        "prefix": "OB",
        "date_format": "%Y%m%d",
        "seq_width": 4,
        "reset_period": "daily",
        "inherit_parent_code": False,
    },
    "renewal_application": {
        "prefix": "RF",
        "date_format": "%Y%m%d",
        "seq_width": 4,
        "reset_period": "daily",
        "inherit_parent_code": False,
    },
    "service_log": {
        "prefix": "SV",
        "date_format": "%Y%m%d",
        "seq_width": 4,
        "reset_period": "daily",
        "inherit_parent_code": False,
    },
    "shop_category": {
        "prefix": "cat.",
        "date_format": "",
        "seq_width": 3,
        "reset_period": "once",
        "inherit_parent_code": True,
    },
    "shop_plan": {
        "prefix": "PL",
        "date_format": "",
        "seq_width": 3,
        "reset_period": "once",
        "inherit_parent_code": False,
    },
    "shop_plan_feature": {
        "prefix": "PF",
        "date_format": "",
        "seq_width": 3,
        "reset_period": "once",
        "inherit_parent_code": False,
    },
    "shop_subscription": {
        "prefix": "DY",
        "date_format": "%Y%m%d",
        "seq_width": 4,
        "reset_period": "daily",
        "inherit_parent_code": False,
    },
    "settlement_batch": {
        "prefix": "JS",
        "date_format": "%G%V",
        "seq_width": 4,
        "reset_period": "weekly",
        "inherit_parent_code": False,
    },
    "shop_store": {
        "prefix": "DP",
        "date_format": "",
        "seq_width": 4,
        "reset_period": "once",
        "inherit_parent_code": False,
    },
    "moderation_case": {
        "prefix": "WG",
        "date_format": "%Y%m%d",
        "seq_width": 4,
        "reset_period": "daily",
        "inherit_parent_code": False,
    },
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


def _date_part(date_format: str, now: datetime) -> str:
    if not date_format:
        return ""
    try:
        return now.strftime(date_format)
    except Exception:
        return ""


def _effective_rule(
    rule: ShopPlatformNumberRule,
    *,
    prefix: str | None = None,
    date_format: str | None = None,
    seq_width: int | None = None,
    reset_period: str | None = None,
    suffix: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        prefix=rule.prefix if prefix is None else prefix,
        date_format=rule.date_format if date_format is None else date_format,
        seq_width=rule.seq_width if seq_width is None else seq_width,
        reset_period=rule.reset_period if reset_period is None else reset_period,
        suffix=rule.suffix if suffix is None else suffix,
        inherit_parent_code=rule.inherit_parent_code,
        separator=rule.separator,
        enabled=rule.enabled,
    )


def _preview_format(rule, *, seq: int = 1, effective_prefix: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    prefix = effective_prefix if effective_prefix is not None else (rule.prefix or "")
    date_part = _date_part(rule.date_format or "", now)
    seq_str = str(seq).zfill(int(rule.seq_width or 3))
    suffix = rule.suffix or ""
    return f"{prefix}{date_part}{seq_str}{suffix}"


def rule_to_dict(rule: ShopPlatformNumberRule, db: Session | None = None) -> dict:
    preview = _preview_format(rule)
    next_seq = 1
    if db is not None:
        nxt = preview_number(db, rule.entity_type)
        preview = nxt.get("code") or preview
        next_seq = int(nxt.get("next_seq") or 1)
    return {
        "id": rule.id,
        "entity_type": rule.entity_type,
        "entity_label": ENTITY_LABELS.get(rule.entity_type, rule.entity_type),
        "prefix": rule.prefix or "",
        "suffix": rule.suffix or "",
        "date_format": rule.date_format or "",
        "seq_width": int(rule.seq_width or 3),
        "reset_period": rule.reset_period or "once",
        "reset_period_label": RESET_PERIOD_LABELS.get(rule.reset_period or "once", rule.reset_period),
        "inherit_parent_code": bool(rule.inherit_parent_code),
        "separator": rule.separator or ".",
        "enabled": bool(rule.enabled),
        "preview": preview,
        "next_seq": next_seq,
        "updated_at": rule.updated_at,
    }


def ensure_seed_rules(db: Session) -> None:
    existing = {r.entity_type for r in db.query(ShopPlatformNumberRule).all()}
    dirty = False
    for entity_type, seed in DEFAULT_RULE_SEEDS.items():
        if entity_type in existing:
            continue
        db.add(
            ShopPlatformNumberRule(
                id=uuid.uuid4(),
                entity_type=entity_type,
                prefix=seed["prefix"],
                suffix="",
                date_format=seed["date_format"],
                seq_width=seed["seq_width"],
                reset_period=seed["reset_period"],
                inherit_parent_code=bool(seed.get("inherit_parent_code")),
                separator=".",
                enabled=True,
            )
        )
        dirty = True
    if dirty:
        db.commit()


def get_rule(db: Session, entity_type: str) -> ShopPlatformNumberRule:
    ensure_seed_rules(db)
    rule = (
        db.query(ShopPlatformNumberRule)
        .filter(ShopPlatformNumberRule.entity_type == entity_type)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail=f"未知实体类型: {entity_type}")
    return rule


def list_rules(db: Session) -> list[dict]:
    ensure_seed_rules(db)
    rows = db.query(ShopPlatformNumberRule).all()
    by_type = {r.entity_type: r for r in rows}
    ordered: list[dict] = []
    for et in DEFAULT_RULE_SEEDS:
        if et in by_type:
            ordered.append(rule_to_dict(by_type[et], db=db))
    return ordered


def update_rule(
    db: Session,
    user: User,
    entity_type: str,
    *,
    prefix: str | None = None,
    suffix: str | None = None,
    date_format: str | None = None,
    seq_width: int | None = None,
    reset_period: str | None = None,
    inherit_parent_code: bool | None = None,
    separator: str | None = None,
    enabled: bool | None = None,
) -> dict:
    if entity_type not in DEFAULT_RULE_SEEDS:
        raise HTTPException(status_code=404, detail=f"未知实体类型: {entity_type}")
    rule = get_rule(db, entity_type)
    values: dict = {"updated_by": user.id}
    if prefix is not None:
        values["prefix"] = prefix
    if suffix is not None:
        values["suffix"] = suffix or ""
    if date_format is not None:
        values["date_format"] = date_format or ""
    if seq_width is not None:
        values["seq_width"] = max(1, min(int(seq_width), 8))
    if reset_period is not None:
        if reset_period not in RESET_PERIOD_LABELS:
            raise HTTPException(status_code=422, detail=f"非法重置周期: {reset_period}")
        values["reset_period"] = reset_period
    if inherit_parent_code is not None:
        values["inherit_parent_code"] = bool(inherit_parent_code)
    if separator is not None:
        values["separator"] = separator or "."
    if enabled is not None:
        values["enabled"] = bool(enabled)
    # SQLite + UUID PK：按 entity_type 更新，避免 StaleDataError
    (
        db.query(ShopPlatformNumberRule)
        .filter(ShopPlatformNumberRule.entity_type == entity_type)
        .update(values, synchronize_session=False)
    )
    db.commit()
    db.expire_all()
    return rule_to_dict(get_rule(db, entity_type), db=db)


def reset_all_defaults(db: Session, user: User) -> list[dict]:
    ensure_seed_rules(db)
    for entity_type, seed in DEFAULT_RULE_SEEDS.items():
        (
            db.query(ShopPlatformNumberRule)
            .filter(ShopPlatformNumberRule.entity_type == entity_type)
            .update(
                {
                    "prefix": seed["prefix"],
                    "suffix": "",
                    "date_format": seed["date_format"],
                    "seq_width": seed["seq_width"],
                    "reset_period": seed["reset_period"],
                    "inherit_parent_code": bool(seed.get("inherit_parent_code")),
                    "separator": ".",
                    "enabled": True,
                    "updated_by": user.id,
                },
                synchronize_session=False,
            )
        )
    db.commit()
    db.expire_all()
    return list_rules(db)


def _resolve_category_prefix(
    db: Session, rule: ShopPlatformNumberRule, parent_id: UUID | None
) -> tuple[str, str]:
    """返回 (effective_prefix, scope_key)。"""
    sep = rule.separator or "."
    if rule.inherit_parent_code and parent_id:
        parent = (
            db.query(ShopPlatformCategory)
            .filter(uuid_eq(ShopPlatformCategory.id, parent_id))
            .first()
        )
        if not parent:
            raise HTTPException(status_code=422, detail="父类目不存在")
        return f"{parent.code}{sep}", parent.code
    return rule.prefix or "", "__root__"


def _code_taken(db: Session, entity_type: str, code: str) -> bool:
    if entity_type == "shop_category":
        return (
            db.query(ShopPlatformCategory.id).filter(ShopPlatformCategory.code == code).first()
            is not None
        )
    if entity_type == "shop_plan":
        return (
            db.query(ShopSubscriptionPlan.id).filter(ShopSubscriptionPlan.code == code).first()
            is not None
        )
    if entity_type == "shop_plan_feature":
        return db.query(ShopPlanFeature.id).filter(ShopPlanFeature.code == code).first() is not None
    if entity_type == "shop_onboarding":
        return (
            db.query(ShopOnboardingApplication.id)
            .filter(ShopOnboardingApplication.application_no == code)
            .first()
            is not None
        )
    if entity_type == "shop_merchant":
        return (
            db.query(ShopMerchantAccount.id)
            .filter(ShopMerchantAccount.merchant_no == code)
            .first()
            is not None
        )
    if entity_type == "shop_subscription":
        return (
            db.query(ShopMerchantSubscription.id)
            .filter(ShopMerchantSubscription.subscription_no == code)
            .first()
            is not None
        )
    return False


def _set_counter_seq(
    db: Session,
    *,
    entity_type: str,
    scope_key: str,
    period_key: str,
    seq: int,
) -> None:
    """SQLite UUID 主键 ORM 更新常 0 行，按业务键 update。"""
    db.query(ShopPlatformNumberCounter).filter(
        ShopPlatformNumberCounter.entity_type == entity_type,
        ShopPlatformNumberCounter.scope_key == scope_key,
        ShopPlatformNumberCounter.period_key == period_key,
    ).update({"seq": int(seq)}, synchronize_session=False)


def _skip_taken_seq(
    db: Session,
    entity_type: str,
    rule,
    *,
    effective_prefix: str,
    start_seq: int,
    scope_key: str | None = None,
    period_key: str | None = None,
) -> tuple[str, int]:
    seq = start_seq
    code = _preview_format(rule, seq=seq, effective_prefix=effective_prefix)
    if entity_type not in (
        "shop_category",
        "shop_plan",
        "shop_plan_feature",
        "shop_onboarding",
        "shop_merchant",
        "shop_subscription",
    ):
        return code, seq
    guard = 0
    while _code_taken(db, entity_type, code) and guard < 200:
        seq += 1
        if scope_key is not None and period_key is not None:
            _set_counter_seq(
                db,
                entity_type=entity_type,
                scope_key=scope_key,
                period_key=period_key,
                seq=seq,
            )
        code = _preview_format(rule, seq=seq, effective_prefix=effective_prefix)
        guard += 1
    return code, seq


def preview_number(
    db: Session,
    entity_type: str,
    *,
    parent_id: UUID | None = None,
    prefix: str | None = None,
    date_format: str | None = None,
    seq_width: int | None = None,
    reset_period: str | None = None,
    suffix: str | None = None,
) -> dict:
    """预览下一号（不占用序号）。可带未保存草稿栏位。"""
    stored = get_rule(db, entity_type)
    rule = _effective_rule(
        stored,
        prefix=prefix,
        date_format=date_format,
        seq_width=seq_width,
        reset_period=reset_period,
        suffix=suffix,
    )
    now = datetime.now(timezone.utc)
    period_key = _period_key(rule.reset_period or "once", now)
    if entity_type == "shop_category":
        effective_prefix, scope_key = _resolve_category_prefix(db, rule, parent_id)
    else:
        effective_prefix, scope_key = rule.prefix or "", period_key or "__global__"
    counter = (
        db.query(ShopPlatformNumberCounter)
        .filter(
            ShopPlatformNumberCounter.entity_type == entity_type,
            ShopPlatformNumberCounter.scope_key == scope_key,
            ShopPlatformNumberCounter.period_key == period_key,
        )
        .first()
    )
    next_seq = int(counter.seq) + 1 if counter else 1
    code, next_seq = _skip_taken_seq(
        db, entity_type, rule, effective_prefix=effective_prefix, start_seq=next_seq
    )
    return {
        "code": code,
        "code_source": "auto",
        "entity_type": entity_type,
        "enabled": bool(rule.enabled),
        "inherit_parent_code": bool(rule.inherit_parent_code),
        "next_seq": next_seq,
    }


def generate_platform_number(
    db: Session,
    entity_type: str,
    *,
    parent_id: UUID | None = None,
) -> str:
    """原子生成下一号；调用方须在事务中。规则关闭时抛 422。"""
    rule = get_rule(db, entity_type)
    if not rule.enabled:
        raise HTTPException(status_code=422, detail="编码规则已关闭，请手工填写 code")
    now = datetime.now(timezone.utc)
    period_key = _period_key(rule.reset_period, now)
    if entity_type == "shop_category":
        effective_prefix, scope_key = _resolve_category_prefix(db, rule, parent_id)
    else:
        effective_prefix, scope_key = rule.prefix or "", period_key or "__global__"

    counter = (
        db.query(ShopPlatformNumberCounter)
        .filter(
            ShopPlatformNumberCounter.entity_type == entity_type,
            ShopPlatformNumberCounter.scope_key == scope_key,
            ShopPlatformNumberCounter.period_key == period_key,
        )
        .first()
    )
    if counter is None:
        counter = ShopPlatformNumberCounter(
            id=uuid.uuid4(),
            entity_type=entity_type,
            scope_key=scope_key,
            period_key=period_key,
            seq=0,
        )
        db.add(counter)
        db.flush()
    seq = int(counter.seq or 0) + 1
    _set_counter_seq(
        db,
        entity_type=entity_type,
        scope_key=scope_key,
        period_key=period_key,
        seq=seq,
    )
    code, _ = _skip_taken_seq(
        db,
        entity_type,
        rule,
        effective_prefix=effective_prefix,
        start_seq=seq,
        scope_key=scope_key,
        period_key=period_key,
    )
    return code
