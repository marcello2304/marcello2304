-- EPPCOM: Test-Daten für RAG E2E-Test einfügen
-- Ausführen auf: appdb als appuser
-- Hinweis: Embedding muss separat über Server-Script eingefügt werden (braucht Ollama)

-- Test-Tenant sicherstellen
INSERT INTO tenants (id, slug, name, email, plan, is_active)
VALUES (
  'a0000000-0000-0000-0000-000000000001',
  'test-kunde',
  'Test-Kunde',
  'test@eppcom.de',
  'starter',
  true
)
ON CONFLICT (id) DO UPDATE SET
  is_active = true,
  updated_at = NOW();

-- Test-Source
INSERT INTO sources (id, tenant_id, name, source_type, status)
VALUES (
  'b0000000-0000-0000-0000-000000000001',
  'a0000000-0000-0000-0000-000000000001',
  'EPPCOM Testdokument',
  'manual',
  'completed'
)
ON CONFLICT (id) DO NOTHING;

-- Test-Document
INSERT INTO documents (id, source_id, tenant_id, content)
VALUES (
  'c0000000-0000-0000-0000-000000000001',
  'b0000000-0000-0000-0000-000000000001',
  'a0000000-0000-0000-0000-000000000001',
  'EPPCOM ist ein Unternehmen für digitale Lösungen. Wir bieten KI-gestützte Chatbots und RAG-Systeme an.'
)
ON CONFLICT (id) DO NOTHING;

-- Test-Chunks
INSERT INTO chunks (id, document_id, tenant_id, content, chunk_index, token_count)
VALUES
  (
    'd0000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'EPPCOM GmbH bietet professionelle Dienstleistungen in den Bereichen KI, Automatisierung und digitale Transformation an. Unser Kernprodukt ist ein modulares RAG-System (Retrieval Augmented Generation) für Unternehmenskunden.',
    0,
    40
  ),
  (
    'd0000000-0000-0000-0000-000000000002',
    'c0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'Unsere Öffnungszeiten sind Montag bis Freitag von 8:00 bis 17:00 Uhr. Samstags sind wir von 9:00 bis 13:00 Uhr erreichbar. Sonntags bleibt unser Büro geschlossen.',
    1,
    35
  ),
  (
    'd0000000-0000-0000-0000-000000000003',
    'c0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'EPPCOM wurde 2020 gegründet und hat seinen Sitz in Deutschland. Wir bedienen Kunden in Deutschland, Österreich und der Schweiz. Kontakt: info@eppcom.de oder telefonisch unter +49 (0) 123 456789.',
    2,
    38
  )
ON CONFLICT (id) DO NOTHING;

-- Status prüfen
SELECT 'Quellen' AS tabelle, COUNT(*) FROM sources WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'
UNION ALL
SELECT 'Dokumente', COUNT(*) FROM documents WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'
UNION ALL
SELECT 'Chunks', COUNT(*) FROM chunks WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'
UNION ALL
SELECT 'Embeddings', COUNT(*) FROM embeddings WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001';
