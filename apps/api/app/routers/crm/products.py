"""产品目录 API（v0.7 CRM-2 + v1.0 filters）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import Product
from app.schemas.crm_deals import (
    PriceBookEntryOut,
    ProductCreate,
    ProductListResponse,
    ProductOut,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantOut,
    ProductVariantUpdate,
)
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.product_catalog_service import (
    create_variant,
    delete_variant,
    get_variant,
    list_product_entries,
    list_variants,
    update_variant,
)
from app.services.crm.product_service import (
    create_product,
    product_to_out,
    require_product,
    soft_delete_product,
    update_product,
)
from app.services.crm.view_service import (
    apply_view_filters,
    apply_view_search,
    apply_view_sort,
    assert_can_access_view,
    get_view,
    resolve_view_list_columns,
)
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/products", tags=["crm-products"])

# 报价/订单/商机选品需要读产品；写操作仍仅 crm.product.manage
_PRODUCT_READ = require_any_permission(
    "crm.product.manage",
    "crm.quote.create",
    "crm.quote.edit",
    "crm.order.create",
    "crm.order.edit",
    "crm.deal.create",
    "crm.deal.edit",
)


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(_PRODUCT_READ),
    db: Session = Depends(get_db),
):
    active_view = None
    filters_applied = False
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(Product).filter(Product.tenant_id == ctx.tenant_id, Product.deleted_at.is_(None))

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "product", active_view.filters)
        query = apply_view_search(query, "product", active_view.search_q)
        query = apply_view_sort(query, "product", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "product", parsed_filters)
            filters_applied = True
        else:
            if is_active is not None:
                query = query.filter(Product.is_active.is_(is_active))
            if category_id is not None:
                query = query.filter(Product.category_id == category_id)
        query = apply_view_search(query, "product", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "product", sort_spec)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return ProductListResponse(
        items=[product_to_out(db, i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "product", active_view),
        view_id=active_view.id if active_view else None,
        filters_applied=filters_applied if filters else None,
    )


@router.post("", response_model=ProductOut, status_code=201)
def post_product(
    body: ProductCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    p = create_product(db, ctx, body)
    return product_to_out(db, p)


@router.get("/{product_id}", response_model=ProductOut)
def get_product_detail(
    product_id: UUID,
    ctx: TenantContext = Depends(_PRODUCT_READ),
    db: Session = Depends(get_db),
):
    p = require_product(db, ctx, product_id)
    return product_to_out(db, p)


@router.patch("/{product_id}", response_model=ProductOut)
def patch_product(
    product_id: UUID,
    body: ProductUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    p = require_product(db, ctx, product_id)
    p = update_product(db, ctx, p, body)
    return product_to_out(db, p)


@router.delete("/{product_id}", status_code=204)
def delete_product_endpoint(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    p = require_product(db, ctx, product_id)
    soft_delete_product(db, p)


@router.get("/{product_id}/variants", response_model=list[ProductVariantOut])
def list_product_variants(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return [ProductVariantOut.model_validate(i) for i in list_variants(db, ctx, product_id)]


@router.post("/{product_id}/variants", response_model=ProductVariantOut, status_code=201)
def post_product_variant(
    product_id: UUID,
    body: ProductVariantCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return ProductVariantOut.model_validate(create_variant(db, ctx, product_id, body))


@router.patch("/variants/{variant_id}", response_model=ProductVariantOut)
def patch_product_variant(
    variant_id: UUID,
    body: ProductVariantUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = get_variant(db, ctx.tenant_id, variant_id)
    if not row:
        raise HTTPException(status_code=404, detail="变体不存在")
    return ProductVariantOut.model_validate(update_variant(db, ctx, row, body))


@router.delete("/variants/{variant_id}", status_code=204)
def delete_product_variant(
    variant_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = get_variant(db, ctx.tenant_id, variant_id)
    if not row:
        raise HTTPException(status_code=404, detail="变体不存在")
    delete_variant(db, row)


@router.get("/{product_id}/price-entries", response_model=list[PriceBookEntryOut])
def list_product_price_entries(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return [PriceBookEntryOut.model_validate(i) for i in list_product_entries(db, ctx, product_id)]
