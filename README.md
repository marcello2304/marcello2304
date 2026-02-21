# Hetzner RAG Platform — Self-Hosted Stack

Multi-Tenant RAG (Retrieval-Augmented Generation) Platform auf Hetzner,
betrieben mit Coolify, PostgreSQL + pgvector, n8n, Typebot, Ollama und LiveKit.

## Struktur

```
docs/
  A-domain-diagnosis.md      — Diagnose: Domains nicht erreichbar
  B-architecture.md          — Zielarchitektur + Netzwerkplan
  C-tenant-rag-design.md     — Multi-Tenant RAG Design + SQL Schema
  D-ingestion-workflow.md    — n8n Ingestion + S3 Struktur
  E-coolify-setup.md         — Coolify Schritt-für-Schritt Anleitung
  F-backup-restore.md        — Backup + Restore Plan
  G-scaling-roadmap.md       — Skalierungs-Roadmap (10 → 200+ Kunden)

sql/
  001_extensions.sql         — pgvector, uuid-ossp
  002_public_schema.sql      — Tenant-Verwaltungstabellen
  003_tenant_template.sql    — Schema-Template (Referenz)
  004_functions.sql          — create_tenant(), search_chunks(), etc.
  005_roles.sql              — DB-Rollen + Berechtigungen

scripts/
  diagnose-domains.sh        — Vollständige Domain-Diagnose ausführen
  backup-postgres.sh         — PostgreSQL zu Hetzner S3 sichern
  create-tenant.sh           — Neuen Tenant anlegen

docker/
  compose-server1.yml        — Server 1: Traefik, Postgres, n8n, Typebot
  compose-server2.yml        — Server 2: Ollama, LiveKit, Nginx
  nginx-server2.conf         — Nginx Reverse Proxy Konfiguration
  livekit.yaml               — LiveKit Server Konfiguration

n8n/
  rag-ingestion-workflow.json — Dokument hochladen + indexieren
  rag-query-workflow.json     — RAG-Query von Typebot beantworten

coolify/env-templates/
  server1.env.example        — ENV Variablen Server 1 (Vorlage)
  server2.env.example        — ENV Variablen Server 2 (Vorlage)
```

## Schnellstart: Domain-Diagnose

```bash
# Auf Server 1 ausführen:
bash scripts/diagnose-domains.sh 2>&1 | tee diagnose-output.txt
```

## Schnellstart: Tenant anlegen

```bash
POSTGRES_CONTAINER=postgres-rag \
POSTGRES_PASSWORD=<passwort> \
bash scripts/create-tenant.sh acme "ACME GmbH" admin@acme.de starter
```

## Schnellstart: SQL Migrationen

```bash
# Auf Server 1:
docker exec -i postgres-rag psql -U postgres -d app_db < sql/001_extensions.sql
docker exec -i postgres-rag psql -U postgres -d app_db < sql/002_public_schema.sql
docker exec -i postgres-rag psql -U postgres -d app_db < sql/004_functions.sql
docker exec -i postgres-rag psql -U postgres -d app_db < sql/005_roles.sql
```

## Architektur-Übersicht

```
Server 1 (94.130.170.167):
  Traefik → n8n, Typebot Builder, Typebot Viewer
  PostgreSQL + pgvector (intern)
  → Hetzner Object Storage (S3-API)

Server 2 (<SERVER2_IP>):
  Nginx → Ollama (gesichert)
  LiveKit Server + Agent
  → Ollama LLM lokal
```

## Tenant-Strategie: Schema-per-Tenant

Jeder Kunde bekommt ein eigenes PostgreSQL-Schema (`tenant_<slug>`).
Klare Datentrennung, effiziente Vektorsearch, skalierbar bis 100+ Kunden.

Dokumente und Medien liegen in Hetzner S3 unter `tenants/<slug>/`.

## Skalierung

| Phase | Kunden | Trigger |
|-------|--------|---------|
| 1 | 0-20 | — |
| 2 | 20-50 | RAM > 8 GB oder Latenz > 2s |
| 3 | 50-100 | RAG DB > 100 GB |
| 4 | 100-200+ | RAG DB > 500 GB |

Details: [docs/G-scaling-roadmap.md](docs/G-scaling-roadmap.md)

---

**DSGVO:** Alle Daten bleiben in Hetzner EU (fsn1/nbg1). Kein Datenabfluss zu externen LLM-APIs durch Ollama-Nutzung.
