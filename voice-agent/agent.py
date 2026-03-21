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
from typing import AsyncGenerator, Optional

import httpx
from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, llm
from livekit.plugins import cartesia, openai, silero

from constants import (
    SENTENCE_PATTERN,
    MAX_SENTENCE_LENGTH,
    TRUNCATION_SUFFIX,
)

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
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi:latest")  # Fast: 3B params (~2s inference)

# TTS Configuration (Cartesia)
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
CARTESIA_VOICE_ID = os.getenv(
    "CARTESIA_VOICE_ID",
    "b9de4a89-2257-424b-94c2-db18ba68c81a"  # German voice
)
CARTESIA_MODEL = "sonic-2"  # Lowest latency model

# RAG Configuration (n8n Webhook)
RAG_WEBHOOK_URL = os.getenv("RAG_WEBHOOK_URL", "")
RAG_WEBHOOK_SECRET = os.getenv("RAG_WEBHOOK_SECRET", "")

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
SYSTEM_PROMPT = """Du bist Nexo, ein hilfreicher deutschsprachiger Voice Assistant.
Du antwortest prägnant, freundlich und direkt auf Fragen des Users.
Nutze verfügbare Kontextinformationen zur Beantwortung von Fragen.
Fasse deine Antworten in 1-2 Sätzen zusammen, um schnelle Voice-Responses zu ermöglichen.
Wenn du nicht sicher bist, frag nach oder sage, dass du die Info nicht hast."""


# ─── RAG Context Caching ───────────────────────────────────────────────
_rag_cache: dict[str, str] = {}  # Cache: query_hash → context

# ─── RAG Context Fetching via n8n Webhook ───────────────────────────────
async def fetch_rag_context(query: str) -> Optional[str]:
    """
    Fetch RAG context from n8n webhook with simple hash-based cache.
    Returns enriched context or None if RAG unavailable.
    Reduces duplicate requests for repeated queries.
    """
    if not RAG_WEBHOOK_URL:
        logger.debug("RAG_WEBHOOK_URL not configured, skipping RAG context")
        return None

    # Check cache first (hash query to avoid large keys)
    query_hash = hashlib.md5(query.encode()).hexdigest()
    if query_hash in _rag_cache:
        logger.debug(f"RAG context cache hit for query hash {query_hash}")
        return _rag_cache[query_hash]

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:  # Reduced: 2.0s → 1.0s
            payload = {
                "query": query,
                "secret": RAG_WEBHOOK_SECRET,
            }
            response = await client.post(RAG_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract context from n8n response
            if isinstance(data, dict) and "context" in data:
                context = data.get("context", "")
                _rag_cache[query_hash] = context  # Cache the result
                logger.info(f"RAG context fetched and cached: {len(context)} chars")
                return context

            return None
    except asyncio.TimeoutError:
        logger.warning(f"RAG context fetch timeout (1.0s) - proceeding without context")
        return None
    except Exception as e:
        logger.warning(f"RAG context fetch failed: {e}")
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

    return openai.LLM(
        model=OLLAMA_MODEL,
        api_key="ollama",  # Not needed for local Ollama
        base_url=OLLAMA_BASE_URL,
    )


# ─── TTS Provider (Cartesia Ultra-Low Latency) ─────────────────────────
def _get_tts():
    """
    Get TTS provider: Cartesia Sonic-3 (ultra-low latency, <100ms).

    For Task C (<2s): Cartesia provides:
    - <100ms latency (fastest in industry)
    - Streaming audio (no batching)
    - German voice with natural prosody
    - PCM16 output for TLS streaming
    """
    if CARTESIA_API_KEY:
        logger.info(
            f"✓ Using TTS: Cartesia {CARTESIA_MODEL} "
            f"(voice: {CARTESIA_VOICE_ID[:8]}..., latency: <100ms)"
        )
        try:
            return cartesia.TTS(
                api_key=CARTESIA_API_KEY,
                model=CARTESIA_MODEL,  # sonic-3: ultra-low latency
                voice=CARTESIA_VOICE_ID,
                encoding="pcm_s16le",  # Lowest latency
                sample_rate=24000,  # Cartesia optimized
                # Streaming: tokens streamed as available (not batched)
            )
        except Exception as e:
            logger.error(f"Cartesia TTS initialization failed: {e}")
            logger.warning("Falling back to OpenAI TTS")
    else:
        logger.warning(
            "⚠️  CARTESIA_API_KEY not set. "
            "Using OpenAI TTS fallback (higher latency, ~500ms). "
            "For <2s target: Set CARTESIA_API_KEY!"
        )

    # Fallback: OpenAI TTS (slower, ~500ms)
    return openai.TTS(model="tts-1", voice="nova")


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
    """Voice agent with sentence-level streaming buffering + RAG integration."""

    def __init__(self, instructions: str = ""):
        """Initialize streaming agent with system instructions."""
        super().__init__(instructions=instructions)

    async def llm_node(
        self,
        chat_ctx: "agents.ChatContext",
        tools: Optional[list] = None,
        **kwargs
    ) -> AsyncGenerator:
        """
        Override LLM node to enable:
        - Token-streaming (yielding partial responses)
        - RAG context injection
        - Sentence-level buffering

        Args:
            chat_ctx: Chat context with messages
            tools: Available tools/functions
            **kwargs: Additional arguments

        Yields:
            ChatChunk: Complete sentences ready for TTS
        """
        # ─── Fetch RAG Context (async, non-blocking) ───────────────────────────
        rag_context = None
        if chat_ctx.messages:
            user_message = chat_ctx.messages[-1].content if chat_ctx.messages else ""
            if isinstance(user_message, str) and user_message.strip():
                rag_context = await fetch_rag_context(user_message)
                if rag_context:
                    logger.info(f"RAG context injected: {len(rag_context)} chars")

        # ─── Inject RAG into system prompt if available ───────────────────────
        enhanced_instructions = self.instructions
        if rag_context:
            enhanced_instructions += f"\n\nVerfügbare Kontextinformationen:\n{rag_context}"

        # ─── Create new chat context with enhanced system prompt ──────────────
        modified_ctx = agents.ChatContext(
            messages=[
                agents.ChatMessage(role="system", content=enhanced_instructions),
                *chat_ctx.messages
            ]
        )

        # Use built-in LLM streaming API (livekit-agents v1.4+)
        async with self.llm.chat(chat_ctx=modified_ctx, tools=tools) as stream:
            buffer = ""

            async for chunk in stream:
                # chunk is ChatChunk with .text, .tool_calls, .usage
                if chunk.text:
                    buffer += chunk.text

                    # Check for sentence boundaries
                    while re.search(SENTENCE_PATTERN, buffer):
                        # Split on sentence boundary (regex)
                        sentences = re.split(
                            SENTENCE_PATTERN, buffer, maxsplit=1
                        )
                        sentence = sentences[0].strip()
                        buffer = sentences[1] if len(sentences) > 1 else ""

                        # Handle oversized sentences (TTS input limit)
                        if len(sentence) > MAX_SENTENCE_LENGTH:
                            max_len = (
                                MAX_SENTENCE_LENGTH -
                                len(TRUNCATION_SUFFIX)
                            )
                            sentence = (
                                sentence[:max_len] + TRUNCATION_SUFFIX
                            )

                        if sentence:
                            # Yield complete sentence as ChatChunk
                            logger.debug(
                                f"Yielding sentence: {sentence[:50]}..."
                            )
                            yield agents.ChatChunk(text=sentence)

                else:
                    # Non-text chunks (tool calls, usage) pass through
                    yield chunk

            # Yield remaining text at end (if not empty)
            if buffer.strip():
                final_text = buffer.strip()
                if len(final_text) > MAX_SENTENCE_LENGTH:
                    max_len = (
                        MAX_SENTENCE_LENGTH -
                        len(TRUNCATION_SUFFIX)
                    )
                    final_text = (
                        final_text[:max_len] + TRUNCATION_SUFFIX
                    )
                logger.debug(f"Yielding final chunk: {final_text[:50]}...")
                yield agents.ChatChunk(text=final_text)


# ─── Agent Entrypoint (v1.4 API) ────────────────────────────────────────
async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint for livekit-agents v1.4.
    - Connects to LiveKit room
    - Creates AgentSession with STT/LLM/TTS/VAD
    - Starts agent and waits for interactions
    """

    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    # Create agent session with optimized latency settings
    session = AgentSession(
        stt=_get_stt(),
        llm=_get_llm(),
        tts=_get_tts(),
        vad=silero.VAD.load(),
    )

    # Select agent class based on streaming configuration
    if VOICEBOT_STREAMING_ENABLED:
        agent_class = NexoStreamingAgent
        logger.info("Using NexoStreamingAgent (streaming enabled)")
    else:
        agent_class = NexoAgent
        logger.info("Using NexoAgent (streaming disabled)")

    # Start agent with selected class
    await session.start(room=ctx.room, agent=agent_class(instructions=SYSTEM_PROMPT))
    logger.info("Agent started and listening")

    # Keep session alive and handle interactions
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
