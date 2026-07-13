import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal
from app.routers import admin, agent, analytics, assistants, auth, brand_settings, content, crm, dashboard, knowledge, llm_settings, me, team, templates, tenant, wechat_settings
from app.services.publish_service import process_due_scheduled_async

logger = logging.getLogger(__name__)


async def _publish_scheduler_loop() -> None:
    while True:
        await asyncio.sleep(settings.PUBLISH_POLL_SEC)
        db = SessionLocal()
        try:
            count = await process_due_scheduled_async(db)
            if count:
                logger.info("Processed %s scheduled publish task(s)", count)
        except Exception:
            logger.exception("Publish scheduler error")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_published_dir.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(_publish_scheduler_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="智营获客 API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    detail = "服务器内部错误，请查看 API 日志"
    msg = str(exc).lower()
    if "does not exist" in msg or "undefinedtable" in msg or "no such table" in msg:
        detail = "数据库表未初始化，请在服务器执行 alembic upgrade head"
    elif "type \"vector\"" in msg or "pg_extension" in msg or "vector" in msg and "does not exist" in msg:
        detail = "知识库向量扩展未就绪，已降级为 JSON 索引；请更新 API 或安装 pgvector"
    elif "marketing" in msg and ("industry" in msg or "顾问" in msg):
        detail = "营销顾问配置未初始化，请执行 alembic upgrade head"
    return JSONResponse(status_code=500, content={"detail": detail})

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(assistants.router, prefix="/api/v1")
app.include_router(llm_settings.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(wechat_settings.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(brand_settings.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(team.router, prefix="/api/v1")
app.include_router(tenant.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(crm.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")

settings.storage_published_dir.mkdir(parents=True, exist_ok=True)
exports_dir = Path(settings.STORAGE_DIR) / "exports"
exports_dir.mkdir(parents=True, exist_ok=True)
app.mount("/storage/published", StaticFiles(directory=str(settings.storage_published_dir)), name="published")
app.mount("/storage/exports", StaticFiles(directory=str(exports_dir)), name="exports")


@app.get("/health")
def health():
    return {"status": "ok"}
