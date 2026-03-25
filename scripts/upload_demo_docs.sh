#!/bin/bash
# Upload all demo PDFs to the EPPCOM RAG platform via API
#
# Usage: ./upload_demo_docs.sh <session_token> <tenant_id>
# Example: ./upload_demo_docs.sh abc123token def456-tenant-uuid
#
# Get session token: Login via UI, check localStorage for 'rag_token'
# Get tenant_id: Check /api/tenants endpoint or Admin UI

set -euo pipefail

API_BASE="${API_BASE:-https://appdb.eppcom.de}"
TOKEN="${1:?Usage: $0 <session_token> <tenant_id>}"
TENANT_ID="${2:?Usage: $0 <session_token> <tenant_id>}"
DOCS_DIR="$(dirname "$0")/../demo_docs"

if [ ! -d "$DOCS_DIR" ]; then
  echo "ERROR: demo_docs directory not found at $DOCS_DIR"
  exit 1
fi

echo "=== EPPCOM Demo Document Upload ==="
echo "API: $API_BASE"
echo "Tenant: $TENANT_ID"
echo "Docs: $DOCS_DIR"
echo ""

SUCCESS=0
FAILED=0

for pdf in "$DOCS_DIR"/*.pdf; do
  filename=$(basename "$pdf")
  echo -n "Uploading: $filename ... "

  response=$(curl -s -w "\n%{http_code}" \
    -X POST "${API_BASE}/api/sources/ingest" \
    -H "X-Session-Token: ${TOKEN}" \
    -F "tenant_id=${TENANT_ID}" \
    -F "file=@${pdf}" \
    2>&1)

  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)

  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    chunks=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chunks_created','?'))" 2>/dev/null || echo "?")
    echo "OK ($chunks chunks)"
    SUCCESS=$((SUCCESS + 1))
  else
    detail=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('detail','Unknown error'))" 2>/dev/null || echo "$body")
    echo "FAILED ($http_code): $detail"
    FAILED=$((FAILED + 1))
  fi

  sleep 2
done

echo ""
echo "=== Done ==="
echo "Success: $SUCCESS"
echo "Failed: $FAILED"
echo "Total: $((SUCCESS + FAILED))"
