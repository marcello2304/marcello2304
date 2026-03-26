# EPPCOM FAQ - Erweitert für RAG-Optimierung

## Warum Self-Hosting statt Cloud-Lösungen?

**Kurze Antwort**: Bei EPPCOM bleiben Ihre Daten auf deutschen Servern unter Ihrer Kontrolle - das ist der Unterschied zwischen DSGVO-Compliance und Datenschutz-Risiko.

**Detail**: Cloud-Anbieter wie OpenAI oder US-Dienste bedeuten Datenexport ins Ausland. Self-Hosting auf Hetzner Deutschland heißt: Ihre Kundendaten, Geschäftsdokumente und sensiblen Infos verlassen nie die EU. Gerade für Branchen wie Gesundheit, Finanzen oder HR ist das nicht optional - es ist rechtlich geboten.

**Konkret bei EPPCOM**: Wir installieren alle Systeme (n8n, Typebot, PostgreSQL, Ollama-LLMs) auf Ihren oder unseren deutschen Hetzner-Servern. Sie haben Root-Zugriff, volle Audit-Logs und können jederzeit Datenschutz-Prüfungen durchführen.

## Was unterscheidet EPPCOM von Standard-Chatbot-Anbietern?

**Kurze Antwort**: Wir bauen keine SaaS-Chatbots - wir bauen Ihre eigene KI-Infrastruktur.

**Detail**: Andere Anbieter (z.B. Voiceflow, Botpress-Cloud) sind Plattformen mit festen Preismodellen und Datensilos. EPPCOM liefert Ihnen die komplette Technologie Stack ownership: eigene Server, eigene LLMs, eigene Datenbanken. Das bedeutet:
- Keine monatlichen Pro-User-Kosten
- Keine Vendor-Lock-in-Effekte
- Unbegrenzte Skalierung ohne Preissteigerungen
- Integration in JEDES bestehende System (ERP, CRM, HR-Software)

**Konkret**: Ein Kunde mit 500 Mitarbeitern zahlt bei SaaS-Anbietern oft 2000-5000 Euro pro Monat. Mit EPPCOM: Einmalige Implementierung plus ca. 200 Euro pro Monat Server-Kosten. Nach 6 Monaten ROI erreicht.

## Wie funktioniert die RAG-Technologie bei EPPCOM praktisch?

**Kurze Antwort**: Ihre Dokumente werden in eine Datenbank umgewandelt, die KI findet blitzschnell die richtige Info und formuliert die Antwort in eigenen Worten.

**Detail-Workflow**:
1. **Ingest**: Ihre PDFs, Word-Docs, Confluence-Seiten werden hochgeladen
2. **Chunking**: Texte werden in 300-500 Wort-Abschnitte zerlegt
3. **Embedding**: Jeder Chunk wird in einen mathematischen Vektor umgewandelt (via qwen3-embedding)
4. **Speicherung**: Vektoren landen in PostgreSQL mit pgvector-Extension
5. **Retrieval**: Bei einer Frage sucht das System die 3-5 relevantesten Chunks (Cosine-Similarity)
6. **Generation**: Das LLM (qwen2.5:7b) bekommt diese Chunks als Kontext und formuliert die Antwort

**Vorteil**: Antworten basieren auf IHREN exakten Dokumenten, nicht auf generischem LLM-Training. Updates? Einfach neue Dokumente hochladen - keine Modell-Neutrainings nötig.

## Kann die KI auch telefonieren / Sprachanrufe entgegennehmen?

**Kurze Antwort**: Ja - mit unserem Voicebot-Stack über LiveKit und deutsche Telefonie-Provider.

**Detail-Architektur**:
- **Eingang**: SIP-Trunk von deutschen Providern (z.B. sipgate, easybell) nach LiveKit
- **STT**: Whisper (OpenAI oder lokal gehostet) wandelt Sprache in Text
- **LLM**: qwen2.5:7b verarbeitet mit RAG-Kontext
- **TTS**: Cartesia oder ElevenLabs für natürliche Sprachausgabe
- **LiveKit**: Orchestriert den Echtzeit-Audio-Stream

**Use-Cases**:
- Terminvereinbarungen automatisieren
- First-Level-Support am Telefon
- Bestellannahme außerhalb der Geschäftszeiten
- Info-Hotlines (z.B. Öffnungszeiten, Preise, Verfügbarkeit)

**DSGVO**: Gespräche können aufgezeichnet werden (mit Ankündigung) oder rein transient verarbeitet werden - je nach Compliance-Anforderung.

## Wie schnell antwortet der Voicebot?

**Kurze Antwort**: Unter 3 Sekunden von Ihrer Frage bis zur gesprochenen Antwort.

**Technische Breakdown**:
1. Sprache nach Text (Whisper): ca. 300-500ms
2. Datenbank-Suche (RAG): ca. 50-100ms
3. KI denkt nach (LLM): ca. 800-1200ms
4. Text nach Sprache (TTS): ca. 200-400ms

**Gesamt**: 1,4-2,2 Sekunden - schneller als die meisten menschlichen Call-Center-Agenten.

**Optimierung**: Durch Streaming (erste Wörter schon während die KI noch denkt) fühlt sich die Antwort noch flüssiger an.

## Welche Datenquellen kann EPPCOM anbinden?

EPPCOM kann praktisch jede Datenquelle anbinden, die über eine API oder Datei-Export verfügbar ist:
- **Dokumente**: PDF, Word, Excel, PowerPoint, Markdown
- **Datenbanken**: PostgreSQL, MySQL, MongoDB, Supabase
- **CRM/ERP**: Salesforce, HubSpot, SAP, Pipedrive
- **Kommunikation**: E-Mail (IMAP/SMTP), Slack, Microsoft Teams
- **Cloud-Speicher**: Google Drive, OneDrive, Dropbox, Nextcloud
- **Ticket-Systeme**: Jira, Zendesk, Freshdesk, Linear
- **Eigene APIs**: REST, GraphQL, Webhooks

Die Integration erfolgt über n8n-Workflows, die automatisch Daten synchronisieren und in der RAG-Datenbank aktuell halten.

## Was kostet eine EPPCOM-Lösung?

**Preismodell**: Einmalige Implementierung + niedrige monatliche Betriebskosten.

**Typische Projekte**:
- **Einfacher Chatbot** (FAQ, Website-Integration): 3.000-5.000 Euro Setup + 100-150 Euro/Monat
- **RAG-Chatbot** (eigene Dokumente, Multi-User): 5.000-8.000 Euro Setup + 150-250 Euro/Monat
- **Voicebot** (Telefonie, LiveKit, TTS): 8.000-15.000 Euro Setup + 250-400 Euro/Monat
- **Enterprise** (Multi-Tenant, Custom Integrationen): Ab 15.000 Euro Setup + individuell

**Vergleich**: SaaS-Chatbot-Plattformen kosten oft 500-5.000 Euro/Monat OHNE eigene Infrastruktur. EPPCOM amortisiert sich typischerweise nach 4-8 Monaten.

## Wie sicher sind die Daten bei EPPCOM?

**Sicherheits-Stack**:
- **Verschlüsselung**: TLS 1.3 für alle Verbindungen, AES-256 für ruhende Daten
- **Zugriffskontrolle**: Multi-Tenant-Isolation mit Row-Level-Security in PostgreSQL
- **Authentifizierung**: JWT-basiert mit konfigurierbarer Session-Dauer
- **Audit-Logging**: Alle Zugriffe werden protokolliert
- **Backup**: Tägliche automatische Backups mit 30-Tage-Retention
- **Standort**: Ausschließlich deutsche Hetzner-Rechenzentren (Nürnberg, Falkenstein)
- **Zertifizierungen**: ISO 27001 (Hetzner), DSGVO-konform by design
