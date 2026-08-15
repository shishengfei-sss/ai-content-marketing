"""小程序 / 买家端 API。"""

from fastapi import APIRouter

from app.routers.mp import shop as mp_shop

router = APIRouter(prefix="/mp", tags=["mp"])
router.include_router(mp_shop.router)
