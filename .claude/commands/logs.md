# /logs — Container-Logs anzeigen

Zeigt die Logs der wichtigsten Container an.

## Was du tun sollst

Frage den User welche Logs er sehen möchte, dann führe den passenden Befehl aus:

```bash
# Traefik/Proxy (SSL, Routing-Fehler):
docker logs coolify-proxy --tail=50 2>&1
# oder
docker logs traefik --tail=50 2>&1

# n8n (Workflow-Fehler, DB-Verbindung):
docker logs n8n --tail=50 2>&1

# Typebot Builder:
docker logs typebot-builder --tail=50 2>&1

# Typebot Viewer:
docker logs typebot-viewer --tail=50 2>&1

# PostgreSQL:
docker logs postgres-rag --tail=30 2>&1

# Alle kritischen Services auf einmal (letzte 20 Zeilen je):
for c in traefik coolify-proxy postgres-rag n8n typebot-builder typebot-viewer; do
    echo "=== $c ==="
    docker logs $c --tail=20 2>&1 || echo "(nicht gefunden)"
    echo ""
done
```

## Fehler-Analyse

Häufige Fehler und ihre Bedeutung:
- `certificate not found` → ACME/SSL gescheitert, DNS noch nicht propagiert
- `connection refused postgres` → Container-Name falsch oder Netz-Isolation
- `ECONNREFUSED` in n8n → Postgres-Host in ENV falsch
- `invalid_grant` in Typebot → NEXTAUTH_URL stimmt nicht mit Domain überein
- `502 Bad Gateway` in Traefik → App-Container down oder falscher Port
