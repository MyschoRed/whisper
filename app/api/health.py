from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_whisper
from app.schemas import Health
from app.services.whisper_client import WhisperClient

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
async def health(
    response: Response,
    whisper: Annotated[WhisperClient, Depends(get_whisper)],
) -> Health:
    backend_ok = await whisper.health()
    if not backend_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Health(status="ok" if backend_ok else "degraded", whisper_backend=backend_ok)
