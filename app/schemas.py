from enum import Enum

from pydantic import BaseModel


class ResponseFormat(str, Enum):
    json = "json"
    text = "text"
    srt = "srt"
    vtt = "vtt"
    verbose_json = "verbose_json"


MEDIA_TYPES: dict[ResponseFormat, str] = {
    ResponseFormat.json: "application/json",
    ResponseFormat.verbose_json: "application/json",
    ResponseFormat.text: "text/plain; charset=utf-8",
    ResponseFormat.srt: "application/x-subrip; charset=utf-8",
    ResponseFormat.vtt: "text/vtt; charset=utf-8",
}


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "local"


class ModelList(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


class Health(BaseModel):
    status: str
    whisper_backend: bool
