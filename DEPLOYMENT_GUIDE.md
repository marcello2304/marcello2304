# Server 2 Deployment Guide

## System Architecture

```
User Browser
    ↓
nginx (reverse proxy at :80)
    ├→ /test-voice-agent.html → static HTML
    ├→ /api/token → token-server:8765 (JWT generation)
    └→ ws://7880 → livekit:7880 (WebSocket)
        ↓
    LiveKit Server (7880)
        ↓
    livekit-agent (voice bot worker)
        ├→ STT: Local Whisper (or Deepgram)
        ├→ LLM: Ollama (phi:2b)
        ├→ TTS: Cartesia (sonic-2)
        └→ RAG: n8n webhook
```

## Prerequisites

- ✅ Server: 46.224.54.65 (Linux with Docker & Docker Compose)
- ✅ Files committed: `compose-server2.yml`, `livekit.yaml`, updated configs
- ✅ Environment: `.env.server2` with credentials

## Deployment Steps

### 1. Connect to Server 2

```bash
ssh root@46.224.54.65
# Password: Use configured SSH key
cd /root/marcello2304
```

### 2. Review Configuration

```bash
# Check environment variables are correct
cat .env.server2 | head -20

# Check docker-compose is updated
grep -A 5 "env_file:" docker/compose-server2.yml
```

Expected output for env_file:
```yaml
env_file:
  - ../.env.server2
```

### 3. Deploy Stack

```bash
# Option A: Use deployment script (automated)
bash DEPLOY_SERVER2.sh

# Option B: Manual deployment (step-by-step)
cd /root/marcello2304/docker

# Stop old standalone container (if exists)
docker stop voice-agent 2>/dev/null || true
docker rm voice-agent 2>/dev/null || true

# Deploy new stack
docker-compose -f compose-server2.yml up -d --build
```

### 4. Verify Deployment

```bash
# Check running containers
docker-compose -f compose-server2.yml ps

# Expected output: 6 containers running
# - nginx-proxy
# - token-server
# - ollama
# - livekit
# - livekit-agent
# - certbot (optional)

# Check network
docker network ls | grep ai-net
# Expected: ai-net bridge network exists

# Test token endpoint (should return JSON)
curl -s "http://46.224.54.65/api/token?room=test&user=tester" | python3 -m json.tool

# Expected response:
# {
#   "token": "eyJ...",
#   "room": "test",
#   "user": "tester",
#   "livekit_url": "ws://46.224.54.65:7880",
#   "status": "ok"
# }
```

### 5. Monitor Logs

```bash
# Watch livekit-agent logs (voice bot)
docker-compose -f compose-server2.yml logs -f livekit-agent

# Watch livekit server logs
docker-compose -f compose-server2.yml logs -f livekit

# Watch all logs
docker-compose -f compose-server2.yml logs -f
```

Expected log patterns for successful startup:
```
livekit-agent    | 2026-03-22 ... Using STT: Local Whisper-small
livekit-agent    | 2026-03-22 ... Using LLM: Ollama phi:2b
livekit-agent    | 2026-03-22 ... Using TTS: Cartesia sonic-2
livekit-agent    | 2026-03-22 ... Starting worker
livekit          | 2026-03-22 ... listening on :7880
```

## Testing Connection

### Option 1: Quick Test (Browser)

1. Open: http://46.224.54.65/test-voice-agent.html
2. Fill in:
   - LiveKit URL: `ws://46.224.54.65:7880`
   - Room Name: `test-voice-bot`
   - Your Name: `Tester`
3. Click "🔗 Verbinden" (Connect)
4. Expected: Status shows "✅ Verbunden als "Tester" in "test-voice-bot""
5. Click "🎤 Unmuted" to activate microphone
6. Speak a test sentence, wait for response

### Option 2: Diagnostic Test

```bash
# 1. Test token generation
TOKEN=$(curl -s "http://46.224.54.65/api/token?room=test&user=test" | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
echo "Token: $TOKEN"

# 2. Test WebSocket connectivity
curl -i -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://46.224.54.65:7880/

# 3. Check LiveKit health
docker exec livekit curl -s http://localhost:7880/ || echo "LiveKit not responding"

# 4. Check agent registration
docker logs livekit-agent | grep -i "registered\|connected\|error" | tail -5
```

## Troubleshooting

### Issue: WebSocket connection fails
```
❌ Fehler: Could not establish signal connection: Load failed
```

**Solution:**
```bash
# 1. Check livekit is running
docker-compose -f compose-server2.yml ps livekit
# Status should be "Up"

# 2. Check health
docker exec livekit curl -s http://localhost:7880/
# Should return HTTP 200

# 3. Check firewall
sudo ufw allow 7880/tcp
sudo ufw allow 7880/udp
sudo ufw allow 50000:50100/udp
```

### Issue: Token generation fails
```
❌ Fehler: Token-Server nicht erreichbar
```

**Solution:**
```bash
# 1. Check token-server container
docker-compose -f compose-server2.yml ps token-server
# Status should be "Up"

# 2. Check token server directly
docker exec token-server curl -s http://localhost:8765?room=test&user=test
# Should return valid JSON

# 3. Check nginx routing
curl -v http://46.224.54.65/api/token?room=test&user=test
# Look for 200 OK response
```

### Issue: Agent doesn't respond
```
No response from voice bot after speaking
```

**Solution:**
```bash
# 1. Check agent logs for errors
docker logs livekit-agent | grep -i error

# 2. Check if Ollama is running
docker exec ollama curl -s http://localhost:11434/api/version
# Should return model version info

# 3. Check if STT is configured
docker logs livekit-agent | grep -i "STT\|whisper\|deepgram"

# 4. Check if TTS is configured
docker logs livekit-agent | grep -i "TTS\|cartesia\|openai"
```

## Rollback

If deployment has issues:

```bash
# Stop new stack
docker-compose -f docker/compose-server2.yml down

# Check if old voice-agent should be restored
docker start voice-agent 2>/dev/null || echo "Old agent not available"

# Or manually start old agent (Keys aus .env.server2)
docker run -d \
  --name voice-agent \
  --env-file /root/marcello2304/.env.server2 \
  -e LIVEKIT_URL=ws://livekit:7880 \
  eppcom/voice-agent:latest
```

## Next Steps After Successful Deployment

1. **Integrate with Homepage**: Update typebot to use voice endpoint
2. **Configure RAG**: Verify n8n workflows are connected
3. **Performance Tuning**: Monitor latency and optimize as needed
4. **Certificate Setup**: Run certbot for HTTPS
5. **Production Hardening**: Configure firewall, rate limiting, etc.

## Key Files

| File | Purpose |
|------|---------|
| `docker/compose-server2.yml` | Orchestration stack (updated) |
| `docker/livekit.yaml` | LiveKit server config (updated) |
| `.env.server2` | Environment variables (CRITICAL - DO NOT COMMIT) |
| `docker/Dockerfile.token-server` | Token server container |
| `docker/nginx/nginx.conf` | Reverse proxy config |
| `voice-agent/agent.py` | Voice bot worker (v1.4 API) |
| `livekit-token-server.py` | JWT token generator |
| `test-voice-agent.html` | Test interface (v2.x API) |

---

**Last Updated**: 2026-03-22
**Status**: ✅ Ready for deployment
