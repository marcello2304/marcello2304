#!/bin/bash
# Diagnose script for voice agent issues
# Run this when you're getting errors or voice quality issues

set -e

echo "═══════════════════════════════════════════════════════════"
echo "VOICE AGENT DIAGNOSTIC TOOL"
echo "═══════════════════════════════════════════════════════════"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ISSUES=0

# Test 1: Container running
echo -e "${BLUE}[CHECK 1/8]${NC} Container status..."
if docker ps -q -f "name=voice-agent" > /dev/null; then
    echo -e "${GREEN}✓ Container is running${NC}"
else
    echo -e "${RED}✗ Container NOT running${NC}"
    ISSUES=$((ISSUES + 1))
    echo "   FIX: docker run -d --name voice-agent ... (see DEPLOY_LOCAL_WHISPER.sh)"
fi
echo ""

# Test 2: STT initialized
echo -e "${BLUE}[CHECK 2/8]${NC} STT provider..."
STT_LOG=$(docker logs voice-agent 2>/dev/null | grep -i "Using STT:" | tail -1 || echo "")
if [ ! -z "$STT_LOG" ]; then
    echo -e "${GREEN}✓ STT initialized${NC}"
    echo "   $STT_LOG"
else
    echo -e "${YELLOW}⚠️  STT initialization not yet logged${NC}"
    echo "   This is OK if container just started"
fi
echo ""

# Test 3: TTS initialized
echo -e "${BLUE}[CHECK 3/8]${NC} TTS provider..."
TTS_LOG=$(docker logs voice-agent 2>/dev/null | grep -i "Using TTS:" | tail -1 || echo "")
if [ ! -z "$TTS_LOG" ]; then
    echo -e "${GREEN}✓ TTS initialized${NC}"
    echo "   $TTS_LOG"

    # Check if it's the new natural voice
    if echo "$TTS_LOG" | grep -q "Bella"; then
        echo -e "${GREEN}✓ Using natural 'Bella' voice (warm, not metallic)${NC}"
    elif echo "$TTS_LOG" | grep -q "OpenAI"; then
        echo -e "${GREEN}✓ Fallback to OpenAI TTS (high quality)${NC}"
    else
        echo -e "${YELLOW}⚠️  Check voice quality${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  TTS initialization not yet logged${NC}"
fi
echo ""

# Test 4: LLM initialized
echo -e "${BLUE}[CHECK 4/8]${NC} LLM provider..."
LLM_LOG=$(docker logs voice-agent 2>/dev/null | grep -i "Using LLM:" | tail -1 || echo "")
if [ ! -z "$LLM_LOG" ]; then
    echo -e "${GREEN}✓ LLM initialized${NC}"
    echo "   $LLM_LOG"
else
    echo -e "${YELLOW}⚠️  LLM initialization not yet logged${NC}"
fi
echo ""

# Test 5: Check for critical errors
echo -e "${BLUE}[CHECK 5/8]${NC} Critical errors..."
ERRORS=$(docker logs voice-agent 2>/dev/null | grep -i "CRITICAL\|FATAL" | wc -l || echo 0)
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✓ No critical errors${NC}"
else
    echo -e "${RED}✗ Found $ERRORS critical errors:${NC}"
    docker logs voice-agent 2>/dev/null | grep -i "CRITICAL\|FATAL" | tail -5
    ISSUES=$((ISSUES + 1))
fi
echo ""

# Test 6: Check for "Entschuldigung, es gab einen Fehler..." errors
echo -e "${BLUE}[CHECK 6/8]${NC} Processing errors (that cause 'Entschuldigung...' message)..."
PROCESSING_ERRORS=$(docker logs voice-agent 2>/dev/null | grep -i "ERROR in llm_node\|failed to recognize\|AgentSession is closing" | wc -l || echo 0)
if [ "$PROCESSING_ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✓ No processing errors found${NC}"
else
    echo -e "${RED}✗ Found $PROCESSING_ERRORS processing errors:${NC}"
    docker logs voice-agent 2>/dev/null | grep -i "ERROR in llm_node\|failed to recognize\|AgentSession is closing" | tail -10
    ISSUES=$((ISSUES + 1))
    echo ""
    echo "   POSSIBLE CAUSES:"
    echo "   1. STT failed (no speech recognized) → check microphone"
    echo "   2. LLM timeout → check Ollama is running"
    echo "   3. RAG timeout → check RAG webhook URL"
    echo "   4. TTS failed → check Cartesia/OpenAI API keys"
fi
echo ""

# Test 7: Check Ollama connectivity
echo -e "${BLUE}[CHECK 7/8]${NC} Ollama LLM server..."
OLLAMA_URL=$(docker inspect voice-agent 2>/dev/null | grep -o "OLLAMA_BASE_URL=[^\"]*" | cut -d= -f2 || echo "http://ollama:11434")
echo "   Testing: $OLLAMA_URL"

if docker exec voice-agent curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama server is reachable${NC}"

    # Check if model is loaded
    MODEL=$(docker inspect voice-agent 2>/dev/null | grep -o "OLLAMA_MODEL=[^\"]*" | cut -d= -f2 || echo "phi:latest")
    if docker exec voice-agent curl -s "$OLLAMA_URL/api/tags" | grep -q "$MODEL"; then
        echo -e "${GREEN}✓ Model '$MODEL' is available${NC}"
    else
        echo -e "${YELLOW}⚠️  Model '$MODEL' not found, checking available models...${NC}"
        docker exec voice-agent curl -s "$OLLAMA_URL/api/tags" | grep -o '"name":"[^"]*' | cut -d'"' -f4 | head -5
    fi
else
    echo -e "${RED}✗ Ollama server NOT reachable at $OLLAMA_URL${NC}"
    ISSUES=$((ISSUES + 1))
    echo "   FIX: Check Ollama is running: docker ps | grep ollama"
fi
echo ""

# Test 8: Recent successful interactions
echo -e "${BLUE}[CHECK 8/8]${NC} Recent interactions..."
INTERACTIONS=$(docker logs voice-agent 2>/dev/null | grep "Sentence #" | wc -l || echo 0)
if [ "$INTERACTIONS" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $INTERACTIONS successful interactions${NC}"
    echo "   Last 3 sentences:"
    docker logs voice-agent 2>/dev/null | grep "Sentence #" | tail -3 | sed 's/^/   /'
else
    echo -e "${YELLOW}⚠️  No successful interactions found${NC}"
    echo "   This is OK if bot hasn't been called yet"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════"
if [ "$ISSUES" -eq 0 ]; then
    echo -e "${GREEN}✅ NO MAJOR ISSUES FOUND${NC}"
    echo ""
    echo "If you're still experiencing problems:"
    echo "1. Test with voice input (speak into microphone)"
    echo "2. Check logs for errors: docker logs -f voice-agent"
    echo "3. Verify microphone works: docker logs voice-agent | grep -i 'recognize\\|transcrib'"
else
    echo -e "${RED}❌ FOUND $ISSUES ISSUE(S)${NC}"
    echo ""
    echo "NEXT STEPS:"
    echo "1. See error details above"
    echo "2. Check full logs: docker logs voice-agent | tail -100"
    echo "3. See DEPLOYMENT_STEPS_DE.md for troubleshooting"
fi
echo "═══════════════════════════════════════════════════════════"
echo ""

# Show last 30 seconds of logs
echo -e "${BLUE}RECENT LOGS (last 30 seconds):${NC}"
docker logs voice-agent --tail 50 | tail -30
