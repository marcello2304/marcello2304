# /new-tenant — Neuen Kunden anlegen

Lege einen neuen Tenant (Kunden) im RAG-System an.

## Was du tun sollst

1. Frage den User nach diesen Informationen:
   - **Slug** (Pflicht): Kurzname, nur Kleinbuchstaben/Zahlen/Bindestrich, z.B. `acme` oder `muster-gmbh`
   - **Name** (Pflicht): Voller Firmenname, z.B. "ACME GmbH"
   - **E-Mail** (Pflicht): Admin-E-Mail des Kunden
   - **Plan** (optional): `starter` (Standard), `pro` oder `enterprise`

2. Validiere den Slug: muss `^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$` matchen

3. Führe aus:
   ```bash
   POSTGRES_CONTAINER=postgres-rag \
   POSTGRES_PASSWORD=$(grep POSTGRES_PASSWORD .env | cut -d= -f2) \
   bash scripts/create-tenant.sh <slug> "<name>" <email> <plan>
   ```

4. Zeige nach Anlage:
   - Schema-Name: `tenant_<slug>`
   - S3-Prefix: `tenants/<slug>/`
   - Tenant-ID aus Datenbank
   - Nächste Schritte für den Kunden

5. Frage ob sofort ein Test-Dokument hochgeladen werden soll

## Nachher zeigen

```
✓ Tenant angelegt: <name>
  Schema: tenant_<slug>
  S3-Prefix: tenants/<slug>/

Nächste Schritte für diesen Kunden:
1. Dokument hochladen via n8n Webhook:
   POST https://n8n.DOMAIN/webhook/ingest
   { "tenant_slug": "<slug>", "name": "...", "source_type": "file", ... }

2. Nach >1000 Embeddings: HNSW-Index erstellen:
   SELECT public.create_vector_index('tenant_<slug>');
```
