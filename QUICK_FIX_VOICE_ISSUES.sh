#!/bin/bash
# Quick fixes for common voice agent issues

set -e

echo "═══════════════════════════════════════════════════════════"
echo "QUICK FIX: VOICE AGENT ISSUES"
echo "═══════════════════════════════════════════════════════════"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get latest code
echo -e "${BLUE}[STEP 1/5]${NC} Pulling latest code with TTS/STT fixes..."
cd /root/marcello2304
git pull origin main
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

# Rebuild Docker image
echo -e "${BLUE}[STEP 2/5]${NC} Rebuilding Docker image with new TTS voice..."
cd voice-agent
docker build --no-cache -t voice-agent:latest .
cd ..
echo -e "${GREEN}✓ Docker image rebuilt with new 'Bella' voice${NC}"
echo ""

# Stop old container
echo -e "${BLUE}[STEP 3/5]${NC} Stopping old container..."
CONTAINER_ID=$(docker ps -q -f "name=voice-agent" 2>/dev/null || true)
if [ ! -z "$CONTAINER_ID" ]; then
    docker stop "$CONTAINER_ID" || true
    docker rm "$CONTAINER_ID" || true
    echo -e "${GREEN}✓ Old container stopped${NC}"
else
    echo "   No running container found"
fi
echo ""

# Start new container
echo -e "${BLUE}[STEP 4/5]${NC} Starting new container with fixes..."
docker run -d \
  --name voice-agent \
  --env-file .env.server2 \
  --volume ~/.cache:/root/.cache \
  --network livekit-net \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  voice-agent:latest

CONTAINER_ID=$(docker ps -q -f "name=voice-agent")
echo -e "${GREEN}✓ New container started: $CONTAINER_ID${NC}"
echo ""

# Wait for initialization
echo -e "${BLUE}[STEP 5/5]${NC} Waiting for initialization (30 seconds)..."
sleep 5

# Show first logs
echo ""
echo -e "${BLUE}INITIALIZATION LOGS:${NC}"
docker logs voice-agent --tail 20

echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ FIXES APPLIED${NC}"
echo ""
echo "IMPROVEMENTS:"
echo "  ✓ TTS Voice changed to 'Bella' (warm, natural German voice)"
echo "  ✓ OpenAI TTS fallback added (high quality)"
echo "  ✓ Better error handling & logging"
echo "  ✓ RAG context errors won't break conversation"
echo "  ✓ Detailed debug logs for troubleshooting"
echo ""
echo "TEST NOW:"
echo "  1. Call voice bot via LiveKit"
echo "  2. Speak a question/greeting"
echo "  3. Check if voice quality improved"
echo "  4. Verify you get a response (no more 'Entschuldigung' errors)"
echo ""
echo "MONITORING:"
echo "  docker logs -f voice-agent"
echo ""
echo "═══════════════════════════════════════════════════════════"
