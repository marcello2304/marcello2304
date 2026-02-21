#!/bin/bash
# diagnose-domains.sh — Vollständige Domain-Diagnose für Server 1
# Ausführen auf Server 1: bash diagnose-domains.sh 2>&1 | tee diagnose-output.txt

set -euo pipefail

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

section() { echo -e "\n${BLUE}=== $1 ===${NC}"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }

echo "================================================================"
echo " Hetzner RAG Platform — Domain Diagnose"
echo " Datum: $(date)"
echo " Server IP: $(curl -s https://ipinfo.io/ip 2>/dev/null || hostname -I | awk '{print $1}')"
echo "================================================================"

# --- 1. Docker Container Status ---
section "Docker Container Status"
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || fail "Docker nicht erreichbar"

section "Container Restart-Counts"
docker inspect --format='{{.Name}} — Restarts: {{.RestartCount}} — Status: {{.State.Status}}' \
    $(docker ps -aq) 2>/dev/null | sed 's/\///'

# --- 2. Port-Belegung ---
section "Port 80 und 443 Listener"
if command -v ss &>/dev/null; then
    ss -tlnp | grep -E ":80|:443" || warn "Keine Listener auf 80/443 gefunden — Traefik läuft möglicherweise nicht"
else
    netstat -tlnp | grep -E ":80|:443" || warn "Keine Listener auf 80/443 gefunden"
fi

# --- 3. Firewall ---
section "Firewall Status (ufw)"
if command -v ufw &>/dev/null; then
    ufw status verbose 2>/dev/null || warn "ufw nicht verfügbar"
else
    warn "ufw nicht installiert — prüfe nftables oder Hetzner Cloud Firewall"
fi

section "nftables (falls genutzt)"
nft list ruleset 2>/dev/null | grep -E "tcp|http|https" | head -20 || warn "nftables nicht verfügbar oder keine TCP-Regeln"

# --- 4. Docker Networks ---
section "Docker Networks"
docker network ls

section "Container pro Netzwerk"
for net in $(docker network ls -q 2>/dev/null); do
    name=$(docker network inspect "$net" --format '{{.Name}}' 2>/dev/null)
    members=$(docker network inspect "$net" --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null)
    if [ -n "$members" ]; then
        echo "$name: $members"
    fi
done

# --- 5. Traefik/Proxy Logs ---
section "Traefik / Coolify-Proxy Logs (letzte 50)"
PROXY_CONTAINER=""
for name in coolify-proxy traefik proxy; do
    if docker ps --filter "name=$name" --quiet 2>/dev/null | grep -q .; then
        PROXY_CONTAINER="$name"
        break
    fi
done

if [ -n "$PROXY_CONTAINER" ]; then
    ok "Proxy-Container gefunden: $PROXY_CONTAINER"
    docker logs "$PROXY_CONTAINER" --tail=50 2>&1
else
    fail "Kein Traefik/Proxy-Container gefunden!"
fi

# --- 6. App Container Logs ---
section "Typebot Logs (letzte 30)"
TYPEBOT=$(docker ps -aq --filter "name=typebot" 2>/dev/null | head -1)
if [ -n "$TYPEBOT" ]; then
    docker logs "$TYPEBOT" --tail=30 2>&1
else
    warn "Kein Typebot-Container gefunden"
fi

section "n8n Logs (letzte 30)"
N8N=$(docker ps -aq --filter "name=n8n" 2>/dev/null | head -1)
if [ -n "$N8N" ]; then
    docker logs "$N8N" --tail=30 2>&1
else
    warn "Kein n8n-Container gefunden"
fi

section "PostgreSQL Logs (letzte 20)"
PG=$(docker ps -aq --filter "name=postgres" 2>/dev/null | head -1)
if [ -n "$PG" ]; then
    docker logs "$PG" --tail=20 2>&1
else
    warn "Kein PostgreSQL-Container gefunden"
fi

# --- 7. Traefik Labels der Container ---
section "Traefik Labels — Typebot"
if [ -n "$TYPEBOT" ]; then
    docker inspect "$TYPEBOT" 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -i traefik | head -20 || warn "Keine Traefik-Labels auf Typebot-Container"
fi

section "Traefik Labels — n8n"
if [ -n "$N8N" ]; then
    docker inspect "$N8N" 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -i traefik | head -20 || warn "Keine Traefik-Labels auf n8n-Container"
fi

# --- 8. ENV Variablen (ohne Passwörter) ---
section "Typebot ENV (Domain-relevante Variablen)"
if [ -n "$TYPEBOT" ]; then
    docker exec "$TYPEBOT" env 2>/dev/null | grep -iE "url|host|nextauth|base|port" | grep -v -iE "password|secret|key|token" || warn "Fehler beim Lesen der ENVs"
fi

section "n8n ENV (Domain-relevante Variablen)"
if [ -n "$N8N" ]; then
    docker exec "$N8N" env 2>/dev/null | grep -iE "url|host|webhook|base|port|protocol" | grep -v -iE "password|secret|key|token" || warn "Fehler beim Lesen der ENVs"
fi

# --- 9. Traefik Routers (API) ---
section "Traefik Registered Routers"
if curl -s http://localhost:8080/api/http/routers 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -E '"name"|"rule"|"status"' | head -40; then
    ok "Traefik Dashboard API erreichbar"
else
    warn "Traefik Dashboard API nicht erreichbar auf localhost:8080"
fi

# --- 10. Connectivity Test ---
section "Lokaler HTTP-Test (intern)"
if curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null; then
    echo " — HTTP localhost"
else
    warn "Kein Response auf http://localhost/"
fi

# --- Zusammenfassung ---
section "ZUSAMMENFASSUNG — Was zu prüfen ist"
echo ""
echo "1. Sind DNS-Records auf 94.130.170.167 gesetzt? (extern prüfen mit: dig domain.de)"
echo "2. Läuft der Proxy-Container? $([ -n "$PROXY_CONTAINER" ] && echo "JA ($PROXY_CONTAINER)" || echo "NEIN - kritisch!")"
echo "3. Hört Port 80/443? Prüfe Port-Listener oben."
echo "4. Sind Container im coolify-Netz? Prüfe 'Container pro Netzwerk' oben."
echo "5. Haben Container korrekte Traefik-Labels? Prüfe Labels-Sektion oben."
echo "6. Sind ENVs korrekt (NEXTAUTH_URL, WEBHOOK_URL etc.)? Prüfe ENV-Sektion."
echo ""
echo "Schicke diese Ausgabe für weitere Diagnose."
echo "================================================================"
