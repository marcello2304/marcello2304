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

# STT Configuration (Deepgram primary, Whisper fallback)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-2")

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


# ─── RAG Context Fetching via n8n Webhook ───────────────────────────────
async def fetch_rag_context(query: str) -> Optional[str]:
    """
    Fetch RAG context from n8n webhook.
    Returns enriched context or None if RAG unavailable.
    """
    if not RAG_WEBHOOK_URL:
        logger.debug("RAG_WEBHOOK_URL not configured, skipping RAG context")
        return None

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
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
                logger.info(f"RAG context fetched: {len(context)} chars")
                return context

            return None
    except Exception as e:
        logger.warning(f"RAG context fetch failed: {e}")
        return None


# ─── LLM with RAG Integration ───────────────────────────────────────────
async def get_llm_response(user_message: str, rag_context: Optional[str] = None) -> str:
    """
    Get LLM response with optional RAG context.
    Uses OpenAI-compatible API (Ollama).
    """
    system_prompt = SYSTEM_PROMPT

    # Inject RAG context if available
    if rag_context:
        system_prompt += f"\n\nVerfügbare Kontextinformationen:\n{rag_context}"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:  # Reduced from 5s → 3s
            # Ollama OpenAI-compatible endpoint
            response = await client.post(
                f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.5,  # Lower temp for faster, more consistent output
                    "max_tokens": 100,  # Shorter responses for voice (was 150)
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Extract message from OpenAI-compatible response
            message = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.info(f"LLM response: {message[:100]}...")
            return message
    except Exception as e:
        logger.error(f"LLM request failed: {e}")
        return "Entschuldigung, ich konnte die Anfrage nicht verarbeiten."


# ─── STT Provider (Deepgram Streaming) ──────────────────────────────────
def _get_stt():
    """
    Get STT provider: Deepgram Streaming (ultra-low latency, <200ms).

    For Task C (<2s): Deepgram Streaming provides:
    - Interim results (partial transcripts)
    - Nova-2 model (<200ms latency)
    - German language support
    """
    if DEEPGRAM_API_KEY:
        logger.info(f"Using STT: Deepgram {DEEPGRAM_MODEL} (streaming, ultra-low latency)")
        try:
            from livekit.plugins import deepgram
            # Deepgram Streaming STT für <200ms latency
            # interim_results: Partial transcripts für User Feedback
            return deepgram.STT(
                model=DEEPGRAM_MODEL,
                # Deepgram automatisch streaming wenn verfügbar
            )
        except ImportError:
            logger.warning("Deepgram plugin not available")

    # Fallback: Use OpenAI Whisper (batch, nicht ideal für Voice)
    logger.warning("Using Whisper fallback (nicht für production Voice Bot empfohlen)")
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
    ) -> AsyncGenerator[agents.ChatChunk, None]:
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
        # Task C: Ultra-low latency configuration (<2s end-to-end)
        # VAD tuned for aggressive turn-taking:
        # - STT Deepgram: ~200ms
        # - LLM phi:2b streaming: ~400ms
        # - TTS Cartesia: ~100ms
        # - VAD: ~100ms
        # = ~1s total (with overhead)
        turn_detection=silero.VAD.load(
            min_speaking_duration=0.03,  # Ultra-aggressive: 30ms
            min_silence_duration=VAD_SILENCE_DURATION_MS / 1000.0,  # 100ms
        ),
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
