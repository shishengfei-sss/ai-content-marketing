"""平台代发起入驻（P02-A）与商家自申（A20）。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import Tenant, User
from app.models.shop import ShopMerchantAccount, ShopOnboardingApplication, ShopTenantProspectAssignment
from app.permissions import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_SHOP_ADMIN
from app.services.platform_shop_service import get_platform_shop_permissions
from app.services.shop.buyer_service import mask_mobile
from app.services.shop.merchant_service import _mask_bank_account, mask_id_no, mask_ocr_results
from app.services.shop.platform_number_service import generate_platform_number
from app.schemas.shop_platform import (
    MerchantOnboardingApplicationSummary,
    MerchantOnboardingStatusResponse,
    MerchantSelfOnboardingCreate,
    OnboardingApplicationCreate,
    OnboardingApplicationOut,
    OnboardingPrefillResponse,
    TenantOnboardingOption,
    TenantOnboardingSearchResponse,
)

ENTITY_TYPES = frozenset({"personal", "individual_business", "enterprise"})
_MOBILE_RE = re.compile(r"^1\d{10}$")


def _validate_mobile(mobile: str) -> None:
    if not _MOBILE_RE.match(mobile.strip()):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="联系人手机号格式不正确")


def _validate_entity_fields_raw(
    *,
    entity_type: str,
    id_no: str | None,
    unified_social_credit_code: str | None,
    legal_rep_name: str | None,
) -> None:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="主体类型无效")
    if entity_type == "personal":
        if not (id_no and id_no.strip()):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="个人主体需填写身份证号")
    else:
        if not (unified_social_credit_code and unified_social_credit_code.strip()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="个体/企业主体需填写统一社会信用代码"
            )
        if not (legal_rep_name and legal_rep_name.strip()):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="个体/企业主体需填写法人姓名")


def _validate_entity_fields(payload: OnboardingApplicationCreate | MerchantSelfOnboardingCreate) -> None:
    _validate_entity_fields_raw(
        entity_type=payload.entity_type,
        id_no=payload.id_no,
        unified_social_credit_code=payload.unified_social_credit_code,
        legal_rep_name=payload.legal_rep_name,
    )


def _file_id(qualification_files: dict, key: str) -> str:
    v = (qualification_files or {}).get(key)
    if isinstance(v, dict):
        return str(v.get("file_id") or "").strip()
    return str(v or "").strip()


def _validate_merchant_self_materials(entity_type: str, qualification_files: dict) -> None:
    """商家自申提交时材料须齐（PRD：A20 提交即齐；正反面分键）。"""
    q = qualification_files or {}
    if entity_type == "personal":
        if not _file_id(q, "id_card_front"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传身份证人像面")
        if not _file_id(q, "id_card_back"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传身份证国徽面")
        return
    if not _file_id(q, "business_license"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传营业执照")
    if not _file_id(q, "legal_id_front"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传法人身份证")


def assert_tenant_eligible_for_onboarding(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租户不存在")
    existing_merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if existing_merchant:
        if existing_merchant.status == "closed":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="商家已清退，不可再入驻")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该租户已入驻")
    pending = (
        db.query(ShopOnboardingApplication)
        .filter(
            uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id),
            ShopOnboardingApplication.status == "pending",
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该租户已有待审入驻申请")
    return tenant


def _to_out(app: ShopOnboardingApplication) -> OnboardingApplicationOut:
    bank, _ = _mask_bank_account(app.bank_account_info)
    return OnboardingApplicationOut(
        id=app.id,
        application_no=app.application_no,
        tenant_id=app.tenant_id,
        entity_type=app.entity_type,
        initiator=app.initiator,
        status=app.status,
        legal_name=app.legal_name,
        display_name=app.display_name,
        contact_name=app.contact_name,
        contact_mobile=mask_mobile(app.contact_mobile) or "",
        id_no=mask_id_no(app.id_no),
        unified_social_credit_code=app.unified_social_credit_code,
        legal_rep_name=app.legal_rep_name,
        bank_account_info=bank,
        qualification_files=app.qualification_files or {},
        ocr_results=mask_ocr_results(app.ocr_results),
        remark=app.remark,
        submitted_at=app.submitted_at,
        created_by=app.created_by,
    )


def _to_summary(app: ShopOnboardingApplication) -> MerchantOnboardingApplicationSummary:
    bank, _ = _mask_bank_account(app.bank_account_info)
    return MerchantOnboardingApplicationSummary(
        id=app.id,
        application_no=app.application_no,
        status=app.status,
        entity_type=app.entity_type,
        legal_name=app.legal_name,
        display_name=app.display_name,
        contact_name=app.contact_name,
        contact_mobile=mask_mobile(app.contact_mobile) or "",
        id_no=mask_id_no(app.id_no),
        unified_social_credit_code=app.unified_social_credit_code,
        legal_rep_name=app.legal_rep_name,
        reject_code=app.reject_code,
        reject_reason=app.reject_reason,
        submitted_at=app.submitted_at,
        bank_account_info=bank,
        qualification_files=app.qualification_files or {},
        ocr_results=mask_ocr_results(app.ocr_results),
        remark=app.remark,
    )


def create_onboarding_application(
    db: Session,
    user: User,
    payload: OnboardingApplicationCreate,
) -> OnboardingApplicationOut:
    _validate_mobile(payload.contact_mobile)
    _validate_entity_fields(payload)
    tenant = assert_tenant_eligible_for_onboarding(db, payload.tenant_id)

    app = ShopOnboardingApplication(
        tenant_id=payload.tenant_id,
        application_no=generate_platform_number(db, "shop_onboarding"),
        entity_type=payload.entity_type,
        initiator="ops_assisted",
        status="pending",
        legal_name=payload.legal_name.strip() or tenant.name,
        display_name=(payload.display_name or payload.legal_name or tenant.name).strip(),
        contact_name=payload.contact_name.strip(),
        contact_mobile=payload.contact_mobile.strip(),
        id_no=(payload.id_no or "").strip() or None,
        unified_social_credit_code=(payload.unified_social_credit_code or "").strip() or None,
        legal_rep_name=(payload.legal_rep_name or "").strip() or None,
        bank_account_info=payload.bank_account_info or {},
        qualification_files=payload.qualification_files or {},
        ocr_results=payload.ocr_results or [],
        remark=payload.remark,
        operator_id=user.id,
        created_by=user.id,
    )
    db.add(app)
    db.flush()
    from app.services.shop.onboarding_review_service import append_review_log

    append_review_log(
        db,
        application=app,
        action="submitted",
        summary="管家代建",
        operator=user,
    )
    if app.ocr_results:
        append_review_log(
            db,
            application=app,
            action="ocr_completed",
            summary="证件识别完成",
            operator=user,
        )
    db.commit()
    db.refresh(app)
    return _to_out(app)


def search_onboarding_tenant_options(
    db: Session,
    *,
    user: User | None = None,
    q: str | None = None,
    limit: int = 20,
) -> TenantOnboardingSearchResponse:
    merchant_tenant_ids = select(ShopMerchantAccount.tenant_id)
    pending_tenant_ids = select(ShopOnboardingApplication.tenant_id).where(
        ShopOnboardingApplication.status == "pending"
    )
    tenant_q = (
        db.query(Tenant)
        .filter(~Tenant.id.in_(merchant_tenant_ids))
        .filter(~Tenant.id.in_(pending_tenant_ids))
        .filter(Tenant.is_active.is_(True))
    )
    if user is not None:
        perms = set(get_platform_shop_permissions(user))
        if "platform.shop.merchant.list_all" not in perms:
            assigned_ids = select(ShopTenantProspectAssignment.tenant_id).where(
                uuid_eq(ShopTenantProspectAssignment.account_manager_user_id, user.id)
            )
            tenant_q = tenant_q.filter(Tenant.id.in_(assigned_ids))
    if q:
        like = f"%{q.strip()}%"
        tenant_q = tenant_q.filter(or_(Tenant.name.ilike(like), Tenant.credit_code.ilike(like)))
    tenants = tenant_q.order_by(Tenant.created_at.desc()).limit(limit).all()
    items = [
        TenantOnboardingOption(
            tenant_id=t.id,
            tenant_name=t.name,
            credit_code=t.credit_code,
            legal_name_prefill=t.name,
        )
        for t in tenants
    ]
    return TenantOnboardingSearchResponse(items=items, total=len(items))


def get_onboarding_prefill(db: Session, tenant_id: UUID) -> OnboardingPrefillResponse:
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租户不存在")
    return OnboardingPrefillResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        legal_name=tenant.name,
        display_name=tenant.name,
        unified_social_credit_code=tenant.credit_code,
    )


def assert_self_onboarding_admin(ctx) -> None:
    """A20 写操作：未入驻无 shop.*，不走 require_permission。

    未入驻：企业管理员（admin）自申。已入驻：店铺管理员亦可补材料/OCR（驳回重提）。
    店员/内容/客服不可写。对照 #a20 · 05 角色权限。
    """
    _assert_tenant_admin(ctx)


def _assert_tenant_admin(ctx) -> None:
    role = getattr(ctx.membership, "role", None)
    code = getattr(role, "code", None)
    if role is not None and role.is_system and code in {SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_SHOP_ADMIN}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅企业管理员可办理入驻")


def get_merchant_onboarding_status(db: Session, ctx) -> MerchantOnboardingStatusResponse:
    tenant_id = ctx.membership.tenant_id
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if merchant:
        return MerchantOnboardingStatusResponse(
            state="onboarded",
            merchant_id=merchant.id,
            merchant_status=merchant.status,
            application=None,
            prefill=None,
        )

    latest = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id))
        .order_by(ShopOnboardingApplication.submitted_at.desc())
        .first()
    )
    prefill = get_onboarding_prefill(db, tenant_id)
    # 自申预填：legal_name 须手填/OCR，不自动写入执照名（PRD §2.1.0）
    prefill.legal_name = ""

    if latest and latest.status == "pending":
        return MerchantOnboardingStatusResponse(
            state="reviewing",
            application=_to_summary(latest),
            prefill=prefill,
        )
    if latest and latest.status == "rejected":
        return MerchantOnboardingStatusResponse(
            state="rejected",
            application=_to_summary(latest),
            prefill=prefill,
        )
    return MerchantOnboardingStatusResponse(state="not_onboarded", application=None, prefill=prefill)


def create_merchant_self_onboarding(
    db: Session,
    ctx,
    payload: MerchantSelfOnboardingCreate,
) -> OnboardingApplicationOut:
    _assert_tenant_admin(ctx)
    _validate_mobile(payload.contact_mobile)
    _validate_entity_fields(payload)
    _validate_merchant_self_materials(payload.entity_type, payload.qualification_files or {})
    tenant_id = ctx.membership.tenant_id
    tenant = assert_tenant_eligible_for_onboarding(db, tenant_id)

    display = (payload.display_name or tenant.name).strip()
    app = ShopOnboardingApplication(
        tenant_id=tenant_id,
        application_no=generate_platform_number(db, "shop_onboarding"),
        entity_type=payload.entity_type,
        initiator="merchant_self",
        status="pending",
        legal_name=payload.legal_name.strip(),
        display_name=display,
        contact_name=payload.contact_name.strip(),
        contact_mobile=payload.contact_mobile.strip(),
        id_no=(payload.id_no or "").strip() or None,
        unified_social_credit_code=(payload.unified_social_credit_code or "").strip() or None,
        legal_rep_name=(payload.legal_rep_name or "").strip() or None,
        bank_account_info=payload.bank_account_info or {},
        qualification_files=payload.qualification_files or {},
        ocr_results=payload.ocr_results or [],
        remark=payload.remark,
        operator_id=None,
        created_by=ctx.user.id,
    )
    db.add(app)
    db.flush()
    from app.services.shop.onboarding_review_service import append_review_log

    append_review_log(
        db,
        application=app,
        action="submitted",
        summary="商家自申",
        operator=ctx.user,
    )
    if app.ocr_results:
        append_review_log(
            db,
            application=app,
            action="ocr_completed",
            summary="证件识别完成",
            operator=ctx.user,
        )
    db.commit()
    db.refresh(app)
    return _to_out(app)


def resubmit_merchant_self_onboarding(
    db: Session,
    ctx,
    application_id: UUID,
    payload: MerchantSelfOnboardingCreate,
) -> OnboardingApplicationOut:
    _assert_tenant_admin(ctx)
    _validate_mobile(payload.contact_mobile)
    _validate_entity_fields(payload)
    _validate_merchant_self_materials(payload.entity_type, payload.qualification_files or {})
    tenant_id = ctx.membership.tenant_id
    app = (
        db.query(ShopOnboardingApplication)
        .filter(
            uuid_eq(ShopOnboardingApplication.id, application_id),
            uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id),
        )
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="申请不存在")
    if app.status != "rejected":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅已驳回申请可重提")

    pending = (
        db.query(ShopOnboardingApplication)
        .filter(
            uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id),
            ShopOnboardingApplication.status == "pending",
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该租户已有待审入驻申请")

    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    display = (payload.display_name or (tenant.name if tenant else payload.legal_name)).strip()
    now = datetime.now(timezone.utc)
    # SQLite UUID 主键偶发 ORM 身份映射与落库格式不一致 → filter update 避免 StaleDataError
    n = (
        db.query(ShopOnboardingApplication)
        .filter(
            uuid_eq(ShopOnboardingApplication.id, application_id),
            uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id),
            ShopOnboardingApplication.status == "rejected",
        )
        .update(
            {
                "entity_type": payload.entity_type,
                "legal_name": payload.legal_name.strip(),
                "display_name": display,
                "contact_name": payload.contact_name.strip(),
                "contact_mobile": payload.contact_mobile.strip(),
                "id_no": (payload.id_no or "").strip() or None,
                "unified_social_credit_code": (payload.unified_social_credit_code or "").strip() or None,
                "legal_rep_name": (payload.legal_rep_name or "").strip() or None,
                "bank_account_info": payload.bank_account_info or {},
                "qualification_files": payload.qualification_files or {},
                "ocr_results": payload.ocr_results or [],
                "remark": payload.remark,
                "status": "pending",
                "reject_code": None,
                "reject_reason": None,
                "reviewed_by": None,
                "reviewed_at": None,
                "submitted_at": now,
                "created_by": ctx.user.id,
            },
            synchronize_session=False,
        )
    )
    if not n:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="申请状态已变更，无法重提")
    db.commit()
    db.expire_all()
    app = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.id, application_id))
        .first()
    )
    from app.services.shop.onboarding_review_service import append_review_log

    append_review_log(
        db,
        application=app,
        action="resubmitted",
        summary="商家重提",
        operator=ctx.user,
    )
    if app and app.ocr_results:
        append_review_log(
            db,
            application=app,
            action="ocr_completed",
            summary="证件识别完成",
            operator=ctx.user,
        )
    db.commit()
    return _to_out(app)
