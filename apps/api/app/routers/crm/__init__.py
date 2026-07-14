"""CRM 路由包。"""

from fastapi import APIRouter

from app.routers.crm import (
    activities,
    attachments,
    campaigns,
    contracts,
    customers,
    deals,
    import_router,
    leads,
    number_rules,
    orders,
    payments,
    pipelines,
    products,
    quotes,
    sales_profiles,
    schema,
    tasks,
    territories,
    views,
)

router = APIRouter(prefix="/crm", tags=["crm"])
router.include_router(leads.router)
router.include_router(customers.router)
router.include_router(activities.router)
router.include_router(territories.router)
router.include_router(sales_profiles.router)
router.include_router(tasks.router)
router.include_router(campaigns.router)
router.include_router(schema.router)
router.include_router(views.router)
router.include_router(import_router.router)
router.include_router(pipelines.router)
router.include_router(deals.router)
router.include_router(products.router)
router.include_router(quotes.router)
router.include_router(contracts.router)
router.include_router(orders.router)
router.include_router(payments.router)
router.include_router(number_rules.router)
router.include_router(attachments.router)


@router.get("/health")
def crm_health():
    return {"status": "ok"}
