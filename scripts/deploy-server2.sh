#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# Deploy-Script für Server 2 (Ollama + LiveKit + Voice Agent)
# Server: 46.224.54.65
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVER2_IP="${SERVER2_IP:-46.224.54.65}"
REMOTE_DIR="/opt/eppcom-server2"

echo "═══════════════════════════════════════════════════════════════"
echo "  EPPCOM Server 2 Deploy — $SERVER2_IP"
echo "═══════════════════════════════════════════════════════════════"

# ── Phase 1: Prüfe .env.server2 ──────────────────────────────────────
ENV_FILE="$PROJECT_DIR/.env.server2"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "⚠  .env.server2 nicht gefunden!"
    echo "   Erstelle aus Template:"
    echo "   cp coolify/env-templates/server2.env.example .env.server2"
    echo "   Dann die Werte ausfüllen und erneut ausführen."
    exit 1
fi

# Prüfe Pflichtfelder
missing=0
for var in LIVEKIT_API_KEY LIVEKIT_API_SECRET OLLAMA_BEARER_TOKEN; do
    val=$(grep "^${var}=" "$ENV_FILE" | cut -d= -f2-)
    if [ -z "$val" ] || echo "$val" | grep -qi "HIER\|CHANGE\|PLATZHALTER"; then
        echo "⚠  $var ist nicht gesetzt oder enthält Platzhalter"
        missing=1
    fi
done
if [ "$missing" -eq 1 ]; then
    echo "Bitte .env.server2 ausfüllen und erneut ausführen."
    exit 1
fi

echo "✓ .env.server2 geprüft"

# ── Phase 2: Dateien auf Server 2 kopieren ───────────────────────────
echo ""
echo "► Dateien auf Server 2 kopieren..."

ssh root@"$SERVER2_IP" "mkdir -p $REMOTE_DIR/{docker,voice-agent,nginx}"

# Docker Compose + Configs
scp "$PROJECT_DIR/docker/compose-server2.yml" root@"$SERVER2_IP":"$REMOTE_DIR/docker-compose.yml"
scp "$PROJECT_DIR/docker/livekit.yaml"        root@"$SERVER2_IP":"$REMOTE_DIR/docker/livekit.yaml"
scp "$PROJECT_DIR/docker/nginx-server2.conf"  root@"$SERVER2_IP":"$REMOTE_DIR/nginx/nginx.conf.template"

# Voice Agent
scp "$PROJECT_DIR/voice-agent/agent.py"        root@"$SERVER2_IP":"$REMOTE_DIR/voice-agent/"
scp "$PROJECT_DIR/voice-agent/requirements.txt" root@"$SERVER2_IP":"$REMOTE_DIR/voice-agent/"
scp "$PROJECT_DIR/voice-agent/Dockerfile"      root@"$SERVER2_IP":"$REMOTE_DIR/voice-agent/"

# .env
scp "$ENV_FILE" root@"$SERVER2_IP":"$REMOTE_DIR/.env"

echo "✓ Dateien kopiert"

# ── Phase 3: LiveKit Konfiguration anpassen ──────────────────────────
echo ""
echo "► LiveKit-Config mit echten Keys aktualisieren..."

LIVEKIT_KEY=$(grep "^LIVEKIT_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
LIVEKIT_SECRET=$(grep "^LIVEKIT_API_SECRET=" "$ENV_FILE" | cut -d= -f2-)
DOMAIN=$(grep "^DOMAIN=" "$ENV_FILE" | cut -d= -f2-)

ssh root@"$SERVER2_IP" bash <<REMOTE_SCRIPT
cat > $REMOTE_DIR/docker/livekit.yaml << 'YAMLEOF'
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 50100
  use_external_ip: true

keys:
  ${LIVEKIT_KEY}: ${LIVEKIT_SECRET}

logging:
  json: false
  level: info

room:
  auto_create: true
  max_participants: 50

turn:
  enabled: false
YAMLEOF

# Livekit-Verzeichnis für Docker-Mount erstellen
mkdir -p $REMOTE_DIR/livekit
cp $REMOTE_DIR/docker/livekit.yaml $REMOTE_DIR/livekit/livekit.yaml

echo "✓ LiveKit-Config aktualisiert"
REMOTE_SCRIPT

# ── Phase 4: Docker Services starten ─────────────────────────────────
echo ""
echo "► Docker Services auf Server 2 starten..."

ssh root@"$SERVER2_IP" bash <<REMOTE_SCRIPT
cd $REMOTE_DIR

# Docker installieren falls nicht vorhanden
if ! command -v docker &> /dev/null; then
    echo "Docker wird installiert..."
    curl -fsSL https://get.docker.com | sh
fi

# Docker Compose Plugin prüfen
if ! docker compose version &> /dev/null; then
    echo "Docker Compose Plugin wird installiert..."
    apt-get update && apt-get install -y docker-compose-plugin
fi

# Voice Agent Image bauen
echo "► Voice Agent Docker-Image bauen (kann 5-10 Min dauern)..."
docker compose build livekit-agent

# Services starten
echo "► Services starten..."
docker compose up -d

# Status anzeigen
echo ""
echo "═══════════════════════════════════════════════════"
docker compose ps
echo "═══════════════════════════════════════════════════"
REMOTE_SCRIPT

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ Deploy abgeschlossen!"
echo ""
echo "  Services:"
echo "    Ollama:     https://ollama.${DOMAIN:-eppcom.de}"
echo "    LiveKit:    wss://voice.${DOMAIN:-eppcom.de}"
echo "    Voice Bot:  Automatisch verbunden mit LiveKit"
echo ""
echo "  Nächste Schritte:"
echo "    1. SSL-Zertifikate: docker compose run certbot certonly --webroot ..."
echo "    2. DNS A-Records für ollama.${DOMAIN} und voice.${DOMAIN}"
echo "    3. Hetzner Firewall: Ports 80,443,7880,7881,50000-50100 freigeben"
echo "═══════════════════════════════════════════════════════════════"
