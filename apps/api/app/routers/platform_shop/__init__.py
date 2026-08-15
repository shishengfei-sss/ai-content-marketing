"""内容获客商城 · 平台运营端 API（platform.shop.*）。"""

from fastapi import APIRouter

from app.routers.platform_shop import (
    analytics,
    categories,
    channel_mappings,
    merchants,
    moderation,
    number_rules,
    onboarding,
    payment_onboarding,
    permissions_router,
    plans,
    product_reviews,
    service_logs,
    settlements,
    sms,
    subscriptions,
)

router = APIRouter(prefix="/admin/shop", tags=["platform-shop"])
router.include_router(permissions_router.router)
router.include_router(analytics.router)
router.include_router(onboarding.router)
router.include_router(service_logs.router)
router.include_router(merchants.catalog_router)
router.include_router(merchants.router)
router.include_router(plans.router)
router.include_router(subscriptions.router)
router.include_router(product_reviews.router)
router.include_router(channel_mappings.router)
router.include_router(categories.router)
router.include_router(number_rules.router)
router.include_router(payment_onboarding.router)
router.include_router(sms.router)
router.include_router(settlements.router)
router.include_router(moderation.router)


@router.get("/health")
def platform_shop_health():
    return {"status": "ok", "module": "platform_shop"}
