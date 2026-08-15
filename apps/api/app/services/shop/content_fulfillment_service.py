"""买家学课 / 资料履约（M07/M08/M09）。

内容源优先级：A04/A06 CMS（product.ref）→ product.extra → 稳定演示大纲。
"""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models.shop import (
    ShopBuyer,
    ShopDigitalDownload,
    ShopEntitlement,
    ShopLessonProgress,
    ShopProduct,
)
from app.schemas.shop_platform import (
    CourseOutlineOut,
    LessonItemOut,
    MaterialDownloadOut,
    MaterialFileOut,
    MaterialsOut,
)

_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

_DEFAULT_LESSON_TITLES = [
    "01 定位选题",
    "02 脚本结构",
    "03 拍摄节奏",
    "04 剪辑节奏",
    "05 投放复盘",
]


def _entitlement_or_404(db: Session, buyer: ShopBuyer, entitlement_id: UUID) -> ShopEntitlement:
    ent = (
        db.query(ShopEntitlement)
        .filter(
            uuid_eq(ShopEntitlement.id, entitlement_id),
            uuid_eq(ShopEntitlement.buyer_id, buyer.id),
        )
        .first()
    )
    if not ent:
        raise HTTPException(status_code=404, detail="权益不存在")
    return ent


def _stable_id(product_id: UUID, kind: str, idx: int) -> UUID:
    return uuid.uuid5(_NS, f"{product_id}:{kind}:{idx}")


def _default_lessons(product: ShopProduct) -> list[dict]:
    lessons = []
    for i, title in enumerate(_DEFAULT_LESSON_TITLES):
        lid = _stable_id(product.id, "lesson", i)
        lessons.append(
            {
                "id": str(lid),
                "title": title,
                "duration_sec": 600 + i * 60,
                "is_trial": i == 3,
                "trial_seconds": 180 if i == 3 else None,
                "sort": i + 1,
                "media_url": f"https://example.com/mock/course/{product.id}/l{i}.mp4",
            }
        )
    return lessons


def _default_files(product: ShopProduct) -> list[dict]:
    return [
        {
            "id": str(_stable_id(product.id, "file", 0)),
            "name": "话术库.pdf",
            "size_bytes": 2_100_000,
            "mime": "application/pdf",
            "url": f"https://example.com/mock/materials/{product.id}/script.pdf",
        },
        {
            "id": str(_stable_id(product.id, "file", 1)),
            "name": "模板.zip",
            "size_bytes": 8_400_000,
            "mime": "application/zip",
            "url": f"https://example.com/mock/materials/{product.id}/tpl.zip",
        },
    ]


def _resolve_lessons(db: Session, product: ShopProduct) -> tuple[UUID, list[dict]]:
    from app.services.shop import content_cms_service

    cms_lessons = content_cms_service.published_lessons_for_product(db, product)
    if cms_lessons:
        cid = product.ref_id if product.ref_type == "column" and product.ref_id else product.id
        return cid, cms_lessons

    extra = product.extra or {}
    raw = extra.get("lessons")
    course_id = extra.get("course_id")
    cid = UUID(str(course_id)) if course_id else product.id
    if isinstance(raw, list) and raw:
        lessons = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            lid = item.get("id") or str(_stable_id(product.id, "lesson", i))
            lessons.append(
                {
                    "id": str(lid),
                    "title": item.get("title") or f"课时 {i + 1}",
                    "duration_sec": int(item.get("duration_sec") or 600),
                    "is_trial": bool(item.get("is_trial")),
                    "trial_seconds": item.get("trial_seconds"),
                    "sort": int(item.get("sort") or i + 1),
                    "media_url": item.get("media_url")
                    or f"https://example.com/mock/course/{product.id}/l{i}.mp4",
                }
            )
        return cid, lessons
    return cid, _default_lessons(product)


def _resolve_files(db: Session, product: ShopProduct) -> tuple[str, int | None, list[dict]]:
    from app.services.shop import content_cms_service

    deliver_mode, max_downloads, files = content_cms_service.package_files_for_product(db, product)
    if files:
        return deliver_mode, max_downloads, files

    extra = product.extra or {}
    deliver_mode = extra.get("deliver_mode") or "online_view"
    max_downloads = extra.get("max_downloads")
    if max_downloads is not None:
        max_downloads = int(max_downloads)
    raw = extra.get("files")
    if isinstance(raw, list) and raw:
        files = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            files.append(
                {
                    "id": str(item.get("id") or _stable_id(product.id, "file", i)),
                    "name": item.get("name") or f"文件{i + 1}",
                    "size_bytes": int(item.get("size_bytes") or 0),
                    "mime": item.get("mime") or "application/octet-stream",
                    "url": item.get("url")
                    or f"https://example.com/mock/materials/{product.id}/f{i}",
                }
            )
        return deliver_mode, max_downloads, files
    return deliver_mode, max_downloads if max_downloads is not None else 10, _default_files(product)


def get_course_outline(db: Session, buyer: ShopBuyer, entitlement_id: UUID) -> CourseOutlineOut:
    ent = _entitlement_or_404(db, buyer, entitlement_id)
    if ent.status not in ("active", "expired", "revoked"):
        raise HTTPException(status_code=403, detail="暂无学习权限")
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, ent.product_id)).first()
    if not product or product.type != "course":
        raise HTTPException(status_code=422, detail="非课程权益")

    course_id, lessons = _resolve_lessons(db, product)
    progress_rows = (
        db.query(ShopLessonProgress)
        .filter(uuid_eq(ShopLessonProgress.entitlement_id, ent.id))
        .all()
    )
    prog_map = {str(r.lesson_id): r for r in progress_rows}

    items: list[LessonItemOut] = []
    done = 0
    learning = 0
    for les in lessons:
        pr = prog_map.get(str(les["id"]))
        pct = int(pr.progress_pct) if pr else 0
        pos = int(pr.position_sec) if pr else 0
        if pct >= 100:
            status = "done"
            done += 1
        elif pct > 0 or pos > 0:
            status = "learning"
            learning += 1
        else:
            status = "todo"
        # 有权看全部；revoked/expired 前端禁用（仍返回目录）
        locked = ent.status != "active" and not les.get("is_trial")
        items.append(
            LessonItemOut(
                id=UUID(str(les["id"])),
                title=les["title"],
                duration_sec=les["duration_sec"],
                is_trial=bool(les.get("is_trial")),
                trial_seconds=les.get("trial_seconds"),
                sort=les["sort"],
                status=status,
                progress_pct=pct,
                position_sec=pos,
                locked=locked,
                media_url=les.get("media_url") if ent.status == "active" or les.get("is_trial") else None,
            )
        )

    total = len(items)
    overall = int(round(100 * done / total)) if total else 0
    return CourseOutlineOut(
        entitlement_id=ent.id,
        product_id=product.id,
        course_id=course_id,
        product_name=product.name,
        entitlement_status=ent.status,
        progress_pct=overall,
        learned_count=done,
        total_count=total,
        lessons=items,
    )


def get_materials(db: Session, buyer: ShopBuyer, entitlement_id: UUID) -> MaterialsOut:
    ent = _entitlement_or_404(db, buyer, entitlement_id)
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, ent.product_id)).first()
    if not product or product.type != "digital":
        raise HTTPException(status_code=422, detail="非资料权益")

    deliver_mode, max_downloads, files = _resolve_files(db, product)
    counts = {
        r.file_id: r.download_count
        for r in db.query(ShopDigitalDownload)
        .filter(uuid_eq(ShopDigitalDownload.entitlement_id, ent.id))
        .all()
    }
    total_dl = sum(counts.values())
    out_files: list[MaterialFileOut] = []
    for f in files:
        mime = (f.get("mime") or "").lower()
        name = f.get("name") or ""
        can_preview = bool(f.get("previewable")) if "previewable" in f else (
            deliver_mode == "online_view"
            and ("pdf" in mime or name.lower().endswith((".pdf", ".doc", ".docx")))
        )
        if name.lower().endswith(".zip") or "zip" in mime:
            can_preview = False
        used = int(counts.get(str(f["id"]), 0))
        remaining = None if max_downloads is None else max(0, max_downloads - used)
        disabled = ent.status != "active" or (remaining is not None and remaining <= 0)
        out_files.append(
            MaterialFileOut(
                id=str(f["id"]),
                name=f["name"],
                size_bytes=int(f.get("size_bytes") or 0),
                mime=f.get("mime") or "application/octet-stream",
                can_preview=can_preview,
                download_count=used,
                remaining_downloads=remaining,
                download_disabled=disabled,
            )
        )
    return MaterialsOut(
        entitlement_id=ent.id,
        product_id=product.id,
        product_name=product.name,
        entitlement_status=ent.status,
        deliver_mode=deliver_mode,
        max_downloads=max_downloads,
        total_download_count=total_dl,
        files=out_files,
    )


def download_material(
    db: Session, buyer: ShopBuyer, entitlement_id: UUID, file_id: str
) -> MaterialDownloadOut:
    ent = _entitlement_or_404(db, buyer, entitlement_id)
    if ent.status != "active":
        raise HTTPException(status_code=403, detail="权限已关闭")
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, ent.product_id)).first()
    if not product or product.type != "digital":
        raise HTTPException(status_code=422, detail="非资料权益")

    deliver_mode, max_downloads, files = _resolve_files(db, product)
    target = next((f for f in files if str(f["id"]) == str(file_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail="文件不存在")

    row = (
        db.query(ShopDigitalDownload)
        .filter(
            uuid_eq(ShopDigitalDownload.entitlement_id, ent.id),
            ShopDigitalDownload.file_id == str(file_id),
        )
        .first()
    )
    used = row.download_count if row else 0
    if max_downloads is not None and used >= max_downloads:
        raise HTTPException(status_code=409, detail="已达下载上限")

    if row is None:
        row = ShopDigitalDownload(
            id=uuid.uuid4(),
            tenant_id=buyer.tenant_id,
            buyer_id=buyer.id,
            entitlement_id=ent.id,
            file_id=str(file_id),
            download_count=1,
        )
        db.add(row)
    else:
        row.download_count = int(row.download_count or 0) + 1
    db.commit()
    db.refresh(row)

    # Mock 短时签名 URL
    url = target.get("url") or f"https://example.com/mock/dl/{file_id}?sig=stub"
    remaining = None if max_downloads is None else max(0, max_downloads - row.download_count)
    return MaterialDownloadOut(
        file_id=str(file_id),
        download_url=url,
        download_count=row.download_count,
        remaining_downloads=remaining,
        deliver_mode=deliver_mode,
    )
