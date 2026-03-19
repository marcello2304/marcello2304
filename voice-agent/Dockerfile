FROM python:3.12-slim

# System dependencies for audio processing + Cartesia TTS streaming
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agent code
COPY agent.py .

ENV PYTHONUNBUFFERED=1
ENV OLLAMA_MODEL=phi:2b
ENV CARTESIA_MODEL=sonic-2

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)" || exit 1

CMD ["python3", "agent.py", "start"]
