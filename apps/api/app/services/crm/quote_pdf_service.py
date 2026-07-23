"""报价 PDF 异步生成（v1.3 FR-CPQ-08）。

MVP：生成可打印 HTML 报价单（浏览器「打印为 PDF」）；状态机 generating → completed/failed。
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.dependencies import TenantContext
from app.models.crm import Customer, Quote, QuoteLine, QuotePdf
from app.schemas.crm_cpq import QuotePdfOut
from app.services.crm.quote_service import _load_lines, require_quote


def _quote_pdf_dir() -> Path:
    d = Path(settings.STORAGE_DIR) / "quote-pdfs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pdf_out(row: QuotePdf) -> QuotePdfOut:
    download_url = None
    if row.status == "completed" and row.id:
        download_url = f"/api/v1/crm/cpq/quotes/{row.quote_id}/pdf/download"
    return QuotePdfOut(
        id=row.id,
        tenant_id=row.tenant_id,
        quote_id=row.quote_id,
        file_path=row.file_path,
        file_name=row.file_name,
        file_size=row.file_size,
        status=row.status,  # type: ignore[arg-type]
        error_message=row.error_message,
        download_url=download_url,
        generated_at=row.generated_at,
        created_at=row.created_at,
    )


def get_latest_pdf(db: Session, ctx: TenantContext, quote_id: UUID) -> QuotePdf | None:
    require_quote(db, ctx, quote_id)
    return (
        db.query(QuotePdf)
        .filter(QuotePdf.tenant_id == ctx.tenant_id, QuotePdf.quote_id == quote_id)
        .order_by(QuotePdf.created_at.desc())
        .first()
    )


def enqueue_quote_pdf(db: Session, ctx: TenantContext, quote_id: UUID) -> tuple[QuotePdf, bool]:
    """返回 (row, should_schedule)。已有 generating 任务则不重复调度。"""
    require_quote(db, ctx, quote_id)
    latest = (
        db.query(QuotePdf)
        .filter(QuotePdf.tenant_id == ctx.tenant_id, QuotePdf.quote_id == quote_id)
        .order_by(QuotePdf.created_at.desc())
        .first()
    )
    if latest and latest.status == "generating":
        return latest, False
    row = QuotePdf(
        tenant_id=ctx.tenant_id,
        quote_id=quote_id,
        status="generating",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True


def _fmt_money(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _build_html(quote: Quote, lines: list[QuoteLine], customer_name: str) -> str:
    snap = quote.cpq_config_snapshot or {}
    params = snap.get("selected_params") or {}
    param_html = ""
    if params:
        items = "".join(
            f"<li>{html.escape(str(k))} = {html.escape(str(v))}</li>" for k, v in params.items()
        )
        param_html = f"<h3>CPQ 配置</h3><ul>{items}</ul>"

    rows = []
    for ln in lines:
        rows.append(
            "<tr>"
            f"<td>{html.escape(ln.name or '')}</td>"
            f"<td>{html.escape(ln.unit or '—')}</td>"
            f"<td style='text-align:right'>{ln.quantity}</td>"
            f"<td style='text-align:right'>¥{_fmt_money(ln.unit_price)}</td>"
            f"<td style='text-align:right'>{(str(ln.discount_rate) + '%') if ln.discount_rate is not None else '—'}</td>"
            f"<td style='text-align:right'>¥{_fmt_money(ln.line_total)}</td>"
            "</tr>"
        )

    subject = html.escape(quote.subject or "")
    qn = html.escape(quote.quote_number or "")
    cust = html.escape(customer_name or str(quote.customer_id))
    created = html.escape(str(quote.created_at or "")[:19].replace("T", " "))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>报价单 {qn}</title>
  <style>
    body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; color: #1f1f1f; margin: 32px; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    .meta {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 10px; font-size: 13px; }}
    th {{ background: #f5f5f5; text-align: left; }}
    .total {{ text-align: right; font-size: 16px; margin-top: 16px; font-weight: 600; }}
    @media print {{ body {{ margin: 12mm; }} }}
  </style>
</head>
<body>
  <h1>报价单</h1>
  <div class="meta">
    <div>单号：{qn}</div>
    <div>主题：{subject}</div>
    <div>客户：{cust}</div>
    <div>创建时间：{created}</div>
  </div>
  {param_html}
  <table>
    <thead>
      <tr><th>名称</th><th>单位</th><th>数量</th><th>单价</th><th>折扣</th><th>小计</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
  <div class="total">合计：¥{_fmt_money(quote.total_amount)}</div>
  <p style="margin-top:24px;color:#999;font-size:12px">可使用浏览器打印功能另存为 PDF。</p>
</body>
</html>
"""


def generate_quote_pdf_job(pdf_id: str) -> None:
    """Background task：独立 Session。"""
    db = SessionLocal()
    try:
        row = db.query(QuotePdf).filter(QuotePdf.id == UUID(pdf_id)).first()
        if not row or row.status != "generating":
            return
        quote = (
            db.query(Quote)
            .filter(Quote.id == row.quote_id, Quote.tenant_id == row.tenant_id, Quote.deleted_at.is_(None))
            .first()
        )
        if not quote:
            row.status = "failed"
            row.error_message = "报价不存在"
            db.commit()
            return

        lines = _load_lines(db, quote.id)
        customer = db.query(Customer).filter(Customer.id == quote.customer_id).first()
        customer_name = customer.company_name if customer else ""
        content = _build_html(quote, lines, customer_name)

        fname = f"quote_{quote.quote_number}_{row.id.hex[:8]}.html"
        path = _quote_pdf_dir() / fname
        path.write_text(content, encoding="utf-8")

        row.file_path = str(path)
        row.file_name = fname
        row.file_size = path.stat().st_size
        row.status = "completed"
        row.generated_at = datetime.now(timezone.utc)
        row.error_message = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            row = db.query(QuotePdf).filter(QuotePdf.id == UUID(pdf_id)).first()
            if row:
                row.status = "failed"
                row.error_message = str(exc)[:500]
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


def pdf_status(db: Session, ctx: TenantContext, quote_id: UUID) -> QuotePdfOut:
    row = get_latest_pdf(db, ctx, quote_id)
    if not row:
        raise HTTPException(status_code=404, detail="尚未发起 PDF 生成")
    return _pdf_out(row)


def resolve_download_path(db: Session, ctx: TenantContext, quote_id: UUID) -> tuple[Path, str]:
    row = get_latest_pdf(db, ctx, quote_id)
    if not row:
        raise HTTPException(status_code=404, detail="尚未发起 PDF 生成")
    if row.status != "completed" or not row.file_path:
        raise HTTPException(status_code=409, detail=f"PDF 尚未就绪（{row.status}）")
    path = Path(row.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PDF 文件不存在")
    return path, row.file_name or path.name
