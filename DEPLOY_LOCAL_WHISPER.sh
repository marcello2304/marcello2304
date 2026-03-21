#!/bin/bash
# Deployment script for self-hosted Whisper-small STT on Server 2
# Usage: bash DEPLOY_LOCAL_WHISPER.sh

set -e

echo "═══════════════════════════════════════════════════════════"
echo "DEPLOYING LOCAL WHISPER-SMALL STT ON SERVER 2"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Pull latest code
echo -e "${BLUE}[STEP 1/5]${NC} Pulling latest code from git..."
git pull origin main
echo -e "${GREEN}✓ Code updated${NC}\n"

# Step 2: Check environment
echo -e "${BLUE}[STEP 2/5]${NC} Verifying .env.server2 configuration..."

if ! grep -q "USE_LOCAL_WHISPER=true" .env.server2; then
    echo -e "${YELLOW}⚠️  USE_LOCAL_WHISPER not found in .env.server2${NC}"
    echo "   Adding: USE_LOCAL_WHISPER=true"
    echo "USE_LOCAL_WHISPER=true" >> .env.server2
fi

if ! grep -q "WHISPER_MODEL=" .env.server2; then
    echo "WHISPER_MODEL=small" >> .env.server2
fi

if ! grep -q "WHISPER_DEVICE=" .env.server2; then
    echo "WHISPER_DEVICE=auto" >> .env.server2
fi

echo -e "${GREEN}✓ Configuration verified${NC}\n"

# Step 3: Stop existing container
echo -e "${BLUE}[STEP 3/5]${NC} Stopping existing voice-agent container..."

CONTAINER_ID=$(docker ps -q -f "name=voice-agent" 2>/dev/null || true)
if [ ! -z "$CONTAINER_ID" ]; then
    echo "   Stopping container $CONTAINER_ID..."
    docker stop "$CONTAINER_ID" || true
    docker rm "$CONTAINER_ID" || true
    echo -e "${GREEN}✓ Old container stopped${NC}"
else
    echo "   No running container found"
fi
echo ""

# Step 4: Build updated Docker image
echo -e "${BLUE}[STEP 4/5]${NC} Building updated Docker image with local Whisper support..."
cd voice-agent
docker build -t voice-agent:latest .
cd ..
echo -e "${GREEN}✓ Docker image built${NC}\n"

# Step 5: Start container with local Whisper
echo -e "${BLUE}[STEP 5/5]${NC} Starting voice-agent container..."
echo "   Config:"
echo "   - USE_LOCAL_WHISPER=true (local Whisper enabled)"
echo "   - WHISPER_MODEL=small (140MB, ~1s latency)"
echo "   - WHISPER_DEVICE=auto (GPU if available)"
echo ""

docker run -d \
  --name voice-agent \
  --env-file .env.server2 \
  --volume ~/.cache:/root/.cache \
  --network livekit-net \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  voice-agent:latest

CONTAINER_ID=$(docker ps -q -f "name=voice-agent")
echo -e "${GREEN}✓ Container started: $CONTAINER_ID${NC}\n"

echo "═══════════════════════════════════════════════════════════"
echo "DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════\n"

# Show logs
echo -e "${BLUE}INITIALIZING (first run downloads Whisper model)...${NC}"
echo "This may take 2-3 minutes on first run. Subsequent starts are instant."
echo ""

# Wait a moment and show initial logs
sleep 2
docker logs voice-agent --tail 20

echo ""
echo "📊 MONITORING MODEL DOWNLOAD:"
echo "   Run: docker logs -f voice-agent"
echo ""
echo "🎤 TESTING VOICE INTERACTION:"
echo "   Once initialization completes, test by speaking into LiveKit room"
echo ""
echo "📝 EXPECTED LOGS:"
echo "   [INFO] Loading Whisper-small model (device: auto)..."
echo "   [INFO] ✓ Whisper-small loaded successfully"
echo ""
echo "❓ For troubleshooting, see: WHISPER_LOCAL_STT_GUIDE.md"
echo ""

# Monitor initialization
echo "Waiting for model initialization..."
MAX_WAIT=180  # 3 minutes
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if docker logs voice-agent 2>/dev/null | grep -q "Whisper.*loaded successfully"; then
        echo -e "${GREEN}✅ MODEL INITIALIZED SUCCESSFULLY!${NC}"
        echo ""
        echo "Voice agent is now ready with local Whisper-small STT:"
        docker logs voice-agent --tail 10
        exit 0
    elif docker logs voice-agent 2>/dev/null | grep -q "ERROR\|CRITICAL"; then
        echo -e "${YELLOW}⚠️  Check logs for errors:${NC}"
        docker logs voice-agent --tail 30
        exit 1
    fi

    ELAPSED=$((ELAPSED + 5))
    echo -n "."
    sleep 5
done

echo ""
echo -e "${YELLOW}⚠️  Initialization taking longer than expected.${NC}"
echo "This may be normal if downloading model for the first time."
echo "Check logs with: docker logs -f voice-agent"
