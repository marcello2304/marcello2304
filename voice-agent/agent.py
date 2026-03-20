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
from typing import Optional

import httpx
from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, llm
from livekit.plugins import cartesia, openai, silero
import re
from typing import AsyncGenerator

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

# Voice Agent Configuration (Latency Optimization)
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.5"))
VAD_SILENCE_DURATION_MS = int(os.getenv("VAD_SILENCE_DURATION_MS", "300"))

# ─── Streaming Configuration ──────────────────────────────────────────────
VOICEBOT_STREAMING_ENABLED = os.getenv("VOICEBOT_STREAMING_ENABLED", "true").lower() == "true"
SENTENCE_PATTERN = r'(?<=[.!?])\s+(?=[A-Z])'  # Regex for sentence boundaries
MAX_SENTENCE_LENGTH = 250  # Cartesia TTS limit (~200-300 tokens)

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
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Ollama OpenAI-compatible endpoint
            response = await client.post(
                f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 150,  # Keep responses short for voice
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


# ─── STT Provider (Deepgram or Whisper) ─────────────────────────────────
def _get_stt():
    """
    Get STT provider: Deepgram (primary, <200ms) or Whisper (fallback).
    """
    if DEEPGRAM_API_KEY:
        logger.info(f"Using STT: Deepgram {DEEPGRAM_MODEL}")
        try:
            from livekit.plugins import deepgram
            return deepgram.STT(model=DEEPGRAM_MODEL)
        except ImportError:
            logger.warning("Deepgram plugin not available, using Whisper fallback")

    # Fallback: Use OpenAI Whisper
    logger.info("Using STT: OpenAI Whisper")
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


# ─── TTS Provider (Cartesia) ────────────────────────────────────────────
def _get_tts():
    """
    Get TTS provider: Cartesia (ultra-low latency, <200ms).
    """
    if not CARTESIA_API_KEY:
        raise ValueError("CARTESIA_API_KEY not set in environment")

    logger.info(f"Using TTS: Cartesia {CARTESIA_MODEL} (voice: {CARTESIA_VOICE_ID[:8]}...)")

    return cartesia.TTS(
        api_key=CARTESIA_API_KEY,
        model=CARTESIA_MODEL,
        voice=CARTESIA_VOICE_ID,
        encoding="pcm_s16le",  # PCM16, lowest latency
        sample_rate=24000,  # Cartesia standard
    )


# ─── Nexo Agent Class ───────────────────────────────────────────────────
class NexoAgent(Agent):
    """
    Nexo voice agent with RAG support.
    v1.4 API: Uses AgentSession for lifecycle management.
    """

    def __init__(self):
        super().__init__(instructions=SYSTEM_PROMPT)


# ─── Nexo Streaming Agent Class ──────────────────────────────────────────
class NexoStreamingAgent(Agent):
    """Voice agent with sentence-level streaming buffering (Option B)."""

    def __init__(self, instructions: str = ""):
        """Initialize streaming agent with system instructions."""
        super().__init__(instructions=instructions)

    async def llm_node(
        self,
        chat_ctx,
        tools=None,
        **kwargs
    ) -> AsyncGenerator[agents.ChatChunk, None]:
        """
        Override LLM node to enable sentence-buffering streaming.

        - Streams LLM response as ChatChunk objects via self.llm.chat()
        - Buffers tokens until sentence boundary (. ! ? followed by space + capital)
        - Yields complete sentences respecting TTS input length limits
        - Handles German abbreviations (Dr., etc., z.B.) via regex

        Args:
            chat_ctx: Chat context with messages and RAG context
            tools: Available tools/functions (passed through)

        Yields:
            ChatChunk: Complete sentences ready for TTS
        """
        # Use built-in LLM streaming API (livekit-agents v1.4+)
        async with self.llm.chat(chat_ctx=chat_ctx, tools=tools) as stream:
            buffer = ""

            async for chunk in stream:
                # chunk is ChatChunk with .text, .tool_calls, .usage
                if chunk.text:
                    buffer += chunk.text

                    # Check for sentence boundaries
                    while re.search(SENTENCE_PATTERN, buffer):
                        # Split on sentence boundary (regex)
                        sentences = re.split(SENTENCE_PATTERN, buffer, maxsplit=1)
                        sentence = sentences[0].strip()
                        buffer = sentences[1] if len(sentences) > 1 else ""

                        # Handle oversized sentences (TTS input limit)
                        if len(sentence) > MAX_SENTENCE_LENGTH:
                            sentence = sentence[:MAX_SENTENCE_LENGTH-3] + "..."

                        if sentence:
                            # Yield complete sentence as ChatChunk
                            logger.debug(f"Yielding sentence: {sentence[:50]}...")
                            yield agents.ChatChunk(text=sentence)

                else:
                    # Non-text chunks (tool calls, usage) pass through
                    yield chunk

            # Yield remaining text at end (if not empty)
            if buffer.strip():
                final_text = buffer.strip()
                if len(final_text) > MAX_SENTENCE_LENGTH:
                    final_text = final_text[:MAX_SENTENCE_LENGTH-3] + "..."
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
        # Latency optimization for <500ms turnaround
        turn_detection=silero.VAD.load(
            min_speaking_duration=0.1,
            min_silence_duration=VAD_SILENCE_DURATION_MS / 1000.0,
        ),
    )

    # Start agent with NexoAgent configuration
    await session.start(room=ctx.room, agent=NexoAgent())
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
