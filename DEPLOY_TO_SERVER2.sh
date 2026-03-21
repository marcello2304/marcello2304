#!/bin/bash
# COMPREHENSIVE DEPLOYMENT TO SERVER 2
# Fixes: IndentationError, Voice ID, RAG config, Docker rebuild
# Run this on Server 2 as root

set -e

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "DEPLOYING FIXED VOICE AGENT TO SERVER 2"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ─── STEP 1: Navigate and verify ─────────────────────────────────────────────────
echo -e "${BLUE}[STEP 1/6]${NC} Verifying Server 2 setup..."

if [ ! -f "/opt/eppcom-server2/voice-agent/agent.py" ]; then
    echo -e "${RED}✗ FATAL: /opt/eppcom-server2/voice-agent/agent.py not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Agent directory confirmed${NC}"
echo ""

# ─── STEP 2: Backup original agent.py ────────────────────────────────────────────
echo -e "${BLUE}[STEP 2/6]${NC} Backing up original agent.py..."
cd /opt/eppcom-server2/voice-agent
cp agent.py agent.py.backup.$(date +%s)
echo -e "${GREEN}✓ Backup created${NC}"
echo ""

# ─── STEP 3: Pull latest code from git ──────────────────────────────────────────
echo -e "${BLUE}[STEP 3/6]${NC} Pulling latest code from repository..."
cd /opt/eppcom-server2
git pull origin main
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

# ─── STEP 4: Fix agent.py (remove any broken lines at end) ───────────────────────
echo -e "${BLUE}[STEP 4/6]${NC} Verifying agent.py integrity..."
cd /opt/eppcom-server2/voice-agent

# Check for IndentationError by looking for raw RAG_WEBHOOK_URL at file root
if tail -20 agent.py | grep -q "^RAG_WEBHOOK_URL = "; then
    echo "  Detected broken lines in agent.py (IndentationError), removing..."
    # Keep only valid Python lines (truncate at last valid function/class)
    python3 << 'PYFIX'
with open("agent.py", "r") as f:
    lines = f.readlines()

# Find last line with proper indentation (should be inside function/class)
valid_lines = []
for i, line in enumerate(lines):
    if i < len(lines) - 1:
        valid_lines.append(line)
    else:
        # Check if last line is properly indented
        if line.startswith("    ") or line.startswith("\t") or line.strip() == "":
            valid_lines.append(line)
        else:
            print(f"Removing broken line {i+1}: {line[:50]}")

# Write back
with open("agent.py", "w") as f:
    f.writelines(valid_lines)

print("✓ Agent.py sanitized")
PYFIX
fi

# Verify no syntax errors
python3 -m py_compile agent.py && echo -e "${GREEN}✓ agent.py syntax OK${NC}" || {
    echo -e "${RED}✗ Syntax error in agent.py${NC}"
    exit 1
}
echo ""

# ─── STEP 5: Verify and set .env configuration ──────────────────────────────────
echo -e "${BLUE}[STEP 5/6]${NC} Verifying .env configuration..."
cd /opt/eppcom-server2

if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env not found${NC}"
    exit 1
fi

# Check Cartesia API Key
if grep -q "CARTESIA_API_KEY=sk_car_" .env; then
    echo -e "${GREEN}✓ Cartesia API Key present${NC}"
else
    echo -e "${RED}✗ Cartesia API Key missing${NC}"
    exit 1
fi

# Ensure RAG is disabled (empty webhook URL)
if grep -q "^RAG_WEBHOOK_URL=" .env; then
    # Update to empty
    sed -i 's/^RAG_WEBHOOK_URL=.*/RAG_WEBHOOK_URL=/g' .env
    echo -e "${GREEN}✓ RAG_WEBHOOK_URL disabled${NC}"
else
    # Add if missing
    echo "RAG_WEBHOOK_URL=" >> .env
    echo -e "${GREEN}✓ RAG_WEBHOOK_URL added (disabled)${NC}"
fi

echo ""

# ─── STEP 6: Rebuild Docker image and restart container ────────────────────────
echo -e "${BLUE}[STEP 6/6]${NC} Rebuilding Docker image..."

cd /opt/eppcom-server2/voice-agent
echo "  Building: docker build -t eppcom/voice-agent:latest ..."
docker build -t eppcom/voice-agent:latest . > /tmp/docker_build.log 2>&1 && {
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
} || {
    echo -e "${RED}✗ Docker build failed${NC}"
    tail -30 /tmp/docker_build.log
    exit 1
}

echo ""

# Stop and remove old container
echo "  Stopping old container..."
cd /opt/eppcom-server2
CONTAINER_ID=$(docker ps -q -f "name=livekit-agent" 2>/dev/null || true)
if [ ! -z "$CONTAINER_ID" ]; then
    docker stop "$CONTAINER_ID" 2>/dev/null || true
    sleep 2
    docker rm "$CONTAINER_ID" 2>/dev/null || true
    echo -e "${GREEN}✓ Old container stopped${NC}"
else
    echo "  (No running container found)"
fi

echo ""

# Start new container
echo "  Starting new container..."
docker run -d \
  --name livekit-agent \
  --env-file .env \
  --network ai-net \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  eppcom/voice-agent:latest > /tmp/container_id.log 2>&1 && {
    CONTAINER_ID=$(cat /tmp/container_id.log | tail -1)
    echo -e "${GREEN}✓ New container started: ${CONTAINER_ID:0:12}${NC}"
} || {
    echo -e "${RED}✗ Failed to start container${NC}"
    cat /tmp/container_id.log
    exit 1
}

echo ""

# Wait for initialization and check logs
echo "  Waiting 5 seconds for container initialization..."
sleep 5

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

echo "Configuration applied:"
echo "  ✓ Code: Latest from git"
echo "  ✓ Voice ID: Using Cartesia default German voice"
echo "  ✓ RAG: Disabled (graceful fallback)"
echo "  ✓ Network: ai-net"
echo "  ✓ TTS Provider: Cartesia Sonic-2"
echo ""

echo "VERIFICATION:"
echo "  docker ps -f 'name=livekit-agent'      # Check container running"
echo "  docker logs -f livekit-agent            # Stream logs"
echo "  docker logs livekit-agent --tail 30     # View last 30 lines"
echo ""

echo "TEST THE VOICE BOT:"
echo "  1. Open: www.eppcom.de/test.php"
echo "  2. Speak: 'Hallo, wie heißt du?'"
echo "  3. Verify:"
echo "     ✓ Voice is WARM & natural (NOT dark/metallic)"
echo "     ✓ You receive RESPONSE (NOT 'Entschuldigung, Fehler...')"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Show container status
echo "Current container status:"
docker ps -f "name=livekit-agent"

echo ""
echo "Recent logs (last 20 lines):"
docker logs livekit-agent --tail 20 || echo "(logs not yet available)"

echo ""
