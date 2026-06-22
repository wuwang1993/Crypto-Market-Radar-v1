#!/usr/bin/env bash
set -euo pipefail

# ── Crypto Market Radar Bot — Install Script ──────────────────────────
# Usage:  chmod +x install.sh && ./install.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }

INSTALL_DIR="${INSTALL_DIR:-/opt/crypto-market-radar}"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "═══════════════════════════════════════════"
echo "  Crypto Market Radar Bot — Installer"
echo "═══════════════════════════════════════════"
echo ""

# ── 1. Pre-flight checks ────────────────────────────────────────────
log "Running pre-flight checks ..."

command -v python3 >/dev/null 2>&1 || err "python3 not found"
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
[[ $(echo "$PY_VER >= 3.11" | bc 2>/dev/null || echo 0) -eq 1 ]] || \
    warn "Python $PY_VER detected; 3.11+ recommended"

# ── 2. Copy files ────────────────────────────────────────────────────
log "Installing to $INSTALL_DIR ..."
if [[ "$SRC_DIR" != "$INSTALL_DIR" ]]; then
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
        "$SRC_DIR/" "$INSTALL_DIR/"
fi

# ── 3. Ensure data/logs directories ──────────────────────────────────
mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/logs"
touch "$INSTALL_DIR/data/.gitkeep" 2>/dev/null || true

# ── 4. Create virtual environment ─────────────────────────────────────
cd "$INSTALL_DIR"
if [[ ! -d ".venv" ]]; then
    log "Creating virtual environment ..."
    python3 -m venv .venv
fi
log "Installing dependencies ..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .

# ── 5. Check token file ──────────────────────────────────────────────
TOKEN_FILE="$INSTALL_DIR/data/tg_bot_token.txt"
if [[ ! -f "$TOKEN_FILE" ]]; then
    warn "Token file not found at $TOKEN_FILE"
    warn "Please create it with your Telegram bot token (single line, no whitespace)"
fi

# ── 6. Install systemd service ────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/crypto-radar.service"
if [[ -f "$INSTALL_DIR/systemd/crypto-radar.service" ]]; then
    log "Installing systemd service ..."
    cp "$INSTALL_DIR/systemd/crypto-radar.service" "$SERVICE_FILE"
    sed -i "s|%i|${TG_CHAT_ID:-}|g" "$SERVICE_FILE"
    systemctl daemon-reload
    systemctl enable crypto-radar.service
    log "Service enabled — start with: systemctl start crypto-radar"
else
    warn "systemd unit file not found; skipping service install"
fi

# ── 7. Done ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo -e "  ${GREEN}Installation complete!${NC}"
echo ""
echo "  Next steps:"
echo "  1. Set TG_CHAT_ID env: export TG_CHAT_ID=your_chat_id"
echo "  2. Ensure token file: $TOKEN_FILE"
echo "  3. Start: systemctl start crypto-radar"
echo "  4. Status: systemctl status crypto-radar"
echo "  5. Logs: journalctl -u crypto-radar -f"
echo "═══════════════════════════════════════════"
