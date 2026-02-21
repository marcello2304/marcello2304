# E. Coolify Umsetzungsanleitung

## Dienste-Übersicht: Was wie deployen

| Service | Typ in Coolify | Zusammen oder getrennt? |
|---------|---------------|-------------------------|
| PostgreSQL | Database Resource | Getrennt (Coolify Database) |
| n8n | Application (Docker Image) | Getrennt |
| Typebot Builder | Application (Docker Image) | Getrennt |
| Typebot Viewer | Application (Docker Image) | Getrennt |
| Traefik | Coolify Proxy (Built-in) | Wird von Coolify verwaltet |

**Nicht in Coolify (Server 1):**
- Hetzner Object Storage → Managed Service, kein Docker nötig
- Redis → Optional, für n8n Queue Mode ab 50+ Kunden

---

## Schritt 1: Coolify Proxy konfigurieren

```
Coolify UI → Settings → Proxy
→ Proxy Type: Traefik v2 (Standard)
→ Redirect www → non-www: Nach Bedarf
→ Wildcard DNS: nicht nötig für Start
→ Let's Encrypt E-Mail: deine@email.de
→ "Restart Proxy" → Speichern
```

Verifizieren:
```bash
docker ps | grep coolify-proxy
docker logs coolify-proxy --tail=20
# Muss: "Traefik started" zeigen
```

---

## Schritt 2: PostgreSQL anlegen

```
Coolify UI → Resources → New Resource → Database → PostgreSQL
```

Konfiguration:
```
Name: postgres-rag
Version: 16-alpine (mit pgvector Schritt unten!)
Internal Port: 5432
Username: postgres
Password: <sicheres-passwort-32-zeichen>
Default Database: app_db
```

**pgvector installieren nach Deployment:**
```bash
# Auf Server 1:
docker exec -it <postgres-container-name> bash
# Im Container:
apt-get update && apt-get install -y postgresql-16-pgvector
# Dann in psql:
psql -U postgres -d app_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Besser: Eigenes PostgreSQL Image mit pgvector:**

In Coolify → PostgreSQL → Advanced → Custom Docker Image:
```
Image: pgvector/pgvector:pg16
```
Dieses Image enthält pgvector bereits. Empfohlen.

**Ports:**
```
Expose to Public: NEIN (nur intern im Docker-Netz)
```

**Volumes (Coolify erstellt automatisch):**
```
/data/coolify/databases/<name>/data → /var/lib/postgresql/data
```

---

## Schritt 3: n8n deployen

```
Coolify UI → Resources → New Resource → Application → Docker Image
```

Konfiguration:
```
Image: n8nio/n8n:latest
Name: n8n
Port: 5678
```

Domain:
```
Domain: https://n8n.deine-domain.de
Force HTTPS: ✓
Port: 5678
```

Volumes (manuell hinzufügen):
```
/data/coolify/volumes/n8n-data → /home/node/.n8n
```

Environment Variables (unter "Environment"):
```
N8N_HOST=n8n.deine-domain.de
N8N_PROTOCOL=https
N8N_PORT=5678
WEBHOOK_URL=https://n8n.deine-domain.de/
N8N_EDITOR_BASE_URL=https://n8n.deine-domain.de/
N8N_ENCRYPTION_KEY=<32-char-zufalls-string>
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=<postgres-service-name-in-coolify>
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_DATABASE=app_db
DB_POSTGRESDB_USER=postgres
DB_POSTGRESDB_PASSWORD=<db-passwort>
DB_POSTGRESDB_SCHEMA=n8n
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<sicheres-admin-passwort>
N8N_SECURE_COOKIE=true
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168
TZ=Europe/Berlin
```

**Wichtig:** Der Postgres-Hostname in n8n ist der Container-Name in Coolify.
Prüfen mit:
```bash
docker ps | grep postgres
# Container-Name z.B.: postgres-rag-xyz123
```

Dann in n8n ENV: `DB_POSTGRESDB_HOST=postgres-rag-xyz123`

Oder besser: Coolify verbindet Services automatisch wenn im gleichen Projekt.

---

## Schritt 4: Typebot Builder deployen

```
Coolify UI → Resources → New Resource → Application → Docker Image
Image: baptistearno/typebot-builder:latest
Name: typebot-builder
Port: 3000
```

Domain:
```
Domain: https://builder.deine-domain.de
Force HTTPS: ✓
Port: 3000
```

Environment Variables:
```
NEXTAUTH_URL=https://builder.deine-domain.de
NEXTAUTH_SECRET=<32-char-zufalls-string>
NEXT_PUBLIC_VIEWER_URL=https://bot.deine-domain.de
DATABASE_URL=postgresql://postgres:<passwort>@<postgres-host>:5432/typebot_db
ENCRYPTION_SECRET=<32-char-zufalls-string>
S3_ACCESS_KEY=<HETZNER_S3_ACCESS_KEY>
S3_SECRET_KEY=<HETZNER_S3_SECRET_KEY>
S3_BUCKET=rag-platform-prod
S3_REGION=eu-central-003
S3_ENDPOINT=https://fsn1.your-objectstorage.com
SMTP_HOST=<smtp>
SMTP_PORT=587
SMTP_AUTH_USER=<email>
SMTP_AUTH_PASS=<passwort>
NEXT_PUBLIC_SMTP_FROM=noreply@deine-domain.de
DISABLE_SIGNUP=true
TZ=Europe/Berlin
```

---

## Schritt 5: Typebot Viewer deployen

```
Coolify UI → Resources → New Resource → Application → Docker Image
Image: baptistearno/typebot-viewer:latest
Name: typebot-viewer
Port: 3000
```

Domain:
```
Domain: https://bot.deine-domain.de
Force HTTPS: ✓
Port: 3000
```

Environment Variables:
```
NEXTAUTH_URL=https://builder.deine-domain.de
NEXT_PUBLIC_VIEWER_URL=https://bot.deine-domain.de
DATABASE_URL=postgresql://postgres:<passwort>@<postgres-host>:5432/typebot_db
ENCRYPTION_SECRET=<gleicher-wert-wie-builder>
S3_ACCESS_KEY=<HETZNER_S3_ACCESS_KEY>
S3_SECRET_KEY=<HETZNER_S3_SECRET_KEY>
S3_BUCKET=rag-platform-prod
S3_REGION=eu-central-003
S3_ENDPOINT=https://fsn1.your-objectstorage.com
TZ=Europe/Berlin
```

---

## Schritt 6: Typebot DB anlegen

Einmalig nach Postgres-Deployment:
```bash
docker exec -it <postgres-container> psql -U postgres
```

```sql
CREATE DATABASE typebot_db;
CREATE USER typebot_user WITH PASSWORD '<passwort>';
GRANT ALL PRIVILEGES ON DATABASE typebot_db TO typebot_user;
\q
```

Typebot führt Migrationen beim Start automatisch aus.

---

## Schritt 7: Docker Networks sicherstellen

Coolify legt automatisch ein `coolify`-Netz an. Alle Services im gleichen Coolify-Projekt sind automatisch darin.

Manuell prüfen:
```bash
# Sind alle Services im coolify-Netz?
docker network inspect coolify | python3 -m json.tool | grep -A2 '"Name"'

# Falls ein Service fehlt:
docker network connect coolify <container-name>
```

**PostgreSQL darf KEINEN externen Port haben:**
```bash
docker port <postgres-container>
# Muss leer sein oder nur 127.0.0.1:5432
```

Falls Port 5432 offen ist → In Coolify: PostgreSQL → Ports → External Port entfernen.

---

## Healthchecks (sinnvoll ohne Fehlalarme)

### n8n Healthcheck
```
Type: HTTP
Path: /healthz
Port: 5678
Interval: 30s
Timeout: 10s
Retries: 3
Start Period: 60s  (n8n braucht Zeit zum Starten)
```

### Typebot Builder Healthcheck
```
Type: HTTP
Path: /api/health
Port: 3000
Interval: 30s
Timeout: 10s
Retries: 3
Start Period: 90s  (Next.js Build-Zeit)
```

### PostgreSQL Healthcheck
```
Type: Command
Command: pg_isready -U postgres
Interval: 15s
Timeout: 5s
Retries: 5
```

In Coolify unter Service → Advanced → Healthcheck konfigurierbar.

**Achtung:** Zu aggressive Healthchecks (kurze Timeouts, wenige Retries) killen Services beim Neustart. Start Period mind. 60-90s setzen.

---

## Coolify Updates (Services updaten)

```
Service → Deployments → "Force Rebuild" oder
Service → Image → "latest" → Deploy
```

Für zero-downtime (ab Pro-Plan oder manuell):
```bash
# Neues Image pullen, alter Container läuft noch:
docker pull baptistearno/typebot-builder:latest
# Dann in Coolify: Deploy auslösen
```

---

## IP-Restriction für Admin-Services

In Coolify → Service → Advanced → Custom Traefik Labels:

```
# n8n nur von deiner IP erreichbar:
traefik.http.middlewares.admin-only.ipallowlist.sourcerange=DEINE.IP.ADRESSE/32,<ZWEITE.IP>/32
traefik.http.routers.n8n.middlewares=admin-only
```

Ersetze `DEINE.IP.ADRESSE` mit deiner tatsächlichen IP.

---

## Secrets generieren (sicher, zufällig)

```bash
# 32-Zeichen zufällige Strings für NEXTAUTH_SECRET, etc.:
openssl rand -hex 32

# Oder:
cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
```

---

## Checkliste: Deployment Reihenfolge

```
[ ] 1. Coolify Proxy konfigurieren + Let's Encrypt E-Mail
[ ] 2. DNS A-Records setzen (alle Subdomains → Server 1 IP)
[ ] 3. PostgreSQL deployen (Image: pgvector/pgvector:pg16)
[ ] 4. pgvector Extension aktivieren
[ ] 5. Datenbanken anlegen (app_db, typebot_db)
[ ] 6. SQL Migrationen ausführen (001-005)
[ ] 7. n8n deployen + ENV setzen
[ ] 8. Typebot Builder deployen + ENV setzen
[ ] 9. Typebot Viewer deployen + ENV setzen
[ ] 10. Alle Services: Domain-Erreichbarkeit testen
[ ] 11. n8n: Credentials für Postgres + S3 + Ollama anlegen
[ ] 12. n8n: Ingestion + RAG Workflows importieren
[ ] 13. Test: Dokument hochladen + RAG-Query ausführen
```
