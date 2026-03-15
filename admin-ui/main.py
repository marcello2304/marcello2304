"""
EPPCOM RAG Admin UI — FastAPI Backend
Deployment: Docker auf Server 1 via Coolify
URL: https://admin.eppcom.de

Features:
  - Rollenbasiertes Login (Super-Admin vs. Tenant-User)
  - Tenant-Verwaltung (CRUD, nur Super-Admin)
  - RAG Dokument-Ingestion (Parse → Chunk → Embed → Store) — direkt, ohne n8n
  - Media-Upload (Bilder, Videos, Audio) → Hetzner S3
  - Chat-Tester (Proxy zu n8n)
"""
import os
import re
import uuid
import hashlib
import json
import io
import math
import secrets
import time
from datetime import datetime
from typing import Optional, List

import asyncpg
import httpx
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Depends, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguration
# ──────────────────────────────────────────────────────────────────────────────
DB_DSN      = os.getenv("DATABASE_URL",  "postgresql://postgres:changeme@postgres-rag:5432/app_db")
S3_ENDPOINT = os.getenv("S3_ENDPOINT",   "https://fsn1.your-objectstorage.com")
S3_BUCKET   = os.getenv("S3_BUCKET",     "rag-platform-prod")
S3_KEY      = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET   = os.getenv("S3_SECRET_KEY", "")
S3_REGION   = os.getenv("S3_REGION",     "eu-central-003")
N8N_URL     = os.getenv("N8N_URL",       "https://workflows.eppcom.de")
OLLAMA_URL  = os.getenv("OLLAMA_URL",    "http://10.0.0.3:11434")
ADMIN_KEY   = os.getenv("ADMIN_API_KEY", "change-this-admin-key-immediately")
EMBED_MODEL = os.getenv("EMBED_MODEL",   "nomic-embed-text")
EMBED_DIM   = int(os.getenv("EMBED_DIM", "768"))

# Super-Admin E-Mail — hat Zugriff auf ALLE Tenants
SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "eppler@eppcom.de")

# Chunking defaults
CHUNK_SIZE     = int(os.getenv("CHUNK_SIZE", "800"))      # Zeichen pro Chunk
CHUNK_OVERLAP  = int(os.getenv("CHUNK_OVERLAP", "200"))   # Überlappung

# Media upload limits
MAX_MEDIA_SIZE = int(os.getenv("MAX_MEDIA_SIZE", str(100 * 1024 * 1024)))  # 100 MB

ALLOWED_MEDIA_TYPES = {
    # Images
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    # Video
    "video/mp4", "video/webm", "video/quicktime",
    # Audio
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/webm", "audio/mp4",
    # Misc
    "application/pdf",
}

MEDIA_EXT_MAP = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/ogg": ".ogg",
    "audio/webm": ".weba", "audio/mp4": ".m4a",
    "application/pdf": ".pdf",
}

# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="EPPCOM RAG Admin", version="2.0.0", docs_url="/api/docs")

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
# Auth — Rollenbasiert (Session-Tokens)
# ──────────────────────────────────────────────────────────────────────────────
# In-Memory Session Store: token → { email, role, tenant_ids, tenant_slugs, created }
_sessions: dict = {}
SESSION_TTL = 86400  # 24h

class SessionInfo:
    def __init__(self, email: str, role: str, tenant_ids: list, tenant_slugs: list):
        self.email = email
        self.role = role  # "superadmin" | "tenant"
        self.tenant_ids = tenant_ids  # Liste von Tenant-UUIDs
        self.tenant_slugs = tenant_slugs
        self.created = time.time()

    def is_superadmin(self):
        return self.role == "superadmin"

    def can_access_tenant(self, tenant_id: str) -> bool:
        return self.is_superadmin() or tenant_id in self.tenant_ids

    def to_dict(self):
        return {
            "email": self.email,
            "role": self.role,
            "tenant_ids": self.tenant_ids,
            "tenant_slugs": self.tenant_slugs,
        }


def _get_session(token: str) -> SessionInfo:
    if not token or token not in _sessions:
        raise HTTPException(401, "Nicht angemeldet oder Session abgelaufen")
    session = _sessions[token]
    if time.time() - session.created > SESSION_TTL:
        del _sessions[token]
        raise HTTPException(401, "Session abgelaufen — bitte neu anmelden")
    return session


def require_auth(x_session_token: str = Header(None), x_admin_key: str = Header(None)) -> SessionInfo:
    """Akzeptiert Session-Token ODER den alten Admin-Key (Abwärtskompatibilität)."""
    if x_session_token:
        return _get_session(x_session_token)
    if x_admin_key and x_admin_key == ADMIN_KEY:
        return SessionInfo(SUPER_ADMIN_EMAIL, "superadmin", [], [])
    raise HTTPException(401, "Nicht autorisiert")


def require_superadmin(session: SessionInfo = Depends(require_auth)) -> SessionInfo:
    if not session.is_superadmin():
        raise HTTPException(403, "Nur Super-Admin erlaubt")
    return session


def require_tenant_access(tenant_id: str, session: SessionInfo = Depends(require_auth)) -> SessionInfo:
    if not session.can_access_tenant(tenant_id):
        raise HTTPException(403, "Kein Zugriff auf diesen Tenant")
    return session

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
# Helpers: Text-Extraktion
# ──────────────────────────────────────────────────────────────────────────────
def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extrahiert Text aus verschiedenen Dateiformaten."""
    lower = filename.lower()

    if lower.endswith(".pdf"):
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[Seite {i+1}]\n{text}")
            return "\n\n".join(pages)
        except Exception as e:
            raise ValueError(f"PDF-Parsing fehlgeschlagen: {e}")

    if lower.endswith((".txt", ".md", ".csv", ".json", ".html", ".htm")):
        return file_bytes.decode("utf-8", errors="ignore")

    if lower.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise ValueError(f"DOCX-Parsing fehlgeschlagen: {e}")

    # Fallback: versuche als Text
    return file_bytes.decode("utf-8", errors="ignore")


def detect_file_type(filename: str) -> str:
    """Gibt den file_type für die DB zurück."""
    lower = filename.lower()
    for ext, ftype in [
        (".pdf", "pdf"), (".docx", "docx"), (".txt", "txt"),
        (".html", "html"), (".htm", "html"), (".md", "md"),
        (".csv", "csv"), (".json", "json"),
    ]:
        if lower.endswith(ext):
            return ftype
    return "other"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers: Chunking
# ──────────────────────────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[dict]:
    """Teilt Text in überlappende Chunks auf. Versucht an Absatz-/Satzgrenzen zu trennen."""
    if not text or not text.strip():
        return []

    # Normalisiere Whitespace
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # Versuche an Absatzgrenze zu trennen
            para_break = text.rfind('\n\n', start + chunk_size // 2, end)
            if para_break > start:
                end = para_break + 2
            else:
                # Versuche an Satzgrenze zu trennen
                for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                    sent_break = text.rfind(sep, start + chunk_size // 2, end)
                    if sent_break > start:
                        end = sent_break + len(sep)
                        break

        chunk_content = text[start:end].strip()
        if chunk_content:
            # Grobe Token-Schätzung (deutsch: ~1 Token pro 4 Zeichen)
            token_count = max(1, len(chunk_content) // 4)
            chunks.append({
                "chunk_index": idx,
                "content": chunk_content,
                "char_count": len(chunk_content),
                "token_count": token_count,
                "content_hash": hashlib.sha256(chunk_content.encode()).hexdigest()[:16],
            })
            idx += 1

        start = max(start + 1, end - overlap)

    return chunks


# ──────────────────────────────────────────────────────────────────────────────
# Helpers: Embedding via Ollama
# ──────────────────────────────────────────────────────────────────────────────
async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generiert einen Embedding-Vektor via Ollama API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
        )
        if resp.status_code != 200:
            raise ValueError(f"Ollama Embed Fehler: {resp.status_code} — {resp.text[:200]}")
        data = resp.json()
        embeddings = data.get("embeddings")
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        raise ValueError("Ollama hat kein Embedding zurückgegeben")


async def generate_embeddings_batch(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    """Generiert Embeddings in Batches."""
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": batch},
            )
            if resp.status_code != 200:
                raise ValueError(f"Ollama Batch-Embed Fehler: {resp.status_code}")
            data = resp.json()
            embeddings = data.get("embeddings", [])
            results.extend(embeddings)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────────────
class TenantCreate(BaseModel):
    name: str
    slug: str
    email: str
    plan: str = "starter"

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    plan: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str  # = Admin-Key oder Tenant-Passwort

class ChatRequest(BaseModel):
    tenant_id: str
    api_key: str
    query: str
    session_id: Optional[str] = None

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Login / Logout / Session
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/login")
async def login(body: LoginRequest):
    """
    Login mit E-Mail + Passwort (= Admin-Key).
    - eppler@eppcom.de + ADMIN_KEY → Super-Admin (alle Tenants)
    - tenant-email + ADMIN_KEY → Tenant-User (nur eigene Tenants)
    """
    email = body.email.strip().lower()

    # Passwort muss der Admin-Key sein (einfaches Shared-Secret-Auth)
    if body.password != ADMIN_KEY:
        raise HTTPException(401, "Falsches Passwort")

    db = await get_db()
    role = "tenant"
    tenant_ids = []
    tenant_slugs = []

    if email == SUPER_ADMIN_EMAIL.lower():
        role = "superadmin"
        # Alle aktiven Tenants laden
        rows = await db.fetch("SELECT id::text, slug FROM public.tenants WHERE status='active' ORDER BY name")
        tenant_ids = [r["id"] for r in rows]
        tenant_slugs = [r["slug"] for r in rows]
    else:
        # Tenant(s) für diese E-Mail finden
        rows = await db.fetch(
            "SELECT id::text, slug FROM public.tenants WHERE LOWER(email)=$1 AND status='active'",
            email,
        )
        if not rows:
            raise HTTPException(401, "Kein Tenant mit dieser E-Mail gefunden")
        tenant_ids = [r["id"] for r in rows]
        tenant_slugs = [r["slug"] for r in rows]

    # Session erstellen
    token = secrets.token_urlsafe(48)
    _sessions[token] = SessionInfo(email, role, tenant_ids, tenant_slugs)

    return {
        "token": token,
        "email": email,
        "role": role,
        "tenant_ids": tenant_ids,
        "tenant_slugs": tenant_slugs,
    }


@app.post("/api/logout")
async def logout(x_session_token: str = Header(None)):
    if x_session_token and x_session_token in _sessions:
        del _sessions[x_session_token]
    return {"message": "Abgemeldet"}


@app.get("/api/me")
async def get_me(session: SessionInfo = Depends(require_auth)):
    """Gibt aktuelle Session-Info zurück, inkl. aktueller Tenant-Liste."""
    db = await get_db()
    if session.is_superadmin():
        rows = await db.fetch("SELECT id::text, slug FROM public.tenants WHERE status='active' ORDER BY name")
        session.tenant_ids = [r["id"] for r in rows]
        session.tenant_slugs = [r["slug"] for r in rows]
    return session.to_dict()


# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Health & Stats
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    db = await get_db()
    db_ok = False
    ollama_ok = False
    ollama_models = []
    try:
        await db.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                ollama_ok = True
                ollama_models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "ollama": ollama_ok,
        "ollama_models": ollama_models,
        "embed_model": EMBED_MODEL,
        "n8n": N8N_URL,
        "s3_endpoint": S3_ENDPOINT,
        "s3_bucket": S3_BUCKET,
    }

@app.get("/api/stats")
async def get_stats(session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    if session.is_superadmin():
        tenants = await db.fetch("SELECT slug, schema_name FROM public.tenants WHERE status='active'")
        tenant_count = len(tenants)
    else:
        tenants = await db.fetch(
            "SELECT slug, schema_name FROM public.tenants WHERE id::text = ANY($1) AND status='active'",
            session.tenant_ids,
        )
        tenant_count = len(tenants)
    total_sources = 0
    total_chunks = 0
    total_embeddings = 0
    for t in tenants:
        try:
            row2 = await db.fetchrow(f"""
                SELECT
                    (SELECT COUNT(*) FROM {t['schema_name']}.sources)::int AS s,
                    (SELECT COUNT(*) FROM {t['schema_name']}.chunks)::int AS c,
                    (SELECT COUNT(*) FROM {t['schema_name']}.embeddings)::int AS e
            """)
            if row2:
                total_sources += row2['s']
                total_chunks += row2['c']
                total_embeddings += row2['e']
        except Exception:
            pass
    return {
        "tenants": tenant_count,
        "sources": total_sources,
        "chunks": total_chunks,
        "embeddings": total_embeddings,
    }

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Tenants
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/tenants")
async def list_tenants(session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    if session.is_superadmin():
        rows = await db.fetch("""
            SELECT id, name, slug, email, plan, status, schema_name, s3_prefix,
                   max_docs, max_chunks, created_at
            FROM public.tenants
            ORDER BY created_at DESC
        """)
    else:
        rows = await db.fetch("""
            SELECT id, name, slug, email, plan, status, schema_name, s3_prefix,
                   max_docs, max_chunks, created_at
            FROM public.tenants
            WHERE id::text = ANY($1) AND status='active'
            ORDER BY name
        """, session.tenant_ids)
    result = []
    for r in rows:
        row_dict = dict(r)
        if r['status'] == 'active':
            try:
                stats = await db.fetchrow(f"""
                    SELECT
                        (SELECT COUNT(*) FROM {r['schema_name']}.sources)::int AS source_count,
                        (SELECT COUNT(*) FROM {r['schema_name']}.chunks)::int AS chunk_count,
                        (SELECT COUNT(*) FROM {r['schema_name']}.embeddings)::int AS embed_count
                """)
                row_dict.update(dict(stats))
            except Exception:
                row_dict["source_count"] = 0
                row_dict["chunk_count"] = 0
                row_dict["embed_count"] = 0
        else:
            row_dict["source_count"] = 0
            row_dict["chunk_count"] = 0
            row_dict["embed_count"] = 0
        result.append(row_dict)
    return result

@app.post("/api/tenants", status_code=201)
async def create_tenant(body: TenantCreate, session: SessionInfo = Depends(require_superadmin)):
    if not re.match(r'^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$', body.slug):
        raise HTTPException(400, "Slug: nur Kleinbuchstaben, Zahlen, - und _ erlaubt (3-64 Zeichen)")
    db = await get_db()
    try:
        tenant_id = await db.fetchval(
            "SELECT public.create_tenant($1, $2, $3, $4)",
            body.slug, body.name, body.email, body.plan
        )
        return {"id": str(tenant_id), "slug": body.slug, "message": f"Tenant '{body.name}' mit Schema tenant_{body.slug} erstellt"}
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, f"Slug '{body.slug}' existiert bereits")
    except Exception as e:
        raise HTTPException(500, f"Tenant-Erstellung fehlgeschlagen: {e}")

@app.put("/api/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, body: TenantUpdate, session: SessionInfo = Depends(require_auth)):
    if not session.can_access_tenant(tenant_id):
        raise HTTPException(403, "Kein Zugriff auf diesen Tenant")
    db = await get_db()
    updates = []
    values = [tenant_id]
    i = 2
    if body.name is not None:
        updates.append(f"name=${i}")
        values.append(body.name)
        i += 1
    if body.email is not None:
        updates.append(f"email=${i}")
        values.append(body.email)
        i += 1
    if body.plan is not None and session.is_superadmin():
        updates.append(f"plan=${i}")
        values.append(body.plan)
        i += 1
    if not updates:
        raise HTTPException(400, "Keine Änderungen angegeben")
    result = await db.execute(
        f"UPDATE public.tenants SET {', '.join(updates)} WHERE id=$1::uuid AND status='active'",
        *values
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Tenant nicht gefunden")
    return {"message": "Tenant aktualisiert"}

@app.delete("/api/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, session: SessionInfo = Depends(require_superadmin)):
    db = await get_db()
    result = await db.execute(
        "UPDATE public.tenants SET status='deleted' WHERE id=$1::uuid AND status='active'",
        tenant_id
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Tenant nicht gefunden oder bereits gelöscht")
    return {"message": "Tenant deaktiviert"}

# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Sources (per Tenant-Schema)
# ──────────────────────────────────────────────────────────────────────────────
async def _get_tenant_schema(db, tenant_id: str, session: SessionInfo = None) -> dict:
    """Holt Tenant-Info, validiert und prüft Zugriff."""
    tenant = await db.fetchrow(
        "SELECT id, slug, schema_name, s3_prefix, name, email FROM public.tenants WHERE id=$1::uuid AND status='active'",
        tenant_id
    )
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden oder inaktiv")
    if session and not session.can_access_tenant(tenant_id):
        raise HTTPException(403, "Kein Zugriff auf diesen Tenant")
    return dict(tenant)

@app.get("/api/tenants/{tenant_id}/sources")
async def list_sources(tenant_id: str, session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)
    schema = tenant["schema_name"]
    rows = await db.fetch(f"""
        SELECT s.id, s.name, s.source_type, s.status, s.file_name, s.file_type,
               s.file_size, s.s3_key, s.error_message, s.created_at, s.tags,
               (SELECT COUNT(*) FROM {schema}.chunks c
                JOIN {schema}.documents d ON d.id = c.document_id
                WHERE d.source_id = s.id)::int AS chunk_count,
               (SELECT COUNT(*) FROM {schema}.embeddings e
                JOIN {schema}.chunks c ON c.id = e.chunk_id
                JOIN {schema}.documents d ON d.id = c.document_id
                WHERE d.source_id = s.id)::int AS embed_count
        FROM {schema}.sources s
        ORDER BY s.created_at DESC
        LIMIT 200
    """)
    return [dict(r) for r in rows]

@app.get("/api/tenants/{tenant_id}/chunks")
async def list_chunks(
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
    session: SessionInfo = Depends(require_auth),
):
    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)
    schema = tenant["schema_name"]
    rows = await db.fetch(f"""
        SELECT c.id, c.chunk_index, LEFT(c.content, 300) AS content_preview,
               c.token_count, c.char_count, c.created_at,
               s.name AS source_name, s.source_type,
               (EXISTS(SELECT 1 FROM {schema}.embeddings e WHERE e.chunk_id=c.id)) AS has_embedding
        FROM {schema}.chunks c
        JOIN {schema}.documents d ON d.id = c.document_id
        JOIN {schema}.sources s ON s.id = d.source_id
        ORDER BY c.created_at DESC, c.chunk_index
        LIMIT $1 OFFSET $2
    """, limit, offset)
    total = await db.fetchval(f"SELECT COUNT(*) FROM {schema}.chunks")
    return {"total": total, "chunks": [dict(r) for r in rows]}

@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str, tenant_id: str = Query(...), session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)
    schema = tenant["schema_name"]
    # Kaskadierend löschen (Embeddings → Chunks → Documents → Source)
    await db.execute(f"""
        DELETE FROM {schema}.embeddings WHERE chunk_id IN (
            SELECT c.id FROM {schema}.chunks c
            JOIN {schema}.documents d ON d.id = c.document_id
            WHERE d.source_id = $1::uuid
        )
    """, source_id)
    await db.execute(f"""
        DELETE FROM {schema}.chunks WHERE document_id IN (
            SELECT id FROM {schema}.documents WHERE source_id = $1::uuid
        )
    """, source_id)
    await db.execute(f"DELETE FROM {schema}.documents WHERE source_id = $1::uuid", source_id)
    await db.execute(f"DELETE FROM {schema}.sources WHERE id = $1::uuid", source_id)
    return {"message": "Quelle und alle zugehörigen Daten gelöscht"}


# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: RAG Dokument-Ingestion (Direkt-Pipeline)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/tenants/{tenant_id}/ingest")
async def ingest_document(
    tenant_id: str,
    file: UploadFile = File(None),
    text_content: str = Form(None),
    name: str = Form("Unbenanntes Dokument"),
    doc_type: str = Form("general"),
    tags: str = Form(""),
    session: SessionInfo = Depends(require_auth),
):
    """
    Komplette RAG-Ingestion-Pipeline:
    1. Datei/Text entgegennehmen
    2. Text extrahieren
    3. In Chunks aufteilen
    4. Embeddings via Ollama generieren
    5. Alles in Tenant-Schema speichern
    6. Optional: Datei in S3 ablegen
    """
    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)
    schema = tenant["schema_name"]

    content = ""
    file_bytes = None
    filename = "manual-input.txt"
    file_size = 0
    s3_key = None

    # ── Schritt 1: Inhalt lesen ──
    if file:
        file_bytes = await file.read()
        filename = file.filename or "upload.txt"
        file_size = len(file_bytes)
        name = name if name != "Unbenanntes Dokument" else filename
    elif text_content:
        content = text_content.strip()
        file_size = len(content.encode("utf-8"))
    else:
        raise HTTPException(400, "Datei oder text_content erforderlich")

    # ── Schritt 2: Text extrahieren ──
    if file_bytes:
        try:
            content = extract_text(file_bytes, filename)
        except ValueError as e:
            raise HTTPException(422, str(e))

    if len(content.strip()) < 10:
        raise HTTPException(400, "Zu wenig verwertbarer Text (< 10 Zeichen)")

    file_type = detect_file_type(filename)
    checksum = hashlib.sha256(content.encode()).hexdigest()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # ── Schritt 3: S3 Upload (optional, Original-Datei sichern) ──
    if file_bytes and S3_KEY:
        try:
            s3 = get_s3()
            s3_key = f"{tenant['s3_prefix']}docs/{uuid.uuid4()}-{filename}"
            s3.upload_fileobj(
                io.BytesIO(file_bytes),
                S3_BUCKET,
                s3_key,
                ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
            )
        except Exception:
            s3_key = None  # S3 optional

    # ── Schritt 4: Source in DB anlegen ──
    source_id = str(uuid.uuid4())
    await db.execute(f"""
        INSERT INTO {schema}.sources (id, name, source_type, file_name, file_type, file_size, checksum, s3_key, status, tags)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, 'processing', $9::text[])
    """, source_id, name, "file" if file else "manual", filename, file_type, file_size, checksum, s3_key, tag_list)

    # ── Schritt 5: Document anlegen ──
    doc_id = str(uuid.uuid4())
    word_count = len(content.split())
    char_count = len(content)
    await db.execute(f"""
        INSERT INTO {schema}.documents (id, source_id, title, doc_type, word_count, char_count)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6)
    """, doc_id, source_id, name, doc_type, word_count, char_count)

    # ── Schritt 6: Chunking ──
    chunks = chunk_text(content)
    if not chunks:
        await db.execute(f"UPDATE {schema}.sources SET status='error', error_message='Keine Chunks erzeugt' WHERE id=$1::uuid", source_id)
        raise HTTPException(422, "Konnte keinen verwertbaren Text extrahieren")

    # Chunks in DB speichern
    chunk_ids = []
    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        chunk_ids.append(chunk_id)
        await db.execute(f"""
            INSERT INTO {schema}.chunks (id, document_id, source_id, chunk_index, content, content_hash, token_count, char_count)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8)
        """, chunk_id, doc_id, source_id, chunk["chunk_index"], chunk["content"],
            chunk["content_hash"], chunk["token_count"], chunk["char_count"])

    # ── Schritt 7: Embeddings generieren ──
    embed_count = 0
    embed_error = None
    try:
        chunk_texts = [c["content"] for c in chunks]
        vectors = await generate_embeddings_batch(chunk_texts)

        for i, vector in enumerate(vectors):
            if i < len(chunk_ids) and vector:
                vec_str = "[" + ",".join(str(v) for v in vector) + "]"
                await db.execute(f"""
                    INSERT INTO {schema}.embeddings (chunk_id, model, vector)
                    VALUES ($1::uuid, $2, $3::vector)
                """, chunk_ids[i], EMBED_MODEL, vec_str)
                embed_count += 1

        await db.execute(f"UPDATE {schema}.sources SET status='indexed' WHERE id=$1::uuid", source_id)
    except Exception as e:
        embed_error = str(e)
        # Chunks sind gespeichert, nur Embeddings fehlen
        await db.execute(
            f"UPDATE {schema}.sources SET status='error', error_message=$2 WHERE id=$1::uuid",
            source_id, f"Embedding-Fehler: {embed_error}"
        )

    return {
        "source_id": source_id,
        "document_id": doc_id,
        "name": name,
        "file_type": file_type,
        "content_length": char_count,
        "word_count": word_count,
        "chunks_created": len(chunks),
        "embeddings_created": embed_count,
        "s3_key": s3_key,
        "status": "indexed" if embed_count == len(chunks) else "partial",
        "embed_error": embed_error,
    }


# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Media-Upload (Bilder, Videos, Audio → S3)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/tenants/{tenant_id}/media")
async def upload_media(
    tenant_id: str,
    file: UploadFile = File(...),
    folder: str = Form("media"),
    description: str = Form(""),
    session: SessionInfo = Depends(require_auth),
):
    """Lädt eine Mediendatei in den Hetzner S3 Speicher."""
    if not S3_KEY:
        raise HTTPException(503, "S3 nicht konfiguriert")

    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)

    file_bytes = await file.read()
    if len(file_bytes) > MAX_MEDIA_SIZE:
        raise HTTPException(413, f"Datei zu groß (max {MAX_MEDIA_SIZE // 1024 // 1024} MB)")

    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload"

    # Sanitize folder name
    folder = re.sub(r'[^a-zA-Z0-9_/-]', '', folder).strip("/")
    if not folder:
        folder = "media"

    # S3 Key generieren
    file_id = str(uuid.uuid4())[:8]
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    s3_key = f"{tenant['s3_prefix']}{folder}/{file_id}-{safe_name}"

    try:
        s3 = get_s3()
        s3.upload_fileobj(
            io.BytesIO(file_bytes),
            S3_BUCKET,
            s3_key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {
                    "original-name": filename[:256],
                    "description": description[:512],
                    "tenant": tenant["slug"],
                },
            },
        )
    except ClientError as e:
        raise HTTPException(502, f"S3-Upload fehlgeschlagen: {e}")

    # Public URL generieren (path-style)
    public_url = f"{S3_ENDPOINT}/{S3_BUCKET}/{s3_key}"

    return {
        "s3_key": s3_key,
        "bucket": S3_BUCKET,
        "url": public_url,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
        "size_human": _human_size(len(file_bytes)),
        "filename": filename,
    }


@app.get("/api/tenants/{tenant_id}/media")
async def list_media(
    tenant_id: str,
    folder: str = Query("media"),
    session: SessionInfo = Depends(require_auth),
):
    """Listet Mediendateien eines Tenants aus S3."""
    if not S3_KEY:
        raise HTTPException(503, "S3 nicht konfiguriert")

    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)

    folder = re.sub(r'[^a-zA-Z0-9_/-]', '', folder).strip("/")
    if not folder:
        folder = "media"
    prefix = f"{tenant['s3_prefix']}{folder}/"

    try:
        s3 = get_s3()
        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix, MaxKeys=500)
        items = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            name = key.split("/")[-1]
            if not name:
                continue
            # Content-Type erraten
            ext = os.path.splitext(name)[1].lower()
            ct = "application/octet-stream"
            for mime, e in MEDIA_EXT_MAP.items():
                if e == ext:
                    ct = mime
                    break
            items.append({
                "key": key,
                "name": name,
                "size_bytes": obj["Size"],
                "size_human": _human_size(obj["Size"]),
                "last_modified": obj["LastModified"].isoformat(),
                "url": f"{S3_ENDPOINT}/{S3_BUCKET}/{key}",
                "content_type": ct,
                "is_image": ct.startswith("image/"),
                "is_video": ct.startswith("video/"),
                "is_audio": ct.startswith("audio/"),
            })
        return {"prefix": prefix, "count": len(items), "items": items}
    except ClientError as e:
        raise HTTPException(502, f"S3-Fehler: {e}")


@app.delete("/api/tenants/{tenant_id}/media")
async def delete_media(
    tenant_id: str,
    s3_key: str = Query(...),
    session: SessionInfo = Depends(require_auth),
):
    """Löscht eine Mediendatei aus S3."""
    if not S3_KEY:
        raise HTTPException(503, "S3 nicht konfiguriert")

    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)

    # Sicherheitscheck: Key muss zum Tenant gehören
    if not s3_key.startswith(tenant["s3_prefix"]):
        raise HTTPException(403, "Zugriff verweigert: Datei gehört nicht zu diesem Tenant")

    try:
        s3 = get_s3()
        s3.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        return {"message": f"Datei gelöscht: {s3_key}"}
    except ClientError as e:
        raise HTTPException(502, f"S3-Löschung fehlgeschlagen: {e}")


def _human_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    i = min(i, len(units) - 1)
    s = round(size_bytes / (1024 ** i), 1)
    return f"{s} {units[i]}"


# ──────────────────────────────────────────────────────────────────────────────
# ROUTES: Chat Tester (Proxy zu n8n)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat_proxy(body: ChatRequest, session: SessionInfo = Depends(require_auth)):
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
# ROUTES: Re-Embed (einzelne Source neu embedden)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/tenants/{tenant_id}/sources/{source_id}/reembed")
async def reembed_source(tenant_id: str, source_id: str, session: SessionInfo = Depends(require_auth)):
    """Löscht bestehende Embeddings und generiert neue für alle Chunks einer Source."""
    db = await get_db()
    tenant = await _get_tenant_schema(db, tenant_id, session)
    schema = tenant["schema_name"]

    # Alte Embeddings löschen
    await db.execute(f"""
        DELETE FROM {schema}.embeddings WHERE chunk_id IN (
            SELECT c.id FROM {schema}.chunks c
            JOIN {schema}.documents d ON d.id = c.document_id
            WHERE d.source_id = $1::uuid
        )
    """, source_id)

    # Chunks laden
    rows = await db.fetch(f"""
        SELECT c.id, c.content FROM {schema}.chunks c
        JOIN {schema}.documents d ON d.id = c.document_id
        WHERE d.source_id = $1::uuid
        ORDER BY c.chunk_index
    """, source_id)

    if not rows:
        raise HTTPException(404, "Keine Chunks gefunden")

    chunk_ids = [str(r["id"]) for r in rows]
    chunk_texts = [r["content"] for r in rows]

    vectors = await generate_embeddings_batch(chunk_texts)
    embed_count = 0
    for i, vector in enumerate(vectors):
        if i < len(chunk_ids) and vector:
            vec_str = "[" + ",".join(str(v) for v in vector) + "]"
            await db.execute(f"""
                INSERT INTO {schema}.embeddings (chunk_id, model, vector)
                VALUES ($1::uuid, $2, $3::vector)
            """, chunk_ids[i], EMBED_MODEL, vec_str)
            embed_count += 1

    await db.execute(f"UPDATE {schema}.sources SET status='indexed', error_message=NULL WHERE id=$1::uuid", source_id)

    return {"source_id": source_id, "chunks": len(rows), "embeddings_created": embed_count}


# ──────────────────────────────────────────────────────────────────────────────
# Statische Dateien (Frontend)
# ──────────────────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html") as f:
        return f.read()
