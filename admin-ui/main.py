"""
EPPCOM RAG Admin UI — FastAPI Backend
Deployment: Docker auf Server 1 via Coolify
URL: https://admin.eppcom.de (oder coolify.eppcom.de:3333 lokal)
"""
import os
import uuid
import hashlib
import json
import io
from datetime import datetime
from typing import Optional, List

import asyncpg
import httpx
import boto3
from botocore.client import Config
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguration
# ──────────────────────────────────────────────────────────────────────────────
DB_DSN      = os.getenv("DATABASE_URL",  "postgresql://appuser:changeme@postgres:5432/appdb")
S3_ENDPOINT = os.getenv("S3_ENDPOINT",  "https://nbg1.your-objectstorage.com")
S3_BUCKET   = os.getenv("S3_BUCKET",    "typebot-assets")
S3_KEY      = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET   = os.getenv("S3_SECRET_KEY", "")
S3_REGION   = os.getenv("S3_REGION",    "nbg1")
N8N_URL     = os.getenv("N8N_URL",      "https://workflows.eppcom.de")
OLLAMA_URL  = os.getenv("OLLAMA_URL",   "http://10.0.0.3:11434")
ADMIN_KEY   = os.getenv("ADMIN_API_KEY","change-this-admin-key-immediately")
EMBED_MODEL = os.getenv("EMBED_MODEL",  "qwen3-embedding:0.6b")

# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="EPPCOM RAG Admin", version="1.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# DB-Pool
# ──────────────────────────────────────────────────────────────────────────────
_db_pool: asyncpg.Pool = None

async def get_db() -> asyncpg.Pool:
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)
    return _db_pool

@app.on_event("startup")
async def startup():
    await get_db()

@app.on_event("shutdown")
async def shutdown():
    if _db_pool:
        await _db_pool.close()

# ──────────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────────
def require_admin(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return True

# ──────────────────────────────────────────────────────────────────────────────
# S3 Client
# ──────────────────────────────────────────────────────────────────────────────
def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_KEY,
        aws_secret_access_key=S3_SECRET,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────────────
class TenantCreate(BaseModel):
    name: str
    slug: str
    email: str
    plan: str = "starter"

class ApiKeyCreate(BaseModel):
    name: str
    key_plaintext: str
    permissions: List[str] = ["read", "write"]

class ChatRequest(BaseModel):
    tenant_id: str
    api_key: str
    query: str
    session_id: Optional[str] = None

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Stats
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats(_: bool = Depends(require_admin)):
    db = await get_db()
    row = await db.fetchrow("""
        SELECT
            (SELECT COUNT(*) FROM tenants WHERE is_active=true)::int AS tenants,
            (SELECT COUNT(*) FROM sources)::int AS sources,
            (SELECT COUNT(*) FROM chunks)::int AS chunks,
            (SELECT COUNT(*) FROM embeddings)::int AS embeddings,
            (SELECT COUNT(*) FROM chat_sessions)::int AS chat_sessions,
            (SELECT COUNT(*) FROM api_keys WHERE is_active=true)::int AS active_keys
    """)
    return dict(row)

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Tenants
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/tenants")
async def list_tenants(_: bool = Depends(require_admin)):
    db = await get_db()
    rows = await db.fetch("""
        SELECT t.id, t.name, t.slug, t.email, t.plan, t.is_active, t.created_at,
               COUNT(DISTINCT s.id)::int AS source_count,
               COUNT(DISTINCT c.id)::int AS chunk_count,
               COUNT(DISTINCT k.id)::int AS key_count
        FROM tenants t
        LEFT JOIN sources s ON s.tenant_id = t.id
        LEFT JOIN chunks c ON c.tenant_id = t.id
        LEFT JOIN api_keys k ON k.tenant_id = t.id AND k.is_active = true
        GROUP BY t.id, t.name, t.slug, t.email, t.plan, t.is_active, t.created_at
        ORDER BY t.created_at DESC
    """)
    return [dict(r) for r in rows]

@app.post("/api/tenants", status_code=201)
async def create_tenant(body: TenantCreate, _: bool = Depends(require_admin)):
    db = await get_db()
    # Slug validieren
    import re
    if not re.match(r'^[a-z0-9_-]+$', body.slug):
        raise HTTPException(400, "Slug: nur Kleinbuchstaben, Zahlen, - und _ erlaubt")
    try:
        tenant_id = str(uuid.uuid4())
        await db.execute("""
            INSERT INTO tenants (id, name, slug, email, plan, is_active)
            VALUES ($1, $2, $3, $4, $5, true)
        """, tenant_id, body.name, body.slug, body.email, body.plan)
        return {"id": tenant_id, "message": "Tenant erstellt"}
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, f"Slug '{body.slug}' existiert bereits")

@app.delete("/api/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, _: bool = Depends(require_admin)):
    db = await get_db()
    result = await db.execute(
        "UPDATE tenants SET is_active=false WHERE id=$1::uuid", tenant_id
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Tenant nicht gefunden")
    return {"message": "Tenant deaktiviert"}

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: API Keys
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/tenants/{tenant_id}/apikeys")
async def list_apikeys(tenant_id: str, _: bool = Depends(require_admin)):
    db = await get_db()
    rows = await db.fetch("""
        SELECT id, name, permissions, is_active, expires_at, created_at
        FROM api_keys WHERE tenant_id=$1::uuid ORDER BY created_at DESC
    """, tenant_id)
    return [dict(r) for r in rows]

@app.post("/api/tenants/{tenant_id}/apikeys", status_code=201)
async def create_apikey(tenant_id: str, body: ApiKeyCreate, _: bool = Depends(require_admin)):
    db = await get_db()
    key_hash = hashlib.sha256(body.key_plaintext.encode()).hexdigest()
    key_id = str(uuid.uuid4())
    await db.execute("""
        INSERT INTO api_keys (id, tenant_id, key_hash, name, permissions, is_active)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, true)
    """, key_id, tenant_id, key_hash, body.name, json.dumps(body.permissions))
    return {"id": key_id, "message": "API-Key erstellt", "warning": "Plaintext-Key sicher speichern — wird nicht wieder angezeigt!"}

@app.delete("/api/apikeys/{key_id}")
async def delete_apikey(key_id: str, _: bool = Depends(require_admin)):
    db = await get_db()
    await db.execute("UPDATE api_keys SET is_active=false WHERE id=$1::uuid", key_id)
    return {"message": "API-Key deaktiviert"}

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Dokumente & Chunks
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/tenants/{tenant_id}/sources")
async def list_sources(tenant_id: str, _: bool = Depends(require_admin)):
    db = await get_db()
    rows = await db.fetch("""
        SET app.current_tenant = '""" + tenant_id + """';
        SELECT s.id, s.name, s.source_type, s.status, s.file_size_bytes,
               s.created_at, COUNT(c.id)::int AS chunk_count
        FROM sources s
        LEFT JOIN documents d ON d.source_id = s.id
        LEFT JOIN chunks c ON c.document_id = d.id
        WHERE s.tenant_id=$1::uuid
        GROUP BY s.id, s.name, s.source_type, s.status, s.file_size_bytes, s.created_at
        ORDER BY s.created_at DESC LIMIT 100
    """, tenant_id)
    return [dict(r) for r in rows]

@app.get("/api/tenants/{tenant_id}/chunks")
async def list_chunks(tenant_id: str, limit: int = 50, offset: int = 0, _: bool = Depends(require_admin)):
    db = await get_db()
    rows = await db.fetch("""
        SELECT c.id, c.chunk_index, LEFT(c.content, 200) AS content_preview,
               c.token_count, c.created_at,
               s.name AS source_name, s.source_type,
               (EXISTS(SELECT 1 FROM embeddings e WHERE e.chunk_id=c.id)) AS has_embedding
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE c.tenant_id=$1::uuid
        ORDER BY c.created_at DESC, c.chunk_index
        LIMIT $2 OFFSET $3
    """, tenant_id, limit, offset)
    total = await db.fetchval("SELECT COUNT(*) FROM chunks WHERE tenant_id=$1::uuid", tenant_id)
    return {"total": total, "chunks": [dict(r) for r in rows]}

@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str, _: bool = Depends(require_admin)):
    db = await get_db()
    # Kaskadierend löschen
    await db.execute("""
        DELETE FROM embeddings WHERE chunk_id IN (
            SELECT c.id FROM chunks c
            JOIN documents d ON d.id=c.document_id
            WHERE d.source_id=$1::uuid
        );
        DELETE FROM chunks WHERE document_id IN (
            SELECT id FROM documents WHERE source_id=$1::uuid
        );
        DELETE FROM documents WHERE source_id=$1::uuid;
        DELETE FROM sources WHERE id=$1::uuid;
    """, source_id)
    return {"message": "Quelle und alle zugehörigen Daten gelöscht"}

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Dokument hochladen + in n8n senden
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/tenants/{tenant_id}/upload")
async def upload_document(
    tenant_id: str,
    file: UploadFile = File(None),
    text_content: str = Form(None),
    name: str = Form("Unbenanntes Dokument"),
    api_key: str = Form(...),
    _: bool = Depends(require_admin),
):
    db = await get_db()

    # Tenant prüfen
    tenant = await db.fetchrow("SELECT id, slug FROM tenants WHERE id=$1::uuid AND is_active=true", tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden")

    content = ""
    s3_key_result = None

    # Text aus Datei extrahieren
    if file:
        file_bytes = await file.read()
        filename = file.filename or "upload.txt"

        # S3 Upload
        if S3_KEY:
            try:
                s3 = get_s3()
                s3_key_result = f"tenants/{tenant['slug']}/documents/{uuid.uuid4()}-{filename}"
                s3.upload_fileobj(
                    io.BytesIO(file_bytes),
                    S3_BUCKET,
                    s3_key_result,
                    ExtraArgs={"ContentType": file.content_type or "application/octet-stream"}
                )
            except Exception as e:
                s3_key_result = None  # S3 optional, weiter ohne

        # Text extrahieren
        if filename.endswith(".pdf"):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                content = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                content = file_bytes.decode("utf-8", errors="ignore")
        else:
            content = file_bytes.decode("utf-8", errors="ignore")

        name = name if name != "Unbenanntes Dokument" else filename
    elif text_content:
        content = text_content.strip()
    else:
        raise HTTPException(400, "file oder text_content erforderlich")

    if len(content) < 10:
        raise HTTPException(400, "Kein verwertbarer Text gefunden")

    # n8n Ingestion Webhook aufrufen
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(
                f"{N8N_URL}/webhook/ingest",
                json={
                    "content": content,
                    "name": name,
                    "source_type": "file" if file else "manual",
                    "s3_key": s3_key_result,
                    "s3_bucket": S3_BUCKET if s3_key_result else None,
                },
                headers={
                    "X-Tenant-ID": tenant_id,
                    "X-API-Key": api_key,
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(502, f"n8n Fehler: {resp.status_code} — {resp.text[:200]}")
        except httpx.TimeoutException:
            raise HTTPException(504, "n8n Timeout — Dokument möglicherweise trotzdem verarbeitet")

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Chat Tester (Proxy zu n8n)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat_proxy(body: ChatRequest, _: bool = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                f"{N8N_URL}/webhook/rag-chat",
                json={"query": body.query, "session_id": body.session_id},
                headers={
                    "X-Tenant-ID": body.tenant_id,
                    "X-API-Key": body.api_key,
                    "Content-Type": "application/json",
                },
            )
            return resp.json()
        except Exception as e:
            raise HTTPException(502, f"Chat-Fehler: {str(e)}")

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Ollama Direkt-Embedding (für Tests)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    db = await get_db()
    db_ok = False
    ollama_ok = False
    try:
        await db.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "ollama": ollama_ok,
        "n8n": N8N_URL,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Statische Dateien (Frontend)
# ──────────────────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html") as f:
        return f.read()
