-- Migration 005: Datenbankrollen und Berechtigungen
-- Ausführen als postgres superuser

-- Haupt-App-User (n8n, Typebot)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_app') THEN
        CREATE ROLE rag_app WITH LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
    END IF;
END$$;

-- Read-Only User (für Monitoring, Reporting)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_readonly') THEN
        CREATE ROLE rag_readonly WITH LOGIN PASSWORD 'CHANGE_ME_READONLY_PASSWORD';
    END IF;
END$$;

-- Admin User (für Migrations, Schema-Erstellung)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_admin') THEN
        CREATE ROLE rag_admin WITH LOGIN PASSWORD 'CHANGE_ME_ADMIN_PASSWORD' CREATEROLE;
    END IF;
END$$;

-- Berechtigungen auf public schema
GRANT USAGE ON SCHEMA public TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rag_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rag_app;

GRANT USAGE ON SCHEMA public TO rag_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rag_readonly;

-- Default Privileges (für zukünftige Tabellen)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO rag_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO rag_app;

-- Funktion: Berechtigungen auf neues Tenant-Schema vergeben
CREATE OR REPLACE FUNCTION public.grant_tenant_permissions(p_schema TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO rag_app', p_schema);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO rag_app', p_schema);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO rag_readonly', p_schema);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_app', p_schema);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO rag_readonly', p_schema);
END;
$$;
