-- Migration 004: Hilfsfunktionen (Flat-Table-Design mit tenant_id)

-- Tenant anlegen (nur public.tenants Eintrag, keine separaten Schemas)
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
    v_tenant_id UUID;
BEGIN
    INSERT INTO public.tenants (slug, name, email, plan)
    VALUES (p_slug, p_name, p_email, p_plan)
    RETURNING id INTO v_tenant_id;

    RETURN v_tenant_id;
END;
$$;


-- Semantic Search für einen Tenant (Flat-Table-Design)
CREATE OR REPLACE FUNCTION public.search_chunks(
    p_tenant_id   UUID,
    p_query_vec   vector,
    p_top_k       INT DEFAULT 5,
    p_min_sim     FLOAT DEFAULT 0.3,
    p_model       TEXT DEFAULT 'qwen3-embedding:0.6b'
)
RETURNS TABLE (
    chunk_id        UUID,
    content         TEXT,
    chunk_index     INT,
    source_name     TEXT,
    similarity      FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.content,
        c.chunk_index,
        s.name,
        (1 - (e.embedding <=> p_query_vec))::double precision AS similarity
    FROM public.embeddings e
    JOIN public.chunks c ON c.id = e.chunk_id
    JOIN public.documents d ON d.id = c.document_id
    JOIN public.sources s ON s.id = d.source_id
    WHERE e.tenant_id = p_tenant_id
      AND e.model_name = p_model
      AND s.status IN ('completed', 'indexed')
      AND (1 - (e.embedding <=> p_query_vec)) >= p_min_sim
    ORDER BY e.embedding <=> p_query_vec
    LIMIT p_top_k;
END;
$$;


-- HNSW Index für die Embeddings-Tabelle erstellen (nach Bulk-Import)
CREATE OR REPLACE FUNCTION public.create_vector_index(
    p_m      INT DEFAULT 16,
    p_ef     INT DEFAULT 64
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_embed_hnsw
    ON public.embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = p_m, ef_construction = p_ef);
END;
$$;


-- Tenant-Statistiken (Flat-Table-Design)
CREATE OR REPLACE FUNCTION public.get_tenant_stats(p_slug TEXT)
RETURNS TABLE (
    tenant_name   TEXT,
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
    v_tenant_id UUID;
BEGIN
    SELECT t.id INTO v_tenant_id FROM public.tenants t WHERE t.slug = p_slug;
    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Tenant % not found', p_slug;
    END IF;

    RETURN QUERY
    SELECT
        p_slug::text,
        (SELECT COUNT(*) FROM public.sources WHERE tenant_id = v_tenant_id)::bigint,
        (SELECT COUNT(*) FROM public.documents WHERE tenant_id = v_tenant_id)::bigint,
        (SELECT COUNT(*) FROM public.chunks WHERE tenant_id = v_tenant_id)::bigint,
        (SELECT COUNT(*) FROM public.embeddings WHERE tenant_id = v_tenant_id)::bigint,
        (SELECT COUNT(*) FROM public.conversations WHERE tenant_id = v_tenant_id)::bigint;
END;
$$;
