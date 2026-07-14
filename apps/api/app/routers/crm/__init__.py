"""CRM 路由包。"""

from fastapi import APIRouter

from app.routers.crm import (
    activities,
    addresses,
    assignment_rules,
    attachments,
    campaigns,
    contracts,
    customer_pools,
    customers,
    deals,
    export_router,
    import_router,
    lead_pools,
    lead_scoring,
    leads,
    notifications,
    number_rules,
    nurture,
    orders,
    payments,
    pipelines,
    products,
    quotes,
    sales_profiles,
    schema,
    tags,
    tasks,
    team_members,
    territories,
    views,
)

router = APIRouter(prefix="/crm", tags=["crm"])
router.include_router(leads.router)
router.include_router(lead_pools.router)
router.include_router(lead_scoring.router)
router.include_router(nurture.router)
router.include_router(assignment_rules.router)
router.include_router(customers.router)
router.include_router(customer_pools.router)
router.include_router(activities.router)
router.include_router(territories.router)
router.include_router(sales_profiles.router)
router.include_router(tasks.router)
router.include_router(campaigns.router)
router.include_router(schema.router)
router.include_router(views.router)
router.include_router(import_router.router)
router.include_router(export_router.router)
router.include_router(pipelines.router)
router.include_router(deals.router)
router.include_router(products.router)
router.include_router(quotes.router)
router.include_router(contracts.router)
router.include_router(orders.router)
router.include_router(payments.router)
router.include_router(number_rules.router)
router.include_router(attachments.router)
router.include_router(addresses.router)
router.include_router(tags.router)
router.include_router(team_members.router)
router.include_router(notifications.router)


@router.get("/health")
def crm_health():
    return {"status": "ok"}
