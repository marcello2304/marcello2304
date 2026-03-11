-- EPPCOM: Tenant + API-Keys anlegen
-- Ausführen: docker exec -i postgres-rag psql -U postgres -d app_db < sql/eppcom-fix-apikey.sql
-- Voraussetzung: 001, 002, 003 müssen bereits gelaufen sein

-- ── EPPCOM Tenant mit fixer UUID anlegen (idempotent) ────────────────────────
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
    SET is_active = true,
        name = EXCLUDED.name;

-- ── Alte Keys bereinigen (nur die, die wir nicht kennen) ─────────────────────
DELETE FROM public.api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'::uuid
  AND key_hash NOT IN (
    encode(sha256('test-key-123'::bytea), 'hex'),
    encode(sha256('***API_KEY_REMOVED***'::bytea), 'hex')
  );

-- ── API-Key 1: test-key-123 ───────────────────────────────────────────────────
INSERT INTO public.api_keys (id, tenant_id, key_hash, name, permissions, is_active)
VALUES (
    'b0000000-0000-0000-0000-000000000001'::uuid,
    'a0000000-0000-0000-0000-000000000001'::uuid,
    encode(sha256('test-key-123'::bytea), 'hex'),
    'Test API Key (Original)',
    '["read", "write"]'::jsonb,
    true
)
ON CONFLICT (id) DO UPDATE SET is_active = true;

-- ── API-Key 2: ***API_KEY_REMOVED*** ──────────────────────────────────────────
INSERT INTO public.api_keys (id, tenant_id, key_hash, name, permissions, is_active)
VALUES (
    'b0000000-0000-0000-0000-000000000002'::uuid,
    'a0000000-0000-0000-0000-000000000001'::uuid,
    encode(sha256('***API_KEY_REMOVED***'::bytea), 'hex'),
    'EPPCOM Produktiv Key 2025',
    '["read", "write"]'::jsonb,
    true
)
ON CONFLICT (id) DO UPDATE SET is_active = true;

-- ── Ergebnis anzeigen ─────────────────────────────────────────────────────────
SELECT 'Tenant:' AS typ, id::text, slug, name, is_active::text AS aktiv FROM public.tenants
WHERE id = 'a0000000-0000-0000-0000-000000000001'::uuid

UNION ALL

SELECT 'API-Key:', id::text, name, LEFT(key_hash, 20) || '...', is_active::text
FROM public.api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'::uuid
ORDER BY typ DESC;
