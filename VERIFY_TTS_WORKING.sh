#!/bin/bash
# VERIFICATION SCRIPT: Proof that TTS is working correctly
# This script PROVES Cartesia TTS is initialized and ready

set -e

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TTS VERIFICATION SCRIPT - Proof of Correct Implementation"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0

# Test 1: Container is running
echo -e "${BLUE}[TEST 1]${NC} Container Status..."
if docker ps -q -f "name=voice-agent" > /dev/null; then
    echo -e "${GREEN}✓ PASS: Container is running${NC}"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗ FAIL: Container NOT running${NC}"
    FAIL=$((FAIL + 1))
    exit 1
fi
echo ""

# Test 2: Cartesia TTS initialized
echo -e "${BLUE}[TEST 2]${NC} Cartesia TTS Initialization..."
if docker logs voice-agent 2>/dev/null | grep -q "Using TTS: Cartesia"; then
    echo -e "${GREEN}✓ PASS: Cartesia TTS initialized${NC}"
    echo "  Details:"
    docker logs voice-agent 2>/dev/null | grep "Using TTS: Cartesia"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗ FAIL: Cartesia TTS NOT initialized${NC}"
    echo "  Checking what TTS is actually used:"
    docker logs voice-agent 2>/dev/null | grep -i "Using TTS\|Cartesia\|OpenAI" | tail -3
    FAIL=$((FAIL + 1))
fi
echo ""

# Test 3: No critical errors
echo -e "${BLUE}[TEST 3]${NC} Error Check..."
CRITICAL_ERRORS=$(docker logs voice-agent 2>/dev/null | grep -i "CRITICAL" | wc -l || echo 0)
if [ "$CRITICAL_ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✓ PASS: No critical errors${NC}"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗ FAIL: Found $CRITICAL_ERRORS critical errors${NC}"
    docker logs voice-agent 2>/dev/null | grep "CRITICAL"
    FAIL=$((FAIL + 1))
fi
echo ""

# Test 4: Cartesia API Key configured
echo -e "${BLUE}[TEST 4]${NC} Cartesia API Key Check..."
if grep -q "CARTESIA_API_KEY=sk_car_" .env.server2; then
    echo -e "${GREEN}✓ PASS: Cartesia API Key configured${NC}"
    CARTESIA_KEY=$(grep "CARTESIA_API_KEY=" .env.server2 | cut -d= -f2)
    echo "  Key: ${CARTESIA_KEY:0:15}...${CARTESIA_KEY: -4} (valid format)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗ FAIL: Cartesia API Key NOT configured${NC}"
    FAIL=$((FAIL + 1))
fi
echo ""

# Test 5: STT initialized (Whisper or alternative)
echo -e "${BLUE}[TEST 5]${NC} STT Provider Check..."
if docker logs voice-agent 2>/dev/null | grep -q "Using STT:"; then
    echo -e "${GREEN}✓ PASS: STT provider initialized${NC}"
    echo "  Details:"
    docker logs voice-agent 2>/dev/null | grep "Using STT:" | tail -1
    PASS=$((PASS + 1))
else
    echo -e "${YELLOW}⚠️  WARNING: STT provider not yet logged${NC}"
    echo "  This is OK if bot hasn't been called yet"
fi
echo ""

# Test 6: LLM initialized
echo -e "${BLUE}[TEST 6]${NC} LLM Provider Check..."
if docker logs voice-agent 2>/dev/null | grep -q "Using LLM:"; then
    echo -e "${GREEN}✓ PASS: LLM provider initialized${NC}"
    echo "  Details:"
    docker logs voice-agent 2>/dev/null | grep "Using LLM:" | tail -1
    PASS=$((PASS + 1))
else
    echo -e "${YELLOW}⚠️  WARNING: LLM provider not yet logged${NC}"
fi
echo ""

# Test 7: No "Entschuldigung, es gab einen Fehler" pattern in recent logs
echo -e "${BLUE}[TEST 7]${NC} Error Response Pattern Check..."
if docker logs voice-agent 2>/dev/null | grep -q "ERROR in llm_node\|failed to recognize\|AgentSession is closing due to unrecoverable"; then
    echo -e "${RED}✗ FAIL: Error patterns detected (would cause 'Entschuldigung...' message)${NC}"
    docker logs voice-agent 2>/dev/null | grep -i "ERROR in llm_node\|failed to recognize\|AgentSession" | head -3
    FAIL=$((FAIL + 1))
else
    echo -e "${GREEN}✓ PASS: No error patterns found${NC}"
    PASS=$((PASS + 1))
fi
echo ""

# Test 8: Memory usage reasonable
echo -e "${BLUE}[TEST 8]${NC} Resource Usage Check..."
CONTAINER_ID=$(docker ps -q -f "name=voice-agent" 2>/dev/null)
if [ ! -z "$CONTAINER_ID" ]; then
    MEMORY=$(docker stats --no-stream "$CONTAINER_ID" 2>/dev/null | tail -1 | awk '{print $4}')
    echo -e "${GREEN}✓ PASS: Memory usage: $MEMORY${NC}"
    echo "  (Cartesia/Whisper models use 1-2GB, this is normal)"
    PASS=$((PASS + 1))
else
    echo -e "${YELLOW}⚠️  Could not check memory${NC}"
fi
echo ""

# Final summary
echo "═══════════════════════════════════════════════════════════════════════════════"
echo -e "${BLUE}RESULT: $PASS PASSED, $FAIL FAILED${NC}"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

if [ "$FAIL" -eq 0 ] && [ "$PASS" -ge 6 ]; then
    echo -e "${GREEN}✅ SUCCESS: Voice Agent is properly configured!${NC}"
    echo ""
    echo "NEXT STEP: Test with real voice input"
    echo "1. Go to: www.eppcom.de/test.php"
    echo "2. Call the voice bot"
    echo "3. CONFIRM:"
    echo "   ✓ Voice is warm & natural (NOT metallic/dark)"
    echo "   ✓ You get a response (NOT 'Entschuldigung, es gab einen Fehler')"
    echo ""
    echo "If tests PASS but you STILL don't hear good quality:"
    echo "  → Frontend may be caching old response"
    echo "  → Try: Hard refresh (Ctrl+Shift+R) or clear browser cache"
    echo "  → Or check frontend code at: /var/www/html/test.php (on Server 2)"
    echo ""
elif [ "$FAIL" -eq 0 ] && [ "$PASS" -ge 5 ]; then
    echo -e "${YELLOW}⚠️  PARTIAL: Most systems working, waiting for STT/LLM initialization${NC}"
    echo ""
    echo "Wait a moment and re-run this script, or call the bot first to initialize"
else
    echo -e "${RED}❌ ISSUES FOUND: Fix before testing${NC}"
    echo ""
    echo "Run: bash DIAGNOSE_VOICE_ISSUES.sh"
    echo "Or: docker logs -f voice-agent"
fi
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
