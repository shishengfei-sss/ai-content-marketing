"""M7：公域映射闸 · 抖店 Webhook · 领权。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    ShopBuyer,
    ShopChannelAuditLog,
    ShopChannelMapping,
    ShopChannelSetting,
    ShopClaimToken,
    ShopEntitlement,
    ShopMerchantAccount,
    ShopOrder,
    ShopProduct,
    ShopSmsLog,
    ShopStore,
    ShopWebhookEvent,
)
from app.config import settings
from app.schemas.shop_platform import (
    ChannelAuditLogOut,
    ChannelMappingCreateRequest,
    ChannelMappingExportRequest,
    ChannelMappingOut,
    ChannelPreviewSyncOut,
    ChannelPreviewSyncRequest,
    ChannelSettingOut,
    ChannelSettingSaveRequest,
    ClaimConfirmResponse,
    ClaimInfoOut,
    DouyinOrderWebhookRequest,
    DouyinRefundWebhookRequest,
    ShopExportTaskOut,
)
from app.services.shop.order_service import _activate_entitlement_for_order, _gen_order_no, _now
from app.services.shop.buyer_service import is_claim_stub_openid


COMBO_CHANNEL = {"1A": "douyin", "1B": "douyin", "2A": "course_lib", "2B": "course_lib"}


def _channel_mock_audit_enabled() -> bool:
    return str(getattr(settings, "SHOP_CHANNEL_MOCK_AUDIT", "1")).lower() in (
        "1",
        "true",
        "yes",
    )


def stub_douyin_sign(payload: dict, secret: str) -> str:
    raw = "|".join(
        [
            str(payload.get("event_id") or ""),
            str(payload.get("external_order_no") or ""),
            str(payload.get("channel_product_id") or ""),
            str(payload.get("paid_amount_cents") or ""),
            secret,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now_utc() -> datetime:
    # SQLite 常把 DateTime(timezone=True) 读成 naive；统一用 naive UTC 比较
    return datetime.utcnow()


def _as_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _audit(
    db: Session,
    *,
    tenant_id: UUID,
    channel: str,
    event: str,
    shop_id: UUID | None = None,
    product_id: UUID | None = None,
    detail: dict | None = None,
) -> None:
    db.add(
        ShopChannelAuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            shop_id=shop_id,
            product_id=product_id,
            channel=channel,
            event=event,
            detail_json=detail or {},
        )
    )


_CHANNEL_LABEL = {"douyin": "抖店", "course_lib": "课程库"}
_STATUS_LABEL = {
    "mapped": "已挂载",
    "unmapped": "未挂载",
    "pending": "未挂载",  # 提审中 UI 仍归「未挂载」Tab 时可另筛
    "syncing": "同步中",
    "blocked": "已阻断",
    "paused": "暂停同步",
}
_AUDIT_LABEL = {
    "submitted": "审核中",
    "approved": "已通过",
    "rejected": "被拒",
}


def _mapping_out(m: ShopChannelMapping, product: ShopProduct | None = None) -> ChannelMappingOut:
    review = None
    if product:
        if product.status == "on_sale":
            review = "已通过"
        elif product.status == "pending_review":
            review = "审核中"
        elif product.status == "rejected":
            review = "已驳回"
        else:
            review = product.status
    audit = m.external_audit_status
    if not audit:
        if m.status in ("mapped", "paused"):
            audit = "approved"
        elif m.status == "blocked":
            audit = "rejected"
        elif m.status == "pending":
            audit = "submitted"
    combo = (getattr(m, "combo", None) or "").strip().upper()
    if not combo:
        combo = "2A" if m.channel == "course_lib" else "1A"
    return ChannelMappingOut(
        id=m.id,
        tenant_id=m.tenant_id,
        shop_id=m.shop_id,
        product_id=m.product_id,
        product_name=product.name if product else None,
        product_review_status=review,
        channel=m.channel,
        channel_label=_CHANNEL_LABEL.get(m.channel, m.channel),
        channel_product_id=m.channel_product_id,
        channel_product_url=m.channel_product_url,
        path_label=_path_label(combo),
        status=m.status,
        status_label=_STATUS_LABEL.get(m.status, m.status),
        external_audit_status=audit,
        external_audit_label=_AUDIT_LABEL.get(audit or "", audit or "—"),
        mount_blocked_code=m.mount_blocked_code,
        mount_blocked_reason=m.mount_blocked_reason,
        blocked_at=m.blocked_at,
        synced_at=m.synced_at,
        created_at=m.created_at,
    )


def get_or_create_settings(db: Session, tenant_id: UUID) -> ShopChannelSetting:
    row = (
        db.query(ShopChannelSetting)
        .filter(uuid_eq(ShopChannelSetting.tenant_id, tenant_id))
        .first()
    )
    if row:
        return row
    row = ShopChannelSetting(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        enabled_combos=["1A"],
        douyin_configured=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def settings_out(db: Session, tenant_id: UUID) -> ChannelSettingOut:
    s = get_or_create_settings(db, tenant_id)
    deal = (s.deal_link or "1").strip() or "1"
    path = (s.path_mode or "A").strip().upper() or "A"
    bind = s.bind_status or ("available" if s.douyin_shop_id else "unbound")
    verified = bool(s.webhook_verified)
    if verified:
        state, state_label = "verified", "已验通"
    elif s.douyin_shop_id:
        state, state_label = "draft", "草稿中"
    else:
        state, state_label = "draft", "未配置"
    combo_label = f"链路{'①' if deal == '1' else '②'} · 路径{path}"
    return ChannelSettingOut(
        tenant_id=tenant_id,
        enabled_combos=list(s.enabled_combos or []),
        deal_link=deal,
        path_mode=path,
        bind_scope=s.bind_scope or "tenant",
        bind_status=bind,
        bind_status_label="可用" if bind == "available" else "未绑定",
        last_synced_at=s.last_synced_at,
        webhook_verified=verified,
        webhook_tested_at=s.webhook_tested_at,
        douyin_shop_id=s.douyin_shop_id,
        douyin_configured=bool(s.douyin_configured),
        webhook_url=f"/api/v1/webhooks/douyin/order?tenant_id={tenant_id}",
        has_webhook_secret=bool(s.douyin_webhook_secret),
        link2_available=False,
        path_b_available=False,
        config_state=state,
        config_state_label=state_label,
        combo_label=combo_label,
        demo_tools_enabled=_channel_mock_audit_enabled(),
    )


def _apply_combo(s: ShopChannelSetting, deal_link: str, path_mode: str) -> None:
    s.deal_link = deal_link
    s.path_mode = path_mode
    s.enabled_combos = [f"{deal_link}{path_mode}"]


def _require_phase1_combo(deal_link: str, path_mode: str) -> None:
    if deal_link == "2":
        raise HTTPException(status_code=422, detail="套餐未开通")
    if path_mode == "B":
        raise HTTPException(status_code=422, detail="路径 B 为本期未开通")
    if deal_link != "1" or path_mode != "A":
        raise HTTPException(status_code=422, detail="请选择成交链路与路径")


def save_settings(
    db: Session, ctx: TenantContext, body: ChannelSettingSaveRequest
) -> ChannelSettingOut:
    s = get_or_create_settings(db, ctx.tenant_id)
    deal = (body.deal_link or s.deal_link or "1").strip() or "1"
    path = (body.path_mode or s.path_mode or "A").strip().upper() or "A"
    if body.enabled_combos:
        first = str(body.enabled_combos[0] or "1A").upper()
        deal = first[0] if first else deal
        path = first[-1] if first else path
        s.enabled_combos = list(body.enabled_combos)
    _require_phase1_combo(deal, path)
    shop_id = s.douyin_shop_id
    if body.douyin_shop_id is not None:
        shop_id = body.douyin_shop_id.strip() or None
        s.douyin_shop_id = shop_id
    if not shop_id:
        raise HTTPException(status_code=422, detail="请先完成绑店")
    _apply_combo(s, deal, path)
    if body.bind_scope is not None:
        if body.bind_scope != "tenant":
            raise HTTPException(status_code=422, detail="按店绑定为本期未开通")
        s.bind_scope = "tenant"
    if body.douyin_webhook_secret is not None:
        s.douyin_webhook_secret = body.douyin_webhook_secret.strip() or None
    if shop_id:
        s.bind_status = "available"
        if not s.last_synced_at:
            s.last_synced_at = _now_utc()
    s.douyin_configured = bool(s.douyin_shop_id and s.douyin_webhook_secret)
    db.commit()
    return settings_out(db, ctx.tenant_id)


def bind_external_shop(
    db: Session, ctx: TenantContext, *, shop_id: str, secret: str | None, bind_scope: str | None
) -> ChannelSettingOut:
    text = (shop_id or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="请填写外部店铺 ID")
    if bind_scope and bind_scope != "tenant":
        raise HTTPException(status_code=422, detail="按店绑定为本期未开通")
    s = get_or_create_settings(db, ctx.tenant_id)
    s.douyin_shop_id = text
    s.bind_scope = "tenant"
    s.bind_status = "available"
    s.last_synced_at = _now_utc()
    if secret is not None and secret.strip():
        s.douyin_webhook_secret = secret.strip()
    s.douyin_configured = bool(s.douyin_shop_id and s.douyin_webhook_secret)
    db.commit()
    return settings_out(db, ctx.tenant_id)


def send_webhook_test(db: Session, ctx: TenantContext) -> ChannelSettingOut:
    s = get_or_create_settings(db, ctx.tenant_id)
    if not s.douyin_shop_id:
        raise HTTPException(status_code=422, detail="请先完成绑店")
    if not s.douyin_webhook_secret:
        raise HTTPException(status_code=422, detail="回调未配置")
    s.webhook_verified = True
    s.webhook_tested_at = _now_utc()
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        channel="douyin",
        event="webhook_test",
        detail={"summary": "发送测试回调", "result": "ok"},
    )
    db.commit()
    return settings_out(db, ctx.tenant_id)


def _assert_combo_enabled(settings: ShopChannelSetting, combo: str) -> None:
    combos = set(settings.enabled_combos or [])
    if combo not in combos:
        raise HTTPException(
            status_code=422,
            detail="channel_combo_not_enabled",
        )


def _path_label(combo: str) -> str:
    c = (combo or "1A").strip().upper()
    return c[-1] if c else "A"


def _assert_product_mappable(
    db: Session, ctx: TenantContext, product: ShopProduct, channel: str
) -> str | None:
    """返回 reason_code；None 表示可通过 F7。"""
    merchant = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, ctx.tenant_id))
        .first()
    )
    shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, product.shop_id)).first()
    if not merchant or merchant.status != "active":
        return "merchant_not_active"
    if not shop:
        return "shop_not_active"
    if shop.status not in ("active", "published", "open", "draft"):
        return "shop_not_active"
    if product.status != "on_sale":
        return "product_not_on_sale"
    if product.last_review_id is None:
        return "product_not_reviewed"
    active = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
            uuid_eq(ShopChannelMapping.product_id, product.id),
            ShopChannelMapping.channel == channel,
            ShopChannelMapping.status.in_(("mapped", "pending", "paused", "syncing")),
        )
        .first()
    )
    if active:
        return "product_already_mapped"
    return None


def preview_sync(
    db: Session, ctx: TenantContext, body: ChannelPreviewSyncRequest
) -> ChannelPreviewSyncOut:
    """A14-A 步2：Mock 同步抖店，预分配 external_product_id。"""
    settings = get_or_create_settings(db, ctx.tenant_id)
    _assert_combo_enabled(settings, body.combo)
    channel = COMBO_CHANNEL.get(body.combo, "douyin")
    if channel == "douyin" and not settings.douyin_configured:
        raise HTTPException(status_code=422, detail="请先完成抖店对接配置")
    if body.sync_mode != "create_new":
        raise HTTPException(status_code=422, detail="Phase1 仅支持在抖店创建新商品")

    product = (
        db.query(ShopProduct)
        .filter(
            uuid_eq(ShopProduct.id, body.product_id),
            uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    reason = _assert_product_mappable(db, ctx, product, channel)
    if reason:
        raise HTTPException(status_code=409, detail=reason)

    title = body.external_title.strip()
    if len(title) < 2 or len(title) > 60:
        raise HTTPException(status_code=422, detail="抖店展示标题须 2–60 字")

    channel_product_id = f"Dou{uuid.uuid4().hex[:10].upper()}"
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        shop_id=product.shop_id,
        product_id=product.id,
        channel=channel,
        event="sync_succeeded",
        detail={
            "channel_product_id": channel_product_id,
            "external_title": title,
            "external_category": body.external_category,
            "summary": f"预同步抖店成功 · {channel_product_id}",
            "preview": True,
        },
    )
    db.commit()
    return ChannelPreviewSyncOut(
        channel_product_id=channel_product_id,
        external_title=title,
        external_category=body.external_category.strip(),
        price_cents=int(product.price_cents or 0),
        product_name=product.name,
        cover_url=getattr(product, "cover_url", None),
        path_label=_path_label(body.combo),
        douyin_shop_id=settings.douyin_shop_id,
        sync_mode=body.sync_mode,
    )


def create_mapping(
    db: Session, ctx: TenantContext, body: ChannelMappingCreateRequest
) -> ChannelMappingOut:
    settings = get_or_create_settings(db, ctx.tenant_id)
    _assert_combo_enabled(settings, body.combo)
    channel = body.channel if body.channel in ("douyin", "course_lib") else COMBO_CHANNEL.get(body.combo, "douyin")
    if channel == "douyin" and not settings.douyin_configured:
        raise HTTPException(status_code=422, detail="请先完成抖店对接配置")

    product = (
        db.query(ShopProduct)
        .filter(
            uuid_eq(ShopProduct.id, body.product_id),
            uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    merchant = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, ctx.tenant_id))
        .first()
    )
    shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, product.shop_id)).first()
    reason_code = None
    if not merchant or merchant.status != "active":
        reason_code = "merchant_not_active"
    elif not shop:
        reason_code = "shop_not_active"
    elif shop.status not in ("active", "published", "open", "draft"):
        reason_code = "shop_not_active"
    elif product.status != "on_sale":
        reason_code = "product_not_on_sale"
    elif product.last_review_id is None:
        reason_code = "product_not_reviewed"
    if reason_code:
        _audit(
            db,
            tenant_id=ctx.tenant_id,
            shop_id=product.shop_id,
            product_id=product.id,
            channel=channel,
            event="auto_reject",
            detail={
                "reason_code": reason_code,
                "channel_product_id": body.channel_product_id,
                "combo": body.combo,
            },
        )
        db.commit()
        raise HTTPException(status_code=409, detail=reason_code)

    existing = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
            ShopChannelMapping.channel == channel,
            ShopChannelMapping.channel_product_id == body.channel_product_id.strip(),
        )
        .first()
    )
    if existing and existing.status in ("mapped", "pending", "paused", "syncing"):
        raise HTTPException(status_code=409, detail="channel_product_already_mapped")

    active_prod = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
            uuid_eq(ShopChannelMapping.product_id, product.id),
            ShopChannelMapping.channel == channel,
            ShopChannelMapping.status.in_(("mapped", "pending", "paused", "syncing")),
        )
        .first()
    )
    if active_prod and (not existing or active_prod.id != existing.id):
        raise HTTPException(status_code=409, detail="product_already_mapped")

    m = existing or ShopChannelMapping(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=product.shop_id,
        product_id=product.id,
        channel=channel,
        channel_product_id=body.channel_product_id.strip(),
    )
    m.shop_id = product.shop_id
    m.product_id = product.id
    m.channel_product_url = body.channel_product_url
    m.combo = (body.combo or "1A").strip().upper()
    submit_mode = (body.submit_mode or "mapped").strip().lower()
    if submit_mode == "audit":
        m.status = "pending"
        m.external_audit_status = "submitted"
        m.synced_at = _now_utc()
        summary = "创建映射 · 已提交外部审核"
    else:
        # 兼容旧调用：直接挂载
        m.status = "mapped"
        m.external_audit_status = "approved"
        m.synced_at = _now_utc()
        summary = "创建映射 · 外部审核通过"
    m.mount_blocked_code = None
    m.mount_blocked_reason = None
    m.blocked_at = None
    if not existing:
        db.add(m)
        db.flush()
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        shop_id=product.shop_id,
        product_id=product.id,
        channel=channel,
        event="map_attempt",
        detail={
            "mapping_id": str(m.id),
            "channel_product_id": m.channel_product_id,
            "status": m.status,
            "combo": body.combo,
            "path_label": _path_label(body.combo),
            "external_title": body.external_title,
            "external_category": body.external_category,
            "sync_mode": body.sync_mode,
            "summary": summary,
        },
    )
    db.commit()
    db.refresh(m)
    if submit_mode == "audit" and _channel_mock_audit_enabled():
        return apply_external_audit(db, ctx, m.id, result="approved")
    out = _mapping_out(m, product)
    # 列表路径展示：按 combo 末位
    out.path_label = _path_label(body.combo)
    return out


def _audit_predicate(value: str):
    col = ShopChannelMapping.external_audit_status
    st = ShopChannelMapping.status
    v = (value or "").strip().lower()
    if v == "approved":
        return or_(col == "approved", and_(col.is_(None), st.in_(("mapped", "paused"))))
    if v == "rejected":
        return or_(col == "rejected", and_(col.is_(None), st == "blocked"))
    if v == "submitted":
        return or_(col == "submitted", and_(col.is_(None), st.in_(("pending", "syncing"))))
    return col == v


def _path_predicate(path: str):
    p = (path or "").strip().upper()
    if p not in ("A", "B"):
        return None
    combo = ShopChannelMapping.combo
    if p == "A":
        return or_(combo.ilike("%A"), combo.is_(None))
    return combo.ilike("%B")


def _scoped_mappings(db: Session, ctx: TenantContext, shop_id: UUID | None):
    base = db.query(ShopChannelMapping).filter(uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id))
    if shop_id:
        base = base.filter(uuid_eq(ShopChannelMapping.shop_id, shop_id))
    return base


def _filter_mappings(
    db: Session,
    ctx: TenantContext,
    query,
    *,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    external_audit_status: str | None = None,
    path: str | None = None,
    mapped_from: datetime | None = None,
    mapped_to: datetime | None = None,
):
    if status:
        if status == "unmapped":
            query = query.filter(ShopChannelMapping.status.in_(("unmapped", "pending")))
        else:
            query = query.filter(ShopChannelMapping.status == status)
    if q:
        like = f"%{q.strip()}%"
        prod_q = db.query(ShopProduct).filter(
            uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
            ShopProduct.name.ilike(like),
        )
        if shop_id:
            prod_q = prod_q.filter(uuid_eq(ShopProduct.shop_id, shop_id))
        pids = [p.id for p in prod_q.all()]
        query = query.filter(
            (ShopChannelMapping.channel_product_id.ilike(like))
            | (ShopChannelMapping.product_id.in_(pids or [uuid.uuid4()]))
        )
    if external_audit_status:
        query = query.filter(_audit_predicate(external_audit_status))
    path_pred = _path_predicate(path or "")
    if path_pred is not None:
        query = query.filter(path_pred)
    if mapped_from is not None:
        query = query.filter(ShopChannelMapping.created_at >= mapped_from)
    if mapped_to is not None:
        query = query.filter(ShopChannelMapping.created_at <= mapped_to)
    return query


def list_mappings(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    external_audit_status: str | None = None,
    path: str | None = None,
    mapped_from: datetime | None = None,
    mapped_to: datetime | None = None,
) -> tuple[list[ChannelMappingOut], int, dict[str, int]]:
    base = _scoped_mappings(db, ctx, shop_id)
    counts = {
        "all": base.count(),
        "mapped": base.filter(ShopChannelMapping.status == "mapped").count(),
        "unmapped": base.filter(
            ShopChannelMapping.status.in_(("unmapped", "pending"))
        ).count(),
        "blocked": base.filter(ShopChannelMapping.status == "blocked").count(),
        "paused": base.filter(ShopChannelMapping.status == "paused").count(),
    }
    query = _filter_mappings(
        db,
        ctx,
        base,
        status=status,
        q=q,
        shop_id=shop_id,
        external_audit_status=external_audit_status,
        path=path,
        mapped_from=mapped_from,
        mapped_to=mapped_to,
    )
    total = query.count()
    rows = (
        query.order_by(ShopChannelMapping.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    products = {
        p.id: p
        for p in db.query(ShopProduct)
        .filter(ShopProduct.id.in_([r.product_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    return [_mapping_out(r, products.get(r.product_id)) for r in rows], total, counts


def export_mappings_csv(
    db: Session,
    ctx: TenantContext,
    *,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    external_audit_status: str | None = None,
    path: str | None = None,
    mapped_from: datetime | None = None,
    mapped_to: datetime | None = None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    import csv
    import io

    items, total, _counts = list_mappings(
        db,
        ctx,
        page=1,
        page_size=5000,
        status=status,
        q=q,
        shop_id=shop_id,
        external_audit_status=external_audit_status,
        path=path,
        mapped_from=mapped_from,
        mapped_to=mapped_to,
    )
    if raise_too_many and total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = [
        "本地商品",
        "商品审核",
        "外部商品 ID",
        "路径",
        "挂载状态",
        "外部审核",
        "映射时间",
        "最近同步时间",
        "渠道",
    ]
    col_map = {
        "product_name": ["本地商品"],
        "product_review_status": ["商品审核"],
        "channel_product_id": ["外部商品 ID"],
        "path_label": ["路径"],
        "status_label": ["挂载状态"],
        "external_audit_status": ["外部审核"],
        "created_at": ["映射时间"],
        "synced_at": ["最近同步时间"],
        "channel_label": ["渠道"],
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
        values = {
            "本地商品": it.product_name or "",
            "商品审核": it.product_review_status or "",
            "外部商品 ID": it.channel_product_id or "",
            "路径": it.path_label or "",
            "挂载状态": it.status_label or it.status or "",
            "外部审核": it.external_audit_label or it.external_audit_status or "",
            "映射时间": it.created_at.isoformat(sep=" ", timespec="minutes") if it.created_at else "",
            "最近同步时间": it.synced_at.isoformat(sep=" ", timespec="minutes") if it.synced_at else "",
            "渠道": it.channel_label or it.channel or "",
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_mapping_export_task(
    db: Session,
    ctx: TenantContext,
    body: ChannelMappingExportRequest | None = None,
    *,
    mapped_from: datetime | None = None,
    mapped_to: datetime | None = None,
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or ChannelMappingExportRequest()
    filters = {
        "status": body.status,
        "q": body.q,
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "external_audit_status": body.external_audit_status,
        "path": body.path,
        "mapped_from": str(mapped_from) if mapped_from else None,
        "mapped_to": str(mapped_to) if mapped_to else None,
        "columns": body.columns,
    }
    csv_text = export_mappings_csv(
        db,
        ctx,
        status=body.status,
        q=body.q,
        shop_id=body.shop_id,
        external_audit_status=body.external_audit_status,
        path=body.path,
        mapped_from=mapped_from,
        mapped_to=mapped_to,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="channel_mappings",
        file_name="shop-channel-mappings.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_mapping_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "channel_mappings")


def read_mapping_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "channel_mappings")


def _get_tenant_mapping(
    db: Session, ctx: TenantContext, mapping_id: UUID
) -> ShopChannelMapping:
    m = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.id, mapping_id),
            uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="映射不存在")
    return m


def pause_mapped_for_product(
    db: Session, ctx: TenantContext, product_id: UUID, *, summary: str
) -> int:
    """商品下架时：将该品所有 mapped 映射改为 paused。返回暂停条数。"""
    rows = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
            uuid_eq(ShopChannelMapping.product_id, product_id),
            ShopChannelMapping.status == "mapped",
        )
        .all()
    )
    for m in rows:
        m.status = "paused"
        _audit(
            db,
            tenant_id=ctx.tenant_id,
            shop_id=m.shop_id,
            product_id=m.product_id,
            channel=m.channel,
            event="listing_paused",
            detail={
                "mapping_id": str(m.id),
                "channel_product_id": m.channel_product_id,
                "operator_id": str(ctx.user.id),
                "summary": summary,
                "source": "product_off_sale",
            },
        )
    return len(rows)


def block_mapped_for_moderation(
    db: Session,
    product_id: UUID,
    *,
    operator_id: UUID,
    summary: str,
) -> int:
    """P07 强制下架：mapped/paused/pending/syncing → blocked（listing blocked）。不 commit。"""
    rows = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.product_id, product_id),
            ShopChannelMapping.status.in_(("mapped", "paused", "pending", "syncing")),
        )
        .all()
    )
    now = _now_utc()
    for m in rows:
        m.status = "blocked"
        m.mount_blocked_code = "moderation_force_off"
        m.mount_blocked_reason = (summary or "")[:500]
        m.blocked_at = now
        _audit(
            db,
            tenant_id=m.tenant_id,
            shop_id=m.shop_id,
            product_id=m.product_id,
            channel=m.channel,
            event="listing_blocked",
            detail={
                "mapping_id": str(m.id),
                "channel_product_id": m.channel_product_id,
                "operator_id": str(operator_id),
                "summary": summary,
                "source": "moderation_force_off",
            },
        )
    return len(rows)


def pause_mapping(db: Session, ctx: TenantContext, mapping_id: UUID) -> ChannelMappingOut:
    """A14：已挂载 → 暂停同步。"""
    m = _get_tenant_mapping(db, ctx, mapping_id)
    if m.status != "mapped":
        raise HTTPException(status_code=422, detail="仅已挂载可暂停")
    m.status = "paused"
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        shop_id=m.shop_id,
        product_id=m.product_id,
        channel=m.channel,
        event="listing_paused",
        detail={
            "mapping_id": str(m.id),
            "channel_product_id": m.channel_product_id,
            "operator_id": str(ctx.user.id),
            "summary": "商家暂停同步",
        },
    )
    db.commit()
    db.refresh(m)
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, m.product_id)).first()
    return _mapping_out(m, product)


def resume_mapping(db: Session, ctx: TenantContext, mapping_id: UUID) -> ChannelMappingOut:
    """A14：暂停同步 → 已挂载。"""
    m = _get_tenant_mapping(db, ctx, mapping_id)
    if m.status != "paused":
        raise HTTPException(status_code=422, detail="仅暂停同步可恢复")
    m.status = "mapped"
    m.synced_at = _now_utc()
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        shop_id=m.shop_id,
        product_id=m.product_id,
        channel=m.channel,
        event="listing_resumed",
        detail={
            "mapping_id": str(m.id),
            "channel_product_id": m.channel_product_id,
            "operator_id": str(ctx.user.id),
            "summary": "商家恢复同步",
        },
    )
    db.commit()
    db.refresh(m)
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, m.product_id)).first()
    return _mapping_out(m, product)


def apply_external_audit(
    db: Session,
    ctx: TenantContext,
    mapping_id: UUID,
    *,
    result: str,
    reject_code: str | None = None,
    reject_reason: str | None = None,
) -> ChannelMappingOut:
    """模拟/联调外部审核回调：approved → mapped；rejected → blocked。"""
    m = _get_tenant_mapping(db, ctx, mapping_id)
    result = (result or "").strip().lower()
    if result not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="result 须为 approved 或 rejected")
    if m.status not in ("pending", "mapped", "blocked", "syncing"):
        raise HTTPException(status_code=422, detail="当前挂载状态不可接收外部审核结果")

    if result == "approved":
        m.status = "mapped"
        m.external_audit_status = "approved"
        m.mount_blocked_code = None
        m.mount_blocked_reason = None
        m.blocked_at = None
        m.synced_at = _now_utc()
        _audit(
            db,
            tenant_id=ctx.tenant_id,
            shop_id=m.shop_id,
            product_id=m.product_id,
            channel=m.channel,
            event="external_audit_approved",
            detail={
                "mapping_id": str(m.id),
                "channel_product_id": m.channel_product_id,
                "summary": "外部审核通过 · mapped",
            },
        )
    else:
        code = (reject_code or "OTHER").strip()[:64]
        reason = (reject_reason or "外部审核未通过").strip()[:500]
        if len(reason) < 2:
            raise HTTPException(status_code=422, detail="请填写驳回原因")
        m.status = "blocked"
        m.external_audit_status = "rejected"
        m.mount_blocked_code = code
        m.mount_blocked_reason = reason
        m.blocked_at = _now_utc()
        _audit(
            db,
            tenant_id=ctx.tenant_id,
            shop_id=m.shop_id,
            product_id=m.product_id,
            channel=m.channel,
            event="external_audit_rejected",
            detail={
                "mapping_id": str(m.id),
                "channel_product_id": m.channel_product_id,
                "reject_code": code,
                "reject_reason": reason,
                "summary": f"外部审核被拒 · {code}",
            },
        )
        product_for_case = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, m.product_id)).first()
        from app.services.shop import p07_moderation_service as p07svc

        p07svc.ingest_from_external_audit(
            db,
            mapping=m,
            product=product_for_case,
            reject_code=code,
            reject_reason=reason,
        )
    db.commit()
    db.refresh(m)
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, m.product_id)).first()
    return _mapping_out(m, product)


def resubmit_mapping(
    db: Session,
    ctx: TenantContext,
    mapping_id: UUID,
    *,
    note: str | None = None,
) -> ChannelMappingOut:
    """A14-B：blocked+rejected → pending+submitted，沿用 external_product_id。"""
    m = _get_tenant_mapping(db, ctx, mapping_id)
    if m.status != "blocked" or (m.external_audit_status or "rejected") != "rejected":
        raise HTTPException(status_code=422, detail="仅已阻断且外部审核被拒可重新提交")

    product = (
        db.query(ShopProduct)
        .filter(
            uuid_eq(ShopProduct.id, m.product_id),
            uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not product or product.status != "on_sale" or product.last_review_id is None:
        raise HTTPException(status_code=422, detail="商品未过审")

    m.status = "pending"
    m.external_audit_status = "submitted"
    # 保留上次驳回文案供对照，直至新结果覆盖
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        shop_id=m.shop_id,
        product_id=m.product_id,
        channel=m.channel,
        event="external_audit_resubmitted",
        detail={
            "mapping_id": str(m.id),
            "channel_product_id": m.channel_product_id,
            "note": note,
            "operator_id": str(ctx.user.id),
            "summary": "修改并重新提交外部审核",
        },
    )
    db.commit()
    db.refresh(m)
    if _channel_mock_audit_enabled():
        return apply_external_audit(db, ctx, mapping_id, result="approved")
    return _mapping_out(m, product)


def resync_mapping(db: Session, ctx: TenantContext, mapping_id: UUID) -> ChannelMappingOut:
    """A14-C：重新同步（Mock 写日志）。"""
    m = _get_tenant_mapping(db, ctx, mapping_id)
    if m.status not in ("mapped", "paused"):
        raise HTTPException(status_code=422, detail="仅已挂载或暂停同步可重新同步")
    m.synced_at = _now_utc()
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        shop_id=m.shop_id,
        product_id=m.product_id,
        channel=m.channel,
        event="sync_succeeded",
        detail={
            "mapping_id": str(m.id),
            "channel_product_id": m.channel_product_id,
            "operator_id": str(ctx.user.id),
            "summary": f"同步抖店成功 · {m.channel_product_id}",
        },
    )
    db.commit()
    db.refresh(m)
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, m.product_id)).first()
    return _mapping_out(m, product)


def list_mapping_logs(
    db: Session,
    ctx: TenantContext,
    mapping_id: UUID,
    *,
    category: str | None = None,
    limit: int = 50,
) -> list[ChannelAuditLogOut]:
    """A14-C：按映射查公域日志。"""
    m = _get_tenant_mapping(db, ctx, mapping_id)
    rows = (
        db.query(ShopChannelAuditLog)
        .filter(
            uuid_eq(ShopChannelAuditLog.tenant_id, ctx.tenant_id),
            uuid_eq(ShopChannelAuditLog.product_id, m.product_id),
            ShopChannelAuditLog.channel == m.channel,
        )
        .order_by(ShopChannelAuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    mid = str(m.id)
    cpid = m.channel_product_id
    items: list[ChannelAuditLogOut] = []
    for r in rows:
        detail = r.detail_json or {}
        if detail.get("mapping_id") and detail.get("mapping_id") != mid:
            continue
        if detail.get("channel_product_id") and detail.get("channel_product_id") != cpid:
            continue
        cat = _event_category(r.event)
        if category and category != "all" and cat != category:
            continue
        items.append(
            ChannelAuditLogOut(
                id=r.id,
                tenant_id=r.tenant_id,
                shop_id=r.shop_id,
                product_id=r.product_id,
                channel=r.channel,
                event=r.event,
                detail_json=detail,
                created_at=r.created_at,
            )
        )
        if len(items) >= limit:
            break
    return items


def _event_category(event: str) -> str:
    if event in (
        "sync_started",
        "sync_succeeded",
        "sync_failed",
        "map_attempt",
        "resync",
    ):
        return "sync"
    if event.startswith("external_audit") or event in (
        "approved",
        "rejected",
        "external_audit_approved",
        "external_audit_rejected",
    ):
        return "external_audit"
    if event.startswith("webhook") or event == "auto_reject":
        return "webhook"
    if event in (
        "listing_paused",
        "listing_resumed",
        "unmount",
        "force_unmount",
        "mapping_created",
        "external_audit_resubmitted",
    ):
        return "status"
    return "status"


def delete_mapping(db: Session, ctx: TenantContext, mapping_id: UUID) -> dict:
    m = _get_tenant_mapping(db, ctx, mapping_id)
    m.status = "unmapped"
    _audit(
        db,
        tenant_id=ctx.tenant_id,
        shop_id=m.shop_id,
        product_id=m.product_id,
        channel=m.channel,
        event="unmount",
        detail={"mapping_id": str(m.id), "summary": "解除映射"},
    )
    db.commit()
    return {"id": str(m.id), "status": "unmapped"}


def force_unmount(db: Session, mapping_id: UUID) -> ChannelMappingOut:
    m = db.query(ShopChannelMapping).filter(uuid_eq(ShopChannelMapping.id, mapping_id)).first()
    if not m:
        raise HTTPException(status_code=404, detail="映射不存在")
    m.status = "unmapped"
    _audit(
        db,
        tenant_id=m.tenant_id,
        shop_id=m.shop_id,
        product_id=m.product_id,
        channel=m.channel,
        event="force_unmount",
        detail={"mapping_id": str(m.id)},
    )
    db.commit()
    db.refresh(m)
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, m.product_id)).first()
    return _mapping_out(m, product)


def list_audit_by_external(
    db: Session, *, external_order_id: str, tenant_id: UUID | None = None
) -> list[ChannelAuditLogOut]:
    q = db.query(ShopChannelAuditLog)
    if tenant_id:
        q = q.filter(uuid_eq(ShopChannelAuditLog.tenant_id, tenant_id))
    rows = q.order_by(ShopChannelAuditLog.created_at.desc()).limit(200).all()
    items = []
    for r in rows:
        detail = r.detail_json or {}
        if detail.get("external_order_id") == external_order_id or detail.get(
            "external_order_no"
        ) == external_order_id:
            items.append(
                ChannelAuditLogOut(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    shop_id=r.shop_id,
                    product_id=r.product_id,
                    channel=r.channel,
                    event=r.event,
                    detail_json=detail,
                    created_at=r.created_at,
                )
            )
    return items


def _resolve_tenant_for_webhook(
    db: Session, *, tenant_id: UUID | None, douyin_shop_id: str | None
) -> ShopChannelSetting:
    if tenant_id:
        return get_or_create_settings(db, tenant_id)
    if douyin_shop_id:
        s = (
            db.query(ShopChannelSetting)
            .filter(ShopChannelSetting.douyin_shop_id == douyin_shop_id)
            .first()
        )
        if s:
            return s
    raise HTTPException(status_code=404, detail="未找到抖店对接租户")


def _verify_sign(settings: ShopChannelSetting, payload: dict, sign: str | None) -> None:
    secret = settings.douyin_webhook_secret or ""
    if not secret:
        raise HTTPException(status_code=422, detail="未配置 webhook secret")
    expected = stub_douyin_sign(payload, secret)
    if not sign or not hmac.compare_digest(str(sign), expected):
        raise HTTPException(status_code=400, detail="签名无效")


def simulate_demo_douyin_order(
    db: Session,
    ctx: TenantContext,
    mapping_id: UUID,
    *,
    buyer_mobile: str | None = None,
) -> dict:
    """本地演示：模拟抖店付款 Webhook → 待领权订单 + 领权链接。"""
    if not _channel_mock_audit_enabled():
        raise HTTPException(status_code=403, detail="演示工具未开启（SHOP_CHANNEL_MOCK_AUDIT）")
    m = _get_tenant_mapping(db, ctx, mapping_id)
    if m.status == "pending":
        raise HTTPException(status_code=422, detail="外部审核未完成，请先点「通过审核」")
    if m.status != "mapped":
        raise HTTPException(status_code=422, detail="仅已挂载商品可模拟下单")
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, m.product_id)).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    ch_settings = get_or_create_settings(db, ctx.tenant_id)
    if not ch_settings.douyin_webhook_secret:
        raise HTTPException(status_code=422, detail="请先完成公域对接 Webhook 配置")
    mobile = (buyer_mobile or "13700000001").strip()
    if len(mobile) != 11:
        raise HTTPException(status_code=422, detail="buyer_mobile 无效")
    event_id = f"demo_{uuid.uuid4().hex[:16]}"
    ext_no = f"DY_DEMO_{uuid.uuid4().hex[:10].upper()}"
    paid = int(product.price_cents or 0) or 100
    body = DouyinOrderWebhookRequest(
        event_id=event_id,
        tenant_id=ctx.tenant_id,
        channel_product_id=m.channel_product_id,
        external_order_no=ext_no,
        buyer_mobile=mobile,
        paid_amount_cents=paid,
        combo=(m.combo or "1A").strip().upper() or "1A",
    )
    sign_payload = {
        "event_id": body.event_id,
        "external_order_no": body.external_order_no,
        "channel_product_id": body.channel_product_id,
        "paid_amount_cents": body.paid_amount_cents,
    }
    body.sign = stub_douyin_sign(sign_payload, ch_settings.douyin_webhook_secret)
    result = handle_douyin_order(db, body)
    token = result.get("claim_token") or ""
    from app.services.shop.a15_sms_settings_service import get_claim_landing_base

    base = (
        get_claim_landing_base(db, ctx.tenant_id) or settings.SHOP_H5_DEMO_BASE or "http://localhost:5174"
    ).rstrip("/")
    claim_url = f"{base}/#/pages/shop/claim?token={token}&tenant_id={ctx.tenant_id}"
    return {
        **result,
        "claim_url": claim_url,
        "orders_path": "/shop/orders",
        "buyer_mobile": mobile,
        "external_order_no": ext_no,
        "product_name": product.name,
        "message": "已模拟抖店付款，请打开领权链接完成绑手机",
    }


def handle_douyin_order(db: Session, body: DouyinOrderWebhookRequest) -> dict:
    settings = _resolve_tenant_for_webhook(
        db, tenant_id=body.tenant_id, douyin_shop_id=body.douyin_shop_id
    )
    tenant_id = settings.tenant_id
    _verify_sign(
        settings,
        {
            "event_id": body.event_id,
            "external_order_no": body.external_order_no,
            "channel_product_id": body.channel_product_id,
            "paid_amount_cents": body.paid_amount_cents,
        },
        body.sign,
    )
    try:
        _assert_combo_enabled(settings, body.combo)
    except HTTPException as e:
        _audit(
            db,
            tenant_id=tenant_id,
            channel="douyin",
            event="auto_reject",
            detail={
                "reason_code": "channel_combo_not_enabled",
                "external_order_no": body.external_order_no,
                "combo": body.combo,
            },
        )
        db.commit()
        raise e

    existing_ev = (
        db.query(ShopWebhookEvent)
        .filter(ShopWebhookEvent.channel == "douyin", ShopWebhookEvent.event_id == body.event_id)
        .first()
    )
    if existing_ev and existing_ev.processed:
        order = None
        if existing_ev.raw_payload_json:
            oid = existing_ev.raw_payload_json.get("_order_id")
            if oid:
                order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, UUID(oid))).first()
        return {
            "status": "idempotent",
            "order_id": str(order.id) if order else None,
            "order_status": order.status if order else None,
        }

    ev = existing_ev or ShopWebhookEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        channel="douyin",
        event_type=body.event_type,
        event_id=body.event_id,
        raw_payload_json=body.model_dump(mode="json"),
    )
    if not existing_ev:
        db.add(ev)
        db.flush()

    mapping_any = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.tenant_id, tenant_id),
            ShopChannelMapping.channel == "douyin",
            ShopChannelMapping.channel_product_id == body.channel_product_id,
        )
        .first()
    )
    mapping = mapping_any if mapping_any and mapping_any.status == "mapped" else None
    if not mapping:
        reason = "mapping_not_found"
        if mapping_any and mapping_any.status == "paused":
            reason = "mapping_paused"
        elif mapping_any and mapping_any.status == "blocked":
            reason = "mapping_blocked"
        ev.processed = True
        ev.processed_at = _now_utc()
        ev.processing_error = reason
        _audit(
            db,
            tenant_id=tenant_id,
            shop_id=mapping_any.shop_id if mapping_any else None,
            product_id=mapping_any.product_id if mapping_any else None,
            channel="douyin",
            event="auto_reject",
            detail={
                "reason_code": reason,
                "external_order_id": body.external_order_no,
                "external_order_no": body.external_order_no,
                "channel_product_id": body.channel_product_id,
                "mapping_id": str(mapping_any.id) if mapping_any else None,
                "summary": (
                    "Webhook 拒单 · 挂载已暂停"
                    if reason == "mapping_paused"
                    else f"Webhook 拒单 · {reason}"
                ),
            },
        )
        db.commit()
        raise HTTPException(status_code=409, detail=reason)

    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, mapping.product_id)).first()
    if not product or product.status != "on_sale":
        ev.processed = True
        ev.processed_at = _now_utc()
        ev.processing_error = "product_gate_failed"
        _audit(
            db,
            tenant_id=tenant_id,
            shop_id=mapping.shop_id,
            product_id=mapping.product_id,
            channel="douyin",
            event="auto_reject",
            detail={
                "reason_code": "product_gate_failed",
                "external_order_id": body.external_order_no,
                "external_order_no": body.external_order_no,
            },
        )
        db.commit()
        raise HTTPException(status_code=409, detail="product_gate_failed")

    mobile = (body.buyer_mobile or "").strip()
    if not mobile or len(mobile) != 11:
        raise HTTPException(status_code=422, detail="buyer_mobile 无效")

    buyer = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.tenant_id, tenant_id), ShopBuyer.mobile == mobile)
        .first()
    )
    if not buyer:
        buyer = ShopBuyer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            mobile=mobile,
            nickname=f"买家{mobile[-4:]}",
        )
        db.add(buyer)
        db.flush()

    # 幂等：同 external_order_no 已有订单
    dup = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.tenant_id, tenant_id), ShopOrder.source == "public_douyin")
        .all()
    )
    for o in dup:
        snap = o.product_snapshot_json or {}
        if snap.get("external_order_no") == body.external_order_no:
            ev.processed = True
            ev.processed_at = _now_utc()
            payload = dict(ev.raw_payload_json or {})
            payload["_order_id"] = str(o.id)
            ev.raw_payload_json = payload
            db.commit()
            return {"status": "idempotent", "order_id": str(o.id), "order_status": o.status}

    now = _now()
    token = secrets.token_urlsafe(24)[:48]
    from app.services.shop.a15_sms_settings_service import (
        build_claim_h5_link,
        get_claim_expire_days,
    )

    expire_days = get_claim_expire_days(db, tenant_id)
    expires = datetime.utcnow() + timedelta(days=expire_days)
    order = ShopOrder(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        shop_id=mapping.shop_id,
        buyer_id=buyer.id,
        product_id=product.id,
        product_snapshot_json={
            "name": product.name,
            "type": product.type,
            "price_cents": product.price_cents,
            "refund_policy": product.refund_policy,
            "ref_id": str(product.ref_id) if product.ref_id else None,
            "extra": product.extra or {},
            "external_order_no": body.external_order_no,
        },
        order_no=_gen_order_no(),
        type=product.type,
        amount_cents=body.paid_amount_cents,
        status="claim_pending",
        paid_amount_cents=body.paid_amount_cents,
        paid_at=now,
        paid_channel="douyin",
        source="public_douyin",
        buyer_mobile_snapshot=mobile,
        claim_token=token,
        claim_expires_at=expires,
    )
    db.add(order)
    db.flush()
    _activate_entitlement_for_order(db, order)
    claim = ShopClaimToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        order_id=order.id,
        buyer_mobile=mobile,
        token=token,
        status="pending",
        expires_at=expires,
    )
    db.add(claim)
    link = build_claim_h5_link(db, tenant_id, token)
    sms = ShopSmsLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        shop_id=mapping.shop_id,
        buyer_mobile=mobile,
        type="claim_link",
        content=f"【内容获客】您已购买{product.name}，请打开领权链接：{link}",
        status="sent",
        provider_msg_id=f"stub_{uuid.uuid4().hex[:12]}",
        sent_at=_now_utc(),
    )
    db.add(sms)
    _audit(
        db,
        tenant_id=tenant_id,
        shop_id=mapping.shop_id,
        product_id=product.id,
        channel="douyin",
        event="webhook_order_paid",
        detail={
            "external_order_id": body.external_order_no,
            "external_order_no": body.external_order_no,
            "order_id": str(order.id),
            "claim_token": token,
        },
    )
    ev.processed = True
    ev.processed_at = _now_utc()
    payload = dict(body.model_dump(mode="json"))
    payload["_order_id"] = str(order.id)
    ev.raw_payload_json = payload
    db.commit()
    ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, order.id)).first()
    return {
        "status": "ok",
        "order_id": str(order.id),
        "order_status": order.status,
        "claim_token": token,
        "entitlement_id": str(ent.id) if ent else None,
        "sms_status": "sent",
    }


def handle_douyin_refund(db: Session, body: DouyinRefundWebhookRequest) -> dict:
    settings = _resolve_tenant_for_webhook(
        db, tenant_id=body.tenant_id, douyin_shop_id=body.douyin_shop_id
    )
    tenant_id = settings.tenant_id
    _verify_sign(
        settings,
        {
            "event_id": body.event_id,
            "external_order_no": body.external_order_no,
            "channel_product_id": "",
            "paid_amount_cents": "",
        },
        body.sign,
    )
    existing_ev = (
        db.query(ShopWebhookEvent)
        .filter(ShopWebhookEvent.channel == "douyin", ShopWebhookEvent.event_id == body.event_id)
        .first()
    )
    if existing_ev and existing_ev.processed:
        return {"status": "idempotent"}

    ev = existing_ev or ShopWebhookEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        channel="douyin",
        event_type=body.event_type,
        event_id=body.event_id,
        raw_payload_json=body.model_dump(mode="json"),
    )
    if not existing_ev:
        db.add(ev)

    order = None
    for o in (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.tenant_id, tenant_id), ShopOrder.source == "public_douyin")
        .all()
    ):
        if (o.product_snapshot_json or {}).get("external_order_no") == body.external_order_no:
            order = o
            break
    if not order:
        ev.processed = True
        ev.processed_at = _now_utc()
        ev.processing_error = "order_not_found"
        db.commit()
        raise HTTPException(status_code=404, detail="订单不存在")

    now = _now()
    order.status = "refunded"
    order.refund_amount_cents = order.paid_amount_cents or order.amount_cents
    order.refunded_at = now
    order.refund_reason = body.reason or "抖店退款"
    ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, order.id)).first()
    if ent and ent.status != "revoked":
        ent.status = "revoked"
        ent.revoked_at = now
        ent.revoke_reason = order.refund_reason
    ev.processed = True
    ev.processed_at = _now_utc()
    db.commit()
    return {"status": "ok", "order_id": str(order.id), "order_status": "refunded"}


def _mask_mobile(mobile: str | None) -> str | None:
    if not mobile or len(mobile) < 7:
        return None
    return f"{mobile[:3]}****{mobile[-4:]}"


def get_pending_claim_for_buyer(db: Session, buyer: ShopBuyer) -> ClaimInfoOut:
    """M15 领权兑换：按当前买家手机号找回待领取 token。对照 #m15。"""
    conds = [uuid_eq(ShopOrder.buyer_id, buyer.id)]
    if buyer.mobile:
        conds.extend(
            [
                ShopOrder.buyer_mobile_snapshot == buyer.mobile,
                uuid_eq(ShopOrder.claimed_buyer_id, buyer.id),
            ]
        )
    order = (
        db.query(ShopOrder)
        .filter(
            uuid_eq(ShopOrder.tenant_id, buyer.tenant_id),
            ShopOrder.status == "claim_pending",
            ShopOrder.claim_token.isnot(None),
            or_(*conds),
        )
        .order_by(ShopOrder.created_at.desc())
        .first()
    )
    if order and order.claim_token:
        return get_claim_info(db, order.claim_token)
    if buyer.mobile:
        row = (
            db.query(ShopClaimToken)
            .filter(
                uuid_eq(ShopClaimToken.tenant_id, buyer.tenant_id),
                ShopClaimToken.buyer_mobile == buyer.mobile,
                ShopClaimToken.status == "pending",
            )
            .order_by(ShopClaimToken.created_at.desc())
            .first()
        )
        if row:
            return get_claim_info(db, row.token)
    raise HTTPException(status_code=404, detail="暂无待领取权益，请使用短信中的领取链接")


def get_claim_info(db: Session, token: str) -> ClaimInfoOut:
    row = db.query(ShopClaimToken).filter(ShopClaimToken.token == token).first()
    if not row:
        raise HTTPException(status_code=404, detail="领权链接无效")
    now = _now_utc()
    status = row.status
    exp = _as_naive(row.expires_at)
    if status == "pending" and exp and exp < now:
        row.status = "expired"
        db.commit()
        status = "expired"
    order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, row.order_id)).first()
    product_name = None
    order_status = order.status if order else None
    if order:
        product_name = (order.product_snapshot_json or {}).get("name")
    message = None
    if order_status == "refunded":
        status = "refunded"
        message = "订单已退款，无法领取"
    elif status == "expired":
        message = "领取码已过期，请联系商家"
    elif status == "claimed":
        message = "您已领取过该权益"
    elif status == "pending":
        message = "请用购买手机号领取权益"
    return ClaimInfoOut(
        token=token,
        status=status,
        tenant_id=row.tenant_id,
        shop_id=order.shop_id if order else None,
        product_name=product_name,
        mobile_tail=(row.buyer_mobile[-4:] if row.buyer_mobile else None),
        mobile_masked=_mask_mobile(row.buyer_mobile),
        order_id=row.order_id,
        expires_at=row.expires_at,
        order_status=order_status,
        message=message,
    )


def confirm_claim(db: Session, token: str, buyer: ShopBuyer) -> ClaimConfirmResponse:
    row = db.query(ShopClaimToken).filter(ShopClaimToken.token == token).first()
    if not row:
        raise HTTPException(status_code=404, detail="领权链接无效")
    now = _now_utc()
    if row.status == "claimed":
        order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, row.order_id)).first()
        ent = (
            db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, row.order_id)).first()
            if order
            else None
        )
        return ClaimConfirmResponse(
            status="claimed",
            order_id=row.order_id,
            entitlement_id=ent.id if ent else None,
            order_status=order.status if order else "paid",
        )
    exp = _as_naive(row.expires_at)
    if row.status == "expired" or (exp and exp < now):
        row.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="领权链接已过期")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"领权状态为 {row.status}")
    if buyer.tenant_id != row.tenant_id:
        raise HTTPException(status_code=403, detail="租户不匹配")

    order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, row.order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "refunded":
        raise HTTPException(status_code=409, detail="订单已退款，无法领取")

    # 保留当前 JWT buyer：把 mobile/订单/权益并到领取者，避免 bind_mobile 删号导致令牌失效
    mobile_buyer = (
        db.query(ShopBuyer)
        .filter(
            uuid_eq(ShopBuyer.tenant_id, row.tenant_id),
            ShopBuyer.mobile == row.buyer_mobile,
            ShopBuyer.id != buyer.id,
        )
        .first()
    )
    if buyer.mobile and buyer.mobile != row.buyer_mobile:
        raise HTTPException(status_code=409, detail="当前账号已绑定其他手机号")
    if mobile_buyer and mobile_buyer.wx_openid and mobile_buyer.wx_openid != buyer.wx_openid:
        if is_claim_stub_openid(mobile_buyer.wx_openid):
            mobile_buyer.wx_openid = None
        else:
            raise HTTPException(status_code=409, detail="该手机号已绑定其他微信账号")

    if mobile_buyer:
        # 先释放手机号唯一约束，再挂到领取者
        if order.buyer_id == mobile_buyer.id:
            order.buyer_id = buyer.id
        ent_mb = (
            db.query(ShopEntitlement)
            .filter(uuid_eq(ShopEntitlement.order_id, order.id))
            .first()
        )
        if ent_mb:
            ent_mb.buyer_id = buyer.id
        mobile_buyer.mobile = None
        db.flush()
        if not mobile_buyer.wx_openid:
            from app.services.shop.buyer_service import reassign_buyer_owned_rows

            reassign_buyer_owned_rows(db, mobile_buyer.id, buyer.id)
            db.delete(mobile_buyer)
            db.flush()

    if not buyer.mobile:
        buyer.mobile = row.buyer_mobile

    order.buyer_id = buyer.id
    order.claimed_buyer_id = buyer.id
    order.status = "paid"
    row.status = "claimed"
    row.claimed_buyer_id = buyer.id
    row.claimed_at = now
    ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, order.id)).first()
    if ent:
        ent.buyer_id = buyer.id
    db.commit()
    return ClaimConfirmResponse(
        status="claimed",
        order_id=order.id,
        entitlement_id=ent.id if ent else None,
        order_status=order.status,
    )


def expire_claim_token_for_test(db: Session, token: str) -> None:
    row = db.query(ShopClaimToken).filter(ShopClaimToken.token == token).first()
    if not row:
        raise HTTPException(status_code=404, detail="token 不存在")
    row.expires_at = datetime.utcnow() - timedelta(hours=1)
    row.status = "pending"
    db.commit()
