#!/bin/bash
# setup-rag-db.sh — Erstellt app_db + führt alle RAG-Migrationen aus
# Kompatibel mit Coolify-PostgreSQL (appuser, auto-detect container)
#
# Verwendung: bash scripts/setup-rag-db.sh
# Voraussetzung: Docker muss auf dem Host laufen

set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC}  $1"; exit 1; }
info() { echo -e "  ${BLUE}→${NC}  $1"; }
warn() { echo -e "  ${YELLOW}!${NC}  $1"; }
step() { echo -e "\n${BLUE}${BOLD}── $1 ──${NC}"; }

echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  RAG Datenbank Setup${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"

# ── Schritt 1: Postgres Container ermitteln ───────────────────────────────────
step "1/6 Postgres-Container erkennen"

PG_CONTAINER="${PG_CONTAINER:-}"
if [ -z "$PG_CONTAINER" ]; then
    PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep '^postgres-' | head -1 || true)
fi
if [ -z "$PG_CONTAINER" ]; then
    PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -i 'postgres' | head -1 || true)
fi
if [ -z "$PG_CONTAINER" ]; then
    fail "Kein Postgres-Container gefunden. Setze PG_CONTAINER=<name> manuell."
fi
ok "Container: $PG_CONTAINER"

# ── Schritt 2: DB-User ermitteln ──────────────────────────────────────────────
step "2/6 Datenbankbenutzer erkennen"

DB_USER="${DB_USER:-}"
if [ -z "$DB_USER" ]; then
    # Coolify nutzt appuser
    if docker exec -i "$PG_CONTAINER" psql -U appuser -d postgres -c "SELECT 1" &>/dev/null 2>&1; then
        DB_USER="appuser"
    elif docker exec -i "$PG_CONTAINER" psql -U postgres -d postgres -c "SELECT 1" &>/dev/null 2>&1; then
        DB_USER="postgres"
    else
        # Versuche via su postgres (Coolify Terminal-Modus)
        DB_USER="appuser"
        warn "Konnte User nicht automatisch ermitteln, versuche 'appuser'"
    fi
fi
ok "DB-User: $DB_USER"

# Hilfsfunktion: SQL in postgres ausführen
pg_exec() {
    local db="${1:-postgres}"
    local sql="$2"
    docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d "$db" -v ON_ERROR_STOP=1 -c "$sql" 2>&1
}

pg_exec_file() {
    local db="$1"
    docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d "$db" -v ON_ERROR_STOP=1
}

# ── Schritt 3: app_db erstellen ───────────────────────────────────────────────
step "3/6 Datenbank app_db"

DB_EXISTS=$(docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='app_db'" 2>/dev/null | xargs || echo "0")

if [ "$DB_EXISTS" = "1" ]; then
    ok "app_db existiert bereits"
else
    info "Erstelle app_db..."
    docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d postgres \
        -c "CREATE DATABASE app_db OWNER $DB_USER;" 2>&1
    ok "app_db erstellt"
fi

# ── Schritt 4: Migrationen ausführen ─────────────────────────────────────────
step "4/6 Migrationen (001 → 003 → 004 → eppcom)"

info "Migration 001: Extensions..."
docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -v ON_ERROR_STOP=1 <<'EOSQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
SELECT 'Migration 001 OK: vector, uuid-ossp, pg_trgm, unaccent' AS status;
EOSQL
ok "001 Extensions"

info "Migration 002: Public Schema (tenants)..."
docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -v ON_ERROR_STOP=1 <<'EOSQL'
SET search_path TO public;

CREATE TABLE IF NOT EXISTS public.tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT NOT NULL UNIQUE
                    CHECK (slug ~ '^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$'),
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    plan          TEXT NOT NULL DEFAULT 'starter'
                    CHECK (plan IN ('starter', 'pro', 'enterprise')),
    status        TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'suspended', 'deleted')),
    is_active     BOOLEAN NOT NULL DEFAULT true,
    schema_name   TEXT NOT NULL UNIQUE
                    GENERATED ALWAYS AS ('tenant_' || slug) STORED,
    s3_prefix     TEXT NOT NULL UNIQUE
                    GENERATED ALWAYS AS ('tenants/' || slug || '/') STORED,
    max_docs      INT NOT NULL DEFAULT 500,
    max_chunks    INT NOT NULL DEFAULT 50000,
    max_s3_bytes  BIGINT NOT NULL DEFAULT 5368709120,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tenants_slug   ON public.tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON public.tenants(status);
CREATE INDEX IF NOT EXISTS idx_tenants_active ON public.tenants(is_active) WHERE is_active = true;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_tenants_updated_at ON public.tenants;
CREATE TRIGGER trg_tenants_updated_at
    BEFORE UPDATE ON public.tenants
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

SELECT 'Migration 002 OK: tenants' AS status;
EOSQL
ok "002 Tenants-Tabelle"

info "Migration 003: RAG-Tabellen (api_keys, sources, documents, chunks, embeddings)..."
docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -v ON_ERROR_STOP=1 <<'EOSQL'
SET search_path TO public;

-- api_keys
CREATE TABLE IF NOT EXISTS public.api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    key_hash    TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL DEFAULT 'default',
    permissions JSONB DEFAULT '["read","write"]'::jsonb,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON public.api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash   ON public.api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON public.api_keys(is_active) WHERE is_active = true;

-- sources
CREATE TABLE IF NOT EXISTS public.sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual'
                    CHECK (source_type IN ('manual', 'file', 'url', 'pdf')),
    s3_key      TEXT,
    s3_bucket   TEXT,
    status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'error', 'deleted')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata    JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sources_tenant ON public.sources(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sources_status ON public.sources(status);

DROP TRIGGER IF EXISTS trg_sources_updated ON public.sources;
CREATE OR REPLACE FUNCTION public.sources_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$;
CREATE TRIGGER trg_sources_updated
    BEFORE UPDATE ON public.sources
    FOR EACH ROW EXECUTE FUNCTION public.sources_set_updated_at();

-- documents
CREATE TABLE IF NOT EXISTS public.documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON public.documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_source ON public.documents(source_id);

-- chunks
CREATE TABLE IF NOT EXISTS public.chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    chunk_index INT NOT NULL,
    token_count INT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata    JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_chunks_tenant   ON public.chunks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON public.chunks(document_id);

-- embeddings (1024 Dimensionen — qwen3-embedding:0.6b)
CREATE TABLE IF NOT EXISTS public.embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id    UUID NOT NULL REFERENCES public.chunks(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    embedding   vector(1024) NOT NULL,
    model_name  TEXT NOT NULL DEFAULT 'qwen3-embedding:0.6b',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_embeddings_tenant ON public.embeddings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk  ON public.embeddings(chunk_id);

-- search_similar() — von RAG-Chat-Workflow aufgerufen
CREATE OR REPLACE FUNCTION public.search_similar(
    p_tenant_id  UUID,
    p_vector     vector(1024),
    p_top_k      INT     DEFAULT 5,
    p_min_sim    FLOAT   DEFAULT 0.3
)
RETURNS TABLE (
    chunk_id    UUID,
    similarity  FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.chunk_id,
        (1 - (e.embedding <=> p_vector))::FLOAT AS similarity
    FROM public.embeddings e
    WHERE
        e.tenant_id = p_tenant_id
        AND (1 - (e.embedding <=> p_vector)) >= p_min_sim
    ORDER BY e.embedding <=> p_vector
    LIMIT p_top_k;
END;
$$;

SELECT 'Migration 003 OK: api_keys, sources, documents, chunks, embeddings, search_similar()' AS status;
EOSQL
ok "003 RAG-Tabellen + search_similar()"

info "EPPCOM Tenant + API-Keys anlegen..."
docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -v ON_ERROR_STOP=1 <<'EOSQL'
-- EPPCOM Tenant
INSERT INTO public.tenants (id, slug, name, email, plan, is_active)
VALUES (
    'a0000000-0000-0000-0000-000000000001'::uuid,
    'eppcom',
    'EPPCOM GmbH',
    'eppler@eppcom.de',
    'pro',
    true
)
ON CONFLICT (id) DO UPDATE
    SET is_active = true, name = EXCLUDED.name;

-- API-Key 1: test-key-123
INSERT INTO public.api_keys (id, tenant_id, key_hash, name, is_active)
VALUES (
    'b0000000-0000-0000-0000-000000000001'::uuid,
    'a0000000-0000-0000-0000-000000000001'::uuid,
    encode(sha256('test-key-123'::bytea), 'hex'),
    'Test API Key',
    true
)
ON CONFLICT (id) DO UPDATE SET is_active = true;

-- API-Key 2: ***API_KEY_REMOVED***
INSERT INTO public.api_keys (id, tenant_id, key_hash, name, is_active)
VALUES (
    'b0000000-0000-0000-0000-000000000002'::uuid,
    'a0000000-0000-0000-0000-000000000001'::uuid,
    encode(sha256('***API_KEY_REMOVED***'::bytea), 'hex'),
    'EPPCOM Produktiv Key 2025',
    true
)
ON CONFLICT (id) DO UPDATE SET is_active = true;

SELECT 'Tenant:' AS typ, id::text, slug, name, is_active::text FROM public.tenants
WHERE id = 'a0000000-0000-0000-0000-000000000001'::uuid
UNION ALL
SELECT 'API-Key:', id::text, name, LEFT(key_hash, 20) || '...', is_active::text
FROM public.api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'::uuid
ORDER BY typ DESC;
EOSQL
ok "EPPCOM Tenant + API-Keys"

# ── Schritt 5: Berechtigungen ─────────────────────────────────────────────────
step "5/6 Berechtigungen"

docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -v ON_ERROR_STOP=1 <<EOSQL
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO ${DB_USER};
SELECT 'Berechtigungen OK' AS status;
EOSQL
ok "Berechtigungen gesetzt"

# ── Schritt 6: Verifikation ───────────────────────────────────────────────────
step "6/6 Verifikation"

TABLE_COUNT=$(docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" 2>/dev/null | xargs)

TENANT_COUNT=$(docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -tAc \
    "SELECT COUNT(*) FROM public.tenants WHERE is_active=true" 2>/dev/null | xargs)

APIKEY_COUNT=$(docker exec -i "$PG_CONTAINER" psql -U "$DB_USER" -d app_db -tAc \
    "SELECT COUNT(*) FROM public.api_keys WHERE is_active=true" 2>/dev/null | xargs)

echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  Setup abgeschlossen ✓${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"
echo ""
ok "Tabellen in app_db: $TABLE_COUNT"
ok "Aktive Tenants: $TENANT_COUNT"
ok "Aktive API-Keys: $APIKEY_COUNT"
echo ""
echo -e "${BOLD}Tenant-Info:${NC}"
echo -e "  UUID:    ${YELLOW}a0000000-0000-0000-0000-000000000001${NC}"
echo -e "  API-Key: ${YELLOW}test-key-123${NC}"
echo -e "  API-Key: ${YELLOW}***API_KEY_REMOVED***${NC}"
echo ""
echo -e "${BOLD}Nächster Schritt — n8n Credential aktualisieren:${NC}"
echo -e "  n8n UI → Settings → Credentials → 'Postgres account'"
echo -e "  Host:     ${YELLOW}${PG_CONTAINER}${NC}"
echo -e "  Database: ${YELLOW}app_db${NC}"
echo -e "  User:     ${YELLOW}${DB_USER}${NC}"
echo -e "  Port:     ${YELLOW}5432${NC}"
echo ""
echo -e "${BOLD}Dann Webhooks testen:${NC}"
echo -e "  ${YELLOW}bash scripts/test-webhooks.sh${NC}"
echo ""
