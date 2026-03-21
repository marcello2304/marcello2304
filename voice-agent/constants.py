"""Shared constants for voice agent streaming."""

# Streaming Configuration
SENTENCE_PATTERN = r'(?<=[.!?])\s+(?=[A-Z])'  # Regex for sentence boundaries
MAX_SENTENCE_LENGTH = 250  # Cartesia TTS limit (~200-300 tokens)
TRUNCATION_SUFFIX = "..."
