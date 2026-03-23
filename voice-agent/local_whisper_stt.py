"""
Local Whisper STT provider for livekit-agents v1.5 using faster-whisper.

Provides zero-cost speech-to-text by running Whisper locally
instead of calling paid APIs like Deepgram or OpenAI.
"""

import asyncio
import logging
import numpy as np
from livekit.agents.stt import (
    STT, STTCapabilities, SpeechEvent, SpeechEventType, SpeechData,
)
from livekit.agents import APIConnectOptions
from faster_whisper import WhisperModel

logger = logging.getLogger("nexo-local-stt")


class LocalWhisperSTT(STT):
    """Local Whisper STT using faster-whisper (livekit-agents v1.5 API)."""

    def __init__(self, model_size: str = "small", device: str = "auto"):
        super().__init__(
            capabilities=STTCapabilities(
                streaming=False,
                interim_results=False,
            )
        )
        self.model_size = model_size
        logger.info(f"Loading Whisper-{model_size} model (device: {device})...")
        self._whisper = WhisperModel(
            model_size,
            device=device,
            compute_type="default",
        )
        logger.info(f"Whisper-{model_size} loaded successfully")

    async def _recognize_impl(self, buffer, *, language="de", conn_options=None):
        """Transcribe audio buffer using local Whisper model."""
        try:
            # Convert AudioBuffer to numpy array
            frame = buffer.to_frame()
            audio_array = np.frombuffer(frame.data, dtype=np.int16).astype(np.float32) / 32768.0

            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None, self._transcribe_sync, audio_array,
            )

            transcript = " ".join(seg.text for seg in segments).strip()
            logger.debug(f"Transcribed: {transcript[:100]}...")

            return SpeechEvent(
                type=SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[
                    SpeechData(
                        language=language if isinstance(language, str) else "de",
                        text=transcript or "",
                        confidence=1.0,
                    )
                ],
            )
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return SpeechEvent(
                type=SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[SpeechData(language="de", text="", confidence=0.0)],
            )

    def _transcribe_sync(self, audio_array):
        segments, info = self._whisper.transcribe(
            audio_array,
            language="de",
            beam_size=5,
            best_of=1,
        )
        return list(segments), info
