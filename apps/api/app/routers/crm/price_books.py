"""价目表 API（v1.0 P1-I）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import (
    PriceBookCreate,
    PriceBookEntryCreate,
    PriceBookEntryOut,
    PriceBookOut,
    PriceBookUpdate,
)
from app.services.crm.product_catalog_service import (
    create_entry,
    create_price_book,
    delete_entry,
    delete_price_book,
    list_entries,
    list_price_books,
    require_price_book,
    update_price_book,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/price-books", tags=["crm-price-books"])


@router.get("", response_model=list[PriceBookOut])
def get_price_books(
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return [PriceBookOut.model_validate(i) for i in list_price_books(db, ctx)]


@router.post("", response_model=PriceBookOut, status_code=201)
def post_price_book(
    body: PriceBookCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return PriceBookOut.model_validate(create_price_book(db, ctx, body))


@router.get("/{book_id}", response_model=PriceBookOut)
def get_price_book_detail(
    book_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return PriceBookOut.model_validate(require_price_book(db, ctx, book_id))


@router.patch("/{book_id}", response_model=PriceBookOut)
def patch_price_book(
    book_id: UUID,
    body: PriceBookUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = require_price_book(db, ctx, book_id)
    return PriceBookOut.model_validate(update_price_book(db, ctx, row, body))


@router.delete("/{book_id}", status_code=204)
def remove_price_book(
    book_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = require_price_book(db, ctx, book_id)
    delete_price_book(db, row)


@router.get("/{book_id}/entries", response_model=list[PriceBookEntryOut])
def get_entries(
    book_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return [PriceBookEntryOut.model_validate(i) for i in list_entries(db, ctx, book_id)]


@router.post("/{book_id}/entries", response_model=PriceBookEntryOut, status_code=201)
def post_entry(
    book_id: UUID,
    body: PriceBookEntryCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return PriceBookEntryOut.model_validate(create_entry(db, ctx, book_id, body))


@router.delete("/entries/{entry_id}", status_code=204)
def remove_entry(
    entry_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    delete_entry(db, ctx, entry_id)
