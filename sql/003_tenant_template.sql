-- Migration 003: Tenant-Schema Template
-- NICHT direkt ausführen — wird von Funktion in 004 aufgerufen
-- Platzhalter :SCHEMA_NAME wird durch tatsächlichen Schema-Namen ersetzt
--
-- Manuell für einen Tenant:
--   SELECT public.create_tenant_schema('acme');

-- Dieses File zeigt die Struktur. Die tatsächliche Erstellung
-- erfolgt über die Funktion create_tenant_schema() in 004_functions.sql

-- Beispiel für Schema: tenant_acme

CREATE SCHEMA IF NOT EXISTS tenant_acme;

SET search_path TO tenant_acme;

CREATE TABLE IF NOT EXISTS tenant_acme.sources (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    source_type   TEXT NOT NULL
                    CHECK (source_type IN ('file', 'url', 'api', 'manual')),
    origin_url    TEXT,
    s3_key        TEXT,
    file_name     TEXT,
    file_type     TEXT
                    CHECK (file_type IN ('pdf', 'docx', 'txt', 'html', 'md', 'csv', 'json', 'other')),
    file_size     BIGINT,
    checksum      TEXT,
    status        TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'indexed', 'error', 'deleted')),
    error_message TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by    TEXT,
    tags          TEXT[] DEFAULT '{}',
    metadata      JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tenant_acme.documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID NOT NULL
                    REFERENCES tenant_acme.sources(id) ON DELETE CASCADE,
    title         TEXT,
    doc_type      TEXT DEFAULT 'general'
                    CHECK (doc_type IN ('faq', 'manual', 'product', 'legal',
                                        'support', 'general', 'other')),
    language      TEXT DEFAULT 'de',
    version       INT NOT NULL DEFAULT 1,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    word_count    INT,
    char_count    INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tenant_acme.chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL
                    REFERENCES tenant_acme.documents(id) ON DELETE CASCADE,
    source_id     UUID NOT NULL
                    REFERENCES tenant_acme.sources(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    content       TEXT NOT NULL,
    content_hash  TEXT,
    token_count   INT,
    char_count    INT,
    page_number   INT,
    section       TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}',
    UNIQUE(document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS tenant_acme.embeddings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id      UUID NOT NULL
                    REFERENCES tenant_acme.chunks(id) ON DELETE CASCADE,
    model         TEXT NOT NULL,
    model_version TEXT,
    vector        vector(768),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_acme.access_rules (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID REFERENCES tenant_acme.sources(id) ON DELETE CASCADE,
    document_id   UUID REFERENCES tenant_acme.documents(id) ON DELETE CASCADE,
    role          TEXT NOT NULL DEFAULT 'public',
    allow         BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_target CHECK (
        (source_id IS NOT NULL AND document_id IS NULL) OR
        (source_id IS NULL AND document_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS tenant_acme.conversations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    TEXT NOT NULL,
    bot_id        TEXT,
    query         TEXT NOT NULL,
    response      TEXT,
    chunks_used   UUID[] DEFAULT '{}',
    model         TEXT,
    latency_ms    INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

-- Indizes
CREATE INDEX IF NOT EXISTS idx_sources_status   ON tenant_acme.sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_type     ON tenant_acme.sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_created  ON tenant_acme.sources(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sources_checksum ON tenant_acme.sources(checksum) WHERE checksum IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_docs_source      ON tenant_acme.documents(source_id);
CREATE INDEX IF NOT EXISTS idx_docs_active      ON tenant_acme.documents(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_docs_type        ON tenant_acme.documents(doc_type);

CREATE INDEX IF NOT EXISTS idx_chunks_doc       ON tenant_acme.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_source    ON tenant_acme.chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_hash      ON tenant_acme.chunks(content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chunks_fts
    ON tenant_acme.chunks USING gin(to_tsvector('german', content));

CREATE INDEX IF NOT EXISTS idx_embed_chunk      ON tenant_acme.embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_embed_model      ON tenant_acme.embeddings(model);

-- HNSW Vector Index (erst nach Bulk-Import erstellen!)
-- CREATE INDEX idx_embed_hnsw ON tenant_acme.embeddings
-- USING hnsw (vector vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_conv_session     ON tenant_acme.conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_created     ON tenant_acme.conversations(created_at DESC);

-- Updated_at Trigger
CREATE TRIGGER trg_sources_updated_at
    BEFORE UPDATE ON tenant_acme.sources
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_docs_updated_at
    BEFORE UPDATE ON tenant_acme.documents
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
