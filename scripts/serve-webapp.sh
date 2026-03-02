#!/bin/bash
# serve-webapp.sh — Startet die RAG-Test-Webapp lokal
# Startet einen einfachen HTTP-Server + optionalen Postgres-Proxy
#
# Verwendung:
#   bash scripts/serve-webapp.sh              # Port 8080
#   bash scripts/serve-webapp.sh --port 3000  # Eigener Port
#   bash scripts/serve-webapp.sh --open       # Browser öffnen

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ -f ".env" ]; then set -a; source .env; set +a; fi

PORT=8080
OPEN_BROWSER=false
for arg in "$@"; do
    [[ "$arg" == --port=* ]] && PORT="${arg#--port=}"
    [[ "$arg" == --port ]]   && shift && PORT="$1"
    [[ "$arg" == --open ]]   && OPEN_BROWSER=true
done

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'; BOLD='\033[1m'

echo ""
echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}${BOLD}  RAG Test-Webapp${NC}"
echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

WEBAPP_DIR="$PROJECT_DIR/webapp"

# ── Server starten ───────────────────────────────────────────────────────
start_server() {
    local METHOD="$1"
    case "$METHOD" in
        python3)
            echo -e "  ${GREEN}→${NC}  Starte mit Python3 HTTP-Server..."
            cd "$WEBAPP_DIR"
            python3 -m http.server "$PORT" --bind 0.0.0.0
            ;;
        python)
            cd "$WEBAPP_DIR"
            python -m SimpleHTTPServer "$PORT"
            ;;
        node)
            echo -e "  ${GREEN}→${NC}  Starte mit Node.js serve..."
            cd "$WEBAPP_DIR"
            npx serve -p "$PORT" -s .
            ;;
        busybox)
            cd "$WEBAPP_DIR"
            busybox httpd -f -p "$PORT"
            ;;
    esac
}

# Verfügbare Methode finden
SERVER_METHOD=""
command -v python3 &>/dev/null && SERVER_METHOD="python3"
[ -z "$SERVER_METHOD" ] && command -v python &>/dev/null && SERVER_METHOD="python"
[ -z "$SERVER_METHOD" ] && command -v node &>/dev/null && SERVER_METHOD="node"
[ -z "$SERVER_METHOD" ] && command -v busybox &>/dev/null && SERVER_METHOD="busybox"

if [ -z "$SERVER_METHOD" ]; then
    echo -e "  ${YELLOW}!${NC}  Kein HTTP-Server verfügbar."
    echo -e "  Installiere Python3: apt install python3"
    echo -e "  Oder öffne webapp/index.html direkt im Browser."
    exit 1
fi

# n8n Webhook-URL ermitteln und in Config-Vorlage eintragen
N8N_INTERNAL="http://$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' n8n 2>/dev/null | head -1):5678/webhook/rag-query"
N8N_PUBLIC="https://n8n.${DOMAIN:-localhost}/webhook/rag-query"

echo -e "  ${GREEN}✓${NC}  Webapp-Verzeichnis: $WEBAPP_DIR"
echo ""
echo -e "  ${BLUE}Webapp:${NC}"
echo -e "    http://localhost:$PORT"
echo ""
echo -e "  ${BLUE}n8n Webhook-URLs (in Webapp eintragen):${NC}"
echo -e "    Intern (im Server-Netz):   $N8N_INTERNAL"
echo -e "    Extern (via Domain/HTTPS): $N8N_PUBLIC"
echo -e "    Lokal (direkter Port):     http://localhost:5678/webhook/rag-query"
echo ""
echo -e "  ${YELLOW}Tipp:${NC} Die URL in der Webapp-Sidebar eintragen und Enter drücken."
echo ""
echo -e "  ${BLUE}Schnell-Test vorher:${NC}"
echo -e "    bash scripts/test-rag-path.sh"
echo ""
echo -e "  ${BLUE}Testdaten einfügen:${NC}"
echo -e "    bash scripts/seed-test-data.sh --tenant demo"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Strg+C zum Beenden"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Browser öffnen (wenn gewünscht)
if [ "$OPEN_BROWSER" = true ]; then
    sleep 1
    (xdg-open "http://localhost:$PORT" 2>/dev/null || \
     open "http://localhost:$PORT" 2>/dev/null || true) &
fi

start_server "$SERVER_METHOD"
