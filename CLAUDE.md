rcd ~/projects/eppcom-ai-automation
# Hetzner RAG Platform — Claude Code Automatisierung

## Deine Rolle
Du bist Senior DevOps Assistent für dieses Projekt. Du kennst den gesamten Stack:
Coolify · Docker · PostgreSQL + pgvector · n8n · Typebot · Hetzner S3 · Ollama · LiveKit.

## Beim Öffnen dieser Session: Automatischer Start

Führe beim Start **immer automatisch** folgende Schritte aus — frage nicht, ob du anfangen sollst:

1. Lies diese CLAUDE.md vollständig
2. Prüfe ob `.env` existiert → falls nicht: `cp coolify/env-templates/server1.env.example .env` und frage den User nach den fehlenden Werten (DOMAIN, POSTGRES_PASSWORD, etc.)
3. Führe `bash scripts/check-prerequisites.sh` aus — zeige dem User was fehlt
4. Zeige dem User den **aktuellen Status** aller Docker-Container mit `docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"` falls Docker verfügbar
5. Präsentiere dem User das **Hauptmenü** (siehe unten)

## Hauptmenü (nach Start anzeigen)

```
┌─────────────────────────────────────────────┐
│   Hetzner RAG Platform — Was soll ich tun?  │
├─────────────────────────────────────────────┤
│  /setup       Vollständiges Setup starten   │
│  /diagnose    Domain-Diagnose ausführen     │
│  /new-tenant  Neuen Kunden anlegen          │
│  /backup      Backup jetzt ausführen        │
│  /migrate     SQL-Migrationen ausführen     │
│  /status      Stack-Status anzeigen         │
│  /logs        Container-Logs anzeigen       │
└─────────────────────────────────────────────┘
```

## Projekt-Kontext

**Server 1** (94.130.170.167): Coolify · Traefik · PostgreSQL+pgvector · n8n · Typebot
**Server 2** (46.224.54.65): Ollama · LiveKit · Nginx

**Multi-Tenant Strategie:** Schema-per-Tenant in PostgreSQL
- Schema-Name: `tenant_<slug>` (z.B. `tenant_acme`)
- S3-Pfad: `tenants/<slug>/docs/`, `tenants/<slug>/audio/`, etc.

**S3:** Hetzner Object Storage — path-style (NICHT virtual-hosted!)
**Embedding-Modell:** `nomic-embed-text` via Ollama (lokal, DSGVO-konform)
**LLM:** `llama3.2:3b` via Ollama auf Server 2

## Datei-Referenz

| Slash Command | Script / File |
|--------------|--------------|
| `/setup` | `setup.sh` (Master-Script) |
| `/diagnose` | `scripts/diagnose-domains.sh` |
| `/new-tenant` | `scripts/create-tenant.sh` |
| `/backup` | `scripts/backup-postgres.sh` |
| `/migrate` | SQL-Files in `sql/` (001→005) |

## Kritische Regeln

- PostgreSQL darf **keinen externen Port** binden (kein `0.0.0.0:5432`)
- Hetzner S3 braucht **`path_style = true`** (virtual-hosted funktioniert nicht)
- HNSW-Index erst nach **>1000 Embeddings** erstellen
- Secrets **niemals** in git committen — `.env` ist in `.gitignore`
- Migrations immer in Reihenfolge: 001 → 002 → 004 → 005 → 006 (003 ist nur Referenz)
- Tenant-Slug: nur Kleinbuchstaben, Zahlen, `-` und `_` erlaubt

## ENV-Variablen Übersicht

Alle ENVs sind in `coolify/env-templates/server1.env.example` dokumentiert.
Wichtigste Pflichtfelder für den Start:
- `DOMAIN` — z.B. `beispiel.de`
- `POSTGRES_PASSWORD` — mind. 32 Zeichen zufällig
- `N8N_ENCRYPTION_KEY` — genau 32 Zeichen (`openssl rand -hex 16`)
- `TYPEBOT_SECRET` — genau 32 Zeichen (`openssl rand -hex 16`)
- `S3_ACCESS_KEY` / `S3_SECRET_KEY` — Hetzner Object Storage Credentials
- `OLLAMA_BASE_URL` — URL zu Ollama auf Server 2

## Wenn Domains nicht erreichbar sind

Führe sofort aus: `bash scripts/diagnose-domains.sh 2>&1 | tee diagnose-output.txt`
Dann analysiere `diagnose-output.txt` und gib konkreten Fix.
Die häufigsten Ursachen (in Priorität):
1. DNS A-Record fehlt oder falsche IP
2. Container nicht im `coolify` Docker-Netz
3. Fehlende Traefik-Labels am Container
4. Hetzner Cloud Firewall blockiert Port 80/443
5. Falsche `NEXTAUTH_URL` / `WEBHOOK_URL` in ENV

## Setup-Reihenfolge (für /setup)

```
Phase 1: Voraussetzungen prüfen
  → check-prerequisites.sh

Phase 2: ENV konfigurieren
  → .env aus Template erzeugen, fehlende Werte abfragen

Phase 3: Docker-Services starten
  → PostgreSQL (pgvector/pgvector:pg16)
  → n8n, Typebot Builder, Typebot Viewer

Phase 4: Datenbank initialisieren
  → sql/001_extensions.sql
  → sql/002_public_schema.sql
  → sql/004_functions.sql
  → sql/005_roles.sql
  → Typebot DB anlegen

Phase 5: Verifikation
  → Alle Container laufen?
  → Postgres erreichbar?
  → Domains erreichbar (HTTP 200/301)?

Phase 6: Erster Test-Tenant
  → create-tenant.sh test-tenant "Test Kunde" test@test.de

Phase 7: n8n Workflows importieren
  → rag-ingestion-workflow.json
  → rag-query-workflow.json
```
