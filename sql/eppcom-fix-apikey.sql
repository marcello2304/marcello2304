-- EPPCOM: Tenant + API-Keys anlegen
-- Ausführen: docker exec -i postgres-rag psql -U postgres -d app_db < sql/eppcom-fix-apikey.sql
-- Voraussetzung: 001, 002, 003 müssen bereits gelaufen sein
--
-- WICHTIG: API-Key muss als ENV übergeben werden!
-- Beispiel:
--   export RAG_API_KEY=$(openssl rand -hex 32)
--   sed "s/PLACEHOLDER_API_KEY/$RAG_API_KEY/g" sql/eppcom-fix-apikey.sql | docker exec -i postgres-rag psql -U postgres -d app_db

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

-- ── Alte unsichere Keys deaktivieren ──────────────────────────────────────────
UPDATE public.api_keys
SET is_active = false
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'::uuid
  AND name IN ('Test API Key (Original)', 'Test API Key', 'Test Key Original');

-- ── Ergebnis anzeigen ─────────────────────────────────────────────────────────
SELECT 'Tenant:' AS typ, id::text, slug, name, is_active::text AS aktiv FROM public.tenants
WHERE id = 'a0000000-0000-0000-0000-000000000001'::uuid

UNION ALL

SELECT 'API-Key:', id::text, name, LEFT(key_hash, 20) || '...', is_active::text
FROM public.api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'::uuid
ORDER BY typ DESC;
