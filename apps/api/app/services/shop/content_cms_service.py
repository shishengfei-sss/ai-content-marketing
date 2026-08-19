"""A04–A06 专栏 / 课时 / 资料包 CMS。对照 PRD #a04 #a05 #a06。"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from html import unescape
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.services.shop.export_limits import SHOP_EXPORT_ROW_LIMIT, assert_export_within_limit
from app.models.shop import (
    ShopColumn,
    ShopDigitalAsset,
    ShopDigitalPackage,
    ShopLesson,
    ShopMerchantAccount,
    ShopProduct,
    ShopStore,
)
from app.schemas.shop_platform import (
    ColumnCreateRequest,
    ColumnExportRequest,
    ColumnOut,
    ColumnPatchRequest,
    ContentFileUploadOut,
    DigitalAssetCreateRequest,
    DigitalAssetOut,
    DigitalPackageCreateRequest,
    DigitalPackageExportRequest,
    DigitalPackageOut,
    DigitalPackagePatchRequest,
    LessonCreateRequest,
    LessonOut,
    LessonPatchRequest,
    ShopExportTaskOut,
)
from app.services.shop.product_service import ensure_default_shop

_PREVIEW_EXT = {".pdf", ".doc", ".docx"}
_ASSET_EXT = {".pdf", ".doc", ".docx", ".zip"}
_MAX_ASSET_BYTES = 50 * 1024 * 1024
_MAX_ASSETS = 20
_LESSON_VIDEO_EXT = {".mp4", ".mov"}
_LESSON_AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav"}
_ARTICLE_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif"}
_MAX_LESSON_VIDEO_BYTES = 2 * 1024 * 1024 * 1024
_MAX_LESSON_AUDIO_BYTES = 200 * 1024 * 1024
_MAX_ARTICLE_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_CONTENT_BODY_CHARS = 50_000
_MAX_ARTICLE_IMAGES = 20
_MAX_LESSON_DURATION_SEC = 180 * 60
_CONTENT_ROOT = Path(__file__).resolve().parents[3] / "storage" / "shop_content"
_COLUMN_STATUS_ZH = {"draft": "草稿", "published": "已发布", "off_sale": "已下架"}
_PACKAGE_STATUS_ZH = _COLUMN_STATUS_ZH
_DELIVER_ZH = {"download": "下载", "online_view": "在线查看"}


def _date_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _date_end_excl(d: date) -> datetime:
    return datetime.combine(d + timedelta(days=1), time.min, tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    if not m:
        raise HTTPException(status_code=404, detail="商家未入驻")
    if m.status in ("closed", "suspended"):
        raise HTTPException(status_code=422, detail="商家不可用")
    return m


def _previewable(name: str, mime: str | None) -> bool:
    lower = (name or "").lower()
    m = (mime or "").lower()
    if lower.endswith(".zip") or "zip" in m:
        return False
    return any(lower.endswith(ext) for ext in _PREVIEW_EXT) or "pdf" in m


def _file_ext(name: str) -> str:
    lower = (name or "").lower()
    i = lower.rfind(".")
    return lower[i:] if i >= 0 else ""


def _validate_lesson_upload(name: str, size: int, purpose: str | None) -> None:
    ext = _file_ext(name)
    if purpose == "lesson_video":
        if ext not in _LESSON_VIDEO_EXT:
            raise HTTPException(status_code=422, detail="视频仅支持 mp4、mov 格式")
        if size > _MAX_LESSON_VIDEO_BYTES:
            raise HTTPException(status_code=422, detail="视频单文件不能超过 2GB")
        return
    if purpose == "lesson_audio":
        if ext not in _LESSON_AUDIO_EXT:
            raise HTTPException(status_code=422, detail="音频仅支持 mp3、m4a、aac、wav 格式")
        if size > _MAX_LESSON_AUDIO_BYTES:
            raise HTTPException(status_code=422, detail="音频单文件不能超过 200MB")
        return
    if purpose == "article_image":
        if ext not in _ARTICLE_IMAGE_EXT:
            raise HTTPException(status_code=422, detail="内嵌图仅支持 jpg、png、gif 格式")
        if size > _MAX_ARTICLE_IMAGE_BYTES:
            raise HTTPException(status_code=422, detail="单张内嵌图不能超过 5MB")
        return


def _plain_text_len(body: str | None) -> int:
    text = re.sub(r"<[^>]+>", "", body or "")
    return len(unescape(text).strip())


def _article_image_count(body: str | None) -> int:
    return len(re.findall(r"<img\b", body or "", flags=re.I))


def _validate_article_body(body: str | None) -> None:
    raw = body or ""
    if len(raw) > _MAX_CONTENT_BODY_CHARS:
        raise HTTPException(status_code=422, detail="正文不能超过 50000 字")
    if _article_image_count(raw) > _MAX_ARTICLE_IMAGES:
        raise HTTPException(status_code=422, detail="内嵌图不能超过 20 张")
    if _plain_text_len(raw) < 10:
        raise HTTPException(status_code=422, detail="图文正文至少 10 字")


def _validate_lesson_media(les: ShopLesson) -> None:
    if les.media_type == "article":
        _validate_article_body(les.content_body)
        return
    if not les.media_id and not les.media_url:
        raise HTTPException(status_code=422, detail="请上传媒体文件")
    if les.media_type == "video" and les.duration_sec > _MAX_LESSON_DURATION_SEC:
        raise HTTPException(status_code=422, detail="视频时长不能超过 180 分钟")


def _ref_count(db: Session, ref_type: str, ref_id: UUID) -> int:
    return (
        db.query(ShopProduct)
        .filter(
            ShopProduct.ref_type == ref_type,
            uuid_eq(ShopProduct.ref_id, ref_id),
            ShopProduct.deleted_at.is_(None),
        )
        .count()
    )


def _column_out(db: Session, c: ShopColumn) -> ColumnOut:
    lessons = (
        db.query(ShopLesson)
        .filter(uuid_eq(ShopLesson.column_id, c.id), ShopLesson.deleted_at.is_(None))
        .all()
    )
    return ColumnOut(
        id=c.id,
        tenant_id=c.tenant_id,
        shop_id=c.shop_id,
        title=c.title,
        intro=c.intro,
        status=c.status,
        lesson_count=len(lessons),
        published_lesson_count=sum(1 for x in lessons if x.status == "published"),
        ref_product_count=_ref_count(db, "column", c.id),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _lesson_out(l: ShopLesson) -> LessonOut:
    return LessonOut(
        id=l.id,
        column_id=l.column_id,
        title=l.title,
        media_type=l.media_type,
        media_id=l.media_id,
        media_url=l.media_url,
        content_body=l.content_body,
        duration_sec=l.duration_sec,
        is_trial=bool(l.is_trial),
        trial_seconds=l.trial_seconds,
        sort_order=l.sort_order,
        status=l.status,
        created_at=l.created_at,
        updated_at=l.updated_at,
    )


def _asset_out(a: ShopDigitalAsset) -> DigitalAssetOut:
    return DigitalAssetOut(
        id=a.id,
        package_id=a.package_id,
        file_id=a.file_id,
        file_name=a.file_name,
        file_url=a.file_url,
        mime=a.mime,
        size_bytes=int(a.size_bytes or 0),
        previewable=bool(a.previewable),
        sort_order=a.sort_order,
        created_at=a.created_at,
    )


def _package_out(db: Session, p: ShopDigitalPackage, *, with_assets: bool = False) -> DigitalPackageOut:
    assets = (
        db.query(ShopDigitalAsset)
        .filter(uuid_eq(ShopDigitalAsset.package_id, p.id))
        .order_by(ShopDigitalAsset.sort_order.asc())
        .all()
    )
    return DigitalPackageOut(
        id=p.id,
        tenant_id=p.tenant_id,
        shop_id=p.shop_id,
        title=p.title,
        deliver_mode=p.deliver_mode,
        max_downloads=p.max_downloads,
        status=p.status,
        file_count=len(assets),
        previewable_count=sum(1 for a in assets if a.previewable),
        ref_product_count=_ref_count(db, "digital_package", p.id),
        assets=[_asset_out(a) for a in assets] if with_assets else [],
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _get_column(db: Session, tenant_id: UUID, column_id: UUID) -> ShopColumn:
    c = (
        db.query(ShopColumn)
        .filter(
            uuid_eq(ShopColumn.id, column_id),
            uuid_eq(ShopColumn.tenant_id, tenant_id),
            ShopColumn.deleted_at.is_(None),
        )
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="专栏不存在")
    return c


def _get_package(db: Session, tenant_id: UUID, package_id: UUID) -> ShopDigitalPackage:
    p = (
        db.query(ShopDigitalPackage)
        .filter(
            uuid_eq(ShopDigitalPackage.id, package_id),
            uuid_eq(ShopDigitalPackage.tenant_id, tenant_id),
            ShopDigitalPackage.deleted_at.is_(None),
        )
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="资料包不存在")
    return p


def upload_content_file(
    db: Session, ctx: TenantContext, file: UploadFile, *, purpose: str | None = None
) -> ContentFileUploadOut:
    _merchant(db, ctx.tenant_id)
    raw_name = (file.filename or "upload.bin").strip() or "upload.bin"
    safe_name = re.sub(r"[^\w.\u4e00-\u9fff\-]+", "_", raw_name)[:180]
    data = file.file.read()
    _validate_lesson_upload(safe_name, len(data), purpose)
    file_id = str(uuid.uuid4())
    root = _CONTENT_ROOT / str(ctx.tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"{file_id}_{safe_name}"
    dest.write_bytes(data)
    mime = file.content_type or "application/octet-stream"
    url = f"/api/v1/shop/content/files/{file_id}"
    return ContentFileUploadOut(
        file_id=file_id,
        file_name=safe_name,
        file_url=url,
        mime=mime,
        size_bytes=len(data),
        previewable=_previewable(safe_name, mime),
    )


def resolve_content_file_path(tenant_id: UUID, file_id: str) -> Path | None:
    root = _CONTENT_ROOT / str(tenant_id)
    if not root.is_dir():
        return None
    fid = (file_id or "").strip()
    for p in root.iterdir():
        if p.name.startswith(f"{fid}_"):
            return p
    return None


def content_file_html_preview(tenant_id: UUID, file_id: str, *, file_name: str | None = None) -> HTMLResponse:
    path = resolve_content_file_path(tenant_id, file_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    name = (file_name or path.name.split("_", 1)[-1]).lower()
    ext = _file_ext(name)
    if ext == ".doc":
        raise HTTPException(status_code=422, detail="旧版 .doc 请下载后用 Word 打开")
    if ext != ".docx":
        raise HTTPException(status_code=422, detail="该文件类型不支持 HTML 预览")
    from app.services.document_text_extract import docx_to_preview_html

    try:
        html = docx_to_preview_html(path.read_bytes())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return HTMLResponse(html)


# ── Columns ──────────────────────────────────────────────────────


def create_column(db: Session, ctx: TenantContext, body: ColumnCreateRequest) -> ColumnOut:
    merchant = _merchant(db, ctx.tenant_id)
    store = (
        db.query(ShopStore).filter(uuid_eq(ShopStore.id, body.shop_id)).first()
        if body.shop_id
        else ensure_default_shop(db, ctx.tenant_id, merchant)
    )
    if not store or store.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=404, detail="店铺不存在")
    c = ShopColumn(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=store.id,
        title=body.title.strip(),
        intro=(body.intro or None),
        status="draft",
        created_by=ctx.user.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _column_out(db, c)


def list_columns(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    ref_min: int | None = None,
    ref_max: int | None = None,
    updated_from: date | None = None,
    updated_to: date | None = None,
) -> tuple[list[ColumnOut], int, dict[str, int]]:
    _merchant(db, ctx.tenant_id)
    base = db.query(ShopColumn).filter(
        uuid_eq(ShopColumn.tenant_id, ctx.tenant_id),
        ShopColumn.deleted_at.is_(None),
    )
    if shop_id:
        base = base.filter(uuid_eq(ShopColumn.shop_id, shop_id))
    counts = {
        "all": base.count(),
        "draft": base.filter(ShopColumn.status == "draft").count(),
        "published": base.filter(ShopColumn.status == "published").count(),
        "off_sale": base.filter(ShopColumn.status == "off_sale").count(),
    }
    query = base
    if status:
        query = query.filter(ShopColumn.status == status)
    if q:
        query = query.filter(ShopColumn.title.contains(q.strip()))
    if updated_from:
        query = query.filter(ShopColumn.updated_at >= _date_start(updated_from))
    if updated_to:
        query = query.filter(ShopColumn.updated_at < _date_end_excl(updated_to))
    if ref_min is not None or ref_max is not None:
        ref_subq = (
            db.query(
                ShopProduct.ref_id.label("cid"),
                func.count(ShopProduct.id).label("cnt"),
            )
            .filter(
                ShopProduct.ref_type == "column",
                ShopProduct.deleted_at.is_(None),
                uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
            )
            .group_by(ShopProduct.ref_id)
            .subquery()
        )
        query = query.outerjoin(ref_subq, ref_subq.c.cid == ShopColumn.id)
        cnt_expr = func.coalesce(ref_subq.c.cnt, 0)
        if ref_min is not None:
            query = query.filter(cnt_expr >= ref_min)
        if ref_max is not None:
            query = query.filter(cnt_expr <= ref_max)
    total = query.count()
    rows = (
        query.order_by(ShopColumn.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_column_out(db, r) for r in rows], total, counts


def export_columns_csv(
    db: Session,
    ctx: TenantContext,
    *,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    ref_min: int | None = None,
    ref_max: int | None = None,
    updated_from: date | None = None,
    updated_to: date | None = None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    import csv
    import io

    items, total, _ = list_columns(
        db,
        ctx,
        page=1,
        page_size=SHOP_EXPORT_ROW_LIMIT,
        status=status,
        q=q,
        shop_id=shop_id,
        ref_min=ref_min,
        ref_max=ref_max,
        updated_from=updated_from,
        updated_to=updated_to,
    )
    if raise_too_many:
        assert_export_within_limit(total)
    default_headers = ["标题", "课时数", "引用商品", "状态", "更新时间"]
    col_map = {
        "title": ["标题"],
        "lesson_count": ["课时数"],
        "ref_product_count": ["引用商品"],
        "status": ["状态"],
        "updated_at": ["更新时间"],
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
    for i in items:
        values = {
            "标题": i.title or "",
            "课时数": i.lesson_count,
            "引用商品": i.ref_product_count,
            "状态": _COLUMN_STATUS_ZH.get(i.status, i.status),
            "更新时间": str(i.updated_at or ""),
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_column_export_task(
    db: Session, ctx: TenantContext, body: ColumnExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or ColumnExportRequest()
    filters = {
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "status": body.status,
        "q": body.q,
        "ref_min": body.ref_min,
        "ref_max": body.ref_max,
        "updated_from": str(body.updated_from) if body.updated_from else None,
        "updated_to": str(body.updated_to) if body.updated_to else None,
        "columns": body.columns,
    }
    csv_text = export_columns_csv(
        db,
        ctx,
        status=body.status,
        q=body.q,
        shop_id=body.shop_id,
        ref_min=body.ref_min,
        ref_max=body.ref_max,
        updated_from=body.updated_from,
        updated_to=body.updated_to,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="columns",
        file_name="shop-columns.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_column_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "columns")


def read_column_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "columns")


def get_column(db: Session, ctx: TenantContext, column_id: UUID) -> ColumnOut:
    return _column_out(db, _get_column(db, ctx.tenant_id, column_id))


def patch_column(
    db: Session, ctx: TenantContext, column_id: UUID, body: ColumnPatchRequest
) -> ColumnOut:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        c.title = data["title"].strip()
        if not c.title:
            raise HTTPException(status_code=422, detail="请填写标题")
    if "intro" in data:
        c.intro = data["intro"]
    db.commit()
    db.refresh(c)
    return _column_out(db, c)


def publish_column(db: Session, ctx: TenantContext, column_id: UUID) -> ColumnOut:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status != "draft":
        raise HTTPException(status_code=422, detail="仅草稿可发布")
    pub = (
        db.query(ShopLesson)
        .filter(
            uuid_eq(ShopLesson.column_id, c.id),
            ShopLesson.deleted_at.is_(None),
            ShopLesson.status == "published",
        )
        .count()
    )
    if pub < 1:
        raise HTTPException(status_code=422, detail="须至少 1 个已发布课时")
    c.status = "published"
    db.commit()
    db.refresh(c)
    return _column_out(db, c)


def off_sale_column(db: Session, ctx: TenantContext, column_id: UUID) -> ColumnOut:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status != "published":
        raise HTTPException(status_code=422, detail="仅已发布专栏可下架")
    c.status = "off_sale"
    db.commit()
    db.refresh(c)
    return _column_out(db, c)


def delete_column(db: Session, ctx: TenantContext, column_id: UUID) -> dict:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status != "draft":
        raise HTTPException(status_code=422, detail="已发布不可删")
    if _ref_count(db, "column", c.id) > 0:
        raise HTTPException(status_code=422, detail="存在商品引用")
    c.deleted_at = _now()
    for les in (
        db.query(ShopLesson)
        .filter(uuid_eq(ShopLesson.column_id, c.id), ShopLesson.deleted_at.is_(None))
        .all()
    ):
        les.deleted_at = _now()
    db.commit()
    return {"ok": True}


# ── Lessons ──────────────────────────────────────────────────────


def list_lessons(db: Session, ctx: TenantContext, column_id: UUID) -> tuple[list[LessonOut], int]:
    c = _get_column(db, ctx.tenant_id, column_id)
    rows = (
        db.query(ShopLesson)
        .filter(uuid_eq(ShopLesson.column_id, c.id), ShopLesson.deleted_at.is_(None))
        .order_by(ShopLesson.sort_order.asc(), ShopLesson.created_at.asc())
        .all()
    )
    return [_lesson_out(r) for r in rows], len(rows)


def create_lesson(
    db: Session, ctx: TenantContext, column_id: UUID, body: LessonCreateRequest
) -> LessonOut:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    max_sort = (
        db.query(ShopLesson)
        .filter(uuid_eq(ShopLesson.column_id, c.id), ShopLesson.deleted_at.is_(None))
        .count()
    )
    sort = body.sort_order if body.sort_order is not None else max_sort
    if body.is_trial and body.media_type != "video":
        raise HTTPException(status_code=422, detail="试看仅支持视频课时")
    if body.is_trial and not body.trial_seconds:
        raise HTTPException(status_code=422, detail="试看须填写试看秒数")
    if body.media_type == "article":
        _validate_article_body(body.content_body)
    elif not body.media_url and not body.media_id:
        raise HTTPException(status_code=422, detail="请上传媒体文件")
    if body.media_type == "video" and body.duration_sec > _MAX_LESSON_DURATION_SEC:
        raise HTTPException(status_code=422, detail="视频时长不能超过 180 分钟")
    les = ShopLesson(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        column_id=c.id,
        title=body.title.strip(),
        media_type=body.media_type,
        media_id=body.media_id if body.media_type != "article" else None,
        media_url=(
            body.media_url
            or (f"/api/v1/shop/content/files/{body.media_id}" if body.media_id else None)
            if body.media_type != "article"
            else None
        ),
        content_body=(body.content_body or None) if body.media_type == "article" else None,
        duration_sec=body.duration_sec if body.media_type != "article" else 0,
        is_trial=body.is_trial if body.media_type == "video" else False,
        trial_seconds=body.trial_seconds if body.is_trial and body.media_type == "video" else None,
        sort_order=sort,
        status="draft",
    )
    db.add(les)
    db.commit()
    db.refresh(les)
    return _lesson_out(les)


def patch_lesson(
    db: Session, ctx: TenantContext, column_id: UUID, lesson_id: UUID, body: LessonPatchRequest
) -> LessonOut:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    les = (
        db.query(ShopLesson)
        .filter(
            uuid_eq(ShopLesson.id, lesson_id),
            uuid_eq(ShopLesson.column_id, c.id),
            ShopLesson.deleted_at.is_(None),
        )
        .first()
    )
    if not les:
        raise HTTPException(status_code=404, detail="课时不存在")
    data = body.model_dump(exclude_unset=True)
    for key in ("title", "media_type", "media_id", "media_url", "content_body", "duration_sec", "sort_order"):
        if key in data and data[key] is not None:
            setattr(les, key, data[key].strip() if key == "title" else data[key])
    if "is_trial" in data and data["is_trial"] is not None:
        if les.media_type != "video":
            les.is_trial = False
            les.trial_seconds = None
        else:
            les.is_trial = data["is_trial"]
    if "trial_seconds" in data:
        les.trial_seconds = data["trial_seconds"]
    if les.media_type == "article":
        les.media_id = None
        les.media_url = None
        les.duration_sec = 0
        les.is_trial = False
        les.trial_seconds = None
    if les.is_trial and les.media_type == "video" and not les.trial_seconds:
        raise HTTPException(status_code=422, detail="试看须填写试看秒数")
    _validate_lesson_media(les)
    db.commit()
    db.refresh(les)
    return _lesson_out(les)


def publish_lesson(db: Session, ctx: TenantContext, column_id: UUID, lesson_id: UUID) -> LessonOut:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    les = (
        db.query(ShopLesson)
        .filter(
            uuid_eq(ShopLesson.id, lesson_id),
            uuid_eq(ShopLesson.column_id, c.id),
            ShopLesson.deleted_at.is_(None),
        )
        .first()
    )
    if not les:
        raise HTTPException(status_code=404, detail="课时不存在")
    if les.status == "published":
        return _lesson_out(les)
    if not (les.title or "").strip():
        raise HTTPException(status_code=422, detail="请填写标题")
    _validate_lesson_media(les)
    les.status = "published"
    db.commit()
    db.refresh(les)
    return _lesson_out(les)


def off_sale_lesson(db: Session, ctx: TenantContext, column_id: UUID, lesson_id: UUID) -> LessonOut:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    les = (
        db.query(ShopLesson)
        .filter(
            uuid_eq(ShopLesson.id, lesson_id),
            uuid_eq(ShopLesson.column_id, c.id),
            ShopLesson.deleted_at.is_(None),
        )
        .first()
    )
    if not les:
        raise HTTPException(status_code=404, detail="课时不存在")
    if les.status != "published":
        raise HTTPException(status_code=422, detail="仅已发布课时可下架")
    les.status = "off_sale"
    db.commit()
    db.refresh(les)
    return _lesson_out(les)


def delete_lesson(db: Session, ctx: TenantContext, column_id: UUID, lesson_id: UUID) -> dict:
    c = _get_column(db, ctx.tenant_id, column_id)
    if c.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    les = (
        db.query(ShopLesson)
        .filter(
            uuid_eq(ShopLesson.id, lesson_id),
            uuid_eq(ShopLesson.column_id, c.id),
            ShopLesson.deleted_at.is_(None),
        )
        .first()
    )
    if not les:
        raise HTTPException(status_code=404, detail="课时不存在")
    if les.status == "published" and c.status == "published":
        # 允许删除草稿/已下架；已发布专栏下的已发布课时用下架
        raise HTTPException(status_code=422, detail="请先下架课时")
    les.deleted_at = _now()
    db.commit()
    return {"ok": True}


# ── Digital packages ─────────────────────────────────────────────


def create_package(
    db: Session, ctx: TenantContext, body: DigitalPackageCreateRequest
) -> DigitalPackageOut:
    merchant = _merchant(db, ctx.tenant_id)
    store = (
        db.query(ShopStore).filter(uuid_eq(ShopStore.id, body.shop_id)).first()
        if body.shop_id
        else ensure_default_shop(db, ctx.tenant_id, merchant)
    )
    if not store or store.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=404, detail="店铺不存在")
    p = ShopDigitalPackage(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=store.id,
        title=body.title.strip(),
        deliver_mode=body.deliver_mode,
        max_downloads=body.max_downloads,
        status="draft",
        created_by=ctx.user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _package_out(db, p, with_assets=True)


def list_packages(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
) -> tuple[list[DigitalPackageOut], int, dict[str, int]]:
    _merchant(db, ctx.tenant_id)
    base = db.query(ShopDigitalPackage).filter(
        uuid_eq(ShopDigitalPackage.tenant_id, ctx.tenant_id),
        ShopDigitalPackage.deleted_at.is_(None),
    )
    if shop_id:
        base = base.filter(uuid_eq(ShopDigitalPackage.shop_id, shop_id))
    counts = {
        "all": base.count(),
        "draft": base.filter(ShopDigitalPackage.status == "draft").count(),
        "published": base.filter(ShopDigitalPackage.status == "published").count(),
        "off_sale": base.filter(ShopDigitalPackage.status == "off_sale").count(),
    }
    query = base
    if status:
        query = query.filter(ShopDigitalPackage.status == status)
    if q:
        query = query.filter(ShopDigitalPackage.title.contains(q.strip()))
    total = query.count()
    rows = (
        query.order_by(ShopDigitalPackage.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_package_out(db, r) for r in rows], total, counts


def export_packages_csv(
    db: Session,
    ctx: TenantContext,
    *,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    import csv
    import io

    items, total, _ = list_packages(
        db, ctx, page=1, page_size=SHOP_EXPORT_ROW_LIMIT, status=status, q=q, shop_id=shop_id
    )
    if raise_too_many:
        assert_export_within_limit(total)
    default_headers = ["标题", "交付方式", "文件数", "引用商品", "状态", "更新时间"]
    col_map = {
        "title": ["标题"],
        "deliver_mode": ["交付方式"],
        "file_count": ["文件数"],
        "ref_product_count": ["引用商品"],
        "status": ["状态"],
        "updated_at": ["更新时间"],
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
    for i in items:
        values = {
            "标题": i.title or "",
            "交付方式": _DELIVER_ZH.get(i.deliver_mode, i.deliver_mode or ""),
            "文件数": i.file_count,
            "引用商品": i.ref_product_count,
            "状态": _PACKAGE_STATUS_ZH.get(i.status, i.status),
            "更新时间": str(i.updated_at or ""),
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_package_export_task(
    db: Session, ctx: TenantContext, body: DigitalPackageExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or DigitalPackageExportRequest()
    filters = {
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "status": body.status,
        "q": body.q,
        "columns": body.columns,
    }
    csv_text = export_packages_csv(
        db,
        ctx,
        status=body.status,
        q=body.q,
        shop_id=body.shop_id,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="digital_packages",
        file_name="shop-digital-packages.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_package_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "digital_packages")


def read_package_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "digital_packages")


def get_package(db: Session, ctx: TenantContext, package_id: UUID) -> DigitalPackageOut:
    return _package_out(db, _get_package(db, ctx.tenant_id, package_id), with_assets=True)


def patch_package(
    db: Session, ctx: TenantContext, package_id: UUID, body: DigitalPackagePatchRequest
) -> DigitalPackageOut:
    p = _get_package(db, ctx.tenant_id, package_id)
    if p.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        p.title = data["title"].strip()
        if not p.title:
            raise HTTPException(status_code=422, detail="请填写标题")
    if "deliver_mode" in data and data["deliver_mode"] is not None:
        p.deliver_mode = data["deliver_mode"]
    if "max_downloads" in data:
        p.max_downloads = data["max_downloads"]
    db.commit()
    db.refresh(p)
    return _package_out(db, p, with_assets=True)


def add_asset(
    db: Session, ctx: TenantContext, package_id: UUID, body: DigitalAssetCreateRequest
) -> DigitalAssetOut:
    p = _get_package(db, ctx.tenant_id, package_id)
    if p.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    if p.status == "published":
        raise HTTPException(status_code=422, detail="已发布不可添加文件")
    path = resolve_content_file_path(ctx.tenant_id, body.file_id)
    if not path:
        raise HTTPException(status_code=422, detail="请先上传文件")
    lower = (body.file_name or "").lower()
    if not any(lower.endswith(ext) for ext in _ASSET_EXT):
        raise HTTPException(status_code=422, detail="仅支持 pdf/doc/docx/zip")
    size = path.stat().st_size if path.is_file() else int(body.size_bytes or 0)
    if size > _MAX_ASSET_BYTES:
        raise HTTPException(status_code=422, detail="文件过大")
    count = (
        db.query(ShopDigitalAsset).filter(uuid_eq(ShopDigitalAsset.package_id, p.id)).count()
    )
    if count >= _MAX_ASSETS:
        raise HTTPException(status_code=422, detail="包内最多 20 个文件")
    mime = body.mime or "application/octet-stream"
    asset = ShopDigitalAsset(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        package_id=p.id,
        file_id=body.file_id,
        file_name=body.file_name.strip(),
        file_url=body.file_url or f"/api/v1/shop/content/files/{body.file_id}",
        mime=mime,
        size_bytes=size,
        previewable=_previewable(body.file_name, mime),
        sort_order=count,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


def delete_asset(db: Session, ctx: TenantContext, package_id: UUID, asset_id: UUID) -> dict:
    p = _get_package(db, ctx.tenant_id, package_id)
    if p.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    if p.status == "published" and _ref_count(db, "digital_package", p.id) > 0:
        raise HTTPException(status_code=422, detail="存在商品引用不可删")
    asset = (
        db.query(ShopDigitalAsset)
        .filter(
            uuid_eq(ShopDigitalAsset.id, asset_id),
            uuid_eq(ShopDigitalAsset.package_id, p.id),
        )
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="文件不存在")
    db.delete(asset)
    db.commit()
    return {"ok": True}


def publish_package(db: Session, ctx: TenantContext, package_id: UUID) -> DigitalPackageOut:
    p = _get_package(db, ctx.tenant_id, package_id)
    if p.status != "draft":
        raise HTTPException(status_code=422, detail="仅草稿可发布")
    assets = (
        db.query(ShopDigitalAsset).filter(uuid_eq(ShopDigitalAsset.package_id, p.id)).all()
    )
    if len(assets) < 1:
        raise HTTPException(status_code=422, detail="请添加至少 1 个文件")
    if p.deliver_mode == "online_view" and not any(a.previewable for a in assets):
        raise HTTPException(status_code=422, detail="在线查看须至少 1 个 pdf/doc 文件")
    p.status = "published"
    db.commit()
    db.refresh(p)
    return _package_out(db, p, with_assets=True)


def off_sale_package(db: Session, ctx: TenantContext, package_id: UUID) -> DigitalPackageOut:
    p = _get_package(db, ctx.tenant_id, package_id)
    if p.status != "published":
        raise HTTPException(status_code=422, detail="仅已发布可下架")
    p.status = "off_sale"
    db.commit()
    db.refresh(p)
    return _package_out(db, p, with_assets=True)


def delete_package(db: Session, ctx: TenantContext, package_id: UUID) -> dict:
    p = _get_package(db, ctx.tenant_id, package_id)
    if p.status != "draft":
        raise HTTPException(status_code=422, detail="仅草稿可删")
    if _ref_count(db, "digital_package", p.id) > 0:
        raise HTTPException(status_code=422, detail="存在商品引用不可删")
    p.deleted_at = _now()
    db.commit()
    return {"ok": True}


def published_lessons_for_product(db: Session, product: ShopProduct) -> list[dict]:
    if product.ref_type != "column" or not product.ref_id:
        return []
    col = (
        db.query(ShopColumn)
        .filter(uuid_eq(ShopColumn.id, product.ref_id), ShopColumn.deleted_at.is_(None))
        .first()
    )
    if not col:
        return []
    rows = (
        db.query(ShopLesson)
        .filter(
            uuid_eq(ShopLesson.column_id, col.id),
            ShopLesson.deleted_at.is_(None),
            ShopLesson.status == "published",
        )
        .order_by(ShopLesson.sort_order.asc())
        .all()
    )
    out = []
    for i, les in enumerate(rows):
        out.append(
            {
                "id": str(les.id),
                "title": les.title,
                "duration_sec": int(les.duration_sec or 0),
                "is_trial": bool(les.is_trial),
                "trial_seconds": les.trial_seconds,
                "sort": les.sort_order if les.sort_order is not None else i + 1,
                "media_type": les.media_type or "video",
                "media_id": str(les.media_id) if les.media_id else None,
                "media_url": les.media_url
                or (f"/api/v1/shop/content/files/{les.media_id}" if les.media_id else None),
            }
        )
    return out


def package_files_for_product(db: Session, product: ShopProduct) -> tuple[str, int | None, list[dict]]:
    if product.ref_type != "digital_package" or not product.ref_id:
        return "download", None, []
    pkg = (
        db.query(ShopDigitalPackage)
        .filter(
            uuid_eq(ShopDigitalPackage.id, product.ref_id),
            ShopDigitalPackage.deleted_at.is_(None),
        )
        .first()
    )
    if not pkg:
        return "download", None, []
    assets = (
        db.query(ShopDigitalAsset)
        .filter(uuid_eq(ShopDigitalAsset.package_id, pkg.id))
        .order_by(ShopDigitalAsset.sort_order.asc())
        .all()
    )
    files = [
        {
            "id": str(a.id),
            "name": a.file_name,
            "size_bytes": int(a.size_bytes or 0),
            "mime": a.mime,
            "url": a.file_url or f"/api/v1/shop/content/files/{a.file_id}",
            "file_id": a.file_id,
            "previewable": bool(a.previewable),
        }
        for a in assets
    ]
    return pkg.deliver_mode, pkg.max_downloads, files
