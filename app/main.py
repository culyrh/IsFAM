from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.anti_spoofing import router as anti_spoofing_router
from app.api.routes.auth import router as auth_router
from app.api.routes.demo import router as demo_router
from app.api.routes.demo import web_router as demo_web_router
from app.api.routes.family import router as family_router
from app.api.routes.voice import router as voice_router
from app.api.routes.voice_session import router as voice_session_router
from app.core.config import get_settings
from app.db.session import init_db


def configure_logging() -> None:
    """Configure simple stdout logging for local development and servers."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local SQLite tables when the API server starts."""

    init_db(settings)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="IsFAM AI model based speaker verification API server.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_origin_regex=settings.cors_allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for load balancers and simple server checks."""

    return {"status": "ok"}


app.include_router(demo_web_router)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(voice_router, prefix=settings.api_v1_prefix)
app.include_router(family_router, prefix=settings.api_v1_prefix)
app.include_router(anti_spoofing_router, prefix=settings.api_v1_prefix)
app.include_router(voice_session_router, prefix=settings.api_v1_prefix)
app.include_router(demo_router, prefix=settings.api_v1_prefix)
