#!/usr/bin/env bash
# fix-all.sh — Behebt alle 3 gefundenen Probleme auf einmal
# Ausführen auf dem Server: bash scripts/fix-all.sh
set -euo pipefail

POSTGRES_CONTAINER="postgres-rag"
POSTGRES_PASSWORD="***POSTGRES_PASSWORD_REMOVED***"
APP_NETWORK="zoc8g4socc0ww80w4s080g4s"
N8N_CONTAINER="n8n-zoc8g4socc0ww80w4s080g4s"
N8N_URL="https://workflows.eppcom.de"
N8N_USER="admin"
N8N_PASS="***N8N_PASSWORD_REMOVED***"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Farben
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
err()  { echo -e "${RED}[FEHLER]${NC} $*"; }
info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

echo ""
echo "========================================================"
echo "  Hetzner RAG Platform — Vollständiger Fix"
echo "========================================================"
echo ""

# ─── SCHRITT 1: SQL-Migrationen auf postgres-rag ────────────────────────────
echo "SCHRITT 1/3: SQL-Migrationen ausführen"
echo "──────────────────────────────────────"

run_sql() {
    local label="$1"
    local sql="$2"
    info "  → $label ..."
    if docker exec -i "$POSTGRES_CONTAINER" \
        env PGPASSWORD="$POSTGRES_PASSWORD" \
        psql -U postgres -d postgres -v ON_ERROR_STOP=1 <<< "$sql" \
        > /tmp/sql-output.txt 2>&1; then
        ok "  $label abgeschlossen"
    else
        err "  $label FEHLGESCHLAGEN:"
        cat /tmp/sql-output.txt | sed 's/^/    /'
        exit 1
    fi
}

run_sql_file() {
    local label="$1"
    local file="$2"
    info "  → $label ..."
    if docker exec -i "$POSTGRES_CONTAINER" \
        env PGPASSWORD="$POSTGRES_PASSWORD" \
        psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
        < "$file" > /tmp/sql-output.txt 2>&1; then
        ok "  $label abgeschlossen"
    else
        err "  $label FEHLGESCHLAGEN:"
        cat /tmp/sql-output.txt | sed 's/^/    /'
        exit 1
    fi
}

# 001 Extensions
run_sql_file "001_extensions.sql" "$PROJECT_DIR/sql/001_extensions.sql"

# 002 Public Schema
run_sql_file "002_public_schema.sql" "$PROJECT_DIR/sql/002_public_schema.sql"

# 004 Funktionen
run_sql_file "004_functions.sql" "$PROJECT_DIR/sql/004_functions.sql"

# 005 Rollen — Passwords aus Umgebung setzen
RAG_APP_PASS="$(openssl rand -hex 20)"
RAG_RO_PASS="$(openssl rand -hex 20)"
RAG_ADMIN_PASS="$(openssl rand -hex 20)"

run_sql "005_roles.sql (Rollen anlegen)" "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_app') THEN
        CREATE ROLE rag_app WITH LOGIN PASSWORD '$RAG_APP_PASS';
    ELSE
        ALTER ROLE rag_app WITH PASSWORD '$RAG_APP_PASS';
    END IF;
END\$\$;

DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_readonly') THEN
        CREATE ROLE rag_readonly WITH LOGIN PASSWORD '$RAG_RO_PASS';
    ELSE
        ALTER ROLE rag_readonly WITH PASSWORD '$RAG_RO_PASS';
    END IF;
END\$\$;

DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_admin') THEN
        CREATE ROLE rag_admin WITH LOGIN PASSWORD '$RAG_ADMIN_PASS' CREATEROLE;
    ELSE
        ALTER ROLE rag_admin WITH PASSWORD '$RAG_ADMIN_PASS';
    END IF;
END\$\$;

GRANT USAGE ON SCHEMA public TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rag_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rag_app;

GRANT USAGE ON SCHEMA public TO rag_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rag_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO rag_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO rag_app;

CREATE OR REPLACE FUNCTION public.grant_tenant_permissions(p_schema TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS \$\$
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO rag_app', p_schema);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO rag_app', p_schema);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO rag_readonly', p_schema);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_app', p_schema);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO rag_readonly', p_schema);
END;
\$\$;
"

# Passwords speichern (für spätere Nutzung)
cat > /tmp/rag-db-credentials.txt <<EOF
RAG Datenbank-Credentials (generiert am $(date))
================================================
rag_app     Password: $RAG_APP_PASS
rag_readonly Password: $RAG_RO_PASS
rag_admin   Password: $RAG_ADMIN_PASS

Datenbank-Host (intern): postgres-rag:5432
Datenbank: postgres
EOF
chmod 600 /tmp/rag-db-credentials.txt
ok "  Credentials gespeichert in /tmp/rag-db-credentials.txt"

# Migration-Status prüfen
info "  → Migrations-Check ..."
TENANT_TABLE=$(docker exec "$POSTGRES_CONTAINER" \
    env PGPASSWORD="$POSTGRES_PASSWORD" \
    psql -U postgres -d postgres -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='tenants';" 2>/dev/null || echo "0")

if [ "$TENANT_TABLE" = "1" ]; then
    ok "  public.tenants Tabelle vorhanden ✓"
else
    err "  public.tenants fehlt noch — Migration fehlgeschlagen"
    exit 1
fi

FUNC_COUNT=$(docker exec "$POSTGRES_CONTAINER" \
    env PGPASSWORD="$POSTGRES_PASSWORD" \
    psql -U postgres -d postgres -tAc \
    "SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='create_tenant';" 2>/dev/null || echo "0")

if [ "$FUNC_COUNT" = "1" ]; then
    ok "  public.create_tenant() Funktion vorhanden ✓"
else
    err "  create_tenant() fehlt — Migration 004 fehlgeschlagen"
    exit 1
fi

echo ""

# ─── SCHRITT 2: postgres-rag ins App-Netz hängen ────────────────────────────
echo "SCHRITT 2/3: postgres-rag mit App-Netzwerk verbinden"
echo "──────────────────────────────────────────────────────"

# Prüfen ob schon verbunden
ALREADY_CONNECTED=$(docker network inspect "$APP_NETWORK" \
    --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null \
    | grep -c "postgres-rag" || true)

if [ "$ALREADY_CONNECTED" -gt "0" ]; then
    ok "  postgres-rag ist bereits im Netz $APP_NETWORK"
else
    info "  → Verbinde postgres-rag mit $APP_NETWORK ..."
    if docker network connect "$APP_NETWORK" "$POSTGRES_CONTAINER" 2>&1; then
        ok "  postgres-rag jetzt im Netz $APP_NETWORK ✓"
    else
        err "  Netzwerk-Verbindung fehlgeschlagen"
        exit 1
    fi
fi

# Verbindung von n8n zu postgres-rag testen
info "  → Teste Verbindung n8n → postgres-rag ..."
if docker exec "$N8N_CONTAINER" \
    nc -z postgres-rag 5432 2>/dev/null; then
    ok "  n8n kann postgres-rag auf Port 5432 erreichen ✓"
else
    # Fallback: ping test
    if docker exec "$N8N_CONTAINER" \
        ping -c1 -W2 postgres-rag > /dev/null 2>&1; then
        ok "  postgres-rag ist von n8n aus erreichbar (ping) ✓"
    else
        err "  Verbindungstest fehlgeschlagen — Container evtl. neu starten nötig"
    fi
fi

echo ""

# ─── SCHRITT 3: n8n Workflows importieren ───────────────────────────────────
echo "SCHRITT 3/3: n8n RAG-Workflows importieren"
echo "──────────────────────────────────────────"

# n8n API Login (Session Cookie holen)
info "  → Authentifiziere bei n8n API ..."
LOGIN_RESPONSE=$(curl -s -c /tmp/n8n-cookies.txt \
    -X POST "${N8N_URL}/rest/login" \
    -H "Content-Type: application/json" \
    -d "{\"emailOrLdapLoginName\": \"${N8N_USER}\", \"password\": \"${N8N_PASS}\"}" \
    -w "\n%{http_code}" 2>/dev/null || echo -e "\n000")

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -1)

if [ "$HTTP_CODE" != "200" ]; then
    err "  n8n Login fehlgeschlagen (HTTP $HTTP_CODE)"
    err "  Workflows müssen manuell importiert werden: ${N8N_URL}/workflow/new"
    echo "  → Datei 1: $PROJECT_DIR/n8n/rag-ingestion-workflow.json"
    echo "  → Datei 2: $PROJECT_DIR/n8n/rag-query-workflow.json"
else
    ok "  n8n Login erfolgreich"

    # Ingestion Workflow importieren
    import_workflow() {
        local name="$1"
        local file="$2"

        # Existiert Workflow bereits?
        EXISTING=$(curl -s -b /tmp/n8n-cookies.txt \
            "${N8N_URL}/rest/workflows" 2>/dev/null \
            | python3 -c "
import json,sys
data=json.load(sys.stdin)
workflows=data.get('data', data) if isinstance(data, dict) else data
print(next((w['id'] for w in workflows if w.get('name','')=='$name'), ''))
" 2>/dev/null || echo "")

        if [ -n "$EXISTING" ]; then
            ok "  Workflow '$name' existiert bereits (ID: $EXISTING)"
            return
        fi

        info "  → Importiere '$name' ..."
        IMPORT_RESULT=$(curl -s -b /tmp/n8n-cookies.txt \
            -X POST "${N8N_URL}/rest/workflows" \
            -H "Content-Type: application/json" \
            -d @"$file" \
            -w "\n%{http_code}" 2>/dev/null)

        IMP_CODE=$(echo "$IMPORT_RESULT" | tail -1)
        IMP_BODY=$(echo "$IMPORT_RESULT" | head -1)

        if [ "$IMP_CODE" = "200" ] || [ "$IMP_CODE" = "201" ]; then
            WF_ID=$(echo "$IMP_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id','?'))" 2>/dev/null || echo "?")
            ok "  Workflow '$name' importiert (ID: $WF_ID)"

            # Workflow aktivieren
            if curl -s -b /tmp/n8n-cookies.txt \
                -X PATCH "${N8N_URL}/rest/workflows/${WF_ID}" \
                -H "Content-Type: application/json" \
                -d '{"active": true}' > /dev/null 2>&1; then
                ok "  Workflow '$name' aktiviert ✓"
            else
                info "  Workflow '$name' bitte manuell aktivieren"
            fi
        else
            err "  Import von '$name' fehlgeschlagen (HTTP $IMP_CODE)"
            info "  → Manuell importieren: ${N8N_URL}/workflow/new"
        fi
    }

    import_workflow "RAG Document Ingestion" "$PROJECT_DIR/n8n/rag-ingestion-workflow.json"
    import_workflow "RAG Query"              "$PROJECT_DIR/n8n/rag-query-workflow.json"

    rm -f /tmp/n8n-cookies.txt
fi

echo ""
echo "========================================================"
echo "  ABGESCHLOSSEN — Zusammenfassung"
echo "========================================================"
echo ""

# Finaler Status-Check
echo "Container-Netzwerk (postgres-rag):"
docker network inspect "$APP_NETWORK" \
    --format '  Netz $APP_NETWORK: {{range .Containers}}{{.Name}} {{end}}' 2>/dev/null \
    | fold -s -w 80
echo ""

echo "Datenbank-Tabellen (postgres-rag):"
docker exec "$POSTGRES_CONTAINER" \
    env PGPASSWORD="$POSTGRES_PASSWORD" \
    psql -U postgres -d postgres -c \
    "\dt public.*" 2>/dev/null | sed 's/^/  /'

echo ""
echo "Nächste Schritte:"
echo "  1. Test-Tenant anlegen:  bash scripts/create-tenant.sh test-kunde 'Test' test@test.de"
echo "  2. n8n Workflows prüfen: ${N8N_URL}/workflows"
echo "  3. RAG-Pfad testen:      bash scripts/test-rag-path.sh"
echo ""
echo "DB-Credentials: cat /tmp/rag-db-credentials.txt"
echo ""
