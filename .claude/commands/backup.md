# /backup — Backup jetzt ausführen

Führe ein sofortiges Backup aller kritischen Daten aus.

## Was du tun sollst

1. Lade ENV-Variablen aus `.env`
2. Prüfe ob `aws` CLI installiert ist — falls nicht, weise darauf hin
3. Führe aus:
   ```bash
   source .env
   S3_ACCESS_KEY="$S3_ACCESS_KEY" \
   S3_SECRET_KEY="$S3_SECRET_KEY" \
   S3_ENDPOINT="$S3_ENDPOINT" \
   S3_BUCKET="${S3_BACKUP_BUCKET:-rag-backups}" \
   POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
   POSTGRES_CONTAINER="postgres-rag" \
   bash scripts/backup-postgres.sh
   ```
4. Zeige Ergebnis: Welche Files wurden gesichert, Größe, S3-Pfad
5. Frage ob Cron-Job eingerichtet werden soll (falls noch nicht vorhanden)

## Cron einrichten (wenn vom User gewünscht)

```bash
# Prüfen ob Cron bereits existiert:
crontab -l | grep backup-postgres

# Falls nicht: hinzufügen
(crontab -l 2>/dev/null; echo "0 2 * * * cd $(pwd) && source .env && bash scripts/backup-postgres.sh >> /var/log/backup-rag.log 2>&1") | crontab -
```
