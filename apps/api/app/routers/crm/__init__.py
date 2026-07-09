"""CRM 路由包。"""

from fastapi import APIRouter

from app.routers.crm import (
    activities,
    campaigns,
    customers,
    import_router,
    leads,
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


@router.get("/health")
def crm_health():
    return {"status": "ok"}
