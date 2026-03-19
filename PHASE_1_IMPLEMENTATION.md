# Admin-UI Phase 1 Implementation Plan (OPTION C)

## Context

Das Admin-UI ist für die Hetzner RAG-Plattform (eppcom.de) als Multi-Tenant Admin-Dashboard geplant.
Das admin-ui Verzeichnis ist aktuell leer (nur .pyc). Datenbank-Schema (PostgreSQL + pgvector) und Docker-Konfigurationen existieren bereits.
OPTION C (Full Featured) wurde gewählt. Wir beginnen mit Phase 1 MVP.

## Ziel dieser Session

Phase 1 vollständig implementieren:
1. **FastAPI Backend** — Auth + User/API Management + Knowledge Base Upload
2. **Vue 3 Frontend** — Layout, Dashboard, Knowledge Base, Voice Bot Monitor

---

## Implementierungsstrategie

### Schritt 1: Backend-Grundstruktur (FastAPI)

**Verzeichnis:** `admin-ui/` (Python Backend)

**Dateien zu erstellen:**
- `admin-ui/main.py` — FastAPI App Entry-point
- `admin-ui/requirements.txt` — Dependencies
- `admin-ui/config.py` — Settings (liest aus .env)
- `admin-ui/models.py` — SQLAlchemy Models (Users, APIKeys, tenants)
- `admin-ui/auth.py` — JWT Authentication + RBAC
- `admin-ui/routers/users.py` — User CRUD Endpoints
- `admin-ui/routers/api_keys.py` — API Key Management
- `admin-ui/routers/knowledge_base.py` — File Upload + Chunking
- `admin-ui/routers/dashboard.py` — Dashboard Stats Endpoints
- `admin-ui/routers/voice.py` — LiveKit Status Endpoints

**Backend-Dependencies:**
```
fastapi==0.115.0
uvicorn==0.30.0
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
pydantic-settings==2.5.2
python-dotenv==1.0.1
httpx==0.27.2
```

---

### Schritt 2: Vue 3 Frontend aufbauen

**Verzeichnis:** `admin-ui/frontend/`

**Setup-Befehle:**
```bash
cd /root/marcello2304/admin-ui
npm create vue@latest frontend -- --typescript --router --pinia
cd frontend && npm install
npm install @headlessui/vue tailwindcss @vueuse/core axios chart.js vue-chartjs lucide-vue-next
npx tailwindcss init -p
```

**Frontend-Struktur:**
```
admin-ui/frontend/src/
├── components/
│   ├── layout/Sidebar.vue
│   ├── layout/Header.vue
│   ├── dashboard/StatsCard.vue
│   ├── dashboard/MetricChart.vue
│   ├── knowledge-base/FileUpload.vue
│   ├── knowledge-base/DocumentList.vue
│   ├── voice/VoiceBotStatus.vue
│   └── users/UserTable.vue
├── views/
│   ├── DashboardView.vue
│   ├── KnowledgeBaseView.vue
│   ├── UsersView.vue
│   └── VoiceMonitorView.vue
├── stores/
│   ├── authStore.ts
│   ├── dashboardStore.ts
│   └── knowledgeBaseStore.ts
├── api/
│   └── client.ts (Axios + Interceptors)
└── router/index.ts
```

---

### Schritt 3: Dashboard-Features

**Backend Endpoints:**
- `GET /api/dashboard/stats` — Gesamt-Metriken (tenants, docs, queries, tokens)
- `GET /api/dashboard/activity` — Letzte Aktivitäten
- `GET /api/dashboard/usage-chart` — Token-Verbrauch Chart-Daten

**Frontend:**
- 4 Stats-Karten (Tenants, Dokumente, Queries heute, Token-Verbrauch)
- Linien-Chart (Queries pro Tag, letzte 30 Tage)
- Letzte Aktivitäten Liste

---

### Schritt 4: Knowledge Base Upload

**Backend Endpoints:**
- `POST /api/knowledge-base/upload` — Datei hochladen (PDF, DOCX, TXT)
- `GET /api/knowledge-base/documents` — Dokument-Liste
- `DELETE /api/knowledge-base/documents/{id}` — Dokument löschen

**Frontend:**
- Drag-and-Drop Upload-Zone
- Dokument-Liste mit Status (indexiert/pending/error)
- Upload-Progress-Bar

---

### Schritt 5: Voice Bot Monitor

**Backend Endpoints:**
- `GET /api/voice/status` — LiveKit Room-Status über LiveKit API
- `GET /api/voice/rooms` — Aktive Räume + Teilnehmer

**Frontend:**
- Live Status-Badge (Online/Offline)
- Aktive Calls Liste
- Agent-Status (STT/TTS Model Status)

---

## Kritische Dateien (Referenz)

| Datei | Zweck |
|-------|-------|
| `docker/compose-server1.yml` | Traefik + PostgreSQL Konfiguration |
| `docker/compose-server2.yml` | LiveKit + Ollama Konfiguration |
| `sql/002_public_schema.sql` | tenants + tenant_usage Tabellen |
| `sql/004_functions.sql` | get_tenant_stats(), search_chunks() |
| `.env` | DB_URL, JWT_SECRET, LIVEKIT_API_KEY, etc. |

---

## Verifikation

Nach Implementierung:
```bash
# Backend starten
cd admin-ui && uvicorn main:app --reload --port 8001
# API docs aufrufen: http://localhost:8001/docs

# Frontend starten
cd admin-ui/frontend && npm run dev
# Browser: http://localhost:5173

# Test: Login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@eppcom.de","password":"test"}'
```

---

## Reihenfolge (Sequential)

1. ✅ Backend-Dateien erstellen (main.py, config.py, auth.py, models.py, routers/)
2. ✅ Vue-Projekt initialisieren + Dependencies installieren
3. ✅ Layout + Router + Sidebar
4. ✅ Dashboard View
5. ✅ Knowledge Base Upload
6. ✅ Voice Bot Monitor
7. ✅ User Management Table
8. ✅ Git commit + push
