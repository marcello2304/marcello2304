# B. Zielarchitektur und Netzwerkplan

## Übersicht

```
┌─────────────────────────────────────────────────────────┐
│                    INTERNET / USER                       │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS (443)
         ┌─────────────▼──────────────────┐
         │         SERVER 1               │
         │     94.130.170.167             │
         │                                │
         │  ┌─────────────────────────┐   │
         │  │   Traefik (Coolify)     │   │
         │  │   Port 80, 443          │   │
         │  │   Let's Encrypt ACME    │   │
         │  └──┬──────┬──────┬───────┘   │
         │     │      │      │            │
         │  ┌──▼──┐ ┌─▼──┐ ┌▼──────┐    │
         │  │Type-│ │ n8n│ │Coolify│    │
         │  │ bot │ │    │ │  UI   │    │
         │  │3000 │ │5678│ │ 8000  │    │
         │  └──┬──┘ └─┬──┘ └───────┘   │
         │     │      │                  │
         │  ┌──▼──────▼──────────────┐  │
         │  │   coolify-net (Docker) │  │
         │  └──────────┬─────────────┘  │
         │             │                 │
         │  ┌──────────▼─────────────┐  │
         │  │  PostgreSQL + pgvector │  │
         │  │  Port 5432 (intern)    │  │
         │  │  DB: app_db, rag_db    │  │
         │  └────────────────────────┘  │
         │                               │
         │  ┌────────────────────────┐  │
         │  │  Hetzner Object Store  │  │
         │  │  (S3-kompatibel)       │  │
         │  │  fsn1.your-objectstore │  │
         │  └────────────────────────┘  │
         └─────────────┬────────────────┘
                       │ Private/Public API calls
                       │ (HTTPS, Port 443 oder 11434)
         ┌─────────────▼──────────────────┐
         │         SERVER 2               │
         │     <SERVER2_IP>               │
         │                                │
         │  ┌─────────────────────────┐   │
         │  │  Ollama (LLM)           │   │
         │  │  Port 11434 (intern)    │   │
         │  │  Reverse Proxy → HTTPS  │   │
         │  └─────────────────────────┘   │
         │                                │
         │  ┌─────────────────────────┐   │
         │  │  LiveKit Server         │   │
         │  │  Port 7880 (HTTPS/WS)   │   │
         │  │  Port 7881 (RTC/UDP)    │   │
         │  │  Port 50000-60000 (UDP) │   │
         │  └─────────────────────────┘   │
         │                                │
         │  ┌─────────────────────────┐   │
         │  │  LiveKit Agent          │   │
         │  │  (Python/Node Worker)   │   │
         │  └─────────────────────────┘   │
         └────────────────────────────────┘
```

---

## Services-Verteilung

### Server 1 — Anwendungs- und Datenschicht

| Service | Zweck | Interner Port | Domain |
|---------|-------|--------------|--------|
| Traefik | Reverse Proxy + SSL | 80, 443 | — |
| Typebot Builder | Chat-Flow Editor | 3000 | builder.deine-domain.de |
| Typebot Viewer | Bot-Frontend (Kunden) | 3001 | bot.deine-domain.de |
| n8n | Workflow Automation + Ingestion | 5678 | n8n.deine-domain.de |
| PostgreSQL + pgvector | App-DB + RAG-Speicher | 5432 (intern only) | — |
| Coolify UI | Deployment Management | 8000 | coolify.deine-domain.de |

**Hetzner Object Storage** (managed, kein Docker):
- Endpoint: `https://fsn1.your-objectstorage.com` (oder `nbg1`)
- Kein Container nötig — S3-API direkt aus n8n und Typebot

### Server 2 — KI und Voice-Schicht

| Service | Zweck | Port |
|---------|-------|------|
| Nginx/Traefik | Reverse Proxy für Ollama | 443 |
| Ollama | LLM Inference | 11434 (intern) |
| LiveKit Server | WebRTC Signaling + Media | 7880 (HTTPS/WS), 7881 (RTC) |
| LiveKit Agent | Voice-to-Text + LLM Bridge | intern |
| LiveKit Egress | Recording (optional) | intern |

---

## Kommunikationswege

### Typebot → Ollama (Server 2)
```
Typebot (Server 1) ──HTTPS──► Nginx (Server 2) ──localhost──► Ollama:11434
```
- Typebot nutzt den "HTTP Request" Block mit Bearer Token
- URL: `https://ollama.deine-domain.de/api/generate`
- Ollama darf NICHT direkt auf Port 11434 vom Internet erreichbar sein

### n8n → PostgreSQL
```
n8n ──coolify-net──► postgres:5432
```
- Rein intern, kein externer Port
- Connection String: `postgresql://n8n_user:password@postgres:5432/app_db`

### Typebot → PostgreSQL (RAG Queries)
```
Typebot ──coolify-net──► postgres:5432
```
- Typebot nutzt n8n-Webhook für RAG-Retrieval (empfohlen)
- Oder: Typebot direkt mit Postgres via HTTP-Block zu n8n RAG-Endpoint

### n8n → Hetzner S3
```
n8n ──HTTPS──► fsn1.your-objectstorage.com (Port 443)
```

### LiveKit Agent → Ollama
```
LiveKit Agent (Server 2) ──localhost──► Ollama:11434
```
- Alles auf Server 2, kein Netzwerk-Hop

### Typebot → LiveKit (Voice UI)
```
Browser ──WSS──► LiveKit Server (Server 2):7880
Typebot stellt LiveKit Token bereit via n8n Webhook
```

---

## Docker Network Design (Server 1)

```yaml
# Netzwerke:
networks:
  coolify:          # Haupt-Netz, Traefik + alle Apps
    external: true  # Von Coolify automatisch erstellt
  rag-internal:     # Isoliertes Netz für DB-Zugriff
    driver: bridge
    internal: true  # Kein Internetzugang
```

**Regeln:**
- Traefik ist IMMER in `coolify`-Netz
- Alle Apps mit öffentlichem Zugang sind in `coolify`-Netz
- PostgreSQL ist NUR in `rag-internal` + `coolify` (kein externer Port bind)
- Kein Container bindet Postgres auf `0.0.0.0:5432`

---

## Ports: Was muss offen sein

### Server 1 (Hetzner Firewall + ufw)

| Port | Protokoll | Von | Wozu | Offen? |
|------|-----------|-----|------|--------|
| 22 | TCP | Deine IP | SSH | JA (nur deine IP) |
| 80 | TCP | 0.0.0.0/0 | HTTP + ACME Challenge | JA |
| 443 | TCP | 0.0.0.0/0 | HTTPS alle Services | JA |
| 5432 | TCP | — | PostgreSQL | NEIN (intern) |
| 5678 | TCP | — | n8n direkt | NEIN (via Traefik) |
| 3000 | TCP | — | Typebot direkt | NEIN (via Traefik) |
| 8000 | TCP | Deine IP | Coolify UI | Optional (nur deine IP) |

### Server 2 (Hetzner Firewall + ufw)

| Port | Protokoll | Von | Wozu | Offen? |
|------|-----------|-----|------|--------|
| 22 | TCP | Deine IP | SSH | JA |
| 80 | TCP | 0.0.0.0/0 | HTTP ACME | JA |
| 443 | TCP | 0.0.0.0/0 | Ollama HTTPS, LiveKit | JA |
| 7880 | TCP | 0.0.0.0/0 | LiveKit WebSocket | JA |
| 7881 | TCP | 0.0.0.0/0 | LiveKit RTC TCP | JA |
| 50000-60000 | UDP | 0.0.0.0/0 | LiveKit Media UDP | JA |
| 11434 | TCP | — | Ollama direkt | NEIN (via Nginx) |

---

## TLS / SSL Strategie

### Coolify mit Traefik (Server 1)

Coolify managed Traefik automatisch. Konfiguration über Coolify UI:

```
Coolify UI → Settings → Proxy → Traefik
→ Let's Encrypt E-Mail: deine@email.de
→ DNS Challenge: NEIN (HTTP Challenge reicht)
→ Wildcard: Optional, aber nicht nötig für Start
```

**Per Service in Coolify:**
```
Service → Domain → https://typebot.deine-domain.de
→ "Force HTTPS": aktiviert
→ Port: 3000
→ Proxy: enabled
```

Traefik generiert Zertifikat automatisch beim ersten Request.

### Wildcard-Zertifikat (optional, für sauberere Verwaltung)

Wenn Kunden eigene Subdomains bekommen sollen:
```
*.deine-domain.de → Wildcard Cert via DNS-01 Challenge
```
Benötigt DNS-Provider API Key (z.B. Hetzner DNS API).

---

## Subdomains Empfehlung

```
# Server 1:
coolify.deine-domain.de      → Coolify UI
n8n.deine-domain.de          → n8n Editor
builder.deine-domain.de      → Typebot Builder (Admin)
bot.deine-domain.de          → Typebot Viewer (Kunden-Chatbots)

# Server 2:
ollama.deine-domain.de       → Ollama API (gesichert)
voice.deine-domain.de        → LiveKit Server

# S3 (Hetzner managed):
storage.deine-domain.de      → Optional CNAME auf Hetzner S3
```

---

## Sicherheitszonen

```
ZONE 1 - Öffentlich (via Traefik):
  typebot-viewer, typebot-builder, n8n

ZONE 2 - Admin only (IP-Restriction in Traefik):
  coolify-ui, n8n (optional), ollama

ZONE 3 - Intern only (kein externer Zugriff):
  postgres:5432, redis (falls genutzt)

ZONE 4 - S3 (Hetzner managed, EU):
  Hetzner Object Storage fsn1/nbg1
```

### IP-Restriction für Admin-Services (Traefik Middleware):
```yaml
# In Coolify: Service → Advanced → Custom Labels:
- "traefik.http.middlewares.admin-ip.ipallowlist.sourcerange=DEINE.IP.ADRESSE/32"
- "traefik.http.routers.n8n.middlewares=admin-ip"
```
