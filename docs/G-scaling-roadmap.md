# G. Skalierungs-Roadmap

## Phase 1: 0–20 Kunden (Start-Setup)

### Hardware
```
Server 1 (App + DB):
  Hetzner CCX23: 4 vCPU, 16 GB RAM, 160 GB NVMe
  Kosten: ~€50/Monat

Server 2 (LLM + Voice):
  Hetzner AX42 (Bare Metal) oder CCX53: GPU optional
  Mind. 8 Cores, 32 GB RAM für Ollama llama3.2:3b
  Kosten: ~€100/Monat (dedicated)
```

### Setup
- Single PostgreSQL Instanz (pgvector/pgvector:pg16)
- Schema-per-Tenant (wie in C beschrieben)
- n8n Standard-Modus (kein Queue-Mode)
- Typebot Builder + Viewer getrennt
- Hetzner Object Storage (fsn1)

### Trigger für Phase 2
| Metrik | Schwellenwert |
|--------|--------------|
| Postgres RAM-Nutzung | > 8 GB dauerhaft |
| Postgres CPU | > 60% über 1h |
| Postgres DB-Größe | > 50 GB |
| n8n Execution Queue | > 50 pending |
| API-Latenz RAG-Query | > 2s p95 |
| Kunden-Anzahl | > 20 |

---

## Phase 2: 20–50 Kunden (Optimierung)

### Was sich ändert
1. **PostgreSQL-Tuning** (kein neuer Server nötig):
```ini
# /var/lib/postgresql/data/postgresql.conf
# Für 16 GB RAM Server:
shared_buffers = 4GB           # 25% RAM
effective_cache_size = 12GB    # 75% RAM
work_mem = 256MB               # pro Verbindung
maintenance_work_mem = 1GB
max_connections = 100
random_page_cost = 1.1         # NVMe SSD
effective_io_concurrency = 200 # NVMe
wal_buffers = 64MB
checkpoint_completion_target = 0.9
```

2. **PgBouncer als Connection Pooler:**
```
PgBouncer (Docker) → PostgreSQL
n8n, Typebot → PgBouncer:5433 → Postgres:5432
Pool Mode: transaction (für n8n)
Max Client Connections: 200
Default Pool Size: 25
```

3. **n8n Queue-Mode:**
```
n8n Worker + Redis für parallele Workflow-Execution
N8N_EXECUTIONS_MODE=queue
QUEUE_BULL_REDIS_HOST=redis
```

4. **Server 1 Upgrade:**
```
Hetzner CCX33: 8 vCPU, 32 GB RAM, 240 GB NVMe
```

### Trigger für Phase 3
| Metrik | Schwellenwert |
|--------|--------------|
| DB-Größe RAG-Daten | > 100 GB |
| Embedding-Count | > 5 Millionen |
| Kunden-Anzahl | > 50 |
| Postgres IOPS | > 5000 sustained |
| p99 RAG-Query Latenz | > 3s |
| Concurrent DB-Connections | > 80 |

---

## Phase 3: 50–100 Kunden (Separation)

### Kernänderung: RAG DB trennen von App DB

```
Server 1a (App-Schicht):
  n8n, Typebot, Coolify
  PostgreSQL: app_db, typebot_db
  Hetzner CCX23: 4 vCPU, 16 GB RAM

Server 1b (RAG DB):
  PostgreSQL + pgvector (nur RAG-Schemas)
  Hetzner CCX53: 16 vCPU, 64 GB RAM, 480 GB NVMe (RAID-Option prüfen)
  Read Replica auf Hetzner (für RAG Queries)
```

### PostgreSQL Streaming Replication einrichten

```bash
# Primary (Server 1b):
# postgresql.conf:
wal_level = replica
max_wal_senders = 3
wal_keep_size = 1GB
hot_standby = on

# pg_hba.conf:
host replication replicator <replica-ip>/32 scram-sha-256

# Replica einrichten:
pg_basebackup -h <primary-ip> -U replicator -D /var/lib/postgresql/data -P -Xs -R
```

Schreibzugriff (Ingestion) → Primary
Lesezugriff (RAG Queries) → Read Replica

n8n RAG Query-Node:
```
DB_POSTGRESDB_HOST_READ=<replica-ip>   # für SELECT
DB_POSTGRESDB_HOST_WRITE=<primary-ip>  # für INSERT/UPDATE
```

### HNSW Index-Tuning für große Datasets

```sql
-- Bei 5M+ Vektoren:
DROP INDEX idx_embed_hnsw;
CREATE INDEX idx_embed_hnsw
ON tenant_acme.embeddings
USING hnsw (vector vector_cosine_ops)
WITH (m = 32, ef_construction = 128);  -- Höhere Qualität, mehr RAM

-- RAM für HNSW schätzen:
-- m=16: ~0.1 GB pro 1M Vektoren (768d)
-- m=32: ~0.2 GB pro 1M Vektoren (768d)
```

### Trigger für Phase 4
| Metrik | Schwellenwert |
|--------|--------------|
| Kunden-Anzahl | > 100 |
| RAG DB-Größe | > 500 GB |
| HNSW Index-RAM | > 20 GB |
| p99 RAG-Latenz trotz Replica | > 2s |
| Monatliche Kosten DB | > €300 |

---

## Phase 4: 100–200+ Kunden (Sharding)

### Strategie: Tenant-Gruppen auf mehrere DB-Instanzen

```
Shard A (Kunden 1-50):    Postgres A, 64 GB RAM, NVMe
Shard B (Kunden 51-100):  Postgres B, 64 GB RAM, NVMe
Shard C (Kunden 101-200): Postgres C, 64 GB RAM, NVMe
```

Routing-Tabelle in public.tenants:
```sql
ALTER TABLE public.tenants ADD COLUMN db_shard TEXT DEFAULT 'shard_a';
-- Neue Kunden kommen auf am wenigsten ausgelasteten Shard
```

n8n Router-Workflow:
```javascript
// Entscheide DB-Connection basierend auf Tenant-Shard
const shard = tenant.db_shard;
const connectionStrings = {
  'shard_a': process.env.DB_SHARD_A,
  'shard_b': process.env.DB_SHARD_B,
  'shard_c': process.env.DB_SHARD_C,
};
return connectionStrings[shard];
```

### Alternative: Citus (Distributed Postgres)

Für 200+ Kunden mit hohem Write-Volume:
```
Citus Coordinator + 3x Worker-Nodes
Verteilung nach tenant_id (Hash Sharding)
```
Nur wenn Sharding-Overhead sich lohnt (>500 Kunden, >TB Daten).

---

## Monitoring: Konkrete Metriken und Tools

### Stack-Empfehlung

```
Prometheus → Postgres Exporter, Node Exporter, n8n Metrics
Grafana → Dashboards
Alertmanager → Email/Slack bei Schwellenwert
```

In Coolify deployen:
```
Coolify → Resources → New → Docker Image
Image: prom/prometheus:latest
Image: grafana/grafana:latest
Image: wrouesnel/postgres_exporter:latest
```

### Kritische Metriken und Alert-Schwellen

#### PostgreSQL

```yaml
# Prometheus Alert Rules:

- alert: PostgresHighConnections
  expr: pg_stat_activity_count > 80
  for: 5m
  annotations:
    summary: "PgBouncer oder Connection Limit erhöhen"

- alert: PostgresHighCPU
  expr: rate(pg_stat_bgwriter_checkpoint_sync_time_total[5m]) > 1000
  for: 10m

- alert: PostgresSlowQueries
  expr: pg_stat_statements_mean_time_seconds > 2
  for: 5m
  annotations:
    summary: "RAG Query > 2s — Index oder Abfrage optimieren"

- alert: PostgresDiskFull
  expr: (pg_database_size_bytes / node_filesystem_size_bytes) > 0.8
  for: 1m
  severity: critical

- alert: ReplicationLag
  expr: pg_replication_lag_seconds > 30
  for: 2m
  annotations:
    summary: "Read Replica hinkt nach"
```

#### Server-Level

```yaml
- alert: HighRAM
  expr: (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) < 0.15
  for: 10m
  annotations:
    summary: "< 15% RAM frei — Server upgraden oder PgBouncer tunen"

- alert: HighCPU
  expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
  for: 15m

- alert: DiskIOPS
  expr: rate(node_disk_io_time_seconds_total[5m]) > 0.9
  for: 10m
  annotations:
    summary: "Disk I/O > 90% — NVMe wechseln oder Caching erhöhen"
```

### Grafana Dashboard: Wichtigste Panels

```
1. RAG Query Latency (p50, p95, p99) — Ziel: p95 < 1.5s
2. Active DB Connections — Alarm bei > 80% Max
3. Embedding Count per Tenant (täglich)
4. n8n Execution Queue Size
5. S3 Storage per Tenant (Wachstum)
6. Server Memory / CPU / Disk per Node
```

---

## Skalierungs-Trigger Zusammenfassung

| Phase | Kunden | Trigger-Metrik | Aktion |
|-------|--------|---------------|--------|
| 1→2 | 20 | RAM > 8 GB oder Latenz > 2s | Server-Upgrade + PgBouncer |
| 2→3 | 50 | RAG DB > 100 GB oder > 5M Embeddings | Separate RAG-DB + Read Replica |
| 3→4 | 100 | RAG DB > 500 GB oder > 50M Embeddings | Tenant-Sharding |
| 4+ | 200+ | > 1 TB oder Response Latenz trotz Shard | Citus oder dedizierte Tenant-DBs |

---

## Kosten-Schätzung pro Phase (Hetzner)

| Phase | Kunden | Server-Kosten/Monat | S3 (~500 MB/Kunde) |
|-------|--------|--------------------|--------------------|
| 1 | 0-20 | €150 | €5 |
| 2 | 20-50 | €200 | €12 |
| 3 | 50-100 | €350 | €25 |
| 4 | 100-200 | €600 | €50 |

*Ollama/LLM auf Server 2 ist größter Kostenpunkt — GPU-Optionen ab Phase 3 prüfen.*
