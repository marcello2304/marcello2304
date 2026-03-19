"""
Nexo — EPPCOM Voice Bot Agent (livekit-agents v0.12+)
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
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import cartesia, openai, silero

# ─── Logging Setup ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nexo-voice")

# ─── Configuration via Environment ──────────────────────────────────────
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

# STT Configuration (Deepgram primary, Whisper fallback)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-2")

# LLM Configuration (Ollama local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi:2b")  # Fast: 2B params

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

# Voice Assistant Configuration (Latency Optimization)
INTERRUPT_MIN_WORDS = int(os.getenv("INTERRUPT_MIN_WORDS", "0"))  # React immediately
INTERRUPT_SPEECH_DURATION = float(os.getenv("INTERRUPT_SPEECH_DURATION", "0.5"))  # 500ms
MIN_ENDPOINTING_DELAY = float(os.getenv("MIN_ENDPOINTING_DELAY", "0.3"))  # 300ms pause = end


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


# ─── Voice Assistant Prolog (Initialization Hook) ───────────────────────
async def prolog(ctx: JobContext):
    """
    Initialize voice assistant session.
    Subscribe to participant audio automatically.
    """
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Welcome message
    participant = await ctx.room.local_participant.identity
    logger.info(f"Voice session started for participant: {participant}")


# ─── Voice Assistant Entrypoint ────────────────────────────────────────
async def entrypoint(ctx: JobContext):
    """
    Main voice assistant logic.
    - Listens to user speech (STT)
    - Fetches RAG context in parallel
    - Sends to LLM
    - Streams TTS back to user
    - Supports interruptions
    """

    # Initialize VoiceAssistant with streaming and interruption support
    assistant = VoiceAssistant(
        vad=silero.VAD.create(
            min_speaking_duration=0.1,
            min_silence_duration=MIN_ENDPOINTING_DELAY,  # 300ms silence = end utterance
        ),
        stt=_get_stt(),  # Deepgram or Whisper
        llm=_get_llm(),  # LLM (Ollama via OpenAI API)
        tts=_get_tts(),  # Cartesia TTS
        # Interruption settings (allow user to cut off bot)
        allow_interruptions=True,
        interrupt_min_words=INTERRUPT_MIN_WORDS,
        interrupt_speech_duration=INTERRUPT_SPEECH_DURATION,
        # Pre-synthesize next TTS chunk while still speaking
        will_synthesize_assistant_reply=True,
    )

    # Connect assistant to room
    assistant.start(ctx.room, ctx.participant)

    # Process user messages with RAG context
    async def on_message(message: agents.AssistantMessage):
        """Handle messages from user and fetch RAG context if needed."""
        user_text = message.content
        logger.info(f"User: {user_text}")

        # Fetch RAG context in parallel (non-blocking)
        rag_context = await fetch_rag_context(user_text)

        # Get LLM response with RAG context
        response = await get_llm_response(user_text, rag_context)
        logger.info(f"Assistant: {response}")

        return agents.AssistantMessage(content=response)

    # Attach message handler (if using custom message processing)
    # Note: VoiceAssistant handles STT→LLM→TTS automatically
    # This is for additional processing if needed

    await asyncio.Event().wait()  # Keep running indefinitely


# ─── STT Provider (Deepgram or Whisper) ─────────────────────────────────
def _get_stt():
    """
    Get STT provider: Deepgram (primary, <200ms) or Whisper (fallback).
    """
    if DEEPGRAM_API_KEY:
        logger.info(f"Using STT: Deepgram {DEEPGRAM_MODEL}")
        # Assuming livekit-plugins-deepgram available
        # Otherwise fallback to Whisper
        try:
            from livekit.plugins import deepgram
            return deepgram.STT(model=DEEPGRAM_MODEL)
        except ImportError:
            logger.warning("Deepgram plugin not available, using Whisper fallback")

    # Fallback: Use OpenAI Whisper (slower but functional)
    logger.info("Using STT: OpenAI Whisper")
    return openai.STT(model="whisper-1")


# ─── LLM Provider (Ollama via OpenAI API) ──────────────────────────────
def _get_llm():
    """
    Get LLM provider using Ollama's OpenAI-compatible API.
    """
    logger.info(f"Using LLM: Ollama {OLLAMA_MODEL} at {OLLAMA_BASE_URL}")

    # OpenAI client can point to Ollama
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


# ─── Worker Options & Entrypoint ───────────────────────────────────────
def prolog_fn(ctx: JobContext):
    """Prolog: Initialize connection."""
    asyncio.create_task(prolog(ctx))


def entrypoint_fn(ctx: JobContext):
    """Entrypoint: Start voice assistant."""
    asyncio.create_task(entrypoint(ctx))


if __name__ == "__main__":
    worker_opts = WorkerOptions(
        prolog_fn=prolog_fn,
        entrypoint_fn=entrypoint_fn,
        api_connect_options=agents.APIConnectOptions(
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        ),
    )

    cli.run_app(
        WorkerOptions(
            prolog_fn=prolog_fn,
            entrypoint_fn=entrypoint_fn,
            api_connect_options=agents.APIConnectOptions(
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_API_SECRET,
            ),
        )
    )
