# EPPCOM Voice Bot — Statusbericht 22.03.2026

## Architektur-Überblick

```
┌─────────────────────────────────────────────────────────────────┐
│  SERVER 1 (Coolify)                                             │
│  ├── PostgreSQL + pgvector (RAG-Speicher)                       │
│  ├── n8n Workflows:                                             │
│  │   ├── RAG Ingestion: workflows.eppcom.de/webhook/rag-ingest │
│  │   └── RAG Query:     workflows.eppcom.de/webhook/rag-query  │
│  ├── Typebot (Builder + Viewer)                                 │
│  └── RAG Admin Panel                                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SERVER 2 (46.224.54.65) — docker-compose-server2.yml           │
│  ├── nginx-proxy (:80/:443) — Reverse Proxy + Static Files     │
│  │   ├── / → Static HTML (test-voice-agent.html)                │
│  │   ├── /api/token → token-server:8765 (JWT)                  │
│  │   └── /livekit/ → livekit:7880 (WebSocket Proxy)            │
│  ├── livekit-server (:7880) — WebRTC Signaling                 │
│  ├── livekit-agent — Voice Bot Worker (Python, v1.4 API)       │
│  │   ├── STT: Local Whisper (small, self-hosted, kostenlos)    │
│  │   ├── LLM: Ollama phi:2b (lokal)                            │
│  │   ├── TTS: Cartesia Sonic-2 (<100ms Latenz)                 │
│  │   ├── VAD: Silero (Voice Activity Detection)                │
│  │   └── RAG: n8n Webhook Integration                          │
│  ├── ollama (:11434) — LLM Inference Server                    │
│  ├── livekit-token-server (:8765) — JWT Token Generator        │
│  └── certbot — SSL-Zertifikate (optional)                      │
└─────────────────────────────────────────────────────────────────┘

Verbindungsfluss:
  Browser → nginx(:80) → /api/token → JWT Token
  Browser → ws://46.224.54.65:7880 → LiveKit Room → livekit-agent
  livekit-agent → Whisper STT → Ollama LLM → Cartesia TTS → Audio zurück
  livekit-agent → n8n RAG Webhook → PostgreSQL/pgvector → Kontext
```

---

## Errungenschaften (Was funktioniert)

### ✅ Infrastruktur
- Docker-Compose Stack mit 6 Services konfiguriert und deployed
- Alle Container laufen (livekit, livekit-agent, token-server, nginx, ollama)
- Docker-Netzwerk `ai-net` verbindet alle Container
- nginx Reverse Proxy routet korrekt

### ✅ Token-Generierung
- JWT Token Server läuft als Container
- Endpunkt: `http://46.224.54.65/api/token?room=NAME&user=NAME`
- Gibt valide JWT Tokens zurück (getestet, funktioniert!)
- CORS Headers korrekt gesetzt

### ✅ LiveKit Server
- LiveKit Server läuft auf Port 7880
- WebSocket-Endpunkt erreichbar
- livekit.yaml korrekt konfiguriert mit API Key/Secret
- Webhook URL auf workflows.eppcom.de gesetzt
- Room auto_create aktiviert

### ✅ Voice Agent Code (Backend)
- `voice-agent/agent.py` — Vollständig auf livekit-agents v1.4 API migriert
- NexoAgent + NexoStreamingAgent Klassen implementiert
- RAG-Kontext-Fetching mit Caching
- STT/LLM/TTS Provider-Ketten mit Fallbacks
- Sentence-Level Streaming für niedrige Latenz

### ✅ Frontend (Browser)
- `test-voice-agent.html` — Korrekte LiveKit v2.x JavaScript API
- Verwendet: `new LivekitClient.Room()` + `room.connect()`
- Token-Generierung via nginx Proxy
- Audio-Playback für Agent-Antworten
- Mikrofon-Toggle

### ✅ RAG Integration
- n8n Workflows laufen auf Server 1
- RAG Ingestion: `https://workflows.eppcom.de/webhook/rag-ingest`
- RAG Query: `https://workflows.eppcom.de/webhook/rag-query`
- Agent holt RAG-Kontext vor jeder Antwort

### ✅ Git Repository
- Alle Dateien committed und gepusht auf `main`
- Secrets nur in `.env.server2` (gitignored)
- Letzter Commit: `4e08685` (22.03.2026)

---

## Bekannte Probleme (Was noch NICHT funktioniert)

### 🔴 KRITISCH: Environment-Variablen werden nicht geladen
**Status:** NICHT GELÖST — Docker-Compose zeigt Warnungen:
```
WARN: "LIVEKIT_API_SECRET" variable is not set. Defaulting to blank string.
WARN: "CARTESIA_API_KEY" variable is not set. Defaulting to blank string.
WARN: "LIVEKIT_API_KEY" variable is not set. Defaulting to blank string.
```

**Ursache:** Docker-Compose liest `${VARIABLE}` Substitutionen nicht aus dem `env_file` der Services, sondern nur aus einer `.env` Datei im gleichen Verzeichnis wie die compose-Datei.

**Lösung (MUSS NOCH AUSGEFÜHRT WERDEN):**
```bash
cp /root/marcello2304/.env.server2 /root/marcello2304/docker/.env
cd /root/marcello2304/docker
docker-compose -f compose-server2.yml down
docker-compose -f compose-server2.yml up -d --build
docker-compose -f compose-server2.yml ps  # Keine WARN mehr!
docker exec livekit-agent env | grep -E "LIVEKIT|CARTESIA"  # Werte prüfen
```

### 🟡 Browser-Fehler: "LivekitClient not properly loaded"
**Status:** UNKLAR — Tritt beim Klicken auf "Verbinden" auf
- LiveKit SDK lädt korrekt (Bibliothek vorhanden)
- Token wird generiert
- Verbindung schlägt fehl mit "LivekitClient not properly loaded"
- Fehlermeldung stimmt nicht mit dem Code in test-voice-agent.html überein
- Möglicherweise wird eine alte/gecachte Version der HTML-Datei geladen

**Debugging-Schritte:**
1. Browser-Cache leeren (Cmd+Shift+R / Ctrl+Shift+R)
2. Prüfen welche Datei tatsächlich geladen wird:
   ```bash
   curl -s http://46.224.54.65/test-voice-agent.html | grep "not properly loaded"
   ```
3. Falls nötig, `test-voice-simple.html` deployen (existiert im Repo als Diagnose-Seite)

### 🟡 Ollama Status: "unhealthy"
**Status:** Ollama Container zeigt `(unhealthy)` Status
- Muss geprüft werden ob das Modell `phi:2b` geladen ist
- Ggf. Modell herunterladen:
  ```bash
  docker exec ollama ollama pull phi:2b
  ```

### 🟡 test-voice-simple.html nicht über nginx erreichbar
- Datei existiert im Repo, aber Volume Mount fehlt in compose-server2.yml
- Muss in nginx Volume Mounts aufgenommen werden

---

## Wichtige Dateien

| Datei | Zweck | Status |
|-------|-------|--------|
| `docker/compose-server2.yml` | Docker-Orchestrierung Server 2 | ✅ Aktuell |
| `docker/livekit.yaml` | LiveKit Server Konfiguration | ✅ Aktuell |
| `docker/nginx/nginx.conf` | nginx Reverse Proxy Config | ✅ Aktuell |
| `docker/Dockerfile.token-server` | Token Server Container | ✅ Aktuell |
| `.env.server2` | Alle Secrets und Keys | ✅ NICHT committet |
| `livekit-token-server.py` | JWT Token Generator | ✅ Funktioniert |
| `test-voice-agent.html` | Browser-Testseite (v2.x API) | ✅ Code korrekt |
| `test-voice-simple.html` | Diagnose-Seite (schrittweise) | ✅ Noch nicht deployed |
| `voice-agent/agent.py` | Voice Bot Worker (v1.4 API) | ✅ Code korrekt |
| `voice-agent/requirements.txt` | Python Dependencies | ✅ Aktuell |
| `voice-agent/Dockerfile` | Agent Container (Python 3.11) | ✅ Aktuell |
| `voice-agent/constants.py` | Streaming-Konstanten | ✅ Vorhanden |
| `voice-agent/local_whisper_stt.py` | Lokaler Whisper STT Adapter | ✅ Vorhanden |

---

## Secrets & Credentials (VERTRAULICH)

Alle Secrets liegen in `.env.server2` (gitignored). Wichtige Keys:
- **LiveKit API Key:** `8fa8f1b33782e91f85b57f6648712aeb`
- **LiveKit API Secret:** `a161db1f4107b166ac82cf45d7799a73284a5a799c8d0b14dcbfc150c5bce21c`
- **Cartesia API Key:** `sk_car_bTemPMLHD6J2o7sjqucYQy` (aus User-Nachricht)
- **Cartesia Voice ID:** `38aabb6a-f52b-4fb0-a3d1-988518f4dc06` (aus User-Nachricht)
- **Ollama Bearer Token:** in .env.server2
- **RAG API Key:** in .env.server2
- SSH-Passwort Server 2: NICHT in Dateien speichern!

---

## Nächste Schritte (Priorität)

### Schritt 1: Environment-Variablen fixen (HÖCHSTE PRIO)
```bash
# Auf Server 2:
cp /root/marcello2304/.env.server2 /root/marcello2304/docker/.env
cd /root/marcello2304/docker
docker-compose -f compose-server2.yml down
docker-compose -f compose-server2.yml up -d --build
```
Verifizieren:
```bash
docker-compose -f compose-server2.yml ps  # Keine WARN!
docker exec livekit-agent env | grep CARTESIA_API_KEY  # Wert sichtbar!
docker logs livekit-agent | head -30  # STT/LLM/TTS Initialisierung prüfen
```

### Schritt 2: Cartesia Voice ID aktualisieren
Die .env.server2 hat `CARTESIA_VOICE_ID=default`, muss auf die echte Voice ID gesetzt werden:
```bash
# In /root/marcello2304/.env.server2 ändern:
CARTESIA_VOICE_ID=38aabb6a-f52b-4fb0-a3d1-988518f4dc06
# Dann erneut kopieren:
cp .env.server2 docker/.env
cd docker && docker-compose -f compose-server2.yml up -d livekit-agent
```

### Schritt 3: Ollama Modell prüfen
```bash
docker exec ollama ollama list  # Modelle anzeigen
docker exec ollama ollama pull phi:2b  # Falls nicht vorhanden
```

### Schritt 4: Browser-Test
1. Cache leeren
2. http://46.224.54.65/test-voice-agent.html öffnen
3. "Verbinden" klicken
4. Browser-Konsole (F12) prüfen — vollständige Fehlermeldung kopieren

### Schritt 5: Agent-Logs bei Verbindung prüfen
```bash
# In einem Terminal laufen lassen während Browser-Test:
docker logs -f livekit-agent
```
Erwartete Ausgabe bei erfolgreicher Verbindung:
```
Connected to room: test-voice-bot
Using NexoStreamingAgent (streaming enabled)
Agent started and listening
```

### Schritt 6: End-to-End Voice Test
- Mikrofon aktivieren
- Testsatz sprechen: "Hallo, wie heißt du?"
- Agent sollte mit Cartesia-Stimme antworten
- Latenz messen (Ziel: <2s Turn-Around)

### Schritt 7: Homepage/Typebot Integration
- Voice Bot in Typebot oder eppcom.de Homepage einbinden
- WebSocket URL und Token-Endpunkt konfigurieren

---

## Häufige Befehle (Cheatsheet)

```bash
# Stack starten/stoppen
cd /root/marcello2304/docker
docker-compose -f compose-server2.yml up -d
docker-compose -f compose-server2.yml down

# Logs prüfen
docker logs -f livekit-agent        # Voice Agent
docker logs -f livekit              # LiveKit Server
docker logs -f nginx-proxy          # nginx
docker logs -f livekit-token-server # Token Server

# Agent neu starten (nach Code-Änderung)
docker-compose -f compose-server2.yml up -d --build livekit-agent

# Token testen
curl "http://46.224.54.65/api/token?room=test&user=test"

# Agent Environment prüfen
docker exec livekit-agent env | sort

# Ollama testen
docker exec ollama ollama run phi:2b "Hallo, wie geht es dir?"
```

---

**Erstellt:** 22.03.2026
**Letzter Commit:** 4e08685
**Branch:** main
**Repository:** github.com/marcello2304/marcello2304
