#!/bin/bash
set -e

echo "========================================"
echo "EPPCOM VOICEBOT E2E TEST SUITE"
echo "========================================"

OLLAMA_URL="${OLLAMA_URL:-http://46.224.54.65:11434}"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

test_model_available() {
    echo -e "\n${YELLOW}[Test 1]${NC} Model Availability: qwen2.5:7b-eppcom"
    RESULT=$(curl -s "$OLLAMA_URL/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
if 'qwen2.5:7b-eppcom:latest' in models or 'qwen2.5:7b-eppcom' in models:
    print('FOUND')
else:
    print('NOT_FOUND: ' + str(models))
" 2>/dev/null)

    if echo "$RESULT" | grep -q "FOUND"; then
        echo -e "${GREEN}PASSED - Model verfuegbar${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED - $RESULT${NC}"
        ((FAILED++))
    fi
}

test_embedding_generation() {
    echo -e "\n${YELLOW}[Test 2]${NC} Embedding Generation"

    RESULT=$(curl -s -X POST "$OLLAMA_URL/api/embed" \
        -d '{"model":"qwen3-embedding:0.6b","input":"Was ist Self-Hosting?"}' \
        | python3 -c "
import sys, json
data = json.load(sys.stdin)
emb = data.get('embeddings', [[]])
if emb and len(emb[0]) == 1024:
    print(f'OK: 1024 dims')
else:
    print(f'FAIL: {len(emb[0]) if emb else 0} dims')
" 2>/dev/null)

    if echo "$RESULT" | grep -q "OK"; then
        echo -e "${GREEN}PASSED - $RESULT${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED - $RESULT${NC}"
        ((FAILED++))
    fi
}

test_llm_response_quality() {
    echo -e "\n${YELLOW}[Test 3]${NC} LLM Response Quality"

    RESPONSE=$(curl -s -X POST "$OLLAMA_URL/api/generate" \
        -d '{
            "model":"qwen2.5:7b-eppcom",
            "prompt":"KONTEXT: EPPCOM bietet Self-Hosted RAG-Loesungen auf deutschen Servern. Kein Vendor-Lock-in, DSGVO-konform.\n\nFRAGE: Warum ist Self-Hosting wichtig?\n\nANTWORT:",
            "stream":false,
            "options":{"temperature":0.7,"num_predict":100}
        }' | python3 -c "import sys,json; print(json.load(sys.stdin).get('response',''))" 2>/dev/null)

    echo "  Response: ${RESPONSE:0:200}"

    if echo "$RESPONSE" | grep -qiE "(daten|dsgvo|server|deutschland|kontrolle|sicher|hosting)"; then
        echo -e "${GREEN}PASSED - Relevante Keywords gefunden${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED - Keine relevanten Keywords${NC}"
        ((FAILED++))
    fi
}

test_llm_latency() {
    echo -e "\n${YELLOW}[Test 4]${NC} LLM Latency (<15s fuer 100 tokens)"

    START=$(date +%s%3N)
    curl -s -X POST "$OLLAMA_URL/api/generate" \
        -d '{
            "model":"qwen2.5:7b-eppcom",
            "prompt":"Was macht EPPCOM?",
            "stream":false,
            "options":{"num_predict":100}
        }' > /dev/null

    END=$(date +%s%3N)
    DURATION=$((END - START))

    echo "  Duration: ${DURATION}ms"

    if [ $DURATION -lt 15000 ]; then
        echo -e "${GREEN}PASSED - Unter 15s${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED - Zu langsam (${DURATION}ms)${NC}"
        ((FAILED++))
    fi
}

test_rag_db_populated() {
    echo -e "\n${YELLOW}[Test 5]${NC} RAG DB: EPPCOM Tenant hat Embeddings"

    RESULT=$(docker exec eppcom-admin-ui python3 -c "
import asyncio, asyncpg, os
async def check():
    db = await asyncpg.connect(os.environ['DATABASE_URL'])
    r = await db.fetchrow(\"SELECT COUNT(*) as cnt FROM embeddings WHERE tenant_id='a0000000-0000-0000-0000-000000000001'::uuid\")
    print(f'EMBEDS:{r[\"cnt\"]}')
    await db.close()
asyncio.run(check())
" 2>&1)

    COUNT=$(echo "$RESULT" | grep -oP 'EMBEDS:\K\d+')
    echo "  Embeddings: $COUNT"

    if [ "$COUNT" -gt 0 ]; then
        echo -e "${GREEN}PASSED - $COUNT Embeddings vorhanden${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED - Keine Embeddings${NC}"
        ((FAILED++))
    fi
}

test_vector_search() {
    echo -e "\n${YELLOW}[Test 6]${NC} Vector Search: Relevante Chunks finden"

    RESULT=$(docker exec eppcom-admin-ui python3 -c "
import asyncio, asyncpg, os, httpx

async def search():
    db = await asyncpg.connect(os.environ['DATABASE_URL'])
    client = httpx.AsyncClient()

    resp = await client.post('http://46.224.54.65:11434/api/embed', json={
        'model': 'qwen3-embedding:0.6b',
        'input': 'Self-Hosting DSGVO Datenschutz'
    }, timeout=15)
    emb = resp.json()['embeddings'][0]

    rows = await db.fetch('''
        SELECT c.content, s.name,
               1 - (e.embedding <=> \$1::vector) AS similarity
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE e.tenant_id = 'a0000000-0000-0000-0000-000000000001'::uuid
        ORDER BY similarity DESC
        LIMIT 3
    ''', str(emb))

    for r in rows:
        sim = round(float(r['similarity']), 3)
        print(f'SIM:{sim} SRC:{r[\"name\"][:40]} CONTENT:{r[\"content\"][:60]}')

    await client.aclose()
    await db.close()

asyncio.run(search())
" 2>&1)

    echo "  $RESULT" | head -3

    if echo "$RESULT" | grep -qE "SIM:0\.[3-9]"; then
        echo -e "${GREEN}PASSED - Relevante Chunks mit Similarity > 0.3${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED - Keine relevanten Chunks${NC}"
        ((FAILED++))
    fi
}

# Run all tests
test_model_available
test_embedding_generation
test_llm_response_quality
test_llm_latency
test_rag_db_populated
test_vector_search

# Summary
echo -e "\n========================================"
echo "TEST SUMMARY"
echo "========================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "========================================"

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
