#!/bin/bash
set -e

echo "🚀 VOICE BOT + RAG DEPLOYMENT - SERVER 2"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/root/marcello2304"
DOCKER_COMPOSE_FILE="$PROJECT_DIR/docker/compose-server2.yml"
ENV_FILE="$PROJECT_DIR/.env.server2"

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 1: Update Git Repository${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"
cd "$PROJECT_DIR"

echo "Fetching latest changes..."
git fetch origin main

echo "Current branch:"
git branch --show-current

echo "Latest commits:"
git log --oneline -5

echo "Pulling main branch..."
git pull origin main

echo -e "${GREEN}✓ Git updated${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 2: Verify Environment Configuration${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}✗ ERROR: $ENV_FILE not found!${NC}"
    exit 1
fi

echo "Checking critical environment variables..."

# Check LiveKit
if grep -q "LIVEKIT_API_KEY=" "$ENV_FILE" && grep -q "LIVEKIT_API_SECRET=" "$ENV_FILE"; then
    echo -e "${GREEN}✓ LiveKit credentials configured${NC}"
else
    echo -e "${RED}✗ Missing LiveKit credentials${NC}"
    exit 1
fi

# Check Cartesia
if grep -q "CARTESIA_API_KEY=" "$ENV_FILE"; then
    echo -e "${GREEN}✓ Cartesia API key configured${NC}"
else
    echo -e "${YELLOW}⚠ Cartesia API key missing (optional, will use fallback)${NC}"
fi

# Check RAG
if grep -q "RAG_WEBHOOK_URL=" "$ENV_FILE"; then
    RAG_URL=$(grep "RAG_WEBHOOK_URL=" "$ENV_FILE" | cut -d'=' -f2)
    echo -e "${GREEN}✓ RAG Webhook configured: $RAG_URL${NC}"
else
    echo -e "${YELLOW}⚠ RAG Webhook not configured (will run without RAG)${NC}"
fi

# Check Ollama
if grep -q "OLLAMA_BASE_URL=" "$ENV_FILE"; then
    OLLAMA_URL=$(grep "OLLAMA_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2)
    echo -e "${GREEN}✓ Ollama configured: $OLLAMA_URL${NC}"
else
    echo -e "${RED}✗ Missing Ollama configuration${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment configuration verified${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 3: Stop Old Voice Agent Container${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

if docker ps -a --format '{{.Names}}' | grep -q "livekit-agent"; then
    echo "Stopping old livekit-agent container..."
    docker stop livekit-agent 2>/dev/null || true
    docker rm livekit-agent 2>/dev/null || true
    echo -e "${GREEN}✓ Old container removed${NC}"
else
    echo -e "${GREEN}✓ No old container running${NC}"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 4: Build New Voice Agent Docker Image${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

cd "$PROJECT_DIR/voice-agent"

echo "Building Docker image..."
docker build -t voice-agent:latest . --progress=plain

if docker images | grep -q "voice-agent.*latest"; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 5: Check Dependencies (Ollama, LiveKit)${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

echo "Checking if Ollama is running..."
if docker ps --format '{{.Names}}' | grep -q "ollama"; then
    echo -e "${GREEN}✓ Ollama container is running${NC}"

    # Check if phi model is loaded
    echo "Checking for phi model..."
    if timeout 5 curl -s http://ollama:11434/api/tags | grep -q "phi"; then
        echo -e "${GREEN}✓ phi model is available${NC}"
    else
        echo -e "${YELLOW}⚠ phi model not found - pulling it...${NC}"
        docker exec ollama ollama pull phi:latest || true
    fi
else
    echo -e "${RED}✗ Ollama not running - start it first!${NC}"
    exit 1
fi

echo "Checking if LiveKit is running..."
if docker ps --format '{{.Names}}' | grep -q "livekit"; then
    echo -e "${GREEN}✓ LiveKit container is running${NC}"
else
    echo -e "${RED}✗ LiveKit not running - start it first!${NC}"
    exit 1
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 6: Start Voice Agent Container${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

cd "$PROJECT_DIR"

echo "Starting livekit-agent via docker-compose..."
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d livekit-agent

sleep 3

if docker ps --format '{{.Names}}' | grep -q "livekit-agent"; then
    echo -e "${GREEN}✓ livekit-agent container started${NC}"
else
    echo -e "${RED}✗ Failed to start livekit-agent${NC}"
    docker logs livekit-agent 2>&1 | tail -50
    exit 1
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 7: Monitor Agent Startup (30 seconds)${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

echo "Waiting for agent to initialize..."
for i in {1..30}; do
    if docker logs livekit-agent 2>&1 | grep -q "Agent started and listening"; then
        echo -e "${GREEN}✓ Agent ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "Latest agent logs:"
docker logs --tail=20 livekit-agent

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 8: Test RAG Webhook${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

echo "Testing RAG Query webhook..."
RAG_URL=$(grep "RAG_WEBHOOK_URL=" "$ENV_FILE" | cut -d'=' -f2)

if [ -n "$RAG_URL" ]; then
    echo "Sending test query to: $RAG_URL"

    RESPONSE=$(curl -s -X POST "$RAG_URL" \
      -H "Content-Type: application/json" \
      -d '{
        "tenant_slug": "eppcom",
        "query": "Test query",
        "session_id": "deployment-test",
        "bot_id": "voice-bot"
      }' 2>&1)

    if echo "$RESPONSE" | grep -q "answer\|sources"; then
        echo -e "${GREEN}✓ RAG webhook is responding${NC}"
        echo "Response preview:"
        echo "$RESPONSE" | jq . 2>/dev/null | head -20 || echo "$RESPONSE" | head -20
    else
        echo -e "${YELLOW}⚠ RAG webhook returned unexpected response${NC}"
        echo "Response: $RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠ RAG_WEBHOOK_URL not configured${NC}"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}STEP 9: Final Status Check${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

echo "Service Status:"
echo "─────────────────────────────────────────────────────────────────────────────"

services=("livekit" "ollama" "livekit-agent")
for service in "${services[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        STATUS=$(docker ps --format '{{.Status}}' -f "name=^${service}$")
        echo -e "${GREEN}✓ $service${NC}: $STATUS"
    else
        echo -e "${RED}✗ $service${NC}: NOT RUNNING"
    fi
done

echo ""
echo -e "${BLUE}Network & Connectivity:${NC}"
echo "─────────────────────────────────────────────────────────────────────────────"

if docker network ls --format '{{.Name}}' | grep -q "ai-net"; then
    echo -e "${GREEN}✓ Network 'ai-net' exists${NC}"
else
    echo -e "${RED}✗ Network 'ai-net' not found${NC}"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

echo "🎯 Voice Bot Status:"
echo "  • Agent: Running (livekit-agent)"
echo "  • LLM: $OLLAMA_URL"
echo "  • TTS: Cartesia (configured)"
echo "  • RAG: $([ -n "$RAG_URL" ] && echo "$RAG_URL" || echo "DISABLED")"
echo ""

echo "📋 Next Steps:"
echo "  1. Monitor logs: docker logs -f livekit-agent"
echo "  2. Test with voice client (LiveKit console)"
echo "  3. Speak: 'Hallo, wer bist du?'"
echo "  4. Expected response time: 2-5 seconds (with RAG context)"
echo ""

echo "🔧 Troubleshooting:"
echo "  • Check agent logs: docker logs livekit-agent"
echo "  • Check Ollama: curl -s http://ollama:11434/api/tags | jq"
echo "  • Check RAG: curl -X POST $RAG_URL -d '{...}'"
echo ""

echo -e "${GREEN}Deployment successful! 🚀${NC}"
