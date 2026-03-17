"""
EPPCOM Voice Bot Agent
- STT: faster-whisper (lokal, DSGVO-konform)
- RAG: n8n Webhook auf Server 1
- TTS: piper-tts (lokal, DSGVO-konform)
- VAD: silero (Voice Activity Detection)

Deployment: Docker auf Server 2 (46.224.54.65)
"""
import asyncio
import os
import struct
import tempfile
import wave
import logging
import subprocess

import httpx
from livekit import agents, rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.plugins import silero
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("eppcom-voice")

# ── Konfiguration via ENV ────────────────────────────────────────────────────
N8N_URL = os.getenv("N8N_URL", "https://workflows.eppcom.de")
TENANT_ID = os.getenv("TENANT_ID", "")
API_KEY = os.getenv("API_KEY", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
PIPER_MODEL = os.getenv("PIPER_MODEL", "/opt/piper/de_DE-thorsten-medium.onnx")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# ── Whisper-Modell einmal beim Start laden ───────────────────────────────────
logger.info(f"Lade Whisper-Modell '{WHISPER_MODEL_SIZE}' (CPU, int8)...")
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
logger.info("Whisper-Modell geladen.")


async def transcribe_audio(audio_frames: list[rtc.AudioFrame]) -> str:
    """Audio-Frames mit faster-whisper transkribieren (synchron in Thread)."""

    def _transcribe():
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)
                for frame in audio_frames:
                    wf.writeframes(frame.data.tobytes() if hasattr(frame.data, "tobytes") else frame.data)
            tmp.flush()
            segments, info = whisper_model.transcribe(tmp.name, language="de")
            text = " ".join(s.text for s in segments).strip()
            return text

    return await asyncio.to_thread(_transcribe)


async def query_rag(question: str, session_id: str) -> str:
    """RAG-Antwort von n8n holen."""
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(
            f"{N8N_URL}/webhook/rag-chat",
            json={"query": question, "session_id": session_id},
            headers={
                "X-Tenant-ID": TENANT_ID,
                "X-API-Key": API_KEY,
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("answer", data.get("response", "Entschuldigung, ich konnte keine Antwort finden."))


async def text_to_speech(text: str) -> bytes:
    """Text mit piper-tts in rohes PCM-Audio (16kHz mono 16-bit) umwandeln."""
    proc = await asyncio.create_subprocess_exec(
        "piper",
        "--model", PIPER_MODEL,
        "--output_raw",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate(text.encode("utf-8"))
    return stdout


async def send_audio_to_room(ctx: JobContext, pcm_data: bytes):
    """PCM-Daten als AudioFrames in den LiveKit-Room streamen."""
    source = rtc.AudioSource(sample_rate=16000, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("agent-voice", source)
    options = rtc.TrackPublishOptions()
    await ctx.room.local_participant.publish_track(track, options)

    # Kurz warten damit der Track sich verbindet
    await asyncio.sleep(0.2)

    frame_duration_ms = 100
    samples_per_frame = 16000 * frame_duration_ms // 1000  # 1600 samples
    bytes_per_frame = samples_per_frame * 2  # 16-bit = 2 bytes pro sample

    for i in range(0, len(pcm_data), bytes_per_frame):
        chunk = pcm_data[i : i + bytes_per_frame]
        if len(chunk) < bytes_per_frame:
            chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))

        frame = rtc.AudioFrame(
            data=chunk,
            sample_rate=16000,
            num_channels=1,
            samples_per_channel=samples_per_frame,
        )
        await source.capture_frame(frame)
        await asyncio.sleep(frame_duration_ms / 1000)

    # Track wieder entfernen nach Abspielen
    await ctx.room.local_participant.unpublish_track(track.sid)


async def entrypoint(ctx: JobContext):
    """Haupteinstiegspunkt des Voice Agents."""
    logger.info(f"Voice Agent gestartet — Room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session_id = f"voice_{ctx.room.name}"
    vad = silero.VAD.load()

    @ctx.room.on("track_subscribed")
    def on_track(
        track: rtc.Track,
        pub: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        logger.info(f"Audio-Track von {participant.identity} abonniert")
        asyncio.ensure_future(_process_audio(track, session_id, ctx, vad))

    # Agent lebt so lange der Room existiert
    await asyncio.sleep(float("inf"))


async def _process_audio(
    track: rtc.Track,
    session_id: str,
    ctx: JobContext,
    vad: silero.VAD,
):
    """Audio-Stream verarbeiten: VAD → STT → RAG → TTS → Antwort."""
    audio_stream = rtc.AudioStream(track)
    vad_stream = vad.stream()
    audio_buffer: list[rtc.AudioFrame] = []
    is_speaking = False

    async for event in audio_stream:
        # VAD auf jedes Frame anwenden
        vad_events = vad_stream.push(event.frame)
        for vad_event in vad_events:
            if vad_event.type == agents.vad.VADEventType.START_OF_SPEECH:
                is_speaking = True
                audio_buffer = []
                logger.info("Sprache erkannt — aufnehmen...")

            elif is_speaking:
                audio_buffer.append(event.frame)

            if vad_event.type == agents.vad.VADEventType.END_OF_SPEECH:
                is_speaking = False
                if not audio_buffer:
                    continue

                logger.info(f"Sprachende — {len(audio_buffer)} Frames transkribieren...")
                try:
                    question = await transcribe_audio(audio_buffer)
                    if not question or len(question.strip()) < 3:
                        logger.info(f"Zu kurze Transkription ignoriert: '{question}'")
                        continue

                    logger.info(f"Frage: {question}")

                    answer = await query_rag(question, session_id)
                    logger.info(f"Antwort: {answer[:100]}...")

                    pcm_data = await text_to_speech(answer)
                    logger.info(f"TTS fertig — {len(pcm_data)} bytes PCM")

                    await send_audio_to_room(ctx, pcm_data)
                    logger.info("Audio-Antwort gesendet")

                except Exception as e:
                    logger.error(f"Fehler in Pipeline: {e}", exc_info=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=LIVEKIT_KEY,
            api_secret=LIVEKIT_SECRET,
            ws_url=LIVEKIT_URL,
        )
    )
