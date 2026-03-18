"""
EPPCOM Voice Bot Agent (livekit-agents v1.4.6)
- STT: faster-whisper (lokal, DSGVO-konform)
- LLM: n8n RAG Webhook (kein lokales LLM nötig)
- TTS: piper-tts (lokal, DSGVO-konform)
- VAD: silero

Deployment: Docker auf Server 2 (46.224.54.65)
"""
import asyncio
import os
import tempfile
import wave
import logging

import httpx
from livekit import rtc, agents
from livekit.agents import (
    APIConnectOptions,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    stt,
    tts,
    llm,
)
from livekit.plugins import silero

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("eppcom-voice")

# ── Konfiguration via ENV ────────────────────────────────────────────────────
RAG_URL = os.getenv("RAG_URL", os.getenv("N8N_URL", "https://appdb.eppcom.de"))
TENANT_ID = os.getenv("TENANT_ID", "")
API_KEY = os.getenv("API_KEY", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
PIPER_MODEL = os.getenv("PIPER_MODEL", "/opt/piper-models/de_DE-thorsten-medium.onnx")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# ── Whisper-Modell einmal laden ──────────────────────────────────────────────
from faster_whisper import WhisperModel

logger.info(f"Lade Whisper-Modell '{WHISPER_MODEL_SIZE}' (CPU, int8)...")
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
logger.info("Whisper-Modell geladen.")


# ═════════════════════════════════════════════════════════════════════════════
# Custom STT: Faster-Whisper
# ═════════════════════════════════════════════════════════════════════════════
class WhisperSTT(stt.STT):
    def __init__(self):
        super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))

    async def _recognize_impl(self, buffer, *, language=None, conn_options=None) -> stt.SpeechEvent:
        def _transcribe(frames) -> str:
            if hasattr(frames, 'data'):
                audio_data = frames.data.tobytes() if hasattr(frames.data, 'tobytes') else bytes(frames.data)
                sr = frames.sample_rate
            elif isinstance(frames, list):
                parts = []
                sr = 16000
                for f in frames:
                    d = f.data.tobytes() if hasattr(f.data, 'tobytes') else bytes(f.data)
                    parts.append(d)
                    sr = f.sample_rate
                audio_data = b''.join(parts)
            else:
                audio_data = bytes(frames)
                sr = 16000

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                with wave.open(tmp, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sr)
                    wf.writeframes(audio_data)
                tmp.flush()
                segments, _ = whisper_model.transcribe(tmp.name, language="de")
                return " ".join(s.text for s in segments).strip()

        text = await asyncio.to_thread(_transcribe, buffer)
        logger.info(f"STT: '{text}'")

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, language="de")],
        )


# ═════════════════════════════════════════════════════════════════════════════
# Custom TTS: Piper
# ═════════════════════════════════════════════════════════════════════════════
class PiperTTS(tts.TTS):
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=22050,
            num_channels=1,
        )

    def synthesize(self, text: str, *, conn_options=None) -> tts.ChunkedStream:
        return PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class PiperChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: PiperTTS, input_text: str, conn_options=None):
        super().__init__(
            tts=tts,
            input_text=input_text,
            conn_options=conn_options or APIConnectOptions(),
        )

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "piper",
                "--model", PIPER_MODEL,
                "--output_raw",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate(self._input_text.encode("utf-8"))
            logger.info(f"TTS: {len(stdout)} bytes PCM für '{self._input_text[:50]}...'")

            if stdout:
                output_emitter.initialize(
                    request_id="piper",
                    sample_rate=22050,
                    num_channels=1,
                    mime_type="audio/pcm",
                )
                output_emitter.push(stdout)
        except Exception as e:
            logger.error(f"TTS Fehler: {e}", exc_info=True)


# ═════════════════════════════════════════════════════════════════════════════
# Custom LLM: n8n RAG Webhook
# ═════════════════════════════════════════════════════════════════════════════
class RagLLM(llm.LLM):
    def __init__(self):
        super().__init__()

    def chat(self, *, chat_ctx: llm.ChatContext, tools=None, conn_options=None,
             parallel_tool_calls=None, tool_choice=None, extra_kwargs=None, **kwargs) -> llm.LLMStream:
        return RagLLMStream(
            llm=self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options or APIConnectOptions(),
        )


class RagLLMStream(llm.LLMStream):
    def __init__(self, llm: RagLLM, chat_ctx: llm.ChatContext,
                 tools: list, conn_options: APIConnectOptions):
        super().__init__(llm=llm, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)

    async def _run(self) -> None:
        question = ""
        for msg in reversed(self._chat_ctx.items):
            if hasattr(msg, "role") and msg.role == "user":
                if hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, str):
                        question = content
                    elif isinstance(content, list):
                        for c in content:
                            if hasattr(c, "text"):
                                question = c.text
                                break
                if question:
                    break

        if not question:
            logger.warning("Keine User-Nachricht gefunden")
            return

        logger.info(f"RAG Query: '{question}'")

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.post(
                    f"{RAG_URL}/api/public/chat",
                    json={"query": question, "session_id": "voice_session"},
                    headers={
                        "X-Tenant-ID": TENANT_ID,
                        "X-API-Key": API_KEY,
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data.get("answer", data.get("response", "Entschuldigung, ich konnte keine Antwort finden."))
        except Exception as e:
            logger.error(f"RAG Fehler: {e}")
            answer = "Entschuldigung, es gab einen Fehler bei der Verarbeitung."

        logger.info(f"RAG Antwort: '{answer[:80]}...'")

        self._event_ch.send_nowait(
            llm.ChatChunk(
                id="rag-response",
                delta=llm.ChoiceDelta(role="assistant", content=answer),
            )
        )


# ═════════════════════════════════════════════════════════════════════════════
# Agent Entrypoint
# ═════════════════════════════════════════════════════════════════════════════
async def _fetch_greeting() -> str:
    """Holt eine Begrüßung mit EPPCOM-Infos aus dem RAG-System."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{RAG_URL}/api/public/chat",
                json={
                    "query": "Stelle dich kurz als EPPCOM Sprach-Assistent vor. "
                             "Beschreibe in 2-3 Sätzen was EPPCOM macht und biete deine Hilfe an.",
                    "session_id": "voice_greeting",
                },
                headers={
                    "X-Tenant-ID": TENANT_ID,
                    "X-API-Key": API_KEY,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("answer", data.get("response", ""))
    except Exception as e:
        logger.error(f"Greeting RAG-Fehler: {e}")
        return ""


FALLBACK_GREETING = (
    "Hallo und willkommen bei EPPCOM! "
    "Ich bin Ihr digitaler Sprach-Assistent. "
    "Wie kann ich Ihnen heute helfen?"
)


async def entrypoint(ctx: JobContext):
    logger.info(f"Voice Agent gestartet — Room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    agent = agents.voice.Agent(
        instructions=(
            "Du bist der EPPCOM Sprach-Assistent. Antworte auf Deutsch, kurz und hilfreich. "
            "Sei freundlich und professionell."
        ),
        stt=WhisperSTT(),
        llm=RagLLM(),
        tts=PiperTTS(),
        vad=silero.VAD.load(min_silence_duration=3.0),
        min_endpointing_delay=3.0,
    )

    session = agents.AgentSession()
    await session.start(agent=agent, room=ctx.room)

    # Begrüßung sofort mit Fallback, RAG-Begrüßung im Hintergrund versuchen
    try:
        greeting = await asyncio.wait_for(_fetch_greeting(), timeout=15)
        if not greeting or len(greeting) < 10:
            greeting = FALLBACK_GREETING
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Begrüßung-Timeout/Fehler: {e}, nutze Fallback")
        greeting = FALLBACK_GREETING
    logger.info(f"Begrüßung: '{greeting[:80]}...'")
    session.say(greeting)

    logger.info("Agent-Session gestartet, warte auf Audio...")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=LIVEKIT_KEY,
            api_secret=LIVEKIT_SECRET,
            ws_url=LIVEKIT_URL,
        )
    )
