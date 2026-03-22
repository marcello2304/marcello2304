# n8n RAG Workflows — Aktivierung & Testing

## 📋 Übersicht

Diese Anleitung aktiviert die beiden RAG Workflows in n8n:
1. **RAG Query** — Webhook: `https://workflows.eppcom.de/webhook/rag-query`
2. **RAG Ingestion** — Webhook: `https://workflows.eppcom.de/webhook/rag-ingest`

---

## 🔧 OPTION A: Workflows in n8n UI Aktivieren (5 Minuten)

### **Schritt 1: n8n öffnen**
```
https://workflows.eppcom.de
```

### **Schritt 2: RAG Query Workflow öffnen**
1. Suche nach `RAG Query (Typebot Integration)`
2. Klick auf den Workflow
3. Oben rechts: Klick auf den **Power-Button** (sollte grau/rot sein)
4. **Bestätigung:** Der Button wird **grün** → Workflow ist aktiv ✅

**Screenshot Markierungen:**
- Power-Button: Oben rechts im Editor
- Status: "Active" sollte neben dem Workflow-Namen angezeigt werden

### **Schritt 3: RAG Ingestion Workflow öffnen**
1. Suche nach `RAG Document Ingestion`
2. Klick auf den Workflow
3. Power-Button → **Green (Aktiv)**
4. **Bestätigung:** Der Button wird **grün** ✅

### **Schritt 4: Webhook URLs überprüfen**
1. Im RAG Query Workflow:
   - Klick auf den **"Webhook: POST /rag-query"** Node (erster Node links)
   - Kopiere die **"Webhook URL"** (sollte sein: `https://workflows.eppcom.de/webhook/rag-query`)
   - Notiz: Das wird für Tests genutzt

---

## 🧪 OPTION B: Workflows via API Aktivieren (Alternative)

Falls die n8n UI nicht erreichbar ist, können Sie die Workflows via n8n API aktivieren:

```bash
# Get n8n API key from n8n UI: Settings → API Keys → Generate

N8N_API_KEY="your-api-key-here"
N8N_BASE_URL="https://workflows.eppcom.de/api/v1"

# List all workflows
curl -s -X GET "$N8N_BASE_URL/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.data[] | {id, name, active}'

# Activate RAG Query by workflow ID
# (Replace WORKFLOW_ID with the actual ID from the list above)
curl -X PATCH "$N8N_BASE_URL/workflows/WORKFLOW_ID" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

---

## 🧪 SCHRITT 5: Test RAG Query Webhook

### **Test 1: Simple Query**
```bash
curl -X POST https://workflows.eppcom.de/webhook/rag-query \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "eppcom",
    "query": "Wer bist du?"
  }'
```

**Erwartete Antwort:**
```json
{
  "answer": "Ich bin ein KI-Assistent...",
  "sources": [...],
  "model": "phi:latest",
  "latency_ms": 5234
}
```

### **Test 2: Voice Bot RAG Format**
```bash
curl -X POST https://workflows.eppcom.de/webhook/rag-query \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "eppcom",
    "query": "Hallo, wie funktioniert der Voice Bot?",
    "session_id": "voice-session-001",
    "bot_id": "voice-bot",
    "top_k": 5,
    "min_similarity": 0.55,
    "model": "phi:latest"
  }'
```

**Debugging bei Fehler:**
- `404`: Workflow nicht aktiviert oder URL falsch
- `500`: Fehler in n8n Workflow (siehe Logs in n8n UI)
- `timeout`: RAG braucht länger (>10s) — Ollama oder DB langsam
- `"no_context": true`: Keine ähnlichen Dokumente gefunden

---

## 📊 RAG Ingestion Test

Dokumente in die RAG DB laden (optional für Tests):

```bash
curl -X POST https://workflows.eppcom.de/webhook/rag-ingest \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "eppcom",
    "name": "Test Document",
    "source_type": "manual",
    "content": "Das ist ein Testdokument für den Voice Bot RAG.",
    "doc_type": "documentation",
    "page_number": 1
  }'
```

---

## ✅ Checkliste

- [ ] n8n UI erreichbar: https://workflows.eppcom.de
- [ ] RAG Query Workflow aktiv (Power-Button grün)
- [ ] RAG Ingestion Workflow aktiv (Power-Button grün)
- [ ] RAG Query Webhook antwortet (`curl` Test erfolgreich)
- [ ] Voice Bot Docker Container läuft (`docker ps | grep livekit-agent`)
- [ ] Agent Logs zeigen "Agent started and listening"

---

## 🚀 Nächster Schritt

Sobald die Workflows aktiv sind, starte das Deployment-Skript auf Server 2:

```bash
ssh user@46.224.54.65
cd /root/marcello2304

# Mach Skript ausführbar
chmod +x DEPLOY_VOICE_BOT_SERVER2.sh

# Starte Deployment
./DEPLOY_VOICE_BOT_SERVER2.sh
```

Das Skript wird:
1. ✅ Git aktualisieren
2. ✅ Docker Image bauen
3. ✅ Voice Agent starten
4. ✅ RAG Webhook testen
5. ✅ Status anzeigen

---

## 🔧 Troubleshooting

### **Problem: RAG Webhook gibt 404**
**Lösung:** Workflow ist nicht aktiviert
```bash
# In n8n UI: Workflow öffnen → Power-Button klicken → Warten bis grün
```

### **Problem: RAG Webhook antwortet nicht (Timeout)**
**Lösung:** Ollama oder DB ist langsam
```bash
# Überprüfe Ollama:
docker exec ollama ollama list
docker logs ollama | tail -50

# Überprüfe n8n Workflow Logs:
# In n8n UI: Workflow öffnen → "Execution" Tab → Fehler anschauen
```

### **Problem: Voice Agent crasht**
**Lösung:** RAG timeout zu kurz, oder Abhängigkeit fehlt
```bash
# Logs anschauen:
docker logs -f livekit-agent

# Starte Agent neu:
docker restart livekit-agent
```

---

## 📞 Support

Falls Probleme auftreten:
1. Überprüfe n8n Workflow Execution Logs
2. Überprüfe Voice Agent Container Logs
3. Teste RAG Webhook direkt mit curl
4. Überprüfe PostgreSQL RAG DB Verbindung (in n8n UI)

---

**Status:** Workflows korrigiert & bereit zur Aktivierung ✅
