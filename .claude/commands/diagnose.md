# /diagnose — Domain-Diagnose

Führe die vollständige Domain-Diagnose aus und analysiere die Ergebnisse.

## Was du tun sollst

1. Führe aus: `bash scripts/diagnose-domains.sh 2>&1 | tee diagnose-output.txt`
2. Analysiere die Ausgabe systematisch nach diesen Prioritäten:
   - DNS: Zeigen A-Records auf die richtige IP?
   - Firewall: Sind Ports 80/443 offen?
   - Docker: Laufen alle Container? Sind sie im coolify-Netz?
   - Traefik: Sind Labels korrekt? Ist Traefik registriert?
   - SSL: Ist das ACME-Zertifikat vorhanden?
   - ENV: Sind NEXTAUTH_URL, WEBHOOK_URL korrekt gesetzt?
3. Gib für jedes Problem einen **konkreten Fix-Befehl** an
4. Frage ob du den Fix direkt ausführen sollst
5. Nach dem Fix: verifiziere ob das Problem behoben ist

## Kritische Checks

```bash
# DNS von extern prüfen:
dig +short n8n.DOMAIN A
dig +short builder.DOMAIN A

# Traefik Router prüfen:
curl -s http://localhost:8080/api/http/routers | python3 -m json.tool

# Container im coolify-Netz:
docker network inspect coolify
```
