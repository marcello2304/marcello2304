-- Migration 003: RAG-Tabellen (flaches Public-Schema mit tenant_id)
-- Passend zu den n8n-Workflows: eppcom-ingestion-workflow + eppcom-rag-chat-workflow
-- Dimension: 1024 (qwen3-embedding:0.6b)
-- Ausführen: docker exec -i postgres-rag psql -U postgres -d app_db < sql/003_rag_tables.sql

SET search_path TO public;

-- ── api_keys ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    key_hash    TEXT NOT NULL UNIQUE,   -- SHA-256 des Klartexts
    name        TEXT NOT NULL DEFAULT 'default',
    permissions JSONB DEFAULT '["read","write"]'::jsonb,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant   ON public.api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash     ON public.api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_active   ON public.api_keys(is_active) WHERE is_active = true;

-- ── sources ──────────────────────────────────────────────────────────────────
-- Metadaten zu jedem importierten Dokument
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
CREATE INDEX IF NOT EXISTS idx_sources_tenant    ON public.sources(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sources_status    ON public.sources(status);

-- ── documents ────────────────────────────────────────────────────────────────
-- Rohinhalt eines Dokuments (1 Source → 1 Document)
CREATE TABLE IF NOT EXISTS public.documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_tenant  ON public.documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_source  ON public.documents(source_id);

-- ── chunks ───────────────────────────────────────────────────────────────────
-- Einzelne Textabschnitte (2000 Zeichen, 200 Overlap)
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
CREATE INDEX IF NOT EXISTS idx_chunks_tenant     ON public.chunks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document   ON public.chunks(document_id);

-- ── embeddings ───────────────────────────────────────────────────────────────
-- Vektoren (1024 Dimensionen — qwen3-embedding:0.6b)
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

-- ── Updated-At Trigger für sources ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.sources_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$;

DROP TRIGGER IF EXISTS trg_sources_updated ON public.sources;
CREATE TRIGGER trg_sources_updated
    BEFORE UPDATE ON public.sources
    FOR EACH ROW EXECUTE FUNCTION public.sources_set_updated_at();

-- ── search_similar ───────────────────────────────────────────────────────────
-- Wird vom RAG-Chat-Workflow aufgerufen:
-- SELECT * FROM search_similar(tenant_id::uuid, query_vector::vector(1024), 5, 0.3)
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

-- ── is_active Spalte für tenants (falls nicht vorhanden) ─────────────────────
-- Der n8n-Auth-Check prüft t.is_active = true
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tenants' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE public.tenants ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
    END IF;
END$$;

-- Index falls nicht vorhanden
CREATE INDEX IF NOT EXISTS idx_tenants_active ON public.tenants(is_active) WHERE is_active = true;

SELECT 'Migration 003 abgeschlossen: api_keys, sources, documents, chunks, embeddings, search_similar()' AS status;
