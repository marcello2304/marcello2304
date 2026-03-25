# CLAUDE CODE PLAN: Jitsi Meet Setup & Demo-Vorbereitung

**Projekt:** EPPCOM RAG-Chatbot für ersten Politik-Kunden  
**Datum:** 2026-03-24  
**Ziel:** Professionelles Meeting-Setup + Live-Demo-Umgebung vorbereiten

---

## TEIL 1: JITSI MEET SETUP AUF SERVER 1

### Kontext
- Server 1: 94.130.170.167 (CX23, Hetzner Falkenstein)
- Coolify läuft bereits mit Traefik
- Ziel-Domain: `meet.eppcom.de`
- Zeitaufwand: 2-3 Stunden

### Schritt 1: Docker Compose File erstellen

**Pfad:** `/root/jitsi-meet/docker-compose.yml`

```yaml
version: '3.8'

services:
  web:
    image: jitsi/web:stable-9258
    restart: unless-stopped
    ports:
      - '8000:80'
      - '8443:443'
    volumes:
      - jitsi-web-config:/config
      - jitsi-web-crontabs:/var/spool/cron/crontabs
      - jitsi-web-transcripts:/usr/share/jitsi-meet/transcripts
    environment:
      - ENABLE_AUTH=0
      - ENABLE_GUESTS=1
      - ENABLE_LETSENCRYPT=0
      - ENABLE_HTTP_REDIRECT=1
      - ENABLE_TRANSCRIPTIONS=0
      - DISABLE_HTTPS=1
      - JICOFO_AUTH_USER=focus
      - TZ=Europe/Berlin
      - PUBLIC_URL=https://meet.eppcom.de
      - XMPP_DOMAIN=meet.jitsi
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_BOSH_URL_BASE=http://xmpp.meet.jitsi:5280
      - XMPP_MUC_DOMAIN=muc.meet.jitsi
      - JVB_TCP_HARVESTER_DISABLED=true
    networks:
      meet.jitsi:
        aliases:
          - meet.jitsi

  prosody:
    image: jitsi/prosody:stable-9258
    restart: unless-stopped
    expose:
      - '5222'
      - '5347'
      - '5280'
    volumes:
      - jitsi-prosody-config:/config
      - jitsi-prosody-plugins-custom:/prosody-plugins-custom
    environment:
      - AUTH_TYPE=internal
      - ENABLE_AUTH=0
      - ENABLE_GUESTS=1
      - ENABLE_LOBBY=0
      - GLOBAL_MODULES=
      - GLOBAL_CONFIG=
      - LDAP_URL=
      - XMPP_DOMAIN=meet.jitsi
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_GUEST_DOMAIN=guest.meet.jitsi
      - XMPP_MUC_DOMAIN=muc.meet.jitsi
      - XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi
      - XMPP_MODULES=
      - XMPP_MUC_MODULES=
      - XMPP_INTERNAL_MUC_MODULES=
      - XMPP_RECORDER_DOMAIN=recorder.meet.jitsi
      - JICOFO_COMPONENT_SECRET=${JICOFO_COMPONENT_SECRET}
      - JICOFO_AUTH_USER=focus
      - JICOFO_AUTH_PASSWORD=${JICOFO_AUTH_PASSWORD}
      - JVB_AUTH_USER=jvb
      - JVB_AUTH_PASSWORD=${JVB_AUTH_PASSWORD}
      - JIGASI_XMPP_USER=jigasi
      - JIGASI_XMPP_PASSWORD=${JIGASI_XMPP_PASSWORD}
      - JIBRI_XMPP_USER=jibri
      - JIBRI_XMPP_PASSWORD=${JIBRI_XMPP_PASSWORD}
      - JIBRI_RECORDER_USER=recorder
      - JIBRI_RECORDER_PASSWORD=${JIBRI_RECORDER_PASSWORD}
      - JWT_APP_ID=
      - JWT_APP_SECRET=
      - JWT_ACCEPTED_ISSUERS=
      - JWT_ACCEPTED_AUDIENCES=
      - JWT_ASAP_KEYSERVER=
      - JWT_ALLOW_EMPTY=
      - JWT_AUTH_TYPE=
      - JWT_TOKEN_AUTH_MODULE=
      - LOG_LEVEL=info
      - TZ=Europe/Berlin
    networks:
      meet.jitsi:
        aliases:
          - xmpp.meet.jitsi

  jicofo:
    image: jitsi/jicofo:stable-9258
    restart: unless-stopped
    volumes:
      - jitsi-jicofo-config:/config
    environment:
      - AUTH_TYPE=internal
      - ENABLE_AUTH=0
      - XMPP_DOMAIN=meet.jitsi
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi
      - XMPP_SERVER=xmpp.meet.jitsi
      - JICOFO_COMPONENT_SECRET=${JICOFO_COMPONENT_SECRET}
      - JICOFO_AUTH_USER=focus
      - JICOFO_AUTH_PASSWORD=${JICOFO_AUTH_PASSWORD}
      - JVB_BREWERY_MUC=jvbbrewery
      - JIGASI_BREWERY_MUC=jigasibrewery
      - JIGASI_SIP_URI=
      - JIBRI_BREWERY_MUC=jibribrewery
      - JIBRI_PENDING_TIMEOUT=90
      - TZ=Europe/Berlin
    depends_on:
      - prosody
    networks:
      meet.jitsi:

  jvb:
    image: jitsi/jvb:stable-9258
    restart: unless-stopped
    ports:
      - '10000:10000/udp'
      - '4443:4443'
    volumes:
      - jitsi-jvb-config:/config
    environment:
      - DOCKER_HOST_ADDRESS=${DOCKER_HOST_ADDRESS}
      - XMPP_AUTH_DOMAIN=auth.meet.jitsi
      - XMPP_INTERNAL_MUC_DOMAIN=internal-muc.meet.jitsi
      - XMPP_SERVER=xmpp.meet.jitsi
      - JVB_AUTH_USER=jvb
      - JVB_AUTH_PASSWORD=${JVB_AUTH_PASSWORD}
      - JVB_BREWERY_MUC=jvbbrewery
      - JVB_PORT=10000
      - JVB_TCP_HARVESTER_DISABLED=true
      - JVB_TCP_PORT=4443
      - JVB_STUN_SERVERS=stun.l.google.com:19302,stun1.l.google.com:19302,stun2.l.google.com:19302
      - JVB_ENABLE_APIS=rest
      - TZ=Europe/Berlin
    depends_on:
      - prosody
    networks:
      meet.jitsi:

volumes:
  jitsi-web-config:
  jitsi-web-crontabs:
  jitsi-web-transcripts:
  jitsi-prosody-config:
  jitsi-prosody-plugins-custom:
  jitsi-jicofo-config:
  jitsi-jvb-config:

networks:
  meet.jitsi:
```

### Schritt 2: Environment File erstellen

**Pfad:** `/root/jitsi-meet/.env`

```bash
# Secrets generieren mit:
# openssl rand -hex 16

JICOFO_COMPONENT_SECRET=<generiere_32_char_hex>
JICOFO_AUTH_PASSWORD=<generiere_32_char_hex>
JVB_AUTH_PASSWORD=<generiere_32_char_hex>
JIGASI_XMPP_PASSWORD=<generiere_32_char_hex>
JIBRI_XMPP_PASSWORD=<generiere_32_char_hex>
JIBRI_RECORDER_PASSWORD=<generiere_32_char_hex>
DOCKER_HOST_ADDRESS=94.130.170.167
```

**Automatisch generieren:**
```bash
cd /root/jitsi-meet
cat > .env << EOF
JICOFO_COMPONENT_SECRET=$(openssl rand -hex 16)
JICOFO_AUTH_PASSWORD=$(openssl rand -hex 16)
JVB_AUTH_PASSWORD=$(openssl rand -hex 16)
JIGASI_XMPP_PASSWORD=$(openssl rand -hex 16)
JIBRI_XMPP_PASSWORD=$(openssl rand -hex 16)
JIBRI_RECORDER_PASSWORD=$(openssl rand -hex 16)
DOCKER_HOST_ADDRESS=94.130.170.167
EOF
```

### Schritt 3: Traefik Labels hinzufügen

**Im docker-compose.yml unter `web` service:**

```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.jitsi.rule=Host(`meet.eppcom.de`)"
      - "traefik.http.routers.jitsi.entrypoints=websecure"
      - "traefik.http.routers.jitsi.tls.certresolver=letsencrypt"
      - "traefik.http.services.jitsi.loadbalancer.server.port=80"
```

### Schritt 4: DNS bei Hetzner konfigurieren

**Hetzner DNS Console (https://dns.hetzner.com):**
```
Zone: eppcom.de
Neuer A-Record:
  Name: meet
  Type: A
  Value: 94.130.170.167
  TTL: 3600
```

### Schritt 5: Deployment

```bash
cd /root/jitsi-meet
docker-compose up -d

# Logs prüfen
docker-compose logs -f

# Status prüfen
docker-compose ps
```

### Schritt 6: Test

```bash
# Im Browser öffnen:
https://meet.eppcom.de

# Erwartung: Jitsi-Startseite erscheint
# Test-Meeting erstellen und beitreten
```

### Schritt 7: Branding (Optional)

```bash
# Ins web-Container
docker exec -it jitsi-meet-web-1 bash

# Logo anpassen
cd /usr/share/jitsi-meet/images
# Eigenes Logo als watermark.png hochladen (272x272 px)

# Farben anpassen
cd /usr/share/jitsi-meet
vi interface_config.js

# Ändern:
DEFAULT_BACKGROUND: '#2c5aa0'
APP_NAME: 'EPPCOM Meet'

# Container neu starten
exit
docker-compose restart web
```

---

## TEIL 2: DEMO-DATEN VORBEREITEN

### Kontext
- Ziel: 25-30 realistische Politik-Dokumente in PostgreSQL
- Kategorien: Strategie, Prozesse, Kommunikation, Schulung
- Alle Dokumente müssen via n8n-Workflow indexiert werden

### Kategorie-Übersicht

**Kategorie 1: Politik-Strategie (7 Dokumente)**
1. `wahlkampf_strategie_2026.pdf` - Digitale Methoden, Social Media, Budget
2. `positionspapier_klimapolitik.pdf` - 5 Kernforderungen, Finanzierung
3. `positionspapier_sozialpolitik.pdf` - Rente, Gesundheit, Wohnen
4. `interne_satzung.pdf` - Rechtsgrundlagen der Organisation
5. `gremienstruktur.pdf` - Vorstand, Beiräte, Ausschüsse
6. `mitgliederordnung.pdf` - Rechte und Pflichten
7. `koalitionsvertrag_entwurf.pdf` - Muster-Verhandlungspapier

**Kategorie 2: Interne Prozesse (7 Dokumente)**
1. `prozess_antrag_stellen.pdf` - Wer, Wie, Fristen, Abstimmung
2. `prozess_veranstaltung_organisieren.pdf` - Checkliste, Raumplanung
3. `prozess_pressemitteilung.pdf` - Workflow, Freigaben, Verteiler
4. `prozess_reisekostenabrechnung.pdf` - Formulare, Belege, Fristen
5. `prozess_mitgliederverwaltung.pdf` - Beiträge, Austritte, Datenschutz
6. `prozess_beschlussverfolgung.pdf` - Tracking, Umsetzung, Reporting
7. `leitfaden_ehrenamtliche.pdf` - Koordination, Onboarding, Wertschätzung

**Kategorie 3: Externe Kommunikation (6 Dokumente)**
1. `leitfaden_social_media.pdf` - Do's & Don'ts, Tonalität, Reaktionszeiten
2. `krisenhandbuch_shitstorm.pdf` - Eskalationsstufen, Reaktionsteam
3. `presseverteiler.pdf` - Kontakte, Zuständigkeiten
4. `corporate_design_manual.pdf` - Logo, Farben, Schriften, Templates
5. `leitfaden_offentlichkeitsarbeit.pdf` - Medienarbeit, Kampagnen
6. `datenschutz_kommunikation.pdf` - DSGVO-konforme Pressearbeit

**Kategorie 4: Schulungsmaterial (7 Dokumente)**
1. `schulung_rhetorik_basics.pdf` - Redetechniken, Körpersprache
2. `schulung_moderation_gremien.pdf` - Gesprächsführung, Konfliktlösung
3. `schulung_konfliktmanagement.pdf` - Mediation, Deeskalation
4. `onboarding_neue_mitglieder.pdf` - Erste Schritte, Ansprechpartner
5. `schulung_fundraising.pdf` - Spenden, Sponsoring, Fördermittel
6. `schulung_campaigning.pdf` - Kampagnenplanung, Mobilisierung
7. `schulung_datenschutz_intern.pdf` - DSGVO für Ehrenamtliche

### Demo-Fragen (Test-Script)

**Einfache Faktenfragen:**
```
Q: "Wer darf in unserer Organisation Anträge stellen?"
A: Sollte aus prozess_antrag_stellen.pdf beantworten mit Quellenangabe

Q: "Welche Fristen gibt es für Anträge?"
A: 14 Tage Vorlauf für ordentliche, 48h für Dringlichkeitsanträge

Q: "Wer ist im Vorstand?"
A: Aus gremienstruktur.pdf
```

**Komplexe Vergleichsfragen:**
```
Q: "Was ist der Unterschied zwischen ordentlichen und Dringlichkeitsanträgen?"
A: Sollte beide Dokument-Abschnitte kombinieren

Q: "Wie unterscheiden sich unsere Positionen zu Klima vs. Sozialpolitik?"
A: Sollte beide Positionspapiere vergleichen
```

**Prozess-Fragen:**
```
Q: "Wie organisiere ich eine Mitgliederversammlung?"
A: 5-Schritte-Antwort aus prozess_veranstaltung_organisieren.pdf

Q: "Was mache ich bei einem Shitstorm?"
A: Eskalationsstufen aus krisenhandbuch_shitstorm.pdf
```

**"Keine Antwort"-Test:**
```
Q: "Wie hoch ist unser Jahresbudget?"
A: "Diese Information finde ich nicht in den verfügbaren Dokumenten."
```

### Dokumente generieren

**Option A: Aus EPPCOM_RAG_Wissensbasis.pdf extrahieren**
```python
# Python-Script erstellen: generate_demo_pdfs.py
# - Nimmt EPPCOM_RAG_Wissensbasis.pdf
# - Splittet in thematische Abschnitte
# - Ergänzt mit fiktiven aber realistischen Politik-Inhalten
# - Generiert 27 PDFs mit pypdf2/reportlab
```

**Option B: Manuell mit öffentlichen Quellen**
- Bundestag.de: Geschäftsordnungen, Satzungen (gemeinfrei)
- Parteien-Websites: Positionspapiere, Satzungen (oft CC-lizenziert)
- Wikipedia: Politische Begriffe, Prozesse

### In PostgreSQL laden

```bash
# n8n-Workflow triggern für jeden Upload
# Endpoint: POST https://workflows.eppcom.de/webhook/rag-ingest

for file in demo_docs/*.pdf; do
  curl -X POST \
    -F "file=@$file" \
    -F "tenant_id=demo-politik" \
    https://workflows.eppcom.de/webhook/rag-ingest
  echo "Uploaded: $file"
  sleep 2
done
```

---

## TEIL 3: TYPEBOT CHATBOT KONFIGURIEREN

### Subdomain erstellen

**Ziel:** `bot-demo.eppcom.de` als Demo-Instanz

**In Coolify:**
1. Typebot Viewer duplizieren
2. Neue Environment Variables:
   ```
   DATABASE_URL=postgresql://postgres:password@postgres/typebot_demo
   NEXTAUTH_URL=https://bot-demo.eppcom.de
   ```
3. Domain: `bot-demo.eppcom.de`
4. Deploy

### Typebot Flow erstellen

**Flow-Struktur:**
```
[Start]
  ↓
[Begrüßung] "👋 Willkommen! Ich bin Ihr KI-Wissensassistent..."
  ↓
[Text Input] "Stellen Sie mir eine Frage zu unseren internen Dokumenten"
  ↓
[Set Variable] user_question = {{input}}
  ↓
[Webhook] POST https://workflows.eppcom.de/webhook/rag-query
  Body: {"question": "{{user_question}}", "tenant_id": "demo-politik"}
  ↓
[Text] {{webhook.answer}}
  ↓
[Text] "Quellen: {{webhook.sources}}"
  ↓
[Buttons] ["Weitere Frage", "Feedback geben"]
```

**Design-Settings:**
- Theme Color: `#2c5aa0` (Politik-Blau)
- Avatar: Robot Icon
- Position: Bottom Right
- Opening Message: "Wie kann ich helfen?"

### Embedding-Code

```html
<script type="module">
  import Typebot from 'https://cdn.jsdelivr.net/npm/@typebot.io/js@0.3/dist/web.js'

  Typebot.initBubble({
    typebot: 'demo-politik-bot',
    apiHost: 'https://bot-demo.eppcom.de',
    previewMessage: {
      message: '👋 Fragen zu unseren Dokumenten?',
      autoShowDelay: 3000,
    },
    theme: {
      button: { backgroundColor: '#2c5aa0' },
      chatWindow: { backgroundColor: '#ffffff' },
    }
  })
</script>
```

---

## TEIL 4: N8N WORKFLOWS ERSTELLEN

### Workflow 1: RAG Ingestion

**Name:** `[DEMO] RAG Document Ingestion`  
**Trigger:** Webhook POST `/webhook/rag-ingest`

**Nodes:**
1. Webhook Trigger
2. Extract Binary Data (PDF → Text)
3. Text Splitter (Chunk Size: 512, Overlap: 50)
4. Loop Over Chunks
5. HTTP Request to Ollama (Embedding Generation)
   - URL: `http://46.224.54.65:11434/api/embeddings`
   - Model: `qwen3-embedding:0.6b`
6. PostgreSQL Insert
   - Table: `rag_chunks`
   - Columns: `document_id, tenant_id, chunk_text, embedding, metadata`
7. Response: `{"status": "success", "chunks": {{count}}}`

### Workflow 2: RAG Query

**Name:** `[DEMO] RAG Query Handler`  
**Trigger:** Webhook POST `/webhook/rag-query`

**Nodes:**
1. Webhook Trigger (Body: `{question, tenant_id}`)
2. HTTP Request - Generate Query Embedding
   - URL: `http://46.224.54.65:11434/api/embeddings`
   - Body: `{"model": "qwen3-embedding:0.6b", "prompt": "{{$json.question}}"}`
3. PostgreSQL Query - Vector Search
   ```sql
   SELECT 
     c.chunk_text,
     d.title,
     d.page_number,
     1 - (c.embedding <=> $1::vector) AS similarity
   FROM rag_chunks c
   JOIN rag_documents d ON c.document_id = d.id
   WHERE c.tenant_id = $2
   ORDER BY c.embedding <=> $1::vector
   LIMIT 5
   ```
4. Aggregate Context (Combine Top-5 Chunks)
5. HTTP Request - LLM Generation
   - URL: `http://46.224.54.65:11434/api/generate`
   - Model: `qwen3:1.7b`
   - Prompt:
     ```
     Du bist ein hilfreicher Assistent einer politischen Organisation.
     Beantworte die Frage ausschließlich basierend auf diesem Kontext:
     
     {{context}}
     
     Frage: {{question}}
     
     Wenn die Antwort nicht im Kontext steht, sage das ehrlich.
     Gib immer Quellenangaben an (Dokument, Seite).
     ```
6. Response:
   ```json
   {
     "answer": "{{llm_response}}",
     "sources": [
       {"title": "prozess_antrag_stellen.pdf", "page": 2},
       {"title": "interne_satzung.pdf", "page": 5}
     ]
   }
   ```

---

## TEIL 5: ADMIN-PANEL (SIMPLE HTML)

### n8n Webhook für Admin-UI

**Workflow:** `[DEMO] Admin Panel`

**Node 1: Webhook GET `/admin-demo`**
```html
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <title>EPPCOM Demo - Admin</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
      background: #f5f7fa;
      padding: 40px 20px;
    }
    .container { max-width: 600px; margin: 0 auto; }
    h1 { 
      color: #1a1a1a; 
      margin-bottom: 10px;
      font-size: 28px;
    }
    .subtitle {
      color: #666;
      margin-bottom: 40px;
    }
    .upload-box {
      background: white;
      border: 2px dashed #2c5aa0;
      border-radius: 12px;
      padding: 60px 40px;
      text-align: center;
      transition: all 0.3s;
    }
    .upload-box:hover {
      border-color: #1e3f7a;
      background: #f8fafc;
    }
    .upload-icon {
      font-size: 48px;
      margin-bottom: 20px;
    }
    input[type="file"] {
      display: none;
    }
    .file-label {
      display: inline-block;
      padding: 14px 32px;
      background: #2c5aa0;
      color: white;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
      transition: background 0.3s;
    }
    .file-label:hover {
      background: #1e3f7a;
    }
    .file-info {
      margin-top: 20px;
      color: #666;
      font-size: 14px;
    }
    .status {
      margin-top: 30px;
      padding: 16px;
      border-radius: 8px;
      display: none;
    }
    .status.success {
      background: #e8f5e9;
      color: #2e7d32;
      border: 1px solid #4caf50;
      display: block;
    }
    .status.error {
      background: #ffebee;
      color: #c62828;
      border: 1px solid #f44336;
      display: block;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      margin-top: 40px;
    }
    .stat-card {
      background: white;
      padding: 24px;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .stat-value {
      font-size: 32px;
      font-weight: bold;
      color: #2c5aa0;
    }
    .stat-label {
      color: #666;
      font-size: 14px;
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📁 Dokument hochladen</h1>
    <p class="subtitle">Demo-Umgebung für Politik-Organisation</p>
    
    <div class="upload-box">
      <div class="upload-icon">📄</div>
      <p style="margin-bottom: 20px; color: #666;">
        Unterstützte Formate: PDF, DOCX, PPTX, XLSX
      </p>
      <label for="fileInput" class="file-label">
        Datei auswählen
      </label>
      <input type="file" id="fileInput" accept=".pdf,.docx,.pptx,.xlsx" onchange="uploadFile()">
      <div class="file-info" id="fileInfo"></div>
    </div>
    
    <div class="status" id="status"></div>
    
    <div class="stats">
      <div class="stat-card">
        <div class="stat-value">27</div>
        <div class="stat-label">Dokumente</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">3.2s</div>
        <div class="stat-label">Ø Antwortzeit</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">94%</div>
        <div class="stat-label">Zufriedenheit</div>
      </div>
    </div>
  </div>
  
  <script>
    function uploadFile() {
      const fileInput = document.getElementById('fileInput');
      const file = fileInput.files[0];
      const status = document.getElementById('status');
      const fileInfo = document.getElementById('fileInfo');
      
      if (!file) return;
      
      fileInfo.textContent = `Ausgewählt: ${file.name}`;
      
      const formData = new FormData();
      formData.append('file', file);
      formData.append('tenant_id', 'demo-politik');
      
      status.className = 'status';
      status.textContent = '⏳ Wird hochgeladen und verarbeitet...';
      status.style.display = 'block';
      
      fetch('https://workflows.eppcom.de/webhook/rag-ingest', {
        method: 'POST',
        body: formData
      })
      .then(res => res.json())
      .then(data => {
        status.className = 'status success';
        status.textContent = `✅ Erfolgreich hochgeladen! ${data.chunks} Textabschnitte indexiert.`;
        fileInfo.textContent = '';
        fileInput.value = '';
      })
      .catch(err => {
        status.className = 'status error';
        status.textContent = '❌ Fehler beim Upload: ' + err.message;
      });
    }
  </script>
</body>
</html>
```

---

## TEIL 6: PRE-CALL CHECKLISTE

### 24h vor Demo-Call

```bash
# Server-Status prüfen
ssh root@94.130.170.167
docker ps
free -h
df -h

# PostgreSQL testen
docker exec -it <postgres-container> psql -U postgres -d eppcom_rag
SELECT count(*) FROM rag_documents WHERE tenant_id='demo-politik';
SELECT count(*) FROM rag_chunks WHERE tenant_id='demo-politik';

# n8n Workflows testen
curl -X POST https://workflows.eppcom.de/webhook/rag-query \
  -H "Content-Type: application/json" \
  -d '{"question": "Wer darf Anträge stellen?", "tenant_id": "demo-politik"}'

# Typebot öffnen und 5 Test-Fragen stellen

# Jitsi testen (mit Kollege/Freund)
https://meet.eppcom.de/demo-test-room
```

### 1h vor Call

**Browser-Tabs vorbereiten:**
1. `meet.eppcom.de/eppcom-politik-demo` (Meeting-Room)
2. `bot-demo.eppcom.de` (Chatbot)
3. `workflows.eppcom.de/admin-demo` (Admin-Panel)
4. `/mnt/user-data/outputs/Angebot_EPPCOM_KI_Wissensdatenbank.pdf` (Backup)

**Notizen griffbereit:**
```
Demo-Fragen:
1. "Wer darf Anträge stellen?"
2. "Welche Fristen gibt es für Anträge?"
3. "Wie organisiere ich eine Mitgliederversammlung?"
4. "Was mache ich bei einem Shitstorm?"
5. "Wie hoch ist unser Jahresbudget?" (sollte "nicht gefunden" sagen)
```

**Hardware-Check:**
- [ ] Mikrofon funktioniert
- [ ] Kamera funktioniert
- [ ] Zweiter Monitor (optional)
- [ ] Handy auf lautlos
- [ ] Wasser bereitstellen

---

## TEIL 7: DEMO-SCRIPT (SCREEN-SHARE)

### Minute 0-2: Intro
> "Vielen Dank für Ihre Zeit! Lassen Sie mich Ihnen zeigen, wie unser 
> DSGVO-konformes KI-System in der Praxis funktioniert. Ich habe hier 
> eine Demo-Umgebung mit typischen Dokumenten einer politischen 
> Organisation vorbereitet."

### Minute 2-5: Chatbot-Demo
**Tab: bot-demo.eppcom.de**

1. Bot öffnen (Widget rechts unten)
2. Frage eingeben: "Wer darf Anträge stellen?"
   - ✅ Sofort-Antwort mit Quellenangabe zeigen
3. "Welche Fristen gibt es?"
   - ✅ Details mit PDF-Verweis
4. "Wie organisiere ich eine Mitgliederversammlung?"
   - ✅ Schritt-für-Schritt-Anleitung
5. "Wie hoch ist unser Jahresbudget?"
   - ✅ "Diese Info finde ich nicht" (Sicherheits-Feature)

> "Wie Sie sehen: Der Bot antwortet nur auf Basis Ihrer Dokumente,
> nie aus dem Internet. Und bei fehlenden Infos sagt er das ehrlich."

### Minute 5-7: Admin-Demo
**Tab: workflows.eppcom.de/admin-demo**

> "Und so würden Ihre Admins neue Dokumente hinzufügen..."

1. Admin-Panel zeigen
2. Test-PDF hochladen (z.B. vorbereitet: "neue_richtlinie.pdf")
3. Upload-Status zeigen: "✅ 12 Textabschnitte indexiert"
4. Zurück zum Chat
5. Frage eingeben: "Was steht in der neuen Richtlinie?"
   - ✅ Bot findet es sofort

> "Das Dokument ist innerhalb von Sekunden durchsuchbar."

### Minute 7-9: DSGVO-Argument
**Optional: Terminal-Fenster**

> "Alle Daten liegen ausschließlich auf diesem Server hier in Deutschland.
> Keine Cloud, keine OpenAI, keine Google APIs."

1. SSH-Fenster zeigen (optional)
2. `docker ps` zeigen
3. Betonen: "Hetzner Falkenstein, Deutschland"

### Minute 9-10: Offene Fragen

> "Das war unser System in Aktion. Welche Fragen haben Sie?"

**Häufige Fragen vorbereiten:**
- "Wie lange dauert die Einrichtung?" → 6 Wochen
- "Was kostet es?" → Pilot: 499€/Monat für 3 Monate
- "Können wir es testen?" → Ja, mit Ihren eigenen Dokumenten

---

## ABSCHLUSS-CHECKS

### Deployment-Checklist
- [ ] Jitsi läuft auf meet.eppcom.de
- [ ] DNS-Eintrag aktiv (meet.eppcom.de → 94.130.170.167)
- [ ] SSL-Zertifikat vorhanden
- [ ] Test-Meeting erfolgreich
- [ ] 27 Demo-PDFs in PostgreSQL
- [ ] n8n RAG-Ingestion-Workflow funktioniert
- [ ] n8n RAG-Query-Workflow funktioniert
- [ ] Typebot auf bot-demo.eppcom.de läuft
- [ ] Admin-Panel erreichbar
- [ ] 5 Test-Fragen erfolgreich beantwortet

### Dokumentation für Kunde
- [ ] Angebot-PDF liegt bereit
- [ ] NDA vorbereitet (falls nötig)
- [ ] Implementierungs-Zeitplan im Angebot
- [ ] Referenz-Case-Study-Vereinbarung vorbereitet

---

## NOTFALLPLAN

### Wenn Jitsi nicht funktioniert
→ Fallback: Google Meet nutzen (sofort verfügbar)

### Wenn Chatbot nicht antwortet
→ Backup: Screenshots von funktionierenden Antworten zeigen

### Wenn Server down ist
→ Status-Check 2h vor Meeting, ggf. neu starten

### Wenn Internet-Verbindung abbricht
→ Handy-Hotspot als Backup, Meeting über Mobile

---

## RESSOURCEN

### Wichtige URLs
- Jitsi: https://meet.eppcom.de
- Demo-Bot: https://bot-demo.eppcom.de
- Admin: https://workflows.eppcom.de/admin-demo
- n8n: https://workflows.eppcom.de

### Zugangsdaten
- Server 1 SSH: root@94.130.170.167
- Coolify: workflows.eppcom.de (bereits eingeloggt)
- PostgreSQL: Container-intern, Port 5432

### Support-Kontakte
- Hetzner Support: +49 9831 5050404
- Eigene Backup-Nummer: [einsetzen]

---

**WICHTIG FÜR CLAUDE CODE:**
- Alle Pfade sind relativ zu Server 1 (94.130.170.167)
- Environment Variables müssen in .env gespeichert werden
- Niemals Secrets in Git committen
- Nach jedem Deployment: Logs prüfen mit `docker-compose logs -f`
- Bei Problemen: Rollback mit `docker-compose down && git checkout main`
