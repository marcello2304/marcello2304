-- Migration 006: Demo-Politik Tenant fuer Kunden-Demo erstellen
-- Ausfuehren auf Server 1: docker exec -i <postgres-container> psql -U postgres -d eppcom_rag < 006_demo_politik_tenant.sql

BEGIN;

-- 1. Tenant anlegen
INSERT INTO public.tenants (id, slug, name, email, plan, status)
VALUES (
    'b0000000-0000-0000-0000-000000000002',
    'demo-politik',
    'Demo Politik-Organisation',
    'demo@eppcom.de',
    'enterprise',
    'active'
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    status = 'active',
    updated_at = NOW();

-- 2. Verify
SELECT id, slug, name, plan, status, schema_name, s3_prefix
FROM public.tenants
WHERE slug = 'demo-politik';

COMMIT;
