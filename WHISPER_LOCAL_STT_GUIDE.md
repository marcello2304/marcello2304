# Self-Hosted Whisper-small STT Guide

## Overview

The voice agent now supports **free, self-hosted Whisper-small** instead of paying for Deepgram ($200+/month) or OpenAI API calls (~$0.02 per 1000 tokens).

**Status**: ✅ Default enabled (`USE_LOCAL_WHISPER=true`)

---

## Architecture Change

### Before (Expensive Cloud STT)
```
User speaks → LiveKit → Agent → Deepgram API ($200/month)
                        ↓
                    OpenAI Whisper ($0.02/1K tokens)
```

### After (Free Local STT)
```
User speaks → LiveKit → Agent → Local Whisper-small (140MB, FREE)
                        ↓
                    Deepgram (fallback only)
                        ↓
                    OpenAI (fallback only)
```

---

## Features

| Feature | Local Whisper-small | Deepgram | OpenAI Whisper |
|---------|-------------------|----------|----------------|
| **Cost** | FREE (one-time 140MB download) | $200+/month | ~$0.02 per request |
| **Latency** | ~1s per 10s audio (CPU) | <200ms | ~500ms |
| **Model Size** | 140MB | N/A | N/A |
| **Language** | 99 languages (including German) | 40 languages | 99 languages |
| **Setup** | Automatic (first run downloads model) | API key required | API key required |
| **Privacy** | 100% local, no data sent | Cloud-based | Cloud-based |

---

## Configuration

### Environment Variables (in `.env.server2`)

```bash
# Use local Whisper as primary STT (default: true)
USE_LOCAL_WHISPER=true

# Whisper model size (default: "small")
# Options: "tiny" (39MB), "small" (140MB), "base" (150MB), "medium" (400MB), "large" (3GB)
WHISPER_MODEL=small

# Device for inference (default: "auto")
# Options: "auto" (GPU if available, else CPU), "cuda" (GPU only), "cpu" (CPU only)
WHISPER_DEVICE=auto
```

### Example Configurations

**Budget Mode (Smallest, Slowest)**
```bash
USE_LOCAL_WHISPER=true
WHISPER_MODEL=tiny        # 39MB, ~3-5s per 10s audio
WHISPER_DEVICE=cpu
```

**Balanced Mode (Recommended)**
```bash
USE_LOCAL_WHISPER=true
WHISPER_MODEL=small       # 140MB, ~1s per 10s audio
WHISPER_DEVICE=auto       # Use GPU if available
```

**High Quality Mode (Largest, Fastest)**
```bash
USE_LOCAL_WHISPER=true
WHISPER_MODEL=base        # 150MB, ~500ms per 10s audio (faster inference)
WHISPER_DEVICE=auto
```

---

## How It Works

### First Run (Model Download)

On the first startup with `USE_LOCAL_WHISPER=true`:

1. Agent checks for cached Whisper model (in `~/.cache/huggingface/`)
2. If not found, downloads the model automatically (~140MB for small, ~150MB for base)
3. Model is cached locally for future runs
4. Subsequent starts use cached model (no re-download)

```
[INFO] Loading Whisper-small model (device: auto)...
[INFO] ✓ Whisper-small loaded successfully
```

### Audio Processing

1. User speaks → LiveKit captures audio as raw PCM16
2. LocalWhisperSTT receives audio chunk (duration varies, typically 0.5-2 seconds)
3. Audio converted to float32 and normalized
4. Whisper model runs in-process inference (on CPU or GPU)
5. Returns transcribed text to agent

### Fallback Chain

If local Whisper fails for any reason:

1. **Deepgram** (if `DEEPGRAM_API_KEY` is set)
2. **OpenAI Whisper** (if valid `OPENAI_API_KEY` is set)
3. **Error**: No valid STT configured, speech recognition fails

---

## Performance Characteristics

### Latency (on CPU)

| Model | Model Size | Inference Time | Total Latency |
|-------|-----------|-----------------|----------------|
| tiny  | 39MB      | 3-5s per 10s    | 3.5-5.5s      |
| small | 140MB     | 1s per 10s      | 1.5-2s        |
| base  | 150MB     | 500ms per 10s   | 1-1.5s        |

**Note**: With GPU (NVIDIA/CUDA), latency is ~50-75% faster.

### Memory Usage

| Model | Download Size | RAM (inference) | VRAM (GPU) |
|-------|---------------|-----------------|-----------|
| tiny  | 39MB          | ~600MB          | ~300MB    |
| small | 140MB         | ~1.2GB          | ~800MB    |
| base  | 150MB         | ~1.5GB          | ~1GB      |

---

## Docker Deployment

The Dockerfile automatically includes the local Whisper module:

```dockerfile
COPY local_whisper_stt.py .
RUN pip install faster-whisper>=1.0.0 numpy>=1.24.0
```

### Container Startup

First run (includes model download):
```
docker run --env USE_LOCAL_WHISPER=true \
           --env WHISPER_MODEL=small \
           --volume ~/.cache:/root/.cache \  # Cache models
           voice-agent
```

**Model caching tip**: Mount `~/.cache` as a Docker volume to persist downloaded models across container restarts.

---

## Troubleshooting

### Issue: "Module 'local_whisper_stt' not found"

**Solution**: Ensure `local_whisper_stt.py` is in the same directory as `agent.py`:
```bash
ls -la voice-agent/*.py
# Should show: agent.py, local_whisper_stt.py, constants.py
```

### Issue: "No module named 'faster_whisper'"

**Solution**: Install Python dependencies:
```bash
pip install -r requirements.txt
# or manually: pip install faster-whisper>=1.0.0
```

### Issue: High latency on first run

**Cause**: Model download on first startup (~2-5 minutes for 140MB)

**Solution**: Pre-warm the model by running the agent once, then restart for subsequent uses.

### Issue: Out of Memory (OOM)

**Cause**: Running large models (base, medium, large) on limited RAM

**Solutions**:
1. Use smaller model: `WHISPER_MODEL=tiny` or `WHISPER_MODEL=small`
2. Increase container memory: `docker run -m 4g` (4GB)
3. Use GPU: `WHISPER_DEVICE=cuda` (processes faster, frees CPU memory)

### Issue: Fallback to Deepgram/OpenAI

**Logs will show**:
```
[WARNING] Local Whisper initialization failed: <error>, checking fallbacks...
[INFO] ✓ Using STT: Deepgram nova-2 (cloud, ~200ms latency)
```

**Cause**: Model download failed, or incorrect device configuration

**Solution**: Check logs for specific error, verify internet connectivity for download, or set `USE_LOCAL_WHISPER=false` to skip to cloud providers.

---

## Cost Analysis

### Scenario: 1000 voice interactions per month

**Option A: Cloud STT (Deepgram)**
- Cost: $200/month (free tier often used)
- Setup time: 10 minutes
- Monthly cost: **$200/month**

**Option B: Self-Hosted Whisper-small**
- Cost: 0 (one-time 140MB download)
- Setup time: 5 minutes + 2 minutes first run (model download)
- Server cost: Included in existing Ollama server
- Monthly cost: **$0/month** ✅

**Savings**: **$200/month** (100% cost reduction)

---

## Language Support

Local Whisper supports German (and 99 other languages). The model automatically detects language, but you can optimize for German:

**Current configuration** (`local_whisper_stt.py` line 86):
```python
segments, info = self.model.transcribe(
    audio_array,
    language="de",  # German language hint
    beam_size=5,
)
```

For other languages, modify the `language="de"` parameter:
- `language="en"` (English)
- `language="es"` (Spanish)
- `language="fr"` (French)
- Or omit `language=` for automatic detection

---

## Performance Tuning

### For Faster Inference

**Use GPU (if available)**:
```bash
WHISPER_DEVICE=cuda
```

**Use smaller model**:
```bash
WHISPER_MODEL=tiny  # 39MB, fastest
```

**Reduce beam size** (in `local_whisper_stt.py`):
```python
beam_size=1  # Faster, less accurate (default is 5)
```

### For Better Accuracy

**Use larger model**:
```bash
WHISPER_MODEL=base  # 150MB, more accurate
```

**Increase beam size** (in `local_whisper_stt.py`):
```python
beam_size=10  # Slower, more accurate (default is 5)
best_of=2    # Try 2 hypotheses, pick best
```

---

## Implementation Details

### LocalWhisperSTT Class

**File**: `local_whisper_stt.py`

**Key methods**:
- `__init__(model_size, device)` — Load Whisper model on init
- `asr(data)` — Async transcription of audio chunk
- `_transcribe_sync()` — Synchronous transcription (runs in thread pool)

**Thread safety**: Uses `loop.run_in_executor()` to run blocking Whisper inference in thread pool, preventing async event loop blocking.

### Integration with agent.py

**In `_get_stt()` function** (line 132-168):
1. Try local Whisper first (if `USE_LOCAL_WHISPER=true`)
2. Fall back to Deepgram (if `DEEPGRAM_API_KEY` set)
3. Fall back to OpenAI Whisper (if `OPENAI_API_KEY` set)
4. Critical error if none available

---

## Migration from Cloud STT

### Step 1: Update .env.server2

```bash
USE_LOCAL_WHISPER=true
WHISPER_MODEL=small
WHISPER_DEVICE=auto

# Keep these as fallbacks (optional):
# DEEPGRAM_API_KEY=...
# OPENAI_API_KEY=...
```

### Step 2: Restart container

```bash
docker stop voice-agent
docker rm voice-agent
# (Re-run with new ENV vars)
```

### Step 3: First run (model downloads)

```
[INFO] Loading Whisper-small model (device: auto)...
# ... 2-3 minute wait for 140MB download ...
[INFO] ✓ Whisper-small loaded successfully
```

### Step 4: Test voice interaction

Record a test interaction and verify transcription works.

---

## Future Improvements

- [ ] Real-time streaming transcription (currently processes complete chunks)
- [ ] Vocabulary customization (domain-specific terms for accuracy)
- [ ] Language detection (automatic, currently German-only)
- [ ] Model fine-tuning on customer voice data
- [ ] Quantization (INT8) for 50% faster inference

---

## References

- **faster-whisper**: https://github.com/guillaumekln/faster-whisper
- **OpenAI Whisper**: https://github.com/openai/whisper
- **LiveKit Agents**: https://docs.livekit.io/agents/

---

## Support

**Question**: Should I use local Whisper or cloud providers?

**Answer**:
- **Local Whisper**: Start here. Free, fast enough (1-2s), simple setup.
- **Deepgram**: If latency <200ms is critical and you have budget.
- **OpenAI Whisper**: If highest accuracy is needed, not primary cost constraint.

**Recommended setup**: Local Whisper-small (140MB) as primary, with Deepgram as fallback for high-volume use cases.
