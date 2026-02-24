#!/bin/bash
# check-prerequisites.sh — Prüft alle benötigten Tools und Konfigurationen
# Wird automatisch beim Session-Start ausgeführt

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

ok()   { echo -e "  ${GREEN}✓${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC}  $1"; ERRORS=$((ERRORS+1)); }
warn() { echo -e "  ${YELLOW}!${NC}  $1"; WARNINGS=$((WARNINGS+1)); }
info() { echo -e "  ${BLUE}→${NC}  $1"; }

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Hetzner RAG Platform — Prerequisite Check   ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# ── Tools ───────────────────────────────────────────────────────────────
echo "Tools:"

if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    ok "Docker $DOCKER_VER"
else
    fail "Docker nicht installiert → https://docs.docker.com/engine/install/"
fi

if docker compose version &>/dev/null 2>&1; then
    ok "Docker Compose (Plugin)"
elif command -v docker-compose &>/dev/null; then
    warn "docker-compose (alt) gefunden — empfehle Docker Compose Plugin"
else
    fail "Docker Compose nicht verfügbar"
fi

if command -v aws &>/dev/null; then
    AWS_VER=$(aws --version 2>&1 | grep -oP '\d+\.\d+\.\d+' | head -1)
    ok "AWS CLI $AWS_VER (für Hetzner S3)"
else
    warn "AWS CLI fehlt — für Backup-Scripts benötigt"
    info "Installieren: pip3 install awscli"
fi

if command -v psql &>/dev/null; then
    ok "psql (PostgreSQL Client)"
else
    warn "psql nicht lokal installiert — nur via Docker nutzbar"
fi

if command -v curl &>/dev/null; then
    ok "curl"
else
    fail "curl fehlt — apt install curl"
fi

if command -v jq &>/dev/null; then
    ok "jq (JSON-Parser)"
else
    warn "jq fehlt (optional) — apt install jq"
fi

# ── .env Datei ─────────────────────────────────────────────────────────
echo ""
echo ".env Konfiguration:"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_DIR/.env" ]; then
    ok ".env Datei vorhanden"

    # Pflichtfelder prüfen
    check_env() {
        local key="$1"
        local val
        val=$(grep -E "^${key}=" "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2- | xargs || echo "")
        if [ -z "$val" ] || [[ "$val" == *"HIER"* ]] || [[ "$val" == *"AENDERN"* ]]; then
            fail "$key fehlt oder noch nicht konfiguriert"
        else
            ok "$key gesetzt"
        fi
    }

    check_env "DOMAIN"
    check_env "POSTGRES_PASSWORD"
    check_env "N8N_ENCRYPTION_KEY"
    check_env "TYPEBOT_SECRET"
    check_env "S3_ACCESS_KEY"
    check_env "S3_SECRET_KEY"
    check_env "OLLAMA_BASE_URL"
else
    fail ".env nicht gefunden"
    info "Erstellen mit: cp coolify/env-templates/server1.env.example .env"
    info "Dann alle Werte in .env ausfüllen (DOMAIN, Passwörter, S3-Keys)"
fi

# ── Docker Status ───────────────────────────────────────────────────────
echo ""
echo "Docker Status:"

if docker info &>/dev/null 2>&1; then
    ok "Docker Daemon läuft"
    CONTAINER_COUNT=$(docker ps -q 2>/dev/null | wc -l)
    info "$CONTAINER_COUNT Container laufend"

    # Coolify-Netz prüfen
    if docker network inspect coolify &>/dev/null 2>&1; then
        ok "coolify Docker-Netz existiert"
    else
        warn "coolify Docker-Netz fehlt — wird von Coolify beim Start erstellt"
        info "Manuell: docker network create coolify"
    fi

    # Postgres prüfen
    PG=$(docker ps -q --filter "name=postgres" 2>/dev/null | head -1)
    if [ -n "$PG" ]; then
        ok "PostgreSQL Container läuft"
    else
        warn "Kein PostgreSQL Container gefunden"
    fi

    # n8n prüfen
    N8N=$(docker ps -q --filter "name=n8n" 2>/dev/null | head -1)
    if [ -n "$N8N" ]; then
        ok "n8n Container läuft"
    else
        warn "Kein n8n Container gefunden"
    fi

    # Typebot prüfen
    TB=$(docker ps -q --filter "name=typebot" 2>/dev/null | head -1)
    if [ -n "$TB" ]; then
        ok "Typebot Container läuft"
    else
        warn "Kein Typebot Container gefunden"
    fi
else
    fail "Docker Daemon nicht erreichbar"
fi

# ── Ports ───────────────────────────────────────────────────────────────
echo ""
echo "Port-Status:"

check_port() {
    local port="$1"
    local desc="$2"
    if ss -tlnp 2>/dev/null | grep -q ":${port} " || netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
        ok "Port $port offen ($desc)"
    else
        warn "Port $port nicht belegt ($desc) — Traefik/Service gestartet?"
    fi
}

check_port 80  "HTTP / ACME"
check_port 443 "HTTPS"

# Postgres darf NICHT extern erreichbar sein
if ss -tlnp 2>/dev/null | grep -q ":5432 "; then
    LISTENER=$(ss -tlnp 2>/dev/null | grep ":5432 ")
    if echo "$LISTENER" | grep -q "0.0.0.0"; then
        fail "PostgreSQL hört auf 0.0.0.0:5432 — SICHERHEITSRISIKO! Nur intern erlaubt"
    else
        ok "PostgreSQL hört nur intern (nicht 0.0.0.0)"
    fi
fi

# ── Zusammenfassung ─────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}  Alles bereit! Führe /setup aus.${NC}"
elif [ "$ERRORS" -eq 0 ]; then
    echo -e "${YELLOW}  $WARNINGS Warnung(en) — Setup möglich, aber prüfe die Warnungen.${NC}"
else
    echo -e "${RED}  $ERRORS Fehler + $WARNINGS Warnung(en) — bitte beheben bevor du /setup startest.${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

exit $ERRORS
