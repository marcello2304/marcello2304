# EPPCOM Voice Bot + UI Setup

## Übersicht

```
Browser/Telefon
      │ Audio-Stream
      ▼
  LiveKit Server (Server 2: 46.224.54.65)
      │ Audio-Frames
      ▼
  LiveKit Agent (Python, Server 2)
      │ Text (transkribiert)
      ▼
  Whisper / Faster-Whisper (STT)
      │ Frage als Text
      ▼
  n8n RAG Chat Webhook (Server 1)
      │ Antwort als Text
      ▼
  Piper TTS / Kokoro (Server 2)
      │ Audio-Stream
      ▼
  Browser / Telefon (Antwort als Sprache)
```

---

## Teil 1: LiveKit Server aufsetzen (Server 2)

### 1.1 LiveKit installieren

```bash
ssh root@46.224.54.65

# LiveKit Server herunterladen
curl -sSL https://get.livekit.io | bash

# Konfigurationsdatei anlegen
cat > /etc/livekit.yaml << 'EOF'
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true

keys:
  devkey: devsecret-change-this-in-production

# Logging
logging:
  level: info

# Webhook (optional: n8n benachrichtigen wenn Session startet)
# webhook:
#   urls:
#     - https://workflows.eppcom.de/webhook/livekit-events
#   api_key: devkey
EOF

# Als Systemd-Service einrichten
cat > /etc/systemd/system/livekit.service << 'EOF'
[Unit]
Description=LiveKit Server
After=network.target

[Service]
ExecStart=/usr/local/bin/livekit-server --config /etc/livekit.yaml
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now livekit
systemctl status livekit
```

### 1.2 Nginx Reverse Proxy für LiveKit (Port 443/WSS)

```nginx
# /etc/nginx/sites-available/livekit
server {
    server_name livekit.eppcom.de;
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/livekit.eppcom.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/livekit.eppcom.de/privkey.pem;

    location / {
        proxy_pass http://localhost:7880;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }
}
```

```bash
certbot --nginx -d livekit.eppcom.de
nginx -t && nginx -s reload
```

---

## Teil 2: Voice Agent aufsetzen (Server 2)

### 2.1 Python-Umgebung

```bash
ssh root@46.224.54.65

apt-get install -y python3-pip python3-venv ffmpeg
python3 -m venv /opt/eppcom-agent
source /opt/eppcom-agent/bin/activate

pip install \
  livekit-agents \
  livekit-plugins-silero \
  faster-whisper \
  httpx \
  piper-tts
```

### 2.2 Agent-Code erstellen

```bash
cat > /opt/eppcom-agent/agent.py << 'AGENT_EOF'
"""
EPPCOM Voice Bot Agent
- STT: faster-whisper (lokal, DSGVO-konform)
- RAG: n8n Webhook
- TTS: piper-tts (lokal)
"""
import asyncio
import os
import httpx
import logging
from livekit import agents, rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.plugins import silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

N8N_URL        = os.getenv("N8N_URL",        "https://workflows.eppcom.de")
TENANT_ID      = os.getenv("TENANT_ID",      "a0000000-0000-0000-0000-000000000001")
API_KEY        = os.getenv("API_KEY",         "DEIN_API_KEY_HIER")
WHISPER_MODEL  = os.getenv("WHISPER_MODEL",   "base")  # tiny/base/small/medium
PIPER_MODEL    = os.getenv("PIPER_MODEL",     "/opt/piper/de_DE-thorsten-medium.onnx")
LIVEKIT_URL    = os.getenv("LIVEKIT_URL",     "wss://livekit.eppcom.de")
LIVEKIT_KEY    = os.getenv("LIVEKIT_KEY",     "devkey")
LIVEKIT_SECRET = os.getenv("LIVEKIT_SECRET",  "devsecret-change-this-in-production")


async def transcribe_audio(audio_frames: list) -> str:
    """Audio mit faster-whisper transkribieren."""
    from faster_whisper import WhisperModel
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

    import tempfile, wave, struct
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            for frame in audio_frames:
                wf.writeframes(frame.data)

    segments, _ = model.transcribe(wav_path, language="de")
    text = " ".join(s.text for s in segments).strip()
    return text


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
        data = resp.json()
        return data.get("answer", "Entschuldigung, ich konnte keine Antwort finden.")


async def text_to_speech(text: str) -> bytes:
    """Text mit piper-tts in Audio umwandeln."""
    import subprocess
    proc = await asyncio.create_subprocess_exec(
        "piper",
        "--model", PIPER_MODEL,
        "--output_raw",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate(text.encode("utf-8"))
    return stdout  # raw PCM 16kHz mono 16bit


async def entrypoint(ctx: JobContext):
    logger.info(f"Voice Agent gestartet: Room={ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # VAD (Voice Activity Detection) mit silero
    vad = silero.VAD.load()
    session_id = f"voice_{ctx.room.name}"

    @ctx.room.on("track_subscribed")
    def on_track(track: rtc.Track, pub: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return

        asyncio.ensure_future(handle_audio(track, session_id, ctx))

    await asyncio.sleep(float("inf"))  # Agent läuft bis Room endet


async def handle_audio(track: rtc.Track, session_id: str, ctx: JobContext):
    """Audio-Stream verarbeiten: STT → RAG → TTS → zurück."""
    audio_stream = rtc.AudioStream(track)
    vad_stream = silero.VAD.load().stream()
    audio_buffer = []

    async for event in vad_stream:
        if event.type == agents.vad.VADEventType.START_OF_SPEECH:
            audio_buffer = []
            logger.info("Sprache erkannt — aufzeichnen...")

        elif event.type == agents.vad.VADEventType.INFERENCE_DONE:
            audio_buffer.append(event.frames)

        elif event.type == agents.vad.VADEventType.END_OF_SPEECH:
            if not audio_buffer:
                continue

            logger.info("Sprachende — Transkription...")
            try:
                question = await transcribe_audio(audio_buffer)
                if not question or len(question) < 3:
                    continue

                logger.info(f"Frage: {question}")

                # RAG-Antwort holen
                answer = await query_rag(question, session_id)
                logger.info(f"Antwort: {answer[:80]}...")

                # TTS
                audio_data = await text_to_speech(answer)

                # Audio in Room senden
                source = rtc.AudioSource(sample_rate=16000, num_channels=1)
                track = rtc.LocalAudioTrack.create_audio_track("agent-voice", source)
                await ctx.room.local_participant.publish_track(track)

                # PCM-Daten in Frames schicken
                frame_size = 1600  # 100ms @ 16kHz
                for i in range(0, len(audio_data), frame_size * 2):
                    chunk = audio_data[i:i + frame_size * 2]
                    if len(chunk) < frame_size * 2:
                        chunk = chunk.ljust(frame_size * 2, b'\x00')
                    frame = rtc.AudioFrame(
                        data=chunk,
                        sample_rate=16000,
                        num_channels=1,
                        samples_per_channel=frame_size,
                    )
                    await source.capture_frame(frame)
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Fehler: {e}")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=LIVEKIT_KEY,
            api_secret=LIVEKIT_SECRET,
            ws_url=LIVEKIT_URL,
        )
    )
AGENT_EOF
```

### 2.3 Piper TTS (deutsches Modell) installieren

```bash
# Piper herunterladen
wget https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz
tar -xf piper_linux_x86_64.tar.gz -C /opt/
ln -sf /opt/piper/piper /usr/local/bin/piper

# Deutsches Stimmmodell herunterladen
mkdir -p /opt/piper
wget -O /opt/piper/de_DE-thorsten-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx"
wget -O /opt/piper/de_DE-thorsten-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json"

# Test
echo "Hallo, ich bin der EPPCOM Assistent" | piper --model /opt/piper/de_DE-thorsten-medium.onnx --output_file /tmp/test.wav
aplay /tmp/test.wav  # oder: ffplay /tmp/test.wav
```

### 2.4 Agent als Service starten

```bash
cat > /etc/systemd/system/eppcom-agent.service << 'EOF'
[Unit]
Description=EPPCOM Voice Agent
After=livekit.service network.target

[Service]
ExecStart=/opt/eppcom-agent/bin/python /opt/eppcom-agent/agent.py start
WorkingDirectory=/opt/eppcom-agent
Environment="N8N_URL=https://workflows.eppcom.de"
Environment="TENANT_ID=a0000000-0000-0000-0000-000000000001"
Environment="API_KEY=DEIN_API_KEY_HIER"
Environment="WHISPER_MODEL=base"
Environment="PIPER_MODEL=/opt/piper/de_DE-thorsten-medium.onnx"
Environment="LIVEKIT_URL=wss://livekit.eppcom.de"
Environment="LIVEKIT_KEY=devkey"
Environment="LIVEKIT_SECRET=devsecret-change-this-in-production"
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now eppcom-agent
journalctl -u eppcom-agent -f
```

---

## Teil 3: Voice Bot Frontend (in Typebot einbetten)

### 3.1 Simples Web-Frontend mit LiveKit SDK

Erstelle `/opt/voicebot-ui/index.html`:

```html
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <title>EPPCOM Voice Assistent</title>
  <script src="https://unpkg.com/livekit-client/dist/livekit-client.umd.min.js"></script>
  <style>
    body { font-family: sans-serif; max-width: 400px; margin: 80px auto; text-align: center; }
    button { padding: 20px 40px; font-size: 18px; border-radius: 50%; cursor: pointer; border: none; }
    #btn-start { background: #2563EB; color: white; }
    #btn-stop  { background: #DC2626; color: white; display: none; }
    #status    { margin: 20px 0; color: #666; }
    #answer    { background: #F1F5F9; padding: 15px; border-radius: 10px; text-align: left; margin-top: 20px; }
  </style>
</head>
<body>
  <h2>🎤 EPPCOM Sprach-Assistent</h2>
  <div id="status">Klicke zum Starten</div>
  <button id="btn-start" onclick="startSession()">🎤</button>
  <button id="btn-stop" onclick="stopSession()">⏹</button>
  <div id="answer" style="display:none;"></div>

  <script>
    const LIVEKIT_URL   = 'wss://livekit.eppcom.de';
    const TOKEN_API     = 'https://admin.eppcom.de/api/livekit-token';  // Dein Token-Endpoint
    const ADMIN_KEY     = 'DEIN-ADMIN-KEY';

    let room = null;

    async function startSession() {
      document.getElementById('status').textContent = 'Verbinde...';
      document.getElementById('btn-start').style.display = 'none';
      document.getElementById('btn-stop').style.display = 'inline-block';

      // Token vom Backend holen
      const r = await fetch(TOKEN_API, {
        method: 'POST',
        headers: { 'X-Admin-Key': ADMIN_KEY, 'Content-Type': 'application/json' },
        body: JSON.stringify({ room: 'eppcom-voice', identity: 'user-' + Date.now() })
      });
      const { token } = await r.json();

      room = new LivekitClient.Room();

      room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === LivekitClient.Track.Kind.Audio) {
          const el = track.attach();
          document.body.appendChild(el);
        }
      });

      await room.connect(LIVEKIT_URL, token);
      await room.localParticipant.setMicrophoneEnabled(true);

      document.getElementById('status').textContent = '🔴 Verbunden — Spreche jetzt!';
    }

    async function stopSession() {
      if (room) await room.disconnect();
      room = null;
      document.getElementById('status').textContent = 'Sitzung beendet';
      document.getElementById('btn-start').style.display = 'inline-block';
      document.getElementById('btn-stop').style.display = 'none';
    }
  </script>
</body>
</html>
```

### 3.2 LiveKit Token-Endpoint in Admin UI hinzufügen

Füge in `admin-ui/main.py` hinzu:

```python
from livekit import api as livekit_api

@app.post("/api/livekit-token")
async def get_livekit_token(body: dict, _: bool = Depends(require_admin)):
    LIVEKIT_KEY    = os.getenv("LIVEKIT_KEY", "devkey")
    LIVEKIT_SECRET = os.getenv("LIVEKIT_SECRET", "devsecret")

    token = livekit_api.AccessToken(LIVEKIT_KEY, LIVEKIT_SECRET) \
        .with_identity(body.get("identity", "user")) \
        .with_name(body.get("identity", "User")) \
        .with_grants(livekit_api.VideoGrants(
            room_join=True,
            room=body.get("room", "eppcom-voice"),
            can_publish=True,
            can_subscribe=True,
        ))
    return {"token": token.to_jwt()}
```

---

## Teil 4: Admin UI — Schnellanleitung

Die Admin UI läuft nach dem Deploy auf `http://SERVER_IP:8080`
oder per Coolify mit Domain auf `https://admin.eppcom.de`.

### Features der Admin UI:

| Tab | Funktion |
|-----|----------|
| **Tenants** | Neue Kunden anlegen, Übersicht aller Tenants |
| **Dokumente** | Dateien hochladen (PDF/TXT/MD), Text direkt eingeben |
| **Chunks** | Alle indexierten Textbausteine durchsuchen |
| **Chat-Tester** | RAG Chat direkt im Browser testen |
| **API-Keys** | Keys pro Tenant erstellen und verwalten |

### Dokument einpflegen (Admin UI):

1. Tab **Dokumente** öffnen
2. Tenant auswählen
3. API-Key eingeben (z.B. `DEIN_API_KEY_HIER`)
4. Datei hochladen ODER Text direkt eingeben
5. Klick auf **"Einpflegen & Embedden"**
6. Warten ~15-60s → Erfolg: Anzahl Chunks angezeigt

### Dokument einpflegen (API direkt):

```bash
# Text direkt
curl -s -X POST https://workflows.eppcom.de/webhook/ingest \
  -H "X-Tenant-ID: a0000000-0000-0000-0000-000000000001" \
  -H "X-API-Key: DEIN_API_KEY_HIER" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hier steht der Volltext des Dokuments...",
    "name": "Produkthandbuch v2",
    "source_type": "manual"
  }'

# Antwort:
# {"success": true, "chunks_created": 7, "source_id": "...", "model": "qwen3-embedding:0.6b"}
```

---

## Teil 5: Coolify-Deploy der Admin UI

1. In Coolify → **New Resource → Docker Image / Dockerfile**
2. Source: dieses Git-Repo → Subfolder: `admin-ui/`
3. Dockerfile: `admin-ui/Dockerfile`
4. Port: `8080`
5. Domain: `admin.eppcom.de`
6. Environment Variables setzen (aus `admin-ui/.env.example`):
   - `DATABASE_URL=postgresql://appuser:PASS@postgres:5432/appdb`
   - `N8N_URL=https://workflows.eppcom.de`
   - `OLLAMA_URL=http://10.0.0.3:11434`
   - `ADMIN_API_KEY=dein-sicherer-admin-key`
   - Network: gleiche wie PostgreSQL Container (`coolify` Netz)

---

## Checkliste: Alles läuft

```
[ ] PostgreSQL + pgvector läuft
[ ] n8n RAG Chat Workflow aktiv (workflows.eppcom.de/webhook/rag-chat)
[ ] n8n Ingestion Workflow aktiv (workflows.eppcom.de/webhook/ingest)
[ ] Admin UI erreichbar (admin.eppcom.de oder :8080)
[ ] Typebot Bot erstellt und published (bot.eppcom.de)
[ ] LiveKit Server läuft (livekit.eppcom.de:7880)
[ ] Voice Agent läuft (systemctl status eppcom-agent)
[ ] Piper TTS Modell geladen (/opt/piper/de_DE-thorsten-medium.onnx)
```

## Schnell-Test alles

```bash
# 1. RAG Chat
curl -s -X POST https://workflows.eppcom.de/webhook/rag-chat \
  -H "X-Tenant-ID: a0000000-0000-0000-0000-000000000001" \
  -H "X-API-Key: DEIN_API_KEY_HIER" \
  -H "Content-Type: application/json" \
  -d '{"query": "Was macht EPPCOM?"}' | python3 -m json.tool

# 2. Dokument einpflegen
curl -s -X POST https://workflows.eppcom.de/webhook/ingest \
  -H "X-Tenant-ID: a0000000-0000-0000-0000-000000000001" \
  -H "X-API-Key: DEIN_API_KEY_HIER" \
  -H "Content-Type: application/json" \
  -d '{"content": "EPPCOM bietet IT-Dienstleistungen in München an.", "name": "Test-Dokument", "source_type": "manual"}'

# 3. Admin UI Health
curl -s http://localhost:8080/api/health

# 4. LiveKit Status
curl -s http://localhost:7880/

# 5. Voice Agent Logs
journalctl -u eppcom-agent --no-pager -n 20
```
