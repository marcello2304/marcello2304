FROM python:3.11-slim

# System-Abhängigkeiten für Audio-Verarbeitung
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agent-Code
COPY agent.py .

ENV WHISPER_MODEL=tiny
ENV PYTHONUNBUFFERED=1

# Whisper-Modell beim Build vorladen (schnellerer Start)
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8')"

CMD ["python3", "agent.py", "start"]
