-- Demo-Testdaten für RAG-Test
-- Platzhalter __SCHEMA__ wird durch seed-test-data.sh ersetzt
-- Inhalt: Deutsche Produkt-FAQ für eine fiktive SaaS-Software "ProManager"

-- ── Source: FAQ Dokument ────────────────────────────────────────────────
INSERT INTO __SCHEMA__.sources (id, name, source_type, file_name, file_type, status, created_by, tags, metadata)
VALUES (
    '11111111-0000-0000-0000-000000000001',
    'ProManager FAQ – Häufige Fragen',
    'file',
    'promanager_faq.md',
    'md',
    'indexed',
    'seed-script',
    ARRAY['faq', 'produkt', 'support'],
    '{"version": "2.1", "language": "de"}'
) ON CONFLICT (id) DO NOTHING;

-- ── Source: Preisliste ──────────────────────────────────────────────────
INSERT INTO __SCHEMA__.sources (id, name, source_type, file_name, file_type, status, created_by, tags, metadata)
VALUES (
    '11111111-0000-0000-0000-000000000002',
    'ProManager Preisliste 2024',
    'file',
    'preisliste_2024.md',
    'md',
    'indexed',
    'seed-script',
    ARRAY['preise', 'lizenz', 'pakete'],
    '{"version": "2024-Q4", "language": "de"}'
) ON CONFLICT (id) DO NOTHING;

-- ── Source: Installationsanleitung ─────────────────────────────────────
INSERT INTO __SCHEMA__.sources (id, name, source_type, file_name, file_type, status, created_by, tags, metadata)
VALUES (
    '11111111-0000-0000-0000-000000000003',
    'ProManager Installationsanleitung',
    'file',
    'installation.md',
    'md',
    'indexed',
    'seed-script',
    ARRAY['installation', 'setup', 'technisch'],
    '{"version": "3.0", "language": "de"}'
) ON CONFLICT (id) DO NOTHING;

-- ── Document: FAQ ───────────────────────────────────────────────────────
INSERT INTO __SCHEMA__.documents (id, source_id, title, doc_type, language, is_active, word_count)
VALUES (
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    'ProManager FAQ – Häufige Fragen',
    'faq',
    'de',
    true,
    850
) ON CONFLICT (id) DO NOTHING;

-- ── Document: Preisliste ────────────────────────────────────────────────
INSERT INTO __SCHEMA__.documents (id, source_id, title, doc_type, language, is_active, word_count)
VALUES (
    '22222222-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000002',
    'Preisliste und Lizenzmodelle 2024',
    'product',
    'de',
    true,
    420
) ON CONFLICT (id) DO NOTHING;

-- ── Document: Installation ──────────────────────────────────────────────
INSERT INTO __SCHEMA__.documents (id, source_id, title, doc_type, language, is_active, word_count)
VALUES (
    '22222222-0000-0000-0000-000000000003',
    '11111111-0000-0000-0000-000000000003',
    'Installationsanleitung ProManager',
    'manual',
    'de',
    true,
    620
) ON CONFLICT (id) DO NOTHING;

-- ════════════════════════════════════════════════════════════════════════
-- CHUNKS — FAQ Dokument
-- ════════════════════════════════════════════════════════════════════════

INSERT INTO __SCHEMA__.chunks (id, document_id, source_id, chunk_index, content, section, page_number)
VALUES
(
    '33333333-0000-0000-0000-000000000001',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    0,
    'ProManager ist eine cloudbasierte Projektmanagement-Software für kleine und mittelständische Unternehmen. Mit ProManager können Teams Aufgaben verwalten, Deadlines tracken und die Zusammenarbeit verbessern. Die Software ist browserbasiert und funktioniert auf allen Geräten ohne Installation.',
    'Allgemein',
    1
),
(
    '33333333-0000-0000-0000-000000000002',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    1,
    'Wie kann ich mein Konto kündigen? Sie können Ihr ProManager-Konto jederzeit in den Kontoeinstellungen unter "Abonnement" kündigen. Die Kündigung ist zum Ende des aktuellen Abrechnungszeitraums wirksam. Sie erhalten keine Rückerstattung für bereits bezahlte Zeiträume. Ihre Daten werden 30 Tage nach Kündigung gelöscht.',
    'Konto & Kündigung',
    2
),
(
    '33333333-0000-0000-0000-000000000003',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    2,
    'Wie viele Nutzer kann ich zu meinem Projekt einladen? Das hängt von Ihrem Paket ab: Im Starter-Paket sind 5 Nutzer inklusive. Im Pro-Paket können Sie bis zu 25 Nutzer hinzufügen. Das Enterprise-Paket bietet unbegrenzte Nutzer. Weitere Nutzer können beim Pro-Paket für 8 Euro pro Monat gebucht werden.',
    'Nutzer & Berechtigungen',
    2
),
(
    '33333333-0000-0000-0000-000000000004',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    3,
    'Welche Dateiformate kann ich in ProManager hochladen? ProManager unterstützt folgende Dateitypen: PDF, Word (DOCX), Excel (XLSX), PowerPoint (PPTX), Bilder (PNG, JPG, GIF), ZIP-Archive sowie Textdateien (TXT, MD, CSV). Die maximale Dateigröße pro Upload beträgt 25 MB im Starter-Paket und 100 MB im Pro- und Enterprise-Paket.',
    'Dateien & Uploads',
    3
),
(
    '33333333-0000-0000-0000-000000000005',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    4,
    'Gibt es eine mobile App für ProManager? Ja, ProManager ist als native App für iOS (ab Version 15) und Android (ab Version 10) verfügbar. Die Apps sind im App Store und Google Play Store kostenlos erhältlich. Alle Features der Web-Version sind auch in der mobilen App verfügbar, inklusive Offline-Modus für gespeicherte Projekte.',
    'Mobile & Apps',
    3
),
(
    '33333333-0000-0000-0000-000000000006',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    5,
    'Wie sicher sind meine Daten bei ProManager? ProManager verwendet AES-256-Verschlüsselung für alle gespeicherten Daten und TLS 1.3 für die Datenübertragung. Unsere Server stehen ausschließlich in deutschen Rechenzentren (DSGVO-konform). Wir führen tägliche Backups durch und haben eine Verfügbarkeitsgarantie von 99.9% SLA. Datenschutz-Zertifizierung nach ISO 27001.',
    'Sicherheit & Datenschutz',
    4
),
(
    '33333333-0000-0000-0000-000000000007',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    6,
    'Kann ich ProManager mit anderen Tools integrieren? ProManager bietet native Integrationen mit Slack, Microsoft Teams, Google Workspace, Jira, GitHub und Zapier. Über unsere REST-API können Sie eigene Integrationen entwickeln. Die API-Dokumentation finden Sie unter api.promanager.de. Webhooks sind ab dem Pro-Paket verfügbar.',
    'Integrationen & API',
    4
),
(
    '33333333-0000-0000-0000-000000000008',
    '22222222-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000001',
    7,
    'Wie kann ich den ProManager Support erreichen? Unser Support-Team ist wie folgt erreichbar: E-Mail: support@promanager.de (Antwort innerhalb 24h), Live-Chat: montags bis freitags 9-18 Uhr, Telefon-Support: nur für Enterprise-Kunden. Im Help-Center unter help.promanager.de finden Sie über 200 Artikel und Video-Tutorials.',
    'Support',
    5
)
ON CONFLICT (id) DO NOTHING;

-- ════════════════════════════════════════════════════════════════════════
-- CHUNKS — Preisliste
-- ════════════════════════════════════════════════════════════════════════

INSERT INTO __SCHEMA__.chunks (id, document_id, source_id, chunk_index, content, section, page_number)
VALUES
(
    '33333333-0000-0000-0000-000000000009',
    '22222222-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000002',
    0,
    'Starter-Paket: 19 Euro pro Monat (bei jährlicher Zahlung: 15 Euro/Monat). Enthält: 5 Nutzer, 10 GB Speicher, 10 aktive Projekte, E-Mail-Support, Basis-Integrationen (Slack, Teams), Mobile App. Keine Kreditkarte für 30-Tage-Testversion erforderlich.',
    'Starter',
    1
),
(
    '33333333-0000-0000-0000-000000000010',
    '22222222-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000002',
    1,
    'Pro-Paket: 49 Euro pro Monat (bei jährlicher Zahlung: 39 Euro/Monat). Enthält: 25 Nutzer, 100 GB Speicher, unbegrenzte Projekte, Priority-Support (24h), alle Integrationen, Webhooks, erweiterte Berichte, Zeiterfassung, Gantt-Charts, 2FA-Authentifizierung.',
    'Pro',
    1
),
(
    '33333333-0000-0000-0000-000000000011',
    '22222222-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000002',
    2,
    'Enterprise-Paket: Ab 149 Euro pro Monat (individuell verhandelbar bei >100 Nutzer). Enthält: Unbegrenzte Nutzer, 1 TB Speicher, eigene Domain (white-label), SSO/SAML, dedizierter Account-Manager, Telefon-Support, SLA 99.9%, On-Premise-Option, DSGVO-Auftragsverarbeitungsvertrag (AVV) inklusive.',
    'Enterprise',
    2
),
(
    '33333333-0000-0000-0000-000000000012',
    '22222222-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000002',
    3,
    'Für gemeinnützige Organisationen, Schulen und Bildungseinrichtungen gewähren wir 50% Rabatt auf alle Pakete. NGO-Rabatt: Nachweis der Gemeinnützigkeit per E-Mail an nonprofit@promanager.de. Studenten erhalten das Pro-Paket kostenlos für 12 Monate bei Nachweis einer gültigen Immatrikulationsbescheinigung.',
    'Rabatte & Sonderkonditionen',
    2
)
ON CONFLICT (id) DO NOTHING;

-- ════════════════════════════════════════════════════════════════════════
-- CHUNKS — Installationsanleitung
-- ════════════════════════════════════════════════════════════════════════

INSERT INTO __SCHEMA__.chunks (id, document_id, source_id, chunk_index, content, section, page_number)
VALUES
(
    '33333333-0000-0000-0000-000000000013',
    '22222222-0000-0000-0000-000000000003',
    '11111111-0000-0000-0000-000000000003',
    0,
    'ProManager benötigt keine lokale Installation für die Web-Version. Öffnen Sie einfach app.promanager.de in einem modernen Browser (Chrome ab v90, Firefox ab v88, Safari ab v14, Edge ab v90). Für optimale Performance empfehlen wir mindestens 4 GB RAM und eine stabile Internetverbindung ab 5 Mbit/s.',
    'Systemanforderungen',
    1
),
(
    '33333333-0000-0000-0000-000000000014',
    '22222222-0000-0000-0000-000000000003',
    '11111111-0000-0000-0000-000000000003',
    1,
    'Für die On-Premise-Installation (nur Enterprise): Voraussetzungen sind Docker 20.10+, Docker Compose 2.0+, min. 4 CPU-Kerne, 8 GB RAM, 50 GB SSD-Speicher, Ubuntu 22.04 LTS oder RHEL 8+. Die Installation erfolgt mit: curl -fsSL install.promanager.de | bash. Das Skript richtet automatisch alle Abhängigkeiten ein.',
    'On-Premise Installation',
    2
),
(
    '33333333-0000-0000-0000-000000000015',
    '22222222-0000-0000-0000-000000000003',
    '11111111-0000-0000-0000-000000000003',
    2,
    'SSO-Einrichtung mit Active Directory / SAML 2.0: Navigieren Sie zu Einstellungen → Sicherheit → SSO. Tragen Sie die Metadaten-URL Ihres Identity Providers ein. ProManager unterstützt Azure AD, Okta, Google Workspace und alle SAML 2.0 kompatiblen Systeme. Nach der Einrichtung können sich alle Mitarbeiter mit ihren Unternehmens-Credentials anmelden.',
    'SSO & Authentifizierung',
    3
),
(
    '33333333-0000-0000-0000-000000000016',
    '22222222-0000-0000-0000-000000000003',
    '11111111-0000-0000-0000-000000000003',
    3,
    'Datenmigration aus anderen Tools: ProManager bietet Import-Funktionen für Jira (JSON-Export), Trello (Board-Export), Asana (CSV), Microsoft Project (MPP/XML) und Basecamp (Backup-Datei). Gehen Sie zu Einstellungen → Daten importieren → Format auswählen. Bei großen Datensätzen (>10.000 Aufgaben) wenden Sie sich an migration@promanager.de für assistierten Import.',
    'Datenmigration',
    4
)
ON CONFLICT (id) DO NOTHING;

-- Status aller Sources auf 'indexed' setzen
UPDATE __SCHEMA__.sources SET status = 'indexed', updated_at = NOW()
WHERE id IN (
    '11111111-0000-0000-0000-000000000001',
    '11111111-0000-0000-0000-000000000002',
    '11111111-0000-0000-0000-000000000003'
);
