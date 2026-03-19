-- Migration 008: Audit Log + Platform Settings
-- Für Admin-UI: Aktivitäts-Tracking und Plattform-Einstellungen

SET search_path TO public;

-- ── audit_log ────────────────────────────────────────────────────────────────
-- Zentrales Audit Log für alle kritischen Admin-Aktionen
CREATE TABLE IF NOT EXISTS public.audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES public.users(id) ON DELETE SET NULL,
    user_email      TEXT,
    action          TEXT NOT NULL,
    -- 'login', 'logout', 'user.create', 'user.delete', 'user.deactivate',
    -- 'tenant.create', 'tenant.delete', 'api_key.create', 'api_key.revoke',
    -- 'document.delete', 'settings.update', etc.
    resource_type   TEXT,           -- 'user', 'tenant', 'document', 'api_key', 'settings'
    resource_id     TEXT,
    details         JSONB DEFAULT '{}',
    ip_address      TEXT,
    user_agent      TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON public.audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON public.audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON public.audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON public.audit_log(resource_type, resource_id);

-- ── platform_settings ────────────────────────────────────────────────────────
-- Zentrale Key-Value-Speicher für Plattform-Konfiguration
CREATE TABLE IF NOT EXISTS public.platform_settings (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    description     TEXT DEFAULT '',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by      UUID REFERENCES public.users(id) ON DELETE SET NULL
);

-- Default-Einstellungen (falls noch nicht existierend)
INSERT INTO public.platform_settings (key, value, description) VALUES
('platform_name', '"EPPCOM"', 'Name der Plattform'),
('support_email', '"support@eppcom.de"', 'Support-E-Mail-Adresse'),
('max_upload_size_mb', '500', 'Maximale Upload-Größe in MB'),
('session_timeout_minutes', '120', 'Session-Timeout in Minuten'),
('embedding_model', '"nomic-embed-text"', 'Embedding-Modell'),
('embedding_dimensions', '768', 'Embedding-Dimensionen'),
('chunk_size', '1024', 'Chunk-Größe in Token'),
('chunk_overlap', '128', 'Chunk-Overlap in Token')
ON CONFLICT (key) DO NOTHING;

-- ── api_keys Tabelle (falls nicht existierend) ───────────────────────────────
-- Für API Key Management in Admin-UI
CREATE TABLE IF NOT EXISTS public.api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES public.tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    key_hash        TEXT NOT NULL UNIQUE,
    key_preview     TEXT NOT NULL,  -- Letzten 8 Zeichen: sk-...xxxxx
    is_active       BOOLEAN NOT NULL DEFAULT true,
    expires_at      TIMESTAMPTZ,
    created_by      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON public.api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON public.api_keys(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_api_keys_created_by ON public.api_keys(created_by);

SELECT 'Migration 008 abgeschlossen: audit_log, platform_settings, api_keys' AS status;
