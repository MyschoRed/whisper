#!/usr/bin/env bash
# Inštalácia na Debian/Ubuntu server (spúšťať ako root z koreňa repozitára):
#   sudo ./scripts/install.sh
#
# Čo urobí:
#   1. nainštaluje systémové balíky (build nástroje, ffmpeg, python)
#   2. vytvorí systémového usera "whisper" a priečinok /opt/whisper
#   3. stiahne a zostaví whisper.cpp (whisper-server)
#   4. stiahne model
#   5. nainštaluje Python API do venv
#   6. nainštaluje a spustí systemd služby
set -euo pipefail

PREFIX="${PREFIX:-/opt/whisper}"
SERVICE_USER="${SERVICE_USER:-whisper}"
WHISPER_CPP_REPO="${WHISPER_CPP_REPO:-https://github.com/ggml-org/whisper.cpp.git}"
# Odporúčané: pripnúť na konkrétny release tag, napr. WHISPER_CPP_REF=v1.x.y
WHISPER_CPP_REF="${WHISPER_CPP_REF:-master}"
MODEL="${MODEL:-large-v3-turbo-q5_0}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "Spusti ako root (sudo)." >&2
    exit 1
fi

echo "==> Systémové balíky"
apt-get update
apt-get install -y --no-install-recommends \
    build-essential cmake git curl ca-certificates ffmpeg rsync \
    python3 python3-venv python3-pip

echo "==> User a priečinky"
id -u "$SERVICE_USER" &>/dev/null || \
    useradd --system --home-dir "$PREFIX" --shell /usr/sbin/nologin "$SERVICE_USER"
mkdir -p "$PREFIX"/{app,models}

echo "==> whisper.cpp ($WHISPER_CPP_REF)"
if [[ ! -d "$PREFIX/whisper.cpp/.git" ]]; then
    git clone "$WHISPER_CPP_REPO" "$PREFIX/whisper.cpp"
fi
git -C "$PREFIX/whisper.cpp" fetch --tags origin
git -C "$PREFIX/whisper.cpp" checkout "$WHISPER_CPP_REF"
git -C "$PREFIX/whisper.cpp" pull --ff-only 2>/dev/null || true
cmake -S "$PREFIX/whisper.cpp" -B "$PREFIX/whisper.cpp/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_NATIVE=ON \
    -DWHISPER_BUILD_EXAMPLES=ON \
    -DWHISPER_BUILD_TESTS=OFF
cmake --build "$PREFIX/whisper.cpp/build" -j"$(nproc)" --target whisper-server
test -x "$PREFIX/whisper.cpp/build/bin/whisper-server"

echo "==> Model $MODEL"
"$REPO_DIR/scripts/download-model.sh" "$MODEL" "$PREFIX/models"

echo "==> Python API"
rsync -a --delete --exclude '.venv' --exclude '.git' --exclude 'models' \
    --exclude 'whisper.cpp' --exclude '.env' "$REPO_DIR/" "$PREFIX/app/"
python3 -m venv "$PREFIX/app/.venv"
"$PREFIX/app/.venv/bin/pip" install --upgrade pip
"$PREFIX/app/.venv/bin/pip" install "$PREFIX/app"

if [[ ! -f "$PREFIX/.env" ]]; then
    cp "$REPO_DIR/.env.example" "$PREFIX/.env"
    KEY="sk-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    sed -i "s|^API_KEYS=.*|API_KEYS=${KEY}|" "$PREFIX/.env"
    sed -i "s|^WHISPER_MODEL=.*|WHISPER_MODEL=${PREFIX}/models/ggml-${MODEL}.bin|" "$PREFIX/.env"
    sed -i "s|^WHISPER_THREADS=.*|WHISPER_THREADS=$(nproc)|" "$PREFIX/.env"
    echo "Vygenerovaný API kľúč je uložený v $PREFIX/.env (API_KEYS)."
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$PREFIX"
chmod 600 "$PREFIX/.env"

echo "==> systemd"
install -m 644 "$REPO_DIR/deploy/systemd/whisper-cpp.service" /etc/systemd/system/
install -m 644 "$REPO_DIR/deploy/systemd/whisper-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now whisper-cpp.service whisper-api.service

echo
echo "Hotovo. Stav:  systemctl status whisper-cpp whisper-api"
echo "Health check: curl http://127.0.0.1:8000/health"
