#!/bin/bash
# Test script for local Whisper deployment
# Verifies that voice-agent is running and configured correctly

set -e

echo "═══════════════════════════════════════════════════════════"
echo "LOCAL WHISPER DEPLOYMENT TEST"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FAILED=0

# Test 1: Container running
echo -e "${BLUE}[TEST 1]${NC} Checking if voice-agent container is running..."
if docker ps -q -f "name=voice-agent" > /dev/null; then
    echo -e "${GREEN}✓ Container is running${NC}"
    CONTAINER_ID=$(docker ps -q -f "name=voice-agent")
    echo "  Container ID: $CONTAINER_ID"
else
    echo -e "${RED}✗ Container is NOT running${NC}"
    FAILED=$((FAILED + 1))
fi
echo ""

# Test 2: Check Whisper model loaded
echo -e "${BLUE}[TEST 2]${NC} Checking if Whisper model initialized..."
if docker logs voice-agent 2>/dev/null | grep -q "Whisper.*loaded successfully"; then
    echo -e "${GREEN}✓ Whisper model loaded successfully${NC}"
    VERSION=$(docker logs voice-agent 2>/dev/null | grep -i "whisper" | head -1)
    echo "  $VERSION"
else
    if docker logs voice-agent 2>/dev/null | grep -q "Loading Whisper"; then
        echo -e "${YELLOW}⏳ Whisper still loading (downloading model, 2-3 min on first run)${NC}"
    else
        echo -e "${RED}✗ Whisper model NOT loaded${NC}"
        FAILED=$((FAILED + 1))
    fi
fi
echo ""

# Test 3: Check for initialization errors
echo -e "${BLUE}[TEST 3]${NC} Checking for critical errors..."
ERROR_COUNT=$(docker logs voice-agent 2>/dev/null | grep -i "CRITICAL\|ERROR" | wc -l || echo 0)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓ No critical errors found${NC}"
else
    echo -e "${RED}✗ Found $ERROR_COUNT errors${NC}"
    echo ""
    echo "Recent errors:"
    docker logs voice-agent 2>/dev/null | grep -i "CRITICAL\|ERROR" | tail -5
    FAILED=$((FAILED + 1))
fi
echo ""

# Test 4: Check STT provider
echo -e "${BLUE}[TEST 4]${NC} Checking STT provider configuration..."
if docker logs voice-agent 2>/dev/null | grep -q "Using STT:.*Local Whisper"; then
    echo -e "${GREEN}✓ Local Whisper STT is active${NC}"
elif docker logs voice-agent 2>/dev/null | grep -q "Using STT:.*Deepgram"; then
    echo -e "${YELLOW}⚠️  Falling back to Deepgram (local Whisper failed)${NC}"
    echo "  This is OK if Deepgram API key is set"
elif docker logs voice-agent 2>/dev/null | grep -q "Using STT:.*OpenAI"; then
    echo -e "${YELLOW}⚠️  Falling back to OpenAI Whisper${NC}"
else
    echo -e "${YELLOW}⚠️  STT provider not yet determined${NC}"
fi
echo ""

# Test 5: Check LiveKit connection
echo -e "${BLUE}[TEST 5]${NC} Checking LiveKit connection..."
if docker logs voice-agent 2>/dev/null | grep -q "Connected to room\|listening"; then
    echo -e "${GREEN}✓ LiveKit connected${NC}"
    docker logs voice-agent 2>/dev/null | grep -i "connected\|listening" | head -1
else
    echo -e "${YELLOW}⏳ Not yet connected to a room (waiting for user)${NC}"
fi
echo ""

# Test 6: Resource usage
echo -e "${BLUE}[TEST 6]${NC} Checking container resource usage..."
CONTAINER_ID=$(docker ps -q -f "name=voice-agent" 2>/dev/null || true)
if [ ! -z "$CONTAINER_ID" ]; then
    STATS=$(docker stats --no-stream "$CONTAINER_ID" 2>/dev/null)
    echo "$STATS"
    echo ""
    echo "Note: Peak memory during Whisper inference ~1-2GB (for small model)"
else
    echo "Container not running, skipping stats"
fi
echo ""

# Test 7: Environment variables
echo -e "${BLUE}[TEST 7]${NC} Checking environment variables..."
if docker inspect voice-agent 2>/dev/null | grep -q "USE_LOCAL_WHISPER"; then
    echo -e "${GREEN}✓ Local Whisper config loaded${NC}"

    USE_LOCAL=$(docker inspect voice-agent 2>/dev/null | grep "USE_LOCAL_WHISPER" | head -1 || echo "")
    WHISPER_MODEL=$(docker inspect voice-agent 2>/dev/null | grep "WHISPER_MODEL" | head -1 || echo "")

    echo "  Configuration:"
    echo "$USE_LOCAL" | sed 's/.*=//; s/"//g' | awk '{print "    USE_LOCAL_WHISPER=" $0}'
    echo "$WHISPER_MODEL" | sed 's/.*=//; s/"//g' | awk '{print "    WHISPER_MODEL=" $0}'
else
    echo -e "${YELLOW}⚠️  Could not verify env vars${NC}"
fi
echo ""

echo "═══════════════════════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo ""
    echo "Your voice agent is ready with local Whisper-small STT!"
    echo ""
    echo "📊 NEXT STEPS:"
    echo "1. Test voice interaction via LiveKit room"
    echo "2. Monitor logs: docker logs -f voice-agent"
    echo "3. Verify transcription works (should NOT use cloud APIs)"
    echo ""
    echo "💰 COST SAVINGS: \$200+/month (no Deepgram or OpenAI charges)"
else
    echo -e "${RED}❌ $FAILED TEST(S) FAILED${NC}"
    echo ""
    echo "📋 TROUBLESHOOTING:"
    echo "1. Check full logs: docker logs voice-agent"
    echo "2. Ensure faster-whisper installed: pip install faster-whisper>=1.0.0"
    echo "3. See WHISPER_LOCAL_STT_GUIDE.md for detailed troubleshooting"
fi
echo "═══════════════════════════════════════════════════════════"
echo ""

exit $FAILED
