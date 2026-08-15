"""外部 Webhook 入口。"""

from fastapi import APIRouter

from app.routers.webhooks import douyin

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
router.include_router(douyin.router)
