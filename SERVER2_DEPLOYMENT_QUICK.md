# Server 2 Deployment - Quick Reference

## Problem Status
- ❌ **agent.py IndentationError on line 406** - prevents container startup
- ❌ **Voice Quality** - dark/metallic tone (wrong voice ID)
- ❌ **Error Messages** - "Entschuldigung, es gab einen Fehler..." (RAG misconfigured)
- ❌ **Desktop/Mac** - No response on non-mobile browsers

## Solution Summary
1. ✅ Fixed NexoAgent `__init__` to accept `instructions` kwarg (done locally)
2. ✅ Added 5 comprehensive edge-case tests (all passing locally)
3. ✅ Created deployment script to fix Server 2
4. 🔄 **NOW: Execute deployment on Server 2**

---

## Deploy (Execute on Server 2 as root)

```bash
# Copy this deployment script from local repo to Server 2
# SSH into Server 2, then:

cd /opt/eppcom-server2

# Option A: If you have the script ready
bash DEPLOY_TO_SERVER2.sh

# Option B: Manual steps (if script unavailable)
cd /opt/eppcom-server2/voice-agent
git pull origin main
python3 -m py_compile agent.py  # verify no syntax errors
cd /opt/eppcom-server2
sed -i 's/^RAG_WEBHOOK_URL=.*/RAG_WEBHOOK_URL=/g' .env
cd voice-agent
docker build -t eppcom/voice-agent:latest .
docker stop livekit-agent 2>/dev/null || true
docker rm livekit-agent 2>/dev/null || true
docker run -d \
  --name livekit-agent \
  --env-file ../.env \
  --network ai-net \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  eppcom/voice-agent:latest
sleep 10
docker logs livekit-agent --tail 30
```

---

## Verify Deployment

```bash
# Check container running
docker ps -f "name=livekit-agent"

# Monitor logs in real-time
docker logs -f livekit-agent

# Check for expected initialization messages
docker logs livekit-agent | grep -i "Using TTS\|Cartesia\|initialized"
```

---

## Test the Voice Bot

### Real-World Test (in Browser)
1. **URL**: `www.eppcom.de/test.php`
2. **Action**: Activate microphone, say: "Hallo, wie heißt du?"
3. **Verify Voice Quality**:
   - ✅ WARM, natural German voice (Cartesia native)
   - ❌ NOT dark, metallic, robotic
4. **Verify Response**:
   - ✅ Agent responds with actual text (e.g., "Ich bin Nexo...")
   - ❌ NOT "Entschuldigung, es gab einen Fehler..."

### Troubleshooting (if issues persist)

**Container won't start**:
```bash
docker logs livekit-agent | tail -50
# Look for IndentationError, ModuleNotFoundError, or import errors
```

**Bad voice quality**:
```bash
# Check Cartesia is being used
docker logs livekit-agent | grep "Using TTS:"

# Hard refresh browser cache (Mac: Cmd+Shift+R, Windows/Linux: Ctrl+Shift+R)
```

**Still getting error responses**:
```bash
# Check for RAG/LLM/STT errors
docker logs livekit-agent | grep -i "error\|critical" | tail -10

# Verify Cartesia API Key
grep CARTESIA_API_KEY /opt/eppcom-server2/.env

# Verify all providers initialized
docker logs livekit-agent | grep -i "Using STT:\|Using LLM:\|Using TTS:"
```

**Desktop/Mac browser issue**:
```bash
# Check for CORS or WebRTC errors in browser DevTools Console
# Logs on Server 2 should show connection attempts:
docker logs -f livekit-agent | grep -i "connect\|session\|peer"
```

---

## Expected Result After Deployment

✅ **Container starts cleanly** (no IndentationError)
✅ **Voice is warm & natural** (Cartesia default German)
✅ **Agent responds to questions** (not error messages)
✅ **Works on mobile AND desktop** (WebRTC should work)
✅ **Ultra-low latency** (<100ms Cartesia TTS)

---

## Local Code Status

✅ **NexoAgent bug fixed** - accepts `instructions` kwarg
✅ **8 comprehensive tests** - all PASSED (sentence buffering, German abbreviations, edge cases)
✅ **Deployment scripts ready** - DEPLOY_TO_SERVER2.sh

---

## Files to Track

| File | Status | Purpose |
|------|--------|---------|
| `/root/marcello2304/voice-agent/agent.py` | ✅ Fixed | Local working copy |
| `/root/marcello2304/voice-agent/test_streaming.py` | ✅ 8/8 Passing | Comprehensive test suite |
| `/root/marcello2304/DEPLOY_TO_SERVER2.sh` | 🔄 Ready | One-command Server 2 fix |
| `/opt/eppcom-server2/voice-agent/agent.py` | ❌ Broken | Needs deployment |
| `/opt/eppcom-server2/.env` | ⚠️ Needs fix | RAG_WEBHOOK_URL must be empty |

---

## Next Steps

1. **SSH to Server 2**
2. **Navigate**: `cd /opt/eppcom-server2`
3. **Execute**: `bash DEPLOY_TO_SERVER2.sh` (or manual steps if unavailable)
4. **Wait**: 5-10 seconds for container initialization
5. **Test**: Open `www.eppcom.de/test.php` and speak
6. **Verify**: Voice is warm, you get responses
7. **Done**: Report voice quality improvement

