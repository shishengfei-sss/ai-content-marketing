"""买家端商城 API · /mp/shop/*。"""

from fastapi import APIRouter

from app.routers.mp.shop import auth, bookings, claim, entitlements, invoices, orders, payments, products, service_offers, store

router = APIRouter(prefix="/shop", tags=["mp-shop"])
router.include_router(auth.router)
router.include_router(store.router)
router.include_router(products.router)
router.include_router(orders.router)
router.include_router(payments.router)
router.include_router(entitlements.router)
router.include_router(bookings.router)
router.include_router(service_offers.router)
router.include_router(invoices.router)
router.include_router(claim.router)
