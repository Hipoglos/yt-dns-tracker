#!/usr/bin/env bash
# yt-dns-tracker — one-command installer for Debian/Ubuntu
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/main/install.sh)

set -euo pipefail
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

REPO_URL="https://github.com/YOUR_USERNAME/yt-dns-tracker"
INSTALL_DIR="/srv/yt-dns-tracker"
DATA_DIR="/srv/yt-dns-tracker/data"

log()  { echo -e "${CYAN}▸${RESET} $*"; }
ok()   { echo -e "${GREEN}✓${RESET} $*"; }
die()  { echo -e "${RED}✗ ERROR:${RESET} $*" >&2; exit 1; }

echo -e "\n${BOLD}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║   YT-DNS Tracker — Installer         ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════╝${RESET}\n"

# ── Check / install dependencies ─────────────────────────────────────────────
log "Checking dependencies…"

if ! command -v docker &>/dev/null; then
  log "Installing Docker…"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  ok "Docker installed."
else
  ok "Docker found: $(docker --version | cut -d' ' -f3 | tr -d ',')"
fi

if ! docker compose version &>/dev/null 2>&1; then
  log "Installing Docker Compose plugin…"
  sudo apt-get update -qq
  sudo apt-get install -y docker-compose-plugin
  ok "Docker Compose installed."
else
  ok "Docker Compose found."
fi

if ! command -v git &>/dev/null; then
  log "Installing git…"
  sudo apt-get update -qq && sudo apt-get install -y git
fi

# ── Create /srv structure ─────────────────────────────────────────────────────
log "Creating /srv/yt-dns-tracker structure…"
sudo mkdir -p "$DATA_DIR"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"
ok "Folders ready:"
ok "  /srv/yt-dns-tracker        <- source code"
ok "  /srv/yt-dns-tracker/data   <- persistent data (config, domains, logs)"

# ── Clone or update ───────────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  log "Updating existing installation in ${INSTALL_DIR}…"
  git -C "$INSTALL_DIR" pull --ff-only
else
  log "Cloning repository to ${INSTALL_DIR}…"
  TMP=$(mktemp -d)
  git clone "$REPO_URL" "$TMP/repo"
  cp -r "$TMP/repo/." "$INSTALL_DIR/"
  rm -rf "$TMP"
fi

cd "$INSTALL_DIR"

# ── Build & start ─────────────────────────────────────────────────────────────
log "Building Docker image (this may take a minute on first run)…"
docker compose build --quiet

log "Starting YT-DNS Tracker…"
docker compose up -d

# ── Done ──────────────────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${BOLD}${GREEN}✓ Installation complete!${RESET}"
echo -e ""
echo -e "  ${BOLD}Folder layout on this host:${RESET}"
echo -e "  ${CYAN}/srv/yt-dns-tracker/${RESET}           source code + docker-compose.yml"
echo -e "  ${CYAN}/srv/yt-dns-tracker/data/${RESET}      config.json, youtube_domains.txt, run.log"
echo ""
echo -e "  UI available at: ${CYAN}http://${LOCAL_IP}:8080${RESET}"
echo ""
echo -e "  Configure AdGuard and GitHub in the web UI, then hit ${BOLD}Sync Now${RESET}."
echo ""
echo -e "  To view logs:  ${BOLD}docker compose -f /srv/yt-dns-tracker/docker-compose.yml logs -f${RESET}"
echo -e "  To stop:       ${BOLD}docker compose -f /srv/yt-dns-tracker/docker-compose.yml down${RESET}"
echo -e "  To update:     ${BOLD}cd /srv/yt-dns-tracker && git pull && docker compose up -d --build${RESET}"
echo ""
