"""Úprava výstupu z whisper.cpp do podoby, akú vracia OpenAI API.

whisper.cpp vracia text segmentov s úvodnou medzerou a zalomeniami riadkov medzi
segmentmi (" Prvá veta.\\n Druhá veta.\\n"). OpenAI vracia súvislý orezaný text.
"""

import json
import re

from app.schemas import ResponseFormat

_WS = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Spojí riadky do jedného textu a zjednotí medzery."""
    return _WS.sub(" ", text).strip()


def normalize(content: bytes, response_format: ResponseFormat) -> bytes:
    """Upraví telo odpovede pre formáty json, verbose_json a text; srt/vtt nechá tak."""
    if response_format is ResponseFormat.text:
        return clean_text(content.decode("utf-8", errors="replace")).encode()

    if response_format in (ResponseFormat.json, ResponseFormat.verbose_json):
        try:
            data = json.loads(content)
        except ValueError:
            return content
        if isinstance(data.get("text"), str):
            data["text"] = clean_text(data["text"])
        for segment in data.get("segments") or []:
            if isinstance(segment, dict) and isinstance(segment.get("text"), str):
                segment["text"] = clean_text(segment["text"])
        return json.dumps(data, ensure_ascii=False).encode()

    return content
