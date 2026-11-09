"""Testy API bez skutočného whisper.cpp a ffmpeg (obe sú nahradené mockom)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from app.services import whisper_client
from app.services.whisper_client import InferenceResult

API_KEY = "sk-test"
AUTH = {"Authorization": f"Bearer {API_KEY}"}


class FakeWhisper:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.healthy = True

    async def health(self) -> bool:
        return self.healthy

    async def inference(self, wav: Path, **kwargs) -> InferenceResult:
        self.calls.append(kwargs)
        if kwargs["response_format"] in ("json", "verbose_json"):
            return InferenceResult(b'{"text": "Ahoj svet."}', "application/json")
        return InferenceResult(b"Ahoj svet.", "text/plain")

    async def close(self) -> None:
        pass


@pytest.fixture
def fake_whisper(monkeypatch: pytest.MonkeyPatch) -> FakeWhisper:
    fake = FakeWhisper()
    monkeypatch.setattr(whisper_client, "WhisperClient", lambda *a, **k: fake)
    import app.main as main_module
    monkeypatch.setattr(main_module, "WhisperClient", lambda *a, **k: fake)

    async def fake_to_wav(src: Path, settings: Settings) -> Path:
        return src

    import app.api.transcriptions as tr
    monkeypatch.setattr(tr, "to_wav16k", fake_to_wav)
    return fake


@pytest.fixture
def client(fake_whisper: FakeWhisper):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        api_keys=[API_KEY], max_upload_mb=1, _env_file=None
    )
    with TestClient(app) as c:
        yield c


def _audio(size: int = 100):
    return {"file": ("test.mp3", b"\x00" * size, "audio/mpeg")}


def test_missing_api_key(client: TestClient) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio())
    assert resp.status_code == 401
    assert "error" in resp.json()


def test_wrong_api_key(client: TestClient) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(),
                       headers={"Authorization": "Bearer zly"})
    assert resp.status_code == 401


def test_transcription_json(client: TestClient, fake_whisper: FakeWhisper) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(),
                       data={"model": "whisper-1"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"text": "Ahoj svet."}
    assert fake_whisper.calls[0]["language"] == "sk"
    assert fake_whisper.calls[0]["translate"] is False


def test_transcription_text_format(client: TestClient) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(),
                       data={"response_format": "text", "language": "en"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.text == "Ahoj svet."
    assert resp.headers["content-type"].startswith("text/plain")


def test_translation_uses_translate(client: TestClient, fake_whisper: FakeWhisper) -> None:
    resp = client.post("/v1/audio/translations", files=_audio(), headers=AUTH)
    assert resp.status_code == 200
    assert fake_whisper.calls[0]["translate"] is True
    assert fake_whisper.calls[0]["language"] == "auto"


def test_invalid_language(client: TestClient) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(),
                       data={"language": "Slovak!"}, headers=AUTH)
    assert resp.status_code == 400


def test_upload_too_large(client: TestClient) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(2 * 1024 * 1024), headers=AUTH)
    assert resp.status_code == 413


def test_empty_upload(client: TestClient) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(0), headers=AUTH)
    assert resp.status_code == 400


def test_models(client: TestClient) -> None:
    resp = client.get("/v1/models", headers=AUTH)
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()["data"]]
    assert "whisper-1" in ids


def test_health(client: TestClient, fake_whisper: FakeWhisper) -> None:
    assert client.get("/health").status_code == 200
    fake_whisper.healthy = False
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["whisper_backend"] is False
