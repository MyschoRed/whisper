"""Testy API bez skutočného whisper.cpp a ffmpeg (obe sú nahradené mockom)."""

import json
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
        # whisper.cpp vracia úvodnú medzeru a zalomenia medzi segmentmi
        if kwargs["response_format"] == "verbose_json":
            body = {"text": " Ahoj\n svet.\n", "segments": [{"id": 0, "text": " Ahoj\n"}]}
            return InferenceResult(json.dumps(body).encode(), "application/json")
        if kwargs["response_format"] == "json":
            return InferenceResult(b'{"text": " Ahoj\\n svet.\\n"}', "application/json")
        return InferenceResult(b" Ahoj\n svet.\n", "text/plain")

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


def _make_client(**overrides):
    app = create_app()
    overrides.setdefault("max_upload_mb", 1)
    settings = Settings(api_keys=[API_KEY], _env_file=None, **overrides)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture
def client(fake_whisper: FakeWhisper):
    with _make_client() as c:
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


def test_verbose_json_segments_cleaned(client: TestClient) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(),
                       data={"response_format": "verbose_json"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "Ahoj svet."
    assert body["segments"][0]["text"] == "Ahoj"


def test_translation_disabled_for_turbo(client: TestClient, fake_whisper: FakeWhisper) -> None:
    resp = client.post("/v1/audio/translations", files=_audio(), headers=AUTH)
    assert resp.status_code == 400
    assert "turbo" in resp.json()["error"]["message"]
    assert fake_whisper.calls == []


def test_translation_uses_translate(fake_whisper: FakeWhisper) -> None:
    with _make_client(model_name="whisper-large-v3") as client:
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


def test_docs_disabled_by_default(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_short_audio_uses_smaller_window(client: TestClient, fake_whisper: FakeWhisper) -> None:
    resp = client.post("/v1/audio/transcriptions", files=_audio(), headers=AUTH)
    assert resp.status_code == 200
    assert fake_whisper.calls[-1]["audio_ctx"] == 768


def test_long_audio_uses_full_window(fake_whisper: FakeWhisper) -> None:
    # 20 s pri 32 000 B/s
    with _make_client(max_upload_mb=2) as c:
        resp = c.post("/v1/audio/transcriptions", files=_audio(20 * 32000 + 44), headers=AUTH)
    assert resp.status_code == 200
    assert fake_whisper.calls[-1]["audio_ctx"] == 0


def test_short_audio_ctx_disabled(fake_whisper: FakeWhisper) -> None:
    with _make_client(short_audio_ctx=0) as c:
        resp = c.post("/v1/audio/transcriptions", files=_audio(), headers=AUTH)
    assert resp.status_code == 200
    assert fake_whisper.calls[-1]["audio_ctx"] == 0
