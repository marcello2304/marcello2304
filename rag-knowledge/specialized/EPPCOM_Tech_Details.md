# EPPCOM Technical Deep-Dive

## RAG-Pipeline Architektur

### Komponenten-Stack

Der EPPCOM RAG-Stack besteht aus folgenden Komponenten:

1. Dokument Upload: Benutzer lädt PDFs, Word-Dateien oder Markdown-Dokumente hoch
2. n8n Workflow Document Processor: Automatische Verarbeitung der hochgeladenen Dokumente
3. Text Extraction: Textextraktion mittels pdf.js, mammoth oder pandoc
4. Chunking: RecursiveCharacterTextSplitter mit 800 Zeichen Chunks und 200 Zeichen Overlap
5. Embedding: qwen3-embedding:0.6b generiert 1024-dimensionale Vektoren
6. Storage: PostgreSQL mit pgvector Extension und HNSW Index

Bei einer Benutzeranfrage:
1. Query Embedding: Selbes Embedding-Modell wie beim Ingest
2. Vector Search: pgvector Cosine Similarity, Top-5 Ergebnisse
3. Reranking: Optional Cross-Encoder für höhere Präzision
4. LLM Context: Top-3 Chunks plus System-Prompt
5. Generation: qwen2.5:7b mit temperature 0.7

### Datenbank-Schema

Die RAG-Daten werden in vier Tabellen gespeichert:

- **sources**: Metadaten der hochgeladenen Dokumente (Dateiname, Typ, Tenant-Zuordnung)
- **documents**: Extrahierter Volltext mit Referenz zur Source
- **chunks**: Zerlegte Textabschnitte mit Position und Referenz zum Dokument
- **embeddings**: 1024-dimensionale Vektoren mit pgvector, verknüpft mit Chunks

Alle Tabellen sind über tenant_id isoliert für Multi-Tenant-Betrieb.

### Performance-Optimierungen
- **HNSW Index**: 50x schneller als IVFFlat bei mehr als 10k Chunks
- **Chunk-Caching**: Häufige Queries werden gecached (60s TTL)
- **Batch-Processing**: Embedding-Generierung in Batches von 32 Chunks
- **Connection Pooling**: Effizientes Connection-Management für PostgreSQL

### Embedding-Modell: qwen3-embedding:0.6b
- **Dimensionen**: 1024
- **Modell-Größe**: ca. 600 MB
- **Geschwindigkeit**: ca. 50ms für 500 Tokens
- **Qualität**: Sehr gut für deutschsprachige Business-Dokumente
- **Hosting**: Lokal auf Server 2 (Hetzner Deutschland)

## Voicebot-Latency-Optimierung

### Ziel: Unter 2 Sekunden von Sprache zu Sprache

**Breakdown**:
1. STT (Whisper): ca. 300-500ms
2. RAG Retrieval: ca. 50-100ms (mit HNSW-Index)
3. LLM Generation: ca. 800-1200ms (qwen2.5:7b, 50 tokens)
4. TTS (Cartesia): ca. 200-400ms

**Total**: 1350-2200ms

**Optimierungen**:
- Whisper: lokal auf Server 2 (GPU) statt API-Call
- LLM: Streaming aktivieren (erste Wörter früher verfügbar)
- TTS: Sentence-Level-Streaming (nicht warten bis komplette Antwort fertig)
- LiveKit: WebRTC statt SIP für niedrigere Netzwerk-Latenz

### Streaming-Implementierung
Die LLM-Antwort wird per Streaming an den TTS-Dienst gesendet. Sobald ein vollständiger Satz generiert ist, beginnt die Sprachsynthese - der Benutzer hört die ersten Wörter, während das LLM noch weitere generiert. Dies reduziert die wahrgenommene Latenz auf unter 1 Sekunde.

## Multi-Tenancy und Datenisolation

### Sicherheits-Architektur
Jeder Kunde (Tenant) hat seine eigenen isolierten RAG-Dokumente. Die Isolation wird auf Datenbankebene durch tenant_id-Filterung in allen Queries sichergestellt.

### Funktionsweise
- Jeder API-Request enthält die Tenant-ID aus dem JWT-Token
- Alle Datenbankabfragen filtern automatisch nach tenant_id
- Ein Tenant kann niemals auf Dokumente eines anderen Tenants zugreifen
- SuperAdmin-Zugriff kann tenant-übergreifend erfolgen (für Verwaltung)

### Benutzer-Rollen
- **SuperAdmin**: Voller Zugriff auf alle Tenants, kann Tenants erstellen/löschen
- **Admin**: Voller Zugriff innerhalb des eigenen Tenants
- **User**: Zugriff auf zugewiesene Dokumente, kann RAG-Abfragen stellen

## Skalierungs-Metriken

### Server-Kapazitäten (Stand März 2026)
- **Server 1** (CX23, 94.130.170.167): 4 vCPU, 8 GB RAM - Admin-UI, PostgreSQL, n8n, Typebot
- **Server 2** (CX33, 46.224.54.65): 8 vCPU, 16 GB RAM - Ollama (LLM + Embeddings)

### Concurrent Users
- **Chatbot**: ca. 50 gleichzeitige Sessions (RAM-limitiert durch PostgreSQL Connections)
- **Voicebot**: ca. 10 gleichzeitige Anrufe (CPU-limitiert durch LLM-Inferenz)

### Skalierungs-Strategie
1. **0-10 Kunden**: Aktueller Stack ausreichend
2. **10-50 Kunden**: Server 2 auf CX53 (32 GB RAM) upgraden
3. **50-200 Kunden**: Horizontale Skalierung mit dediziertem PostgreSQL-Server, Load Balancer vor n8n-Instanzen, Ollama auf 2-3 Servern (Round-Robin)

## Technologie-Stack Übersicht

### Backend & Infrastruktur
- **FastAPI**: Python Web-Framework für die Admin-UI API
- **PostgreSQL + pgvector**: Relationale Datenbank mit Vektor-Erweiterung
- **n8n**: Workflow-Automatisierung (Self-Hosted)
- **Typebot**: Chatbot-Builder (Self-Hosted)
- **Ollama**: LLM-Inference-Server (Self-Hosted)
- **Docker + Coolify**: Container-Orchestrierung und Deployment
- **Traefik**: Reverse Proxy mit automatischen SSL-Zertifikaten

### KI-Modelle
- **qwen2.5:7b**: Haupt-LLM für Textgenerierung (7B Parameter, 4-bit Quantisierung)
- **qwen3-embedding:0.6b**: Embedding-Modell für Vektorisierung (595M Parameter)
- **Whisper**: Speech-to-Text (lokal oder API)
- **Cartesia**: Text-to-Speech für natürliche Sprachausgabe

### Kommunikation & Echtzeit
- **LiveKit**: WebRTC-basierte Echtzeit-Audio/Video-Plattform
- **Jitsi Meet**: Video-Konferenz-Lösung (Self-Hosted)
- **JWT-Authentifizierung**: Sichere Token-basierte Zugriffskontrolle

### Deployment
- **Hetzner Cloud**: Deutsche Rechenzentren (Nürnberg, Falkenstein)
- **Coolify**: Self-Hosted PaaS für Container-Management
- **GitHub**: Versionskontrolle und CI/CD
- **Let's Encrypt**: Automatische SSL-Zertifikate via Traefik
