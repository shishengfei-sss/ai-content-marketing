"""入驻审核（P03）与 OCR stub。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import Tenant, User
from app.models.shop import (
    ShopMerchantAccount,
    ShopMerchantServiceLog,
    ShopOnboardingApplication,
    ShopOnboardingReviewLog,
    ShopSubscriptionPlan,
    ShopTenantProspectAssignment,
)
from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
from app.schemas.shop_platform import (
    MerchantRevealResponse,
    OnboardingApplicationDetail,
    OnboardingApplicationListItem,
    OnboardingApplicationListResponse,
    OnboardingApproveManagerOption,
    OnboardingApproveOptionsResponse,
    OnboardingApprovePlanOption,
    OnboardingApproveRequest,
    OnboardingApproveResponse,
    OnboardingRejectReasonGroup,
    OnboardingRejectReasonItem,
    OnboardingRejectReasonsResponse,
    OnboardingRejectRequest,
    OnboardingReviewLogItem,
)
from app.services.platform_shop_service import get_platform_shop_permissions, user_has_platform_shop_permission
from app.services.shop.buyer_service import mask_mobile
from app.services.shop.merchant_service import (
    _mask_bank_account,
    assert_can_read_merchant_tenant,
    mask_id_no,
)
from app.services.shop.onboarding_service import _to_out
from app.services.shop.platform_number_service import generate_platform_number
from app.services.shop.subscription_service import _default_expires, insert_subscription_row

OCR_DOC_TYPES = frozenset(
    {
        "id_card_front",
        "id_card_back",
        "legal_id_front",
        "legal_id_back",
        "business_license",
    }
)
PURCHASE_MODES = frozenset({"renew_same", "stack", "replace"})
_REVEAL_FIELDS = frozenset({"contact_mobile", "id_no", "bank_account_no"})
_REVIEW_ACTION_LABELS = {
    "submitted": "提交申请",
    "ocr_completed": "OCR 完成",
    "review_started": "开始审核",
    "approved": "通过",
    "rejected": "驳回",
    "resubmitted": "重提",
    "reveal_sensitive": "查看敏感信息",
}
_INITIATOR_SUMMARY = {
    "merchant_self": "商家自申",
    "ops_assisted": "管家代建",
    "platform": "管家代建",
}

_OCR_STUB: dict[str, dict] = {
    "id_card_front": {
        "name": "张三",
        "id_no": "110101199001011234",
        "address": "北京市东城区示例路1号",
    },
    "id_card_back": {
        "issue_authority": "北京市公安局东城分局",
        "valid_from": "2015-01-01",
        "valid_to": "2035-01-01",
    },
    "business_license": {
        "legal_name": "示例教育科技有限公司",
        "unified_social_credit_code": "91110000MA01234567",
        "legal_rep_name": "张三",
        "business_scope": "教育培训；技术服务",
    },
}

_OCR_STUB_ALIAS = {
    "legal_id_front": "id_card_front",
    "legal_id_back": "id_card_back",
}

# 对照 04-数据模型.html#enum-onboarding-reject-code（15 项 · 4 组 + 其他）
ONBOARDING_REJECT_REASON_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "材料证照",
        [
            ("incomplete_docs", "资质材料不全"),
            ("illegible_docs", "证照影像不清"),
            ("expired_docs", "证照过期/失效"),
            ("need_supplement", "需补充材料（通用补件）"),
        ],
    ),
    (
        "主体与人员",
        [
            ("entity_mismatch", "主体与证照信息不符"),
            ("wrong_entity_type", "主体类型选错"),
            ("legal_rep_mismatch", "法人/负责人信息不符"),
        ],
    ),
    (
        "联系与进件",
        [
            ("contact_invalid", "联系人信息无效"),
            ("payment_incomplete", "支付进件信息不全"),
            ("payment_mismatch", "结算信息与主体不一致"),
        ],
    ),
    (
        "平台规则",
        [
            ("duplicate_application", "重复申请"),
            ("policy_not_met", "不符合入驻政策"),
            ("category_blocked", "经营类目禁入"),
            ("risk_control", "风控审核未通过"),
        ],
    ),
    ("其他", [("other", "其他")]),
]
ONBOARDING_REJECT_CODES: frozenset[str] = frozenset(
    code for _, items in ONBOARDING_REJECT_REASON_GROUPS for code, _ in items
)


def run_onboarding_ocr(doc_type: str, file_id: str | None = None) -> dict:
    if doc_type not in OCR_DOC_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="证件类型无效")
    if not file_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传文件再识别")
    stub_key = _OCR_STUB_ALIAS.get(doc_type, doc_type)
    return {
        "doc_type": doc_type,
        "file_id": file_id,
        "fields": dict(_OCR_STUB[stub_key]),
        "confidence": 0.92,
        "stub": True,
    }


def _operator_display_name(user: User | None, *, initiator: str | None = None) -> str:
    if user is None:
        return "系统"
    name = (user.display_name or user.phone or "").strip() or "用户"
    if initiator == "merchant_self":
        return f"商家·{name}"
    role = getattr(user, "platform_shop_role", None)
    if role == PLATFORM_SHOP_ROLE_CS:
        return f"管家·{name}"
    if user.role == PLATFORM_ADMIN_ROLE:
        return f"运营·{name}"
    return name


def append_review_log(
    db: Session,
    *,
    application: ShopOnboardingApplication,
    action: str,
    summary: str,
    operator: User | None = None,
    meta: dict | None = None,
    created_at: datetime | None = None,
) -> ShopOnboardingReviewLog:
    initiator = application.initiator if action in ("submitted", "resubmitted") else None
    log = ShopOnboardingReviewLog(
        application_id=application.id,
        tenant_id=application.tenant_id,
        action=action,
        summary=summary,
        operator_id=operator.id if operator is not None else None,
        operator_name=_operator_display_name(operator, initiator=initiator),
        meta=dict(meta or {}),
    )
    if created_at is not None:
        log.created_at = created_at
    db.add(log)
    return log


def _reject_label(code: str) -> str:
    for _, items in ONBOARDING_REJECT_REASON_GROUPS:
        for c, label in items:
            if c == code:
                return label
    return code


def _log_item(row: ShopOnboardingReviewLog) -> OnboardingReviewLogItem:
    return OnboardingReviewLogItem(
        id=row.id,
        action=row.action,
        action_label=_REVIEW_ACTION_LABELS.get(row.action, row.action),
        summary=row.summary,
        operator_name=row.operator_name,
        created_at=row.created_at,
        meta=row.meta or {},
    )


def list_review_logs(db: Session, application_id: UUID) -> list[OnboardingReviewLogItem]:
    rows = (
        db.query(ShopOnboardingReviewLog)
        .filter(uuid_eq(ShopOnboardingReviewLog.application_id, application_id))
        .order_by(ShopOnboardingReviewLog.created_at.desc())
        .all()
    )
    return [_log_item(r) for r in rows]


def _ensure_submitted_log(db: Session, app: ShopOnboardingApplication) -> None:
    exists = (
        db.query(ShopOnboardingReviewLog.id)
        .filter(
            uuid_eq(ShopOnboardingReviewLog.application_id, app.id),
            ShopOnboardingReviewLog.action == "submitted",
        )
        .first()
    )
    if exists:
        return
    op = db.query(User).filter(uuid_eq(User.id, app.created_by)).first() if app.created_by else None
    append_review_log(
        db,
        application=app,
        action="submitted",
        summary=_INITIATOR_SUMMARY.get(app.initiator, app.initiator or "提交申请"),
        operator=op,
        created_at=app.submitted_at,
    )


def _maybe_mark_review_started(db: Session, user: User, app: ShopOnboardingApplication) -> None:
    if app.status != "pending":
        return
    if not user_has_platform_shop_permission(user, "platform.shop.approve"):
        return
    exists = (
        db.query(ShopOnboardingReviewLog.id)
        .filter(
            uuid_eq(ShopOnboardingReviewLog.application_id, app.id),
            ShopOnboardingReviewLog.action == "review_started",
        )
        .first()
    )
    if exists:
        return
    append_review_log(
        db,
        application=app,
        action="review_started",
        summary="运营打开入驻审核",
        operator=user,
    )


def _mask_application_payload(app: ShopOnboardingApplication, dumped: dict) -> dict:
    dumped["contact_mobile"] = mask_mobile(app.contact_mobile)
    dumped["id_no"] = mask_id_no(app.id_no)
    bank, display = _mask_bank_account(app.bank_account_info)
    dumped["bank_account_info"] = bank
    dumped["bank_account_display"] = display
    return dumped


def _assert_can_reveal_application(db: Session, user: User, tenant_id: UUID) -> None:
    perms = set(get_platform_shop_permissions(user))
    if not perms.intersection({"platform.shop.merchant.read", "platform.shop.approve"}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无查看权限")
    try:
        assert_can_read_merchant_tenant(db, user, tenant_id)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无查看权限") from None


def reveal_onboarding_sensitive(
    db: Session,
    user: User,
    application_id: UUID,
    field: str | None,
) -> MerchantRevealResponse:
    row = (
        db.query(ShopOnboardingApplication).filter(uuid_eq(ShopOnboardingApplication.id, application_id)).first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="入驻申请不存在")
    _assert_can_reveal_application(db, user, row.tenant_id)
    key = (field or "contact_mobile").strip()
    if key not in _REVEAL_FIELDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="字段无效")
    if key == "contact_mobile":
        raw = row.contact_mobile
        summary = "查看经营联系人手机"
    elif key == "id_no":
        raw = row.id_no
        if not raw:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该主体无身份证号")
        summary = "查看身份证号"
    else:
        info = dict(row.bank_account_info or {})
        raw = str(info.get("account_no") or info.get("account") or "").strip()
        if not raw:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该主体无对公账号")
        summary = "查看对公账号"
    if not raw:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="无可揭露字段")
    append_review_log(
        db,
        application=row,
        action="reveal_sensitive",
        summary=summary,
        operator=user,
        meta={"field": key},
    )
    db.commit()
    return MerchantRevealResponse(field=key, value=raw)


def _can_view_onboarding_applications(user: User) -> bool:
    from app.services.platform_shop_service import user_has_platform_shop_permission

    return any(
        user_has_platform_shop_permission(user, code)
        for code in (
            "platform.shop.approve",
            "platform.shop.onboarding.initiate",
            "platform.shop.merchant.read",
        )
    )


def list_onboarding_reject_reasons() -> OnboardingRejectReasonsResponse:
    groups: list[OnboardingRejectReasonGroup] = []
    flat: list[OnboardingRejectReasonItem] = []
    for group_name, items in ONBOARDING_REJECT_REASON_GROUPS:
        group_items = [OnboardingRejectReasonItem(code=c, label=l) for c, l in items]
        groups.append(OnboardingRejectReasonGroup(group=group_name, items=group_items))
        flat.extend(group_items)
    return OnboardingRejectReasonsResponse(groups=groups, items=flat)


def list_onboarding_approve_options(
    db: Session,
    user: User,
    *,
    entity_type: str | None = None,
) -> OnboardingApproveOptionsResponse:
    query = db.query(ShopSubscriptionPlan).filter(
        ShopSubscriptionPlan.is_active.is_(True),
        ShopSubscriptionPlan.is_public.is_(True),
        ShopSubscriptionPlan.plan_type == "main",
    )
    plans_out: list[OnboardingApprovePlanOption] = []
    for row in query.order_by(ShopSubscriptionPlan.sort_order.asc(), ShopSubscriptionPlan.name.asc()).all():
        allowed = list(row.allowed_entity_types or [])
        if entity_type and allowed and entity_type not in allowed:
            continue
        plans_out.append(
            OnboardingApprovePlanOption(
                id=row.id,
                code=row.code,
                name=row.name,
                allowed_entity_types=allowed,
            )
        )

    cs_users = (
        db.query(User)
        .filter(
            User.role == PLATFORM_ADMIN_ROLE,
            User.platform_shop_role == PLATFORM_SHOP_ROLE_CS,
            User.is_active.is_(True),
        )
        .order_by(User.display_name.asc())
        .all()
    )
    seen: set = {u.id for u in cs_users}
    managers: list[OnboardingApproveManagerOption] = [
        OnboardingApproveManagerOption(
            id=u.id,
            display_name=u.display_name or u.phone or str(u.id),
            platform_shop_role=u.platform_shop_role,
            is_current=u.id == user.id,
        )
        for u in cs_users
    ]
    if user.id not in seen:
        managers.insert(
            0,
            OnboardingApproveManagerOption(
                id=user.id,
                display_name=user.display_name or user.phone or "当前审核人",
                platform_shop_role=getattr(user, "platform_shop_role", None),
                is_current=True,
            ),
        )
    else:
        managers.sort(key=lambda m: (not m.is_current, m.display_name))
    return OnboardingApproveOptionsResponse(
        plans=plans_out,
        managers=managers,
        default_manager_user_id=user.id,
    )


def _application_list_item(
    app: ShopOnboardingApplication,
    tenant: Tenant,
    reviewer_name: str | None = None,
    merchant_no: str | None = None,
) -> OnboardingApplicationListItem:
    return OnboardingApplicationListItem(
        id=app.id,
        application_no=app.application_no,
        tenant_id=app.tenant_id,
        tenant_name=tenant.name,
        display_name=app.display_name or app.legal_name or tenant.name,
        legal_name=app.legal_name,
        entity_type=app.entity_type,
        initiator=app.initiator,
        status=app.status,
        contact_name=app.contact_name,
        contact_mobile=mask_mobile(app.contact_mobile) or "",
        submitted_at=app.submitted_at,
        reviewed_at=app.reviewed_at,
        reviewer_name=reviewer_name,
        merchant_id=app.merchant_id,
        merchant_code=merchant_no,
    )


_ONBOARDING_SORT_FIELDS = frozenset({"display_name", "submitted_at"})


def list_onboarding_applications(
    db: Session,
    user: User,
    *,
    q: str | None = None,
    status_filter: str | None = None,
    entity_type: str | None = None,
    initiator: str | None = None,
    submitted_from: date | None = None,
    submitted_until: date | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> OnboardingApplicationListResponse:
    if not _can_view_onboarding_applications(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无入驻申请查看权限")

    query = (
        db.query(ShopOnboardingApplication, Tenant)
        .join(Tenant, ShopOnboardingApplication.tenant_id == Tenant.id)
    )
    if status_filter:
        query = query.filter(ShopOnboardingApplication.status == status_filter)
    if entity_type:
        query = query.filter(ShopOnboardingApplication.entity_type == entity_type)
    if initiator == "merchant_self":
        query = query.filter(ShopOnboardingApplication.initiator == "merchant_self")
    elif initiator in ("platform", "ops_assisted"):
        query = query.filter(ShopOnboardingApplication.initiator.in_(("platform", "ops_assisted")))
    if submitted_from:
        query = query.filter(
            ShopOnboardingApplication.submitted_at
            >= datetime.combine(submitted_from, datetime.min.time(), tzinfo=timezone.utc)
        )
    if submitted_until:
        query = query.filter(
            ShopOnboardingApplication.submitted_at
            < datetime.combine(submitted_until, datetime.min.time(), tzinfo=timezone.utc)
            + timedelta(days=1)
        )
    if q:
        like = f"%{q.strip()}%"
        merchant_no_subq = db.query(ShopMerchantAccount.id).filter(
            ShopMerchantAccount.merchant_no.ilike(like)
        )
        query = query.filter(
            or_(
                ShopOnboardingApplication.display_name.ilike(like),
                ShopOnboardingApplication.legal_name.ilike(like),
                ShopOnboardingApplication.application_no.ilike(like),
                Tenant.name.ilike(like),
                ShopOnboardingApplication.merchant_id.in_(merchant_no_subq),
            )
        )

    field = sort_by if sort_by in _ONBOARDING_SORT_FIELDS else "submitted_at"
    reverse = (sort_dir or "desc").lower() != "asc"
    if field == "display_name":
        col = ShopOnboardingApplication.display_name
    else:
        col = ShopOnboardingApplication.submitted_at
    query = query.order_by(col.desc() if reverse else col.asc())

    rows = query.all()
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    reviewer_ids = {app.reviewed_by for app, _ in page_rows if app.reviewed_by}
    reviewer_map: dict = {}
    if reviewer_ids:
        for u in db.query(User).filter(User.id.in_(list(reviewer_ids))).all():
            reviewer_map[u.id] = u.display_name or u.phone or str(u.id)

    merchant_ids = [app.merchant_id for app, _ in page_rows if app.merchant_id]
    merchant_no_map: dict = {}
    if merchant_ids:
        for m in db.query(ShopMerchantAccount).filter(ShopMerchantAccount.id.in_(list(merchant_ids))).all():
            merchant_no_map[m.id] = m.merchant_no

    items = [
        _application_list_item(
            app,
            tenant,
            reviewer_map.get(app.reviewed_by) if app.reviewed_by else None,
            merchant_no_map.get(app.merchant_id) if app.merchant_id else None,
        )
        for app, tenant in page_rows
    ]
    return OnboardingApplicationListResponse(items=items, total=total, page=page, page_size=page_size)


def get_onboarding_application_detail(
    db: Session,
    user: User,
    application_id: UUID,
    *,
    check_perm: bool = True,
) -> OnboardingApplicationDetail:
    if check_perm and not _can_view_onboarding_applications(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无入驻申请查看权限")

    row = (
        db.query(ShopOnboardingApplication, Tenant)
        .join(Tenant, ShopOnboardingApplication.tenant_id == Tenant.id)
        .filter(uuid_eq(ShopOnboardingApplication.id, application_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="入驻申请不存在")
    app, tenant = row
    _ensure_submitted_log(db, app)
    _maybe_mark_review_started(db, user, app)
    db.commit()
    base = _to_out(app)
    dumped = _mask_application_payload(app, base.model_dump())
    merchant_no = None
    if app.merchant_id:
        merchant = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.id, app.merchant_id))
            .first()
        )
        merchant_no = merchant.merchant_no if merchant else None
    return OnboardingApplicationDetail(
        **dumped,
        tenant_name=tenant.name,
        reject_code=app.reject_code,
        reject_reason=app.reject_reason,
        reviewed_by=app.reviewed_by,
        reviewed_at=app.reviewed_at,
        merchant_id=app.merchant_id,
        merchant_code=merchant_no,
        review_logs=list_review_logs(db, app.id),
    )


def _assert_pending_application(app: ShopOnboardingApplication) -> None:
    if app.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅待审申请可审核")


def reject_onboarding_application(
    db: Session,
    user: User,
    application_id: UUID,
    payload: OnboardingRejectRequest,
) -> OnboardingApplicationDetail:
    reason = (payload.reject_reason or "").strip()
    if len(reason) < 4:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请填写驳回原因（至少4字）")
    code = (payload.reject_code or "").strip()
    if code not in ONBOARDING_REJECT_CODES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="驳回原因码无效")

    app = db.query(ShopOnboardingApplication).filter(uuid_eq(ShopOnboardingApplication.id, application_id)).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="入驻申请不存在")
    _assert_pending_application(app)

    now = datetime.now(timezone.utc)
    # SQLite UUID 主键偶发 ORM 身份映射与落库格式不一致 → 用 filter update 避免 StaleDataError
    n = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.id, application_id))
        .filter(ShopOnboardingApplication.status == "pending")
        .update(
            {
                "status": "rejected",
                "reject_code": code,
                "reject_reason": reason,
                "reviewed_by": user.id,
                "reviewed_at": now,
            },
            synchronize_session=False,
        )
    )
    if not n:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="申请状态已变更，无法驳回")
    append_review_log(
        db,
        application=app,
        action="rejected",
        summary=f"原因码={code}（{_reject_label(code)}）",
        operator=user,
        meta={"reject_code": code},
    )
    db.commit()
    return get_onboarding_application_detail(db, user, application_id, check_perm=False)


def _resolve_first_plan(
    db: Session,
    app: ShopOnboardingApplication,
    payload: OnboardingApproveRequest,
) -> ShopSubscriptionPlan:
    plan = None
    if payload.plan_id:
        plan = (
            db.query(ShopSubscriptionPlan)
            .filter(uuid_eq(ShopSubscriptionPlan.id, payload.plan_id))
            .first()
        )
    elif (payload.plan_label or "").strip():
        plan = (
            db.query(ShopSubscriptionPlan)
            .filter(
                ShopSubscriptionPlan.name == payload.plan_label.strip(),
                ShopSubscriptionPlan.is_active.is_(True),
                ShopSubscriptionPlan.is_public.is_(True),
                ShopSubscriptionPlan.plan_type == "main",
            )
            .first()
        )
    if plan is None:
        rows = (
            db.query(ShopSubscriptionPlan)
            .filter(
                ShopSubscriptionPlan.is_active.is_(True),
                ShopSubscriptionPlan.is_public.is_(True),
                ShopSubscriptionPlan.plan_type == "main",
            )
            .order_by(ShopSubscriptionPlan.sort_order.asc(), ShopSubscriptionPlan.name.asc())
            .all()
        )
        for row in rows:
            allowed = list(row.allowed_entity_types or [])
            if allowed and app.entity_type not in allowed:
                continue
            plan = row
            break
    if not plan or not plan.is_active or not plan.is_public:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="套餐未上架")
    if plan.plan_type != "main":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="首开须为主套餐")
    allowed = list(plan.allowed_entity_types or [])
    if allowed and app.entity_type not in allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="主体不可购")
    return plan


def approve_onboarding_application(
    db: Session,
    user: User,
    application_id: UUID,
    payload: OnboardingApproveRequest,
) -> OnboardingApproveResponse:
    app = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.id, application_id))
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="入驻申请不存在")
    _assert_pending_application(app)

    plan = _resolve_first_plan(db, app, payload)
    plan_label = plan.name

    existing = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, app.tenant_id)).first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该租户已入驻")

    today = date.today()
    benefits_from = payload.benefits_from or today
    benefits_until = payload.benefits_until
    if benefits_until is None and payload.trial_days:
        benefits_until = benefits_from + timedelta(days=payload.trial_days)
    if benefits_until is None:
        benefits_until = _default_expires(plan, benefits_from)

    manager_id = payload.account_manager_user_id
    if manager_id is None:
        prospect = (
            db.query(ShopTenantProspectAssignment)
            .filter(uuid_eq(ShopTenantProspectAssignment.tenant_id, app.tenant_id))
            .first()
        )
        if prospect is not None:
            manager_id = prospect.account_manager_user_id
        else:
            manager_id = user.id
    manager = db.query(User).filter(uuid_eq(User.id, manager_id)).first()
    if not manager or manager.role != PLATFORM_ADMIN_ROLE or not manager.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="商家管家无效")
    now = datetime.now(timezone.utc)

    merchant = ShopMerchantAccount(
        tenant_id=app.tenant_id,
        merchant_no=generate_platform_number(db, "shop_merchant"),
        onboarding_application_id=app.id,
        entity_type=app.entity_type,
        legal_name=app.legal_name,
        display_name=app.display_name,
        contact_name=app.contact_name,
        contact_mobile=app.contact_mobile,
        id_no=app.id_no,
        unified_social_credit_code=app.unified_social_credit_code,
        legal_rep_name=app.legal_rep_name,
        status="active",
        onboarding_approved_at=now,
        account_manager_user_id=manager_id,
        plan_label=plan_label,
        plan_status="active",
        benefits_until=benefits_until,
        store_count_active=0,
        store_quota=payload.store_quota,
        has_pending_renewal=False,
    )
    db.add(merchant)
    db.flush()

    from app.services.shop.audit_log_service import (
        ACTION_ONBOARD,
        SOURCE_ONBOARDING,
        record_merchant_audit,
    )

    record_merchant_audit(
        db,
        tenant_id=app.tenant_id,
        merchant_id=merchant.id,
        action=ACTION_ONBOARD,
        summary=f"创建商家 · 首开{plan_label}",
        source=SOURCE_ONBOARDING,
        operator=user,
    )

    source = "trial" if payload.trial_days else "manual"
    sub = insert_subscription_row(
        db,
        merchant=merchant,
        plan=plan,
        user=user,
        effective=benefits_from,
        expires=benefits_until,
        source=source,
        purchase_mode="stack",
        paid_amount_cents=0,
        remark="入驻首开试用" if source == "trial" else "入驻首开",
    )

    app.status = "approved"
    app.merchant_id = merchant.id
    app.reviewed_by = user.id
    app.reviewed_at = now

    db.add(
        ShopMerchantServiceLog(
            merchant_id=merchant.id,
            tenant_id=app.tenant_id,
            type="onboarding_assist",
            status="completed",
            content=f"入驻审核通过，首开套餐：{plan_label}（{sub.subscription_no}）",
            payload_json={
                "application_id": str(app.id),
                "plan_id": str(plan.id),
                "plan_label": plan_label,
                "subscription_id": str(sub.id),
                "subscription_no": sub.subscription_no,
                "benefits_from": benefits_from.isoformat(),
                "benefits_until": benefits_until.isoformat() if benefits_until else None,
            },
            operator_user_id=user.id,
            related_onboarding_id=app.id,
            related_subscription_id=sub.id,
        )
    )
    db.query(ShopTenantProspectAssignment).filter(
        uuid_eq(ShopTenantProspectAssignment.tenant_id, app.tenant_id)
    ).delete(synchronize_session=False)
    append_review_log(
        db,
        application=app,
        action="approved",
        summary=f"首开套餐={plan_label} {sub.subscription_no}",
        operator=user,
        meta={
            "plan_label": plan_label,
            "plan_id": str(plan.id),
            "subscription_id": str(sub.id),
            "subscription_no": sub.subscription_no,
        },
    )
    db.commit()
    db.refresh(merchant)

    return OnboardingApproveResponse(
        application_id=app.id,
        merchant_id=merchant.id,
        tenant_id=app.tenant_id,
        display_name=merchant.display_name,
        plan_label=merchant.plan_label,
        plan_status=merchant.plan_status,
        benefits_until=merchant.benefits_until,
        account_manager_user_id=merchant.account_manager_user_id,
        subscription_id=sub.id,
        subscription_no=sub.subscription_no,
    )
