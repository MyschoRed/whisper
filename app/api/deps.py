from fastapi import Request

from app.services.whisper_client import WhisperClient


def get_whisper(request: Request) -> WhisperClient:
    return request.app.state.whisper
