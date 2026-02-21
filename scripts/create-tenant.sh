#!/bin/bash
# create-tenant.sh — Neuen Tenant anlegen (DB-Schema + S3-Prefix)
# Verwendung: ./create-tenant.sh <slug> <name> <email> [plan]
# Beispiel:   ./create-tenant.sh acme "ACME GmbH" admin@acme.de starter

set -euo pipefail

SLUG="${1:?Verwendung: $0 <slug> <name> <email> [plan]}"
NAME="${2:?Name fehlt}"
EMAIL="${3:?E-Mail fehlt}"
PLAN="${4:-starter}"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres-rag}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD nicht gesetzt}"

# Slug validieren
if ! echo "$SLUG" | grep -qE '^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$'; then
    echo "FEHLER: Slug muss lowercase alphanumerisch sein (a-z, 0-9, _ -)"
    echo "Beispiel: acme, muster-gmbh, test_kunde_1"
    exit 1
fi

echo "Lege Tenant an:"
echo "  Slug:   $SLUG"
echo "  Name:   $NAME"
echo "  E-Mail: $EMAIL"
echo "  Plan:   $PLAN"
echo ""

# Tenant in PostgreSQL anlegen
RESULT=$(docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$POSTGRES_CONTAINER" \
    psql -U "$POSTGRES_USER" -d app_db -t -c \
    "SELECT public.create_tenant('$SLUG', '$NAME', '$EMAIL', '$PLAN');" 2>&1)

if echo "$RESULT" | grep -q "ERROR\|error"; then
    echo "FEHLER beim Anlegen: $RESULT"
    exit 1
fi

TENANT_ID=$(echo "$RESULT" | xargs)
echo "Tenant angelegt. ID: $TENANT_ID"

# Berechtigungen vergeben
docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$POSTGRES_CONTAINER" \
    psql -U "$POSTGRES_USER" -d app_db -c \
    "SELECT public.grant_tenant_permissions('tenant_$SLUG');" > /dev/null

echo "Berechtigungen gesetzt für Schema: tenant_$SLUG"

# HNSW Index (erst nach Daten-Import sinnvoll, daher Hinweis)
echo ""
echo "Nächste Schritte:"
echo "  1. Dokumente hochladen via n8n Ingestion-Workflow"
echo "  2. Nach > 1000 Embeddings: HNSW Index erstellen:"
echo "     SELECT public.create_vector_index('tenant_$SLUG');"
echo "  3. S3-Prefix 'tenants/$SLUG/' wird automatisch genutzt"
echo ""
echo "Tenant $SLUG bereit."
