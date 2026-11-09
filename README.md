# Whisper API

Lokálny server na prepis reči s OpenAI-kompatibilným API. Beží nad [whisper.cpp](https://github.com/ggml-org/whisper.cpp) s modelom `large-v3-turbo` a je optimalizovaný pre Linux server iba s CPU.

```
klient (OpenAI SDK / curl)
   │  Authorization: Bearer <API kľúč>
   ▼
whisper-api      FastAPI, 0.0.0.0:8000        (whisper-api.service)
   │  ffmpeg → 16 kHz mono WAV
   ▼
whisper-server   whisper.cpp, 127.0.0.1:8081  (whisper-cpp.service)
   └─ ggml-large-v3-turbo-q5_0.bin
```

## Endpointy

| Metóda | Cesta                       | Popis                                         |
|--------|-----------------------------|-----------------------------------------------|
| POST   | `/v1/audio/transcriptions`  | prepis (`file`, `language`, `prompt`, `response_format`, `temperature`) |
| POST   | `/v1/audio/translations`    | preklad do angličtiny                         |
| GET    | `/v1/models`                | zoznam modelov                                |
| GET    | `/health`                   | stav API aj whisper.cpp (bez autentifikácie)  |

`response_format` podporuje: `json`, `text`, `srt`, `vtt`, `verbose_json`.
Ak klient nepošle `language`, použije sa `DEFAULT_LANGUAGE` (predvolene `sk`).

## Inštalácia na server (Debian/Ubuntu)

```bash
git clone <repo> whisper && cd whisper
sudo ./scripts/install.sh
```

Skript zostaví whisper.cpp, stiahne model (~550 MB), vytvorí `/opt/whisper/.env` s vygenerovaným API kľúčom a spustí obe systemd služby.

Voliteľné premenné: `WHISPER_CPP_REF` (odporúčam pripnúť release tag), `MODEL` (napr. `large-v3-turbo-q8_0`), `PREFIX`.

### Rozloženie na serveri

```
/opt/whisper/
├── app/          # kód + .venv
├── whisper.cpp/  # build/bin/whisper-server
├── models/       # ggml modely
└── .env          # konfigurácia + API kľúče (chmod 600)
```

### Správa

```bash
systemctl status whisper-cpp whisper-api
journalctl -u whisper-api -f
sudo systemctl restart whisper-cpp whisper-api   # po zmene .env
```

## Použitie

```bash
curl http://server:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer $API_KEY" \
  -F file=@nahravka.mp3 \
  -F model=whisper-1 \
  -F response_format=srt
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://server:8000/v1", api_key="sk-...")
with open("nahravka.mp3", "rb") as f:
    print(client.audio.transcriptions.create(model="whisper-1", file=f, language="sk").text)
```

## Vývoj

```bash
uv sync
uv run pytest
uv run ruff check .
```

Lokálne spustenie (whisper-server musí bežať na `WHISPER_URL`):

```bash
cp .env.example .env
uv run uvicorn app.main:app --reload
```

## Poznámky

- whisper.cpp spracúva requesty **sériovo**: súbežné requesty čakajú vo fronte.
- Na CPU trvá prepis dlhej nahrávky aj niekoľko minút; limit nastavíš cez `REQUEST_TIMEOUT`. Ak je pred serverom reverse proxy, zvýš timeout aj tam.
- Port 8000 je vystavený na všetkých rozhraniach. Ak k serveru nepristupuješ iba z dôveryhodnej siete, daj pred neho reverse proxy s TLS (napr. Caddy alebo nginx).
