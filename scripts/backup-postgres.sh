#!/bin/bash
# backup-postgres.sh — PostgreSQL Backup zu Hetzner S3
# Cron: 0 2 * * * /opt/backup/backup-postgres.sh >> /var/log/backup-postgres.log 2>&1
#
# Benötigte ENV-Variablen (in Cron oder .env Datei setzen):
#   S3_ACCESS_KEY, S3_SECRET_KEY, POSTGRES_PASSWORD, S3_ENDPOINT, S3_BUCKET

set -euo pipefail

# Konfiguration
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/postgres}"
S3_BUCKET="${S3_BUCKET:-rag-backups}"
S3_ENDPOINT="${S3_ENDPOINT:-https://fsn1.your-objectstorage.com}"
S3_REGION="${S3_REGION:-eu-central-003}"
DATE=$(date +%Y-%m-%d_%H-%M)
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres-rag}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD nicht gesetzt}"
S3_ACCESS_KEY="${S3_ACCESS_KEY:?S3_ACCESS_KEY nicht gesetzt}"
S3_SECRET_KEY="${S3_SECRET_KEY:?S3_SECRET_KEY nicht gesetzt}"
LOCAL_RETENTION_DAYS=3
S3_RETENTION_DAYS=30
TENANT_RETENTION_DAYS=90

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"; }

log "Backup gestartet"
mkdir -p "$BACKUP_DIR"

# aws CLI verfügbar?
if ! command -v aws &>/dev/null; then
    log "FEHLER: aws CLI nicht installiert. Installieren mit: pip3 install awscli"
    exit 1
fi

export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
export AWS_DEFAULT_REGION="$S3_REGION"

aws_s3() {
    aws --endpoint-url="$S3_ENDPOINT" s3 "$@"
}

# Container läuft?
if ! docker ps --filter "name=$POSTGRES_CONTAINER" --quiet | grep -q .; then
    log "FEHLER: Container $POSTGRES_CONTAINER nicht gefunden oder nicht running"
    exit 1
fi

# --- 1. Vollständiger Dump aller Datenbanken ---
log "Dumpe alle Datenbanken..."
docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$POSTGRES_CONTAINER" \
    pg_dumpall -U "$POSTGRES_USER" \
    | gzip > "$BACKUP_DIR/all_databases_${DATE}.sql.gz"

log "Upload all_databases zu S3..."
aws_s3 cp \
    "$BACKUP_DIR/all_databases_${DATE}.sql.gz" \
    "s3://$S3_BUCKET/postgres/daily/all_databases_${DATE}.sql.gz"

# --- 2. Einzelne App-Datenbanken ---
for DB in app_db typebot_db; do
    # Prüfe ob DB existiert
    DB_EXISTS=$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
        psql -U "$POSTGRES_USER" -t -c \
        "SELECT 1 FROM pg_database WHERE datname='$DB';" 2>/dev/null | xargs)

    if [ "$DB_EXISTS" = "1" ]; then
        log "Dumpe Datenbank: $DB"
        docker exec \
            -e PGPASSWORD="$POSTGRES_PASSWORD" \
            "$POSTGRES_CONTAINER" \
            pg_dump -U "$POSTGRES_USER" -Fc "$DB" \
            > "$BACKUP_DIR/${DB}_${DATE}.dump"

        log "Upload $DB zu S3..."
        aws_s3 cp \
            "$BACKUP_DIR/${DB}_${DATE}.dump" \
            "s3://$S3_BUCKET/postgres/daily/${DB}_${DATE}.dump"
    else
        log "SKIP: Datenbank $DB existiert nicht"
    fi
done

# --- 3. Tenant-Schemas einzeln ---
log "Dumpe Tenant-Schemas..."
TENANTS=$(docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$POSTGRES_CONTAINER" \
    psql -U "$POSTGRES_USER" -d app_db -t -c \
    "SELECT schema_name FROM public.tenants WHERE status='active';" 2>/dev/null || echo "")

if [ -n "$TENANTS" ]; then
    for SCHEMA in $TENANTS; do
        SCHEMA=$(echo "$SCHEMA" | xargs)
        if [ -z "$SCHEMA" ] || [ "$SCHEMA" = "|" ]; then continue; fi

        log "Dumpe Tenant-Schema: $SCHEMA"
        docker exec \
            -e PGPASSWORD="$POSTGRES_PASSWORD" \
            "$POSTGRES_CONTAINER" \
            pg_dump -U "$POSTGRES_USER" -Fc \
            --schema="$SCHEMA" app_db \
            > "$BACKUP_DIR/tenant_${SCHEMA}_${DATE}.dump"

        aws_s3 cp \
            "$BACKUP_DIR/tenant_${SCHEMA}_${DATE}.dump" \
            "s3://$S3_BUCKET/postgres/tenants/$SCHEMA/${DATE}.dump"
    done
else
    log "Keine aktiven Tenants gefunden (erste Einrichtung?)"
fi

# --- 4. Lokale Bereinigung ---
log "Bereinige lokale Backups älter als $LOCAL_RETENTION_DAYS Tage..."
find "$BACKUP_DIR" -name "*.dump" -mtime +"$LOCAL_RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$LOCAL_RETENTION_DAYS" -delete

# --- 5. S3 Bereinigung (Daily Backups) ---
log "Bereinige S3 Daily-Backups älter als $S3_RETENTION_DAYS Tage..."
aws_s3 ls "s3://$S3_BUCKET/postgres/daily/" 2>/dev/null \
    | awk '{print $4}' \
    | while read -r FILE; do
        FILE_DATE=$(echo "$FILE" | grep -oP '\d{4}-\d{2}-\d{2}' | head -1 || true)
        if [ -n "$FILE_DATE" ]; then
            DIFF=$(( ($(date +%s) - $(date -d "$FILE_DATE" +%s 2>/dev/null || echo 0)) / 86400 ))
            if [ "$DIFF" -gt "$S3_RETENTION_DAYS" ]; then
                log "Lösche altes S3-Backup: $FILE (Alter: ${DIFF}d)"
                aws_s3 rm "s3://$S3_BUCKET/postgres/daily/$FILE"
            fi
        fi
    done

# --- 6. Status prüfen ---
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
S3_COUNT=$(aws_s3 ls "s3://$S3_BUCKET/postgres/daily/" 2>/dev/null | wc -l || echo "?")

log "Backup abgeschlossen"
log "Lokale Backup-Größe: $BACKUP_SIZE"
log "S3 Daily-Backups vorhanden: $S3_COUNT"
log "S3-Pfad: s3://$S3_BUCKET/postgres/daily/"
