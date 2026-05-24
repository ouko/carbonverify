from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.core.logging import get_logger
from app.database import engine
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.projects import router as projects_router
from app.api.data_sources import router as data_sources_router
from app.api.calculations import router as calculations_router
from app.api.reports import router as reports_router
from app.api.review_queue import router as review_queue_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.websocket import router as websocket_router
from app.api.uploads import router as uploads_router
from app.api.webhooks import router as webhooks_router
from app.api.vvb_liaison import router as vvb_router
from app.api.orchestrator import router as orchestrator_router

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", environment=settings.ENVIRONMENT)
    yield
    logger.info("app_shutdown")
    await engine.dispose()


app = FastAPI(
    title="CarbonVerify API",
    description="Automated carbon credit MRV preparation platform",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(data_sources_router)
app.include_router(calculations_router)
app.include_router(reports_router)
app.include_router(review_queue_router)
app.include_router(dashboard_router)
app.include_router(health_router)
app.include_router(websocket_router)
app.include_router(uploads_router)
app.include_router(webhooks_router)
app.include_router(vvb_router)
app.include_router(orchestrator_router)


@app.get("/")
async def root():
    return {"message": "CarbonVerify API", "version": "1.1.0"}
