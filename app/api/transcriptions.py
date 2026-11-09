"""POST /v1/audio/transcriptions a /v1/audio/translations (OpenAI-kompatibilné)."""

import logging
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response

from app.api.deps import get_whisper
from app.auth import require_api_key
from app.config import Settings, get_settings
from app.errors import api_error
from app.schemas import MEDIA_TYPES, ResponseFormat
from app.services.audio import save_upload, to_wav16k, workdir
from app.services.whisper_client import WhisperClient

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["audio"], dependencies=[Depends(require_api_key)])

# Klient môže poslať napr. "whisper-1" (OpenAI SDK) – akceptujeme akýkoľvek názov,
# server má načítaný jeden model.


@router.post("/transcriptions")
async def create_transcription(
    file: Annotated[UploadFile, File()],
    settings: Annotated[Settings, Depends(get_settings)],
    whisper: Annotated[WhisperClient, Depends(get_whisper)],
    model: Annotated[str, Form()] = "whisper-1",
    language: Annotated[str | None, Form()] = None,
    prompt: Annotated[str | None, Form()] = None,
    response_format: Annotated[ResponseFormat, Form()] = ResponseFormat.json,
    temperature: Annotated[float, Form(ge=0.0, le=1.0)] = 0.0,
) -> Response:
    return await _run(
        file, settings, whisper,
        language=language or settings.default_language,
        prompt=prompt, response_format=response_format,
        temperature=temperature, translate=False,
    )


@router.post("/translations")
async def create_translation(
    file: Annotated[UploadFile, File()],
    settings: Annotated[Settings, Depends(get_settings)],
    whisper: Annotated[WhisperClient, Depends(get_whisper)],
    model: Annotated[str, Form()] = "whisper-1",
    prompt: Annotated[str | None, Form()] = None,
    response_format: Annotated[ResponseFormat, Form()] = ResponseFormat.json,
    temperature: Annotated[float, Form(ge=0.0, le=1.0)] = 0.0,
) -> Response:
    """Preklad do angličtiny (ako OpenAI); jazyk zdroja sa detekuje automaticky."""
    return await _run(
        file, settings, whisper,
        language="auto", prompt=prompt, response_format=response_format,
        temperature=temperature, translate=True,
    )


async def _run(
    file: UploadFile,
    settings: Settings,
    whisper: WhisperClient,
    *,
    language: str,
    prompt: str | None,
    response_format: ResponseFormat,
    temperature: float,
    translate: bool,
) -> Response:
    if not _valid_language(language):
        raise api_error(status.HTTP_400_BAD_REQUEST,
                        "Neplatný kód jazyka (očakáva sa ISO-639-1, napr. 'sk', alebo 'auto').",
                        param="language")

    started = time.perf_counter()
    with workdir() as tmp:
        src = await save_upload(file, Path(tmp), settings.max_upload_bytes)
        wav = await to_wav16k(src, settings)
        result = await whisper.inference(
            wav,
            response_format=response_format.value,
            language=language,
            translate=translate,
            prompt=prompt,
            temperature=temperature,
        )

    log.info("prepis hotový: file=%s format=%s lang=%s translate=%s trvanie=%.1fs",
             file.filename, response_format.value, language, translate,
             time.perf_counter() - started)
    return Response(content=result.content, media_type=MEDIA_TYPES[response_format])


def _valid_language(code: str) -> bool:
    return code == "auto" or (len(code) in (2, 3) and code.isalpha() and code.islower())
