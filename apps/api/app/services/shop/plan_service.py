"""P10 功能字典与套餐模板。对照 PRD：06-平台端UI.html#p10 · 04#pl。"""

from __future__ import annotations

import re
import uuid
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import User
from app.models.shop import (
    ShopMerchantAccount,
    ShopMerchantSubscription,
    ShopPlanFeature,
    ShopSubscriptionPlan,
)
from app.schemas.shop_platform import (
    PlanFeatureCreate,
    PlanFeatureOut,
    PlanFeatureTreeNode,
    PlanFeatureUpdate,
    PlanTemplateCreate,
    PlanTemplateOut,
    PlanTemplateUpdate,
)
from app.services.shop import platform_number_service

NODE_TYPES = frozenset({"group", "leaf"})
CATEGORIES = frozenset({"quota", "usage", "feature"})
VALUE_TYPES = frozenset({"int", "usage", "bool", "unlimited"})
AGGREGATE_MODES = frozenset({"max", "sum", "any"})
USAGE_PERIODS = frozenset({"daily", "monthly", "subscription"})
PLAN_TYPES = frozenset({"main", "addon"})
BILLING_PERIODS = frozenset({"monthly", "yearly", "custom_days"})
ENTITY_TYPES = frozenset({"personal", "individual_business", "enterprise"})


def _user_names(db: Session, ids: set[UUID | None]) -> dict[UUID, str]:
    out: dict[UUID, str] = {}
    for uid in ids:
        if not uid:
            continue
        u = db.query(User).filter(uuid_eq(User.id, uid)).first()
        if not u:
            continue
        label = (u.display_name or u.phone or "").strip()
        if label:
            out[uid] = label
    return out


def _feature_index(db: Session) -> dict[UUID, ShopPlanFeature]:
    return {r.id: r for r in db.query(ShopPlanFeature).all()}


def _parent_path_for(row: ShopPlanFeature, idx: dict[UUID, ShopPlanFeature]) -> str | None:
    parts: list[str] = []
    pid = row.parent_id
    seen: set[UUID] = set()
    while pid and pid not in seen:
        seen.add(pid)
        parent = idx.get(pid)
        if not parent:
            break
        parts.append(parent.name)
        pid = parent.parent_id
    return " / ".join(reversed(parts)) if parts else None


def _infer_code_source(code: str | None, prefix: str) -> str:
    if code and re.match(rf"^{re.escape(prefix)}\d+$", code):
        return "auto"
    return "manual"


def _active_counts(db: Session, plan_ids: list[UUID]) -> dict[UUID, int]:
    if not plan_ids:
        return {}
    rows = (
        db.query(ShopMerchantSubscription.plan_id, func.count(ShopMerchantSubscription.id))
        .filter(
            ShopMerchantSubscription.plan_id.in_(plan_ids),
            ShopMerchantSubscription.status == "active",
        )
        .group_by(ShopMerchantSubscription.plan_id)
        .all()
    )
    return {pid: int(n) for pid, n in rows}


def _feature_out(
    db: Session,
    row: ShopPlanFeature,
    *,
    names: dict[UUID, str] | None = None,
    paths: dict[UUID, str | None] | None = None,
) -> PlanFeatureOut:
    names = names or _user_names(db, {row.created_by, row.updated_by})
    path = (paths or {}).get(row.id) if paths is not None else None
    if paths is None:
        path = _parent_path_for(row, _feature_index(db))
    return PlanFeatureOut(
        id=row.id,
        code=row.code,
        name=row.name,
        node_type=row.node_type,
        parent_id=row.parent_id,
        parent_path=path,
        sort_order=row.sort_order,
        category=row.category,
        value_type=row.value_type,
        aggregate_mode=row.aggregate_mode,
        usage_period=row.usage_period,
        meter_key=row.meter_key,
        unit=row.unit,
        description=row.description,
        is_active=row.is_active,
        created_by=row.created_by,
        created_by_name=names.get(row.created_by) if row.created_by else None,
        created_at=row.created_at,
        updated_by=row.updated_by,
        updated_by_name=names.get(row.updated_by) if row.updated_by else None,
        updated_at=row.updated_at,
    )


def _plan_out(
    db: Session,
    row: ShopSubscriptionPlan,
    *,
    names: dict[UUID, str] | None = None,
    counts: dict[UUID, int] | None = None,
) -> PlanTemplateOut:
    names = names or _user_names(db, {row.created_by, row.updated_by})
    if counts is None:
        counts = _active_counts(db, [row.id])
    return PlanTemplateOut(
        id=row.id,
        code=row.code,
        name=row.name,
        plan_type=row.plan_type,
        sort_order=row.sort_order,
        is_public=row.is_public,
        is_active=row.is_active,
        stackable=row.stackable,
        replace_group=row.replace_group,
        billing_period=row.billing_period,
        price_cents=row.price_cents,
        quotas=row.quotas or {},
        features=row.features or {},
        usage_limits=row.usage_limits or {},
        allowed_entity_types=list(row.allowed_entity_types or []),
        description=row.description,
        code_source=_infer_code_source(row.code, "PL"),
        active_subscription_count=counts.get(row.id, 0),
        created_by=row.created_by,
        created_by_name=names.get(row.created_by) if row.created_by else None,
        created_at=row.created_at,
        updated_by=row.updated_by,
        updated_by_name=names.get(row.updated_by) if row.updated_by else None,
        updated_at=row.updated_at,
    )


def _validate_leaf_rules(
    *,
    category: str | None,
    value_type: str | None,
    aggregate_mode: str | None,
    usage_period: str | None,
    meter_key: str | None,
) -> None:
    if category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="业务分类无效")
    if value_type not in VALUE_TYPES:
        raise HTTPException(status_code=422, detail="数值类型无效")
    if value_type == "bool":
        aggregate_mode = aggregate_mode or "any"
        if aggregate_mode != "any":
            raise HTTPException(status_code=422, detail="开关类型合并方式须为 any")
    elif aggregate_mode not in AGGREGATE_MODES:
        raise HTTPException(status_code=422, detail="合并方式无效")
    if value_type == "usage":
        if usage_period not in USAGE_PERIODS:
            raise HTTPException(status_code=422, detail="用量类型须填写统计周期")
        if not (meter_key or "").strip():
            raise HTTPException(status_code=422, detail="用量类型须填写埋点标识")
    if value_type == "unlimited" and category != "quota":
        raise HTTPException(status_code=422, detail="unlimited 仅可用于配额类")


def preview_feature_code(db: Session) -> dict:
    """P10-A/F 自动编码预览。对照 #p10a · #p10f。"""
    return platform_number_service.preview_number(db, "shop_plan_feature")


def preview_plan_code(db: Session) -> dict:
    """P10-H/I 自动编码预览。对照 #p10h · #p10i。"""
    return platform_number_service.preview_number(db, "shop_plan")


def list_features(
    db: Session,
    *,
    q: str | None = None,
    node_type: str | None = None,
    is_active: bool | None = None,
    parent_id: UUID | None = None,
    tree: bool = False,
) -> list[PlanFeatureOut] | list[PlanFeatureTreeNode]:
    query = db.query(ShopPlanFeature)
    if node_type:
        if node_type not in NODE_TYPES:
            raise HTTPException(status_code=422, detail="node_type 无效")
        query = query.filter(ShopPlanFeature.node_type == node_type)
    if is_active is not None:
        query = query.filter(ShopPlanFeature.is_active.is_(is_active))
    if parent_id is not None:
        query = query.filter(uuid_eq(ShopPlanFeature.parent_id, parent_id))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(ShopPlanFeature.name.ilike(like), ShopPlanFeature.code.ilike(like)))
    rows = query.order_by(ShopPlanFeature.sort_order.asc(), ShopPlanFeature.name.asc()).all()
    names = _user_names(db, {r.created_by for r in rows} | {r.updated_by for r in rows})
    idx = _feature_index(db)
    paths = {r.id: _parent_path_for(r, idx) for r in rows}
    if not tree:
        return [_feature_out(db, r, names=names, paths=paths) for r in rows]

    by_parent: dict[UUID | None, list[ShopPlanFeature]] = {}
    for r in rows:
        by_parent.setdefault(r.parent_id, []).append(r)

    def build(parent: UUID | None) -> list[PlanFeatureTreeNode]:
        nodes: list[PlanFeatureTreeNode] = []
        for r in by_parent.get(parent, []):
            item = _feature_out(db, r, names=names, paths=paths)
            children = build(r.id) if r.node_type == "group" else []
            nodes.append(PlanFeatureTreeNode(**item.model_dump(), children=children))
        return nodes

    # 若筛了 leaf，仍按扁平返回树根下无父的项；完整树从根构建
    if node_type == "leaf":
        return [
            PlanFeatureTreeNode(**_feature_out(db, r, names=names, paths=paths).model_dump(), children=[])
            for r in rows
        ]
    return build(None)


def get_feature(db: Session, feature_id: UUID) -> PlanFeatureOut:
    row = db.query(ShopPlanFeature).filter(uuid_eq(ShopPlanFeature.id, feature_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="功能项不存在")
    return _feature_out(db, row)


def create_feature(db: Session, payload: PlanFeatureCreate, user: User) -> PlanFeatureOut:
    if payload.node_type not in NODE_TYPES:
        raise HTTPException(status_code=422, detail="node_type 无效")
    code = (payload.code or "").strip()
    if not code:
        code = platform_number_service.generate_platform_number(db, "shop_plan_feature")
    if db.query(ShopPlanFeature).filter(ShopPlanFeature.code == code).first():
        raise HTTPException(status_code=422, detail="code 已存在")

    parent_id = payload.parent_id
    category = payload.category
    value_type = payload.value_type
    aggregate_mode = payload.aggregate_mode
    usage_period = payload.usage_period
    meter_key = payload.meter_key

    if payload.node_type == "group":
        if parent_id is not None:
            parent = db.query(ShopPlanFeature).filter(uuid_eq(ShopPlanFeature.id, parent_id)).first()
            if not parent or parent.node_type != "group":
                raise HTTPException(status_code=422, detail="上级须为功能分组")
        # 同层名称唯一
        dup_q = db.query(ShopPlanFeature).filter(
            ShopPlanFeature.node_type == "group",
            ShopPlanFeature.name == payload.name.strip(),
        )
        if parent_id is None:
            dup_q = dup_q.filter(ShopPlanFeature.parent_id.is_(None))
        else:
            dup_q = dup_q.filter(uuid_eq(ShopPlanFeature.parent_id, parent_id))
        if dup_q.first():
            raise HTTPException(status_code=422, detail="分组名已存在")
        category = value_type = aggregate_mode = usage_period = meter_key = None
    else:
        if parent_id is None:
            raise HTTPException(status_code=422, detail="请选择所属分组")
        parent = db.query(ShopPlanFeature).filter(uuid_eq(ShopPlanFeature.id, parent_id)).first()
        if not parent or parent.node_type != "group":
            raise HTTPException(status_code=422, detail="请选择所属分组")
        _validate_leaf_rules(
            category=category,
            value_type=value_type,
            aggregate_mode=aggregate_mode,
            usage_period=usage_period,
            meter_key=meter_key,
        )
        if value_type == "bool":
            aggregate_mode = "any"

    row = ShopPlanFeature(
        id=uuid.uuid4(),
        code=code,
        name=payload.name.strip(),
        node_type=payload.node_type,
        parent_id=parent_id,
        sort_order=payload.sort_order if payload.sort_order is not None else 0,
        category=category,
        value_type=value_type,
        aggregate_mode=aggregate_mode,
        usage_period=usage_period,
        meter_key=(meter_key or None),
        unit=payload.unit,
        description=payload.description,
        is_active=True,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _feature_out(db, row)


def _plans_referencing_code(db: Session, code: str) -> list[ShopSubscriptionPlan]:
    plans = db.query(ShopSubscriptionPlan).all()
    hit: list[ShopSubscriptionPlan] = []
    for p in plans:
        bags = (p.quotas or {}, p.features or {}, p.usage_limits or {})
        if any(code in bag for bag in bags):
            hit.append(p)
    return hit


def update_feature(db: Session, feature_id: UUID, payload: PlanFeatureUpdate, user: User) -> PlanFeatureOut:
    row = db.query(ShopPlanFeature).filter(uuid_eq(ShopPlanFeature.id, feature_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="功能项不存在")
    if not row.is_active and payload.sync_to_templates:
        raise HTTPException(status_code=422, detail="停用项请先启用再同步模板")

    if payload.name is not None:
        name = payload.name.strip()
        if row.node_type == "group":
            dup_q = db.query(ShopPlanFeature).filter(
                ShopPlanFeature.node_type == "group",
                ShopPlanFeature.name == name,
                ShopPlanFeature.id != row.id,
            )
            parent_id = payload.parent_id if payload.parent_id is not None else row.parent_id
            if parent_id is None:
                dup_q = dup_q.filter(ShopPlanFeature.parent_id.is_(None))
            else:
                dup_q = dup_q.filter(uuid_eq(ShopPlanFeature.parent_id, parent_id))
            if dup_q.first():
                raise HTTPException(status_code=422, detail="分组名已存在")
        row.name = name

    if payload.parent_id is not None:
        if payload.parent_id == row.id:
            raise HTTPException(status_code=422, detail="不能将自身设为上级")
        parent = db.query(ShopPlanFeature).filter(uuid_eq(ShopPlanFeature.id, payload.parent_id)).first()
        if not parent or parent.node_type != "group":
            raise HTTPException(status_code=422, detail="上级须为功能分组")
        row.parent_id = payload.parent_id

    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    if payload.unit is not None:
        row.unit = payload.unit
    if payload.description is not None:
        row.description = payload.description

    if row.node_type == "leaf":
        # category / value_type 不可改（PRD）
        aggregate_mode = payload.aggregate_mode if payload.aggregate_mode is not None else row.aggregate_mode
        usage_period = payload.usage_period if payload.usage_period is not None else row.usage_period
        meter_key = payload.meter_key if payload.meter_key is not None else row.meter_key
        _validate_leaf_rules(
            category=row.category,
            value_type=row.value_type,
            aggregate_mode=aggregate_mode,
            usage_period=usage_period,
            meter_key=meter_key,
        )
        if row.value_type == "bool":
            aggregate_mode = "any"
        row.aggregate_mode = aggregate_mode
        if payload.usage_period is not None:
            row.usage_period = usage_period
        if payload.meter_key is not None:
            row.meter_key = meter_key

    if payload.sync_to_templates:
        refs = _plans_referencing_code(db, row.code)
        for plan in refs:
            # 规则字段不落在模板 JSON 内；若统一数值则改模板值
            if payload.uniform_limit_value is not None and row.value_type in ("int", "usage"):
                for bag_name in ("quotas", "usage_limits"):
                    bag = getattr(plan, bag_name) or {}
                    if row.code in bag:
                        bag = dict(bag)
                        bag[row.code] = payload.uniform_limit_value
                        setattr(plan, bag_name, bag)
            if row.value_type == "bool" and payload.uniform_limit_value is not None:
                feats = dict(plan.features or {})
                if row.code in feats:
                    feats[row.code] = True
                    plan.features = feats
            plan.updated_by = user.id

    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _feature_out(db, row)


def deactivate_feature(
    db: Session,
    feature_id: UUID,
    user: User,
    *,
    remove_from_templates: bool = False,
) -> PlanFeatureOut:
    row = db.query(ShopPlanFeature).filter(uuid_eq(ShopPlanFeature.id, feature_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="功能项不存在")
    if not row.is_active:
        return _feature_out(db, row)
    if row.node_type == "group":
        children = (
            db.query(ShopPlanFeature)
            .filter(uuid_eq(ShopPlanFeature.parent_id, row.id), ShopPlanFeature.is_active.is_(True))
            .count()
        )
        if children:
            raise HTTPException(status_code=422, detail="存在启用中的子功能时不可停用分组")

    row.is_active = False
    row.updated_by = user.id
    if remove_from_templates and row.node_type == "leaf":
        for plan in _plans_referencing_code(db, row.code):
            for bag_name in ("quotas", "features", "usage_limits"):
                bag = dict(getattr(plan, bag_name) or {})
                if row.code in bag:
                    bag.pop(row.code, None)
                    setattr(plan, bag_name, bag)
            plan.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _feature_out(db, row)


def activate_feature(db: Session, feature_id: UUID, user: User) -> PlanFeatureOut:
    row = db.query(ShopPlanFeature).filter(uuid_eq(ShopPlanFeature.id, feature_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="功能项不存在")
    row.is_active = True
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _feature_out(db, row)


def _normalize_entity_types(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        x = v.strip()
        if x == "individual":
            x = "individual_business"
        if x not in ENTITY_TYPES:
            raise HTTPException(status_code=422, detail=f"适用主体无效: {v}")
        if x not in out:
            out.append(x)
    if not out:
        raise HTTPException(status_code=422, detail="请至少选择一种适用主体")
    return out


def _split_feature_values(db: Session, feature_values: dict[str, Any]) -> tuple[dict, dict, dict]:
    if not feature_values:
        return {}, {}, {}
    codes = list(feature_values.keys())
    rows = db.query(ShopPlanFeature).filter(ShopPlanFeature.code.in_(codes)).all()
    by_code = {r.code: r for r in rows}
    quotas: dict[str, Any] = {}
    features: dict[str, Any] = {}
    usage_limits: dict[str, Any] = {}
    for code, val in feature_values.items():
        feat = by_code.get(code)
        if not feat or feat.node_type != "leaf":
            raise HTTPException(status_code=422, detail=f"功能未配置完整: {code}")
        if feat.category == "quota":
            quotas[code] = val
        elif feat.category == "usage":
            usage_limits[code] = val
        else:
            features[code] = val
    return quotas, features, usage_limits


def _validate_plan_bags(
    db: Session,
    *,
    quotas: dict,
    features: dict,
    usage_limits: dict,
    allow_inactive_codes: set[str] | None = None,
) -> None:
    allow_inactive_codes = allow_inactive_codes or set()
    bags = [("quotas", quotas), ("features", features), ("usage_limits", usage_limits)]
    total = sum(len(b or {}) for _, b in bags)
    if total < 1:
        raise HTTPException(status_code=422, detail="请至少配置一项能力")
    for bag_name, bag in bags:
        for code, val in (bag or {}).items():
            feat = db.query(ShopPlanFeature).filter(ShopPlanFeature.code == code).first()
            if not feat or feat.node_type != "leaf":
                raise HTTPException(status_code=422, detail=f"功能未配置完整: {code}")
            if not feat.is_active and code not in allow_inactive_codes:
                raise HTTPException(status_code=422, detail=f"功能已停用不可勾选: {code}")
            expected = {
                "quotas": "quota",
                "features": "feature",
                "usage_limits": "usage",
            }[bag_name]
            if feat.category != expected:
                raise HTTPException(status_code=422, detail=f"功能分类与写入区不符: {code}")
            if feat.value_type == "bool" and not isinstance(val, bool):
                raise HTTPException(status_code=422, detail=f"开关值须为布尔: {code}")
            if feat.value_type in ("int", "usage") and val != "unlimited" and not isinstance(val, int):
                raise HTTPException(status_code=422, detail=f"数值须为整数或不限量: {code}")


def _apply_plan_type_defaults(
    plan_type: str,
    *,
    stackable: bool | None,
    replace_group: str | None,
) -> tuple[bool, str | None]:
    if plan_type == "main":
        if stackable is True:
            raise HTTPException(status_code=422, detail="主套餐不可叠加（非法叠加）")
        return False, (replace_group or "main")
    if stackable is False:
        raise HTTPException(status_code=422, detail="加购包须可叠加")
    if replace_group:
        raise HTTPException(status_code=422, detail="加购包不可设置互斥组")
    return True, None


def _resolve_plan_bags(
    db: Session,
    payload: PlanTemplateCreate | PlanTemplateUpdate,
    existing: ShopSubscriptionPlan | None = None,
) -> tuple[dict, dict, dict]:
    if payload.feature_values is not None:
        return _split_feature_values(db, payload.feature_values)
    quotas = payload.quotas if payload.quotas is not None else (existing.quotas if existing else {})
    features = payload.features if payload.features is not None else (existing.features if existing else {})
    usage_limits = (
        payload.usage_limits
        if payload.usage_limits is not None
        else (existing.usage_limits if existing else {})
    )
    return dict(quotas or {}), dict(features or {}), dict(usage_limits or {})


def list_plan_templates(
    db: Session,
    *,
    q: str | None = None,
    plan_type: str | None = None,
    published: bool | None = None,
    is_active: bool | None = True,
    stackable: bool | None = None,
    replace_group: str | None = None,
    upgrade_from: str | None = None,
    tenant_id: UUID | None = None,
    purchase_mode: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[PlanTemplateOut], int]:
    query = db.query(ShopSubscriptionPlan)
    if is_active is not None:
        query = query.filter(ShopSubscriptionPlan.is_active.is_(is_active))
    if published is not None:
        query = query.filter(ShopSubscriptionPlan.is_public.is_(published))
    if plan_type:
        if plan_type not in PLAN_TYPES:
            raise HTTPException(status_code=422, detail="plan_type 无效")
        query = query.filter(ShopSubscriptionPlan.plan_type == plan_type)
    if stackable is not None:
        query = query.filter(ShopSubscriptionPlan.stackable.is_(stackable))
    if replace_group:
        query = query.filter(ShopSubscriptionPlan.replace_group == replace_group)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(ShopSubscriptionPlan.name.ilike(like), ShopSubscriptionPlan.code.ilike(like))
        )

    entity_type: str | None = None
    if tenant_id is not None:
        merchant = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
            .first()
        )
        if merchant:
            entity_type = merchant.entity_type

    rows = query.order_by(
        ShopSubscriptionPlan.plan_type.asc(),
        ShopSubscriptionPlan.sort_order.asc(),
        ShopSubscriptionPlan.name.asc(),
    ).all()

    if upgrade_from:
        base = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == upgrade_from).first()
        if not base:
            raise HTTPException(status_code=422, detail="upgrade_from 套餐不存在")
        rows = [
            r
            for r in rows
            if r.plan_type == "main"
            and r.replace_group == base.replace_group
            and r.sort_order > base.sort_order
        ]

    if purchase_mode == "stack":
        rows = [r for r in rows if r.stackable and r.plan_type == "addon"]
    elif purchase_mode == "replace":
        rows = [r for r in rows if r.plan_type == "main"]

    if entity_type:
        rows = [r for r in rows if entity_type in (r.allowed_entity_types or [])]

    total = len(rows)
    start = max(page - 1, 0) * page_size
    page_rows = rows[start : start + page_size]
    names = _user_names(
        db, {r.created_by for r in page_rows} | {r.updated_by for r in page_rows}
    )
    counts = _active_counts(db, [r.id for r in page_rows])
    return [_plan_out(db, r, names=names, counts=counts) for r in page_rows], total


def get_plan_template(db: Session, code: str) -> PlanTemplateOut:
    row = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == code).first()
    if not row:
        raise HTTPException(status_code=404, detail="套餐模板不存在")
    return _plan_out(db, row)


def create_plan_template(db: Session, payload: PlanTemplateCreate, user: User) -> PlanTemplateOut:
    if payload.plan_type not in PLAN_TYPES:
        raise HTTPException(status_code=422, detail="plan_type 无效")
    if payload.billing_period not in BILLING_PERIODS:
        raise HTTPException(status_code=422, detail="计费周期无效")
    if payload.price_cents < 0:
        raise HTTPException(status_code=422, detail="标价不可为负")

    code = (payload.code or "").strip()
    if not code:
        code = platform_number_service.generate_platform_number(db, "shop_plan")
    if db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == code).first():
        raise HTTPException(status_code=422, detail="code 已存在")
    name = payload.name.strip()
    if db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.name == name).first():
        raise HTTPException(status_code=422, detail="套餐名称已存在")

    stackable, replace_group = _apply_plan_type_defaults(
        payload.plan_type, stackable=payload.stackable, replace_group=payload.replace_group
    )
    quotas, features, usage_limits = _resolve_plan_bags(db, payload, None)
    _validate_plan_bags(db, quotas=quotas, features=features, usage_limits=usage_limits)
    allowed = _normalize_entity_types(payload.allowed_entity_types)

    sort_order = payload.sort_order
    if sort_order is None:
        scope_q = db.query(ShopSubscriptionPlan)
        if payload.plan_type == "main":
            scope_q = scope_q.filter(ShopSubscriptionPlan.replace_group == replace_group)
        else:
            scope_q = scope_q.filter(ShopSubscriptionPlan.plan_type == "addon")
        max_sort = max((p.sort_order for p in scope_q.all()), default=0)
        sort_order = max_sort + 10 if max_sort else 10

    is_public = bool(payload.publish_after_save or payload.is_public)
    if is_public and not (quotas or features or usage_limits):
        raise HTTPException(status_code=422, detail="功能未配置完整")

    row = ShopSubscriptionPlan(
        id=uuid.uuid4(),
        code=code,
        name=name,
        plan_type=payload.plan_type,
        sort_order=sort_order,
        is_public=is_public,
        is_active=True,
        stackable=stackable,
        replace_group=replace_group,
        billing_period=payload.billing_period,
        price_cents=payload.price_cents,
        quotas=quotas,
        features=features,
        usage_limits=usage_limits,
        allowed_entity_types=allowed,
        description=payload.description,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_out(db, row)


def update_plan_template(db: Session, code: str, payload: PlanTemplateUpdate, user: User) -> PlanTemplateOut:
    row = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == code).first()
    if not row:
        raise HTTPException(status_code=404, detail="套餐模板不存在")

    if payload.name is not None:
        name = payload.name.strip()
        dup = (
            db.query(ShopSubscriptionPlan)
            .filter(ShopSubscriptionPlan.name == name, ShopSubscriptionPlan.id != row.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=422, detail="套餐名称已存在")
        row.name = name

    plan_type = row.plan_type
    stackable = row.stackable
    replace_group = row.replace_group
    if payload.stackable is not None or payload.replace_group is not None:
        stackable, replace_group = _apply_plan_type_defaults(
            plan_type,
            stackable=payload.stackable if payload.stackable is not None else row.stackable,
            replace_group=payload.replace_group if payload.replace_group is not None else row.replace_group,
        )
        row.stackable = stackable
        row.replace_group = replace_group

    if payload.billing_period is not None:
        if payload.billing_period not in BILLING_PERIODS:
            raise HTTPException(status_code=422, detail="计费周期无效")
        row.billing_period = payload.billing_period
    if payload.price_cents is not None:
        if payload.price_cents < 0:
            raise HTTPException(status_code=422, detail="标价不可为负")
        row.price_cents = payload.price_cents
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    if payload.description is not None:
        row.description = payload.description
    if payload.allowed_entity_types is not None:
        row.allowed_entity_types = _normalize_entity_types(payload.allowed_entity_types)

    if (
        payload.feature_values is not None
        or payload.quotas is not None
        or payload.features is not None
        or payload.usage_limits is not None
    ):
        existing_codes = set(row.quotas or {}) | set(row.features or {}) | set(row.usage_limits or {})
        inactive = {
            f.code
            for f in db.query(ShopPlanFeature)
            .filter(ShopPlanFeature.code.in_(list(existing_codes)), ShopPlanFeature.is_active.is_(False))
            .all()
        }
        quotas, features, usage_limits = _resolve_plan_bags(db, payload, row)
        _validate_plan_bags(
            db,
            quotas=quotas,
            features=features,
            usage_limits=usage_limits,
            allow_inactive_codes=inactive,
        )
        row.quotas = quotas
        row.features = features
        row.usage_limits = usage_limits

    if payload.is_public is not None:
        if payload.is_public:
            _validate_plan_bags(
                db,
                quotas=row.quotas or {},
                features=row.features or {},
                usage_limits=row.usage_limits or {},
                allow_inactive_codes=set(row.quotas or {})
                | set(row.features or {})
                | set(row.usage_limits or {}),
            )
        row.is_public = payload.is_public
    if payload.publish_after_save:
        _validate_plan_bags(
            db,
            quotas=row.quotas or {},
            features=row.features or {},
            usage_limits=row.usage_limits or {},
            allow_inactive_codes=set(row.quotas or {})
            | set(row.features or {})
            | set(row.usage_limits or {}),
        )
        row.is_public = True

    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _plan_out(db, row)


def publish_plan_template(db: Session, code: str, user: User) -> PlanTemplateOut:
    return update_plan_template(
        db, code, PlanTemplateUpdate(is_public=True), user
    )


def unpublish_plan_template(db: Session, code: str, user: User) -> PlanTemplateOut:
    row = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == code).first()
    if not row:
        raise HTTPException(status_code=404, detail="套餐模板不存在")
    row.is_public = False
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _plan_out(db, row)


def assert_plan_selectable_for_subscribe(db: Session, plan: ShopSubscriptionPlan) -> None:
    """P11 开通前校验：禁用/未上架模板不可新开。"""
    if not plan.is_active:
        raise HTTPException(status_code=422, detail="套餐模板已禁用，不可新开")
    if not plan.is_public:
        raise HTTPException(status_code=422, detail="套餐未上架，不可新开")
