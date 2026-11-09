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
| POST   | `/v1/audio/translations`    | preklad do angličtiny (nie s modelmi „turbo“, pozri nižšie) |
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

- **Preklad a modely „turbo“:** `large-v3-turbo` nebol trénovaný na preklad, preto je `/v1/audio/translations` pri ňom predvolene vypnutý a vracia `400` s vysvetlením. Ak preklad potrebuješ, nasaď napr. `large-v3` (`MODEL=large-v3-q5_0`, `MODEL_NAME=whisper-large-v3`) alebo nastav `TRANSLATIONS_ENABLED=true`.
- Text v odpovediach `json`, `verbose_json` a `text` je orezaný a spojený do jedného riadku ako pri OpenAI. Formáty `srt` a `vtt` ostávajú nezmenené.
- **Krátke nahrávky:** whisper vždy kóduje celé 30 s okno, takže aj 3 s nahrávka trvá na 2 jadrách ~30 s. Nahrávky do `SHORT_AUDIO_MAX_SECONDS` (14 s) sa preto posielajú s `audio_ctx=768` (polovičné okno, ~2× rýchlejšie). Vypneš `SHORT_AUDIO_CTX=0`; hodnoty pod 768 výrazne zhoršujú presnosť.
- whisper.cpp spracúva requesty **sériovo**: súbežné requesty čakajú vo fronte.
- Na CPU trvá prepis dlhej nahrávky aj niekoľko minút; limit nastavíš cez `REQUEST_TIMEOUT`. Ak je pred serverom reverse proxy, zvýš timeout aj tam.
- API aj whisper-server počúvajú iba na `127.0.0.1`; zvonku sú dostupné len cez nginx (`deploy/nginx/mh.azeta.sk.conf`).
- Služby majú nízku prioritu CPU (`Nice`, `CPUWeight`) a strop RAM (`MemoryMax`), aby nespomalili ostatné aplikácie na serveri.

## Nginx a bezpečnosť

`deploy/nginx/mh.azeta.sk.conf` pridáva nový `server` blok iba pre `mh.azeta.sk`. Ostatné stránky sa nemenia.

- prepúšťa iba `/v1/…`; `/`, `/docs` a všetko ostatné vráti 404
- `/health` je dostupné iba z lokálnej siete
- limit počtu requestov na IP: 6/min na prepis, 30/min na ostatné `/v1/`, max. 4 súbežné spojenia (pri prekročení `429`)
- skutočnú IP klienta preberá z reverse proxy `10.0.10.22` (`X-Forwarded-For`)

```bash
sudo cp deploy/nginx/mh.azeta.sk.conf /etc/nginx/sites-available/whisper
sudo ln -s /etc/nginx/sites-available/whisper /etc/nginx/sites-enabled/whisper
sudo nginx -t && sudo systemctl reload nginx
```

Na reverse proxy (TLS) pre `mh.azeta.sk` treba povoliť veľké uploady a dlhé timeouty: `client_max_body_size 200M; proxy_read_timeout 1800s; proxy_send_timeout 1800s; proxy_request_buffering off;`. Bez toho proxy odmietne súbory nad cca 10–50 MB (`413`) a ukončí prepis po 60 s (`504`).

Interná DNS musí smerovať `mh.azeta.sk` na reverse proxy (ako `hub.azeta.sk`), nie priamo na `10.0.10.13`, kde HTTPS nebeží. Dovtedy sa dá z LAN testovať cez verejnú IP:

```bash
RESOLVE=87.197.112.46 API_KEY=sk-... ./scripts/smoke-test.sh https://mh.azeta.sk nahravka.wav
```
