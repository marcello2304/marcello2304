# /status — Stack-Status anzeigen

Zeige den vollständigen Status aller Platform-Komponenten.

## Was du tun sollst

Führe folgende Befehle aus und präsentiere die Ergebnisse übersichtlich:

```bash
# 1. Container-Status
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 2. Container Health + Restarts
docker inspect --format='{{.Name}} | Restarts: {{.RestartCount}} | Health: {{.State.Health.Status}}' \
    $(docker ps -aq) 2>/dev/null | sed 's/\///' | grep -E "postgres|n8n|typebot|traefik"

# 3. Postgres Tenants
docker exec -e PGPASSWORD=$(grep POSTGRES_PASSWORD .env | cut -d= -f2) postgres-rag \
    psql -U postgres -d app_db -c \
    "SELECT slug, name, plan, status, created_at FROM public.tenants ORDER BY created_at;"

# 4. Tenant-Statistiken
docker exec -e PGPASSWORD=$(grep POSTGRES_PASSWORD .env | cut -d= -f2) postgres-rag \
    psql -U postgres -d app_db -c \
    "SELECT * FROM public.get_tenant_stats(slug) FROM public.tenants WHERE status='active';" 2>/dev/null || true

# 5. Disk-Nutzung
docker system df

# 6. Port-Status
ss -tlnp | grep -E ":80|:443|:5432"
```

## Ausgabe-Format

Präsentiere als übersichtliche Tabelle mit Ampel-Status:
- 🟢 Running + healthy
- 🟡 Running + unhealthy / Restarts > 5
- 🔴 Stopped / Exited
