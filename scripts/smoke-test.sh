#!/usr/bin/env bash
# Rýchly end-to-end test nasadeného API.
# Použitie: API_KEY=sk-... scripts/smoke-test.sh [base-url] [audio-súbor]
#   napr.   API_KEY=sk-... scripts/smoke-test.sh https://mh.azeta.sk nahravka.mp3
set -uo pipefail

BASE="${1:-https://mh.azeta.sk}"
FILE="${2:-}"
: "${API_KEY:?Nastav API_KEY (napr. API_KEY=sk-... $0)}"

AUTH=(-H "Authorization: Bearer ${API_KEY}")

# RESOLVE=87.197.112.46 → obíde lokálnu DNS a ide cez verejnú IP (reverse proxy)
if [[ -n "${RESOLVE:-}" ]]; then
    HOST="${BASE#*://}"; HOST="${HOST%%/*}"
    AUTH+=(--resolve "${HOST}:443:${RESOLVE}")
fi

echo "== GET /v1/models"
curl -s -m 15 -w "\nHTTP %{http_code}\n" "${AUTH[@]}" "$BASE/v1/models"

if [[ -z "$FILE" ]]; then
    if command -v say >/dev/null; then
        FILE="$(mktemp -t whisper-smoke).aiff"
        # slovenský hlas Laura (inak by slovenský text čítal anglický hlas)
        VOICE=$(say -v '?' | grep -q '^Laura' && echo Laura || echo "")
        say ${VOICE:+-v "$VOICE"} -o "$FILE" "Dobrý deň, toto je test prepisu reči." \
            && echo "(vygenerovaná vzorka $FILE, hlas ${VOICE:-predvolený})"
    else
        echo "Zadaj audio súbor ako 2. parameter." >&2
        exit 1
    fi
fi

echo "== POST /v1/audio/transcriptions ($FILE, $(du -h "$FILE" | cut -f1))"
curl -s -m 3600 "${AUTH[@]}" \
    -w "\nHTTP %{http_code} | upload %{size_upload} B | čas %{time_total} s\n" \
    "$BASE/v1/audio/transcriptions" \
    -F "file=@${FILE}" -F model=whisper-1 -F response_format=json
