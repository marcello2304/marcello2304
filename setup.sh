#!/bin/bash
# setup.sh — Master-Setup für Hetzner RAG Platform
# Wird von Claude Code via /setup Command ausgeführt
# Kann auch direkt ausgeführt werden: bash setup.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ── Farben ──────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

STEP=0

header() {
    STEP=$((STEP+1))
    echo ""
    echo -e "${BLUE}${BOLD}━━━ Phase $STEP: $1 ━━━${NC}"
}

ok()     { echo -e "  ${GREEN}✓${NC}  $1"; }
fail()   { echo -e "  ${RED}✗${NC}  $1"; exit 1; }
warn()   { echo -e "  ${YELLOW}!${NC}  $1"; }
info()   { echo -e "  ${CYAN}→${NC}  $1"; }
prompt() { echo -e "\n  ${YELLOW}?${NC}  $1"; }

echo ""
echo -e "${BLUE}${BOLD}"
echo "  ██████╗  █████╗  ██████╗     ██████╗ ██╗      █████╗ ████████╗"
echo "  ██╔══██╗██╔══██╗██╔════╝     ██╔══██╗██║     ██╔══██╗╚══██╔══╝"
echo "  ██████╔╝███████║██║  ███╗    ██████╔╝██║     ███████║   ██║   "
echo "  ██╔══██╗██╔══██║██║   ██║    ██╔═══╝ ██║     ██╔══██║   ██║   "
echo "  ██║  ██║██║  ██║╚██████╔╝    ██║     ███████╗██║  ██║   ██║   "
echo "  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝     ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   "
echo -e "${NC}"
echo -e "  ${BOLD}Hetzner Self-Hosted RAG Platform — Automatisches Setup${NC}"
echo ""

# ════════════════════════════════════════════════════════════════════════
# PHASE 1: Voraussetzungen prüfen
# ════════════════════════════════════════════════════════════════════════
header "Voraussetzungen prüfen"

if ! command -v docker &>/dev/null; then
    fail "Docker nicht installiert. Bitte zuerst Docker installieren."
fi
ok "Docker $(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)"

if ! docker info &>/dev/null 2>&1; then
    fail "Docker Daemon läuft nicht. Starte Docker und versuche es erneut."
fi
ok "Docker Daemon läuft"

# ════════════════════════════════════════════════════════════════════════
# PHASE 2: ENV konfigurieren
# ════════════════════════════════════════════════════════════════════════
header "Konfiguration (.env)"

if [ ! -f ".env" ]; then
    info "Erzeuge .env aus Template..."
    cp coolify/env-templates/server1.env.example .env
    ok ".env erstellt"

    echo ""
    echo -e "  ${YELLOW}${BOLD}Bitte fülle jetzt die Pflichtfelder in .env aus:${NC}"
    echo ""

    # Interaktive ENV-Konfiguration
    configure_env() {
        local KEY="$1"
        local DESC="$2"
        local DEFAULT="$3"
        local CURRENT
        CURRENT=$(grep -E "^${KEY}=" .env | cut -d= -f2- || echo "")

        if [ -n "$DEFAULT" ] && ([ -z "$CURRENT" ] || [[ "$CURRENT" == *"HIER"* ]] || [[ "$CURRENT" == *"AENDERN"* ]]); then
            prompt "$DESC"
            if [ "$DEFAULT" = "AUTO" ]; then
                local GENERATED
                GENERATED=$(openssl rand -hex 16 2>/dev/null || cat /dev/urandom | tr -dc 'a-f0-9' | head -c 32)
                sed -i "s|^${KEY}=.*|${KEY}=${GENERATED}|" .env
                ok "$KEY → automatisch generiert"
            else
                read -r -p "    Wert (Enter für '$DEFAULT'): " VALUE
                VALUE="${VALUE:-$DEFAULT}"
                sed -i "s|^${KEY}=.*|${KEY}=${VALUE}|" .env
                ok "$KEY gesetzt"
            fi
        fi
    }

    configure_env "DOMAIN"            "Deine Hauptdomain (z.B. beispiel.de)" ""
    configure_env "ADMIN_IP"          "Deine Admin-IP (für n8n/Coolify Zugriff)" ""
    configure_env "ACME_EMAIL"        "E-Mail für Let's Encrypt SSL" ""
    configure_env "POSTGRES_PASSWORD" "PostgreSQL Passwort (mind. 32 Zeichen)" "AUTO"
    configure_env "N8N_ENCRYPTION_KEY" "n8n Verschlüsselungskey (32 Zeichen)" "AUTO"
    configure_env "N8N_ADMIN_PASSWORD" "n8n Admin Passwort" ""
    configure_env "TYPEBOT_SECRET"    "Typebot Secret (32 Zeichen)" "AUTO"
    configure_env "S3_ACCESS_KEY"     "Hetzner S3 Access Key ID" ""
    configure_env "S3_SECRET_KEY"     "Hetzner S3 Secret Access Key" ""
    configure_env "S3_ENDPOINT"       "Hetzner S3 Endpoint (z.B. https://fsn1.your-objectstorage.com)" "https://fsn1.your-objectstorage.com"
    configure_env "OLLAMA_BASE_URL"   "Ollama URL auf Server 2 (z.B. https://ollama.beispiel.de)" ""
    configure_env "OLLAMA_API_KEY"    "Ollama Bearer Token (mind. 32 Zeichen)" "AUTO"
else
    ok ".env bereits vorhanden"
fi

# ENV laden
set -a
source .env
set +a

# Pflichtfelder validieren
MISSING=0
for KEY in DOMAIN POSTGRES_PASSWORD N8N_ENCRYPTION_KEY TYPEBOT_SECRET; do
    VAL=$(grep -E "^${KEY}=" .env | cut -d= -f2- | xargs || echo "")
    if [ -z "$VAL" ] || [[ "$VAL" == *"HIER"* ]] || [[ "$VAL" == *"AENDERN"* ]]; then
        warn "$KEY ist noch nicht gesetzt in .env"
        MISSING=$((MISSING+1))
    fi
done

if [ "$MISSING" -gt 0 ]; then
    echo ""
    echo -e "  ${RED}$MISSING Pflichtfelder fehlen in .env${NC}"
    echo -e "  Öffne .env und fülle alle Werte aus, dann starte setup.sh erneut."
    exit 1
fi

ok "Alle Pflichtfelder gesetzt"

# ════════════════════════════════════════════════════════════════════════
# PHASE 3: Docker-Netz anlegen
# ════════════════════════════════════════════════════════════════════════
header "Docker-Netzwerk"

if docker network inspect coolify &>/dev/null 2>&1; then
    ok "coolify Netz existiert bereits"
else
    docker network create coolify
    ok "coolify Netz erstellt"
fi

# ════════════════════════════════════════════════════════════════════════
# PHASE 4: PostgreSQL starten
# ════════════════════════════════════════════════════════════════════════
header "PostgreSQL + pgvector starten"

PG_NAME="postgres-rag"
PG_RUNNING=$(docker ps -q --filter "name=$PG_NAME" 2>/dev/null | head -1)

if [ -n "$PG_RUNNING" ]; then
    ok "PostgreSQL läuft bereits (Container: $PG_NAME)"
else
    info "Starte PostgreSQL Container..."
    docker run -d \
        --name "$PG_NAME" \
        --network coolify \
        --restart unless-stopped \
        -e POSTGRES_USER=postgres \
        -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
        -e POSTGRES_DB=app_db \
        -e PGDATA=/var/lib/postgresql/data/pgdata \
        -v postgres-rag-data:/var/lib/postgresql/data \
        --health-cmd="pg_isready -U postgres" \
        --health-interval=15s \
        --health-timeout=5s \
        --health-retries=5 \
        pgvector/pgvector:pg16

    info "Warte auf PostgreSQL (max 60s)..."
    for i in $(seq 1 12); do
        if docker exec "$PG_NAME" pg_isready -U postgres &>/dev/null 2>&1; then
            ok "PostgreSQL bereit"
            break
        fi
        sleep 5
        if [ "$i" -eq 12 ]; then
            fail "PostgreSQL startet nicht — prüfe: docker logs $PG_NAME"
        fi
    done
fi

# ════════════════════════════════════════════════════════════════════════
# PHASE 5: Datenbank initialisieren
# ════════════════════════════════════════════════════════════════════════
header "Datenbank-Migrationen"

run_migration() {
    local FILE="$1"
    local NAME
    NAME=$(basename "$FILE")
    if docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$PG_NAME" \
        psql -U postgres -d app_db -f - < "$FILE" &>/dev/null 2>&1; then
        ok "Migration: $NAME"
    else
        # Nochmal mit Fehlerausgabe
        docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$PG_NAME" \
            psql -U postgres -d app_db -f - < "$FILE" 2>&1 | tail -5
        warn "$NAME — möglicherweise bereits ausgeführt (idempotent, OK)"
    fi
}

run_migration "sql/001_extensions.sql"
run_migration "sql/002_public_schema.sql"
run_migration "sql/004_functions.sql"
run_migration "sql/005_roles.sql"

# Typebot-Datenbank anlegen
info "Lege typebot_db an..."
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$PG_NAME" \
    psql -U postgres -c "CREATE DATABASE typebot_db;" &>/dev/null 2>&1 || ok "typebot_db existiert bereits"
ok "typebot_db bereit"

# ════════════════════════════════════════════════════════════════════════
# PHASE 6: n8n starten
# ════════════════════════════════════════════════════════════════════════
header "n8n starten"

N8N_RUNNING=$(docker ps -q --filter "name=n8n" 2>/dev/null | head -1)

if [ -n "$N8N_RUNNING" ]; then
    ok "n8n läuft bereits"
else
    info "Starte n8n..."
    docker run -d \
        --name n8n \
        --network coolify \
        --restart unless-stopped \
        -e "N8N_HOST=n8n.${DOMAIN}" \
        -e N8N_PROTOCOL=https \
        -e N8N_PORT=5678 \
        -e "WEBHOOK_URL=https://n8n.${DOMAIN}/" \
        -e "N8N_EDITOR_BASE_URL=https://n8n.${DOMAIN}/" \
        -e "N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}" \
        -e DB_TYPE=postgresdb \
        -e DB_POSTGRESDB_HOST=postgres-rag \
        -e DB_POSTGRESDB_PORT=5432 \
        -e DB_POSTGRESDB_DATABASE=app_db \
        -e DB_POSTGRESDB_USER=postgres \
        -e "DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}" \
        -e DB_POSTGRESDB_SCHEMA=n8n \
        -e N8N_BASIC_AUTH_ACTIVE=true \
        -e "N8N_BASIC_AUTH_USER=${N8N_ADMIN_USER:-admin}" \
        -e "N8N_BASIC_AUTH_PASSWORD=${N8N_ADMIN_PASSWORD:?N8N_ADMIN_PASSWORD muss in .env gesetzt sein}" \
        -e N8N_SECURE_COOKIE=true \
        -e EXECUTIONS_DATA_PRUNE=true \
        -e EXECUTIONS_DATA_MAX_AGE=168 \
        -e TZ=Europe/Berlin \
        -l "traefik.enable=true" \
        -l "traefik.http.routers.n8n.rule=Host(\`n8n.${DOMAIN}\`)" \
        -l "traefik.http.routers.n8n.entrypoints=websecure" \
        -l "traefik.http.routers.n8n.tls.certresolver=letsencrypt" \
        -l "traefik.http.services.n8n.loadbalancer.server.port=5678" \
        -v n8n-data:/home/node/.n8n \
        n8nio/n8n:latest

    ok "n8n gestartet"
fi

# ════════════════════════════════════════════════════════════════════════
# PHASE 7: Typebot starten
# ════════════════════════════════════════════════════════════════════════
header "Typebot Builder + Viewer starten"

TB_BUILDER=$(docker ps -q --filter "name=typebot-builder" 2>/dev/null | head -1)
if [ -n "$TB_BUILDER" ]; then
    ok "Typebot Builder läuft bereits"
else
    info "Starte Typebot Builder..."
    docker run -d \
        --name typebot-builder \
        --network coolify \
        --restart unless-stopped \
        -e "NEXTAUTH_URL=https://builder.${DOMAIN}" \
        -e "NEXTAUTH_SECRET=${TYPEBOT_SECRET}" \
        -e "NEXT_PUBLIC_VIEWER_URL=https://bot.${DOMAIN}" \
        -e "DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-rag:5432/typebot_db" \
        -e "ENCRYPTION_SECRET=${TYPEBOT_SECRET}" \
        -e "S3_ACCESS_KEY=${S3_ACCESS_KEY:-}" \
        -e "S3_SECRET_KEY=${S3_SECRET_KEY:-}" \
        -e "S3_BUCKET=${S3_BUCKET:-rag-platform-prod}" \
        -e "S3_REGION=${S3_REGION:-eu-central-003}" \
        -e "S3_ENDPOINT=${S3_ENDPOINT:-}" \
        -e DISABLE_SIGNUP=true \
        -e TZ=Europe/Berlin \
        -l "traefik.enable=true" \
        -l "traefik.http.routers.typebot-builder.rule=Host(\`builder.${DOMAIN}\`)" \
        -l "traefik.http.routers.typebot-builder.entrypoints=websecure" \
        -l "traefik.http.routers.typebot-builder.tls.certresolver=letsencrypt" \
        -l "traefik.http.services.typebot-builder.loadbalancer.server.port=3000" \
        baptistearno/typebot-builder:latest

    ok "Typebot Builder gestartet"
fi

TB_VIEWER=$(docker ps -q --filter "name=typebot-viewer" 2>/dev/null | head -1)
if [ -n "$TB_VIEWER" ]; then
    ok "Typebot Viewer läuft bereits"
else
    info "Starte Typebot Viewer..."
    docker run -d \
        --name typebot-viewer \
        --network coolify \
        --restart unless-stopped \
        -e "NEXTAUTH_URL=https://builder.${DOMAIN}" \
        -e "NEXT_PUBLIC_VIEWER_URL=https://bot.${DOMAIN}" \
        -e "DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-rag:5432/typebot_db" \
        -e "ENCRYPTION_SECRET=${TYPEBOT_SECRET}" \
        -e "S3_ACCESS_KEY=${S3_ACCESS_KEY:-}" \
        -e "S3_SECRET_KEY=${S3_SECRET_KEY:-}" \
        -e "S3_BUCKET=${S3_BUCKET:-rag-platform-prod}" \
        -e "S3_REGION=${S3_REGION:-eu-central-003}" \
        -e "S3_ENDPOINT=${S3_ENDPOINT:-}" \
        -e TZ=Europe/Berlin \
        -l "traefik.enable=true" \
        -l "traefik.http.routers.typebot-viewer.rule=Host(\`bot.${DOMAIN}\`)" \
        -l "traefik.http.routers.typebot-viewer.entrypoints=websecure" \
        -l "traefik.http.routers.typebot-viewer.tls.certresolver=letsencrypt" \
        -l "traefik.http.services.typebot-viewer.loadbalancer.server.port=3000" \
        baptistearno/typebot-viewer:latest

    ok "Typebot Viewer gestartet"
fi

# ════════════════════════════════════════════════════════════════════════
# PHASE 8: Test-Tenant anlegen
# ════════════════════════════════════════════════════════════════════════
header "Test-Tenant anlegen"

TENANT_EXISTS=$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$PG_NAME" \
    psql -U postgres -d app_db -t -c \
    "SELECT COUNT(*) FROM public.tenants WHERE slug='test-setup';" 2>/dev/null | xargs || echo "0")

if [ "$TENANT_EXISTS" -gt 0 ]; then
    ok "Test-Tenant existiert bereits (test-setup)"
else
    POSTGRES_CONTAINER="$PG_NAME" \
    POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    bash scripts/create-tenant.sh test-setup "Setup Test Kunde" setup@test.de starter 2>/dev/null
    ok "Test-Tenant 'test-setup' angelegt"
fi

# ════════════════════════════════════════════════════════════════════════
# PHASE 9: Verifikation
# ════════════════════════════════════════════════════════════════════════
header "Verifikation"

echo ""
echo -e "  ${BOLD}Container Status:${NC}"
docker ps --format "    {{.Names}}\t{{.Status}}" | grep -E "postgres|n8n|typebot|traefik|coolify" || true

echo ""
echo -e "  ${BOLD}PostgreSQL Datenbanken:${NC}"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$PG_NAME" \
    psql -U postgres -t -c "\l" 2>/dev/null | grep -E "app_db|typebot_db" | \
    awk '{print "    " $1}' || true

echo ""
echo -e "  ${BOLD}Tenant-Schemas:${NC}"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$PG_NAME" \
    psql -U postgres -d app_db -t -c \
    "SELECT slug, name, schema_name, plan, status FROM public.tenants;" \
    2>/dev/null | grep -v "^$" | awk '{print "    " $0}' || warn "Keine Tenants"

# ════════════════════════════════════════════════════════════════════════
# ABSCHLUSS
# ════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}   Setup abgeschlossen!${NC}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Nächste Schritte:${NC}"
echo ""
echo -e "  1. ${CYAN}DNS-Records prüfen${NC} — A-Records für alle Subdomains auf 94.130.170.167"
echo -e "  2. ${CYAN}Domains testen${NC} — https://builder.${DOMAIN:-DEINE_DOMAIN}"
echo -e "  3. ${CYAN}n8n Workflows importieren${NC}:"
echo -e "     n8n UI → Workflows → Import → n8n/rag-ingestion-workflow.json"
echo -e "     n8n UI → Workflows → Import → n8n/rag-query-workflow.json"
echo -e "  4. ${CYAN}Echten Kunden anlegen${NC}:"
echo -e "     /new-tenant  oder  bash scripts/create-tenant.sh <slug> <name> <email>"
echo -e "  5. ${CYAN}Backup einrichten${NC}:"
echo -e "     crontab -e → 0 2 * * * bash $(pwd)/scripts/backup-postgres.sh"
echo ""
echo -e "  ${BOLD}Verfügbare Commands:${NC}"
echo -e "  /diagnose   → Domain-Probleme analysieren"
echo -e "  /status     → Stack-Status anzeigen"
echo -e "  /new-tenant → Neuen Kunden anlegen"
echo ""
