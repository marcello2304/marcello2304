"""
Nexo — EPPCOM Voice Bot Agent (livekit-agents v1.4.6)
- STT: faster-whisper (lokal, DSGVO-konform)
- LLM: RAG-Pipeline via Admin-UI
- TTS: Cartesia AI Sonic-3 (ultra-natürlich, schnell)
- VAD: silero (0.8s Stille = Endpunkt)

Deployment: Docker auf Server 2 (46.224.54.65)
"""
import asyncio
import json
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
logger = logging.getLogger("nexo-voice")

# ── Konfiguration via ENV ────────────────────────────────────────────────────
RAG_URL = os.getenv("RAG_URL", os.getenv("N8N_URL", "https://appdb.eppcom.de"))
TENANT_ID = os.getenv("TENANT_ID", "")
API_KEY = os.getenv("API_KEY", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# Cartesia AI TTS (Cloud-basiert, ultra-natürlich)
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "b9de4a89-2257-424b-94c2-db18ba68c81a")

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
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))

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
# Custom TTS: Cartesia AI Sonic-3 (Ultra-natürlich, 44.1kHz)
# ═════════════════════════════════════════════════════════════════════════════
class CartesiaTTS(tts.TTS):
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=44100,  # Cartesia: 44.1kHz
            num_channels=1,
        )

    def synthesize(self, text: str, *, conn_options=None) -> tts.ChunkedStream:
        return CartesiaChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class CartesiaChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: CartesiaTTS, input_text: str, conn_options=None):
        super().__init__(
            tts=tts,
            input_text=input_text,
            conn_options=conn_options or APIConnectOptions(),
        )

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        try:
            if not CARTESIA_API_KEY:
                logger.error("CARTESIA_API_KEY nicht gesetzt!")
                return

            output_emitter.initialize(
                request_id="cartesia-stream",
                sample_rate=44100,
                num_channels=1,
                mime_type="audio/pcm",
            )

            async with httpx.AsyncClient(timeout=30) as client:
                async with client.stream(
                    "POST",
                    "https://api.cartesia.ai/tts/sse",
                    headers={
                        "Cartesia-Version": "2025-04-16",
                        "X-API-Key": CARTESIA_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model_id": "sonic-3",
                        "transcript": self._input_text,
                        "voice": {
                            "mode": "id",
                            "id": CARTESIA_VOICE_ID,
                        },
                        "output_format": {
                            "container": "raw",
                            "encoding": "pcm_f32le",
                            "sample_rate": 44100,
                        },
                        "stream": True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    chunk_count = 0
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        if chunk:
                            chunk_count += 1
                            output_emitter.push(chunk)
                    logger.info(f"Cartesia TTS: {chunk_count} chunks streamed für '{self._input_text[:50]}...'")
        except Exception as e:
            logger.error(f"Cartesia TTS Fehler: {e}", exc_info=True)


# ═════════════════════════════════════════════════════════════════════════════
# Custom LLM: RAG via Admin-UI
# ═════════════════════════════════════════════════════════════════════════════

# Session-Speicher für Benutzernamen (pro Room)
_user_names = {}


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
        # Letzte User-Nachricht extrahieren (v1.4.6 API: text_content property)
        question = ""
        for msg in reversed(self._chat_ctx.items):
            if hasattr(msg, "role") and msg.role == "user":
                # text_content gibt den Text direkt zurück
                if hasattr(msg, "text_content") and msg.text_content:
                    question = msg.text_content
                elif hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, str):
                        question = content
                    elif isinstance(content, list):
                        for c in content:
                            if isinstance(c, str):
                                question = c
                                break
                if question:
                    break

        if not question:
            logger.warning("Keine User-Nachricht gefunden")
            return

        logger.info(f"RAG Query: '{question[:100]}...'")  # Kurzes Logging für Speed

        # Prüfe ob der User seinen Namen sagt (erste Interaktion)
        session_id = "voice_session"
        name_prefix = ""

        # Prüfe ob ein Name gespeichert ist
        if session_id in _user_names:
            name_prefix = f"Der Gesprächspartner heißt {_user_names[session_id]}. Sprich ihn mit seinem Namen an. "
        else:
            # Erste Antwort — der User hat wahrscheinlich seinen Namen gesagt
            # Speichere den Text als potentiellen Namen
            words = question.strip().split()
            if len(words) <= 4:
                # Kurze Antwort = wahrscheinlich ein Name
                name = question.strip().rstrip(".!?,")
                # Entferne typische Phrasen
                for prefix in ["ich bin ", "mein name ist ", "ich heiße ", "ich heisse "]:
                    if name.lower().startswith(prefix):
                        name = name[len(prefix):].strip()
                        break
                if name and len(name) < 30:
                    _user_names[session_id] = name
                    name_prefix = f"Der Gesprächspartner hat sich gerade als {name} vorgestellt. Begrüße ihn herzlich mit seinem Namen und frage wie du helfen kannst. "
                    logger.info(f"Name erkannt: '{name}'")

        try:
            enriched_query = name_prefix + question if name_prefix else question
            full_answer = ""  # Für Logging

            # Timeout 45s für Ollama Streaming (keep_alive=30m sorgt dafür dass Modell warm bleibt)
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.post(
                    f"{RAG_URL}/api/public/chat",
                    json={"query": enriched_query, "session_id": session_id},
                    headers={
                        "X-Tenant-ID": TENANT_ID,
                        "X-API-Key": API_KEY,
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()

                # Versuche Streaming zu verarbeiten (JSONL format von Ollama)
                is_streaming = False
                try:
                    # Zuerst checken ob es streaming Response ist
                    content_type = resp.headers.get("content-type", "")
                    if "application/json" in content_type:
                        # Versuche JSON Lines zu parsen
                        async for line in resp.aiter_lines():
                            if not line.strip():
                                continue
                            try:
                                chunk = json.loads(line)
                                # Ollama Streaming Format: {"message": {"content": "token"}}
                                token = chunk.get("message", {}).get("content", "")
                                if token:
                                    is_streaming = True
                                    full_answer += token
                                    # Token sofort senden (streaming)
                                    self._event_ch.send_nowait(
                                        llm.ChatChunk(
                                            id="rag-response",
                                            delta=llm.ChoiceDelta(role="assistant", content=token),
                                        )
                                    )
                            except (json.JSONDecodeError, KeyError):
                                pass  # Skip invalid lines
                except Exception as stream_err:
                    logger.warning(f"Streaming parse failed: {stream_err}, fallback zu JSON response")

                # Fallback: Wenn nicht streaming, dann komplette Antwort
                if not is_streaming:
                    data = resp.json()
                    answer = data.get("answer", data.get("response", "Entschuldigung, ich konnte keine Antwort finden."))
                    self._event_ch.send_nowait(
                        llm.ChatChunk(
                            id="rag-response",
                            delta=llm.ChoiceDelta(role="assistant", content=answer),
                        )
                    )
                    full_answer = answer
        except Exception as e:
            logger.error(f"RAG Fehler: {e}")
            answer = "Entschuldigung, es gab einen Fehler bei der Verarbeitung. Bitte versuchen Sie es erneut."
            self._event_ch.send_nowait(
                llm.ChatChunk(
                    id="rag-response",
                    delta=llm.ChoiceDelta(role="assistant", content=answer),
                )
            )
            full_answer = answer

        logger.info(f"RAG Antwort: '{full_answer[:80]}...' (Streaming: {full_answer != ''})")


# ═════════════════════════════════════════════════════════════════════════════
# Agent Entrypoint
# ═════════════════════════════════════════════════════════════════════════════
NEXO_GREETING = (
    "Hallo! Ich bin Nexo von EPPCOM Solutions. "
    "Wie darf ich Sie ansprechen?"
)


async def entrypoint(ctx: JobContext):
    logger.info(f"Nexo Voice Agent gestartet — Room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    agent = agents.voice.Agent(
        instructions=(
            "Du bist Nexo, die freundliche KI-Sprach-Assistentin von EPPCOM Solutions. "
            "Antworte auf Deutsch, kurz und hilfreich. "
            "Sei freundlich, warmherzig und professionell. "
            "EPPCOM bietet KI-Automatisierung und Workflow-Optimierung für KMU. "
            "Wenn der Gesprächspartner sich vorstellt, merke dir seinen Namen und verwende ihn."
        ),
        stt=WhisperSTT(),
        llm=RagLLM(),
        tts=CartesiaTTS(),
        vad=silero.VAD.load(min_silence_duration=0.8),
        min_endpointing_delay=0.5,
        allow_interruptions=True,
        # Phase B Optimierungen: Streaming & Partial Processing
        allow_partial_requests=True,  # Sende partielle Transkripte zur LLM
    )

    session = agents.AgentSession()
    await session.start(agent=agent, room=ctx.room)

    # Sofortige Begrüßung — fragt nach dem Namen
    logger.info(f"Begrüßung: '{NEXO_GREETING[:80]}...'")
    session.say(NEXO_GREETING)

    logger.info("Nexo-Session gestartet, warte auf Audio...")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=LIVEKIT_KEY,
            api_secret=LIVEKIT_SECRET,
            ws_url=LIVEKIT_URL,
        )
    )
