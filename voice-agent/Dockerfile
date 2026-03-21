FROM python:3.11-slim

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
COPY constants.py .
COPY local_whisper_stt.py .

ENV PYTHONUNBUFFERED=1
ENV OLLAMA_MODEL=phi:latest
ENV CARTESIA_MODEL=sonic-2

CMD ["python3", "agent.py", "start"]
