-- Migration 002: Zentrales Public-Schema (Tenant-Verwaltung)
-- Ausführen als app_user oder postgres

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
    schema_name   TEXT NOT NULL UNIQUE
                    GENERATED ALWAYS AS ('tenant_' || slug) STORED,
    s3_prefix     TEXT NOT NULL UNIQUE
                    GENERATED ALWAYS AS ('tenants/' || slug || '/') STORED,
    max_docs      INT NOT NULL DEFAULT 500,
    max_chunks    INT NOT NULL DEFAULT 50000,
    max_s3_bytes  BIGINT NOT NULL DEFAULT 5368709120,  -- 5 GB
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS public.tenant_usage (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    period_start  DATE NOT NULL,
    period_end    DATE NOT NULL,
    doc_count     INT DEFAULT 0,
    chunk_count   INT DEFAULT 0,
    embed_tokens  BIGINT DEFAULT 0,
    llm_tokens    BIGINT DEFAULT 0,
    s3_bytes      BIGINT DEFAULT 0,
    query_count   INT DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, period_start)
);

CREATE INDEX IF NOT EXISTS idx_tenants_slug   ON public.tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON public.tenants(status);
CREATE INDEX IF NOT EXISTS idx_tenants_plan   ON public.tenants(plan);
CREATE INDEX IF NOT EXISTS idx_usage_tenant   ON public.tenant_usage(tenant_id, period_start DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_tenants_updated_at
    BEFORE UPDATE ON public.tenants
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_usage_updated_at
    BEFORE UPDATE ON public.tenant_usage
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
