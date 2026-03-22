#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Deploy Server 2 Complete Stack (LiveKit + Ollama + Voice Agent)
# ═══════════════════════════════════════════════════════════════════════════
# Usage:
#   On Server 2 (46.224.54.65):
#   cd /root/marcello2304
#   bash DEPLOY_SERVER2.sh
# ═══════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

echo "🚀 Deploying Server 2 Stack (LiveKit + Ollama + Voice Agent + Token Server)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─────────────────────────────────────────────────────────────────────────
# Step 1: Stop old standalone containers
# ─────────────────────────────────────────────────────────────────────────
echo "1️⃣  Stopping old standalone containers..."
docker stop voice-agent 2>/dev/null || echo "  (voice-agent not running)"
docker rm voice-agent 2>/dev/null || echo "  (voice-agent not found)"

# ─────────────────────────────────────────────────────────────────────────
# Step 2: Navigate to docker directory
# ─────────────────────────────────────────────────────────────────────────
cd /root/marcello2304/docker || exit 1
echo "2️⃣  Working directory: $(pwd)"

# ─────────────────────────────────────────────────────────────────────────
# Step 3: Load environment variables from .env.server2
# ─────────────────────────────────────────────────────────────────────────
echo "3️⃣  Checking environment file..."
if [ ! -f "../.env.server2" ]; then
    echo "❌ ERROR: ../.env.server2 not found!"
    exit 1
fi
echo "  ✓ .env.server2 found"

# ─────────────────────────────────────────────────────────────────────────
# Step 4: Pull latest images
# ─────────────────────────────────────────────────────────────────────────
echo "4️⃣  Pulling latest Docker images..."
docker pull nginx:alpine
docker pull ollama/ollama:latest
docker pull livekit/livekit-server:latest
docker pull python:3.11-slim

# ─────────────────────────────────────────────────────────────────────────
# Step 5: Build and deploy docker-compose stack
# ─────────────────────────────────────────────────────────────────────────
echo "5️⃣  Building and deploying docker-compose stack..."
docker-compose -f compose-server2.yml up -d --build

echo ""
echo "⏳ Waiting for services to start (30 seconds)..."
sleep 30

# ─────────────────────────────────────────────────────────────────────────
# Step 6: Verify deployments
# ─────────────────────────────────────────────────────────────────────────
echo "6️⃣  Verifying container status..."
echo ""
echo "🐳 Running containers:"
docker-compose -f compose-server2.yml ps

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment complete!"
echo ""
echo "🔍 Next steps:"
echo "  1. Check logs: docker-compose -f compose-server2.yml logs -f livekit-agent"
echo "  2. Test token endpoint: curl http://46.224.54.65/api/token?room=test&user=test"
echo "  3. Open browser: http://46.224.54.65/test-voice-agent.html"
echo "  4. Click 'Verbinden' and test voice connection"
echo ""
echo "📋 Service URLs:"
echo "  - Web Interface: http://46.224.54.65/test-voice-agent.html"
echo "  - Token API: http://46.224.54.65/api/token"
echo "  - LiveKit WS: ws://46.224.54.65:7880"
echo "  - Health Check: http://46.224.54.65/health"
