-- EPPCOM: API-Key für Test-Tenant reparieren
-- Ausführen auf: appdb als appuser
-- docker exec -i <postgres-container> psql -U appuser -d appdb < sql/eppcom-fix-apikey.sql

-- Vorhandene Keys anzeigen (Diagnose)
SELECT id, tenant_id, name, key_hash, is_active, created_at
FROM api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001';

-- Alten Key mit unbekanntem Plaintext löschen
-- (behält Keys, die wir kennen)
DELETE FROM api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'
  AND key_hash NOT IN (
    encode(sha256('test-key-123'::bytea), 'hex'),
    encode(sha256('***API_KEY_REMOVED***'::bytea), 'hex')
  );

-- test-key-123 sicherstellen (war bestätigt funktionierend)
INSERT INTO api_keys (id, tenant_id, key_hash, name, permissions, is_active)
VALUES (
  gen_random_uuid(),
  'a0000000-0000-0000-0000-000000000001',
  encode(sha256('test-key-123'::bytea), 'hex'),
  'Test API Key (Original)',
  '["read", "write"]'::jsonb,
  true
)
ON CONFLICT DO NOTHING;

-- ***API_KEY_REMOVED*** eintragen
INSERT INTO api_keys (id, tenant_id, key_hash, name, permissions, is_active)
VALUES (
  gen_random_uuid(),
  'a0000000-0000-0000-0000-000000000001',
  encode(sha256('***API_KEY_REMOVED***'::bytea), 'hex'),
  'Test API Key 2025',
  '["read", "write"]'::jsonb,
  true
)
ON CONFLICT DO NOTHING;

-- Ergebnis verifizieren
SELECT id, tenant_id, name,
       LEFT(key_hash, 16) || '...' AS key_hash_preview,
       is_active, created_at
FROM api_keys
WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'
ORDER BY created_at;
