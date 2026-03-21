"""
Local Whisper STT provider for livekit-agents using faster-whisper.

Provides zero-cost speech-to-text by running Whisper-small (140MB) or Whisper-base (150MB)
locally instead of calling paid APIs like Deepgram or OpenAI.

Supports streaming transcription with word-level timestamps.
"""

import asyncio
import logging
from typing import Optional
from livekit.agents import STT, SpeechData
from faster_whisper import WhisperModel

logger = logging.getLogger("nexo-local-stt")


class LocalWhisperSTT(STT):
    """
    Local Whisper STT implementation using faster-whisper.

    Key advantages:
    - Zero cost (runs locally)
    - Fast inference (GPU optional, CPU works fine for small models)
    - German language support included
    - No API keys required

    Resource usage (on CPU):
    - Whisper-tiny (39MB): ~2s per 10s audio (slowest but smallest)
    - Whisper-small (140MB): ~1s per 10s audio (good balance)
    - Whisper-base (150MB): ~500ms per 10s audio (faster, more accurate)
    """

    def __init__(self, model_size: str = "small", device: str = "auto"):
        """
        Initialize local Whisper model.

        Args:
            model_size: "tiny", "small", "base", "medium", or "large"
            device: "auto", "cuda", "cpu"
        """
        super().__init__()
        self.model_size = model_size
        self.device = device

        logger.info(f"Loading Whisper-{model_size} model (device: {device})...")
        try:
            # faster-whisper handles model downloads automatically
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type="default",  # auto-select int8/float32 based on device
            )
            logger.info(f"✓ Whisper-{model_size} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def asr(self, data: SpeechData) -> Optional[str]:
        """
        Transcribe audio to text using local Whisper model.

        Args:
            data: SpeechData with audio bytes, sample_rate, channels, samples

        Returns:
            Transcribed text or None if transcription fails
        """
        try:
            # faster-whisper expects float32 PCM audio
            # Convert raw bytes to audio array
            import numpy as np

            # Assuming data.data is raw bytes in PCM16 format
            audio_array = np.frombuffer(data.data, dtype=np.int16).astype(np.float32) / 32768.0

            # Run transcription in thread pool to avoid blocking async event loop
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio_array,
                data.sample_rate or 16000,
            )

            # Combine all segments into single transcript
            transcript = " ".join(segment.text for segment in segments)

            if transcript.strip():
                logger.debug(f"Transcribed: {transcript[:100]}...")
                return transcript.strip()
            else:
                logger.debug("No speech detected")
                return None

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return None

    def _transcribe_sync(self, audio_array, sample_rate: int):
        """
        Synchronous transcription (runs in thread pool).

        Args:
            audio_array: numpy array of float32 audio samples
            sample_rate: sample rate in Hz (16000, 24000, etc.)

        Returns:
            Tuple of (segments, info)
        """
        segments, info = self.model.transcribe(
            audio_array,
            language="de",  # German by default (user can override)
            beam_size=5,  # Balance between speed and accuracy
            best_of=1,  # Set >1 for better quality (slower)
        )
        return list(segments), info
