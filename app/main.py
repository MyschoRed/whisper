import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health, models, transcriptions
from app.config import get_settings
from app.errors import http_exception_handler
from app.services.whisper_client import WhisperClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not settings.api_keys:
        logging.getLogger(__name__).warning(
            "API_KEYS je prázdne – všetky requesty budú odmietnuté."
        )

    app.state.whisper = WhisperClient(settings.whisper_url, settings.request_timeout)
    try:
        yield
    finally:
        await app.state.whisper.close()


def create_app() -> FastAPI:
    docs = get_settings().enable_docs
    app = FastAPI(
        title="Whisper API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(transcriptions.router)
    return app


app = create_app()
