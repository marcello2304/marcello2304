# Voice Bot Latenz-Analyse

## 🐢 Identifizierte Bottlenecks

### 1. **WHISPER STT (Speech-to-Text)**
**Problem:** CPU-intensive, baseline 2-5 Sekunden pro Audioblock
- Whisper `base` Model über Ollama (nicht optimiert)
- Läuft CPU-only (keine GPU auf Server 2)
- Wartet auf kompletten Audio-Frame

**Symptom:** "Ich rede → lange Pause → Transkription kommt"

**Lösung:**
- Whisper `tiny` Model (50% schneller, 95% Genauigkeit)
- Oder: Deepgram API (100ms Latenz, cloud)
- Oder: **Cartesia** (streaming STT, real-time)

### 2. **OLLAMA LLM Inference**
**Problem:** llama3.2:3b ohne GPU = 50-200ms pro Token
- Hetzner CX33: CPU-only (2 Cores)
- llama3.2:3b = 3B Parameter = lange Sequenz
- Keepalive: 5m = immer warm (gut)
- Parallelism: 2 = ganz okay

**Symptom:** "Antwort kommt langsam: 'hello... world... is... great...'"

**Schnellere Modelle:**
- `phi:2b` (2B params, 40% schneller)
- `neural-chat:7b` (spezialisiert auf Dialog)
- GPU-Upgrade nötig für llama3

### 3. **PIPER TTS (Text-to-Speech)**
**Problem:** Nicht-streaming, wartet auf kompletten Text
- Piper thorsten-medium braucht 500-1000ms für 1-2 Sätze
- Lädt Audio sequenziell
- Keine Streaming-Chunks

**Symptom:** "Antwort ist da → lange Pause → dann Stimme"

**Lösung:**
- **Cartesia:** Streaming TTS (100ms start latency!)
- ElevenLabs API (aber teuer)
- oder Tacotron2 (schneller aber weniger Qualität)

### 4. **NETZWERK-ROUTING**
**Problem:** Browser → LiveKit → Agent → Ollama → TTS
```
User Audio
  ↓ (WSS)
LiveKit Server (7880)
  ↓ (intern)
LiveKit Agent Container
  ↓ (HTTP)
Ollama Container (11434)
  ↓ (+ TTS Processing)
TTS Output
  ↓ (WSS back to Browser)
User Hears Voice
```

**Total Roundtrips:** 5-7 Hops
**Latency pro Hop:** 10-50ms
**Total:** 50-350ms JUST für Routing

### 5. **SEQUENTIAL Processing (BIGGEST ISSUE!)**
```
1. Listen (wait for audio chunk)
2. Send to STT (Whisper)
3. Wait for transcript
4. Send to LLM (Ollama)
5. Wait for complete response
6. Send to TTS (Piper)
7. Wait for audio
8. Stream back to user
```

**TOTAL LATENCY = SUM of all steps!**
- STT: 2-5s
- LLM: 3-10s (token by token)
- TTS: 0.5-2s
- **Total: 5.5 - 17 seconds!**

---

## 📊 Latenz-Breakdown (Realistic Numbers)

| Component | Latency | Notes |
|-----------|---------|-------|
| Audio Capture & Network | 200ms | User speaking |
| Whisper STT (base) | 3-5s | CPU-bound |
| LLM First Token | 1-2s | Cold start |
| LLM Token Generation | 200-500ms/token | Depends on response length |
| TTS (Piper) | 1-2s | Full response wait |
| Audio Streaming Back | 500ms | Network + buffering |
| **TOTAL** | **6-15s** | From silence to speech |

---

## 🚀 Quick Wins (Low Effort, High Impact)

### 1. **Switch Ollama Model (5 min)**
```yaml
# In compose-server2.yml
environment:
  OLLAMA_MODEL: "phi:2b"  # Instead of llama3.2:3b
```
**Impact:** -40% latency

### 2. **Parallel STT + Early Response (1-2 hours)**
- Don't wait for full transcript
- Send partial transcripts to LLM
- Stream response tokens back DURING generation
- User hears first word in 1-2s instead of 5s

### 3. **Add Cartesia (Medium Effort, Big Impact)**
- Streaming STT (100ms start latency!)
- Streaming TTS (start playing in 100ms!)
- **Total impact: -60% to -70% latency**

---

## 🔥 Recommended Solution Stack

### Tier 1: Quick Fix (Today)
1. Switch `llama3.2:3b` → `phi:2b` (-40%)
2. Enable streaming TTS in Agent Code
3. Document current latency baseline

### Tier 2: Streaming (This Week)
1. Partial Transcript Processing
2. Token-by-Token LLM Streaming
3. TTS Chunks as they arrive

### Tier 3: Cartesia (Next Week)
1. Replace Whisper with Cartesia Streaming STT
2. Replace Piper with Cartesia Streaming TTS
3. End-to-end latency: <2 seconds possible!

---

## 📋 Bottleneck Priority

1. **LLM Model Choice (llama3.2 too slow)** - BIGGEST
2. **Sequential Processing (not streaming)** - BIGGEST  
3. **Whisper STT (CPU-heavy)** - MEDIUM
4. **Piper TTS (non-streaming)** - MEDIUM
5. **Network routing** - SMALL (but adds up)

**Quick Win:** Swap to `phi:2b` = immediate 40% improvement
**Real Win:** Streaming LLM + Cartesia = <2s latency

