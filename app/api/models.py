from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.schemas import ModelInfo, ModelList

router = APIRouter(prefix="/v1", tags=["models"], dependencies=[Depends(require_api_key)])


@router.get("/models", response_model=ModelList)
async def list_models(settings: Annotated[Settings, Depends(get_settings)]) -> ModelList:
    # "whisper-1" je alias kvôli kompatibilite s OpenAI klientmi.
    return ModelList(data=[ModelInfo(id=settings.model_name), ModelInfo(id="whisper-1")])
