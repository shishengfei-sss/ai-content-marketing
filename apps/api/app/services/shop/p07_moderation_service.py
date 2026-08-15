"""P07 违规稽查。对照 PRD 06#p07 · #p07a · #p07b · #p07c · §8.14.4 · F12。"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import uuid_eq
from app.models import Tenant, User
from app.models.shop import (
    ShopChannelMapping,
    ShopMerchantAccount,
    ShopModerationCase,
    ShopOrder,
    ShopProduct,
    ShopStore,
)
from app.services.platform_shop_service import user_has_platform_shop_permission
from app.services.shop.entitlement_service import TZ_SH
from app.services.shop.platform_number_service import generate_platform_number

CASE_TYPE_LABEL = {
    "sensitive_word": "敏感词命中",
    "product_violation": "商品违规",
    "buyer_complaint": "买家投诉",
    "user_report": "用户举报",
    "external_audit": "外部审核",
    "manual": "运营巡查",
}
SOURCE_LABEL = {
    "f6_auto": "机审",
    "f7_callback": "公域拒审",
    "service_log": "服务记录",
    "buyer_report": "买家投诉",
    "ops_manual": "运营手工",
}
STATUS_LABEL = {
    "pending": "待处理",
    "processing": "处理中",
    "closed": "已结案",
}
REASON_TYPE_LABEL = {
    "false_ad": "虚假宣传",
    "prohibited": "违禁内容",
    "missing_qual": "资质缺失",
}
RESOLUTION_LABEL = {
    "off_sale": "已下架商品",
    "warned": "已警告商家",
    "false_positive": "误报无责",
    "other": "其他",
}
KIND_LABEL = {
    "chat_screenshot": "聊天截图",
    "order_snapshot": "订单快照",
    "other": "附件",
}
ATTACHMENT_MEDIA = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".json": "application/json",
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^\w.\u4e00-\u9fff\-]+")
OPEN_STATUSES = ("pending", "processing")
PRODUCT_OBJECT = "product"


def _now() -> datetime:
    return datetime.now(TZ_SH)


def _month_start(now: datetime | None = None) -> datetime:
    n = now or _now()
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_SH)
    return dt.astimezone(TZ_SH).isoformat()


def _merchant_map(db: Session) -> dict[str, ShopMerchantAccount]:
    out: dict[str, ShopMerchantAccount] = {}
    for m in db.query(ShopMerchantAccount).all():
        out[str(m.tenant_id)] = m
        out[m.tenant_id.hex] = m
    return out


def _user_name(db: Session, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if not user:
        return None
    return user.display_name or user.phone or None


def _is_product_case(row: ShopModerationCase) -> bool:
    return row.object_type == PRODUCT_OBJECT and row.product_id is not None


def _append_timeline(row: ShopModerationCase, *, at: datetime, label: str) -> None:
    events = list(row.timeline_json or [])
    events.append({"at": _iso(at), "label": label})
    row.timeline_json = events


def _timeline(row: ShopModerationCase, db: Session) -> list[dict]:
    events = list(row.timeline_json or [])
    if events:
        return events
    out: list[dict] = []
    if row.reported_at:
        out.append({"at": _iso(row.reported_at), "label": "上报"})
    if row.taken_at:
        name = _user_name(db, row.assignee_id) or "运营"
        out.append({"at": _iso(row.taken_at), "label": f"{name}接单"})
    if row.force_off_at:
        out.append({"at": _iso(row.force_off_at), "label": "强制下架"})
    if row.closed_at:
        name = _user_name(db, row.assignee_id) or "运营"
        out.append({"at": _iso(row.closed_at), "label": f"{name}结案"})
    return out


def _recent_7d_orders(db: Session, product_id: UUID | None) -> int:
    if product_id is None:
        return 0
    since = _now() - timedelta(days=7)
    q = db.query(func.count(ShopOrder.id)).filter(
        uuid_eq(ShopOrder.product_id, product_id),
        ShopOrder.paid_at.isnot(None),
        ShopOrder.paid_at >= since,
    )
    return int(q.scalar() or 0)


def _actions(row: ShopModerationCase, *, can_force_off: bool) -> dict:
    product = _is_product_case(row)
    pending = row.status == "pending"
    processing = row.status == "processing"
    return {
        "force_off": pending and product and can_force_off,
        "take": pending and not product,
        "close": processing,
        "view": True,
    }


def _case_out(
    db: Session,
    row: ShopModerationCase,
    *,
    merchants: dict | None = None,
    can_force_off: bool = False,
    detail: bool = False,
) -> dict:
    merchants = merchants or _merchant_map(db)
    m = merchants.get(str(row.tenant_id)) or merchants.get(getattr(row.tenant_id, "hex", ""))
    tenant = db.get(Tenant, row.tenant_id)
    shop = db.get(ShopStore, row.shop_id)
    name = (m.display_name if m else None) or (tenant.name if tenant else "") or (shop.name if shop else "")
    product = None
    if row.product_id:
        product = db.get(ShopProduct, row.product_id)
    payload = {
        "id": str(row.id),
        "case_no": row.case_no,
        "tenant_id": str(row.tenant_id),
        "shop_id": str(row.shop_id),
        "shop_name": shop.name if shop else None,
        "merchant_name": name,
        "case_type": row.case_type,
        "case_type_label": CASE_TYPE_LABEL.get(row.case_type, row.case_type),
        "object_type": row.object_type,
        "object_ref": row.object_ref,
        "product_id": str(row.product_id) if row.product_id else None,
        "order_id": str(row.order_id) if row.order_id else None,
        "source": row.source,
        "source_label": SOURCE_LABEL.get(row.source, row.source),
        "status": row.status,
        "status_label": STATUS_LABEL.get(row.status, row.status),
        "assignee_id": str(row.assignee_id) if row.assignee_id else None,
        "assignee_name": _user_name(db, row.assignee_id),
        "reported_at": _iso(row.reported_at),
        "taken_at": _iso(row.taken_at),
        "force_off_at": _iso(row.force_off_at),
        "closed_at": _iso(row.closed_at),
        "is_product_case": _is_product_case(row),
        "actions": _actions(row, can_force_off=can_force_off),
    }
    if detail:
        payload.update(
            {
                "off_reason_type": row.off_reason_type,
                "off_reason_type_label": REASON_TYPE_LABEL.get(row.off_reason_type or "", None),
                "off_reason_text": row.off_reason_text,
                "resolution": row.resolution,
                "resolution_label": RESOLUTION_LABEL.get(row.resolution or "", None),
                "conclusion": row.conclusion,
                "notify_in_app": bool(row.notify_in_app),
                "notify_sms": bool(row.notify_sms),
                "attachments": _normalize_attachments(row.attachments_json),
                "timeline": _timeline(row, db),
                "product_status": product.status if product else None,
                "product_name": product.name if product else None,
                "recent_7d_order_count": _recent_7d_orders(db, row.product_id),
                "will_execute": (
                    "写强制下架 + listing blocked；暂停公域映射；已购权益保留"
                    if _is_product_case(row)
                    else None
                ),
            }
        )
    return payload


def _normalize_attachments(raw) -> list[dict]:
    out: list[dict] = []
    for item in raw or []:
        if isinstance(item, str):
            out.append(
                {
                    "file_id": None,
                    "file_name": item,
                    "kind": "other",
                    "kind_label": KIND_LABEL["other"],
                    "size": None,
                    "content_type": None,
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") if item.get("kind") in KIND_LABEL else "other"
        out.append(
            {
                "file_id": item.get("file_id"),
                "file_name": item.get("file_name") or item.get("name") or "附件",
                "kind": kind,
                "kind_label": item.get("kind_label") or KIND_LABEL[kind],
                "size": item.get("size"),
                "content_type": item.get("content_type"),
            }
        )
    return out


def _attach_root(case_id: UUID) -> Path:
    root = Path(settings.STORAGE_DIR) / "shop_moderation" / str(case_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_attachment_path(case_id: UUID, file_id: str) -> Path | None:
    fid = (file_id or "").strip()
    if not fid or ".." in fid or "/" in fid or "\\" in fid:
        return None
    root = Path(settings.STORAGE_DIR) / "shop_moderation" / str(case_id)
    if not root.is_dir():
        return None
    matches = sorted(root.glob(f"{fid}_*"))
    return matches[0] if matches else None


def attachment_media_type(path: Path) -> str:
    return ATTACHMENT_MEDIA.get(path.suffix.lower(), "application/octet-stream")


def add_attachment_bytes(
    db: Session,
    case_id: UUID,
    *,
    filename: str,
    content: bytes,
    kind: str = "chat_screenshot",
    content_type: str | None = None,
) -> dict:
    row = _get(db, case_id)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件为空")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件不能超过 10MB")
    kind_key = kind if kind in KIND_LABEL else "other"
    safe_name = _SAFE_NAME.sub("_", (filename or "file.bin").strip())[:120] or "file.bin"
    file_id = str(uuid4())
    dest = _attach_root(case_id) / f"{file_id}_{safe_name}"
    dest.write_bytes(content)
    att = {
        "file_id": file_id,
        "file_name": safe_name,
        "kind": kind_key,
        "kind_label": KIND_LABEL[kind_key],
        "size": len(content),
        "content_type": content_type,
    }
    items = list(row.attachments_json or [])
    items.append(att)
    row.attachments_json = items
    db.commit()
    db.refresh(row)
    return att


def seed_sample_attachments(db: Session, case_id: UUID) -> list[dict]:
    """验收：聊天截图 + 订单快照，详情可预览。"""
    png = add_attachment_bytes(
        db,
        case_id,
        filename="聊天截图.png",
        content=b"\x89PNG\r\n\x1a\nfake-chat",
        kind="chat_screenshot",
        content_type="image/png",
    )
    snap = add_attachment_bytes(
        db,
        case_id,
        filename="订单快照.json",
        content=b'{"order_no":"demo","status":"paid"}',
        kind="order_snapshot",
        content_type="application/json",
    )
    return [png, snap]


def _get(db: Session, case_id: UUID) -> ShopModerationCase:
    row = db.query(ShopModerationCase).filter(uuid_eq(ShopModerationCase.id, case_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    return row


def open_case_count(db: Session) -> int:
    """与 P01 open_moderation_cases 同源：pending + processing。"""
    return int(
        db.query(func.count(ShopModerationCase.id))
        .filter(ShopModerationCase.status.in_(OPEN_STATUSES))
        .scalar()
        or 0
    )


def summary_stats(db: Session) -> dict:
    month_start = _month_start()
    pending = int(
        db.query(func.count(ShopModerationCase.id))
        .filter(ShopModerationCase.status == "pending")
        .scalar()
        or 0
    )
    processing = int(
        db.query(func.count(ShopModerationCase.id))
        .filter(ShopModerationCase.status == "processing")
        .scalar()
        or 0
    )
    closed_month = int(
        db.query(func.count(ShopModerationCase.id))
        .filter(
            ShopModerationCase.status == "closed",
            ShopModerationCase.closed_at.isnot(None),
            ShopModerationCase.closed_at >= month_start,
        )
        .scalar()
        or 0
    )
    force_off_month = int(
        db.query(func.count(ShopModerationCase.id))
        .filter(
            ShopModerationCase.force_off_at.isnot(None),
            ShopModerationCase.force_off_at >= month_start,
        )
        .scalar()
        or 0
    )
    return {
        "pending_count": pending,
        "processing_count": processing,
        "closed_month_count": closed_month,
        "force_off_month_count": force_off_month,
        "open_count": pending + processing,
        "scope": "all",
    }


def _apply_filters(
    q,
    *,
    q_text: str | None,
    status_val: str | None,
    case_type: str | None,
    source: str | None,
    view: str | None,
    merchants: dict[str, ShopMerchantAccount],
):
    if view == "open":
        q = q.filter(ShopModerationCase.status.in_(OPEN_STATUSES))
    elif view == "closed_month":
        q = q.filter(
            ShopModerationCase.status == "closed",
            ShopModerationCase.closed_at.isnot(None),
            ShopModerationCase.closed_at >= _month_start(),
        )
    elif view in STATUS_LABEL:
        q = q.filter(ShopModerationCase.status == view)
    if status_val:
        q = q.filter(ShopModerationCase.status == status_val)
    if case_type:
        q = q.filter(ShopModerationCase.case_type == case_type)
    if source:
        q = q.filter(ShopModerationCase.source == source)
    needle = (q_text or "").strip()
    if needle:
        matched_tids: list[str] = []
        for m in merchants.values():
            blob = f"{m.display_name or ''}{m.legal_name or ''}"
            if needle in blob:
                matched_tids.append(str(m.tenant_id))
                matched_tids.append(m.tenant_id.hex)
        clauses = [
            ShopModerationCase.object_ref.contains(needle),
            ShopModerationCase.case_no.contains(needle),
        ]
        if matched_tids:
            clauses.append(cast(ShopModerationCase.tenant_id, String).in_(list(set(matched_tids))))
        q = q.filter(or_(*clauses))
    return q


def list_cases(
    db: Session,
    user: User,
    *,
    q: str | None = None,
    status: str | None = None,
    case_type: str | None = None,
    source: str | None = None,
    view: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str | None = None,
    sort_dir: str = "desc",
) -> dict:
    merchants = _merchant_map(db)
    query = db.query(ShopModerationCase)
    query = _apply_filters(
        query,
        q_text=q,
        status_val=status,
        case_type=case_type,
        source=source,
        view=view,
        merchants=merchants,
    )
    total = int(query.count())
    col = ShopModerationCase.reported_at
    if sort_by == "reported_at":
        col = ShopModerationCase.reported_at
    order = col.asc() if sort_dir == "asc" else col.desc()
    rows = (
        query.order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    can_force = user_has_platform_shop_permission(user, "platform.shop.product.force_off")
    items = [_case_out(db, r, merchants=merchants, can_force_off=can_force) for r in rows]
    stats = summary_stats(db)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": stats,
    }


def get_case(db: Session, user: User, case_id: UUID) -> dict:
    row = _get(db, case_id)
    can_force = user_has_platform_shop_permission(user, "platform.shop.product.force_off")
    return _case_out(db, row, can_force_off=can_force, detail=True)


def export_list_csv(
    db: Session,
    user: User,
    *,
    q: str | None = None,
    status: str | None = None,
    case_type: str | None = None,
    source: str | None = None,
    view: str | None = None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    data = list_cases(
        db,
        user,
        q=q,
        status=status,
        case_type=case_type,
        source=source,
        view=view,
        page=1,
        page_size=5000,
    )
    if raise_too_many and int(data.get("total") or 0) > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = ["工单号", "类型", "对象", "商家", "上报时间", "处理人", "状态", "结案时间"]
    col_map = {
        "case_type": ["类型"],
        "object_ref": ["对象"],
        "merchant_name": ["商家"],
        "reported_at": ["上报时间"],
        "assignee_name": ["处理人"],
        "status": ["状态"],
        "closed_at": ["结案时间"],
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
    for it in data["items"]:
        values = {
            "工单号": it.get("case_no") or "",
            "类型": it.get("case_type_label") or "",
            "对象": it.get("object_ref") or "",
            "商家": it.get("merchant_name") or "",
            "上报时间": it.get("reported_at") or "",
            "处理人": it.get("assignee_name") or "",
            "状态": it.get("status_label") or "",
            "结案时间": it.get("closed_at") or "",
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_moderation_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import ModerationExportRequest
    from app.services.shop import export_task_service

    body = body or ModerationExportRequest()
    filters = {
        "q": body.q,
        "status": body.status,
        "case_type": body.case_type,
        "source": body.source,
        "view": body.view,
        "columns": body.columns,
    }
    csv_text = export_list_csv(
        db,
        user,
        q=body.q,
        status=body.status,
        case_type=body.case_type,
        source=body.source,
        view=body.view,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_for_user(
        db,
        user,
        resource="moderation_cases",
        file_name="shop-moderation-cases.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_moderation_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "moderation_cases")


def read_moderation_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "moderation_cases")


def _new_case(
    db: Session,
    *,
    tenant_id: UUID,
    shop_id: UUID,
    case_type: str,
    object_type: str,
    object_ref: str,
    source: str,
    product_id: UUID | None = None,
    order_id: UUID | None = None,
    source_ref_id: str | None = None,
) -> ShopModerationCase:
    now = _now()
    row = ShopModerationCase(
        id=uuid4(),
        case_no=generate_platform_number(db, "moderation_case"),
        tenant_id=tenant_id,
        shop_id=shop_id,
        case_type=case_type,
        object_type=object_type,
        object_ref=(object_ref or "")[:300],
        product_id=product_id,
        order_id=order_id,
        source=source,
        source_ref_id=source_ref_id,
        status="pending",
        reported_at=now,
        attachments_json=[],
        timeline_json=[{"at": _iso(now), "label": "上报"}],
    )
    db.add(row)
    db.flush()
    return row


def ingest_from_auto_review(
    db: Session,
    *,
    product: ShopProduct,
    review_id: UUID | None,
    auto_result: str,
    auto_flags: list | None = None,
) -> ShopModerationCase | None:
    """F6：机审 flag/reject 自动建单。调用方负责 commit。"""
    if auto_result not in ("flag", "reject"):
        return None
    existing = (
        db.query(ShopModerationCase)
        .filter(
            uuid_eq(ShopModerationCase.product_id, product.id),
            ShopModerationCase.source == "f6_auto",
            ShopModerationCase.status.in_(OPEN_STATUSES),
        )
        .first()
    )
    if existing:
        return existing
    flags = auto_flags or []
    sensitive = any((f or {}).get("rule") == "sensitive_word" for f in flags)
    case_type = "sensitive_word" if sensitive or auto_result == "reject" else "product_violation"
    return _new_case(
        db,
        tenant_id=product.tenant_id,
        shop_id=product.shop_id,
        case_type=case_type,
        object_type=PRODUCT_OBJECT,
        object_ref=product.name,
        source="f6_auto",
        product_id=product.id,
        source_ref_id=str(review_id) if review_id else None,
    )


def ingest_from_external_audit(
    db: Session,
    *,
    mapping: ShopChannelMapping,
    product: ShopProduct | None,
    reject_code: str | None,
    reject_reason: str | None,
) -> ShopModerationCase | None:
    """F7：公域拒审自动建单。调用方负责 commit。"""
    existing = (
        db.query(ShopModerationCase)
        .filter(
            ShopModerationCase.source == "f7_callback",
            ShopModerationCase.source_ref_id == str(mapping.id),
            ShopModerationCase.status.in_(OPEN_STATUSES),
        )
        .first()
    )
    if existing:
        return existing
    prod = product or db.get(ShopProduct, mapping.product_id)
    if not prod:
        return None
    ref = prod.name
    if reject_code:
        ref = f"{prod.name}（{reject_code}）"
    return _new_case(
        db,
        tenant_id=mapping.tenant_id,
        shop_id=mapping.shop_id,
        case_type="external_audit",
        object_type=PRODUCT_OBJECT,
        object_ref=ref[:300],
        source="f7_callback",
        product_id=mapping.product_id,
        source_ref_id=str(mapping.id),
    )


def take_case(db: Session, user: User, case_id: UUID) -> dict:
    row = _get(db, case_id)
    if row.status != "pending":
        raise HTTPException(status_code=422, detail="仅待处理可接单")
    if _is_product_case(row):
        raise HTTPException(status_code=422, detail="商品类工单请走下架")
    now = _now()
    row.status = "processing"
    row.assignee_id = user.id
    row.taken_at = now
    name = user.display_name or user.phone or "运营"
    _append_timeline(row, at=now, label=f"{name}接单")
    can_force = user_has_platform_shop_permission(user, "platform.shop.product.force_off")
    db.commit()
    db.refresh(row)
    return _case_out(db, row, can_force_off=can_force, detail=True)


def force_off_sale(
    db: Session,
    user: User,
    case_id: UUID,
    *,
    reason_type: str | None,
    reason: str | None,
) -> dict:
    if not user_has_platform_shop_permission(user, "platform.shop.product.force_off"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无强制下架权限")
    row = _get(db, case_id)
    if row.status != "pending":
        raise HTTPException(status_code=422, detail="仅待处理可下架")
    if not _is_product_case(row):
        raise HTTPException(status_code=422, detail="非商品类工单请走结案")
    rt = (reason_type or "").strip()
    if rt not in REASON_TYPE_LABEL:
        raise HTTPException(status_code=422, detail="请选择下架原因类型")
    text = (reason or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="请填写说明")
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, row.product_id)).first()
    if not product or product.deleted_at is not None:
        raise HTTPException(status_code=422, detail="商品不存在")
    from app.services.shop.product_service import transition_product

    transition_product(product, "force_off")
    extra = dict(product.extra or {})
    extra["moderation_force_off"] = {
        "case_id": str(row.id),
        "case_no": row.case_no,
        "reason_type": rt,
        "reason": text,
    }
    product.extra = extra
    from app.services.shop import channel_service

    channel_service.block_mapped_for_moderation(
        db,
        product.id,
        operator_id=user.id,
        summary=f"违规稽查强制下架 {row.case_no}：{REASON_TYPE_LABEL[rt]} {text}",
    )
    now = _now()
    row.status = "processing"
    row.assignee_id = user.id
    row.taken_at = row.taken_at or now
    row.force_off_at = now
    row.off_reason_type = rt
    row.off_reason_text = text
    name = user.display_name or user.phone or "运营"
    _append_timeline(row, at=now, label=f"{name}强制下架")
    can_force = user_has_platform_shop_permission(user, "platform.shop.product.force_off")
    db.commit()
    db.refresh(row)
    return _case_out(db, row, can_force_off=can_force, detail=True)


def close_case(
    db: Session,
    user: User,
    case_id: UUID,
    *,
    resolution: str | None,
    conclusion: str | None,
    notify_in_app: bool = False,
    notify_sms: bool = False,
) -> dict:
    row = _get(db, case_id)
    if row.status != "processing":
        raise HTTPException(status_code=422, detail="仅处理中可结案")
    res = (resolution or "").strip()
    if res not in RESOLUTION_LABEL:
        raise HTTPException(status_code=422, detail="请选择处理结果")
    text = (conclusion or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="请填写结案说明")
    now = _now()
    row.status = "closed"
    row.assignee_id = row.assignee_id or user.id
    row.resolution = res
    row.conclusion = text
    row.notify_in_app = bool(notify_in_app)
    row.notify_sms = bool(notify_sms)
    row.closed_at = now
    name = user.display_name or user.phone or "运营"
    _append_timeline(row, at=now, label=f"{name}结案")
    can_force = user_has_platform_shop_permission(user, "platform.shop.product.force_off")
    db.commit()
    db.refresh(row)
    return _case_out(db, row, can_force_off=can_force, detail=True)


def seed_case(
    db: Session,
    *,
    tenant_id: UUID,
    shop_id: UUID,
    case_type: str,
    object_type: str,
    object_ref: str,
    source: str = "ops_manual",
    product_id: UUID | None = None,
    order_id: UUID | None = None,
    case_status: str = "pending",
) -> ShopModerationCase:
    """验收种子。"""
    row = _new_case(
        db,
        tenant_id=tenant_id,
        shop_id=shop_id,
        case_type=case_type,
        object_type=object_type,
        object_ref=object_ref,
        source=source,
        product_id=product_id,
        order_id=order_id,
    )
    if case_status != "pending":
        row.status = case_status
    db.commit()
    db.refresh(row)
    return row
