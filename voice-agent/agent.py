"""
Nexo — EPPCOM Voice Bot Agent (livekit-agents v1.4+)
- STT: Deepgram (streaming) or Whisper (fallback) — DSGVO-konform
- LLM: Ollama phi:2b (local, ~40ms latency) or llama3.2:3b (better quality)
- TTS: Cartesia AI Sonic-2 (ultra-natürlich, ultra-schnell, <200ms)
- VAD: Silero (0.3s endpointing für niedrige Latenz)
- Interruption: True (User kann Bot unterbrechen)
- RAG: n8n Webhook für kontextuelle Antworten

Deployment: Docker auf Server 2 (46.224.54.65)
Optimized for <500ms turn-around (STT→LLM→TTS)
"""
import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Optional

import httpx
from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, APIConnectOptions, JobContext, WorkerOptions, cli, llm
from livekit.plugins import cartesia, openai, silero


# ─── Logging Setup ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nexo-voice")

# ─── Configuration via Environment ──────────────────────────────────────
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://livekit:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

# STT Configuration
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-2")

# Local Whisper Configuration (self-hosted, zero-cost)
USE_LOCAL_WHISPER = os.getenv("USE_LOCAL_WHISPER", "true").lower() == "true"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # tiny, small, base, medium, large
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")  # auto, cuda, cpu

# LLM Configuration (Ollama local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://10.0.0.3:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-nothink:latest")  # Fast 2B model, TTFT <0.5s on CPU

# TTS Configuration (Cartesia Primary - Ultra-Low Latency)
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
# Voice ID - use "default" or valid UUID for natural German voice
# If empty, Cartesia uses default German voice
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "default")
CARTESIA_MODEL = "sonic-2"  # Lowest latency model

# OpenAI TTS as fallback (requires API key)
OPENAI_API_KEY_EXPLICIT = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TTS_ENABLED = bool(OPENAI_API_KEY_EXPLICIT and not OPENAI_API_KEY_EXPLICIT.startswith("sk-dummy"))

# RAG Configuration (n8n Webhook)
RAG_WEBHOOK_URL = os.getenv("RAG_WEBHOOK_URL", "")
RAG_WEBHOOK_SECRET = os.getenv("RAG_WEBHOOK_SECRET", "")
RAG_TENANT_ID = os.getenv("RAG_TENANT_ID", "a0000000-0000-0000-0000-000000000001")  # eppcom UUID

# Voice Agent Configuration (Ultra-Low Latency for <2s target)
# Task C: Cartesia TTS + Deepgram STT + Token-Streaming LLM
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.5"))
# Ultra-aggressive VAD: 200ms → 100ms für <2s target
VAD_SILENCE_DURATION_MS = int(os.getenv("VAD_SILENCE_DURATION_MS", "100"))

# ─── Streaming Configuration ──────────────────────────────────────────────
# Token-Streaming aktiviert für -50% Latency (3-7s statt 6-15s)
VOICEBOT_STREAMING_ENABLED = os.getenv("VOICEBOT_STREAMING_ENABLED", "true").lower() == "true"
ENABLE_PARTIAL_TRANSCRIPTS = os.getenv("ENABLE_PARTIAL_TRANSCRIPTS", "true").lower() == "true"

# ─── System Prompt with RAG Context ─────────────────────────────────────
SYSTEM_PROMPT = """Du bist Nexo, der KI-Assistent von EPPCOM Solutions - Experte für Workflow-Automatisierung und KI-Chatbots.

ANTWORTSTIL:
- Formuliere IMMER in eigenen Worten, nie copy-paste
- Halte Antworten prägnant (max 2-3 Sätze für Voice)
- Professionell aber zugänglich, kundenorientiert
- Nutze bereitgestellte Kontextinformationen zur Beantwortung

Wenn du nicht sicher bist, frag nach oder sage ehrlich, dass du die Info nicht hast."""


# ─── RAG Context Caching ───────────────────────────────────────────────
_rag_cache: dict[str, str] = {}  # Cache: query_hash → context

# ─── RAG Context Fetching via n8n Webhook ───────────────────────────────
async def fetch_rag_context(query: str) -> Optional[str]:
    """
    Fetch RAG context from n8n RAG Query webhook.
    Returns enriched system_prompt or None if RAG unavailable.
    Caches results to avoid duplicate requests.
    """
    if not RAG_WEBHOOK_URL:
        logger.debug("RAG_WEBHOOK_URL not configured, skipping RAG context")
        return None

    # Check cache first (hash query to avoid large keys)
    query_hash = hashlib.md5(query.encode()).hexdigest()
    if query_hash in _rag_cache:
        logger.debug(f"RAG cache HIT: {query_hash[:8]}...")
        return _rag_cache[query_hash]

    try:
        # 8.0s timeout: RAG includes vector embedding (~3s) + DB queries (~2-3s)
        async with httpx.AsyncClient(timeout=8.0) as client:
            payload = {
                "tenant_id": RAG_TENANT_ID,  # UUID for n8n RAG Query workflow
                "query": query,
                "transcript": query,  # n8n Workflow erwartet 'transcript'
                "top_k": 5,
            }
            logger.debug(f"RAG fetching: {query[:50]}...")
            response = await client.post(RAG_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            # n8n RAG Query returns: { "answer": "...", "sources": [...], ... }
            if isinstance(data, dict):
                # Try different response formats
                answer = data.get("answer") or data.get("response") or data.get("system_prompt") or data.get("context") or ""
                if answer:
                    _rag_cache[query_hash] = answer  # Cache for reuse
                    logger.info(f"RAG fetched: {len(answer)} chars (cached)")
                    return answer

            logger.debug(f"RAG: No answer in response: {list(data.keys())}")
            return None
    except asyncio.TimeoutError:
        logger.warning(f"RAG timeout (8.0s) - proceeding without context")
        return None
    except Exception as e:
        logger.warning(f"RAG fetch failed: {e}")
        return None


# ─── STT Provider (Local Whisper > Deepgram > OpenAI Whisper) ──────────
def _get_stt():
    """
    Get STT provider with fallback chain (preferred: local to avoid API costs):
    1. Local Whisper-small (free, zero-cost, self-hosted)
    2. Deepgram (preferred cloud option, <200ms)
    3. OpenAI Whisper (requires valid API key)
    """
    # ─── Try Local Whisper First (FREE, ZERO-COST) ──────────────────────
    if USE_LOCAL_WHISPER:
        logger.info(f"✓ Using STT: Local Whisper-{WHISPER_MODEL} (self-hosted, zero cost)")
        try:
            from local_whisper_stt import LocalWhisperSTT
            return LocalWhisperSTT(model_size=WHISPER_MODEL, device=WHISPER_DEVICE)
        except ImportError:
            logger.warning("Local Whisper module not available, checking fallbacks...")
        except Exception as e:
            logger.warning(f"Local Whisper initialization failed: {e}, checking fallbacks...")

    # ─── Fallback: Deepgram (Cloud, requires API key) ───────────────────
    if DEEPGRAM_API_KEY:
        logger.info(f"✓ Using STT: Deepgram {DEEPGRAM_MODEL} (cloud, ~200ms latency)")
        try:
            from livekit.plugins import deepgram
            return deepgram.STT(model=DEEPGRAM_MODEL)
        except ImportError:
            logger.warning("Deepgram plugin not available")

    # ─── Fallback: OpenAI Whisper (Cloud, requires valid API key) ────────
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key and not openai_key.startswith("sk-dummy"):
        logger.info("✓ Using STT: OpenAI Whisper (cloud, ~500ms latency)")
        try:
            return openai.STT(model="whisper-1")
        except Exception as e:
            logger.warning(f"OpenAI STT failed: {e}")

    # ⚠️ CRITICAL: No valid STT provider configured
    logger.critical("⚠️⚠️⚠️ NO VALID STT PROVIDER CONFIGURED ⚠️⚠️⚠️")
    logger.critical("⚠️ The bot will NOT recognize speech without one of:")
    logger.critical("  1. USE_LOCAL_WHISPER=true (default, free, self-hosted)")
    logger.critical("  2. DEEPGRAM_API_KEY - Get free tier at https://deepgram.com")
    logger.critical("  3. OPENAI_API_KEY - Set valid OpenAI API key (not dummy key)")
    logger.critical("⚠⚠⚠ Using fallback STT - speech recognition WILL FAIL ⚠⚠⚠")

    # Fallback: try to use OpenAI as last resort (will fail but won't crash at init)
    try:
        os.environ["OPENAI_API_KEY"] = openai_key or "dummy"
        return openai.STT(model="whisper-1")
    except Exception as e:
        logger.error(f"STT initialization failed: {e}")
        return openai.STT(model="whisper-1")


# ─── LLM Provider (Ollama via OpenAI API) ──────────────────────────────
def _get_llm():
    """
    Get LLM provider using Ollama's OpenAI-compatible API.
    """
    logger.info(f"Using LLM: Ollama {OLLAMA_MODEL} at {OLLAMA_BASE_URL}")

    try:
        llm = openai.LLM(
            model=OLLAMA_MODEL,
            api_key="ollama",  # Not needed for local Ollama
            base_url=OLLAMA_BASE_URL,
        )
        logger.info("✓ Ollama LLM initialized successfully")
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize Ollama LLM: {e}")
        logger.warning("Proceeding anyway (will fail at runtime if Ollama unavailable)")
        return openai.LLM(
            model=OLLAMA_MODEL,
            api_key="ollama",
            base_url=OLLAMA_BASE_URL,
        )


# ─── TTS Provider (Cartesia Primary > OpenAI Fallback) ──────────────────
def _get_tts():
    """
    Get TTS provider with natural German voices.

    Primary:
    - Cartesia Sonic-2: Ultra-low latency <100ms, German voice
      Uses default German voice (warm, natural) if no voice ID specified

    Fallback:
    - OpenAI TTS-1: High-quality neural voice ~300ms (if API key available)
    """
    # ─── Primary: Cartesia Sonic-2 (Ultra-Low Latency) ────────────────
    if CARTESIA_API_KEY:
        logger.info(
            f"✓ Using TTS: Cartesia {CARTESIA_MODEL} "
            f"(German voice, ultra-low latency <100ms)"
        )
        try:
            # Build Cartesia TTS kwargs - only add voice if not "default"
            cartesia_kwargs = {
                "api_key": CARTESIA_API_KEY,
                "model": CARTESIA_MODEL,
                "encoding": "pcm_s16le",
                "sample_rate": 24000,
            }

            # Only set voice if not default
            if CARTESIA_VOICE_ID and CARTESIA_VOICE_ID.lower() != "default":
                cartesia_kwargs["voice"] = CARTESIA_VOICE_ID

            return cartesia.TTS(**cartesia_kwargs)

        except Exception as e:
            logger.error(f"Cartesia TTS failed: {e}")
            logger.warning("Falling back to OpenAI TTS")

    # ─── Fallback: OpenAI TTS (if API key available) ────────────────
    if OPENAI_TTS_ENABLED:
        logger.info(
            "✓ Using TTS: OpenAI TTS-1 (nova voice, "
            "high-quality neural, natural German prosody)"
        )
        try:
            return openai.TTS(model="tts-1", voice="nova")
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}")

    # ─── Last resort: Cartesia without custom voice ──────────────────
    logger.warning("⚠️  Using Cartesia with default voice (no API key or config)")
    if CARTESIA_API_KEY:
        return cartesia.TTS(
            api_key=CARTESIA_API_KEY,
            model="sonic-2",
            encoding="pcm_s16le",
            sample_rate=24000,
        )

    # ─── CRITICAL: No TTS provider available ────────────────────────
    logger.critical("⚠️⚠️⚠️ NO TTS PROVIDER CONFIGURED ⚠️⚠️⚠️")
    logger.critical("Set one of:")
    logger.critical("  1. CARTESIA_API_KEY (recommended, ultra-low latency)")
    logger.critical("  2. OPENAI_API_KEY (fallback, high quality)")
    # Return dummy that will fail at runtime
    try:
        return openai.TTS(model="tts-1", voice="nova")
    except:
        return cartesia.TTS(api_key="dummy", model="sonic-2")


# ─── Nexo Agent Class ───────────────────────────────────────────────────
class NexoAgent(Agent):
    """
    Nexo voice agent with RAG support.
    v1.4 API: Uses AgentSession for lifecycle management.
    """

    def __init__(self, instructions: str = SYSTEM_PROMPT):
        super().__init__(instructions=instructions)


# ─── Nexo Streaming Agent Class ──────────────────────────────────────────
class NexoStreamingAgent(Agent):
    """Voice agent with RAG integration (livekit-agents v1.5 API)."""

    def __init__(self, instructions: str = ""):
        super().__init__(instructions=instructions)

    async def llm_node(self, chat_ctx, tools, model_settings):
        """
        Override LLM node for RAG context injection.
        Delegates streaming to the framework's default implementation.
        """
        # ─── Fetch RAG Context ───────────────────────────────────────────
        try:
            user_msg = ""
            for item in reversed(chat_ctx.items):
                if hasattr(item, 'role') and item.role == 'user':
                    user_msg = getattr(item, 'text_content', '') or ''
                    break

            if user_msg.strip():
                rag_context = await fetch_rag_context(user_msg)
                if rag_context:
                    logger.info(f"RAG context injected: {len(rag_context)} chars")
                    chat_ctx = chat_ctx.copy()
                    chat_ctx.add_message(
                        role="system",
                        content=f"Kontextinformationen:\n{rag_context}",
                    )
        except Exception as e:
            logger.warning(f"RAG fetch failed (proceeding without): {e}")

        # ─── Delegate to default LLM node (handles streaming natively) ───
        return Agent.default.llm_node(self, chat_ctx, tools, model_settings)


# ─── Agent Entrypoint (v1.5 API) ────────────────────────────────────────
async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint for livekit-agents v1.5.
    """

    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    # Ollama needs higher timeout (model cold-start can take 15-30s)
    from livekit.agents.voice.agent_session import SessionConnectOptions
    conn_opts = SessionConnectOptions(
        llm_conn_options=APIConnectOptions(max_retry=3, retry_interval=2.0, timeout=60.0),
    )

    session = AgentSession(
        stt=_get_stt(),
        llm=_get_llm(),
        tts=_get_tts(),
        vad=silero.VAD.load(),
        conn_options=conn_opts,
    )

    # Select agent class based on streaming configuration
    if VOICEBOT_STREAMING_ENABLED:
        agent_class = NexoStreamingAgent
        logger.info("Using NexoStreamingAgent (streaming enabled)")
    else:
        agent_class = NexoAgent
        logger.info("Using NexoAgent (streaming disabled)")

    agent = agent_class(instructions=SYSTEM_PROMPT)
    await session.start(room=ctx.room, agent=agent)
    logger.info("Agent started and listening")

    # Greeting message
    await session.say("Hallo! Ich bin Nexo, der KI-Assistent von EPPCOM. Wie kann ich dir helfen?")

    await asyncio.Event().wait()


# ─── Worker Options & CLI ───────────────────────────────────────────────
if __name__ == "__main__":
    worker_opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        ws_url=LIVEKIT_URL,
    )
    cli.run_app(worker_opts)
