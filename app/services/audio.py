"""Konverzia ľubovoľného audio/video vstupu na 16 kHz mono WAV, ktorý vyžaduje whisper.cpp."""

import asyncio
import logging
import tempfile
from pathlib import Path

from fastapi import UploadFile, status

from app.config import Settings
from app.errors import api_error

log = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024


async def save_upload(upload: UploadFile, dest_dir: Path, max_bytes: int) -> Path:
    """Uloží upload na disk po častiach a stráži maximálnu veľkosť."""
    suffix = Path(upload.filename or "audio").suffix or ".bin"
    dest = dest_dir / f"input{suffix}"
    written = 0
    with dest.open("wb") as fh:
        while chunk := await upload.read(CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                raise api_error(
                    413,  # Content Too Large
                    f"Súbor je väčší ako povolený limit {max_bytes // (1024 * 1024)} MB.",
                    param="file",
                )
            fh.write(chunk)
    if written == 0:
        raise api_error(status.HTTP_400_BAD_REQUEST, "Nahraný súbor je prázdny.", param="file")
    return dest


async def to_wav16k(src: Path, settings: Settings) -> Path:
    """Spustí ffmpeg a vráti cestu k 16 kHz mono PCM WAV."""
    dest = src.with_name("audio.wav")
    proc = await asyncio.create_subprocess_exec(
        settings.ffmpeg_bin, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        "-y", str(dest),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.warning("ffmpeg zlyhal: %s", stderr.decode(errors="replace").strip())
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "Súbor sa nepodarilo dekódovať ako audio. Podporované sú bežné audio/video formáty.",
            param="file",
        )
    return dest


def workdir() -> tempfile.TemporaryDirectory[str]:
    """Dočasný priečinok pre jeden request (zmaže sa po spracovaní)."""
    return tempfile.TemporaryDirectory(prefix="whisper-api-")


# 16 kHz × 1 kanál × 2 B (pcm_s16le) – formát, ktorý vyrába to_wav16k
_WAV_BYTES_PER_SECOND = 16000 * 2
_WAV_HEADER = 44


def wav_duration(wav: Path) -> float:
    """Dĺžka 16 kHz mono PCM WAV v sekundách (podľa veľkosti súboru)."""
    return max(wav.stat().st_size - _WAV_HEADER, 0) / _WAV_BYTES_PER_SECOND
