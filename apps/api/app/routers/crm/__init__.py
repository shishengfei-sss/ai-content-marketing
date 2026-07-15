"""CRM 路由包。"""

from fastapi import APIRouter

from app.routers.crm import (
    activities,
    addresses,
    approval_rules,
    assignment_rules,
    attachments,
    campaigns,
    contract_templates,
    contracts,
    customer_pools,
    customers,
    deals,
    deliveries,
    export_router,
    import_router,
    invoices,
    lead_pools,
    lead_scoring,
    leads,
    notifications,
    number_rules,
    nurture,
    orders,
    payments,
    pipelines,
    price_books,
    product_categories,
    products,
    quotes,
    sales_profiles,
    schema,
    segments,
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
router.include_router(segments.router)
router.include_router(schema.router)
router.include_router(views.router)
router.include_router(import_router.router)
router.include_router(export_router.router)
router.include_router(pipelines.router)
router.include_router(deals.router)
router.include_router(products.router)
router.include_router(product_categories.router)
router.include_router(price_books.router)
router.include_router(quotes.router)
router.include_router(contracts.router)
router.include_router(contract_templates.router)
router.include_router(orders.router)
router.include_router(approval_rules.router)
router.include_router(deliveries.router)
router.include_router(invoices.router)
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
