"""Klient na HTTP server z whisper.cpp (binárka `whisper-server`, endpoint POST /inference)."""

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import status

from app.errors import api_error

log = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    content: bytes
    content_type: str


class WhisperClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            resp = await self._client.get("/health", timeout=3.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def inference(
        self,
        wav: Path,
        *,
        response_format: str,
        language: str,
        translate: bool = False,
        prompt: str | None = None,
        temperature: float = 0.0,
    ) -> InferenceResult:
        data = {
            "response_format": response_format,
            "language": language,
            "translate": "true" if translate else "false",
            "temperature": str(temperature),
        }
        if prompt:
            data["prompt"] = prompt

        try:
            with wav.open("rb") as fh:
                resp = await self._client.post(
                    "/inference",
                    data=data,
                    files={"file": (wav.name, fh, "audio/wav")},
                )
        except httpx.TimeoutException as exc:
            raise api_error(status.HTTP_504_GATEWAY_TIMEOUT,
                            "Prepis trval dlhšie ako povolený timeout.", "server_error") from exc
        except httpx.HTTPError as exc:
            log.error("whisper-server nedostupný: %s", exc)
            raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Prepisovací backend je nedostupný.", "server_error") from exc

        if resp.status_code != 200:
            log.error("whisper-server vrátil %s: %s", resp.status_code, resp.text[:500])
            raise api_error(status.HTTP_502_BAD_GATEWAY,
                            "Prepisovací backend vrátil chybu.", "server_error")

        return InferenceResult(
            content=resp.content,
            content_type=resp.headers.get("content-type", "application/json"),
        )
