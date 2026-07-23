"""CPQ API（v1.3：取价 + 参数 + calculate + 写入 quotes + PDF）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_cpq import (
    CpqAiParseOut,
    CpqAiParseRequest,
    CpqCalculateOut,
    CpqCalculateRequest,
    CpqSaveQuoteRequest,
    ParamPricingCreate,
    ParamPricingOut,
    ParamPricingUpdate,
    ProductParamCreate,
    ProductParamOut,
    ProductParamUpdate,
    QuotePdfOut,
    ResolvePriceOut,
    ResolvePriceRequest,
)
from app.schemas.crm_deals import ProductOut, QuoteOut
from app.services.crm import cpq_ai_service, cpq_service, quote_pdf_service
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/cpq", tags=["crm-cpq"])


def _param_out(row) -> ProductParamOut:
    data = ProductParamOut.model_validate(row)
    pricings = getattr(row, "pricings", []) or []
    data.pricings = [ParamPricingOut.model_validate(p) for p in pricings]
    return data


@router.get("/products", response_model=list[ProductOut])
def get_cpq_products(
    ctx: TenantContext = Depends(require_permission("crm.quote.create")),
    db: Session = Depends(get_db),
):
    return [ProductOut.model_validate(p) for p in cpq_service.list_cpq_products(db, ctx)]


@router.post("/resolve-price", response_model=ResolvePriceOut)
def post_resolve_price(
    body: ResolvePriceRequest,
    ctx: TenantContext = Depends(require_permission("crm.quote.create")),
    db: Session = Depends(get_db),
):
    return cpq_service.resolve_unit_price(db, ctx, body)


@router.post("/calculate", response_model=CpqCalculateOut)
def post_calculate(
    body: CpqCalculateRequest,
    ctx: TenantContext = Depends(require_permission("crm.quote.create")),
    db: Session = Depends(get_db),
):
    return cpq_service.calculate_quote(db, ctx, body)


@router.post("/quotes", response_model=QuoteOut, status_code=201)
def post_cpq_quote(
    body: CpqSaveQuoteRequest,
    ctx: TenantContext = Depends(require_permission("crm.quote.create")),
    db: Session = Depends(get_db),
):
    """CPQ 配置保存为现有 quotes（含明细与快照）。"""
    return cpq_service.save_cpq_as_quote(db, ctx, body)


@router.post("/ai-parse", response_model=CpqAiParseOut)
async def post_ai_parse(
    body: CpqAiParseRequest,
    ctx: TenantContext = Depends(require_permission("crm.quote.create")),
    db: Session = Depends(get_db),
):
    """AI 解析需求文本 → 参数推荐（不落库；须前端人审采纳）。"""
    return await cpq_ai_service.parse_requirements(db, ctx, body)


@router.post("/quotes/{quote_id}/pdf", response_model=QuotePdfOut, status_code=202)
def post_quote_pdf(
    quote_id: UUID,
    background_tasks: BackgroundTasks,
    ctx: TenantContext = Depends(require_permission("crm.quote.view")),
    db: Session = Depends(get_db),
):
    row, should_schedule = quote_pdf_service.enqueue_quote_pdf(db, ctx, quote_id)
    if should_schedule:
        background_tasks.add_task(quote_pdf_service.generate_quote_pdf_job, str(row.id))
    return quote_pdf_service._pdf_out(row)


@router.get("/quotes/{quote_id}/pdf-status", response_model=QuotePdfOut)
def get_quote_pdf_status(
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.quote.view")),
    db: Session = Depends(get_db),
):
    return quote_pdf_service.pdf_status(db, ctx, quote_id)


@router.get("/quotes/{quote_id}/pdf/download")
def download_quote_pdf(
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.quote.view")),
    db: Session = Depends(get_db),
):
    path, filename = quote_pdf_service.resolve_download_path(db, ctx, quote_id)
    return FileResponse(path, filename=filename, media_type="text/html; charset=utf-8")


@router.get("/products/{product_id}/params", response_model=list[ProductParamOut])
def get_product_params(
    product_id: UUID,
    include_inactive: bool = Query(default=False),
    ctx: TenantContext = Depends(
        require_any_permission("crm.product.manage", "crm.quote.create")
    ),
    db: Session = Depends(get_db),
):
    rows = cpq_service.list_params(db, ctx, product_id, include_inactive=include_inactive)
    return [_param_out(r) for r in rows]


@router.post("/products/{product_id}/params", response_model=ProductParamOut, status_code=201)
def post_product_param(
    product_id: UUID,
    body: ProductParamCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return _param_out(cpq_service.create_param(db, ctx, product_id, body))


@router.patch("/params/{param_id}", response_model=ProductParamOut)
def patch_product_param(
    param_id: UUID,
    body: ProductParamUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = cpq_service.get_param(db, ctx, param_id)
    return _param_out(cpq_service.update_param(db, ctx, row, body))


@router.delete("/params/{param_id}", status_code=204)
def delete_product_param(
    param_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = cpq_service.get_param(db, ctx, param_id)
    cpq_service.delete_param(db, row)


@router.post("/params/{param_id}/pricings", response_model=ParamPricingOut, status_code=201)
def post_param_pricing(
    param_id: UUID,
    body: ParamPricingCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return ParamPricingOut.model_validate(cpq_service.create_pricing(db, ctx, param_id, body))


@router.patch("/pricings/{pricing_id}", response_model=ParamPricingOut)
def patch_param_pricing(
    pricing_id: UUID,
    body: ParamPricingUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return ParamPricingOut.model_validate(cpq_service.update_pricing(db, ctx, pricing_id, body))


@router.delete("/pricings/{pricing_id}", status_code=204)
def delete_param_pricing(
    pricing_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    cpq_service.delete_pricing(db, ctx, pricing_id)
