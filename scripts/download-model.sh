#!/usr/bin/env bash
# Stiahne ggml model pre whisper.cpp z Hugging Face.
# Použitie: scripts/download-model.sh [názov-modelu] [cieľový-priečinok]
#   napr.   scripts/download-model.sh large-v3-turbo-q5_0 /opt/whisper/models
set -euo pipefail

MODEL="${1:-large-v3-turbo-q5_0}"
DEST_DIR="${2:-/opt/whisper/models}"
URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${MODEL}.bin"
DEST="${DEST_DIR}/ggml-${MODEL}.bin"

mkdir -p "$DEST_DIR"

if [[ -f "$DEST" ]]; then
    echo "Model už existuje: $DEST"
    exit 0
fi

echo "Sťahujem $URL"
curl -fL --retry 3 --progress-bar -o "${DEST}.part" "$URL"
mv "${DEST}.part" "$DEST"
echo "Hotovo: $DEST ($(du -h "$DEST" | cut -f1))"
