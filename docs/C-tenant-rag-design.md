# C. Multi-Tenant RAG Design

## Entscheidung: Schema-per-Tenant

### Warum Schema-per-Tenant (und nicht DB-per-Tenant oder RLS)?

**DB-per-Tenant:** Für 200+ Kunden ist das nicht sinnvoll. Jede Datenbank benötigt eigene Verbindungen, eigene Backup-Jobs, eigenes pgvector Setup. Management-Overhead ist zu hoch. Sinnvoll erst ab Enterprise-Kunden mit Datenisolationspflicht.

**Row Level Security (RLS):** Einfach einzurichten, aber bei pgvector-Queries mit Cosine-Similarity über große Mengen Performance-Probleme. RLS-Policies werden bei jedem Embedding-Query ausgewertet — das ist bei 200 Kunden mit je 50.000 Chunks messbar langsamer. Außerdem: ein Bug in der Policy-Definition kann Datenleck verursachen.

**Schema-per-Tenant (gewählt):**
- Klare Datentrennung auf Datenbankebene
- pgvector Index pro Schema — Queries scannen nur Tenant-Daten
- Kein Cross-Tenant Scan möglich (kein RLS-Bug-Risiko)
- Backup pro Schema möglich (`pg_dump -n tenant_abc`)
- Migration eines Kunden auf eigene DB später einfach
- Bis 100 Kunden problemlos performant
- Connection Pooling via PgBouncer reicht für 200+ Kunden

**Namenskonvention:** `tenant_<slug>` (z.B. `tenant_acme`, `tenant_muster_gmbh`)

---

## Tabellenmodell

### Zentrales Verwaltungsschema (public)

```sql
-- Schema für zentrale Verwaltung
-- Niemals Kundendaten hier speichern

CREATE TABLE public.tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT NOT NULL UNIQUE,           -- z.B. 'acme'
    name          TEXT NOT NULL,                  -- z.B. 'ACME GmbH'
    email         TEXT NOT NULL,
    plan          TEXT NOT NULL DEFAULT 'starter', -- starter|pro|enterprise
    status        TEXT NOT NULL DEFAULT 'active',  -- active|suspended|deleted
    schema_name   TEXT NOT NULL UNIQUE,            -- 'tenant_acme'
    s3_prefix     TEXT NOT NULL UNIQUE,            -- 'tenants/acme/'
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

CREATE TABLE public.tenant_usage (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES public.tenants(id),
    period_start  DATE NOT NULL,
    period_end    DATE NOT NULL,
    doc_count     INT DEFAULT 0,
    chunk_count   INT DEFAULT 0,
    embed_tokens  BIGINT DEFAULT 0,
    llm_tokens    BIGINT DEFAULT 0,
    s3_bytes      BIGINT DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON public.tenants(slug);
CREATE INDEX idx_tenants_status ON public.tenants(status);
CREATE INDEX idx_usage_tenant_period ON public.tenant_usage(tenant_id, period_start);
```

### Tenant-Schema (wird pro Kunde erstellt)

```sql
-- Template: wird bei Tenant-Onboarding ausgeführt
-- Ersetze 'tenant_acme' durch den tatsächlichen Schema-Namen

CREATE SCHEMA IF NOT EXISTS tenant_acme;

-- Erweiterung: pgvector (nur einmal pro DB nötig)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Quellen (Dokument-Ursprung)
CREATE TABLE tenant_acme.sources (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    source_type   TEXT NOT NULL,   -- 'file' | 'url' | 'api' | 'manual'
    origin_url    TEXT,            -- URL oder Pfad der Originalquelle
    s3_key        TEXT,            -- S3-Pfad: 'tenants/acme/docs/datei.pdf'
    file_name     TEXT,
    file_type     TEXT,            -- 'pdf' | 'docx' | 'txt' | 'html' | 'md'
    file_size     BIGINT,
    checksum      TEXT,            -- SHA256 des Originals
    status        TEXT NOT NULL DEFAULT 'pending', -- pending|processing|indexed|error
    error_message TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by    TEXT,            -- n8n workflow ID oder User
    tags          TEXT[] DEFAULT '{}',
    metadata      JSONB DEFAULT '{}'
);

-- Dokumente (verarbeitete Texte aus Sources)
CREATE TABLE tenant_acme.documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID NOT NULL REFERENCES tenant_acme.sources(id) ON DELETE CASCADE,
    title         TEXT,
    doc_type      TEXT,           -- 'faq' | 'manual' | 'product' | 'legal' | etc.
    language      TEXT DEFAULT 'de',
    version       INT NOT NULL DEFAULT 1,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    word_count    INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

-- Chunks (Abschnitte der Dokumente)
CREATE TABLE tenant_acme.chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES tenant_acme.documents(id) ON DELETE CASCADE,
    source_id     UUID NOT NULL REFERENCES tenant_acme.sources(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,         -- Position im Dokument (0-basiert)
    content       TEXT NOT NULL,        -- Klartext des Chunks
    content_hash  TEXT,                 -- SHA256 für Deduplizierung
    token_count   INT,
    char_count    INT,
    page_number   INT,                  -- falls PDF
    section       TEXT,                 -- Abschnittsüberschrift
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

-- Embeddings (Vektoren der Chunks)
CREATE TABLE tenant_acme.embeddings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id      UUID NOT NULL REFERENCES tenant_acme.chunks(id) ON DELETE CASCADE,
    model         TEXT NOT NULL,        -- 'nomic-embed-text' | 'mxbai-embed-large'
    model_version TEXT,
    vector        vector(768),          -- Dimension je nach Modell anpassen
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Access Control (welche Rollen sehen welche Quellen)
CREATE TABLE tenant_acme.access_rules (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID REFERENCES tenant_acme.sources(id) ON DELETE CASCADE,
    document_id   UUID REFERENCES tenant_acme.documents(id) ON DELETE CASCADE,
    role          TEXT NOT NULL,        -- 'public' | 'internal' | 'admin' | custom
    allow         BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_target CHECK (
        (source_id IS NOT NULL AND document_id IS NULL) OR
        (source_id IS NULL AND document_id IS NOT NULL)
    )
);

-- Konversationen (optional, für Audit)
CREATE TABLE tenant_acme.conversations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    TEXT NOT NULL,
    bot_id        TEXT,               -- Typebot Bot ID
    query         TEXT NOT NULL,
    response      TEXT,
    chunks_used   UUID[],             -- Referenz auf chunk IDs
    model         TEXT,
    latency_ms    INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB DEFAULT '{}'
);

CREATE INDEX idx_conv_session ON tenant_acme.conversations(session_id);
CREATE INDEX idx_conv_created ON tenant_acme.conversations(created_at DESC);
```

---

## pgvector Index-Strategie

```sql
-- HNSW Index (empfohlen für Production, schneller bei Queries)
-- Erstelle NACH dem Bulk-Import der ersten Embeddings (nicht vorher!)
CREATE INDEX idx_embeddings_vector_hnsw
ON tenant_acme.embeddings
USING hnsw (vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- IVFFlat Alternative (weniger RAM, gut für < 100k Vektoren)
-- Erst erstellen wenn mindestens 1000 Zeilen vorhanden:
-- CREATE INDEX idx_embeddings_vector_ivf
-- ON tenant_acme.embeddings
-- USING ivfflat (vector vector_cosine_ops)
-- WITH (lists = 100);

-- Weitere nützliche Indizes:
CREATE INDEX idx_embeddings_chunk ON tenant_acme.embeddings(chunk_id);
CREATE INDEX idx_embeddings_model ON tenant_acme.embeddings(model);

CREATE INDEX idx_chunks_document ON tenant_acme.chunks(document_id);
CREATE INDEX idx_chunks_source ON tenant_acme.chunks(source_id);
CREATE UNIQUE INDEX idx_chunks_doc_idx ON tenant_acme.chunks(document_id, chunk_index);
CREATE INDEX idx_chunks_content_hash ON tenant_acme.chunks(content_hash) WHERE content_hash IS NOT NULL;

CREATE INDEX idx_documents_source ON tenant_acme.documents(source_id);
CREATE INDEX idx_documents_active ON tenant_acme.documents(is_active) WHERE is_active = true;
CREATE INDEX idx_documents_type ON tenant_acme.documents(doc_type);

CREATE INDEX idx_sources_status ON tenant_acme.sources(status);
CREATE INDEX idx_sources_type ON tenant_acme.sources(source_type);
CREATE INDEX idx_sources_created ON tenant_acme.sources(created_at DESC);

-- Volltext-Index für Hybrid-Search (Vektor + Keyword):
CREATE INDEX idx_chunks_fts ON tenant_acme.chunks
USING gin(to_tsvector('german', content));
```

### Embedding-Dimensionen je Modell

| Modell | Dimension | Hinweis |
|--------|-----------|---------|
| nomic-embed-text | 768 | Standard, gut für DE/EN |
| mxbai-embed-large | 1024 | Bessere Qualität, mehr RAM |
| all-minilm | 384 | Sehr schnell, geringere Qualität |
| text-embedding-3-small (OpenAI) | 1536 | Falls OpenAI genutzt |

**Empfehlung für diesen Stack:** `nomic-embed-text` über Ollama (lokal, DSGVO-konform)

---

## SQL Migrationen (nummeriert)

Die vollständigen Migration-Files sind in `/sql/`:

- `001_extensions.sql` — pgvector, uuid-ossp
- `002_public_schema.sql` — tenants, tenant_usage
- `003_tenant_template.sql` — Template für Schema-Erstellung
- `004_functions.sql` — Hilfsfunktionen (create_tenant, search_chunks)
- `005_roles.sql` — DB-Rollen und Rechte

---

## RAG-Query zur Laufzeit (Typebot → n8n → Postgres)

```sql
-- Semantic Search innerhalb eines Tenant-Schemas
-- Parameter: $1 = query_vector, $2 = top_k, $3 = min_similarity
SELECT
    c.id AS chunk_id,
    c.content,
    c.chunk_index,
    c.page_number,
    c.section,
    d.title AS document_title,
    d.doc_type,
    s.file_name,
    s.s3_key,
    1 - (e.vector <=> $1::vector) AS similarity
FROM tenant_acme.embeddings e
JOIN tenant_acme.chunks c ON c.id = e.chunk_id
JOIN tenant_acme.documents d ON d.id = c.document_id
JOIN tenant_acme.sources s ON s.id = c.source_id
WHERE
    d.is_active = true
    AND s.status = 'indexed'
    AND e.model = 'nomic-embed-text'
    AND 1 - (e.vector <=> $1::vector) >= $3
ORDER BY e.vector <=> $1::vector
LIMIT $2;
```

### Hybrid Search (Vektor + Volltext):
```sql
-- Kombiniert Semantic + Keyword für bessere Relevanz
WITH semantic AS (
    SELECT
        c.id,
        c.content,
        1 - (e.vector <=> $1::vector) AS sem_score
    FROM tenant_acme.embeddings e
    JOIN tenant_acme.chunks c ON c.id = e.chunk_id
    JOIN tenant_acme.documents d ON d.id = c.document_id
    WHERE d.is_active = true AND e.model = 'nomic-embed-text'
    ORDER BY e.vector <=> $1::vector
    LIMIT 20
),
keyword AS (
    SELECT
        c.id,
        ts_rank(to_tsvector('german', c.content), plainto_tsquery('german', $2)) AS kw_score
    FROM tenant_acme.chunks c
    WHERE to_tsvector('german', c.content) @@ plainto_tsquery('german', $2)
    LIMIT 20
)
SELECT
    s.id,
    s.content,
    s.sem_score,
    COALESCE(k.kw_score, 0) AS kw_score,
    (s.sem_score * 0.7 + COALESCE(k.kw_score, 0) * 0.3) AS final_score
FROM semantic s
LEFT JOIN keyword k ON k.id = s.id
ORDER BY final_score DESC
LIMIT $3;
```

---

## Tenant-Verwaltung: Namenskonventionen

### S3-Struktur pro Tenant
```
tenants/
  acme/
    docs/        ← Original-Uploads (PDF, DOCX, etc.)
    audio/       ← Voice-Recordings
    assets/      ← Bilder, Medien
    exports/     ← Generierte Reports, Exports
    tmp/         ← Temporäre Dateien (Lifecycle: 7 Tage)
  muster-gmbh/
    docs/
    audio/
    ...
```

### DB-Schema pro Tenant
```
tenant_acme          ← Schema-Name = 'tenant_' + slug
tenant_muster_gmbh
tenant_xyz_holding
```

### Sichtbarkeit und Sortierung in n8n
Queries in n8n immer mit explizitem Schema:
```sql
SET search_path TO tenant_acme, public;
SELECT * FROM sources ORDER BY created_at DESC;
```

Oder vollqualifiziert:
```sql
SELECT * FROM tenant_acme.sources ORDER BY created_at DESC;
```
