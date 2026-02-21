# F. Backup und Restore Plan

## Strategie-Übersicht

| Was | Methode | Frequenz | Aufbewahrung | Wo |
|-----|---------|----------|--------------|-----|
| PostgreSQL (alle DBs) | pg_dump (custom format) | Täglich 02:00 | 30 Tage | Hetzner S3 |
| PostgreSQL Tenant-Schema | pg_dump -n tenant_X | Täglich 03:00 | 90 Tage | Hetzner S3 |
| n8n Workflows + Credentials | n8n Export JSON | Täglich 04:00 | 60 Tage | Hetzner S3 |
| Typebot Bots | Typebot Export API | Täglich 04:30 | 60 Tage | Hetzner S3 |
| S3 Tenant-Dateien | Hetzner S3 Versioning | Kontinuierlich | 30 Tage Versionen | Hetzner S3 (anderer Bucket) |
| Docker Volumes | rsync snapshot | Täglich | 7 Tage | Lokales Backup-Verzeichnis |
| Server Snapshot | Hetzner Console | Wöchentlich | 4 Snapshots | Hetzner |

---

## PostgreSQL Backup

### Backup-Script

```bash
#!/bin/bash
# /opt/backup/backup-postgres.sh

set -euo pipefail

BACKUP_DIR="/opt/backups/postgres"
S3_BUCKET="rag-backups"
S3_ENDPOINT="https://fsn1.your-objectstorage.com"
S3_ACCESS_KEY="${S3_ACCESS_KEY}"
S3_SECRET_KEY="${S3_SECRET_KEY}"
DATE=$(date +%Y-%m-%d_%H-%M)
POSTGRES_CONTAINER="postgres-rag"  # Container-Name anpassen
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD}"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# Vollständiger Dump aller Datenbanken
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    pg_dumpall -U "$POSTGRES_USER" \
    | gzip > "$BACKUP_DIR/all_databases_${DATE}.sql.gz"

# Einzelne DBs für schnelleres Restore
for DB in app_db typebot_db; do
    docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
        pg_dump -U "$POSTGRES_USER" -Fc \
        --no-password "$DB" \
        > "$BACKUP_DIR/${DB}_${DATE}.dump"
done

# Upload zu S3
export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"

aws --endpoint-url="$S3_ENDPOINT" s3 cp \
    "$BACKUP_DIR/all_databases_${DATE}.sql.gz" \
    "s3://$S3_BUCKET/postgres/daily/all_databases_${DATE}.sql.gz"

for DB in app_db typebot_db; do
    aws --endpoint-url="$S3_ENDPOINT" s3 cp \
        "$BACKUP_DIR/${DB}_${DATE}.dump" \
        "s3://$S3_BUCKET/postgres/daily/${DB}_${DATE}.dump"
done

# Tenant-Schemas einzeln sichern
TENANTS=$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    psql -U "$POSTGRES_USER" -d app_db -t -c \
    "SELECT schema_name FROM public.tenants WHERE status='active';")

for SCHEMA in $TENANTS; do
    SCHEMA=$(echo "$SCHEMA" | xargs)
    if [ -n "$SCHEMA" ]; then
        docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
            pg_dump -U "$POSTGRES_USER" -Fc \
            --schema="$SCHEMA" app_db \
            > "$BACKUP_DIR/tenant_${SCHEMA}_${DATE}.dump"

        aws --endpoint-url="$S3_ENDPOINT" s3 cp \
            "$BACKUP_DIR/tenant_${SCHEMA}_${DATE}.dump" \
            "s3://$S3_BUCKET/postgres/tenants/${SCHEMA}/${DATE}.dump"
    fi
done

# Lokale Backups bereinigen (älter als 3 Tage lokal halten)
find "$BACKUP_DIR" -name "*.dump" -mtime +3 -delete
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +3 -delete

# S3 alte Backups löschen (älter als RETENTION_DAYS)
aws --endpoint-url="$S3_ENDPOINT" s3 ls \
    "s3://$S3_BUCKET/postgres/daily/" \
    | awk '{print $4}' \
    | while read FILE; do
        FILE_DATE=$(echo "$FILE" | grep -oP '\d{4}-\d{2}-\d{2}' | head -1)
        if [ -n "$FILE_DATE" ]; then
            DIFF=$(( ($(date +%s) - $(date -d "$FILE_DATE" +%s)) / 86400 ))
            if [ "$DIFF" -gt "$RETENTION_DAYS" ]; then
                aws --endpoint-url="$S3_ENDPOINT" s3 rm \
                    "s3://$S3_BUCKET/postgres/daily/$FILE"
            fi
        fi
    done

echo "Backup abgeschlossen: $DATE"
```

### Cron-Job einrichten (auf Server 1)

```bash
crontab -e

# Täglich 02:00 Uhr (Server-Zeit)
0 2 * * * S3_ACCESS_KEY=<key> S3_SECRET_KEY=<secret> POSTGRES_PASSWORD=<pw> /opt/backup/backup-postgres.sh >> /var/log/backup-postgres.log 2>&1
```

---

## n8n Workflows Backup

```bash
#!/bin/bash
# /opt/backup/backup-n8n.sh

DATE=$(date +%Y-%m-%d_%H-%M)
N8N_CONTAINER="n8n"
BACKUP_DIR="/opt/backups/n8n"
S3_BUCKET="rag-backups"
S3_ENDPOINT="https://fsn1.your-objectstorage.com"

mkdir -p "$BACKUP_DIR"

# Workflows exportieren
docker exec "$N8N_CONTAINER" n8n export:workflow --all \
    --output=/home/node/.n8n/workflows_backup.json

docker cp "$N8N_CONTAINER:/home/node/.n8n/workflows_backup.json" \
    "$BACKUP_DIR/workflows_${DATE}.json"

# Credentials (nur Metadaten, keine Secrets — die sind verschlüsselt)
docker exec "$N8N_CONTAINER" n8n export:credentials --all \
    --output=/home/node/.n8n/credentials_backup.json

docker cp "$N8N_CONTAINER:/home/node/.n8n/credentials_backup.json" \
    "$BACKUP_DIR/credentials_${DATE}.json"

# Upload zu S3
aws --endpoint-url="$S3_ENDPOINT" s3 cp \
    "$BACKUP_DIR/workflows_${DATE}.json" \
    "s3://$S3_BUCKET/n8n/workflows_${DATE}.json"

aws --endpoint-url="$S3_ENDPOINT" s3 cp \
    "$BACKUP_DIR/credentials_${DATE}.json" \
    "s3://$S3_BUCKET/n8n/credentials_${DATE}.json"

find "$BACKUP_DIR" -mtime +7 -delete
```

---

## Restore Plan

### PostgreSQL: Einzelne DB restoren

```bash
# Neueste Backup-Datei von S3 herunterladen:
aws --endpoint-url="$S3_ENDPOINT" s3 ls s3://rag-backups/postgres/daily/ \
    | sort | tail -5

# Datei herunterladen:
aws --endpoint-url="$S3_ENDPOINT" s3 cp \
    s3://rag-backups/postgres/daily/app_db_2024-11-15_02-00.dump \
    /tmp/restore_app_db.dump

# DB droppen (ACHTUNG: Datenverlust!) und neu erstellen:
docker exec -it postgres-rag psql -U postgres -c "DROP DATABASE IF EXISTS app_db;"
docker exec -it postgres-rag psql -U postgres -c "CREATE DATABASE app_db;"

# Restore:
docker exec -i postgres-rag pg_restore \
    -U postgres -d app_db \
    --no-owner --no-privileges \
    < /tmp/restore_app_db.dump

echo "Restore abgeschlossen"
```

### PostgreSQL: Einzelnen Tenant restoren

```bash
# Tenant-Backup von S3:
aws --endpoint-url="$S3_ENDPOINT" s3 cp \
    s3://rag-backups/postgres/tenants/tenant_acme/2024-11-15_02-00.dump \
    /tmp/restore_tenant_acme.dump

# Schema droppen und neu erstellen:
docker exec -it postgres-rag psql -U postgres -d app_db \
    -c "DROP SCHEMA IF EXISTS tenant_acme CASCADE;"

# Restore nur dieses Schema:
docker exec -i postgres-rag pg_restore \
    -U postgres -d app_db \
    --no-owner --no-privileges \
    < /tmp/restore_tenant_acme.dump

# Berechtigungen neu vergeben:
docker exec -it postgres-rag psql -U postgres -d app_db \
    -c "SELECT public.grant_tenant_permissions('tenant_acme');"
```

### n8n Workflows restoren

```bash
# Backup herunterladen:
aws --endpoint-url="$S3_ENDPOINT" s3 cp \
    s3://rag-backups/n8n/workflows_2024-11-15_02-00.json \
    /tmp/workflows_restore.json

# In n8n Container kopieren:
docker cp /tmp/workflows_restore.json n8n:/home/node/.n8n/workflows_import.json

# Importieren:
docker exec n8n n8n import:workflow \
    --input=/home/node/.n8n/workflows_import.json

echo "Workflows importiert — manuell in n8n UI aktivieren!"
```

---

## S3 Tenant-Dateien Backup

### Hetzner S3 Versioning aktivieren

```bash
# Versioning einschalten (einmalig):
aws --endpoint-url="$S3_ENDPOINT" s3api put-bucket-versioning \
    --bucket rag-platform-prod \
    --versioning-configuration Status=Enabled
```

### Cross-Bucket Replikation (für Disaster Recovery)

```bash
# Backup-Bucket in anderem Hetzner Standort:
# fsn1 (primary) → nbg1 (backup)

# Sync täglich:
aws --endpoint-url="$S3_ENDPOINT" s3 sync \
    s3://rag-platform-prod \
    s3://rag-platform-backup \
    --endpoint-url="https://nbg1.your-objectstorage.com"
```

---

## Hetzner Server Snapshots

```
Hetzner Console → Server → Snapshots → Create Snapshot
→ Wöchentlich (Sonntag Nacht)
→ Max 4 Snapshots behalten (automatisch rotieren)
→ Snapshot-Name: server1-<datum>
```

Snapshots decken den gesamten Serverzustand ab — schnellste Recover-Methode bei Totalausfall.

---

## Backup-Monitoring und Alerting

### Backup-Status prüfen (in n8n als täglicher Workflow)

```javascript
// n8n Code-Node: Backup Check
const yesterday = new Date();
yesterday.setDate(yesterday.getDate() - 1);
const dateStr = yesterday.toISOString().split('T')[0];

// AWS CLI im Bash-Node oder HTTP Request zu S3 List
// Prüfe ob Backup von gestern vorhanden
const expectedFiles = [
    `postgres/daily/app_db_${dateStr}`,
    `postgres/daily/typebot_db_${dateStr}`,
    `n8n/workflows_${dateStr}`
];

// Falls Datei fehlt → Slack/Email Alert über n8n
```

### Restore-Tests (monatlich)

```bash
# Teste Restore auf separatem Container:
docker run -d --name postgres-test \
    -e POSTGRES_PASSWORD=test \
    pgvector/pgvector:pg16

# Restore einspielen:
docker exec -i postgres-test pg_restore \
    -U postgres -d postgres \
    < /tmp/latest_backup.dump

# Prüfen:
docker exec postgres-test psql -U postgres \
    -c "SELECT COUNT(*) FROM tenant_acme.chunks;"

# Aufräumen:
docker stop postgres-test && docker rm postgres-test
```

---

## Wichtige Backup-Dateipfade

```
/opt/backups/
  postgres/     ← Lokale Postgres-Dumps (3 Tage)
  n8n/          ← n8n Workflow-Exports (7 Tage)

Hetzner S3 (rag-backups Bucket):
  postgres/
    daily/      ← Tägliche Gesamtdumps (30 Tage)
    tenants/    ← Tenant-Schemas einzeln (90 Tage)
  n8n/          ← Workflow-Backups (60 Tage)
  typebot/      ← Bot-Exports (60 Tage)

Hetzner S3 (rag-platform-prod):
  tenants/      ← Produktiv-Dateien (mit Versioning)

Hetzner S3 (rag-platform-backup):
  tenants/      ← Replikation von prod (Disaster Recovery)

Hetzner Snapshots:
  server1-*     ← Server-Snapshots (4 wöchentliche)
```
