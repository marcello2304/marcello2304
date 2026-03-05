#!/usr/bin/env bash
# eppcom-deploy.sh — Vollständiger EPPCOM RAG Stack Deploy
# Auf Server 1 (94.130.170.167) ausführen als root:
#   cd /root && git clone <repo> || git pull
#   bash scripts/eppcom-deploy.sh
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguration (aus Handoff-Docs und bestätigten Werten)
# ──────────────────────────────────────────────────────────────────────────────
OLLAMA_HOST="http://10.0.0.3:11434"
N8N_URL="https://workflows.eppcom.de"
N8N_USER="admin"
N8N_PASS="***N8N_PASSWORD_REMOVED***"
TENANT_ID="a0000000-0000-0000-0000-000000000001"
API_KEY_PLAINTEXT="***API_KEY_REMOVED***"
API_KEY_OLD="test-key-123"
EMBED_MODEL="qwen3-embedding:0.6b"
CHAT_MODEL="qwen3-nothink"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# PostgreSQL-Container automatisch ermitteln
PG_CONTAINER="$(docker ps -q --filter name=postgres | head -1)"
PG_USER="appuser"
PG_DB="appdb"

# Farben
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
err()   { echo -e "${RED}[FEHLER]${NC} $*"; exit 1; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
step()  { echo ""; echo -e "${BLUE}━━━ SCHRITT $* ━━━${NC}"; }

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   EPPCOM RAG Platform — Vollständiger Deploy              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 0: Voraussetzungen prüfen
# ──────────────────────────────────────────────────────────────────────────────
step "0/7: Voraussetzungen prüfen"

if [ -z "$PG_CONTAINER" ]; then
  err "Kein PostgreSQL-Container gefunden! 'docker ps' prüfen."
fi
ok "PostgreSQL-Container: $PG_CONTAINER"

# Ollama erreichbar?
if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
  ok "Ollama erreichbar: $OLLAMA_HOST"
else
  warn "Ollama NICHT erreichbar unter $OLLAMA_HOST"
  warn "Embedding-Schritt wird übersprungen"
  OLLAMA_OK=false
fi
OLLAMA_OK="${OLLAMA_OK:-true}"

# n8n erreichbar?
N8N_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$N8N_URL" 2>/dev/null || echo "000")
if [ "$N8N_HTTP" = "200" ] || [ "$N8N_HTTP" = "301" ] || [ "$N8N_HTTP" = "302" ]; then
  ok "n8n erreichbar: $N8N_URL (HTTP $N8N_HTTP)"
else
  warn "n8n unter $N8N_URL nicht erreichbar (HTTP $N8N_HTTP)"
fi

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 1: API-Key reparieren
# ──────────────────────────────────────────────────────────────────────────────
step "1/7: API-Key für Test-Tenant reparieren"

psql_exec() {
  docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 "$@"
}

psql_exec <<'EOF'
-- Alte Keys mit unbekanntem Plaintext entfernen
DELETE FROM api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'
  AND key_hash NOT IN (
    encode(sha256('test-key-123'::bytea), 'hex'),
    encode(sha256('***API_KEY_REMOVED***'::bytea), 'hex')
  );

-- test-key-123 sicherstellen (bestätigt funktionierend)
INSERT INTO api_keys (id, tenant_id, key_hash, name, permissions, is_active)
VALUES (
  gen_random_uuid(),
  'a0000000-0000-0000-0000-000000000001',
  encode(sha256('test-key-123'::bytea), 'hex'),
  'Test Key Original',
  '["read","write"]'::jsonb,
  true
)
ON CONFLICT DO NOTHING;

-- ***API_KEY_REMOVED*** hinzufügen
INSERT INTO api_keys (id, tenant_id, key_hash, name, permissions, is_active)
VALUES (
  gen_random_uuid(),
  'a0000000-0000-0000-0000-000000000001',
  encode(sha256('***API_KEY_REMOVED***'::bytea), 'hex'),
  'Test API Key 2025',
  '["read","write"]'::jsonb,
  true
)
ON CONFLICT DO NOTHING;
EOF

KEY_COUNT=$(psql_exec -tAc "SELECT COUNT(*) FROM api_keys WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001' AND is_active = true;" 2>/dev/null || echo "0")
ok "API-Keys aktiv: $KEY_COUNT (inkl. test-key-123 + ***API_KEY_REMOVED***)"

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 2: Test-Daten einfügen
# ──────────────────────────────────────────────────────────────────────────────
step "2/7: Test-Daten (Chunks) einfügen"

psql_exec < "$PROJECT_DIR/sql/eppcom-test-data.sql" > /tmp/testdata-output.txt 2>&1 || {
  warn "SQL-Output:"
  cat /tmp/testdata-output.txt
}

CHUNK_COUNT=$(psql_exec -tAc "SELECT COUNT(*) FROM chunks WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001';" 2>/dev/null || echo "0")
ok "Chunks in DB: $CHUNK_COUNT"

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 3: Embeddings generieren
# ──────────────────────────────────────────────────────────────────────────────
step "3/7: Embeddings für Test-Chunks generieren"

if [ "$OLLAMA_OK" = "true" ]; then

  embed_chunk() {
    local CHUNK_ID="$1"
    local CONTENT="$2"

    # Prüfen ob schon vorhanden
    EXISTING=$(psql_exec -tAc "SELECT COUNT(*) FROM embeddings WHERE chunk_id = '${CHUNK_ID}';" 2>/dev/null || echo "0")
    if [ "${EXISTING:-0}" -gt "0" ]; then
      info "  Chunk $CHUNK_ID hat bereits Embedding — übersprungen"
      return
    fi

    info "  → Embedding für Chunk $CHUNK_ID ..."

    # Embedding von Ollama holen
    local EMBED_JSON
    EMBED_JSON=$(curl -s --connect-timeout 30 -X POST "$OLLAMA_HOST/api/embed" \
      -H "Content-Type: application/json" \
      -d "{\"model\":\"$EMBED_MODEL\",\"input\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$CONTENT")}" 2>/dev/null)

    if [ -z "$EMBED_JSON" ]; then
      warn "  Kein Response von Ollama für Chunk $CHUNK_ID"
      return
    fi

    # Embedding-Array extrahieren und in DB einfügen
    local VECTOR_STR
    VECTOR_STR=$(echo "$EMBED_JSON" | python3 -c "
import json,sys
data = json.load(sys.stdin)
emb = data.get('embeddings', [[]])[0] or data.get('embedding', [])
if not emb: sys.exit(1)
print('[' + ','.join(str(round(x, 8)) for x in emb) + ']')
" 2>/dev/null)

    if [ -z "$VECTOR_STR" ]; then
      warn "  Embedding-Extraktion fehlgeschlagen für Chunk $CHUNK_ID"
      return
    fi

    psql_exec -c "
INSERT INTO embeddings (chunk_id, tenant_id, embedding, model_name)
VALUES (
  '${CHUNK_ID}',
  'a0000000-0000-0000-0000-000000000001',
  '${VECTOR_STR}'::vector(1024),
  '${EMBED_MODEL}'
)
ON CONFLICT (chunk_id) DO UPDATE SET
  embedding = EXCLUDED.embedding,
  model_name = EXCLUDED.model_name;
" > /dev/null 2>&1 && ok "  Chunk $CHUNK_ID embedded ✓" || warn "  INSERT fehlgeschlagen für $CHUNK_ID"
  }

  # Chunks ohne Embedding holen und embedden
  CHUNKS_WITHOUT_EMBEDDING=$(psql_exec -tA <<'EOF'
SELECT c.id, c.content
FROM chunks c
WHERE c.tenant_id = 'a0000000-0000-0000-0000-000000000001'
  AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.chunk_id = c.id);
EOF
)

  if [ -z "$CHUNKS_WITHOUT_EMBEDDING" ]; then
    ok "Alle Chunks haben bereits Embeddings"
  else
    echo "$CHUNKS_WITHOUT_EMBEDDING" | while IFS='|' read -r CHUNK_ID CONTENT; do
      [ -z "$CHUNK_ID" ] && continue
      embed_chunk "$CHUNK_ID" "$CONTENT"
    done
  fi

  EMBED_COUNT=$(psql_exec -tAc "SELECT COUNT(*) FROM embeddings WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001';" 2>/dev/null || echo "0")
  ok "Embeddings gesamt: $EMBED_COUNT"

else
  warn "Ollama nicht erreichbar — Embedding-Schritt übersprungen"
  warn "Manuell ausführen:"
  warn "  EMBEDDING=\$(curl -s http://10.0.0.3:11434/api/embed -d '{\"model\":\"qwen3-embedding:0.6b\",\"input\":\"...\"}' | python3 -c \"import sys,json; print('['+','.join(str(x) for x in json.load(sys.stdin)['embeddings'][0])+']')\")"
fi

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 4: n8n RAG Chat Workflow importieren und aktivieren
# ──────────────────────────────────────────────────────────────────────────────
step "4/7: n8n RAG Chat Workflow importieren und aktivieren"

WORKFLOW_JSON="$PROJECT_DIR/n8n/eppcom-rag-chat-workflow.json"

if [ ! -f "$WORKFLOW_JSON" ]; then
  warn "Workflow-Datei nicht gefunden: $WORKFLOW_JSON"
else
  # n8n Login (Session-Cookie)
  info "  → Login bei n8n ..."
  LOGIN_RESP=$(curl -s -c /tmp/n8n-eppcom-cookies.txt \
    -X POST "$N8N_URL/rest/login" \
    -H "Content-Type: application/json" \
    -d "{\"emailOrLdapLoginName\":\"${N8N_USER}\",\"password\":\"${N8N_PASS}\"}" \
    -w "\n%{http_code}" 2>/dev/null || echo -e "\n000")

  N8N_CODE=$(echo "$LOGIN_RESP" | tail -1)

  if [ "$N8N_CODE" != "200" ]; then
    warn "  n8n Login fehlgeschlagen (HTTP $N8N_CODE)"
    warn "  → Workflow manuell importieren:"
    warn "    $N8N_URL → New → Import from File → $WORKFLOW_JSON"
  else
    ok "  n8n Login erfolgreich"

    # Prüfen ob Workflow schon existiert
    EXISTING_WF=$(curl -s -b /tmp/n8n-eppcom-cookies.txt \
      "$N8N_URL/rest/workflows" 2>/dev/null \
      | python3 -c "
import json,sys
data=json.load(sys.stdin)
wfs = data.get('data', []) if isinstance(data, dict) else data
for wf in wfs:
    if 'RAG Chat' in wf.get('name','') and 'EPPCOM' in wf.get('name',''):
        print(wf['id'])
        break
" 2>/dev/null || echo "")

    if [ -n "$EXISTING_WF" ]; then
      info "  → RAG Chat Workflow existiert bereits (ID: $EXISTING_WF)"

      # Aktivieren
      ACTIVATE_CODE=$(curl -s -b /tmp/n8n-eppcom-cookies.txt \
        -X PATCH "$N8N_URL/rest/workflows/$EXISTING_WF" \
        -H "Content-Type: application/json" \
        -d '{"active": true}' \
        -w "\n%{http_code}" 2>/dev/null | tail -1)

      if [ "$ACTIVATE_CODE" = "200" ]; then
        ok "  Bestehender Workflow aktiviert ✓"
      else
        warn "  Aktivierung fehlgeschlagen (HTTP $ACTIVATE_CODE) — manuell aktivieren"
      fi

      # Disconnected Nodes löschen (bekanntes Problem aus Handoff)
      info "  → Disconnected 'Ollama: Chat' Node entfernen ..."
      WF_DATA=$(curl -s -b /tmp/n8n-eppcom-cookies.txt \
        "$N8N_URL/rest/workflows/$EXISTING_WF" 2>/dev/null)

      CLEANED_WF=$(echo "$WF_DATA" | python3 -c "
import json,sys
data = json.load(sys.stdin)
# Alle Nodes entfernen, die disconnected sind (nicht in connections)
nodes = data.get('nodes', [])
conns = data.get('connections', {})
connected_names = set()
for src, outs in conns.items():
    connected_names.add(src)
    for branch in outs.get('main', []):
        for link in branch:
            connected_names.add(link.get('node',''))
# Behalte Nodes, die verbunden sind oder Webhook/Respond sind
kept = []
for n in nodes:
    name = n.get('name','')
    ntype = n.get('type','')
    is_endpoint = 'webhook' in ntype.lower() or 'respondTo' in ntype
    if name in connected_names or is_endpoint:
        kept.append(n)
    else:
        print(f'ENTFERNT: {name}', file=sys.stderr)
data['nodes'] = kept
print(json.dumps(data))
" 2>/dev/null)

      if [ -n "$CLEANED_WF" ]; then
        UPDATE_CODE=$(curl -s -b /tmp/n8n-eppcom-cookies.txt \
          -X PUT "$N8N_URL/rest/workflows/$EXISTING_WF" \
          -H "Content-Type: application/json" \
          -d "$CLEANED_WF" \
          -w "\n%{http_code}" 2>/dev/null | tail -1)
        [ "$UPDATE_CODE" = "200" ] && ok "  Disconnected Nodes entfernt ✓" || info "  Workflow-Update: HTTP $UPDATE_CODE"
      fi

    else
      info "  → Importiere neuen RAG Chat Workflow ..."
      IMPORT_RESP=$(curl -s -b /tmp/n8n-eppcom-cookies.txt \
        -X POST "$N8N_URL/rest/workflows" \
        -H "Content-Type: application/json" \
        -d @"$WORKFLOW_JSON" \
        -w "\n%{http_code}" 2>/dev/null)

      IMPORT_CODE=$(echo "$IMPORT_RESP" | tail -1)
      IMPORT_BODY=$(echo "$IMPORT_RESP" | head -1)

      if [ "$IMPORT_CODE" = "200" ] || [ "$IMPORT_CODE" = "201" ]; then
        WF_ID=$(echo "$IMPORT_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id','?'))" 2>/dev/null || echo "?")
        ok "  Workflow importiert (ID: $WF_ID)"

        # Aktivieren
        curl -s -b /tmp/n8n-eppcom-cookies.txt \
          -X PATCH "$N8N_URL/rest/workflows/$WF_ID" \
          -H "Content-Type: application/json" \
          -d '{"active": true}' > /dev/null 2>&1 && ok "  Workflow aktiviert ✓" || warn "  Manuell aktivieren: $N8N_URL/workflow/$WF_ID"

        warn ""
        warn "  WICHTIG: Credentials nach Import manuell prüfen!"
        warn "  → Workflow öffnen: $N8N_URL/workflow/$WF_ID"
        warn "  → PostgreSQL-Nodes: Credential auf 'Postgres account' setzen"
        warn "  → IF-Node 'Auth OK?': Bedingung manuell prüfen (geht bei Import verloren)"
      else
        warn "  Import fehlgeschlagen (HTTP $IMPORT_CODE)"
        warn "  → Manuell importieren: $N8N_URL → Import → $WORKFLOW_JSON"
      fi
    fi

    rm -f /tmp/n8n-eppcom-cookies.txt
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 5: Document Ingestion Workflow aktivieren
# ──────────────────────────────────────────────────────────────────────────────
step "5/7: Document Ingestion Workflow aktivieren"

# n8n Login erneut (Cookie weg nach letztem Step)
LOGIN_RESP2=$(curl -s -c /tmp/n8n-eppcom-cookies2.txt \
  -X POST "$N8N_URL/rest/login" \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginName\":\"${N8N_USER}\",\"password\":\"${N8N_PASS}\"}" \
  -w "\n%{http_code}" 2>/dev/null | tail -1)

if [ "${LOGIN_RESP2:-000}" = "200" ]; then
  INGEST_WF=$(curl -s -b /tmp/n8n-eppcom-cookies2.txt \
    "$N8N_URL/rest/workflows" 2>/dev/null \
    | python3 -c "
import json,sys
data=json.load(sys.stdin)
wfs = data.get('data', []) if isinstance(data, dict) else data
for wf in wfs:
    name = wf.get('name','')
    if 'Ingestion' in name or 'ingest' in name.lower():
        print(wf['id'])
        break
" 2>/dev/null || echo "")

  if [ -n "$INGEST_WF" ]; then
    ACTIVATE_CODE=$(curl -s -b /tmp/n8n-eppcom-cookies2.txt \
      -X PATCH "$N8N_URL/rest/workflows/$INGEST_WF" \
      -H "Content-Type: application/json" \
      -d '{"active": true}' \
      -w "\n%{http_code}" 2>/dev/null | tail -1)
    [ "$ACTIVATE_CODE" = "200" ] && ok "Document Ingestion Workflow aktiviert ✓" || info "Ingestion: HTTP $ACTIVATE_CODE"
  else
    info "Kein Ingestion-Workflow gefunden — wird separat gebaut"
  fi
  rm -f /tmp/n8n-eppcom-cookies2.txt
else
  info "n8n Login für Step 5 übersprungen"
fi

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 6: End-to-End Test
# ──────────────────────────────────────────────────────────────────────────────
step "6/7: End-to-End Test"

info "  → Teste /webhook/rag-chat (Produktion) ..."
E2E_RESPONSE=$(curl -s --connect-timeout 15 -X POST \
  "$N8N_URL/webhook/rag-chat" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "X-API-Key: $API_KEY_PLAINTEXT" \
  -d '{"query": "Was sind die Öffnungszeiten?"}' 2>/dev/null || echo "")

if echo "$E2E_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK') if 'answer' in d else sys.exit(1)" 2>/dev/null; then
  ANSWER=$(echo "$E2E_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('answer','?')[:100])" 2>/dev/null)
  ok "  Produktion-Endpoint funktioniert!"
  info "  Antwort: $ANSWER..."
else
  info "  Produktion-Endpoint noch nicht bereit — teste Test-Endpoint ..."
  E2E_TEST_RESPONSE=$(curl -s --connect-timeout 15 -X POST \
    "$N8N_URL/webhook-test/rag-chat" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: $TENANT_ID" \
    -H "X-API-Key: $API_KEY_OLD" \
    -d '{"query": "Was sind die Öffnungszeiten?"}' 2>/dev/null || echo "")

  if echo "$E2E_TEST_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK') if 'answer' in d else sys.exit(1)" 2>/dev/null; then
    ANSWER=$(echo "$E2E_TEST_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('answer','?')[:100])" 2>/dev/null)
    ok "  Test-Endpoint funktioniert! (Workflow muss noch aktiviert werden)"
    info "  Antwort: $ANSWER..."
  else
    warn "  Kein JSON-Response — Response war:"
    echo "${E2E_RESPONSE:-leer}" | head -5
    echo "${E2E_TEST_RESPONSE:-leer}" | head -5
    warn "  Manuell prüfen: $N8N_URL/executions"
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# SCHRITT 7: Typebot Setup Anleitung
# ──────────────────────────────────────────────────────────────────────────────
step "6b/7: Admin UI deployen (Docker)"

ADMIN_UI_DIR="$PROJECT_DIR/admin-ui"
ADMIN_UI_PORT="${ADMIN_UI_PORT:-8080}"

if [ -d "$ADMIN_UI_DIR" ]; then
  # .env für Admin UI erzeugen falls nicht vorhanden
  if [ ! -f "$ADMIN_UI_DIR/.env" ]; then
    info "  → Erstelle Admin UI .env ..."
    # Werte aus Hauptprojekt .env übernehmen
    MAIN_ENV="$PROJECT_DIR/.env"
    PG_PASS=""
    if [ -f "$MAIN_ENV" ]; then
      PG_PASS=$(grep "^POSTGRES_PASSWORD=" "$MAIN_ENV" | cut -d= -f2- | tr -d '"' | tr -d "'")
    fi
    ADMIN_KEY_VAL="$(openssl rand -hex 24 2>/dev/null || echo 'admin-key-change-me-now')"
    cat > "$ADMIN_UI_DIR/.env" <<ADMINENV
DATABASE_URL=postgresql://appuser:${PG_PASS:-changeme}@postgres:5432/appdb
N8N_URL=${N8N_URL}
OLLAMA_URL=${OLLAMA_HOST}
EMBED_MODEL=${EMBED_MODEL}
ADMIN_API_KEY=${ADMIN_KEY_VAL}
S3_ENDPOINT=https://nbg1.your-objectstorage.com
S3_BUCKET=typebot-assets
ADMINENV
    ok "  .env erstellt — ADMIN_API_KEY: $ADMIN_KEY_VAL"
    warn "  Diesen Key sicher notieren!"
  fi

  # Container stoppen und neu bauen
  info "  → Baue Admin UI Docker Image ..."
  docker build -q -t eppcom-admin-ui "$ADMIN_UI_DIR" 2>&1 | tail -3

  # Alten Container entfernen
  docker rm -f eppcom-admin-ui 2>/dev/null || true

  # Starten (mit Zugriff auf das Docker-Netz von PostgreSQL)
  POSTGRES_NETWORK=$(docker inspect "$PG_CONTAINER" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin)[0]; nets=list(d.get('NetworkSettings',{}).get('Networks',{}).keys()); print(nets[0] if nets else 'coolify')" 2>/dev/null || echo "coolify")

  docker run -d \
    --name eppcom-admin-ui \
    --network "$POSTGRES_NETWORK" \
    --env-file "$ADMIN_UI_DIR/.env" \
    -p "${ADMIN_UI_PORT}:8080" \
    --restart unless-stopped \
    eppcom-admin-ui > /dev/null 2>&1

  sleep 3
  ADMIN_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${ADMIN_UI_PORT}/api/health" 2>/dev/null || echo "000")
  if [ "$ADMIN_HEALTH" = "200" ]; then
    ok "  Admin UI läuft auf http://localhost:${ADMIN_UI_PORT}"
    ok "  Admin Key: $(grep ADMIN_API_KEY "$ADMIN_UI_DIR/.env" | cut -d= -f2)"
  else
    warn "  Admin UI gestartet aber Health-Check: HTTP $ADMIN_HEALTH"
    warn "  Logs: docker logs eppcom-admin-ui"
  fi
else
  warn "  admin-ui/ Verzeichnis nicht gefunden — übersprungen"
fi

step "7/7: Typebot Setup (manuell)"

echo ""
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│  TYPEBOT: EPPCOM Assistent erstellen                            │"
echo "│  URL: https://admin-bot.eppcom.de                              │"
echo "├─────────────────────────────────────────────────────────────────┤"
echo "│                                                                 │"
echo "│  1. Neuer Bot → Name: 'EPPCOM Assistent'                       │"
echo "│                                                                 │"
echo "│  2. Flow:                                                       │"
echo "│     Text: 'Hallo! Ich bin der EPPCOM Assistent.'               │"
echo "│     Text Input → Variable: question                             │"
echo "│     Webhook Block:                                              │"
echo "│       Method: POST                                              │"
echo "│       URL: $N8N_URL/webhook/rag-chat     │"
echo "│       Headers:                                                  │"
echo "│         Content-Type: application/json                          │"
echo "│         X-Tenant-ID: $TENANT_ID                                │"
echo "│         X-API-Key: $API_KEY_PLAINTEXT                          │"
echo "│       Body: {\"query\": \"{{question}}\"}                           │"
echo "│       Save in variable: answer ← response.answer               │"
echo "│     Text: '{{answer}}'                                          │"
echo "│     Jump → Text Input (Loop)                                    │"
echo "│                                                                 │"
echo "│  3. Publish → https://bot.eppcom.de                            │"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""

# ──────────────────────────────────────────────────────────────────────────────
# ZUSAMMENFASSUNG
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   EPPCOM Deploy — ABGESCHLOSSEN                           ║"
echo "╠═══════════════════════════════════════════════════════════╣"

DB_CHUNKS=$(psql_exec -tAc "SELECT COUNT(*) FROM chunks WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001';" 2>/dev/null || echo "?")
DB_EMBEDS=$(psql_exec -tAc "SELECT COUNT(*) FROM embeddings WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001';" 2>/dev/null || echo "?")
DB_KEYS=$(psql_exec -tAc "SELECT COUNT(*) FROM api_keys WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001' AND is_active=true;" 2>/dev/null || echo "?")

printf "║  %-30s %-26s ║\n" "Chunks in DB:" "$DB_CHUNKS"
printf "║  %-30s %-26s ║\n" "Embeddings in DB:" "$DB_EMBEDS"
printf "║  %-30s %-26s ║\n" "Aktive API-Keys:" "$DB_KEYS"
printf "║  %-30s %-26s ║\n" "API-Key 1:" "test-key-123"
printf "║  %-30s %-26s ║\n" "API-Key 2:" "***API_KEY_REMOVED***"
echo "╠═══════════════════════════════════════════════════════════╣"
echo "║  Test-Commands:                                           ║"
echo "║                                                           ║"
echo "║  curl -s -X POST $N8N_URL/webhook/rag-chat \\"
echo "║    -H 'X-Tenant-ID: $TENANT_ID' \\"
echo "║    -H 'X-API-Key: $API_KEY_PLAINTEXT' \\"
echo "║    -H 'Content-Type: application/json' \\"
echo "║    -d '{\"query\": \"Was macht EPPCOM?\"}' | python3 -m json.tool"
echo "║                                                           ║"
echo "║  Offene Aufgaben:                                         ║"
echo "║  → Typebot Bot erstellen (Schritt 7 oben)                ║"
echo "║  → n8n IF-Node Condition nach Import prüfen              ║"
echo "║  → PostgreSQL Credentials in n8n verifizieren            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
