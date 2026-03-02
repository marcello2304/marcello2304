# /test-rag — Kompletten RAG-Pfad testen

Testet den vollständigen RAG-Pfad: Daten → Vektorsuche → n8n → LLM → Antwort.

## Was du tun sollst

### Schritt 1: Testdaten einfügen (falls noch nicht vorhanden)

```bash
bash scripts/seed-test-data.sh --tenant demo
```

Falls Ollama verfügbar ist, mit echten Embeddings:
```bash
bash scripts/seed-test-data.sh --tenant demo --with-ollama
```

### Schritt 2: End-to-End CLI-Test

```bash
bash scripts/test-rag-path.sh --tenant demo --query "Was kostet das Pro-Paket?"
```

Führe weitere Testfragen aus:
```bash
bash scripts/test-rag-path.sh --tenant demo --query "Wie installiere ich ProManager?"
bash scripts/test-rag-path.sh --tenant demo --query "Gibt es einen NGO-Rabatt?"
bash scripts/test-rag-path.sh --tenant demo --query "Wie sicher sind meine Daten?"
```

### Schritt 3: Test-Webapp starten

```bash
bash scripts/serve-webapp.sh
```

Dann im Browser: http://localhost:8080

### Schritt 4: Ergebnisse analysieren

Prüfe für jeden Test:
- Werden die richtigen Chunks gefunden? (Ähnlichkeitswert > 0.6 = gut)
- Ist die LLM-Antwort korrekt und basiert auf den Quellen?
- Wird die Konversation in `tenant_demo.conversations` gespeichert?
- Wie hoch ist die Latenz? (Ziel: < 2s für Vektorsuche, < 5s gesamt)

### Schritt 5: HNSW Index erstellen (nach >1000 Embeddings)

```bash
# Erst wenn genug echte Daten vorhanden:
docker exec -e PGPASSWORD=$(grep POSTGRES_PASSWORD .env | cut -d= -f2) postgres-rag \
    psql -U postgres -d app_db -c \
    "SELECT public.create_vector_index('tenant_demo');"
```

## Bekannte Einschränkungen bei Dummy-Embeddings

Ohne Ollama (Dummy-Vektoren) sind die Suchergebnisse thematisch geclustert
aber nicht semantisch präzise. Der vollständige RAG-Pfad funktioniert dennoch —
nur die Relevanz der gefundenen Chunks ist reduziert.

Für echte Relevanz: `--with-ollama` Flag nutzen.
