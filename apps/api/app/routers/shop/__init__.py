"""内容获客商城 · 商家端 API（租户内 shop.*）。"""

from fastapi import APIRouter

from app.routers.shop import (
    analytics,
    bookings,
    buyers,
    channel_settings,
    channels,
    columns,
    content_files,
    digital_packages,
    entitlements,
    invoices,
    onboarding,
    orders,
    payment_config,
    permissions_router,
    platform_categories,
    products,
    refunds,
    roles,
    members,
    service_offers,
    settings_payment,
    settings_sms,
    stores,
    subscription,
    verifications,
)

router = APIRouter(prefix="/shop", tags=["shop"])
router.include_router(permissions_router.router)
router.include_router(analytics.router)
router.include_router(roles.router)
router.include_router(members.router)
router.include_router(onboarding.router)
router.include_router(subscription.router)
router.include_router(products.router)
router.include_router(platform_categories.router)
router.include_router(columns.router)
router.include_router(digital_packages.router)
router.include_router(content_files.router)
router.include_router(service_offers.router)
router.include_router(orders.router)
router.include_router(buyers.router)
router.include_router(entitlements.router)
router.include_router(refunds.router)
router.include_router(payment_config.router)
router.include_router(settings_payment.router)
router.include_router(settings_sms.router)
router.include_router(verifications.router)
router.include_router(bookings.router)
router.include_router(invoices.router)
router.include_router(stores.router)
router.include_router(channels.router)
router.include_router(channel_settings.router)


@router.get("/health")
def shop_health():
    return {"status": "ok", "module": "shop"}
