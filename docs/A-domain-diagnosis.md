# A. Sofort-Diagnose: Domains nicht erreichbar

## Hypothesen (Priorität nach Häufigkeit)

1. **DNS A-Record fehlt oder zeigt auf falsche IP** — häufigster Fehler
2. **Traefik (Coolify) hat den Container nicht registriert** — Labels fehlen oder falsch
3. **Firewall blockiert Port 80/443** — ufw oder Hetzner Firewall Regel fehlt
4. **SSL-Zertifikat schlägt fehl** — ACME Challenge blockiert, falsche E-Mail, Rate Limit
5. **Container läuft nicht oder ist unhealthy** — Postgres Abhängigkeit, ENV Fehler
6. **Docker Network Isolation** — Container nicht im gleichen Coolify-Netz wie Traefik
7. **Falsche BASE_URL in Typebot/n8n** — Loop oder Redirect auf falschen Host
8. **Port 443 durch anderen Prozess belegt** — selten, aber möglich

---

## Checkliste: Schritt für Schritt auf Server 1 (94.130.170.167)

### SCHRITT 1: DNS prüfen

```bash
# Von extern (deinem Laptop oder einem anderen Server):
dig +short typebot.deine-domain.de A
dig +short n8n.deine-domain.de A
# Muss 94.130.170.167 zurückgeben.

# Alternativ mit nslookup:
nslookup typebot.deine-domain.de 8.8.8.8
nslookup n8n.deine-domain.de 8.8.8.8

# TTL prüfen — wenn zu hoch, warte auf Propagation:
dig typebot.deine-domain.de +ttl | grep -i ttl
```

**Erwartetes Ergebnis:** `94.130.170.167`
**Bei Fehler:** DNS A-Record beim Registrar/Hetzner DNS setzen:
```
Typ: A
Name: typebot    (oder @, n8n, etc.)
Wert: 94.130.170.167
TTL: 300
```

---

### SCHRITT 2: Firewall prüfen (auf Server 1)

```bash
# ufw Status:
ufw status verbose

# Falls nftables:
nft list ruleset | grep -E "80|443|22"

# Hetzner Cloud Firewall — muss im Hetzner Panel geprüft werden,
# da diese VOR ufw greift. Prüfe:
# Hetzner Console > Firewall > Inbound Rules:
# TCP 80  (HTTP)  — Quelle: 0.0.0.0/0
# TCP 443 (HTTPS) — Quelle: 0.0.0.0/0
# TCP 22  (SSH)   — Quelle: deine IP

# Schnelltest von extern:
curl -v --max-time 5 http://94.130.170.167/
# Wenn Connection refused → Port 80 geblockt oder Traefik down
# Wenn Timeout → Hetzner Cloud Firewall blockiert
```

**Fix falls ufw:**
```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw reload
```

---

### SCHRITT 3: Traefik / Coolify Proxy prüfen

```bash
# Traefik Container läuft?
docker ps | grep traefik

# Falls Coolify eigenen Proxy nutzt:
docker ps | grep coolify-proxy

# Traefik Logs (letzte 100 Zeilen):
docker logs coolify-proxy --tail=100 2>&1

# Oder falls Traefik direkt:
docker logs traefik --tail=100 2>&1

# Traefik Dashboard erreichbar? (nur lokal, da Dashboard meist intern)
curl -s http://localhost:8080/api/rawdata | python3 -m json.tool | head -100
# oder
curl -s http://localhost:8080/api/http/routers | python3 -m json.tool

# Welche Router hat Traefik registriert?
docker exec coolify-proxy traefik version 2>/dev/null || true
curl -s http://localhost:8080/api/http/routers 2>/dev/null | python3 -m json.tool | grep -E "name|rule|service"
```

**Kritische Prüfung: Labels der Container:**
```bash
# Typebot Labels prüfen:
docker inspect $(docker ps -q --filter "name=typebot") | python3 -m json.tool | grep -A2 -i "traefik"

# n8n Labels prüfen:
docker inspect $(docker ps -q --filter "name=n8n") | python3 -m json.tool | grep -A2 -i "traefik"
```

**Minimum Labels die ein Container braucht:**
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.typebot.rule=Host(`typebot.deine-domain.de`)"
  - "traefik.http.routers.typebot.entrypoints=websecure"
  - "traefik.http.routers.typebot.tls.certresolver=letsencrypt"
  - "traefik.http.services.typebot.loadbalancer.server.port=3000"
```

---

### SCHRITT 4: Container Status prüfen

```bash
# Alle laufenden Container:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Alle Container inkl. gestoppte:
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Typebot Logs:
docker logs $(docker ps -aq --filter "name=typebot") --tail=50 2>&1

# n8n Logs:
docker logs $(docker ps -aq --filter "name=n8n") --tail=50 2>&1

# Postgres Logs:
docker logs $(docker ps -aq --filter "name=postgres") --tail=50 2>&1

# Container restart-Count — häufige Restarts = Crash Loop:
docker inspect --format='{{.Name}} Restarts:{{.RestartCount}}' $(docker ps -aq)
```

---

### SCHRITT 5: Docker Networks prüfen

```bash
# Alle Netzwerke:
docker network ls

# Coolify Netzwerk (meist 'coolify' oder 'proxy'):
docker network inspect coolify 2>/dev/null || docker network inspect proxy 2>/dev/null

# Ist Traefik im gleichen Netz wie die App-Container?
docker inspect coolify-proxy | python3 -m json.tool | grep -A 20 "Networks"

# Ist Typebot im Coolify Netz?
docker inspect $(docker ps -q --filter "name=typebot") | python3 -m json.tool | grep -A 5 "Networks"

# Kurzcheck: Welche Container sind in welchem Netz:
for net in $(docker network ls -q); do
  echo "=== $(docker network inspect $net --format '{{.Name}}') ==="
  docker network inspect $net --format '{{range .Containers}}  {{.Name}}{{"\n"}}{{end}}'
done
```

**Fix: Container muss im Coolify-Netz sein:**
```bash
docker network connect coolify typebot
docker network connect coolify n8n
```

---

### SCHRITT 6: SSL / ACME prüfen

```bash
# ACME Zertifikat-Store von Traefik:
docker exec coolify-proxy cat /etc/traefik/acme.json 2>/dev/null | python3 -m json.tool | grep -E "domain|sans|notAfter" | head -30

# Falls Datei leer oder nicht vorhanden:
# Traefik kann keine Challenge abschließen → Port 80 muss offen sein für HTTP Challenge

# Prüfe ob Port 80 auf Traefik ankommt:
curl -v http://94.130.170.167/.well-known/acme-challenge/test 2>&1 | head -20

# Let's Encrypt Rate Limit Check:
# https://crt.sh/?q=deine-domain.de
# Max 5 Fehlversuche pro Stunde, 50 Zertifikate pro Woche

# Traefik muss Let's Encrypt E-Mail konfiguriert haben:
docker exec coolify-proxy cat /etc/traefik/traefik.yml 2>/dev/null | grep -A5 "certificatesResolvers"
```

---

### SCHRITT 7: Port-Belegung prüfen

```bash
# Was hört auf Port 80 und 443?
ss -tlnp | grep -E ":80|:443"
# oder
netstat -tlnp | grep -E ":80|:443"

# Falls ein anderer Prozess Port 80/443 belegt:
fuser 80/tcp
fuser 443/tcp
```

---

### SCHRITT 8: BASE_URL Konfiguration prüfen

```bash
# Typebot ENV:
docker exec $(docker ps -q --filter "name=typebot") env | grep -iE "url|host|nextauth|base"

# n8n ENV:
docker exec $(docker ps -q --filter "name=n8n") env | grep -iE "url|host|webhook|base"
```

**Korrekte Werte:**
```
# Typebot:
NEXTAUTH_URL=https://typebot.deine-domain.de
NEXT_PUBLIC_VIEWER_URL=https://bot.deine-domain.de

# n8n:
N8N_HOST=n8n.deine-domain.de
N8N_PROTOCOL=https
WEBHOOK_URL=https://n8n.deine-domain.de/
N8N_EDITOR_BASE_URL=https://n8n.deine-domain.de/
```

---

### SCHRITT 9: Vollständiger Connectivity-Test

```bash
# Intern vom Server direkt testen (bypass DNS):
curl -v -H "Host: typebot.deine-domain.de" http://localhost/ 2>&1 | head -30

# Mit IP direkt (prüft ob Traefik überhaupt antwortet):
curl -v http://94.130.170.167/ 2>&1 | head -20

# HTTPS Test:
curl -v https://typebot.deine-domain.de/ 2>&1 | head -30
```

---

### SCHRITT 10: Coolify Service Health im Panel

```
Coolify UI → Services → [Typebot / n8n]
→ Prüfe: Status (Running / Stopped / Error)
→ Prüfe: Domain konfiguriert? (https:// Prefix, kein trailing slash)
→ Prüfe: "Proxy" aktiviert? (Toggle muss ON sein)
→ Prüfe: Port korrekt? (Typebot: 3000, n8n: 5678)
→ Logs Tab: Fehler beim Start?
```

---

## Schnell-Diagnose Script (alles auf einmal)

```bash
#!/bin/bash
# Auf Server 1 ausführen:
echo "=== DOCKER CONTAINERS ==="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n=== PORT 80/443 LISTENER ==="
ss -tlnp | grep -E ":80|:443"

echo -e "\n=== UFW STATUS ==="
ufw status verbose

echo -e "\n=== DOCKER NETWORKS ==="
docker network ls

echo -e "\n=== TRAEFIK/PROXY LOGS (last 30) ==="
docker logs coolify-proxy --tail=30 2>&1 || docker logs traefik --tail=30 2>&1

echo -e "\n=== TYPEBOT LOGS (last 20) ==="
docker logs $(docker ps -aq --filter "name=typebot") --tail=20 2>&1

echo -e "\n=== N8N LOGS (last 20) ==="
docker logs $(docker ps -aq --filter "name=n8n") --tail=20 2>&1

echo -e "\n=== NETWORK MEMBERSHIP ==="
for net in $(docker network ls -q); do
  name=$(docker network inspect $net --format '{{.Name}}')
  members=$(docker network inspect $net --format '{{range .Containers}}{{.Name}} {{end}}')
  if [ -n "$members" ]; then
    echo "$name: $members"
  fi
done
```

Speichere als `diagnose.sh`, dann: `bash diagnose.sh 2>&1 | tee diagnose-output.txt`

Schicke mir `diagnose-output.txt` und ich liefere den genauen Fix.
