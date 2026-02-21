# D. Ingestion Workflow (n8n) + S3-Struktur

## Überblick: Standard Ingestion Flow

```
User/Admin                n8n                    Postgres           S3 / Ollama
    │                      │                         │                  │
    │──Upload File/URL────►│                         │                  │
    │                      │──Upload zu S3──────────────────────────►│  │
    │                      │◄──S3 Key────────────────────────────────│  │
    │                      │                         │                  │
    │                      │──INSERT source──────────►│                  │
    │                      │◄──source_id─────────────│                  │
    │                      │                         │                  │
    │                      │──Text extrahieren       │                  │
    │                      │  (PDF/DOCX/HTML/TXT)    │                  │
    │                      │                         │                  │
    │                      │──Chunking (500-1000 tok)│                  │
    │                      │                         │                  │
    │                      │──INSERT document────────►│                  │
    │                      │──INSERT chunks (batch)──►│                  │
    │                      │                         │                  │
    │                      │──Embed Request─────────────────────────►│  │
    │                      │  (nomic-embed-text)      │               │  │
    │                      │◄──Vectors────────────────────────────────│  │
    │                      │                         │                  │
    │                      │──INSERT embeddings──────►│                  │
    │                      │──UPDATE source.status──►│                  │
    │                      │  ('indexed')             │                  │
    │                      │                         │                  │
    │◄──Fertig Callback───│                         │                  │
```

---

## n8n Workflow 1: Document Ingestion

### Nodes (in Reihenfolge)

| # | Node-Typ | Name | Zweck |
|---|----------|------|-------|
| 1 | Webhook | `POST /webhook/ingest` | Empfängt Upload-Request |
| 2 | Code (JS) | `Validate Input` | Schema prüfen, Tenant-Slug validieren |
| 3 | Postgres | `Get Tenant` | Tenant aus public.tenants laden |
| 4 | Switch | `Source Type?` | file / url / text verzweigen |
| 5a | HTTP Request | `Download URL` | Bei URL: Seite fetchen |
| 5b | Binary Data | `Process File` | Bei File: aus Request lesen |
| 6 | S3 Upload | `Upload to S3` | Original in S3 speichern |
| 7 | Postgres | `Insert Source` | source-Eintrag anlegen |
| 8 | Code (JS) | `Extract Text` | Text aus Binary (PDF/DOCX/HTML) |
| 9 | Code (JS) | `Chunk Text` | Text in 500-Token Chunks aufteilen |
| 10 | Postgres | `Insert Document` | Dokument-Eintrag |
| 11 | Postgres | `Insert Chunks` | Chunks in Batch einfügen |
| 12 | Split In Batches | `Batch Chunks` | 10 Chunks pro Batch |
| 13 | HTTP Request | `Get Embeddings` | Ollama nomic-embed-text |
| 14 | Code (JS) | `Map Vectors` | Vektoren den Chunks zuordnen |
| 15 | Postgres | `Insert Embeddings` | Embeddings speichern |
| 16 | Postgres | `Update Source Status` | status = 'indexed' |
| 17 | Postgres | `Create HNSW Index` | Nach 1000+ Chunks: Index-Check |
| 18 | HTTP Request | `Callback/Notify` | Optional: Typebot oder Webhook |

### Webhook Request-Format (JSON Body)

```json
{
  "tenant_slug": "acme",
  "name": "Produkthandbuch v2.3",
  "source_type": "file",
  "doc_type": "manual",
  "language": "de",
  "tags": ["produkt", "handbuch"],
  "file_base64": "JVBERi0x...",
  "file_name": "handbuch_v2.pdf",
  "file_type": "pdf",
  "created_by": "n8n-upload-form"
}
```

Oder bei URL-Quelle:
```json
{
  "tenant_slug": "acme",
  "name": "FAQ Seite",
  "source_type": "url",
  "doc_type": "faq",
  "origin_url": "https://acme.de/faq"
}
```

---

## n8n Workflow 2: RAG Retrieval (für Typebot)

### Nodes

| # | Node-Typ | Name | Zweck |
|---|----------|------|-------|
| 1 | Webhook | `POST /webhook/rag-query` | Query von Typebot empfangen |
| 2 | Code (JS) | `Validate` | tenant_slug + query prüfen |
| 3 | HTTP Request | `Embed Query` | Query-Text → Vektor via Ollama |
| 4 | Postgres | `Vector Search` | Ähnlichste Chunks finden |
| 5 | Code (JS) | `Build Context` | Chunks zu Prompt-Context zusammenbauen |
| 6 | HTTP Request | `LLM Call` | Ollama mit Context + Query |
| 7 | Postgres | `Log Conversation` | Antwort in conversations speichern |
| 8 | Respond to Webhook | `Return Response` | JSON an Typebot zurückgeben |

### Query Request-Format

```json
{
  "tenant_slug": "acme",
  "query": "Wie installiere ich das Produkt?",
  "session_id": "typebot-session-abc123",
  "bot_id": "typebot-bot-id",
  "top_k": 5,
  "min_similarity": 0.6,
  "doc_type": null,
  "model": "llama3.2:3b"
}
```

### Response-Format

```json
{
  "answer": "Um das Produkt zu installieren...",
  "sources": [
    {
      "chunk_id": "uuid",
      "document_title": "Produkthandbuch v2.3",
      "similarity": 0.87,
      "page_number": 12,
      "section": "Installation"
    }
  ],
  "model": "llama3.2:3b",
  "latency_ms": 1240
}
```

---

## n8n Code-Node: Text Chunking

```javascript
// Node: "Chunk Text"
// Voraussetzung: items[0].json.extracted_text

const CHUNK_SIZE = 1000;     // Zeichen (ca. 250 Tokens)
const CHUNK_OVERLAP = 150;   // Überlappung für Kontext-Kontinuität

function chunkText(text, size, overlap) {
  const chunks = [];
  let start = 0;
  let index = 0;

  // Normalisieren
  text = text.replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();

  while (start < text.length) {
    let end = start + size;

    // Auf Satzgrenze snappen (kein Wort mitte zerteilen)
    if (end < text.length) {
      const lastPeriod = text.lastIndexOf('.', end);
      const lastNewline = text.lastIndexOf('\n', end);
      const boundary = Math.max(lastPeriod, lastNewline);
      if (boundary > start + size * 0.5) {
        end = boundary + 1;
      }
    }

    const content = text.substring(start, end).trim();
    if (content.length > 50) {  // Min-Länge
      chunks.push({
        chunk_index: index,
        content: content,
        char_count: content.length,
        content_hash: null  // SHA256 in DB oder hier berechnen
      });
      index++;
    }

    start = end - overlap;
    if (start <= 0) start = end;  // Safety
  }

  return chunks;
}

const extractedText = $input.first().json.extracted_text;
const chunks = chunkText(extractedText, CHUNK_SIZE, CHUNK_OVERLAP);

return chunks.map(chunk => ({ json: chunk }));
```

---

## n8n Code-Node: Build RAG Context

```javascript
// Node: "Build Context"
// Input: chunks aus Vector Search

const MAX_CONTEXT_CHARS = 4000;
const query = $('Validate').first().json.query;

const chunks = $input.all().map(item => item.json);

// Sortiert nach Similarity DESC (bereits von DB sortiert)
let contextParts = [];
let totalChars = 0;

for (const chunk of chunks) {
  const text = `[${chunk.document_title || 'Quelle'}, Seite ${chunk.page_number || '?'}]:\n${chunk.content}`;
  if (totalChars + text.length > MAX_CONTEXT_CHARS) break;
  contextParts.push(text);
  totalChars += text.length;
}

const context = contextParts.join('\n\n---\n\n');

const systemPrompt = `Du bist ein hilfreicher Assistent. Beantworte die Frage ausschließlich auf Basis der folgenden Quellen. Falls die Antwort nicht in den Quellen enthalten ist, sage das ehrlich.

QUELLEN:
${context}`;

const userMessage = query;

return [{
  json: {
    system_prompt: systemPrompt,
    user_message: userMessage,
    chunks_used: chunks.map(c => c.chunk_id)
  }
}];
```

---

## n8n HTTP Request: Ollama Embedding

```
Method: POST
URL: https://ollama.deine-domain.de/api/embeddings

Headers:
  Content-Type: application/json
  Authorization: Bearer {{ $env.OLLAMA_API_KEY }}

Body (JSON):
{
  "model": "nomic-embed-text",
  "prompt": "{{ $json.content }}"
}
```

Response-Mapping:
```javascript
// In Code-Node nach HTTP Request:
return [{ json: {
  ...($input.first().json),
  embedding: $input.first().json.embedding  // Array von Floats
}}];
```

---

## n8n HTTP Request: Ollama LLM Call

```
Method: POST
URL: https://ollama.deine-domain.de/api/chat

Headers:
  Content-Type: application/json
  Authorization: Bearer {{ $env.OLLAMA_API_KEY }}

Body (JSON):
{
  "model": "{{ $json.model || 'llama3.2:3b' }}",
  "stream": false,
  "messages": [
    {
      "role": "system",
      "content": "{{ $json.system_prompt }}"
    },
    {
      "role": "user",
      "content": "{{ $json.user_message }}"
    }
  ],
  "options": {
    "temperature": 0.1,
    "num_ctx": 4096
  }
}
```

---

## S3 Konfiguration (Hetzner Object Storage)

### Bucket-Setup

```
Region: fsn1 (Falkenstein) oder nbg1 (Nürnberg)
Bucket-Name: rag-platform-prod
Access Control: Private (kein öffentlicher Zugriff)
```

### Endpoint-Konfiguration

```
Endpoint: https://fsn1.your-objectstorage.com
Region: eu-central (Hetzner nutzt diesen Wert)
Path Style: true (NICHT virtual-hosted-style bei Hetzner!)
Access Key: HT_ACCESS_KEY_HIER
Secret Key: HT_SECRET_KEY_HIER
```

**Wichtig: Hetzner S3 braucht `path style = true`**
Virtual-hosted-style (`bucket.endpoint`) funktioniert bei Hetzner NICHT standardmäßig.

### n8n S3 Node Konfiguration

```
Service: AWS S3 (n8n nutzt S3-kompatibles Interface)
Credential Type: Amazon S3

Credentials:
  Access Key ID: <HETZNER_ACCESS_KEY>
  Secret Access Key: <HETZNER_SECRET_KEY>
  Region: eu-central-003 (oder was Hetzner vorgibt)
  Endpoint: https://fsn1.your-objectstorage.com
  Force Path Style: ✓ aktiviert
```

### Upload-Pfad-Schema

```
Bucket: rag-platform-prod

Struktur:
  tenants/<slug>/docs/<year>/<month>/<uuid>-<filename>
  tenants/<slug>/audio/<year>/<month>/<uuid>.webm
  tenants/<slug>/assets/<uuid>-<filename>
  tenants/<slug>/exports/<date>-<report-name>.pdf
  tenants/<slug>/tmp/<uuid>   ← Lifecycle: 7 Tage TTL

Beispiel:
  tenants/acme/docs/2024/11/a1b2c3d4-handbuch_v2.pdf
  tenants/acme/audio/2024/11/e5f6g7h8.webm
```

### S3 Lifecycle Rules (im Hetzner Panel)

```json
{
  "Rules": [
    {
      "ID": "delete-tmp-files",
      "Filter": { "Prefix": "tenants/" },
      "Status": "Enabled",
      "Expiration": {
        "Days": 7
      },
      "Filter": { "Prefix": "tenants/*/tmp/" }
    }
  ]
}
```

---

## ENV Variablen (n8n in Coolify)

```bash
# n8n Core
N8N_HOST=n8n.deine-domain.de
N8N_PROTOCOL=https
N8N_PORT=5678
WEBHOOK_URL=https://n8n.deine-domain.de/
N8N_EDITOR_BASE_URL=https://n8n.deine-domain.de/
N8N_ENCRYPTION_KEY=<32-char-random-string>

# PostgreSQL
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=postgres
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_DATABASE=app_db
DB_POSTGRESDB_USER=n8n_user
DB_POSTGRESDB_PASSWORD=<sicheres-passwort>
DB_POSTGRESDB_SCHEMA=n8n

# S3 / Hetzner Object Storage
N8N_DEFAULT_BINARY_DATA_MODE=filesystem
# Oder S3 als Binary Storage:
# N8N_DEFAULT_BINARY_DATA_MODE=s3
# N8N_BINARY_DATA_S3_BUCKET=rag-platform-prod
# N8N_BINARY_DATA_S3_REGION=eu-central-003
# N8N_BINARY_DATA_S3_ENDPOINT=https://fsn1.your-objectstorage.com

# Ollama (als n8n-Credential gespeichert, nicht ENV)
OLLAMA_BASE_URL=https://ollama.deine-domain.de
OLLAMA_API_KEY=<bearer-token>

# Security
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<sicheres-passwort>
N8N_SECURE_COOKIE=true
N8N_JWT_SECRET=<32-char-random-string>

# Executions
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168
EXECUTIONS_DATA_PRUNE_MAX_COUNT=10000
```

## ENV Variablen (Typebot Builder in Coolify)

```bash
# Typebot Core
NEXTAUTH_URL=https://builder.deine-domain.de
NEXTAUTH_SECRET=<32-char-random-string>
NEXT_PUBLIC_VIEWER_URL=https://bot.deine-domain.de

# PostgreSQL
DATABASE_URL=postgresql://typebot_user:password@postgres:5432/typebot_db

# S3 / Hetzner Object Storage
S3_ACCESS_KEY=<HETZNER_ACCESS_KEY>
S3_SECRET_KEY=<HETZNER_SECRET_KEY>
S3_BUCKET=rag-platform-prod
S3_REGION=eu-central-003
S3_ENDPOINT=https://fsn1.your-objectstorage.com
S3_PORT=443
S3_SSL=true

# E-Mail (für Auth)
SMTP_HOST=<smtp-server>
SMTP_PORT=587
SMTP_AUTH_USER=<email>
SMTP_AUTH_PASS=<password>
SMTP_SECURE=false
NEXT_PUBLIC_SMTP_FROM=noreply@deine-domain.de

# RAG via n8n Webhook
N8N_RAG_WEBHOOK_URL=https://n8n.deine-domain.de/webhook/rag-query
N8N_RAG_SECRET=<shared-secret>

# Optional: Disable Sign-ups (nur Einladungen)
DISABLE_SIGNUP=true
```
