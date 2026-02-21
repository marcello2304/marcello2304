-- Migration 004: Hilfsfunktionen

-- Tenant anlegen (Schema + öffentlicher Eintrag)
CREATE OR REPLACE FUNCTION public.create_tenant(
    p_slug    TEXT,
    p_name    TEXT,
    p_email   TEXT,
    p_plan    TEXT DEFAULT 'starter'
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_tenant_id  UUID;
    v_schema     TEXT;
    v_sql        TEXT;
BEGIN
    -- Tenant in public.tenants einfügen
    INSERT INTO public.tenants (slug, name, email, plan)
    VALUES (p_slug, p_name, p_email, p_plan)
    RETURNING id, schema_name INTO v_tenant_id, v_schema;

    -- Schema erstellen (dynamisches SQL)
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', v_schema);

    -- Tabellen anlegen (aus Template)
    -- sources
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.sources (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name          TEXT NOT NULL,
            source_type   TEXT NOT NULL CHECK (source_type IN (''file'', ''url'', ''api'', ''manual'')),
            origin_url    TEXT,
            s3_key        TEXT,
            file_name     TEXT,
            file_type     TEXT CHECK (file_type IN (''pdf'', ''docx'', ''txt'', ''html'', ''md'', ''csv'', ''json'', ''other'')),
            file_size     BIGINT,
            checksum      TEXT,
            status        TEXT NOT NULL DEFAULT ''pending'' CHECK (status IN (''pending'', ''processing'', ''indexed'', ''error'', ''deleted'')),
            error_message TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by    TEXT,
            tags          TEXT[] DEFAULT ''{}'',
            metadata      JSONB DEFAULT ''{}''
        )', v_schema);

    -- documents
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.documents (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id     UUID NOT NULL REFERENCES %I.sources(id) ON DELETE CASCADE,
            title         TEXT,
            doc_type      TEXT DEFAULT ''general'' CHECK (doc_type IN (''faq'', ''manual'', ''product'', ''legal'', ''support'', ''general'', ''other'')),
            language      TEXT DEFAULT ''de'',
            version       INT NOT NULL DEFAULT 1,
            is_active     BOOLEAN NOT NULL DEFAULT true,
            word_count    INT,
            char_count    INT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            metadata      JSONB DEFAULT ''{}''
        )', v_schema, v_schema);

    -- chunks
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.chunks (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id   UUID NOT NULL REFERENCES %I.documents(id) ON DELETE CASCADE,
            source_id     UUID NOT NULL REFERENCES %I.sources(id) ON DELETE CASCADE,
            chunk_index   INT NOT NULL,
            content       TEXT NOT NULL,
            content_hash  TEXT,
            token_count   INT,
            char_count    INT,
            page_number   INT,
            section       TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            metadata      JSONB DEFAULT ''{}'',
            UNIQUE(document_id, chunk_index)
        )', v_schema, v_schema, v_schema);

    -- embeddings
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.embeddings (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chunk_id      UUID NOT NULL REFERENCES %I.chunks(id) ON DELETE CASCADE,
            model         TEXT NOT NULL,
            model_version TEXT,
            vector        vector(768),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )', v_schema, v_schema);

    -- conversations
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.conversations (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id    TEXT NOT NULL,
            bot_id        TEXT,
            query         TEXT NOT NULL,
            response      TEXT,
            chunks_used   UUID[] DEFAULT ''{}'',
            model         TEXT,
            latency_ms    INT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            metadata      JSONB DEFAULT ''{}''
        )', v_schema);

    -- Indizes
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_sources_status  ON %I.sources(status)', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_sources_created ON %I.sources(created_at DESC)', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_docs_source     ON %I.documents(source_id)', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_docs_active     ON %I.documents(is_active) WHERE is_active = true', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_chunks_doc      ON %I.chunks(document_id)', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_chunks_fts      ON %I.chunks USING gin(to_tsvector(''german'', content))', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_embed_chunk     ON %I.embeddings(chunk_id)', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_embed_model     ON %I.embeddings(model)', v_schema);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_conv_session    ON %I.conversations(session_id)', v_schema);

    -- Triggers
    EXECUTE format('
        CREATE TRIGGER trg_sources_updated_at
            BEFORE UPDATE ON %I.sources
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', v_schema);

    EXECUTE format('
        CREATE TRIGGER trg_docs_updated_at
            BEFORE UPDATE ON %I.documents
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', v_schema);

    RETURN v_tenant_id;
END;
$$;


-- Semantic Search für einen Tenant
CREATE OR REPLACE FUNCTION public.search_chunks(
    p_schema      TEXT,
    p_query_vec   vector(768),
    p_top_k       INT DEFAULT 5,
    p_min_sim     FLOAT DEFAULT 0.5,
    p_model       TEXT DEFAULT 'nomic-embed-text',
    p_doc_type    TEXT DEFAULT NULL,
    p_role        TEXT DEFAULT 'public'
)
RETURNS TABLE (
    chunk_id        UUID,
    content         TEXT,
    chunk_index     INT,
    page_number     INT,
    section         TEXT,
    document_title  TEXT,
    doc_type        TEXT,
    file_name       TEXT,
    s3_key          TEXT,
    similarity      FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_sql TEXT;
BEGIN
    v_sql := format('
        SELECT
            c.id,
            c.content,
            c.chunk_index,
            c.page_number,
            c.section,
            d.title,
            d.doc_type,
            s.file_name,
            s.s3_key,
            1 - (e.vector <=> $1) AS similarity
        FROM %I.embeddings e
        JOIN %I.chunks c ON c.id = e.chunk_id
        JOIN %I.documents d ON d.id = c.document_id
        JOIN %I.sources s ON s.id = c.source_id
        WHERE
            d.is_active = true
            AND s.status = ''indexed''
            AND e.model = $4
            AND 1 - (e.vector <=> $1) >= $3
            AND ($5::text IS NULL OR d.doc_type = $5)
        ORDER BY e.vector <=> $1
        LIMIT $2',
        p_schema, p_schema, p_schema, p_schema);

    RETURN QUERY EXECUTE v_sql
        USING p_query_vec, p_top_k, p_min_sim, p_model, p_doc_type;
END;
$$;


-- HNSW Index für einen Tenant erstellen (nach Bulk-Import)
CREATE OR REPLACE FUNCTION public.create_vector_index(
    p_schema TEXT,
    p_m      INT DEFAULT 16,
    p_ef     INT DEFAULT 64
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_embed_hnsw
        ON %I.embeddings
        USING hnsw (vector vector_cosine_ops)
        WITH (m = %s, ef_construction = %s)',
        p_schema, p_m, p_ef);
END;
$$;


-- Tenant-Statistiken
CREATE OR REPLACE FUNCTION public.get_tenant_stats(p_slug TEXT)
RETURNS TABLE (
    schema_name   TEXT,
    source_count  BIGINT,
    doc_count     BIGINT,
    chunk_count   BIGINT,
    embed_count   BIGINT,
    conv_count    BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_schema TEXT;
    v_sql    TEXT;
BEGIN
    SELECT t.schema_name INTO v_schema FROM public.tenants t WHERE t.slug = p_slug;
    IF v_schema IS NULL THEN
        RAISE EXCEPTION 'Tenant % not found', p_slug;
    END IF;

    RETURN QUERY EXECUTE format('
        SELECT
            %L::text,
            (SELECT COUNT(*) FROM %I.sources)::bigint,
            (SELECT COUNT(*) FROM %I.documents)::bigint,
            (SELECT COUNT(*) FROM %I.chunks)::bigint,
            (SELECT COUNT(*) FROM %I.embeddings)::bigint,
            (SELECT COUNT(*) FROM %I.conversations)::bigint',
        v_schema, v_schema, v_schema, v_schema, v_schema, v_schema);
END;
$$;
