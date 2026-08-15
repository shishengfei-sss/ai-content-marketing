"""P04 平台类目与费率。对照 PRD 06-平台端UI.html #p04 · #p04d。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import User
from app.models.shop import ShopCategoryEnableApplication, ShopPlatformCategory, ShopProduct
from app.schemas.shop_platform import (
    CategoryEnableApplicationOut,
    PlatformCategoryCreateRequest,
    PlatformCategoryEnableRequest,
    PlatformCategoryOut,
    PlatformCategoryPatchRequest,
)

CODE_RE = re.compile(r"^[a-z][a-z0-9._-]{1,62}$")
SETTLEMENT_RULES = frozenset({"standard", "platform_plus_channel"})
QUAL_OPTS = ("办学许可证", "ICP备案", "其他")
APPROVER_LABEL = "平台超管（单级审批）"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fee_label(bps: int) -> str:
    return f"{bps / 100:.1f}%"


def _qual_label(items: list | None) -> str:
    arr = [str(x) for x in (items or []) if x]
    return " / ".join(arr) if arr else "—"


def _pending_map(db: Session, category_ids: list[UUID]) -> dict[UUID, UUID]:
    if not category_ids:
        return {}
    rows = (
        db.query(ShopCategoryEnableApplication)
        .filter(
            ShopCategoryEnableApplication.category_id.in_(category_ids),
            ShopCategoryEnableApplication.status == "pending",
        )
        .all()
    )
    return {r.category_id: r.id for r in rows}


def _same_level_name_exists(
    db: Session, *, parent_id: UUID | None, name: str, exclude_id: UUID | None = None
) -> bool:
    q = db.query(ShopPlatformCategory).filter(ShopPlatformCategory.name == name)
    if parent_id:
        q = q.filter(uuid_eq(ShopPlatformCategory.parent_id, parent_id))
    else:
        q = q.filter(ShopPlatformCategory.parent_id.is_(None))
    if exclude_id:
        q = q.filter(ShopPlatformCategory.id != exclude_id)
    return q.first() is not None


def _on_sale_map(db: Session, category_ids: list[UUID]) -> dict[UUID, int]:
    if not category_ids:
        return {}
    rows = (
        db.query(ShopProduct.category_id, func.count())
        .filter(
            ShopProduct.category_id.in_(category_ids),
            ShopProduct.status == "on_sale",
            ShopProduct.deleted_at.is_(None),
        )
        .group_by(ShopProduct.category_id)
        .all()
    )
    return {cid: int(n) for cid, n in rows if cid}


def _blocked_status_label(row: ShopPlatformCategory, updated_by_name: str | None) -> str | None:
    if row.status != "blocked":
        return None
    day = ""
    if row.updated_at:
        day = row.updated_at.strftime("%Y-%m-%d")
    if day and updated_by_name:
        return f"禁入（{day} 由{updated_by_name}禁用）"
    if day:
        return f"禁入（{day}）"
    return "禁入"


def _out(
    row: ShopPlatformCategory,
    *,
    updated_by_name: str | None = None,
    pending_enable_application_id: UUID | None = None,
    on_sale_ref_count: int | None = None,
) -> PlatformCategoryOut:
    status_display = "启用" if row.status == "enabled" else "禁入"
    if pending_enable_application_id:
        status_display = "启用审批中"
    return PlatformCategoryOut(
        id=row.id,
        parent_id=row.parent_id,
        name=row.name,
        code=row.code,
        code_source=row.code_source,
        platform_fee_bps=int(row.platform_fee_bps or 0),
        platform_fee_label=_fee_label(int(row.platform_fee_bps or 0)),
        settlement_rule=row.settlement_rule or "standard",
        require_qualifications=list(row.require_qualifications or []),
        require_qualifications_label=_qual_label(row.require_qualifications),
        status=row.status,
        description=row.description,
        updated_by_name=updated_by_name,
        pending_enable_application_id=pending_enable_application_id,
        on_sale_ref_count=on_sale_ref_count,
        status_display=status_display,
        blocked_status_label=_blocked_status_label(row, updated_by_name),
        created_at=row.created_at,
        updated_at=row.updated_at,
        path_label=row.name,
    )


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


def _app_out(
    db: Session,
    app: ShopCategoryEnableApplication,
    cat: ShopPlatformCategory | None = None,
) -> CategoryEnableApplicationOut:
    if cat is None:
        cat = (
            db.query(ShopPlatformCategory)
            .filter(uuid_eq(ShopPlatformCategory.id, app.category_id))
            .first()
        )
    names = _user_names(
        db,
        {app.submitted_by, app.reviewer_id, cat.updated_by if cat else None},
    )
    who = names.get(cat.updated_by) if cat and cat.updated_by else None
    blocked_note = (_blocked_status_label(cat, who) if cat else None) or "禁入"
    return CategoryEnableApplicationOut(
        id=app.id,
        category_id=app.category_id,
        category_name=cat.name if cat else None,
        category_code=cat.code if cat else None,
        category_status=cat.status if cat else None,
        status_label=blocked_note,
        proposed_platform_fee_bps=int(app.proposed_platform_fee_bps or 0),
        proposed_platform_fee_label=_fee_label(int(app.proposed_platform_fee_bps or 0)),
        proposed_require_qualifications=list(app.proposed_require_qualifications or []),
        proposed_require_qualifications_label=_qual_label(app.proposed_require_qualifications),
        reason=app.reason,
        status=app.status,
        submitted_by_name=names.get(app.submitted_by) if app.submitted_by else None,
        submitted_at=app.submitted_at,
        reviewer_name=names.get(app.reviewer_id) if app.reviewer_id else None,
        reviewed_at=app.reviewed_at,
        reject_reason=app.reject_reason,
        approver_label=APPROVER_LABEL,
    )


def _names(db: Session, rows: list[ShopPlatformCategory]) -> dict[UUID, str]:
    return _user_names(db, {r.updated_by for r in rows})


def ensure_seed_categories(db: Session) -> None:
    n = db.query(ShopPlatformCategory).count()
    if n > 0:
        return
    root = ShopPlatformCategory(
        id=uuid.uuid4(),
        parent_id=None,
        name="职业培训",
        code="cat.vocational",
        code_source="auto",
        platform_fee_bps=200,
        settlement_rule="standard",
        require_qualifications=["办学许可证", "备案"],
        status="enabled",
    )
    db.add(root)
    db.flush()
    db.add(
        ShopPlatformCategory(
            id=uuid.uuid4(),
            parent_id=root.id,
            name="销售话术",
            code="cat.vocational.sales",
            code_source="auto",
            platform_fee_bps=200,
            settlement_rule="standard",
            require_qualifications=[],
            status="enabled",
        )
    )
    db.add(
        ShopPlatformCategory(
            id=uuid.uuid4(),
            parent_id=None,
            name="企业服务",
            code="cat.enterprise",
            code_source="auto",
            platform_fee_bps=180,
            settlement_rule="standard",
            require_qualifications=[],
            status="enabled",
        )
    )
    db.add(
        ShopPlatformCategory(
            id=uuid.uuid4(),
            parent_id=None,
            name="医疗健康",
            code="cat.health",
            code_source="auto",
            platform_fee_bps=0,
            settlement_rule="standard",
            require_qualifications=[],
            status="blocked",
            description="禁入类目示例",
        )
    )
    db.commit()


def first_enabled_category_id(db: Session) -> UUID | None:
    ensure_seed_categories(db)
    row = (
        db.query(ShopPlatformCategory)
        .filter(ShopPlatformCategory.status == "enabled")
        .order_by(ShopPlatformCategory.code.asc())
        .first()
    )
    return row.id if row else None


def get_enabled_category(db: Session, category_id: UUID) -> ShopPlatformCategory:
    row = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, category_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=422, detail="请补全平台类目")
    if row.status != "enabled":
        raise HTTPException(status_code=422, detail="所选类目禁售")
    return row


def list_for_merchant(db: Session, *, status: str | None = "enabled") -> list[PlatformCategoryOut]:
    ensure_seed_categories(db)
    q = db.query(ShopPlatformCategory)
    if status:
        q = q.filter(ShopPlatformCategory.status == status)
    rows = q.order_by(ShopPlatformCategory.code.asc()).all()
    parents = {r.id: r.name for r in rows}
    missing = {r.parent_id for r in rows if r.parent_id and r.parent_id not in parents}
    if missing:
        for p in db.query(ShopPlatformCategory).filter(ShopPlatformCategory.id.in_(list(missing))).all():
            parents[p.id] = p.name
    out: list[PlatformCategoryOut] = []
    for r in rows:
        item = _out(r)
        if r.parent_id and r.parent_id in parents:
            item.path_label = f"{parents[r.parent_id]} / {r.name}"
        else:
            item.path_label = r.name
        out.append(item)
    return out


def list_admin(
    db: Session,
    *,
    status: str | None = None,
    q: str | None = None,
    parent_id: UUID | None = None,
    root_only: bool = False,
    settlement_rule: str | None = None,
    pending_enable: bool | None = None,
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PlatformCategoryOut], int]:
    ensure_seed_categories(db)
    query = db.query(ShopPlatformCategory)
    if status:
        query = query.filter(ShopPlatformCategory.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(ShopPlatformCategory.name.ilike(like), ShopPlatformCategory.code.ilike(like))
        )
    if root_only:
        query = query.filter(ShopPlatformCategory.parent_id.is_(None))
    elif parent_id:
        query = query.filter(uuid_eq(ShopPlatformCategory.parent_id, parent_id))
    if settlement_rule:
        query = query.filter(ShopPlatformCategory.settlement_rule == settlement_rule)
    if pending_enable:
        pending_ids = [
            r.category_id
            for r in db.query(ShopCategoryEnableApplication.category_id)
            .filter(ShopCategoryEnableApplication.status == "pending")
            .all()
        ]
        if pending_ids:
            query = query.filter(ShopPlatformCategory.id.in_(pending_ids))
        else:
            query = query.filter(ShopPlatformCategory.id == uuid.uuid4())
    sort_col = {
        "name": ShopPlatformCategory.name,
        "code": ShopPlatformCategory.code,
        "updated_at": ShopPlatformCategory.updated_at,
    }.get(sort_by, ShopPlatformCategory.updated_at)
    order = sort_col.asc() if sort_dir == "asc" else sort_col.desc()
    total = query.count()
    rows = query.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    names = _names(db, rows)
    ids = [r.id for r in rows]
    pending = _pending_map(db, ids)
    on_sale = _on_sale_map(db, ids)
    return [
        _out(
            r,
            updated_by_name=names.get(r.updated_by) if r.updated_by else None,
            pending_enable_application_id=pending.get(r.id),
            on_sale_ref_count=on_sale.get(r.id, 0),
        )
        for r in rows
    ], total


def get_category(db: Session, category_id: UUID) -> PlatformCategoryOut:
    row = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, category_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="类目不存在")
    names = _names(db, [row])
    pending = _pending_map(db, [row.id])
    on_sale = _on_sale_map(db, [row.id])
    return _out(
        row,
        updated_by_name=names.get(row.updated_by) if row.updated_by else None,
        pending_enable_application_id=pending.get(row.id),
        on_sale_ref_count=on_sale.get(row.id, 0),
    )


def preview_code(db: Session, *, parent_id: UUID | None, name: str) -> dict:
    """P04-A 预览下一号；走平台编码规则（不占用序号）。name 保留兼容。"""
    ensure_seed_categories(db)
    from app.services.shop import platform_number_service

    out = platform_number_service.preview_number(db, "shop_category", parent_id=parent_id)
    # 规则关闭时仍返回提示码，前端可切手工
    if not out.get("enabled"):
        out["hint"] = "编码规则已关闭，请手工填写 code"
    _ = name  # 兼容旧入参
    return out


def create_category(
    db: Session, user: User, body: PlatformCategoryCreateRequest
) -> PlatformCategoryOut:
    ensure_seed_categories(db)
    from app.services.shop import platform_number_service

    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="请填写类目名称")
    if body.platform_fee_bps < 0 or body.platform_fee_bps > 3000:
        raise HTTPException(status_code=422, detail="平台费率须在 0–30%")
    if body.settlement_rule not in SETTLEMENT_RULES:
        raise HTTPException(status_code=422, detail="分账规则无效")
    parent_id = body.parent_id
    if parent_id:
        parent = (
            db.query(ShopPlatformCategory)
            .filter(uuid_eq(ShopPlatformCategory.id, parent_id))
            .first()
        )
        if not parent:
            raise HTTPException(status_code=422, detail="父类目不存在")
    if _same_level_name_exists(db, parent_id=parent_id, name=name):
        raise HTTPException(status_code=422, detail="同层类目名称已存在")
    code_source = (body.code_source or "auto").strip().lower()
    if code_source == "auto":
        code = platform_number_service.generate_platform_number(
            db, "shop_category", parent_id=parent_id
        )
    else:
        code = (body.code or "").strip()
        if not CODE_RE.match(code):
            raise HTTPException(status_code=422, detail="类目编码格式无效")
        if db.query(ShopPlatformCategory).filter(ShopPlatformCategory.code == code).first():
            raise HTTPException(status_code=409, detail="类目 code 已存在")
    row = ShopPlatformCategory(
        id=uuid.uuid4(),
        parent_id=parent_id,
        name=name,
        code=code,
        code_source=code_source,
        platform_fee_bps=int(body.platform_fee_bps),
        settlement_rule=body.settlement_rule,
        require_qualifications=list(body.require_qualifications or []),
        status="enabled",
        description=body.description,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


def patch_category(
    db: Session, user: User, category_id: UUID, body: PlatformCategoryPatchRequest
) -> PlatformCategoryOut:
    row = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, category_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="类目不存在")
    if row.status != "enabled":
        raise HTTPException(status_code=422, detail="禁入类目请走启用审批")
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="请填写类目名称")
        if _same_level_name_exists(db, parent_id=row.parent_id, name=name, exclude_id=row.id):
            raise HTTPException(status_code=422, detail="同层类目名称已存在")
        row.name = name
    if body.platform_fee_bps is not None:
        if body.platform_fee_bps < 0 or body.platform_fee_bps > 3000:
            raise HTTPException(status_code=422, detail="平台费率须在 0–30%")
        row.platform_fee_bps = int(body.platform_fee_bps)
    if body.settlement_rule is not None:
        if body.settlement_rule not in SETTLEMENT_RULES:
            raise HTTPException(status_code=422, detail="分账规则无效")
        row.settlement_rule = body.settlement_rule
    if body.require_qualifications is not None:
        row.require_qualifications = list(body.require_qualifications)
    if body.description is not None:
        row.description = body.description
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return _out(row)


def disable_category(
    db: Session, user: User, category_id: UUID, *, reason_type: str, reason: str
) -> PlatformCategoryOut:
    row = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, category_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="类目不存在")
    if row.status != "enabled":
        raise HTTPException(status_code=422, detail="仅启用状态可禁用")
    text = (reason or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="说明至少 4 字")
    who = (user.display_name or user.phone or "").strip() or None
    on_sale = _on_sale_map(db, [category_id]).get(category_id, 0)
    (
        db.query(ShopCategoryEnableApplication)
        .filter(
            uuid_eq(ShopCategoryEnableApplication.category_id, category_id),
            ShopCategoryEnableApplication.status == "pending",
        )
        .update(
            {
                "status": "rejected",
                "reject_reason": "类目再次禁用，自动关闭审批",
                "reviewed_at": _now(),
            },
            synchronize_session=False,
        )
    )
    row.status = "blocked"
    row.description = (row.description or "") + f"\n[禁用:{reason_type}] {text}"
    row.updated_by = user.id
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _out(row, updated_by_name=who, on_sale_ref_count=int(on_sale))


def submit_enable_application(
    db: Session, user: User, category_id: UUID, body: PlatformCategoryEnableRequest
) -> CategoryEnableApplicationOut:
    """P04-D：仅 blocked 可申请；写 pending 审批单，类目仍禁入。"""
    row = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, category_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="类目不存在")
    if row.status != "blocked":
        raise HTTPException(status_code=422, detail="仅禁入可申请启用")
    text = (body.reason or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="启用理由至少 4 字")
    if body.platform_fee_bps < 0 or body.platform_fee_bps > 3000:
        raise HTTPException(status_code=422, detail="拟设费率须在 0–30%")
    existing = (
        db.query(ShopCategoryEnableApplication)
        .filter(
            uuid_eq(ShopCategoryEnableApplication.category_id, category_id),
            ShopCategoryEnableApplication.status == "pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=422, detail="已有待审启用申请")
    app = ShopCategoryEnableApplication(
        id=uuid.uuid4(),
        category_id=category_id,
        proposed_platform_fee_bps=int(body.platform_fee_bps),
        proposed_require_qualifications=list(body.require_qualifications or []),
        reason=text,
        status="pending",
        submitted_by=user.id,
        submitted_at=_now(),
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _app_out(db, app, row)


def get_enable_application(db: Session, application_id: UUID) -> CategoryEnableApplicationOut:
    app = (
        db.query(ShopCategoryEnableApplication)
        .filter(uuid_eq(ShopCategoryEnableApplication.id, application_id))
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="审批单不存在")
    return _app_out(db, app)


def list_enable_applications(
    db: Session,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[CategoryEnableApplicationOut], int]:
    q = db.query(ShopCategoryEnableApplication)
    if status:
        q = q.filter(ShopCategoryEnableApplication.status == status)
    total = q.count()
    rows = (
        q.order_by(ShopCategoryEnableApplication.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_app_out(db, r) for r in rows], total


def approve_enable_application(
    db: Session, user: User, application_id: UUID
) -> CategoryEnableApplicationOut:
    """审批通过 → 写 enabled + 拟设费率/资质。"""
    app = (
        db.query(ShopCategoryEnableApplication)
        .filter(uuid_eq(ShopCategoryEnableApplication.id, application_id))
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="审批单不存在")
    if app.status != "pending":
        raise HTTPException(status_code=422, detail="仅待审可通过")
    row = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, app.category_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="类目不存在")
    if row.status != "blocked":
        raise HTTPException(status_code=422, detail="类目状态已变更，无法通过")
    now = _now()
    row.status = "enabled"
    row.platform_fee_bps = int(app.proposed_platform_fee_bps or 0)
    row.require_qualifications = list(app.proposed_require_qualifications or [])
    row.description = (row.description or "") + f"\n[启用审批通过] {app.reason}"
    row.updated_by = user.id
    app.status = "approved"
    app.reviewer_id = user.id
    app.reviewed_at = now
    db.commit()
    db.refresh(app)
    return _app_out(db, app, row)


def reject_enable_application(
    db: Session, user: User, application_id: UUID, *, reject_reason: str
) -> CategoryEnableApplicationOut:
    """驳回保留禁入并记录原因。"""
    app = (
        db.query(ShopCategoryEnableApplication)
        .filter(uuid_eq(ShopCategoryEnableApplication.id, application_id))
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="审批单不存在")
    if app.status != "pending":
        raise HTTPException(status_code=422, detail="仅待审可驳回")
    text = (reject_reason or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="驳回原因至少 4 字")
    row = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, app.category_id))
        .first()
    )
    app.status = "rejected"
    app.reject_reason = text
    app.reviewer_id = user.id
    app.reviewed_at = _now()
    if row:
        row.description = (row.description or "") + f"\n[启用审批驳回] {text}"
        row.updated_by = user.id
    db.commit()
    db.refresh(app)
    return _app_out(db, app, row)


def enable_category(
    db: Session, user: User, category_id: UUID, *, reason: str, **kwargs
) -> CategoryEnableApplicationOut:
    """兼容旧名：提交审批（不再直通启用）。"""
    body = PlatformCategoryEnableRequest(
        reason=reason,
        platform_fee_bps=int(kwargs.get("platform_fee_bps", 200)),
        require_qualifications=list(kwargs.get("require_qualifications") or []),
    )
    return submit_enable_application(db, user, category_id, body)
