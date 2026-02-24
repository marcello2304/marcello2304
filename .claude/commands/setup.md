# /setup — Vollständiges Platform-Setup

Führe das vollständige automatisierte Setup der Hetzner RAG Platform aus.

## Was du tun sollst

1. Führe zuerst `bash scripts/check-prerequisites.sh` aus und zeige die Ausgabe
2. Falls Fehler vorhanden sind, behebe sie interaktiv mit dem User bevor du weiter machst
3. Führe dann `bash setup.sh` aus
4. Überwache die Ausgabe und erkläre dem User jeden Schritt
5. Bei Fehlern: analysiere die Ursache und biete einen Fix an
6. Nach erfolgreichem Setup: zeige eine Zusammenfassung mit allen URLs und nächsten Schritten

## Nach dem Setup ausgeben

```
✓ PostgreSQL + pgvector läuft
✓ n8n läuft → https://n8n.DOMAIN
✓ Typebot Builder → https://builder.DOMAIN
✓ Typebot Viewer → https://bot.DOMAIN
✓ Test-Tenant angelegt

Nächste Schritte:
1. DNS A-Records prüfen (alle Subdomains → Server IP)
2. n8n Workflows importieren (n8n/ Ordner)
3. Ersten echten Kunden anlegen: /new-tenant
4. Backup-Cron einrichten
```
