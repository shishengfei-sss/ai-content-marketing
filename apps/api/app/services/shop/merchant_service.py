"""平台商家列表（P02）与续费待办（P11）。"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.models import Tenant, User
from app.models.shop import (
    ShopAuditLog,
    ShopMerchantAccount,
    ShopMerchantServiceLog,
    ShopMerchantTag,
    ShopMerchantTagLink,
    ShopOnboardingApplication,
    ShopStore,
    ShopTenantProspectAssignment,
)
from app.schemas.shop_platform import (
    MerchantExportRequest,
    MerchantRevealResponse,
    MerchantServiceLogItem,
    MerchantStoreItem,
    OnboardingMaterialSection,
    PlatformMerchantDetailResponse,
    PlatformMerchantListItem,
    PlatformMerchantListResponse,
    PlatformPendingRenewalItem,
    PlatformPendingRenewalListResponse,
    ShopExportTaskOut,
    ShopMerchantTagItem,
)
from app.services.platform_shop_service import get_platform_shop_permissions
from app.services.shop.buyer_service import mask_mobile
from app.services.shop.store_manage_service import _month_gmv, _product_counts

_REVEAL_FIELDS = frozenset({"contact_mobile", "id_no"})


def resolve_merchant_list_scope(user: User) -> str:
    perms = set(get_platform_shop_permissions(user))
    if "platform.shop.merchant.list_all" in perms:
        return "all"
    if "platform.shop.merchant.list_assigned" in perms:
        return "assigned"
    if "platform.shop.merchant.read" in perms:
        return "all"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无商家列表数据范围权限")


_COMMON_TAG_NAMES = frozenset({"续费意向", "高价值", "需回访", "华东区", "对公客户"})


def _tag_items_for_merchant(db: Session, merchant_id: UUID) -> tuple[list[str], list[ShopMerchantTagItem]]:
    tags = (
        db.query(ShopMerchantTag)
        .join(ShopMerchantTagLink, ShopMerchantTagLink.tag_id == ShopMerchantTag.id)
        .filter(uuid_eq(ShopMerchantTagLink.merchant_id, merchant_id))
        .order_by(ShopMerchantTag.name.asc())
        .all()
    )
    items = [
        ShopMerchantTagItem(
            id=t.id,
            name=t.name,
            color=t.color or "blue",
            usage_count=t.usage_count or 0,
            is_archived=bool(t.is_archived),
            is_common=t.name in _COMMON_TAG_NAMES,
        )
        for t in tags
    ]
    return [t.name for t in tags], items


def _prospect_manager(db: Session, tenant_id: UUID) -> tuple[UUID | None, str | None]:
    row = (
        db.query(ShopTenantProspectAssignment, User)
        .join(User, User.id == ShopTenantProspectAssignment.account_manager_user_id)
        .filter(uuid_eq(ShopTenantProspectAssignment.tenant_id, tenant_id))
        .first()
    )
    if not row:
        return None, None
    prospect, user = row
    return prospect.account_manager_user_id, user.display_name or user.phone


def _merchant_code(merchant: ShopMerchantAccount | None) -> str | None:
    if merchant is None:
        return None
    return merchant.merchant_no


def _merchant_row(
    merchant: ShopMerchantAccount | None,
    tenant: Tenant,
    onboarding: ShopOnboardingApplication | None,
    manager_name: str | None,
    *,
    manager_id: UUID | None = None,
    tags: list[str] | None = None,
) -> PlatformMerchantListItem:
    tag_names = list(tags or [])
    if merchant is not None:
        onboarding_status = merchant.status
        return PlatformMerchantListItem(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            merchant_id=merchant.id,
            merchant_code=_merchant_code(merchant),
            onboarding_application_id=merchant.onboarding_application_id,
            display_name=merchant.display_name or merchant.legal_name or tenant.name,
            entity_type=merchant.entity_type,
            onboarding_status=onboarding_status,
            plan_label=merchant.plan_label,
            plan_status=merchant.plan_status,
            benefits_until=merchant.benefits_until,
            store_count_active=merchant.store_count_active,
            store_quota=merchant.store_quota,
            account_manager_user_id=merchant.account_manager_user_id,
            account_manager_name=manager_name,
            tags=tag_names,
            fee_tier=merchant.fee_tier,
            has_pending_renewal=merchant.has_pending_renewal,
            created_at=merchant.created_at,
        )
    if onboarding is not None and onboarding.status == "pending":
        return PlatformMerchantListItem(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            merchant_id=None,
            merchant_code=None,
            onboarding_application_id=onboarding.id,
            display_name=onboarding.display_name or onboarding.legal_name or tenant.name,
            entity_type=onboarding.entity_type,
            onboarding_status="reviewing",
            account_manager_user_id=manager_id,
            account_manager_name=manager_name,
            tags=[],
            created_at=onboarding.submitted_at,
        )
    return PlatformMerchantListItem(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        display_name=tenant.name,
        onboarding_status="not_onboarded",
        account_manager_user_id=manager_id,
        account_manager_name=manager_name,
        tags=[],
        created_at=tenant.created_at,
    )


def _sort_key(dt: datetime | None) -> float:
    if dt is None:
        return 0.0
    if dt.tzinfo is not None:
        return dt.timestamp()
    return dt.replace(tzinfo=timezone.utc).timestamp()


# 对照 PRD #p02-list 可排序列：商家 · 商家编码 · 权益至 · 店铺数 · 创建时间
_MERCHANT_SORT_FIELDS = frozenset(
    {"display_name", "merchant_code", "benefits_until", "store_count", "created_at"}
)


def _row_sort_key(row: PlatformMerchantListItem, sort_by: str):
    if sort_by == "display_name":
        return (row.display_name or "").casefold()
    if sort_by == "merchant_code":
        return (row.merchant_code or "").casefold()
    if sort_by == "benefits_until":
        # 无到期排最后（升序时靠后；降序时靠前用反向再处理）
        return row.benefits_until.toordinal() if row.benefits_until else -1
    if sort_by == "store_count":
        return row.store_count_active if row.store_count_active is not None else -1
    # created_at default
    return _sort_key(row.created_at)


def _sort_merchant_rows(
    rows: list[PlatformMerchantListItem],
    *,
    sort_by: str | None,
    sort_dir: str | None,
) -> None:
    field = sort_by if sort_by in _MERCHANT_SORT_FIELDS else "created_at"
    reverse = (sort_dir or "desc").lower() != "asc"
    rows.sort(key=lambda r: _row_sort_key(r, field), reverse=reverse)


def mask_id_no(id_no: str | None) -> str | None:
    if not id_no:
        return None
    s = str(id_no)
    if "*" in s:
        return s
    if len(s) < 8:
        return "***"
    return f"{s[:3]}{'*' * (len(s) - 7)}{s[-4:]}"


def mask_ocr_results(items: list | None) -> list:
    """申请详情/材料中的 OCR 快照：证号脱敏；OCR 当时填表接口仍返回明文。"""
    out: list = []
    for item in items or []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        row = dict(item)
        fields = dict(row.get("fields") or {})
        if fields.get("id_no"):
            fields["id_no"] = mask_id_no(fields.get("id_no"))
        row["fields"] = fields
        out.append(row)
    return out


def _mask_bank_account(info: dict | None) -> tuple[dict, str | None]:
    raw = dict(info or {})
    if not raw:
        return {}, None
    acc = str(raw.get("account_no") or raw.get("account") or "")
    bank = str(raw.get("bank_name") or "").strip()
    name = str(raw.get("account_name") or "").strip()
    out: dict = {}
    if bank:
        out["bank_name"] = bank
    if name:
        out["account_name"] = name
    display = None
    if len(acc) >= 4:
        out["account_no_masked"] = f"尾号 {acc[-4:]}"
        display = " ".join(p for p in (bank or None, f"尾号 {acc[-4:]}") if p)
    elif bank or name:
        display = " ".join(p for p in (bank or None, name or None) if p)
    return out, display


def _approved_application(
    db: Session,
    merchant: ShopMerchantAccount | None,
    fallback: ShopOnboardingApplication | None,
) -> ShopOnboardingApplication | None:
    if merchant is not None and merchant.onboarding_application_id:
        app = (
            db.query(ShopOnboardingApplication)
            .filter(uuid_eq(ShopOnboardingApplication.id, merchant.onboarding_application_id))
            .first()
        )
        if app is not None:
            return app
    if merchant is not None:
        approved = (
            db.query(ShopOnboardingApplication)
            .filter(
                uuid_eq(ShopOnboardingApplication.tenant_id, merchant.tenant_id),
                ShopOnboardingApplication.status == "approved",
            )
            .order_by(ShopOnboardingApplication.reviewed_at.desc())
            .first()
        )
        if approved is not None:
            return approved
    return fallback


def assert_can_read_merchant_tenant(db: Session, user: User, tenant_id: UUID) -> None:
    scope = resolve_merchant_list_scope(user)
    if scope == "all":
        return
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if merchant is not None:
        if merchant.account_manager_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅可查看所辖商家")
        return
    prospect = (
        db.query(ShopTenantProspectAssignment)
        .filter(uuid_eq(ShopTenantProspectAssignment.tenant_id, tenant_id))
        .first()
    )
    if prospect is None or prospect.account_manager_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅可查看所辖商家")


def _build_onboarding_materials(
    merchant: ShopMerchantAccount | None,
    onboarding: ShopOnboardingApplication | None,
    snapshot: ShopOnboardingApplication | None = None,
) -> OnboardingMaterialSection | None:
    snap = snapshot or onboarding
    files = (snap.qualification_files if snap is not None else None) or {}
    ocr = list((snap.ocr_results if snap is not None else None) or [])
    bank_raw = (snap.bank_account_info if snap is not None else None) or {}
    bank, bank_display = _mask_bank_account(bank_raw)
    if merchant is not None:
        return OnboardingMaterialSection(
            source="merchant",
            application_id=merchant.onboarding_application_id or (snap.id if snap else None),
            application_no=(snap.application_no if snap is not None else None),
            entity_type=merchant.entity_type,
            legal_name=merchant.legal_name,
            display_name=merchant.display_name,
            contact_name=merchant.contact_name,
            contact_mobile=mask_mobile(merchant.contact_mobile),
            id_no=mask_id_no(merchant.id_no),
            unified_social_credit_code=merchant.unified_social_credit_code,
            legal_rep_name=merchant.legal_rep_name,
            qualification_files=files,
            ocr_results=mask_ocr_results(ocr),
            bank_account_info=bank,
            bank_account_display=bank_display,
            status=merchant.status,
        )
    if onboarding is not None:
        return OnboardingMaterialSection(
            source="application",
            application_id=onboarding.id,
            application_no=onboarding.application_no,
            entity_type=onboarding.entity_type,
            legal_name=onboarding.legal_name,
            display_name=onboarding.display_name,
            contact_name=onboarding.contact_name,
            contact_mobile=mask_mobile(onboarding.contact_mobile),
            id_no=mask_id_no(onboarding.id_no),
            unified_social_credit_code=onboarding.unified_social_credit_code,
            legal_rep_name=onboarding.legal_rep_name,
            qualification_files=onboarding.qualification_files or {},
            ocr_results=mask_ocr_results(onboarding.ocr_results),
            bank_account_info=bank,
            bank_account_display=bank_display,
            status=onboarding.status,
        )
    return None


def get_platform_merchant_detail(db: Session, user: User, tenant_id: UUID) -> PlatformMerchantDetailResponse:
    assert_can_read_merchant_tenant(db, user, tenant_id)
    scope = resolve_merchant_list_scope(user)

    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租户不存在")

    merchant = (
        db.query(ShopMerchantAccount)
        .options(joinedload(ShopMerchantAccount.account_manager))
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
        .first()
    )
    onboarding = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id))
        .order_by(ShopOnboardingApplication.submitted_at.desc())
        .first()
    )

    stores: list[MerchantStoreItem] = []
    service_logs: list[MerchantServiceLogItem] = []

    if merchant is not None:
        store_rows = (
            db.query(ShopStore)
            .filter(uuid_eq(ShopStore.tenant_id, tenant_id))
            .order_by(ShopStore.created_at.asc())
            .all()
        )
        shop_ids = [s.id for s in store_rows]
        gmvs = _month_gmv(db, shop_ids)
        products = _product_counts(db, shop_ids)
        stores = [
            MerchantStoreItem(
                id=s.id,
                name=s.name,
                slug=s.slug,
                status=s.status,
                logo_url=s.logo_url,
                wx_mp_app_id=s.wx_mp_app_id,
                created_at=s.created_at,
                product_count=products.get(s.id, 0),
                month_gmv_cents=gmvs.get(s.id, 0),
            )
            for s in store_rows
        ]
        month_gmv_cents = sum(gmvs.values())
        snap = _approved_application(db, merchant, onboarding)
        log_rows = (
            db.query(ShopMerchantServiceLog)
            .options(joinedload(ShopMerchantServiceLog.operator))
            .filter(
                uuid_eq(ShopMerchantServiceLog.merchant_id, merchant.id),
                ShopMerchantServiceLog.type != "audit",
            )
            .order_by(ShopMerchantServiceLog.created_at.desc())
            .limit(50)
            .all()
        )
        service_logs = [
            MerchantServiceLogItem(
                id=log.id,
                type=log.type,
                status=log.status,
                content=log.content,
                payload_json=log.payload_json or {},
                operator_user_id=log.operator_user_id,
                operator_name=log.operator.display_name if log.operator else None,
                follow_up_at=log.follow_up_at,
                related_onboarding_id=log.related_onboarding_id,
                related_subscription_id=log.related_subscription_id,
                created_at=log.created_at,
                updated_at=log.updated_at,
            )
            for log in log_rows
        ]
        manager_name = merchant.account_manager.display_name if merchant.account_manager else None
        tags, tag_items = _tag_items_for_merchant(db, merchant.id)
        return PlatformMerchantDetailResponse(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            merchant_id=merchant.id,
            merchant_code=merchant.merchant_no,
            onboarding_application_id=merchant.onboarding_application_id,
            display_name=merchant.display_name or merchant.legal_name or tenant.name,
            entity_type=merchant.entity_type,
            onboarding_status=merchant.status,
            contact_name=merchant.contact_name,
            contact_mobile=mask_mobile(merchant.contact_mobile),
            plan_label=merchant.plan_label,
            plan_status=merchant.plan_status,
            benefits_until=merchant.benefits_until,
            store_count_active=merchant.store_count_active,
            store_quota=merchant.store_quota,
            account_manager_user_id=merchant.account_manager_user_id,
            account_manager_name=manager_name,
            tags=tags,
            tag_items=tag_items,
            has_pending_renewal=merchant.has_pending_renewal,
            onboarding_approved_at=merchant.onboarding_approved_at,
            stores=stores,
            month_gmv_cents=month_gmv_cents,
            onboarding_materials=_build_onboarding_materials(merchant, onboarding, snap),
            service_logs=service_logs,
            operation_logs=_build_operation_logs(db, tenant_id),
            scope=scope,
        )

    if onboarding is not None and onboarding.status == "pending":
        mgr_id, mgr_name = _prospect_manager(db, tenant_id)
        return PlatformMerchantDetailResponse(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            onboarding_application_id=onboarding.id,
            display_name=onboarding.display_name or onboarding.legal_name or tenant.name,
            entity_type=onboarding.entity_type,
            onboarding_status="reviewing",
            account_manager_user_id=mgr_id,
            account_manager_name=mgr_name,
            onboarding_materials=_build_onboarding_materials(None, onboarding),
            scope=scope,
        )

    mgr_id, mgr_name = _prospect_manager(db, tenant_id)
    return PlatformMerchantDetailResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        display_name=tenant.name,
        onboarding_status="not_onboarded",
        account_manager_user_id=mgr_id,
        account_manager_name=mgr_name,
        onboarding_materials=None,
        scope=scope,
    )


def list_platform_merchants(
    db: Session,
    user: User,
    *,
    q: str | None = None,
    onboarding_status: str | None = None,
    plan_status: str | None = None,
    entity_type: str | None = None,
    plan_label: str | None = None,
    fee_tier: str | None = None,
    account_manager_user_id: UUID | None = None,
    tag_ids: list[UUID] | None = None,
    benefits_from: date | None = None,
    benefits_until: date | None = None,
    store_count_min: int | None = None,
    store_count_max: int | None = None,
    created_from: date | None = None,
    created_until: date | None = None,
    tab: str | None = None,
    include_not_onboarded: bool = False,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PlatformMerchantListResponse:
    scope = resolve_merchant_list_scope(user)
    if tab == "my_clients":
        scope = "assigned"

    merchant_q = (
        db.query(ShopMerchantAccount)
        .options(joinedload(ShopMerchantAccount.tenant), joinedload(ShopMerchantAccount.account_manager))
        .join(Tenant, ShopMerchantAccount.tenant_id == Tenant.id)
    )
    if scope == "assigned":
        merchant_q = merchant_q.filter(uuid_eq(ShopMerchantAccount.account_manager_user_id, user.id))

    if q:
        like = f"%{q.strip()}%"
        merchant_q = merchant_q.filter(
            or_(
                ShopMerchantAccount.display_name.ilike(like),
                ShopMerchantAccount.legal_name.ilike(like),
                ShopMerchantAccount.merchant_no.ilike(like),
                Tenant.name.ilike(like),
            )
        )
    if onboarding_status in ("active", "suspended", "closed"):
        merchant_q = merchant_q.filter(ShopMerchantAccount.status == onboarding_status)
    if plan_status:
        merchant_q = merchant_q.filter(ShopMerchantAccount.plan_status == plan_status)
    if entity_type:
        merchant_q = merchant_q.filter(ShopMerchantAccount.entity_type == entity_type)
    if plan_label:
        merchant_q = merchant_q.filter(ShopMerchantAccount.plan_label == plan_label)
    if fee_tier:
        merchant_q = merchant_q.filter(ShopMerchantAccount.fee_tier == fee_tier)
    if account_manager_user_id:
        merchant_q = merchant_q.filter(uuid_eq(ShopMerchantAccount.account_manager_user_id, account_manager_user_id))
    if tag_ids:
        merchant_q = merchant_q.filter(
            ShopMerchantAccount.id.in_(
                select(ShopMerchantTagLink.merchant_id).where(ShopMerchantTagLink.tag_id.in_(tag_ids))
            )
        )
    if benefits_from:
        merchant_q = merchant_q.filter(ShopMerchantAccount.benefits_until >= benefits_from)
    if benefits_until:
        merchant_q = merchant_q.filter(ShopMerchantAccount.benefits_until <= benefits_until)
    if store_count_min is not None:
        merchant_q = merchant_q.filter(ShopMerchantAccount.store_count_active >= store_count_min)
    if store_count_max is not None:
        merchant_q = merchant_q.filter(ShopMerchantAccount.store_count_active <= store_count_max)
    if created_from:
        merchant_q = merchant_q.filter(ShopMerchantAccount.created_at >= datetime.combine(created_from, datetime.min.time(), tzinfo=timezone.utc))
    if created_until:
        merchant_q = merchant_q.filter(
            ShopMerchantAccount.created_at
            < datetime.combine(created_until, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
        )
    if tab == "expiring_soon":
        merchant_q = merchant_q.filter(ShopMerchantAccount.plan_status == "expiring_soon")
    elif tab == "expired":
        merchant_q = merchant_q.filter(ShopMerchantAccount.plan_status == "expired")
    elif tab == "suspended":
        merchant_q = merchant_q.filter(ShopMerchantAccount.status == "suspended")

    merchants = merchant_q.order_by(ShopMerchantAccount.created_at.desc()).all()
    rows: list[PlatformMerchantListItem] = []
    seen_tenant_ids: set[UUID] = set()
    tag_map: dict[UUID, list[str]] = {}
    if merchants:
        tag_pairs = (
            db.query(ShopMerchantTagLink.merchant_id, ShopMerchantTag.name)
            .join(ShopMerchantTag, ShopMerchantTag.id == ShopMerchantTagLink.tag_id)
            .filter(ShopMerchantTagLink.merchant_id.in_([m.id for m in merchants]))
            .order_by(ShopMerchantTag.name.asc())
            .all()
        )
        for mid, name in tag_pairs:
            tag_map.setdefault(mid, []).append(name)

    prospect_pairs = (
        db.query(ShopTenantProspectAssignment, User)
        .join(User, User.id == ShopTenantProspectAssignment.account_manager_user_id)
        .all()
    )
    prospect_map = {
        p.tenant_id: (p.account_manager_user_id, manager.display_name or manager.phone)
        for p, manager in prospect_pairs
    }

    for m in merchants:
        seen_tenant_ids.add(m.tenant_id)
        if onboarding_status in ("not_onboarded", "reviewing"):
            continue
        manager_name = m.account_manager.display_name if m.account_manager else None
        rows.append(_merchant_row(m, m.tenant, None, manager_name, tags=tag_map.get(m.id, [])))

    skip_pending = any(
        [
            entity_type,
            plan_label,
            fee_tier,
            plan_status,
            benefits_from,
            benefits_until,
            store_count_min is not None,
            store_count_max is not None,
            bool(tag_ids),
            tab in ("expiring_soon", "expired", "suspended", "my_clients"),
        ]
    )

    if scope == "all" and not skip_pending and (tab in (None, "all", "reviewing") or onboarding_status == "reviewing"):
        pending_q = (
            db.query(ShopOnboardingApplication, Tenant)
            .join(Tenant, ShopOnboardingApplication.tenant_id == Tenant.id)
            .filter(ShopOnboardingApplication.status == "pending")
        )
        if seen_tenant_ids:
            pending_q = pending_q.filter(~ShopOnboardingApplication.tenant_id.in_(seen_tenant_ids))
        if q:
            like = f"%{q.strip()}%"
            pending_q = pending_q.filter(
                or_(
                    ShopOnboardingApplication.display_name.ilike(like),
                    ShopOnboardingApplication.legal_name.ilike(like),
                    Tenant.name.ilike(like),
                )
            )
        if entity_type:
            pending_q = pending_q.filter(ShopOnboardingApplication.entity_type == entity_type)
        for onboarding, tenant in pending_q.all():
            if onboarding.tenant_id in seen_tenant_ids:
                continue
            row = _merchant_row(None, tenant, onboarding, None)
            if onboarding_status and onboarding_status != "reviewing":
                continue
            rows.append(row)
            seen_tenant_ids.add(tenant.id)

    if (
        scope == "all"
        and include_not_onboarded
        and not skip_pending
        and tab not in ("expiring_soon", "expired", "suspended", "my_clients", "reviewing")
    ):
        tenant_q = db.query(Tenant)
        if q:
            like = f"%{q.strip()}%"
            tenant_q = tenant_q.filter(Tenant.name.ilike(like))
        if seen_tenant_ids:
            tenant_q = tenant_q.filter(~Tenant.id.in_(seen_tenant_ids))
        for tenant in tenant_q.order_by(Tenant.created_at.desc()).limit(200).all():
            if onboarding_status and onboarding_status != "not_onboarded":
                continue
            mgr_id, mgr_name = prospect_map.get(tenant.id, (None, None))
            if account_manager_user_id and mgr_id != account_manager_user_id:
                continue
            rows.append(
                _merchant_row(None, tenant, None, mgr_name, manager_id=mgr_id)
            )
            seen_tenant_ids.add(tenant.id)

    if (
        not tag_ids
        and (tab == "my_clients" or (scope == "assigned" and include_not_onboarded))
        and tab not in ("expiring_soon", "expired", "suspended", "reviewing")
        and onboarding_status in (None, "", "not_onboarded")
    ):
        for prospect, manager in prospect_pairs:
            if prospect.account_manager_user_id != user.id:
                continue
            if prospect.tenant_id in seen_tenant_ids:
                continue
            if account_manager_user_id and prospect.account_manager_user_id != account_manager_user_id:
                continue
            tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, prospect.tenant_id)).first()
            if tenant is None:
                continue
            if q and q.strip():
                like = q.strip().casefold()
                if like not in (tenant.name or "").casefold():
                    continue
            rows.append(
                _merchant_row(
                    None,
                    tenant,
                    None,
                    manager.display_name or manager.phone,
                    manager_id=prospect.account_manager_user_id,
                )
            )
            seen_tenant_ids.add(tenant.id)

    _sort_merchant_rows(rows, sort_by=sort_by, sort_dir=sort_dir)
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return PlatformMerchantListResponse(
        items=rows[start:end],
        total=total,
        page=page,
        page_size=page_size,
        scope=scope,
    )


def list_pending_renewals(db: Session) -> PlatformPendingRenewalListResponse:
    logs = (
        db.query(ShopMerchantServiceLog)
        .options(
            joinedload(ShopMerchantServiceLog.merchant).joinedload(ShopMerchantAccount.tenant),
            joinedload(ShopMerchantServiceLog.operator),
        )
        .filter(
            ShopMerchantServiceLog.type == "renewal_request",
            ShopMerchantServiceLog.status.in_(("pending", "processing")),
        )
        .order_by(ShopMerchantServiceLog.created_at.desc())
        .all()
    )
    items: list[PlatformPendingRenewalItem] = []
    for log in logs:
        merchant = log.merchant
        payload = log.payload_json or {}
        items.append(
            PlatformPendingRenewalItem(
                service_log_id=log.id,
                merchant_id=log.merchant_id,
                tenant_id=log.tenant_id,
                display_name=merchant.display_name if merchant else "",
                plan_label=merchant.plan_label if merchant else None,
                target_plan=payload.get("target_plan"),
                purchase_mode=payload.get("purchase_mode"),
                quoted_amount_cents=payload.get("quoted_amount_cents"),
                catalog_price_cents=payload.get("catalog_price_cents"),
                content=log.content,
                status=log.status,
                status_label="处理中" if log.status == "processing" else "待处理",
                operator_user_id=log.operator_user_id,
                operator_name=log.operator.display_name if log.operator else None,
                created_at=log.created_at,
            )
        )
    return PlatformPendingRenewalListResponse(items=items, total=len(items))


def _build_operation_logs(db: Session, tenant_id: UUID) -> list[dict]:
    """对照 #p02b-audit：只读操作日志，来自 shop_audit_logs。"""
    rows = (
        db.query(ShopAuditLog)
        .filter(uuid_eq(ShopAuditLog.tenant_id, tenant_id))
        .order_by(ShopAuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": row.id,
            "at": row.created_at,
            "action": row.action,
            "summary": row.summary,
            "operator_name": row.operator_name,
            "source": row.source,
        }
        for row in rows
    ]


def refresh_plan_statuses(db: Session) -> int:
    """将 benefits_until 同步为 plan_status（定时任务可复用）。"""
    today = date.today()
    soon = today + timedelta(days=30)
    updated = 0
    merchants = db.query(ShopMerchantAccount).filter(ShopMerchantAccount.benefits_until.isnot(None)).all()
    for m in merchants:
        if m.benefits_until is None:
            continue
        new_status = m.plan_status
        if m.benefits_until < today:
            new_status = "expired"
        elif m.benefits_until <= soon:
            new_status = "expiring_soon"
        else:
            new_status = "active"
        if new_status != m.plan_status:
            m.plan_status = new_status
            updated += 1
    if updated:
        db.commit()
    return updated


def _assert_can_reveal(db: Session, user: User, tenant_id: UUID) -> None:
    perms = set(get_platform_shop_permissions(user))
    if not perms.intersection(
        {
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        }
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无查看权限")
    try:
        assert_can_read_merchant_tenant(db, user, tenant_id)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无查看权限") from None


def reveal_merchant_sensitive(
    db: Session,
    user: User,
    tenant_id: UUID,
    field: str | None,
) -> MerchantRevealResponse:
    """对照 #p02b-materials：POST reveal-sensitive，写操作日志。"""
    _assert_can_reveal(db, user, tenant_id)
    key = (field or "contact_mobile").strip()
    if key not in _REVEAL_FIELDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="字段无效")

    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    onboarding = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id))
        .order_by(ShopOnboardingApplication.submitted_at.desc())
        .first()
    )
    snap = _approved_application(db, merchant, onboarding)
    if key == "contact_mobile":
        raw = (merchant.contact_mobile if merchant else None) or (snap.contact_mobile if snap else None)
        content = "查看经营联系人手机"
    else:
        raw = (merchant.id_no if merchant else None) or (snap.id_no if snap else None)
        if not raw:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该主体无身份证号")
        content = "查看身份证号"
    if not raw:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="无可揭露字段")

    operator_id = user.id
    if merchant is not None:
        db.add(
            ShopMerchantServiceLog(
                merchant_id=merchant.id,
                tenant_id=tenant_id,
                type="audit",
                status="logged",
                content=content,
                payload_json={"action": "reveal_sensitive", "field": key},
                operator_user_id=operator_id,
            )
        )
        from app.services.shop.audit_log_service import (
            ACTION_REVEAL,
            SOURCE_MERCHANT_DETAIL,
            record_merchant_audit,
        )

        record_merchant_audit(
            db,
            tenant_id=tenant_id,
            merchant_id=merchant.id,
            action=ACTION_REVEAL,
            summary=content,
            source=SOURCE_MERCHANT_DETAIL,
            operator=user,
        )
        db.commit()
    return MerchantRevealResponse(field=key, value=raw)


_MERCHANT_CSV_ALL_HEADERS = [
    "商家展示名",
    "租户",
    "商家编码",
    "主体",
    "当前套餐",
    "套餐状态",
    "权益至",
    "店铺数",
    "店铺配额",
    "商家管家",
    "标签",
    "费率档",
    "入驻状态",
    "创建时间",
]

_MERCHANT_CSV_COL_MAP = {
    "display_name": ["商家展示名"],
    "tenant_name": ["租户"],
    "merchant_code": ["商家编码"],
    "entity_type": ["主体"],
    "plan_label": ["当前套餐"],
    "plan_status": ["套餐状态"],
    "benefits_until": ["权益至"],
    "store_count": ["店铺数", "店铺配额"],
    "account_manager_name": ["商家管家"],
    "tags": ["标签"],
    "fee_tier": ["费率档"],
    "created_at": ["创建时间"],
    "onboarding_status": ["入驻状态"],
}


def _parse_export_tag_ids(raw: str | None) -> list[UUID] | None:
    if not raw:
        return None
    out: list[UUID] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(UUID(part))
    return out or None


def _merchant_csv_headers(columns: list[str] | None) -> list[str]:
    if not columns:
        return list(_MERCHANT_CSV_ALL_HEADERS)
    headers: list[str] = []
    seen: set[str] = set()
    for key in columns:
        for h in _MERCHANT_CSV_COL_MAP.get(key, []):
            if h not in seen:
                seen.add(h)
                headers.append(h)
    return headers or list(_MERCHANT_CSV_ALL_HEADERS)


def export_platform_merchants_csv(
    db: Session,
    user: User,
    *,
    q: str | None = None,
    onboarding_status: str | None = None,
    plan_status: str | None = None,
    entity_type: str | None = None,
    plan_label: str | None = None,
    fee_tier: str | None = None,
    account_manager_user_id: UUID | None = None,
    tag_ids: list[UUID] | None = None,
    benefits_from: date | None = None,
    benefits_until: date | None = None,
    store_count_min: int | None = None,
    store_count_max: int | None = None,
    created_from: date | None = None,
    created_until: date | None = None,
    tab: str | None = None,
    include_not_onboarded: bool = True,
    sort_by: str | None = "created_at",
    sort_dir: str | None = "desc",
    columns: list[str] | None = None,
    limit: int = 5000,
    raise_too_many: bool = True,
) -> str:
    data = list_platform_merchants(
        db,
        user,
        q=q,
        onboarding_status=onboarding_status,
        plan_status=plan_status,
        entity_type=entity_type,
        plan_label=plan_label,
        fee_tier=fee_tier,
        account_manager_user_id=account_manager_user_id,
        tag_ids=tag_ids,
        benefits_from=benefits_from,
        benefits_until=benefits_until,
        store_count_min=store_count_min,
        store_count_max=store_count_max,
        created_from=created_from,
        created_until=created_until,
        tab=tab,
        include_not_onboarded=include_not_onboarded,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=1,
        page_size=limit,
    )
    if raise_too_many and data.total > limit:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    headers = _merchant_csv_headers(columns)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in data.items:
        values = {
            "商家展示名": row.display_name,
            "租户": row.tenant_name,
            "商家编码": row.merchant_code or "",
            "主体": row.entity_type or "",
            "当前套餐": row.plan_label or "",
            "套餐状态": row.plan_status or "",
            "权益至": row.benefits_until.isoformat() if row.benefits_until else "",
            "店铺数": row.store_count_active if row.store_count_active is not None else "",
            "店铺配额": row.store_quota if row.store_quota is not None else "",
            "商家管家": row.account_manager_name or "",
            "标签": "、".join(row.tags or []),
            "费率档": row.fee_tier or "",
            "入驻状态": row.onboarding_status,
            "创建时间": row.created_at.isoformat() if row.created_at else "",
        }
        writer.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_merchant_export_task(
    db: Session, user: User, body: MerchantExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or MerchantExportRequest()
    filters = {
        "q": body.q,
        "onboarding_status": body.onboarding_status,
        "plan_status": body.plan_status,
        "entity_type": body.entity_type,
        "plan_label": body.plan_label,
        "fee_tier": body.fee_tier,
        "account_manager_user_id": str(body.account_manager_user_id)
        if body.account_manager_user_id
        else None,
        "tag_ids": body.tag_ids,
        "benefits_from": str(body.benefits_from) if body.benefits_from else None,
        "benefits_until": str(body.benefits_until) if body.benefits_until else None,
        "store_count_min": body.store_count_min,
        "store_count_max": body.store_count_max,
        "created_from": str(body.created_from) if body.created_from else None,
        "created_until": str(body.created_until) if body.created_until else None,
        "tab": body.tab,
        "columns": body.columns,
    }
    csv_text = export_platform_merchants_csv(
        db,
        user,
        q=body.q,
        onboarding_status=body.onboarding_status,
        plan_status=body.plan_status,
        entity_type=body.entity_type,
        plan_label=body.plan_label,
        fee_tier=body.fee_tier,
        account_manager_user_id=body.account_manager_user_id,
        tag_ids=_parse_export_tag_ids(body.tag_ids),
        benefits_from=body.benefits_from,
        benefits_until=body.benefits_until,
        store_count_min=body.store_count_min,
        store_count_max=body.store_count_max,
        created_from=body.created_from,
        created_until=body.created_until,
        tab=body.tab,
        include_not_onboarded=body.include_not_onboarded,
        sort_by=body.sort_by,
        sort_dir=body.sort_dir,
        columns=body.columns,
    )
    return export_task_service.persist_csv_for_user(
        db,
        user,
        resource="merchants",
        file_name="shop-merchants.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_merchant_export_task(db: Session, user: User, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "merchants")


def read_merchant_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "merchants")
