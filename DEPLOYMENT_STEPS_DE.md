# Deployment: Kostenlose Whisper-small STT auf Server 2

## 🎯 Ziel
Voice-Agent mit lokaler Whisper-small STT deployen statt teurer Cloud APIs (Deepgram: $200+/Monat, OpenAI: $0.02/Anfrage).

**Kosteneinsparung: $200+/Monat** ✅

---

## 📋 Voraussetzungen

- Server 2 (46.224.54.65) mit Docker
- Git-Repository aktualisiert (mit neuen Local-Whisper-Dateien)
- Bash-Zugriff auf Server

---

## 🚀 SCHRITT 1: Code auf Server 2 aktualisieren

```bash
ssh user@46.224.54.65

# Ins Projekt-Verzeichnis wechseln
cd /path/to/marcello2304

# Neuesten Code abrufen (mit local_whisper_stt.py)
git pull origin main

# Verfügbare Änderungen prüfen
git status
```

**Erwartete Dateien:**
```
✓ voice-agent/local_whisper_stt.py      (NEU)
✓ voice-agent/requirements.txt           (AKTUALISIERT)
✓ voice-agent/Dockerfile                (AKTUALISIERT)
✓ .env.server2                          (AKTUALISIERT)
✓ WHISPER_LOCAL_STT_GUIDE.md            (DOKUMENTATION)
✓ DEPLOY_LOCAL_WHISPER.sh               (DEPLOYMENT-SKRIPT)
```

---

## 🚀 SCHRITT 2: Umgebungsvariablen prüfen

**Öffnen: `.env.server2`**

```bash
# Überprüfen, ob diese Zeilen existieren:
grep "USE_LOCAL_WHISPER\|WHISPER_MODEL\|WHISPER_DEVICE" .env.server2
```

**Sollte anzeigen:**
```
USE_LOCAL_WHISPER=true
WHISPER_MODEL=small
WHISPER_DEVICE=auto
```

Falls fehlend, manuell hinzufügen:
```bash
echo "USE_LOCAL_WHISPER=true" >> .env.server2
echo "WHISPER_MODEL=small" >> .env.server2
echo "WHISPER_DEVICE=auto" >> .env.server2
```

---

## 🚀 SCHRITT 3: Alten Container stoppen

```bash
# Laufende voice-agent Container anzeigen
docker ps -f "name=voice-agent"

# Stoppen (falls läuft)
docker stop voice-agent || true
docker rm voice-agent || true

# Bestätigung
docker ps -f "name=voice-agent"  # Sollte leer sein
```

---

## 🚀 SCHRITT 4: Docker-Image bauen

```bash
cd voice-agent

# Baue neues Image mit lokaler Whisper-Unterstützung
docker build -t voice-agent:latest .

# Bestätigung
docker images | grep voice-agent
```

**Erwartete Ausgabe:**
```
REPOSITORY   TAG      IMAGE ID      CREATED      SIZE
voice-agent  latest   abc123...     2 min ago    2.5GB
```

> **Hinweis**: `2.5GB` ist größer als vorher, weil `faster-whisper` und PyTorch enthalten sind.

---

## 🚀 SCHRITT 5: Container starten mit Local Whisper

### Option A: Automatisiertes Deployment-Skript

```bash
cd /path/to/marcello2304

# Skript ausführbar machen
chmod +x DEPLOY_LOCAL_WHISPER.sh

# Ausführen (macht alles automatisch)
./DEPLOY_LOCAL_WHISPER.sh
```

**Das Skript macht:**
1. ✓ Älteren Container stoppen
2. ✓ Docker-Image bauen
3. ✓ Neuen Container mit `USE_LOCAL_WHISPER=true` starten
4. ✓ Wartet auf Whisper-Modell-Download (2-3 Min)
5. ✓ Zeigt Erfolg/Fehler an

### Option B: Manuelles Starten

```bash
docker run -d \
  --name voice-agent \
  --env-file .env.server2 \
  --volume ~/.cache:/root/.cache \
  --network livekit-net \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  voice-agent:latest

# Container-Status prüfen
docker ps -f "name=voice-agent"
```

---

## ⏳ SCHRITT 6: Warten auf Whisper-Modell-Download (2-3 Minuten)

**Logs anschauen:**
```bash
docker logs -f voice-agent
```

**Erwartete Ausgabe (Schritt für Schritt):**

### Phase 1: Container Start
```
[INFO] Loading Whisper-small model (device: auto)...
```

### Phase 2: Modell Download
```
Downloading model from https://huggingface.co/...
Downloading pytorch_model.bin: 140MB ...
█████████████░░░░░░░░░░ 60%
```

### Phase 3: Modell Verarbeitung
```
[INFO] ✓ Whisper-small loaded successfully
[INFO] Connected to room: main-room
[INFO] Agent started and listening
```

**🎉 Erfolgreich, wenn diese Zeilen sichtbar:**
```
✓ Using STT: Local Whisper-small (self-hosted, zero cost)
✓ Agent started and listening
```

> **Hinweis**: Diese Zeilen können bis zu 3 Minuten dauern (beim ersten Mal). Bei nachfolgenden Starts ist das Modell gecacht und es dauert nur ~30 Sekunden.

---

## 🎤 SCHRITT 7: Test durchführen

### Test 1: Logs überwachen
```bash
# In Terminal 1: Logs beobachten
docker logs -f voice-agent

# In Terminal 2: Test durchführen (siehe unten)
```

### Test 2: Sprache-Input testen
```bash
# Verbinde dich mit LiveKit-Raum:
livekit-cli participant \
  --url ws://livekit.eppcom.de \
  --api-key <LIVEKIT_API_KEY> \
  --api-secret <LIVEKIT_API_SECRET> \
  --room test-room

# Spreche ins Mikrofon (z.B. "Hallo, wie heißt du?")
```

### Test 3: Erwartete Logs überprüfen

**Logs sollten zeigen:**
```
[INFO] STT received: "Hallo wie heißt du"
[INFO] LLM processing: "Hallo wie heißt du"
[INFO] TTS output: "Ich bin Nexo..."
[DEBUG] Yielding sentence: "Ich bin Nexo..."
```

**WICHTIG: Sollte KEINE dieser Logs zeigen:**
```
❌ Deepgram API request
❌ OpenAI API request
❌ failed to recognize speech (STT error)
```

Falls diese Fehler angezeigt werden → siehe "Troubleshooting" unten.

---

## ✅ SCHRITT 8: Deployment verifizieren

### Schneller Check (< 1 Min)
```bash
chmod +x TEST_WHISPER_DEPLOYMENT.sh
./TEST_WHISPER_DEPLOYMENT.sh
```

**Sollte zeigen:**
```
✓ Container is running
✓ Whisper model loaded successfully
✓ No critical errors found
✓ Local Whisper STT is active
✓ ALL TESTS PASSED
```

### Tieferer Check
```bash
# 1. Prüfe Container läuft
docker ps -f "name=voice-agent"

# 2. Prüfe Whisper geladen
docker logs voice-agent | grep "loaded successfully"

# 3. Prüfe STT-Provider
docker logs voice-agent | grep "Using STT:"

# 4. Prüfe Memory-Nutzung
docker stats voice-agent --no-stream
# Sollte ~1-2GB sein (für small model)

# 5. Prüfe kein Cloud-API-Zugriff
docker logs voice-agent | grep -i "deepgram\|openai\|api" | head -10
# Sollte LEER sein (kein Cloud-Zugriff)
```

---

## 📊 Kosteneinsparung überprüfen

**Vor (Cloud STT):**
- Deepgram: $200+/Monat
- OpenAI Whisper: ~$0.02 pro 1000 Token
- **Monatlich: $200-500**

**Nach (Local Whisper):**
- One-time Download: 140MB
- Server-Ressourcen: Bereits durch Ollama bezahlt
- **Monatlich: $0** ✅

**Einsparung: $200+/Monat!**

---

## 🔧 Troubleshooting

### Problem 1: "Module 'local_whisper_stt' not found"

**Ursache**: Datei nicht kopiert oder git pull nicht aktualisiert

**Lösung:**
```bash
# Prüfen ob Datei existiert
ls -la voice-agent/local_whisper_stt.py

# Falls nicht: git pull ausführen
git pull origin main

# Falls immer noch nicht: manuell kopieren
cp voice-agent/local_whisper_stt.py voice-agent/

# Container neustarten
docker restart voice-agent
```

### Problem 2: "No module named 'faster_whisper'"

**Ursache**: requirements.txt nicht installiert

**Lösung:**
```bash
# Dockerfile neu bauen
cd voice-agent
docker build --no-cache -t voice-agent:latest .
cd ..

# Container mit neuem Image starten
docker stop voice-agent
docker run -d ... (siehe Schritt 5)
```

### Problem 3: Whisper download bricht ab (timeout)

**Ursache**: Netzwerk-Verbindung zu HuggingFace zu langsam

**Lösung:**
```bash
# Cache auf lokalem Rechner vorbereiten (falls möglich)
# oder: Timeout erhöhen

# Oder: Modell manuell herunterladen
docker exec voice-agent \
  python3 -c "from faster_whisper import WhisperModel; WhisperModel('small')"
```

### Problem 4: Agent lädt immer noch zu langsam (Fallback zu Deepgram)

**Logs zeigen:**
```
[INFO] ✓ Using STT: Deepgram nova-2
```

**Ursache**: Local Whisper fehlgeschlagen (falsche Device, fehlende Dependencies)

**Lösung:**
```bash
# 1. Prüfe Logs auf spezifischen Fehler
docker logs voice-agent | grep -i "whisper\|error"

# 2. Prüfe WHISPER_DEVICE
docker inspect voice-agent | grep WHISPER_DEVICE

# 3. Falls GPU verfügbar, nutzen
# In .env.server2:
WHISPER_DEVICE=cuda
docker restart voice-agent

# 4. Wenn noch nicht funktioniert: zu Deepgram fallback ist OK
# (Du sparest immer noch vs Deepgram-only, weil Local als Primary)
```

### Problem 5: Hohe CPU-Nutzung während Whisper-Inference

**Normal?** Ja, Whisper braucht CPU/GPU.

**Verbesserung:**
```bash
# Nutze GPU statt CPU (wenn verfügbar)
WHISPER_DEVICE=cuda
docker restart voice-agent

# Oder kleineres Modell
WHISPER_MODEL=tiny
docker restart voice-agent
```

---

## 📈 Monitoring nach Deployment

### Daily Checks

```bash
# 1. Container läuft noch?
docker ps -f "name=voice-agent"

# 2. Fehler in Logs?
docker logs voice-agent --tail 50 | grep -i error

# 3. Speicher OK?
docker stats voice-agent --no-stream
# Sollte <3GB sein
```

### Weekly Checks

```bash
# Model-Caching prüfen
du -sh ~/.cache/huggingface

# Container-Restarts
docker inspect voice-agent | grep "RestartCount"
# Sollte klein sein (<10)
```

---

## 🎉 Nächste Schritte

1. ✅ **Deployment abgeschlossen**
2. ⬜ **Test mit echten Users** — Stelle sicher, dass Spracherkennung überall funktioniert
3. ⬜ **Monitoring einrichten** — Log-Alerts falls Whisper-Fehler
4. ⬜ **Dokumentation teilen** — Users informieren über Datenschutz (100% lokal)

---

## 📚 Referenzen

- **Detailliertes Guide**: `WHISPER_LOCAL_STT_GUIDE.md`
- **Integration Tests**: `voice-agent/test_local_whisper_integration.py`
- **Streaming Tests**: `voice-agent/test_streaming.py`

---

## ❓ FAQ

**F: Wie lange dauert Download beim ersten Start?**
A: 2-3 Minuten (140MB für small model). Danach gecacht, <30 Sekunden pro Start.

**F: Kann ich zurück zu Deepgram wechseln?**
A: Ja, `USE_LOCAL_WHISPER=false` in `.env.server2` und Container neustarten.

**F: Brauche ich eine GPU?**
A: Nein, läuft auch auf CPU. GPU macht es 2-3x schneller.

**F: Ist lokal 100% privat?**
A: Ja! Keine Daten verlassen deinen Server (im Gegensatz zu Cloud APIs).

**F: Kann ich größeres Modell nutzen?**
A: Ja, `WHISPER_MODEL=base` für bessere Genauigkeit.

---

**Version**: 1.0
**Datum**: 2026-03-21
**Status**: ✅ Ready for Production
