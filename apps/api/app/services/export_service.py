import io
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Content, ExportRecord


def assert_exportable(content: Content, export_type: str) -> None:
    if export_type == "xhs" and content.platform != "xhs":
        raise HTTPException(status_code=400, detail="仅小红书内容可导出 zip")
    if export_type == "douyin" and content.platform != "douyin":
        raise HTTPException(status_code=400, detail="仅抖音内容可导出脚本")
    if not content.body.strip():
        raise HTTPException(status_code=400, detail="内容正文为空，无法导出")


def _exports_dir() -> Path:
    path = Path(settings.STORAGE_DIR) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _render_cover_svg(title: str, subtitle: str = "智营获客") -> bytes:
    safe_title = (title or "财税笔记")[:20].replace("&", "&amp;").replace("<", "&lt;")
    safe_sub = subtitle.replace("&", "&amp;").replace("<", "&lt;")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1440" viewBox="0 0 1080 1440">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1677ff"/>
      <stop offset="100%" style="stop-color:#0958d9"/>
    </linearGradient>
  </defs>
  <rect width="1080" height="1440" fill="url(#bg)"/>
  <rect x="60" y="60" width="960" height="1320" fill="none" stroke="#ffffff" stroke-width="4" opacity="0.6"/>
  <text x="120" y="680" fill="#ffffff" font-size="64" font-family="Microsoft YaHei, sans-serif">{safe_title}</text>
  <text x="120" y="780" fill="#e6f4ff" font-size="36" font-family="Microsoft YaHei, sans-serif">{safe_sub}</text>
</svg>"""
    return svg.encode("utf-8")


def export_xhs_zip(db: Session, content: Content) -> tuple[ExportRecord, Path]:
    assert_exportable(content, "xhs")
    export_dir = _exports_dir()
    zip_name = f"{content.id}_xhs.zip"
    zip_path = export_dir / zip_name

    cover_bytes = _render_cover_svg(content.topic or "财税笔记")
    copy_text = f"标题：{content.topic}\n\n{content.body}\n"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("文案.txt", copy_text.encode("utf-8"))
        zf.writestr("cover.svg", cover_bytes)
        zf.writestr(
            "README.txt",
            "小红书导出包：cover.svg 为封面（1080x1440），文案.txt 为正文。可用设计工具将 SVG 转 PNG。\n".encode(
                "utf-8"
            ),
        )

    content.status = "exported"
    record = ExportRecord(
        content_id=content.id,
        tenant_id=content.tenant_id,
        export_type="xhs",
        file_name=zip_name,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    db.refresh(content)
    return record, zip_path


def export_douyin_markdown(db: Session, content: Content) -> tuple[ExportRecord, Path]:
    assert_exportable(content, "douyin")
    export_dir = _exports_dir()
    file_name = f"{content.id}_douyin.md"
    file_path = export_dir / file_name

    md = f"""# {content.topic}

## 分镜脚本

{content.body}

---
> 导出时间：自动生成 · 智营获客
"""
    file_path.write_text(md, encoding="utf-8")

    content.status = "exported"
    record = ExportRecord(
        content_id=content.id,
        tenant_id=content.tenant_id,
        export_type="douyin",
        file_name=file_name,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    db.refresh(content)
    return record, file_path
