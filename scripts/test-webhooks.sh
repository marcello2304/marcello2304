#!/bin/bash
# test-webhooks.sh — Testet Ingest + RAG-Chat Webhooks gegen workflows.eppcom.de
#
# Verwendung:
#   bash scripts/test-webhooks.sh
#   API_KEY=dein-key bash scripts/test-webhooks.sh --domain workflows.eppcom.de

set -euo pipefail

# ── Konfiguration ─────────────────────────────────────────────────────────────
DOMAIN="${WEBHOOK_DOMAIN:-workflows.eppcom.de}"
TENANT_ID="${TENANT_ID:-a0000000-0000-0000-0000-000000000001}"
API_KEY="${API_KEY:?Bitte API_KEY als ENV setzen: API_KEY=dein-key bash scripts/test-webhooks.sh}"

for arg in "$@"; do
    [[ "$arg" == --domain=* ]] && DOMAIN="${arg#--domain=}"
    [[ "$arg" == --key=* ]]    && API_KEY="${arg#--key=}"
done

BASE_URL="https://${DOMAIN}/webhook"

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC}  $1"; }
info() { echo -e "  ${BLUE}→${NC}  $1"; }
step() { echo -e "\n${BLUE}${BOLD}── $1 ──${NC}"; }

echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  Webhook-Tests — ${DOMAIN}${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo ""
info "Tenant-ID: $TENANT_ID"
info "API-Key:   $API_KEY"
info "Base-URL:  $BASE_URL"

PASSED=0; FAILED=0

# ── Test 1: n8n erreichbar? ───────────────────────────────────────────────────
step "Test 1: n8n Erreichbarkeit"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://${DOMAIN}/healthz" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" =~ ^(200|301|302|401|404)$ ]]; then
    ok "n8n antwortet (HTTP $HTTP_CODE)"
    PASSED=$((PASSED+1))
else
    fail "n8n nicht erreichbar (HTTP $HTTP_CODE) — Container läuft?"
    FAILED=$((FAILED+1))
fi

# ── Test 2: Ingest Webhook ────────────────────────────────────────────────────
step "Test 2: Ingest Webhook (POST /webhook/ingest)"

info "Sende Testdokument..."
echo ""

info "(Timeout 5 min — Ollama Embedding kann langsam sein beim ersten Aufruf)"
INGEST_RESPONSE=$(curl -s --max-time 300 \
    -X POST "${BASE_URL}/ingest" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: ${TENANT_ID}" \
    -H "X-API-Key: ${API_KEY}" \
    -d '{
        "content": "EPPCOM GmbH bietet professionelle Dienstleistungen in den Bereichen KI, Automatisierung und digitale Transformation an. Unser Kernprodukt ist ein modulares RAG-System (Retrieval Augmented Generation) fuer Unternehmenskunden. Wir wurden 2020 gegruendet und haben unseren Sitz in Deutschland.",
        "name": "EPPCOM Testdokument",
        "source_type": "manual"
    }' 2>/dev/null || echo '{"error":"curl_timeout_or_failed"}')

if echo "$INGEST_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('success') else 1)" 2>/dev/null; then
    ok "Ingest erfolgreich!"
    echo "$INGEST_RESPONSE" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f'  source_id:     {d.get(\"source_id\",\"?\")[:40]}')
print(f'  document_id:   {d.get(\"document_id\",\"?\")[:40]}')
print(f'  chunks:        {d.get(\"chunks_created\",\"?\")}')
print(f'  timing:        {d.get(\"timing_ms\",\"?\")}ms')
" 2>/dev/null
    PASSED=$((PASSED+1))
elif echo "$INGEST_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if 'error' in d else 1)" 2>/dev/null; then
    fail "Ingest-Fehler:"
    echo "$INGEST_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  {d}')" 2>/dev/null || echo "  $INGEST_RESPONSE"
    FAILED=$((FAILED+1))
elif [ -z "$INGEST_RESPONSE" ]; then
    fail "Leere Antwort — Workflow möglicherweise inaktiv"
    echo ""
    echo -e "  ${YELLOW}Checke in n8n UI:${NC}"
    echo -e "  1. Workflows → 'Ingest' → ist der Toggle ${YELLOW}ON${NC} (grün)?"
    echo -e "  2. Executions → letzte Ausführung auf Fehler prüfen"
    FAILED=$((FAILED+1))
else
    fail "Unerwartete Antwort:"
    echo "  ${INGEST_RESPONSE:0:300}"
    FAILED=$((FAILED+1))
fi

# ── Test 3: RAG Chat Webhook ──────────────────────────────────────────────────
step "Test 3: RAG Chat Webhook (POST /webhook/rag-chat)"

info "Sende Query: 'Was macht EPPCOM?'"
echo ""

CHAT_RESPONSE=$(curl -s --max-time 90 \
    -X POST "${BASE_URL}/rag-chat" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: ${TENANT_ID}" \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"query": "Was macht EPPCOM und in welchen Bereichen ist das Unternehmen taetig?"}' 2>/dev/null || echo '{"error":"curl_failed"}')

if echo "$CHAT_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('answer') or d.get('response') else 1)" 2>/dev/null; then
    ok "RAG Chat antwortet!"
    echo "$CHAT_RESPONSE" | python3 -c "
import json,sys
d=json.load(sys.stdin)
answer = d.get('answer') or d.get('response','?')
sources = d.get('sources',[])
latency = d.get('latency_ms','?')
print()
print('  \033[34mAntwort:\033[0m')
for line in answer[:600].split('\n'):
    print(f'    {line}')
if len(answer) > 600:
    print(f'    [...{len(answer)-600} weitere Zeichen]')
print(f'\n  \033[34mQuellen:\033[0m {len(sources)} Chunks gefunden')
for s in sources[:3]:
    sim = s.get('similarity',0)
    src = s.get('source_title',s.get('document_title','?'))
    print(f'    [{sim:.0%}] {src}')
print(f'\n  \033[34mLatenz:\033[0m {latency}ms')
" 2>/dev/null
    PASSED=$((PASSED+1))
elif echo "$CHAT_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if 'error' in d else 1)" 2>/dev/null; then
    fail "Chat-Fehler:"
    echo "$CHAT_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  {d}')" 2>/dev/null || echo "  $CHAT_RESPONSE"
    FAILED=$((FAILED+1))
else
    fail "Unerwartete Antwort:"
    echo "  ${CHAT_RESPONSE:0:400}"
    FAILED=$((FAILED+1))
fi

# ── Ergebnis ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Bestanden: $PASSED${NC}  |  ${RED}Fehlgeschlagen: $FAILED${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo ""

if [ "$FAILED" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}Alle Webhooks funktionieren!${NC}"
    echo ""
    echo -e "  Weitere Tests mit:"
    echo -e "  ${YELLOW}API_KEY=dein-key bash scripts/test-webhooks.sh${NC}"
else
    echo -e "  ${YELLOW}${BOLD}Checklist bei Fehlern:${NC}"
    echo -e "  1. DB Setup: ${YELLOW}bash scripts/setup-rag-db.sh${NC}"
    echo -e "  2. n8n Credential: Host=${YELLOW}<postgres-container>${NC} DB=${YELLOW}app_db${NC} User=${YELLOW}appuser${NC}"
    echo -e "  3. n8n Workflow aktiv? UI → Workflow → Toggle ON"
    echo -e "  4. Ollama erreichbar? ${YELLOW}curl https://ollama.eppcom.de/api/tags${NC}"
fi
echo ""
