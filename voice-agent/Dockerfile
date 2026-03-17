FROM python:3.11-slim

# System-Abhängigkeiten für Audio-Verarbeitung + Piper TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Piper TTS installieren
RUN wget -q https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz \
    && tar -xf piper_linux_x86_64.tar.gz -C /opt/ \
    && ln -sf /opt/piper/piper /usr/local/bin/piper \
    && rm piper_linux_x86_64.tar.gz

# Deutsches Stimmmodell (thorsten-medium) herunterladen
RUN mkdir -p /opt/piper-models \
    && wget -q -O /opt/piper-models/de_DE-thorsten-medium.onnx \
       "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx" \
    && wget -q -O /opt/piper-models/de_DE-thorsten-medium.onnx.json \
       "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json"

WORKDIR /app

# Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agent-Code
COPY agent.py .

ENV PIPER_MODEL=/opt/piper-models/de_DE-thorsten-medium.onnx
ENV WHISPER_MODEL=base
ENV PYTHONUNBUFFERED=1

# Whisper-Modell beim Build vorladen (schnellerer Start)
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

CMD ["python3", "agent.py", "start"]
