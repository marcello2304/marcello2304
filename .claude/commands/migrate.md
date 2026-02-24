# /migrate — SQL-Migrationen ausführen

Führt alle ausstehenden SQL-Migrationen gegen PostgreSQL aus.

## Was du tun sollst

1. Lade `POSTGRES_PASSWORD` aus `.env`
2. Prüfe ob PostgreSQL-Container läuft
3. Führe Migrationen **in dieser Reihenfolge** aus:

```bash
PG="postgres-rag"
PW=$(grep POSTGRES_PASSWORD .env | cut -d= -f2 | xargs)

# 001: Extensions (pgvector, uuid-ossp)
docker exec -e PGPASSWORD="$PW" $PG psql -U postgres -d app_db -f - < sql/001_extensions.sql

# 002: Public Schema (tenants, tenant_usage Tabellen)
docker exec -e PGPASSWORD="$PW" $PG psql -U postgres -d app_db -f - < sql/002_public_schema.sql

# 004: Funktionen (create_tenant, search_chunks, etc.)
docker exec -e PGPASSWORD="$PW" $PG psql -U postgres -d app_db -f - < sql/004_functions.sql

# 005: Rollen und Berechtigungen
docker exec -e PGPASSWORD="$PW" $PG psql -U postgres -d app_db -f - < sql/005_roles.sql
```

**Hinweis:** 003_tenant_template.sql ist nur Referenz — nicht ausführen!

4. Zeige was erfolgreich war / was übersprungen wurde (Migrationen sind idempotent)
5. Verifiziere danach:
   ```sql
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
   SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace;
   ```
