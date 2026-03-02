#!/bin/bash
# seed-test-data.sh — Fügt realistische Testdaten in den RAG-Stack ein
# Testet den kompletten Pfad: Tenant → Dokument → Chunks → Embeddings → Suche
#
# Verwendung:
#   bash scripts/seed-test-data.sh [--tenant demo] [--with-ollama]
#
# Modi:
#   Standard:      Fügt Chunks mit vorberechneten Dummy-Vektoren ein (kein Ollama nötig)
#   --with-ollama: Generiert echte Embeddings via Ollama (empfohlen für echte Suche)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# ENV laden
if [ -f ".env" ]; then
    set -a; source .env; set +a
fi

# Argumente
TENANT_SLUG="${1:-demo}"
USE_OLLAMA=false
for arg in "$@"; do
    [ "$arg" = "--with-ollama" ] && USE_OLLAMA=true
    [[ "$arg" == --tenant=* ]] && TENANT_SLUG="${arg#--tenant=}"
    [[ "$arg" == --tenant ]] && shift && TENANT_SLUG="$1"
done

PG_CONTAINER="${POSTGRES_CONTAINER:-postgres-rag}"
PG_PASS="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD nicht gesetzt}"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
OLLAMA_KEY="${OLLAMA_API_KEY:-}"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC}  $1"; }
info() { echo -e "  ${BLUE}→${NC}  $1"; }
warn() { echo -e "  ${YELLOW}!${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC}  $1"; exit 1; }

psql_cmd() {
    docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
        psql -U postgres -d app_db -t -c "$1" 2>/dev/null
}

psql_file() {
    docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
        psql -U postgres -d app_db -f - <<< "$1" 2>/dev/null
}

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  RAG Test-Daten Seed — Tenant: $TENANT_SLUG${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── 1. Postgres erreichbar? ──────────────────────────────────────────────
info "Prüfe PostgreSQL..."
if ! docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" pg_isready -U postgres &>/dev/null; then
    fail "PostgreSQL nicht erreichbar. Starte zuerst: bash setup.sh"
fi
ok "PostgreSQL erreichbar"

# ── 2. Tenant anlegen (falls nicht vorhanden) ────────────────────────────
info "Prüfe Tenant '$TENANT_SLUG'..."
TENANT_EXISTS=$(psql_cmd "SELECT COUNT(*) FROM public.tenants WHERE slug='$TENANT_SLUG';" | xargs)

if [ "$TENANT_EXISTS" = "0" ]; then
    info "Lege Tenant '$TENANT_SLUG' an..."
    POSTGRES_CONTAINER="$PG_CONTAINER" \
    POSTGRES_PASSWORD="$PG_PASS" \
    bash scripts/create-tenant.sh "$TENANT_SLUG" "Demo Firma GmbH" "demo@beispiel.de" starter
    ok "Tenant '$TENANT_SLUG' angelegt"
else
    ok "Tenant '$TENANT_SLUG' existiert bereits"
fi

SCHEMA="tenant_$TENANT_SLUG"

# ── 3. Prüfe ob bereits Daten vorhanden ─────────────────────────────────
CHUNK_COUNT=$(psql_cmd "SELECT COUNT(*) FROM ${SCHEMA}.chunks;" | xargs || echo "0")
if [ "$CHUNK_COUNT" -gt 0 ]; then
    warn "Bereits $CHUNK_COUNT Chunks in ${SCHEMA} vorhanden"
    echo ""
    read -r -p "  Trotzdem neu einfügen? (j/N): " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[jJyY]$ ]]; then
        echo "  Abgebrochen."
        exit 0
    fi
fi

# ── 4. Test-Dokumente per SQL einfügen ───────────────────────────────────
info "Füge Test-Dokumente ein..."

SQL_SEED=$(cat sql/seeds/demo-content.sql | sed "s/__SCHEMA__/${SCHEMA}/g")
psql_file "$SQL_SEED"

ok "Dokumente + Chunks eingefügt"

# Chunk-IDs und Inhalte laden
CHUNK_DATA=$(docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -t -A -F '|' -c \
    "SELECT id, content FROM ${SCHEMA}.chunks ORDER BY chunk_index;" 2>/dev/null)

CHUNK_COUNT=$(echo "$CHUNK_DATA" | grep -c '|' || echo "0")
info "$CHUNK_COUNT Chunks geladen"

# ── 5. Embeddings generieren ─────────────────────────────────────────────
echo ""
if [ "$USE_OLLAMA" = true ]; then
    echo -e "  ${BLUE}Modus: Echte Embeddings via Ollama${NC}"
    info "Prüfe Ollama Verbindung..."

    AUTH_HEADER=""
    [ -n "$OLLAMA_KEY" ] && AUTH_HEADER="-H 'Authorization: Bearer $OLLAMA_KEY'"

    if ! curl -sf "$OLLAMA_URL/api/version" $AUTH_HEADER &>/dev/null; then
        warn "Ollama nicht erreichbar unter $OLLAMA_URL"
        warn "Falle zurück auf Dummy-Embeddings..."
        USE_OLLAMA=false
    else
        ok "Ollama erreichbar"
    fi
fi

if [ "$USE_OLLAMA" = true ]; then
    # Echte Embeddings via Ollama
    info "Generiere Embeddings (nomic-embed-text)..."
    EMBEDDED=0

    while IFS='|' read -r CHUNK_ID CONTENT; do
        [ -z "$CHUNK_ID" ] && continue

        # Sonderzeichen escapen für JSON
        ESCAPED=$(echo "$CONTENT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || \
                  echo "$CONTENT" | sed 's/"/\\"/g; s/$/\\n/' | tr -d '\n')

        EMBED_JSON=$(curl -sf \
            -H "Content-Type: application/json" \
            ${OLLAMA_KEY:+-H "Authorization: Bearer $OLLAMA_KEY"} \
            -d "{\"model\":\"nomic-embed-text\",\"prompt\":${ESCAPED}}" \
            "$OLLAMA_URL/api/embeddings" 2>/dev/null || echo "")

        if [ -n "$EMBED_JSON" ]; then
            VECTOR=$(echo "$EMBED_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
vec = data.get('embedding', [])
print('[' + ','.join(str(v) for v in vec) + ']')
" 2>/dev/null)

            if [ -n "$VECTOR" ] && [ "$VECTOR" != "[]" ]; then
                psql_cmd "INSERT INTO ${SCHEMA}.embeddings (chunk_id, model, vector)
                          VALUES ('$CHUNK_ID', 'nomic-embed-text', '$VECTOR'::vector)
                          ON CONFLICT DO NOTHING;" > /dev/null
                EMBEDDED=$((EMBEDDED+1))
                printf "\r  → Eingebettet: %d/%d" "$EMBEDDED" "$CHUNK_COUNT"
            fi
        fi
    done <<< "$CHUNK_DATA"
    echo ""
    ok "$EMBEDDED echte Embeddings generiert"

else
    # Dummy-Embeddings (normalisierte Zufallsvektoren, 768-dimensional)
    echo -e "  ${YELLOW}Modus: Dummy-Embeddings (normalisierte Zufallsvektoren)${NC}"
    warn "Für echte Suche: --with-ollama Flag nutzen"
    info "Füge Dummy-Embeddings ein..."

    # Python generiert normalisierte 768d Vektoren
    python3 - <<PYEOF
import subprocess, random, math

pg_container = "$PG_CONTAINER"
pg_pass = "$PG_PASS"
schema = "$SCHEMA"

chunks_raw = """$CHUNK_DATA"""
chunks = [(line.split('|')[0], line.split('|', 1)[1]) for line in chunks_raw.strip().splitlines() if '|' in line]

# Cluster-Vektoren: Chunks zu ähnlichen Themen bekommen ähnliche Vektoren
# (simuliert semantische Nähe ohne echtes LLM)
topics = {
    'produkt':       [random.gauss(0.8, 0.1) if i < 20 else random.gauss(0, 0.1) for i in range(768)],
    'installation':  [random.gauss(0, 0.1) if i < 20 else random.gauss(0.7, 0.1) if i < 40 else random.gauss(0, 0.1) for i in range(768)],
    'preise':        [random.gauss(0, 0.1) if i < 40 else random.gauss(0.9, 0.1) if i < 60 else random.gauss(0, 0.1) for i in range(768)],
    'support':       [random.gauss(0, 0.1) if i < 60 else random.gauss(0.8, 0.1) if i < 80 else random.gauss(0, 0.1) for i in range(768)],
    'datenschutz':   [random.gauss(0, 0.1) if i < 80 else random.gauss(0.85, 0.1) if i < 100 else random.gauss(0, 0.1) for i in range(768)],
}

def normalize(vec):
    norm = math.sqrt(sum(x*x for x in vec))
    return [x/norm for x in vec] if norm > 0 else vec

def topic_for_content(content):
    content_lower = content.lower()
    for key in topics:
        if key in content_lower:
            return key
    return random.choice(list(topics.keys()))

for chunk_id, content in chunks:
    topic = topic_for_content(content)
    base = topics[topic]
    # Etwas Rauschen hinzufügen
    noisy = [b + random.gauss(0, 0.05) for b in base]
    normed = normalize(noisy)
    vec_str = '[' + ','.join(f'{v:.6f}' for v in normed) + ']'

    sql = f"""INSERT INTO {schema}.embeddings (chunk_id, model, vector)
              VALUES ('{chunk_id}', 'nomic-embed-text', '{vec_str}'::vector(768))
              ON CONFLICT DO NOTHING;"""

    result = subprocess.run(
        ['docker', 'exec', '-e', f'PGPASSWORD={pg_pass}', pg_container,
         'psql', '-U', 'postgres', '-d', 'app_db', '-c', sql],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Fehler bei Chunk {chunk_id}: {result.stderr[:100]}")

print(f"  → {len(chunks)} Dummy-Embeddings eingefügt")
PYEOF
fi

# ── 6. Status-Ausgabe ────────────────────────────────────────────────────
echo ""
info "Datenbank-Status nach Seed:"
docker exec -e PGPASSWORD="$PG_PASS" "$PG_CONTAINER" \
    psql -U postgres -d app_db -c "
SELECT
    (SELECT COUNT(*) FROM ${SCHEMA}.sources)     AS quellen,
    (SELECT COUNT(*) FROM ${SCHEMA}.documents)   AS dokumente,
    (SELECT COUNT(*) FROM ${SCHEMA}.chunks)      AS chunks,
    (SELECT COUNT(*) FROM ${SCHEMA}.embeddings)  AS embeddings
;" 2>/dev/null

# ── 7. Test-Suche ────────────────────────────────────────────────────────
echo ""
info "Test-Suche mit Beispiel-Query..."
python3 - <<PYEOF
import subprocess, math, random

pg_container = "$PG_CONTAINER"
pg_pass = "$PG_PASS"
schema = "$SCHEMA"

# Simulations-Vektor für "Preis" (entspricht annähernd dem Preis-Cluster)
base = [0.0]*768
for i in range(40, 60):
    base[i] = 0.9
norm = math.sqrt(sum(x*x for x in base))
query_vec = [x/norm if norm > 0 else 0 for x in base]

# Mit echten Embeddings: ersten Embedding-Vektor als Query nutzen
result = subprocess.run(
    ['docker', 'exec', '-e', f'PGPASSWORD={pg_pass}', pg_container,
     'psql', '-U', 'postgres', '-d', 'app_db', '-t', '-A', '-F', '||',
     '-c', f"SELECT content, 1-(vector<=>vector) FROM {schema}.embeddings e JOIN {schema}.chunks c ON c.id=e.chunk_id ORDER BY e.vector <=> vector LIMIT 3;"],
    capture_output=True, text=True
)

if result.returncode == 0 and result.stdout.strip():
    print("  Top-3 ähnlichste Chunks (interne Vektordistanz):")
    for i, line in enumerate(result.stdout.strip().splitlines()[:3], 1):
        if '||' in line:
            content, sim = line.split('||', 1)
            print(f"    [{i}] {content[:80]}... (sim: {sim.strip()[:6]})")
else:
    print("  (Suche übersprungen — Embeddings noch nicht verarbeitbar)")
PYEOF

# ── 8. Abschluss ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Testdaten eingefügt!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BLUE}Nächste Schritte:${NC}"
echo ""
echo -e "  1. Webapp starten:  bash scripts/serve-webapp.sh"
echo -e "     Dann im Browser: http://localhost:8080"
echo ""
echo -e "  2. CLI-Test:        bash scripts/test-rag-path.sh --tenant $TENANT_SLUG"
echo ""
echo -e "  3. Echte Embeddings (mit Ollama):"
echo -e "     bash scripts/seed-test-data.sh --tenant $TENANT_SLUG --with-ollama"
echo ""
