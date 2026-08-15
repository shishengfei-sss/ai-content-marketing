"""P11 订阅开通 / 换档 / 续费 / 取消。对照 PRD：§8.3 · 06#p11 · 03#f8。"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import User
from app.models.shop import ShopMerchantAccount, ShopMerchantServiceLog, ShopMerchantSubscription, ShopSubscriptionPlan
from app.schemas.shop_platform import (
    SubscriptionCancelRequest,
    SubscriptionCreateRequest,
    SubscriptionOut,
    SubscriptionRenewRequest,
    SubscriptionReplaceRequest,
)
from app.services.shop.a18_service import build_p02b_usage_payload
from app.services.shop.entitlement_service import (
    build_plan_snapshot,
    date_to_effective_at,
    date_to_expires_at_exclusive,
    exclusive_to_inclusive_date,
    get_merged_entitlements,
    list_active_subscriptions,
    now_sh,
    preview_merged_entitlements,
    refresh_merchant_plan_fields,
)
from app.services.shop.merchant_service import assert_can_read_merchant_tenant, resolve_merchant_list_scope
from app.services.shop.plan_service import assert_plan_selectable_for_subscribe
from app.services.shop.platform_number_service import generate_platform_number

SOURCES = frozenset({"manual", "trial", "renew", "upgrade", "purchase", "addon"})
PURCHASE_MODES = frozenset({"stack", "replace"})
STATUS_LABEL = {
    "active": "生效中",
    "expired": "已到期",
    "cancelled": "已取消",
    "superseded": "已换档",
    "pending": "待生效",
}


def _next_subscription_no(db: Session) -> str:
    return generate_platform_number(db, "shop_subscription")


def insert_subscription_row(
    db: Session,
    *,
    merchant: ShopMerchantAccount,
    plan: ShopSubscriptionPlan,
    user: User,
    effective: date,
    expires: date,
    source: str = "manual",
    purchase_mode: str = "stack",
    paid_amount_cents: int = 0,
    remark: str | None = None,
    commit: bool = False,
) -> ShopMerchantSubscription:
    """写入一条生效订阅并刷新商家冗余字段。默认不 commit，供入驻通过同事务调用。"""
    if source not in SOURCES:
        raise HTTPException(status_code=422, detail="来源无效")
    if purchase_mode not in PURCHASE_MODES:
        raise HTTPException(status_code=422, detail="开通方式无效")
    if effective > expires:
        raise HTTPException(status_code=422, detail="生效区间不合法")
    snap = build_plan_snapshot(plan)
    row = ShopMerchantSubscription(
        id=uuid4(),
        subscription_no=_next_subscription_no(db),
        tenant_id=merchant.tenant_id,
        plan_id=plan.id,
        status="active",
        effective_at=date_to_effective_at(effective),
        expires_at=date_to_expires_at_exclusive(expires),
        purchase_mode=purchase_mode,
        source=source,
        plan_snapshot=snap,
        catalog_price_cents=int(plan.price_cents or 0),
        paid_amount_cents=int(paid_amount_cents or 0),
        operator_id=user.id,
        remark=remark,
    )
    db.add(row)
    db.flush()
    refresh_merchant_plan_fields(db, merchant)
    from app.services.shop.audit_log_service import SUBSCRIPTION_AUDIT, record_merchant_audit

    action, src = SUBSCRIPTION_AUDIT.get(source, ("订阅开通", "订阅台账"))
    snap_name = (snap or {}).get("plan_name") or (snap or {}).get("plan_code") or plan.name
    until = expires.isoformat() if expires else ""
    summary = " · ".join(p for p in (snap_name, row.subscription_no, f"至 {until}" if until else "") if p)
    record_merchant_audit(
        db,
        tenant_id=merchant.tenant_id,
        merchant_id=merchant.id,
        action=action,
        summary=summary,
        source=src,
        operator=user,
    )
    if commit:
        db.commit()
        db.refresh(row)
    return row


def _get_merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    if not m:
        raise HTTPException(status_code=404, detail="商家不存在")
    return m


def _assert_merchant_active(merchant: ShopMerchantAccount) -> None:
    if merchant.status == "closed":
        raise HTTPException(status_code=422, detail="商家已清退，不可开通套餐")
    if merchant.status != "active":
        raise HTTPException(status_code=422, detail="商家已暂停，请先恢复")


def _validate_money(catalog: int, paid: int, remark: str | None) -> None:
    if paid < 0 or catalog < 0:
        raise HTTPException(status_code=422, detail="金额不能为负")
    if catalog > 0 and paid > catalog * 2:
        raise HTTPException(status_code=422, detail="金额异常，请核对")
    if (paid == 0 or (catalog > 0 and paid != catalog)) and not (remark or "").strip():
        raise HTTPException(status_code=422, detail="0 元/议价须填写原因")


def _default_expires(plan: ShopSubscriptionPlan, effective: date) -> date:
    if plan.billing_period == "monthly":
        return effective + timedelta(days=30) - timedelta(days=1)
    try:
        return date(effective.year + 1, effective.month, effective.day) - timedelta(days=1)
    except ValueError:
        return date(effective.year + 1, 2, 28)


def subscription_to_out(db: Session, row: ShopMerchantSubscription) -> SubscriptionOut:
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, row.tenant_id)).first()
    )
    from app.services.shop.entitlement_service import TZ_SH

    snap = row.plan_snapshot or {}
    plan_type = snap.get("plan_type")
    eff = row.effective_at.astimezone(TZ_SH).date() if row.effective_at.tzinfo else row.effective_at.date()
    expires_inc = exclusive_to_inclusive_date(row.expires_at)
    today = now_sh().date()
    display = row.status
    if row.status == "active" and expires_inc <= today + timedelta(days=30):
        display = "expiring_soon"
    op_name = None
    if row.operator_id:
        op = db.query(User).filter(uuid_eq(User.id, row.operator_id)).first()
        if op:
            op_name = op.display_name or op.phone
        elif row.source in ("trial", "purchase"):
            op_name = "系统"
        else:
            op_name = "运营"
    return SubscriptionOut(
        id=row.id,
        subscription_no=row.subscription_no,
        tenant_id=row.tenant_id,
        merchant_display_name=(merchant.display_name or merchant.legal_name) if merchant else None,
        plan_id=row.plan_id,
        plan_code=snap.get("plan_code"),
        plan_name=snap.get("plan_name"),
        plan_type=plan_type,
        status=row.status,
        purchase_mode=row.purchase_mode,
        source=row.source,
        effective_at=eff,
        expires_at_inclusive=expires_inc,
        paid_at=row.paid_at,
        catalog_price_cents=row.catalog_price_cents,
        paid_amount_cents=row.paid_amount_cents,
        previous_subscription_id=row.previous_subscription_id,
        plan_snapshot=snap,
        operator_id=row.operator_id,
        operator_name=op_name,
        remark=row.remark,
        created_at=row.created_at,
        updated_at=row.updated_at,
        status_label=STATUS_LABEL.get(row.status, row.status),
        display_status=display,
        plan_type_label="叠加" if plan_type == "addon" else "主套餐",
        has_pending_renewal=bool(merchant.has_pending_renewal) if merchant else False,
        billing_period=snap.get("billing_period"),
    )


def _complete_renewal(
    db: Session,
    merchant: ShopMerchantAccount,
    renewal_request_id: UUID,
    new_sub: ShopMerchantSubscription,
) -> None:
    log = (
        db.query(ShopMerchantServiceLog)
        .filter(
            uuid_eq(ShopMerchantServiceLog.id, renewal_request_id),
            uuid_eq(ShopMerchantServiceLog.merchant_id, merchant.id),
            ShopMerchantServiceLog.type == "renewal_request",
        )
        .first()
    )
    if not log:
        raise HTTPException(status_code=422, detail="续费申请不存在")
    if log.status not in ("pending", "processing"):
        raise HTTPException(status_code=422, detail="续费申请已取消")
    log.status = "completed"
    log.related_subscription_id = new_sub.id
    merchant.has_pending_renewal = False


def create_subscription(
    db: Session,
    user: User,
    payload: SubscriptionCreateRequest,
) -> SubscriptionOut:
    merchant = _get_merchant(db, payload.tenant_id)
    _assert_merchant_active(merchant)

    plan = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == payload.plan_code).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐模板不存在")
    assert_plan_selectable_for_subscribe(db, plan)
    if merchant.entity_type not in (plan.allowed_entity_types or []):
        raise HTTPException(status_code=422, detail="主体不可购此套餐")

    purchase_mode = payload.purchase_mode
    if purchase_mode not in PURCHASE_MODES:
        raise HTTPException(status_code=422, detail="开通方式无效")

    # 主套餐不可 stack 若已有同组 active
    active = list_active_subscriptions(db, merchant.tenant_id)
    if plan.plan_type == "main" and purchase_mode == "stack":
        for s in active:
            if (s.plan_snapshot or {}).get("replace_group") == plan.replace_group and (
                s.plan_snapshot or {}
            ).get("plan_type") == "main":
                raise HTTPException(status_code=422, detail="主套餐不可 stack，请换档")
    if plan.plan_type == "main" and purchase_mode == "replace":
        pass
    if plan.plan_type == "addon" and purchase_mode != "stack":
        raise HTTPException(status_code=422, detail="加购包须使用叠加开通")

    catalog = (
        payload.catalog_price_cents if payload.catalog_price_cents is not None else int(plan.price_cents or 0)
    )
    paid = payload.paid_amount_cents
    _validate_money(catalog, paid, payload.remark)

    effective = payload.effective_at or now_sh().date()
    expires = payload.expires_at or _default_expires(plan, effective)
    if effective > expires:
        raise HTTPException(status_code=422, detail="生效区间不合法")

    source = payload.source or "manual"
    if source not in SOURCES:
        raise HTTPException(status_code=422, detail="来源无效")

    prev_id = None
    if purchase_mode == "replace":
        for s in active:
            if (s.plan_snapshot or {}).get("replace_group") == plan.replace_group and (
                s.plan_snapshot or {}
            ).get("plan_type") == "main":
                s.status = "superseded"
                prev_id = s.id

    snap = build_plan_snapshot(plan)
    if payload.plan_label:
        snap["plan_name"] = payload.plan_label

    row = ShopMerchantSubscription(
        id=uuid4(),
        subscription_no=_next_subscription_no(db),
        tenant_id=merchant.tenant_id,
        plan_id=plan.id,
        status="active",
        effective_at=date_to_effective_at(effective),
        expires_at=date_to_expires_at_exclusive(expires),
        purchase_mode=purchase_mode,
        source=source,
        previous_subscription_id=prev_id,
        plan_snapshot=snap,
        catalog_price_cents=catalog,
        paid_amount_cents=paid,
        operator_id=user.id,
        remark=payload.remark,
    )
    db.add(row)
    db.flush()

    if payload.renewal_request_id:
        _complete_renewal(db, merchant, payload.renewal_request_id, row)

    refresh_merchant_plan_fields(db, merchant)
    # 服务日志：开通留痕
    db.add(
        ShopMerchantServiceLog(
            merchant_id=merchant.id,
            tenant_id=merchant.tenant_id,
            type="subscription",
            status="logged",
            content=f"开通套餐 {snap.get('plan_name')}（{row.subscription_no}）",
            payload_json={
                "subscription_id": str(row.id),
                "plan_code": plan.code,
                "purchase_mode": purchase_mode,
                "paid_amount_cents": paid,
            },
            operator_user_id=user.id,
            related_subscription_id=row.id,
        )
    )
    db.commit()
    db.refresh(row)
    return subscription_to_out(db, row)


def replace_subscription(
    db: Session,
    user: User,
    subscription_id: UUID,
    payload: SubscriptionReplaceRequest,
) -> SubscriptionOut:
    old = db.query(ShopMerchantSubscription).filter(uuid_eq(ShopMerchantSubscription.id, subscription_id)).first()
    if not old:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return create_subscription(
        db,
        user,
        SubscriptionCreateRequest(
            tenant_id=old.tenant_id,
            plan_code=payload.target_plan_code,
            purchase_mode="replace",
            effective_at=payload.effective_at,
            expires_at=payload.expires_at,
            catalog_price_cents=payload.catalog_price_cents,
            paid_amount_cents=payload.paid_amount_cents,
            source="upgrade",
            remark=payload.remark,
        ),
    )


def renew_subscription(
    db: Session,
    user: User,
    subscription_id: UUID,
    payload: SubscriptionRenewRequest,
) -> SubscriptionOut:
    old = db.query(ShopMerchantSubscription).filter(uuid_eq(ShopMerchantSubscription.id, subscription_id)).first()
    if not old:
        raise HTTPException(status_code=404, detail="订阅不存在")
    plan_code = (old.plan_snapshot or {}).get("plan_code")
    if not plan_code:
        raise HTTPException(status_code=422, detail="原订阅缺少套餐编码")

    # 续费衔接：默认生效 = 旧止日 + 1
    old_end = exclusive_to_inclusive_date(old.expires_at)
    effective = payload.effective_at or (old_end + timedelta(days=1))
    plan = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == plan_code).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐模板不存在")
    expires = payload.expires_at or _default_expires(plan, effective)

    # 同档续费：对已到期主套餐用 stack/replace 新开；若仍 active 则 replace 同组
    mode = "replace" if plan.plan_type == "main" else "stack"
    return create_subscription(
        db,
        user,
        SubscriptionCreateRequest(
            tenant_id=old.tenant_id,
            plan_code=plan_code,
            purchase_mode=mode,
            effective_at=effective,
            expires_at=expires,
            catalog_price_cents=payload.catalog_price_cents,
            paid_amount_cents=payload.paid_amount_cents,
            source="renew",
            remark=payload.remark,
            renewal_request_id=payload.renewal_request_id,
        ),
    )


def cancel_subscription(
    db: Session,
    user: User,
    subscription_id: UUID,
    payload: SubscriptionCancelRequest | None = None,
) -> SubscriptionOut:
    row = db.query(ShopMerchantSubscription).filter(uuid_eq(ShopMerchantSubscription.id, subscription_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if row.status != "active":
        raise HTTPException(status_code=422, detail="仅生效中订阅可取消")
    if (row.plan_snapshot or {}).get("plan_type") != "addon":
        raise HTTPException(status_code=422, detail="仅加购包可取消")
    row.status = "cancelled"
    if payload and payload.remark:
        row.remark = ((row.remark or "") + "\n" + payload.remark).strip()
    row.operator_id = user.id
    merchant = _get_merchant(db, row.tenant_id)
    refresh_merchant_plan_fields(db, merchant)
    db.commit()
    db.refresh(row)
    return subscription_to_out(db, row)


def get_subscription(db: Session, user: User, subscription_id: UUID) -> SubscriptionOut:
    row = db.query(ShopMerchantSubscription).filter(uuid_eq(ShopMerchantSubscription.id, subscription_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="订阅不存在")
    assert_can_read_merchant_tenant(db, user, row.tenant_id)
    return subscription_to_out(db, row)


def list_subscriptions(
    db: Session,
    user: User,
    *,
    tenant_id: UUID | None = None,
    status_filter: str | None = None,
    plan_code: str | None = None,
    q: str | None = None,
    view: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str | None = None,
    sort_dir: str = "desc",
) -> tuple[list[SubscriptionOut], int]:
    scope = resolve_merchant_list_scope(user)
    query = db.query(ShopMerchantSubscription)
    if tenant_id:
        assert_can_read_merchant_tenant(db, user, tenant_id)
        query = query.filter(uuid_eq(ShopMerchantSubscription.tenant_id, tenant_id))
    elif scope == "assigned":
        merchants = (
            db.query(ShopMerchantAccount.tenant_id)
            .filter(uuid_eq(ShopMerchantAccount.account_manager_user_id, user.id))
            .all()
        )
        tids = [t[0] for t in merchants]
        if not tids:
            return [], 0
        query = query.filter(ShopMerchantSubscription.tenant_id.in_(tids))
    if status_filter:
        query = query.filter(ShopMerchantSubscription.status == status_filter)
    rows = query.order_by(ShopMerchantSubscription.created_at.desc()).all()
    if plan_code:
        rows = [r for r in rows if (r.plan_snapshot or {}).get("plan_code") == plan_code]
    items = [subscription_to_out(db, r) for r in rows]
    needle = (q or "").strip()
    if needle:
        items = [
            it
            for it in items
            if needle in (it.subscription_no or "")
            or needle in (it.merchant_display_name or "")
            or needle in (it.plan_name or "")
        ]
    if view in ("renewal", "todo"):
        items = [it for it in items if it.has_pending_renewal]
    reverse = sort_dir != "asc"
    key = sort_by or "created_at"
    attr_map = {
        "subscription_no": lambda x: x.subscription_no or "",
        "merchant": lambda x: x.merchant_display_name or "",
        "effective_at": lambda x: str(x.effective_at or ""),
        "expires_at": lambda x: str(x.expires_at_inclusive or ""),
        "created_at": lambda x: str(x.created_at or ""),
    }
    getter = attr_map.get(key, attr_map["created_at"])
    items.sort(key=getter, reverse=reverse)
    total = len(items)
    start = (page - 1) * page_size
    return items[start : start + page_size], total


def export_list_csv(
    db: Session,
    user: User,
    *,
    tenant_id: UUID | None = None,
    status_filter: str | None = None,
    plan_code: str | None = None,
    q: str | None = None,
    view: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    import csv
    import io

    items, total = list_subscriptions(
        db,
        user,
        tenant_id=tenant_id,
        status_filter=status_filter,
        plan_code=plan_code,
        q=q,
        view=view,
        page=1,
        page_size=5000,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    if raise_too_many and int(total or 0) > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = ["开通单号", "商家", "套餐", "订阅类型", "生效起", "生效止", "开通时间", "开通人", "状态"]
    col_map = {
        "subscription_no": ["开通单号"],
        "merchant_name": ["商家"],
        "plan_name": ["套餐"],
        "plan_type": ["订阅类型"],
        "effective_at": ["生效起"],
        "expires_at": ["生效止"],
        "created_at": ["开通时间"],
        "operator_name": ["开通人"],
        "status": ["状态"],
        "tenant_id": ["租户编号"],
        "snapshot_ver": ["套餐快照版本"],
    }
    if columns:
        headers: list[str] = []
        seen: set[str] = set()
        for key in columns:
            for h in col_map.get(key, []):
                if h not in seen:
                    seen.add(h)
                    headers.append(h)
        headers = headers or default_headers
    else:
        headers = default_headers
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for it in items:
        snap = it.plan_snapshot if isinstance(getattr(it, "plan_snapshot", None), dict) else {}
        values = {
            "开通单号": it.subscription_no or "",
            "商家": it.merchant_display_name or "",
            "套餐": it.plan_name or "",
            "订阅类型": it.plan_type_label or "",
            "生效起": it.effective_at.isoformat() if it.effective_at else "",
            "生效止": it.expires_at_inclusive.isoformat() if it.expires_at_inclusive else "",
            "开通时间": it.created_at.isoformat() if it.created_at else "",
            "开通人": it.operator_name or "",
            "状态": it.status_label or it.status or "",
            "租户编号": str(it.tenant_id) if it.tenant_id else "",
            "套餐快照版本": str(snap.get("version") or snap.get("plan_code") or ""),
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_subscription_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import SubscriptionExportRequest
    from app.services.shop import export_task_service

    body = body or SubscriptionExportRequest()
    filters = {
        "tenant_id": str(body.tenant_id) if body.tenant_id else None,
        "status": body.status,
        "plan_code": body.plan_code,
        "q": body.q,
        "view": body.view,
        "sort_by": body.sort_by,
        "sort_dir": body.sort_dir,
        "columns": body.columns,
    }
    csv_text = export_list_csv(
        db,
        user,
        tenant_id=body.tenant_id,
        status_filter=body.status,
        plan_code=body.plan_code,
        q=body.q,
        view=body.view,
        sort_by=body.sort_by,
        sort_dir=body.sort_dir or "desc",
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_for_user(
        db,
        user,
        resource="subscriptions",
        file_name="shop-subscriptions.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_subscription_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "subscriptions")


def read_subscription_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "subscriptions")


def merchant_subscriptions_with_entitlements(db: Session, user: User, tenant_id: UUID) -> dict:
    assert_can_read_merchant_tenant(db, user, tenant_id)
    items, _ = list_subscriptions(db, user, tenant_id=tenant_id, page=1, page_size=100)
    merged = get_merged_entitlements(db, tenant_id)
    usage = build_p02b_usage_payload(db, tenant_id, merged)
    return {
        "items": items,
        "entitlements": {**merged, **usage},
    }


def merchant_entitlements(
    db: Session,
    user: User,
    tenant_id: UUID,
    *,
    preview_plan: str | None = None,
    preview_mode: str | None = None,
) -> dict:
    assert_can_read_merchant_tenant(db, user, tenant_id)
    if preview_plan:
        return preview_merged_entitlements(db, tenant_id, preview_plan, preview_mode)
    return get_merged_entitlements(db, tenant_id)
