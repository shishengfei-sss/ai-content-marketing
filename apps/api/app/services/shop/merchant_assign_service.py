"""P02-E 分配管家 · P02-B-T 商家标签。对照 06#p02e · #p02b-tags。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import User
from app.models.shop import (
    ShopMerchantAccount,
    ShopMerchantServiceLog,
    ShopMerchantTag,
    ShopMerchantTagLink,
    ShopOnboardingApplication,
    ShopTenantProspectAssignment,
)
from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
from app.schemas.shop_platform import (
    MerchantAssignRequest,
    MerchantBatchAssignRequest,
    MerchantBatchAssignResponse,
    MerchantTagsPutRequest,
    MerchantTagsPutResponse,
    PlatformMerchantDetailResponse,
    ShopCsUserItem,
    ShopCsUserListResponse,
    ShopMerchantTagItem,
    ShopMerchantTagListResponse,
)
from app.services.platform_shop_service import user_has_platform_shop_permission
from app.services.shop.merchant_service import assert_can_read_merchant_tenant, get_platform_merchant_detail

COMMON_TAG_NAMES = ("续费意向", "高价值", "需回访", "华东区", "对公客户")
_MAX_TAGS = 20
_ASSIGNABLE_STATUSES = frozenset({"active", "suspended", "not_onboarded"})


def _user_label(user: User | None) -> str:
    if user is None:
        return "未分配"
    return (user.display_name or user.phone or str(user.id)).strip() or str(user.id)


def _is_cs_user(user: User | None) -> bool:
    return bool(
        user
        and user.is_active
        and user.role == PLATFORM_ADMIN_ROLE
        and user.platform_shop_role == PLATFORM_SHOP_ROLE_CS
    )


def _tag_item(tag: ShopMerchantTag) -> ShopMerchantTagItem:
    return ShopMerchantTagItem(
        id=tag.id,
        name=tag.name,
        color=tag.color or "blue",
        usage_count=tag.usage_count or 0,
        is_archived=bool(tag.is_archived),
        is_common=tag.name in COMMON_TAG_NAMES,
    )


def _merchant_tag_payload(db: Session, merchant_id: UUID) -> tuple[list[str], list[ShopMerchantTagItem]]:
    rows = (
        db.query(ShopMerchantTag)
        .join(ShopMerchantTagLink, ShopMerchantTagLink.tag_id == ShopMerchantTag.id)
        .filter(uuid_eq(ShopMerchantTagLink.merchant_id, merchant_id))
        .order_by(ShopMerchantTag.name.asc())
        .all()
    )
    items = [_tag_item(t) for t in rows]
    return [t.name for t in rows], items


def tag_names_by_merchant_ids(db: Session, merchant_ids: list[UUID]) -> dict[UUID, list[str]]:
    if not merchant_ids:
        return {}
    rows = (
        db.query(ShopMerchantTagLink.merchant_id, ShopMerchantTag.name)
        .join(ShopMerchantTag, ShopMerchantTag.id == ShopMerchantTagLink.tag_id)
        .filter(ShopMerchantTagLink.merchant_id.in_(merchant_ids))
        .order_by(ShopMerchantTag.name.asc())
        .all()
    )
    out: dict[UUID, list[str]] = {mid: [] for mid in merchant_ids}
    for merchant_id, name in rows:
        out.setdefault(merchant_id, []).append(name)
    return out


def prospect_manager_map(db: Session, tenant_ids: list[UUID] | None = None) -> dict[UUID, tuple[UUID, str]]:
    q = db.query(ShopTenantProspectAssignment, User).join(
        User, User.id == ShopTenantProspectAssignment.account_manager_user_id
    )
    if tenant_ids:
        q = q.filter(ShopTenantProspectAssignment.tenant_id.in_(tenant_ids))
    out: dict[UUID, tuple[UUID, str]] = {}
    for row, user in q.all():
        out[row.tenant_id] = (row.account_manager_user_id, _user_label(user))
    return out


def list_cs_users(db: Session) -> ShopCsUserListResponse:
    users = (
        db.query(User)
        .filter(
            User.role == PLATFORM_ADMIN_ROLE,
            User.platform_shop_role == PLATFORM_SHOP_ROLE_CS,
            User.is_active.is_(True),
        )
        .order_by(User.display_name.asc(), User.phone.asc())
        .all()
    )
    return ShopCsUserListResponse(
        items=[
            ShopCsUserItem(
                id=u.id,
                display_name=_user_label(u),
                phone=u.phone,
                is_active=bool(u.is_active),
            )
            for u in users
        ]
    )


def list_merchant_tags(db: Session, *, q: str | None = None) -> ShopMerchantTagListResponse:
    query = db.query(ShopMerchantTag).filter(ShopMerchantTag.is_archived.is_(False))
    if q and q.strip():
        query = query.filter(ShopMerchantTag.name.ilike(f"%{q.strip()}%"))
    rows = query.order_by(ShopMerchantTag.usage_count.desc(), ShopMerchantTag.name.asc()).all()
    return ShopMerchantTagListResponse(items=[_tag_item(t) for t in rows])


def _resolve_assign_target(db: Session, tenant_id: UUID) -> tuple[str, ShopMerchantAccount | None]:
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if merchant is not None:
        if merchant.status == "closed":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="商家状态不可分配")
        if merchant.status not in ("active", "suspended"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="商家状态不可分配")
        return merchant.status, merchant
    pending = (
        db.query(ShopOnboardingApplication)
        .filter(
            uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id),
            ShopOnboardingApplication.status == "pending",
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="商家状态不可分配")
    return "not_onboarded", None


def _current_manager_id(
    db: Session,
    merchant: ShopMerchantAccount | None,
    tenant_id: UUID,
) -> UUID | None:
    if merchant is not None:
        return merchant.account_manager_user_id
    prospect = (
        db.query(ShopTenantProspectAssignment)
        .filter(uuid_eq(ShopTenantProspectAssignment.tenant_id, tenant_id))
        .first()
    )
    return prospect.account_manager_user_id if prospect else None


def _write_assign_note(
    db: Session,
    *,
    merchant: ShopMerchantAccount | None,
    tenant_id: UUID,
    operator_id: UUID,
    old_name: str,
    new_name: str,
    remark: str | None,
) -> None:
    extra = f"。{remark.strip()}" if remark and remark.strip() else ""
    summary = f"管家改派：{old_name} → {new_name}{extra}"
    if merchant is not None:
        db.add(
            ShopMerchantServiceLog(
                merchant_id=merchant.id,
                tenant_id=tenant_id,
                type="note",
                status="logged",
                content=summary,
                payload_json={"action": "assign_manager", "from": old_name, "to": new_name},
                operator_user_id=operator_id,
            )
        )
    from app.services.shop.audit_log_service import (
        ACTION_ASSIGN,
        SOURCE_MERCHANT_LIST,
        record_merchant_audit,
    )

    record_merchant_audit(
        db,
        tenant_id=tenant_id,
        merchant_id=merchant.id if merchant is not None else None,
        action=ACTION_ASSIGN,
        summary=summary,
        source=SOURCE_MERCHANT_LIST,
        operator_user_id=operator_id,
    )


def _apply_assign(
    db: Session,
    user: User,
    tenant_id: UUID,
    payload: MerchantAssignRequest,
) -> None:
    operator_id = user.id
    status_code, merchant = _resolve_assign_target(db, tenant_id)
    if status_code not in _ASSIGNABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="商家状态不可分配")

    current_id = _current_manager_id(db, merchant, tenant_id)
    current_user = db.query(User).filter(uuid_eq(User.id, current_id)).first() if current_id else None
    old_name = _user_label(current_user) if current_user else "未分配"

    if payload.clear:
        if current_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="当前未分配管家")
        if merchant is not None:
            merchant.account_manager_user_id = None
            _write_assign_note(
                db,
                merchant=merchant,
                tenant_id=tenant_id,
                operator_id=operator_id,
                old_name=old_name,
                new_name="未分配",
                remark=payload.remark,
            )
        else:
            db.query(ShopTenantProspectAssignment).filter(
                uuid_eq(ShopTenantProspectAssignment.tenant_id, tenant_id)
            ).delete(synchronize_session=False)
        return

    new_id = payload.account_manager_user_id
    if new_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请选择新管家")
    if current_id is not None and new_id == current_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="新管家与当前管家相同")

    new_user = db.query(User).filter(uuid_eq(User.id, new_id)).first()
    if not _is_cs_user(new_user):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该账号不是商家管家")

    new_name = _user_label(new_user)
    if merchant is not None:
        merchant.account_manager_user_id = new_id
        _write_assign_note(
            db,
            merchant=merchant,
            tenant_id=tenant_id,
            operator_id=operator_id,
            old_name=old_name,
            new_name=new_name,
            remark=payload.remark,
        )
    else:
        prospect = (
            db.query(ShopTenantProspectAssignment)
            .filter(uuid_eq(ShopTenantProspectAssignment.tenant_id, tenant_id))
            .first()
        )
        if prospect is None:
            prospect = ShopTenantProspectAssignment(
                tenant_id=tenant_id,
                account_manager_user_id=new_id,
                assigned_by=user.id,
                remark=(payload.remark or "").strip() or None,
            )
            db.add(prospect)
        else:
            prospect.account_manager_user_id = new_id
            prospect.assigned_by = user.id
            if payload.remark is not None:
                prospect.remark = payload.remark.strip() or None


def assign_account_manager(
    db: Session,
    user: User,
    tenant_id: UUID,
    payload: MerchantAssignRequest,
) -> PlatformMerchantDetailResponse:
    if not user_has_platform_shop_permission(user, "platform.shop.merchant.assign"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无分配权限")
    operator_id = user.id
    _apply_assign(db, user, tenant_id, payload)
    db.commit()
    return _detail_after_write(db, operator_id, tenant_id)


def batch_assign_account_managers(
    db: Session,
    user: User,
    payload: MerchantBatchAssignRequest,
) -> MerchantBatchAssignResponse:
    """对照 #p02e 批量分配：所选须均可分配，单次 ≤50，失败不落库。"""
    if not user_has_platform_shop_permission(user, "platform.shop.merchant.assign"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无分配权限")

    seen: set[UUID] = set()
    tenant_ids: list[UUID] = []
    for tid in payload.tenant_ids or []:
        if tid in seen:
            continue
        seen.add(tid)
        tenant_ids.append(tid)
    if not tenant_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请选择商家")
    if len(tenant_ids) > 50:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="单次最多分配 50 家")

    new_user = db.query(User).filter(uuid_eq(User.id, payload.account_manager_user_id)).first()
    if not _is_cs_user(new_user):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该账号不是商家管家")

    row_payload = MerchantAssignRequest(
        account_manager_user_id=payload.account_manager_user_id,
        remark=payload.remark,
    )
    for tid in tenant_ids:
        try:
            status_code, merchant = _resolve_assign_target(db, tid)
        except HTTPException as exc:
            db.rollback()
            if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="所选含不可分配商家",
                ) from exc
            raise
        if status_code not in _ASSIGNABLE_STATUSES:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="所选含不可分配商家",
            )
        current_id = _current_manager_id(db, merchant, tid)
        if current_id == payload.account_manager_user_id:
            continue
        _apply_assign(db, user, tid, row_payload)
    db.commit()
    return MerchantBatchAssignResponse(assigned=len(tenant_ids), tenant_ids=tenant_ids)


def _detail_after_write(db: Session, operator_id: UUID, tenant_id: UUID) -> PlatformMerchantDetailResponse:
    op = db.query(User).filter(uuid_eq(User.id, operator_id)).first()
    if not op:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="操作人加载失败")
    return get_platform_merchant_detail(db, op, tenant_id)


def consume_prospect_manager_id(db: Session, tenant_id: UUID) -> UUID | None:
    """P03 通过时合并预分配并删除 prospect 行。"""
    prospect = (
        db.query(ShopTenantProspectAssignment)
        .filter(uuid_eq(ShopTenantProspectAssignment.tenant_id, tenant_id))
        .first()
    )
    if prospect is None:
        return None
    manager_id = prospect.account_manager_user_id
    db.delete(prospect)
    return manager_id


def _normalize_tag_name(raw: str) -> str:
    name = (raw or "").strip()
    if len(name) < 2 or len(name) > 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="标签名须为 2～12 字")
    return name


def put_merchant_tags(
    db: Session,
    user: User,
    tenant_id: UUID,
    payload: MerchantTagsPutRequest,
) -> MerchantTagsPutResponse:
    if not user_has_platform_shop_permission(user, "platform.shop.merchant.tag"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无打标权限")

    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if merchant is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未入驻商家不可打标")
    if merchant.status == "closed":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="清退商家只读")
    assert_can_read_merchant_tenant(db, user, tenant_id)

    create_names = [_normalize_tag_name(n) for n in payload.create_names if (n or "").strip()]
    if create_names and not user_has_platform_shop_permission(user, "platform.shop.merchant.tag.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限创建新标签")

    wanted_ids: list[UUID] = list(payload.tag_ids or [])
    for name in create_names:
        existing = db.query(ShopMerchantTag).filter(ShopMerchantTag.name == name).first()
        if existing is not None:
            if existing.is_archived:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="标签已归档")
            if existing.id not in wanted_ids:
                wanted_ids.append(existing.id)
            continue
        tag = ShopMerchantTag(name=name, color="blue", usage_count=0, created_by=user.id)
        db.add(tag)
        db.flush()
        wanted_ids.append(tag.id)

    # 去重保序
    seen: set[UUID] = set()
    unique_ids: list[UUID] = []
    for tid in wanted_ids:
        if tid in seen:
            continue
        seen.add(tid)
        unique_ids.append(tid)
    if len(unique_ids) > _MAX_TAGS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="标签过多")

    tags = (
        db.query(ShopMerchantTag).filter(ShopMerchantTag.id.in_(unique_ids)).all() if unique_ids else []
    )
    found = {t.id: t for t in tags}
    missing = [tid for tid in unique_ids if tid not in found]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="标签不存在")
    for tag in tags:
        if tag.is_archived:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="标签已归档")

    current_links = (
        db.query(ShopMerchantTagLink).filter(uuid_eq(ShopMerchantTagLink.merchant_id, merchant.id)).all()
    )
    current_ids = {link.tag_id for link in current_links}
    wanted = set(unique_ids)

    for link in current_links:
        if link.tag_id not in wanted:
            tag = db.query(ShopMerchantTag).filter(uuid_eq(ShopMerchantTag.id, link.tag_id)).first()
            if tag and tag.usage_count > 0:
                tag.usage_count -= 1
            db.delete(link)

    for tid in unique_ids:
        if tid in current_ids:
            continue
        db.add(ShopMerchantTagLink(merchant_id=merchant.id, tag_id=tid, tagged_by=user.id))
        tag = found[tid]
        tag.usage_count = (tag.usage_count or 0) + 1

    db.commit()
    names, items = _merchant_tag_payload(db, merchant.id)
    return MerchantTagsPutResponse(tags=names, tag_items=items)
