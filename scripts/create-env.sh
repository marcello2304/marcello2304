#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# create-env.sh  —  Erstellt .env für Hetzner RAG Platform (Server 1)
# Aufruf: bash scripts/create-env.sh
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$DIR/.env"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Hetzner RAG Platform — .env Generator${RESET}"
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo ""

# Abbruch wenn .env bereits existiert und nicht leer
if [[ -f "$ENV_FILE" ]] && [[ -s "$ENV_FILE" ]]; then
  echo -e "${YELLOW}⚠  .env existiert bereits: $ENV_FILE${RESET}"
  read -rp "   Überschreiben? (j/N): " OVERWRITE
  [[ "$OVERWRITE" =~ ^[jJ]$ ]] || { echo "Abgebrochen."; exit 0; }
fi

# ── Pflichtabfragen ──────────────────────────────────────────────

ask() {
  local VAR="$1" PROMPT="$2" DEFAULT="$3"
  local INPUT
  if [[ -n "$DEFAULT" ]]; then
    read -rp "  $PROMPT [$DEFAULT]: " INPUT
    echo "${INPUT:-$DEFAULT}"
  else
    while true; do
      read -rp "  $PROMPT: " INPUT
      [[ -n "$INPUT" ]] && { echo "$INPUT"; return; }
      echo -e "  ${RED}Pflichtfeld — bitte einen Wert eingeben.${RESET}" >&2
    done
  fi
}

ask_secret() {
  local VAR="$1" PROMPT="$2"
  local INPUT
  while true; do
    read -rsp "  $PROMPT: " INPUT; echo ""
    [[ -n "$INPUT" ]] && { echo "$INPUT"; return; }
    echo -e "  ${RED}Pflichtfeld — bitte einen Wert eingeben.${RESET}" >&2
  done
}

echo -e "${CYAN}── Allgemein ────────────────────────────────────${RESET}"
DOMAIN=$(ask DOMAIN "Domain (z.B. beispiel.de)" "eppcom.de")
ADMIN_IP=$(ask ADMIN_IP "Server 1 IP" "94.130.170.167")
ACME_EMAIL=$(ask ACME_EMAIL "E-Mail für Let's Encrypt" "eppler@eppcom.de")

echo ""
echo -e "${CYAN}── Hetzner Object Storage (S3) ──────────────────${RESET}"
echo -e "  ${YELLOW}→ Hetzner Cloud Console → Object Storage → Zugangsdaten erstellen${RESET}"
S3_ACCESS_KEY=$(ask_secret S3_ACCESS_KEY "S3 Access Key")
S3_SECRET_KEY=$(ask_secret S3_SECRET_KEY "S3 Secret Key")
S3_BUCKET=$(ask S3_BUCKET "S3 Bucket (Typebot Assets)" "typebot-assets")
S3_REGION=$(ask S3_REGION "S3 Region" "eu-central-003")
S3_ENDPOINT=$(ask S3_ENDPOINT "S3 Endpoint" "https://nbg1.your-objectstorage.com")

echo ""
echo -e "${CYAN}── Ollama (Server 2) ────────────────────────────${RESET}"
OLLAMA_BASE_URL=$(ask OLLAMA_BASE_URL "Ollama URL" "https://ollama.${DOMAIN}")
OLLAMA_API_KEY=$(ask_secret OLLAMA_API_KEY "Ollama Bearer-Token (Nginx auth auf Server 2)")

echo ""
echo -e "${CYAN}── SMTP — Ionos ─────────────────────────────────${RESET}"
SMTP_USER=$(ask SMTP_USER "SMTP Benutzer (E-Mail)" "eppler@eppcom.de")
SMTP_PASSWORD=$(ask_secret SMTP_PASSWORD "SMTP Passwort (Ionos)")

# ── Secrets automatisch generieren ──────────────────────────────
echo ""
echo -e "${CYAN}── Secrets werden generiert …${RESET}"
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 40)
N8N_ENCRYPTION_KEY=$(openssl rand -hex 16)
TYPEBOT_SECRET=$(openssl rand -hex 16)
N8N_ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9' | head -c 22)

# ── .env schreiben ───────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
# Hetzner RAG Platform — Server 1 Konfiguration
# Generiert: $(date +%Y-%m-%d)
# NICHT in Git committen!

# ═══════════════════════════════════════════════
# ALLGEMEIN
# ═══════════════════════════════════════════════
DOMAIN=${DOMAIN}
ADMIN_IP=${ADMIN_IP}
ACME_EMAIL=${ACME_EMAIL}
TZ=Europe/Berlin

# ═══════════════════════════════════════════════
# POSTGRESQL
# ═══════════════════════════════════════════════
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_USER=postgres
POSTGRES_DB=app_db
POSTGRES_CONTAINER=postgres-rag

# ═══════════════════════════════════════════════
# N8N
# ═══════════════════════════════════════════════
N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
N8N_ADMIN_USER=admin
N8N_ADMIN_PASSWORD=${N8N_ADMIN_PASSWORD}
N8N_WEBHOOK_URL=https://n8n.${DOMAIN}

# ═══════════════════════════════════════════════
# TYPEBOT
# ═══════════════════════════════════════════════
TYPEBOT_SECRET=${TYPEBOT_SECRET}
NEXTAUTH_URL=https://builder.${DOMAIN}
NEXT_PUBLIC_VIEWER_URL=https://bot.${DOMAIN}

# ═══════════════════════════════════════════════
# HETZNER OBJECT STORAGE (S3-kompatibel)
# ═══════════════════════════════════════════════
S3_ACCESS_KEY=${S3_ACCESS_KEY}
S3_SECRET_KEY=${S3_SECRET_KEY}
S3_BUCKET=${S3_BUCKET}
S3_REGION=${S3_REGION}
S3_ENDPOINT=${S3_ENDPOINT}
S3_BACKUP_BUCKET=rag-backups
S3_BACKUP_ENDPOINT=${S3_ENDPOINT}

# ═══════════════════════════════════════════════
# OLLAMA (Server 2)
# ═══════════════════════════════════════════════
OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
OLLAMA_API_KEY=${OLLAMA_API_KEY}

# ═══════════════════════════════════════════════
# SMTP — Ionos
# ═══════════════════════════════════════════════
SMTP_HOST=smtp.ionos.de
SMTP_PORT=587
SMTP_USER=${SMTP_USER}
SMTP_PASSWORD=${SMTP_PASSWORD}
SMTP_FROM=${SMTP_USER}

# ═══════════════════════════════════════════════
# BACKUP
# ═══════════════════════════════════════════════
BACKUP_DIR=/opt/backups/postgres
RETENTION_DAYS=30
EOF

chmod 600 "$ENV_FILE"

echo ""
echo -e "${GREEN}✔  .env erstellt: $ENV_FILE${RESET}"
echo -e "${GREEN}✔  Berechtigungen gesetzt: chmod 600${RESET}"
echo ""
echo -e "${BOLD}── Generierte Zugangsdaten (jetzt notieren!) ────${RESET}"
echo -e "  n8n Admin:          admin / ${N8N_ADMIN_PASSWORD}"
echo -e "  PostgreSQL Passwort: ${POSTGRES_PASSWORD}"
echo ""
echo -e "${YELLOW}  → Setup starten: bash setup.sh${RESET}"
echo ""
