-- Migration 006: Users-Tabelle mit Passwort-Auth
-- Ausführen: docker exec -i postgres-rag psql -U postgres -d app_db < sql/006_users.sql

SET search_path TO public;

-- ── users ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user'
                    CHECK (role IN ('superadmin', 'admin', 'user')),
    tenant_id     UUID REFERENCES public.tenants(id) ON DELETE SET NULL,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email     ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant    ON public.users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_active    ON public.users(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_users_role      ON public.users(role);

-- Updated-At Trigger
DROP TRIGGER IF EXISTS trg_users_updated ON public.users;
CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── user_id Spalte zu sources hinzufügen (für User-scoped Inhalte) ────────
DO $$
BEGIN
    -- sources in public schema (003 migration)
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'sources'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'sources' AND column_name = 'user_id'
        ) THEN
            ALTER TABLE public.sources ADD COLUMN user_id UUID REFERENCES public.users(id) ON DELETE SET NULL;
            CREATE INDEX IF NOT EXISTS idx_sources_user ON public.sources(user_id);
        END IF;
    END IF;
END$$;

-- ── media_files Tabelle (Tracking von S3 Medien-Uploads) ──────────────────
CREATE TABLE IF NOT EXISTS public.media_files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id       UUID REFERENCES public.users(id) ON DELETE SET NULL,
    file_name     TEXT NOT NULL,
    original_name TEXT NOT NULL,
    s3_key        TEXT NOT NULL UNIQUE,
    s3_bucket     TEXT NOT NULL,
    content_type  TEXT NOT NULL DEFAULT 'application/octet-stream',
    file_size     BIGINT NOT NULL DEFAULT 0,
    folder        TEXT NOT NULL DEFAULT 'media',
    description   TEXT DEFAULT '',
    is_public     BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_media_tenant    ON public.media_files(tenant_id);
CREATE INDEX IF NOT EXISTS idx_media_user      ON public.media_files(user_id);
CREATE INDEX IF NOT EXISTS idx_media_folder    ON public.media_files(folder);
CREATE INDEX IF NOT EXISTS idx_media_type      ON public.media_files(content_type);

DROP TRIGGER IF EXISTS trg_media_updated ON public.media_files;
CREATE TRIGGER trg_media_updated
    BEFORE UPDATE ON public.media_files
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

SELECT 'Migration 006 abgeschlossen: users, media_files, sources.user_id' AS status;
