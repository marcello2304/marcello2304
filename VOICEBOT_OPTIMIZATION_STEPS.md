# Voice Bot Latenz-Optimierung — Schritt A (Quick Win)

## Quick Win: phi:2b Model Switch

**Ziel:** 40% schnellere Antworten durch kleineres, schnelleres LLM
**Aufwand:** 10-15 Minuten
**Expected Result:** 6-15s → 4-9s Latenz

---

## Deployment auf Server 2

### Schritt 1: SSH zu Server 2
```bash
ssh root@46.224.54.65
cd /opt/eppcom-server2
```

### Schritt 2: Neues Model laden
```bash
# Pull the phi:2b model (ca. 1.5 GB)
docker exec ollama ollama pull phi:2b

# Verify it's loaded
docker exec ollama ollama list
# Should show: phi:2b  latest
```

**Dauer:** 2-5 Minuten (abhängig von Netzwerk)

### Schritt 3: LiveKit Agent konfigurieren
Der LiveKit Agent muss phi:2b verwenden. Leider ist das in `agents-playground` hardcoded.

**Option A: Über Environment Variable (wenn unterstützt)**
```bash
# Edit .env on Server 2
echo "OLLAMA_MODEL=phi:2b" >> /opt/eppcom-server2/.env

# Restart container
docker-compose down
docker-compose up -d
```

**Option B: Custom Agent schreiben (nächste Phase)**
Wird in Schritt B implementiert.

### Schritt 4: Test
```bash
# Check if phi:2b is responding
curl http://ollama:11434/api/generate \
  -d '{
    "model": "phi:2b",
    "prompt": "Hello, how are you?",
    "stream": false
  }'

# Expected: Quick response (< 2 seconds)
```

---

## Testing auf Client (Browser)

1. Öffne Voice Bot in Typebot
2. Starte einen Voice Call
3. Sprich eine Frage
4. **Beobachte:**
   - Wie schnell antwortet der Bot?
   - Ist die Antwort Qualität noch okay?
   - Gemessen: Stilles Audioende → erste Stimme (sollte 4-9s sein)

---

## Git-Changes in diesem Repo

✅ `compose-server2.yml` wurde aktualisiert mit:
- Kommentar zu phi:2b vs llama3.2
- `OLLAMA_NUM_THREADS: "4"` für bessere Performance

Diese Änderungen müssen auf Server 2 manuell deployed werden.

---

## Rollback (falls nötig)

```bash
# Falls phi:2b nicht gut funktioniert:
docker exec ollama ollama pull llama3.2:3b
# Agent wird wieder langsam, aber qualitativ besser
```

---

## Next Steps (Phase B)

Nach erfolgreichem Test von phi:2b:
1. Streaming Token aktivieren (Agent Code)
2. Partial Transcripts verarbeiten
3. Expected: weitere -10% Latenz

---

## Metrics to Track

**Before phi:2b:**
- Latency: 6-15s
- Token/s: ~2 tokens/second
- Response Time: sehr langsam für Voice

**After phi:2b (Expected):**
- Latency: 4-9s (-40%)
- Token/s: ~3.3 tokens/second
- Response Time: akzeptabel für Voice

---

## Troubleshooting

### "Model phi:2b not found"
```bash
docker exec ollama ollama pull phi:2b
# Verify with: docker exec ollama ollama list
```

### "Response still slow"
1. Check if phi:2b is actually loaded:
   ```bash
   docker logs livekit-agent | grep phi
   ```
2. Check CPU usage:
   ```bash
   docker stats ollama
   ```
3. If still slow: May need Option B (Custom Agent with streaming)

### "Quality is bad"
phi:2b is optimized for speed, not quality. Options:
- Use neural-chat:7b (better, but slower)
- Move to Phase B with Cartesia (best solution)

---

**Status:** Ready to deploy to Server 2
