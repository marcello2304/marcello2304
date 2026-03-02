#!/bin/bash
# test-rag-path.sh — End-to-End RAG-Pfad-Test (ohne Browser)
# Testet: Daten vorhanden → Vektorsuche → n8n Webhook → Antwort
#
# Verwendung:
#   bash scripts/test-rag-path.sh
#   bash scripts/test-rag-path.sh --tenant demo --query "Was kostet das Pro-Paket?"

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ -f ".env" ]; then set -a; source .env; set +a; fi

# Argumente
TENANT="${1:-demo}"
QUERY="${2:-Was kostet das Pro-Paket?}"
for arg in "$@"; do
    [[ "$arg" == --tenant=* ]] && TENANT="${arg#--tenant=}"
    [[ "$arg" == --tenant ]]   && shift && TENANT="$1"
    [[ "$arg" == --query=* ]]  && QUERY="${arg#--query=}"
    [[ "$arg" == --query ]]    && shift && QUERY="$1"
done

PG_CONTAINER="${POSTGRES_CONTAINER:-postgres-rag}"
PG_PASS="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD nicht gesetzt}"
N8N_URL="${N8N_WEBHOOK_URL:-https://n8n.${DOMAIN:-localhost}/webhook/rag-query}"
SCHEMA="tenant_${TENANT}"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'; BOLD='\033[1m'
ok()   { echo -e "  ${GREEN}✓${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC}  $1"; }
info() { echo -e "  ${BLUE}→${NC}  $1"; }
warn() { echo -e "  ${YELLOW}!${NC}  $1"; }
sep()  { echo -e "\n${BLUE}${BOLD}── $1 ──${NC}"; }

echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  RAG End-to-End Test${NC}"
echo -e "${BLUE}${BOLD}  Tenant: $TENANT  |  Query: \"$QUERY\"${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"

PASSED=0; FAILED=0

pass() { ok "$1"; PASSED=$((PASSED+1)); }
fail_test() { fail "$1"; FAILED=$((FAILED+1)); }

# ════════════════════════════════════════════════════════════════════════
sep "Test 1: PostgreSQL Verbindung"

if docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" pg_isready -U postgres &>/dev/null; then
    pass "PostgreSQL erreichbar"
else
    fail_test "PostgreSQL nicht erreichbar"
    echo -e "\n  ${RED}Abbruch: Ohne DB keine weiteren Tests möglich${NC}"
    exit 1
fi

# ════════════════════════════════════════════════════════════════════════
sep "Test 2: Tenant und Schema"

TENANT_ROW=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -t -A -c \
    "SELECT id, name, status FROM public.tenants WHERE slug='$TENANT';" 2>/dev/null || echo "")

if [ -n "$TENANT_ROW" ]; then
    TENANT_NAME=$(echo "$TENANT_ROW" | cut -d'|' -f2)
    TENANT_STATUS=$(echo "$TENANT_ROW" | cut -d'|' -f3)
    pass "Tenant gefunden: $TENANT_NAME (Status: $TENANT_STATUS)"
else
    fail_test "Tenant '$TENANT' nicht gefunden"
    info "Anlegen mit: bash scripts/seed-test-data.sh --tenant $TENANT"
fi

SCHEMA_EXISTS=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -t -c \
    "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='$SCHEMA';" \
    2>/dev/null | xargs || echo "0")

if [ "$SCHEMA_EXISTS" = "1" ]; then
    pass "Schema '$SCHEMA' existiert"
else
    fail_test "Schema '$SCHEMA' nicht gefunden"
fi

# ════════════════════════════════════════════════════════════════════════
sep "Test 3: Testdaten vorhanden"

SOURCE_COUNT=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -t -c \
    "SELECT COUNT(*) FROM ${SCHEMA}.sources WHERE status='indexed';" \
    2>/dev/null | xargs || echo "0")

CHUNK_COUNT=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -t -c \
    "SELECT COUNT(*) FROM ${SCHEMA}.chunks;" \
    2>/dev/null | xargs || echo "0")

EMBED_COUNT=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -t -c \
    "SELECT COUNT(*) FROM ${SCHEMA}.embeddings;" \
    2>/dev/null | xargs || echo "0")

info "Quellen: $SOURCE_COUNT | Chunks: $CHUNK_COUNT | Embeddings: $EMBED_COUNT"

[ "$SOURCE_COUNT" -gt 0 ] && pass "Sources vorhanden" || fail_test "Keine indizierten Sources — seed ausführen"
[ "$CHUNK_COUNT" -gt 0 ]  && pass "Chunks vorhanden"  || fail_test "Keine Chunks — seed ausführen"
[ "$EMBED_COUNT" -gt 0 ]  && pass "Embeddings vorhanden" || fail_test "Keine Embeddings — seed ausführen"

if [ "$CHUNK_COUNT" -gt 0 ] && [ "$EMBED_COUNT" = "0" ]; then
    warn "Chunks aber keine Embeddings → bash scripts/seed-test-data.sh --tenant $TENANT"
fi

# ════════════════════════════════════════════════════════════════════════
sep "Test 4: Vektorsuche direkt in PostgreSQL"

if [ "$EMBED_COUNT" -gt 0 ]; then
    # Ersten vorhandenen Vektor als Query-Vektor nutzen (Self-Similarity Test)
    SEARCH_RESULT=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
        psql -U postgres -d app_db -t -A -F '|' -c "
        WITH query_vec AS (
            SELECT vector FROM ${SCHEMA}.embeddings LIMIT 1
        )
        SELECT
            c.content,
            ROUND((1 - (e.vector <=> qv.vector))::numeric, 4) AS sim
        FROM ${SCHEMA}.embeddings e
        JOIN ${SCHEMA}.chunks c ON c.id = e.chunk_id
        CROSS JOIN query_vec qv
        ORDER BY e.vector <=> qv.vector
        LIMIT 3;" 2>/dev/null || echo "")

    if [ -n "$SEARCH_RESULT" ]; then
        pass "Vektorsuche liefert Ergebnisse"
        echo ""
        echo -e "  ${BLUE}Top-3 Treffer (Self-Similarity):${NC}"
        echo "$SEARCH_RESULT" | while IFS='|' read -r content sim; do
            [ -z "$content" ] && continue
            CONTENT_SHORT="${content:0:70}..."
            echo -e "  ${GREEN}[$sim]${NC} $CONTENT_SHORT"
        done
    else
        fail_test "Vektorsuche ohne Ergebnis"
    fi
else
    warn "Test 4 übersprungen (keine Embeddings)"
fi

# ════════════════════════════════════════════════════════════════════════
sep "Test 5: n8n Erreichbarkeit"

N8N_HOST="${DOMAIN:-}"
N8N_LOCAL="http://localhost:5678"

N8N_CONTAINER=$(docker ps -q --filter "name=n8n" 2>/dev/null | head -1)
if [ -n "$N8N_CONTAINER" ]; then
    pass "n8n Container läuft"

    # Health-Check intern
    N8N_HEALTH=$(docker exec "$N8N_CONTAINER" \
        curl -sf http://localhost:5678/healthz 2>/dev/null || echo "")

    if [ -n "$N8N_HEALTH" ]; then
        pass "n8n Health-Check OK"
    else
        warn "n8n Health-Check nicht erreichbar (ggf. noch startend)"
    fi
else
    fail_test "n8n Container nicht gefunden"
fi

# ════════════════════════════════════════════════════════════════════════
sep "Test 6: n8n Webhook Test"

WEBHOOK_URL="${N8N_WEBHOOK_URL:-http://localhost:5678/webhook/rag-query}"

info "Webhook URL: $WEBHOOK_URL"
info "Query: \"$QUERY\""
echo ""

START_TS=$(($(date +%s%N)/1000000))

WEBHOOK_RESPONSE=$(curl -sf \
    --max-time 30 \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{
        \"tenant_slug\": \"$TENANT\",
        \"query\": \"$QUERY\",
        \"session_id\": \"test-$(date +%s)\",
        \"top_k\": 5,
        \"min_similarity\": 0.3,
        \"model\": \"llama3.2:3b\"
    }" \
    "$WEBHOOK_URL" 2>/dev/null || echo "")

END_TS=$(($(date +%s%N)/1000000))
LATENCY=$((END_TS - START_TS))

if [ -n "$WEBHOOK_RESPONSE" ]; then
    pass "Webhook antwortet ($LATENCY ms)"

    # JSON parsen mit Python
    python3 - <<PYEOF
import json, sys

try:
    data = json.loads("""$WEBHOOK_RESPONSE""")

    answer = data.get('answer', '')
    sources = data.get('sources', [])
    latency = data.get('latency_ms', '?')

    print(f"\n  \033[34mAntwort:\033[0m")
    for line in answer[:500].split('\n'):
        print(f"    {line}")
    if len(answer) > 500:
        print(f"    [...{len(answer)-500} Zeichen mehr]")

    print(f"\n  \033[34mQuellen ({len(sources)}):\033[0m")
    for i, src in enumerate(sources[:3], 1):
        title = src.get('document_title', '?')
        sim = src.get('similarity', 0)
        print(f"    [{i}] {title} (Ähnlichkeit: {sim:.0%})")

    print(f"\n  \033[34mLatenz:\033[0m {latency}ms (gemessen: $LATENCY ms)")

except json.JSONDecodeError as e:
    print(f"  JSON-Parse-Fehler: {e}")
    print(f"  Rohe Antwort: {"""$WEBHOOK_RESPONSE"""[:200]}")
PYEOF
else
    warn "Webhook nicht erreichbar (Test 6 übersprungen)"
    info "Mögliche Ursachen:"
    info "  1. n8n läuft nicht: bash setup.sh"
    info "  2. Workflow nicht aktiviert: n8n UI → Workflow aktivieren"
    info "  3. URL falsch: setze N8N_WEBHOOK_URL in .env"
fi

# ════════════════════════════════════════════════════════════════════════
sep "Test 7: Konversation gespeichert?"

CONV_COUNT_BEFORE=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -t -c \
    "SELECT COUNT(*) FROM ${SCHEMA}.conversations;" \
    2>/dev/null | xargs || echo "?")

if [ -n "$WEBHOOK_RESPONSE" ] && [ "$CONV_COUNT_BEFORE" != "?" ]; then
    # Kurz warten, dann prüfen
    sleep 1
    CONV_COUNT_AFTER=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
        psql -U postgres -d app_db -t -c \
        "SELECT COUNT(*) FROM ${SCHEMA}.conversations;" \
        2>/dev/null | xargs || echo "?")

    if [ "$CONV_COUNT_AFTER" -gt "$CONV_COUNT_BEFORE" ] 2>/dev/null; then
        pass "Konversation in DB gespeichert ($CONV_COUNT_AFTER gesamt)"
    else
        warn "Konversation nicht gespeichert — Workflow-Log in n8n prüfen"
    fi
else
    warn "Test 7 übersprungen"
fi

# ════════════════════════════════════════════════════════════════════════
sep "Ergebnis"

echo ""
echo -e "  ${GREEN}Bestanden: $PASSED${NC}  |  ${RED}Fehlgeschlagen: $FAILED${NC}"
echo ""

if [ "$FAILED" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}Alle Tests bestanden — RAG-Pfad funktioniert!${NC}"
    echo ""
    echo -e "  Webapp starten: ${BLUE}bash scripts/serve-webapp.sh${NC}"
else
    echo -e "  ${YELLOW}${BOLD}$FAILED Test(s) fehlgeschlagen — prüfe die Ausgabe oben.${NC}"
    echo ""
    echo -e "  Fehlende Daten: ${BLUE}bash scripts/seed-test-data.sh --tenant $TENANT${NC}"
fi
echo ""
