"""
EPPCOM RAG Admin UI — FastAPI Backend
Deployment: Docker auf Server 1 via Coolify
URL: https://appdb.eppcom.de

Features:
  - Echte User-Auth mit bcrypt-Passwörtern
  - Rollenbasiert: superadmin / admin / user
  - User-scoped RAG-Dokumente und Medien
  - Admin: Kunden-, User- und Content-Verwaltung
  - Media-Upload/-Browse/-Delete mit Hetzner S3
  - RAG Dokument-Ingestion (Parse → Chunk → Embed → Store)
  - Chat-Tester (Proxy zu n8n)
"""
import asyncio
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
import bcrypt
import httpx
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Depends, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguration
# ──────────────────────────────────────────────────────────────────────────────
_db_url = os.getenv("DATABASE_URL", "")
if not _db_url:
    raise RuntimeError("DATABASE_URL ist nicht gesetzt — App kann nicht starten ohne DB-Verbindung")
DB_DSN      = _db_url
S3_ENDPOINT = os.getenv("S3_ENDPOINT",   "https://fsn1.your-objectstorage.com")
S3_BUCKET   = os.getenv("S3_BUCKET",     "rag-platform-prod")
S3_KEY      = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET   = os.getenv("S3_SECRET_KEY", "")
S3_REGION   = os.getenv("S3_REGION",     "eu-central-003")
N8N_URL     = os.getenv("N8N_URL",       "https://workflows.eppcom.de")
OLLAMA_URL  = os.getenv("OLLAMA_URL",    "http://10.0.0.3:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL",   "qwen3-embedding:0.6b")
EMBED_DIM   = int(os.getenv("EMBED_DIM", "1024"))

SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "eppler@eppcom.de")
SUPER_ADMIN_DEFAULT_PW = os.getenv("SUPER_ADMIN_DEFAULT_PW", "")

CHUNK_SIZE     = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP  = int(os.getenv("CHUNK_OVERLAP", "200"))
MAX_MEDIA_SIZE = int(os.getenv("MAX_MEDIA_SIZE", str(100 * 1024 * 1024)))

ALLOWED_DOC_TYPES = {".pdf", ".txt", ".md", ".csv", ".json", ".html", ".htm", ".docx"}

ALLOWED_MEDIA_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "video/mp4", "video/webm", "video/quicktime",
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/webm", "audio/mp4",
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
app = FastAPI(title="EPPCOM RAG Admin", version="3.0.0", docs_url="/api/docs")

_cors_origins = os.getenv("CORS_ORIGINS", "").strip()
_allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins else []

# Dynamische CORS für Widget-Endpoints: alle Domains aus domain_whitelist erlauben
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class WidgetCORSMiddleware(BaseHTTPMiddleware):
    """Erlaubt CORS für /api/public/* Endpoints (widget-chat + chat für Typebot)."""
    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin", "")
        is_public = request.url.path.startswith("/api/public/")

        if is_public and request.method == "OPTIONS":
            return Response(status_code=200, headers={
                "Access-Control-Allow-Origin": origin or "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Tenant-ID, X-API-Key",
                "Access-Control-Max-Age": "86400",
            })

        response = await call_next(request)

        if is_public and origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Tenant-ID, X-API-Key"

        return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WidgetCORSMiddleware muss NACH CORSMiddleware registriert werden,
# damit es in der Middleware-Kette VOR CORSMiddleware ausgeführt wird
app.add_middleware(WidgetCORSMiddleware)

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
    db = await get_db()
    # Super-Admin auto-erstellen falls nicht vorhanden UND Passwort gesetzt
    if SUPER_ADMIN_DEFAULT_PW:
        existing = await db.fetchval("SELECT id FROM public.users WHERE email=$1", SUPER_ADMIN_EMAIL.lower())
        if not existing:
            pw_hash = bcrypt.hashpw(SUPER_ADMIN_DEFAULT_PW.encode(), bcrypt.gensalt()).decode()
            await db.execute(
                """INSERT INTO public.users (email, password_hash, display_name, role)
                   VALUES ($1, $2, $3, 'superadmin')
                   ON CONFLICT (email) DO NOTHING""",
                SUPER_ADMIN_EMAIL.lower(), pw_hash, "Admin Eppler"
            )

@app.on_event("shutdown")
async def shutdown():
    if _db_pool:
        await _db_pool.close()

# ──────────────────────────────────────────────────────────────────────────────
# Auth — bcrypt-basiert mit Session-Tokens
# ──────────────────────────────────────────────────────────────────────────────
_sessions: dict = {}
SESSION_TTL = 86400  # 24h

class SessionInfo:
    def __init__(self, user_id: str, email: str, display_name: str, role: str,
                 tenant_id: str = None, tenant_slug: str = None):
        self.user_id = user_id
        self.email = email
        self.display_name = display_name
        self.role = role
        self.tenant_id = tenant_id
        self.tenant_slug = tenant_slug
        self.created = time.time()

    def is_superadmin(self):
        return self.role == "superadmin"

    def is_admin(self):
        return self.role in ("superadmin", "admin")

    def can_access_tenant(self, tenant_id: str) -> bool:
        if self.is_superadmin():
            return True
        return self.tenant_id == tenant_id

    def can_access_user_content(self, user_id: str) -> bool:
        if self.is_superadmin():
            return True
        return self.user_id == user_id

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "tenant_slug": self.tenant_slug,
        }


def _get_session(token: str) -> SessionInfo:
    if not token or token not in _sessions:
        raise HTTPException(401, "Nicht angemeldet oder Session abgelaufen")
    session = _sessions[token]
    if time.time() - session.created > SESSION_TTL:
        del _sessions[token]
        raise HTTPException(401, "Session abgelaufen")
    return session


def require_auth(x_session_token: str = Header(None)) -> SessionInfo:
    if x_session_token:
        return _get_session(x_session_token)
    raise HTTPException(401, "Nicht autorisiert")


def require_admin(session: SessionInfo = Depends(require_auth)) -> SessionInfo:
    if not session.is_admin():
        raise HTTPException(403, "Admin-Rechte erforderlich")
    return session


def require_superadmin(session: SessionInfo = Depends(require_auth)) -> SessionInfo:
    if not session.is_superadmin():
        raise HTTPException(403, "Nur Super-Admin erlaubt")
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


def presign_url(s3_key: str, bucket: str = None, expires: int = 3600) -> str:
    """Erzeugt eine temporäre presigned URL (Standard: 1h gültig)."""
    if not S3_KEY or not s3_key:
        return ""
    try:
        return get_s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket or S3_BUCKET, "Key": s3_key},
            ExpiresIn=expires,
        )
    except Exception:
        return f"{S3_ENDPOINT}/{bucket or S3_BUCKET}/{s3_key}"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def _human_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = min(int(math.floor(math.log(size_bytes, 1024))), len(units) - 1)
    s = round(size_bytes / (1024 ** i), 1)
    return f"{s} {units[i]}"

def extract_text(file_bytes: bytes, filename: str) -> str:
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
    return file_bytes.decode("utf-8", errors="ignore")

def detect_file_type(filename: str) -> str:
    lower = filename.lower()
    for ext, ftype in [
        (".pdf", "pdf"), (".docx", "docx"), (".txt", "txt"),
        (".html", "html"), (".htm", "html"), (".md", "md"),
        (".csv", "csv"), (".json", "json"),
    ]:
        if lower.endswith(ext):
            return ftype
    return "other"

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[dict]:
    if not text or not text.strip():
        return []
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            para_break = text.rfind('\n\n', start + chunk_size // 2, end)
            if para_break > start:
                end = para_break + 2
            else:
                for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                    sent_break = text.rfind(sep, start + chunk_size // 2, end)
                    if sent_break > start:
                        end = sent_break + len(sep)
                        break
        chunk_content = text[start:end].strip()
        if chunk_content:
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

async def generate_embedding(text: str) -> Optional[List[float]]:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": text})
        if resp.status_code != 200:
            raise ValueError(f"Ollama Embed Fehler: {resp.status_code}")
        data = resp.json()
        embeddings = data.get("embeddings")
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        raise ValueError("Ollama hat kein Embedding zurückgegeben")

async def generate_embeddings_batch(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": batch, "keep_alive": "30m"})
            if resp.status_code != 200:
                raise ValueError(f"Ollama Batch-Embed Fehler: {resp.status_code}")
            data = resp.json()
            results.extend(data.get("embeddings", []))
    return results

async def _get_tenant_schema(db, tenant_id: str, session: SessionInfo = None) -> dict:
    tenant = await db.fetchrow(
        "SELECT id, slug, schema_name, s3_prefix, name, email FROM public.tenants WHERE id=$1::uuid AND status='active'",
        tenant_id
    )
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden oder inaktiv")
    if session and not session.can_access_tenant(str(tenant["id"])):
        raise HTTPException(403, "Kein Zugriff auf diesen Tenant")
    return dict(tenant)


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class TenantCreate(BaseModel):
    name: str
    slug: str
    email: str
    plan: str = "starter"

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    plan: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    password: str
    display_name: str
    role: str = "user"
    tenant_id: Optional[str] = None

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = None

class PasswordChange(BaseModel):
    new_password: str

class ChatRequest(BaseModel):
    tenant_id: str
    api_key: str
    query: str
    session_id: Optional[str] = None

class RagChatRequest(BaseModel):
    query: str
    tenant_id: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Login / Logout / Session
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/login")
async def login(body: LoginRequest):
    email = body.email.strip().lower()
    db = await get_db()

    user = await db.fetchrow(
        "SELECT id, email, password_hash, display_name, role, tenant_id, is_active FROM public.users WHERE email=$1",
        email
    )
    if not user:
        raise HTTPException(401, "E-Mail oder Passwort falsch")
    if not user["is_active"]:
        raise HTTPException(403, "Account deaktiviert")
    if not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "E-Mail oder Passwort falsch")

    tenant_slug = None
    tenant_id_str = str(user["tenant_id"]) if user["tenant_id"] else None
    if tenant_id_str:
        t = await db.fetchval("SELECT slug FROM public.tenants WHERE id=$1::uuid AND status='active'", tenant_id_str)
        tenant_slug = t

    token = secrets.token_urlsafe(48)
    _sessions[token] = SessionInfo(
        user_id=str(user["id"]),
        email=user["email"],
        display_name=user["display_name"],
        role=user["role"],
        tenant_id=tenant_id_str,
        tenant_slug=tenant_slug,
    )

    return {
        "token": token,
        "user_id": str(user["id"]),
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "tenant_id": tenant_id_str,
        "tenant_slug": tenant_slug,
    }


@app.post("/api/logout")
async def logout(x_session_token: str = Header(None)):
    if x_session_token and x_session_token in _sessions:
        del _sessions[x_session_token]
    return {"message": "Abgemeldet"}


@app.get("/api/me")
async def get_me(session: SessionInfo = Depends(require_auth)):
    # Immer aus DB lesen, damit Änderungen (z.B. Tenant-Zuweisung) sofort wirken
    db = await get_db()
    user = await db.fetchrow(
        "SELECT id, email, display_name, role, tenant_id, is_active FROM public.users WHERE id=$1::uuid",
        session.user_id
    )
    if not user or not user["is_active"]:
        raise HTTPException(401, "Account nicht gefunden oder deaktiviert")

    tenant_id_str = str(user["tenant_id"]) if user["tenant_id"] else None
    tenant_slug = None
    if tenant_id_str:
        tenant_slug = await db.fetchval(
            "SELECT slug FROM public.tenants WHERE id=$1::uuid AND status='active'", tenant_id_str
        )

    # Session aktualisieren damit Backend-Checks (Upload etc.) sofort greifen
    session.email = user["email"]
    session.display_name = user["display_name"]
    session.role = user["role"]
    session.tenant_id = tenant_id_str
    session.tenant_slug = tenant_slug

    return {
        "user_id": session.user_id,
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "tenant_id": tenant_id_str,
        "tenant_slug": tenant_slug,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Health & Stats
# ══════════════════════════════════════════════════════════════════════════════
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
        "db": db_ok, "ollama": ollama_ok, "ollama_models": ollama_models,
        "embed_model": EMBED_MODEL, "s3_endpoint": S3_ENDPOINT, "s3_bucket": S3_BUCKET,
    }


@app.get("/api/stats")
async def get_stats(session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    if session.is_superadmin():
        tenant_count = await db.fetchval("SELECT COUNT(*) FROM public.tenants WHERE status='active'")
        user_count = await db.fetchval("SELECT COUNT(*) FROM public.users WHERE is_active=true")
        source_count = await db.fetchval("SELECT COUNT(*) FROM public.sources") or 0
        media_count = await db.fetchval("SELECT COUNT(*) FROM public.media_files") or 0
    else:
        tenant_count = 1 if session.tenant_id else 0
        user_count = 1
        where = "WHERE user_id=$1::uuid" if session.user_id else "WHERE 1=0"
        source_count = await db.fetchval(f"SELECT COUNT(*) FROM public.sources {where}", session.user_id) or 0
        media_count = await db.fetchval(f"SELECT COUNT(*) FROM public.media_files {where}", session.user_id) or 0
    return {"tenants": tenant_count, "users": user_count, "sources": source_count, "media": media_count}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Tenants (Super-Admin)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/tenants")
async def list_tenants(session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    if session.is_superadmin():
        rows = await db.fetch("""
            SELECT t.id, t.name, t.slug, t.email, t.plan, t.status, t.schema_name,
                   t.s3_prefix, t.max_docs, t.max_chunks, t.created_at,
                   (SELECT COUNT(*) FROM public.users u WHERE u.tenant_id=t.id AND u.is_active=true)::int AS user_count,
                   (SELECT COUNT(*) FROM public.sources s WHERE s.tenant_id=t.id)::int AS source_count,
                   (SELECT COUNT(*) FROM public.media_files m WHERE m.tenant_id=t.id)::int AS media_count
            FROM public.tenants t
            ORDER BY t.created_at DESC
        """)
    elif session.tenant_id:
        rows = await db.fetch("""
            SELECT t.id, t.name, t.slug, t.email, t.plan, t.status, t.schema_name,
                   t.s3_prefix, t.max_docs, t.max_chunks, t.created_at,
                   (SELECT COUNT(*) FROM public.users u WHERE u.tenant_id=t.id AND u.is_active=true)::int AS user_count,
                   (SELECT COUNT(*) FROM public.sources s WHERE s.tenant_id=t.id)::int AS source_count,
                   (SELECT COUNT(*) FROM public.media_files m WHERE m.tenant_id=t.id)::int AS media_count
            FROM public.tenants t
            WHERE t.id=$1::uuid AND t.status='active'
        """, session.tenant_id)
    else:
        return []
    return [dict(r) for r in rows]


@app.post("/api/tenants", status_code=201)
async def create_tenant(body: TenantCreate, session: SessionInfo = Depends(require_superadmin)):
    if not re.match(r'^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$', body.slug):
        raise HTTPException(400, "Slug: nur Kleinbuchstaben, Zahlen, - und _ (3-64 Zeichen)")
    db = await get_db()
    try:
        tenant_id = await db.fetchval(
            "SELECT public.create_tenant($1, $2, $3, $4)",
            body.slug, body.name, body.email, body.plan
        )
        return {"id": str(tenant_id), "slug": body.slug, "message": f"Tenant '{body.name}' erstellt"}
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, f"Slug '{body.slug}' existiert bereits")
    except Exception as e:
        raise HTTPException(500, f"Tenant-Erstellung fehlgeschlagen: {e}")


@app.put("/api/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, body: TenantUpdate, session: SessionInfo = Depends(require_auth)):
    if not session.can_access_tenant(tenant_id):
        raise HTTPException(403, "Kein Zugriff")
    db = await get_db()
    updates = []
    values = [tenant_id]
    i = 2
    for field, val in [("name", body.name), ("email", body.email)]:
        if val is not None:
            updates.append(f"{field}=${i}")
            values.append(val)
            i += 1
    if body.plan is not None and session.is_superadmin():
        updates.append(f"plan=${i}")
        values.append(body.plan)
        i += 1
    if not updates:
        raise HTTPException(400, "Keine Änderungen")
    result = await db.execute(
        f"UPDATE public.tenants SET {', '.join(updates)} WHERE id=$1::uuid AND status='active'", *values
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Tenant nicht gefunden")
    return {"message": "Tenant aktualisiert"}


@app.delete("/api/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, session: SessionInfo = Depends(require_superadmin)):
    db = await get_db()
    result = await db.execute(
        "UPDATE public.tenants SET status='deleted' WHERE id=$1::uuid AND status='active'", tenant_id
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Tenant nicht gefunden")
    return {"message": "Tenant deaktiviert"}


@app.put("/api/tenants/{tenant_id}/restore")
async def restore_tenant(tenant_id: str, session: SessionInfo = Depends(require_superadmin)):
    db = await get_db()
    result = await db.execute(
        "UPDATE public.tenants SET status='active' WHERE id=$1::uuid AND status='deleted'", tenant_id
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Tenant nicht gefunden oder bereits aktiv")
    return {"message": "Tenant wiederhergestellt"}


@app.delete("/api/tenants/{tenant_id}/permanent")
async def delete_tenant_permanent(tenant_id: str, session: SessionInfo = Depends(require_superadmin)):
    db = await get_db()
    tenant = await db.fetchrow(
        "SELECT slug, schema_name, status FROM public.tenants WHERE id=$1::uuid", tenant_id
    )
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden")
    if tenant["status"] == "active":
        raise HTTPException(400, "Aktive Tenants müssen zuerst deaktiviert werden")

    schema = tenant["schema_name"] or f"tenant_{tenant['slug']}"

    # Zugehörige Daten löschen
    await db.execute("DELETE FROM public.media_files WHERE tenant_id=$1::uuid", tenant_id)
    await db.execute("DELETE FROM public.sources WHERE tenant_id=$1::uuid", tenant_id)
    await db.execute("DELETE FROM public.conversations WHERE tenant_id=$1::uuid", tenant_id)
    await db.execute("DELETE FROM public.domain_whitelist WHERE tenant_id=$1::uuid", tenant_id)
    await db.execute("DELETE FROM public.users WHERE tenant_id=$1::uuid", tenant_id)
    await db.execute("DELETE FROM public.tenants WHERE id=$1::uuid", tenant_id)

    # Tenant-Schema löschen (falls vorhanden)
    try:
        await db.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    except Exception:
        pass  # Schema existiert möglicherweise nicht

    return {"message": f"Tenant '{tenant['slug']}' und alle zugehörigen Daten endgültig gelöscht"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: User-Verwaltung (Admin)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/users")
async def list_users(
    tenant_id: str = Query(None),
    session: SessionInfo = Depends(require_auth),
):
    db = await get_db()
    if session.is_superadmin():
        if tenant_id:
            rows = await db.fetch("""
                SELECT u.id, u.email, u.display_name, u.role, u.tenant_id, u.is_active,
                       u.created_at, t.name AS tenant_name, t.slug AS tenant_slug,
                       (SELECT COUNT(*) FROM public.sources s WHERE s.user_id=u.id)::int AS source_count,
                       (SELECT COUNT(*) FROM public.media_files m WHERE m.user_id=u.id)::int AS media_count
                FROM public.users u
                LEFT JOIN public.tenants t ON t.id=u.tenant_id
                WHERE u.tenant_id=$1::uuid
                ORDER BY u.created_at DESC
            """, tenant_id)
        else:
            rows = await db.fetch("""
                SELECT u.id, u.email, u.display_name, u.role, u.tenant_id, u.is_active,
                       u.created_at, t.name AS tenant_name, t.slug AS tenant_slug,
                       (SELECT COUNT(*) FROM public.sources s WHERE s.user_id=u.id)::int AS source_count,
                       (SELECT COUNT(*) FROM public.media_files m WHERE m.user_id=u.id)::int AS media_count
                FROM public.users u
                LEFT JOIN public.tenants t ON t.id=u.tenant_id
                ORDER BY u.created_at DESC
            """)
    elif session.is_admin() and session.tenant_id:
        rows = await db.fetch("""
            SELECT u.id, u.email, u.display_name, u.role, u.tenant_id, u.is_active,
                   u.created_at, t.name AS tenant_name, t.slug AS tenant_slug,
                   (SELECT COUNT(*) FROM public.sources s WHERE s.user_id=u.id)::int AS source_count,
                   (SELECT COUNT(*) FROM public.media_files m WHERE m.user_id=u.id)::int AS media_count
            FROM public.users u
            LEFT JOIN public.tenants t ON t.id=u.tenant_id
            WHERE u.tenant_id=$1::uuid
            ORDER BY u.created_at DESC
        """, session.tenant_id)
    else:
        rows = await db.fetch("""
            SELECT u.id, u.email, u.display_name, u.role, u.tenant_id, u.is_active,
                   u.created_at, t.name AS tenant_name, t.slug AS tenant_slug,
                   (SELECT COUNT(*) FROM public.sources s WHERE s.user_id=u.id)::int AS source_count,
                   (SELECT COUNT(*) FROM public.media_files m WHERE m.user_id=u.id)::int AS media_count
            FROM public.users u
            LEFT JOIN public.tenants t ON t.id=u.tenant_id
            WHERE u.id=$1::uuid
        """, session.user_id)
    return [dict(r) for r in rows]


@app.post("/api/users", status_code=201)
async def create_user(body: UserCreate, session: SessionInfo = Depends(require_admin)):
    email = body.email.strip().lower()
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        raise HTTPException(400, "Ungültige E-Mail-Adresse")
    if len(body.password) < 6:
        raise HTTPException(400, "Passwort muss mindestens 6 Zeichen haben")
    if body.role == "superadmin" and not session.is_superadmin():
        raise HTTPException(403, "Nur Super-Admin kann Super-Admins erstellen")

    db = await get_db()
    pw_hash = _hash_password(body.password)
    tid = body.tenant_id
    if not session.is_superadmin() and session.tenant_id:
        tid = session.tenant_id
    if not tid:
        raise HTTPException(400, "Bitte eine Firma (Tenant) zuweisen — User ohne Tenant können keine Dokumente hochladen oder chatten")

    try:
        user_id = await db.fetchval(
            """INSERT INTO public.users (email, password_hash, display_name, role, tenant_id)
               VALUES ($1, $2, $3, $4, $5::uuid)
               RETURNING id""",
            email, pw_hash, body.display_name, body.role, tid
        )
        return {"id": str(user_id), "email": email, "message": f"User '{body.display_name}' erstellt"}
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, f"E-Mail '{email}' existiert bereits")


@app.put("/api/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, session: SessionInfo = Depends(require_admin)):
    db = await get_db()
    # Prüfe ob Admin den User bearbeiten darf
    target = await db.fetchrow("SELECT tenant_id, role FROM public.users WHERE id=$1::uuid", user_id)
    if not target:
        raise HTTPException(404, "User nicht gefunden")
    if not session.is_superadmin():
        if str(target["tenant_id"]) != session.tenant_id:
            raise HTTPException(403, "Kein Zugriff auf diesen User")
        if target["role"] == "superadmin":
            raise HTTPException(403, "Super-Admin kann nicht von Admin bearbeitet werden")

    updates = []
    values = [user_id]
    i = 2
    if body.display_name is not None:
        updates.append(f"display_name=${i}")
        values.append(body.display_name)
        i += 1
    if body.role is not None and session.is_superadmin():
        updates.append(f"role=${i}")
        values.append(body.role)
        i += 1
    if body.tenant_id is not None and session.is_superadmin():
        updates.append(f"tenant_id=${i}::uuid")
        values.append(body.tenant_id)
        i += 1
    if body.is_active is not None:
        updates.append(f"is_active=${i}")
        values.append(body.is_active)
        i += 1
    if not updates:
        raise HTTPException(400, "Keine Änderungen")
    await db.execute(f"UPDATE public.users SET {', '.join(updates)} WHERE id=$1::uuid", *values)
    return {"message": "User aktualisiert"}


@app.put("/api/users/{user_id}/password")
async def change_password(user_id: str, request: Request, session: SessionInfo = Depends(require_auth)):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Ungültiger Request-Body")

    new_password = body.get("new_password") or ""
    if not new_password:
        raise HTTPException(400, "Neues Passwort erforderlich")

    if not session.is_superadmin() and session.user_id != user_id:
        if not session.is_admin():
            raise HTTPException(403, "Keine Berechtigung")
        # Admin darf nur User im eigenen Tenant ändern
        db = await get_db()
        target = await db.fetchrow("SELECT tenant_id FROM public.users WHERE id=$1::uuid", user_id)
        if not target or str(target["tenant_id"]) != session.tenant_id:
            raise HTTPException(403, "Kein Zugriff")
    else:
        db = await get_db()

    if len(new_password) < 6:
        raise HTTPException(400, "Passwort muss mindestens 6 Zeichen haben")

    pw_hash = _hash_password(new_password)
    result = await db.execute("UPDATE public.users SET password_hash=$2 WHERE id=$1::uuid", user_id, pw_hash)
    if result == "UPDATE 0":
        raise HTTPException(404, "User nicht gefunden")
    return {"message": "Passwort geändert"}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str, session: SessionInfo = Depends(require_admin)):
    if user_id == session.user_id:
        raise HTTPException(400, "Eigenen Account kann man nicht löschen")
    db = await get_db()
    target = await db.fetchrow("SELECT role, tenant_id FROM public.users WHERE id=$1::uuid", user_id)
    if not target:
        raise HTTPException(404, "User nicht gefunden")
    if target["role"] == "superadmin" and not session.is_superadmin():
        raise HTTPException(403, "Super-Admin kann nicht gelöscht werden")
    if not session.is_superadmin() and str(target["tenant_id"]) != session.tenant_id:
        raise HTTPException(403, "Kein Zugriff")

    await db.execute("UPDATE public.users SET is_active=false WHERE id=$1::uuid", user_id)
    return {"message": "User deaktiviert"}


@app.delete("/api/users/{user_id}/permanent")
async def delete_user_permanent(user_id: str, session: SessionInfo = Depends(require_admin)):
    if user_id == session.user_id:
        raise HTTPException(400, "Eigenen Account kann man nicht löschen")
    db = await get_db()
    target = await db.fetchrow("SELECT role, email, tenant_id FROM public.users WHERE id=$1::uuid", user_id)
    if not target:
        raise HTTPException(404, "User nicht gefunden")
    if target["role"] == "superadmin":
        raise HTTPException(403, "Super-Admin kann nicht endgültig gelöscht werden")
    if not session.is_superadmin():
        if str(target["tenant_id"]) != session.tenant_id:
            raise HTTPException(403, "Kein Zugriff auf diesen User")
        if target["role"] in ("admin", "superadmin"):
            raise HTTPException(403, "Admins können nicht von anderen Admins gelöscht werden")

    await db.execute("DELETE FROM public.users WHERE id=$1::uuid", user_id)
    return {"message": f"User {target['email']} endgültig gelöscht"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Sources / RAG-Dokumente (User-scoped)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/sources")
async def list_sources(
    tenant_id: str = Query(None),
    user_id: str = Query(None),
    session: SessionInfo = Depends(require_auth),
):
    db = await get_db()
    conditions = []
    params = []
    idx = 1

    if session.is_superadmin():
        if tenant_id:
            conditions.append(f"s.tenant_id=${idx}::uuid")
            params.append(tenant_id)
            idx += 1
        if user_id:
            conditions.append(f"s.user_id=${idx}::uuid")
            params.append(user_id)
            idx += 1
    elif session.tenant_id:
        conditions.append(f"s.tenant_id=${idx}::uuid")
        params.append(session.tenant_id)
        idx += 1
        if not session.is_admin():
            conditions.append(f"s.user_id=${idx}::uuid")
            params.append(session.user_id)
            idx += 1
        elif user_id:
            conditions.append(f"s.user_id=${idx}::uuid")
            params.append(user_id)
            idx += 1
    else:
        # User sieht eigene + freigegebene Dokumente
        conditions.append(f"""(s.user_id=${idx}::uuid OR s.id IN (
            SELECT content_id FROM public.content_shares
            WHERE shared_with=${idx}::uuid AND content_type='source'
        ))""")
        params.append(session.user_id)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.fetch(f"""
        SELECT s.id, s.name, s.source_type, s.status, s.s3_key, s.created_at, s.updated_at,
               s.tenant_id, s.user_id, s.metadata,
               t.slug AS tenant_slug, t.name AS tenant_name,
               u.display_name AS user_name, u.email AS user_email
        FROM public.sources s
        LEFT JOIN public.tenants t ON t.id=s.tenant_id
        LEFT JOIN public.users u ON u.id=s.user_id
        {where}
        ORDER BY s.created_at DESC
        LIMIT 200
    """, *params)
    return [dict(r) for r in rows]


@app.post("/api/sources/ingest")
async def ingest_document(
    tenant_id: str = Form(...),
    file: UploadFile = File(None),
    text_content: str = Form(None),
    name: str = Form("Unbenanntes Dokument"),
    tags: str = Form(""),
    session: SessionInfo = Depends(require_auth),
):
    db = await get_db()
    # Tenant-Zugriff prüfen — IMMER aus DB lesen, Session kann veraltet sein
    effective_tenant = tenant_id.strip() if tenant_id else ""
    if not session.is_superadmin():
        # Tenant direkt aus der DB lesen, nicht aus der Session
        user_row = await db.fetchrow(
            "SELECT tenant_id FROM public.users WHERE id=$1::uuid", session.user_id
        )
        db_tenant = str(user_row["tenant_id"]) if user_row and user_row["tenant_id"] else None
        if db_tenant:
            effective_tenant = db_tenant
            # Session aktualisieren fuer nachfolgende Checks
            session.tenant_id = db_tenant
        else:
            raise HTTPException(403, "Kein Tenant zugewiesen — bitte Admin kontaktieren, damit Ihnen eine Firma zugewiesen wird")
    if not effective_tenant:
        raise HTTPException(400, "Bitte zuerst eine Firma (Tenant) oben rechts auswählen")
    if not session.is_superadmin() and effective_tenant != session.tenant_id:
        raise HTTPException(403, "Kein Zugriff auf diesen Tenant")

    tenant = await db.fetchrow(
        "SELECT id, slug, s3_prefix, name FROM public.tenants WHERE id=$1::uuid AND status='active'",
        effective_tenant
    )
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden")

    content = ""
    file_bytes = None
    filename = "manual-input.txt"
    file_size = 0
    s3_key = None

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

    # S3 Upload
    if file_bytes and S3_KEY:
        try:
            s3 = get_s3()
            s3_key = f"{tenant['s3_prefix']}docs/{uuid.uuid4()}-{filename}"
            s3.upload_fileobj(
                io.BytesIO(file_bytes), S3_BUCKET, s3_key,
                ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
            )
        except Exception:
            s3_key = None

    # Source in DB (mit user_id)
    source_id = str(uuid.uuid4())
    metadata = json.dumps({"file_name": filename, "file_type": file_type, "file_size": file_size,
                           "checksum": checksum, "tags": tag_list, "word_count": len(content.split())})
    await db.execute("""
        INSERT INTO public.sources (id, tenant_id, user_id, name, source_type, s3_key, status, metadata)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'processing', $7::jsonb)
    """, source_id, effective_tenant, session.user_id, name,
        "file" if file else "manual", s3_key, metadata)

    # Document
    doc_id = str(uuid.uuid4())
    await db.execute("""
        INSERT INTO public.documents (id, source_id, tenant_id, content)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4)
    """, doc_id, source_id, effective_tenant, content)

    # Chunks
    chunks = chunk_text(content)
    if not chunks:
        await db.execute(
            "UPDATE public.sources SET status='error', metadata=metadata||$2::jsonb WHERE id=$1::uuid",
            source_id, json.dumps({"error": "Keine Chunks erzeugt"})
        )
        raise HTTPException(422, "Konnte keinen verwertbaren Text extrahieren")

    chunk_ids = []
    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        chunk_ids.append(chunk_id)
        await db.execute("""
            INSERT INTO public.chunks (id, document_id, tenant_id, content, chunk_index, token_count, metadata)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::jsonb)
        """, chunk_id, doc_id, effective_tenant, chunk["content"],
            chunk["chunk_index"], chunk["token_count"],
            json.dumps({"content_hash": chunk["content_hash"], "char_count": chunk["char_count"]}))

    # Embeddings
    embed_count = 0
    embed_error = None
    try:
        vectors = await generate_embeddings_batch([c["content"] for c in chunks])
        for i, vector in enumerate(vectors):
            if i < len(chunk_ids) and vector:
                vec_str = "[" + ",".join(str(v) for v in vector) + "]"
                await db.execute(f"""
                    INSERT INTO public.embeddings (chunk_id, tenant_id, embedding, model_name)
                    VALUES ($1::uuid, $2::uuid, $3::vector({EMBED_DIM}), $4)
                """, chunk_ids[i], effective_tenant, vec_str, EMBED_MODEL)
                embed_count += 1
        await db.execute("UPDATE public.sources SET status='completed' WHERE id=$1::uuid", source_id)
    except Exception as e:
        embed_error = str(e)
        await db.execute(
            "UPDATE public.sources SET status='error', metadata=metadata||$2::jsonb WHERE id=$1::uuid",
            source_id, json.dumps({"error": f"Embedding-Fehler: {embed_error}"})
        )

    return {
        "source_id": source_id, "name": name, "chunks_created": len(chunks),
        "embeddings_created": embed_count, "s3_key": s3_key,
        "status": "completed" if embed_count == len(chunks) else "partial",
        "embed_error": embed_error,
    }


@app.get("/api/sources/{source_id}/content")
async def get_source_content(source_id: str, session: SessionInfo = Depends(require_auth)):
    """Gibt den Text-Inhalt eines Dokuments zurück (zum Anzeigen/Bearbeiten)."""
    db = await get_db()
    source = await db.fetchrow(
        "SELECT s.tenant_id, s.user_id, s.name FROM public.sources s WHERE s.id=$1::uuid", source_id
    )
    if not source:
        raise HTTPException(404, "Quelle nicht gefunden")
    if not session.is_superadmin():
        if not session.can_access_tenant(str(source["tenant_id"])):
            raise HTTPException(403, "Kein Zugriff")
        if not session.is_admin() and str(source["user_id"]) != session.user_id:
            # Prüfe ob Dokument für diesen User freigegeben ist
            shared = await db.fetchval(
                "SELECT 1 FROM public.content_shares WHERE content_type='source' AND content_id=$1::uuid AND shared_with=$2::uuid",
                source_id, session.user_id
            )
            if not shared:
                raise HTTPException(403, "Nur eigene Quellen einsehen")

    doc = await db.fetchrow(
        "SELECT content FROM public.documents WHERE source_id=$1::uuid ORDER BY created_at DESC LIMIT 1",
        source_id,
    )
    return {"source_id": source_id, "name": source["name"], "content": doc["content"] if doc else ""}


@app.put("/api/sources/{source_id}/content")
async def update_source_content(source_id: str, request: Request, session: SessionInfo = Depends(require_auth)):
    """Aktualisiert den Text eines Dokuments: neu chunken + neu embedden."""
    db = await get_db()
    source = await db.fetchrow(
        "SELECT s.id, s.tenant_id, s.user_id, s.name FROM public.sources s WHERE s.id=$1::uuid", source_id
    )
    if not source:
        raise HTTPException(404, "Quelle nicht gefunden")
    if not session.is_superadmin():
        if not session.can_access_tenant(str(source["tenant_id"])):
            raise HTTPException(403, "Kein Zugriff")
        if not session.is_admin() and str(source["user_id"]) != session.user_id:
            raise HTTPException(403, "Nur eigene Quellen bearbeiten")

    body = await request.json()
    new_content = (body.get("content") or "").strip()
    new_name = (body.get("name") or "").strip()
    if len(new_content) < 10:
        raise HTTPException(400, "Zu wenig Text (mind. 10 Zeichen)")

    tenant_id = str(source["tenant_id"])

    # Altes Dokument holen
    doc = await db.fetchrow(
        "SELECT id FROM public.documents WHERE source_id=$1::uuid ORDER BY created_at DESC LIMIT 1",
        source_id,
    )
    if not doc:
        raise HTTPException(404, "Kein Dokument gefunden")
    doc_id = str(doc["id"])

    # Alte Embeddings + Chunks löschen
    await db.execute(
        "DELETE FROM public.embeddings WHERE chunk_id IN (SELECT id FROM public.chunks WHERE document_id=$1::uuid)",
        doc_id,
    )
    await db.execute("DELETE FROM public.chunks WHERE document_id=$1::uuid", doc_id)

    # Dokument-Inhalt aktualisieren
    await db.execute("UPDATE public.documents SET content=$2 WHERE id=$1::uuid", doc_id, new_content)

    # Name aktualisieren falls angegeben
    if new_name:
        await db.execute("UPDATE public.sources SET name=$2 WHERE id=$1::uuid", source_id, new_name)

    # Neue Chunks erzeugen
    chunks = chunk_text(new_content)
    chunk_ids = []
    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        chunk_ids.append(chunk_id)
        await db.execute("""
            INSERT INTO public.chunks (id, document_id, tenant_id, content, chunk_index, token_count, metadata)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::jsonb)
        """, chunk_id, doc_id, tenant_id, chunk["content"],
            chunk["chunk_index"], chunk["token_count"],
            json.dumps({"content_hash": chunk["content_hash"], "char_count": chunk["char_count"]}))

    # Neue Embeddings erzeugen
    embed_count = 0
    try:
        vectors = await generate_embeddings_batch([c["content"] for c in chunks])
        for i, vector in enumerate(vectors):
            if i < len(chunk_ids) and vector:
                vec_str = "[" + ",".join(str(v) for v in vector) + "]"
                await db.execute(f"""
                    INSERT INTO public.embeddings (chunk_id, tenant_id, embedding, model_name)
                    VALUES ($1::uuid, $2::uuid, $3::vector({EMBED_DIM}), $4)
                """, chunk_ids[i], tenant_id, vec_str, EMBED_MODEL)
                embed_count += 1
        await db.execute("UPDATE public.sources SET status='completed' WHERE id=$1::uuid", source_id)
    except Exception as e:
        await db.execute(
            "UPDATE public.sources SET status='error', metadata=metadata||$2::jsonb WHERE id=$1::uuid",
            source_id, json.dumps({"error": f"Embedding-Fehler: {str(e)}"})
        )

    # Metadaten aktualisieren
    metadata_update = json.dumps({"word_count": len(new_content.split()), "updated_by": session.user_id})
    await db.execute(
        "UPDATE public.sources SET metadata=metadata||$2::jsonb, updated_at=NOW() WHERE id=$1::uuid",
        source_id, metadata_update,
    )

    return {
        "source_id": source_id,
        "chunks_created": len(chunks),
        "embeddings_created": embed_count,
    }


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str, session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    source = await db.fetchrow("SELECT tenant_id, user_id FROM public.sources WHERE id=$1::uuid", source_id)
    if not source:
        raise HTTPException(404, "Quelle nicht gefunden")
    if not session.is_superadmin():
        if not session.can_access_tenant(str(source["tenant_id"])):
            raise HTTPException(403, "Kein Zugriff")
        if not session.is_admin() and str(source["user_id"]) != session.user_id:
            raise HTTPException(403, "Nur eigene Quellen löschen")

    # S3 Datei löschen
    s3_key = await db.fetchval("SELECT s3_key FROM public.sources WHERE id=$1::uuid", source_id)
    if s3_key and S3_KEY:
        try:
            get_s3().delete_object(Bucket=S3_BUCKET, Key=s3_key)
        except Exception:
            pass

    # Kaskadierend löschen
    await db.execute("DELETE FROM public.embeddings WHERE chunk_id IN (SELECT c.id FROM public.chunks c JOIN public.documents d ON d.id=c.document_id WHERE d.source_id=$1::uuid)", source_id)
    await db.execute("DELETE FROM public.chunks WHERE document_id IN (SELECT id FROM public.documents WHERE source_id=$1::uuid)", source_id)
    await db.execute("DELETE FROM public.documents WHERE source_id=$1::uuid", source_id)
    await db.execute("DELETE FROM public.sources WHERE id=$1::uuid", source_id)
    return {"message": "Quelle und alle zugehörigen Daten gelöscht"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Content Sharing (Admin verteilt Zugriff)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/shares")
async def list_shares(
    content_type: str = Query(None),
    tenant_id: str = Query(None),
    shared_with: str = Query(None),
    session: SessionInfo = Depends(require_auth),
):
    """Listet Freigaben auf. Admins sehen alle der Firma, User nur eigene."""
    db = await get_db()
    conditions = []
    params = []
    idx = 1

    if session.is_superadmin():
        if tenant_id:
            conditions.append(f"cs.tenant_id=${idx}::uuid")
            params.append(tenant_id)
            idx += 1
    elif session.is_admin() and session.tenant_id:
        conditions.append(f"cs.tenant_id=${idx}::uuid")
        params.append(session.tenant_id)
        idx += 1
    else:
        conditions.append(f"(cs.shared_with=${idx}::uuid OR cs.shared_by=${idx}::uuid)")
        params.append(session.user_id)
        idx += 1

    if content_type:
        conditions.append(f"cs.content_type=${idx}")
        params.append(content_type)
        idx += 1

    if shared_with:
        conditions.append(f"cs.shared_with=${idx}::uuid")
        params.append(shared_with)
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await db.fetch(f"""
        SELECT cs.id, cs.content_type, cs.content_id, cs.shared_by, cs.shared_with,
               cs.tenant_id, cs.created_at,
               sb.display_name AS shared_by_name, sb.email AS shared_by_email,
               sw.display_name AS shared_with_name, sw.email AS shared_with_email,
               COALESCE(src.name, mf.original_name, cs.content_id::text) AS content_name
        FROM public.content_shares cs
        LEFT JOIN public.users sb ON sb.id=cs.shared_by
        LEFT JOIN public.users sw ON sw.id=cs.shared_with
        LEFT JOIN public.sources src ON cs.content_type='source' AND src.id=cs.content_id
        LEFT JOIN public.media_files mf ON cs.content_type='media' AND mf.id=cs.content_id
        {where}
        ORDER BY cs.created_at DESC
        LIMIT 500
    """, *params)
    return [dict(r) for r in rows]


@app.post("/api/shares", status_code=201)
async def create_share(request: Request, session: SessionInfo = Depends(require_admin)):
    """Erstellt eine Freigabe. Nur Admins können Inhalte für User freigeben."""
    body = await request.json()
    content_type = body.get("content_type", "")
    content_id = body.get("content_id", "")
    shared_with = body.get("shared_with", "")

    if content_type not in ("source", "media", "conversation"):
        raise HTTPException(400, "content_type muss 'source', 'media' oder 'conversation' sein")
    if not content_id or not shared_with:
        raise HTTPException(400, "content_id und shared_with erforderlich")

    db = await get_db()

    # Prüfe ob der Ziel-User im selben Tenant ist
    target = await db.fetchrow("SELECT tenant_id FROM public.users WHERE id=$1::uuid AND is_active=true", shared_with)
    if not target:
        raise HTTPException(404, "Ziel-User nicht gefunden")
    if not session.is_superadmin():
        if str(target["tenant_id"]) != session.tenant_id:
            raise HTTPException(403, "User gehört nicht zur gleichen Firma")

    effective_tenant = session.tenant_id or str(target["tenant_id"])

    try:
        share_id = await db.fetchval("""
            INSERT INTO public.content_shares (content_type, content_id, shared_by, shared_with, tenant_id)
            VALUES ($1, $2::uuid, $3::uuid, $4::uuid, $5::uuid)
            RETURNING id
        """, content_type, content_id, session.user_id, shared_with, effective_tenant)
        return {"id": str(share_id), "message": "Freigabe erstellt"}
    except Exception:
        raise HTTPException(409, "Freigabe existiert bereits")


@app.delete("/api/shares/{share_id}")
async def delete_share(share_id: str, session: SessionInfo = Depends(require_admin)):
    """Entfernt eine Freigabe."""
    db = await get_db()
    share = await db.fetchrow("SELECT tenant_id FROM public.content_shares WHERE id=$1::uuid", share_id)
    if not share:
        raise HTTPException(404, "Freigabe nicht gefunden")
    if not session.is_superadmin() and str(share["tenant_id"]) != session.tenant_id:
        raise HTTPException(403, "Kein Zugriff")

    await db.execute("DELETE FROM public.content_shares WHERE id=$1::uuid", share_id)
    return {"message": "Freigabe entfernt"}


@app.post("/api/shares/bulk", status_code=201)
async def create_shares_bulk(request: Request, session: SessionInfo = Depends(require_admin)):
    """Erstellt mehrere Freigaben auf einmal (Admin wählt Dokument + mehrere User)."""
    body = await request.json()
    content_type = body.get("content_type", "")
    content_id = body.get("content_id", "")
    user_ids = body.get("user_ids", [])

    if content_type not in ("source", "media", "conversation"):
        raise HTTPException(400, "Ungültiger content_type")
    if not content_id or not user_ids:
        raise HTTPException(400, "content_id und user_ids erforderlich")

    db = await get_db()
    effective_tenant = session.tenant_id
    if not effective_tenant and session.is_superadmin():
        effective_tenant = body.get("tenant_id", "")
    if not effective_tenant:
        raise HTTPException(400, "Tenant erforderlich")

    created = 0
    for uid in user_ids:
        try:
            await db.execute("""
                INSERT INTO public.content_shares (content_type, content_id, shared_by, shared_with, tenant_id)
                VALUES ($1, $2::uuid, $3::uuid, $4::uuid, $5::uuid)
                ON CONFLICT DO NOTHING
            """, content_type, content_id, session.user_id, uid, effective_tenant)
            created += 1
        except Exception:
            pass

    return {"created": created, "message": f"{created} Freigaben erstellt"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Media-Dateien (S3, User-scoped, DB-tracked)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/media")
async def list_media(
    tenant_id: str = Query(None),
    user_id: str = Query(None),
    folder: str = Query(None),
    session: SessionInfo = Depends(require_auth),
):
    db = await get_db()
    conditions = []
    params = []
    idx = 1

    if session.is_superadmin():
        if tenant_id:
            conditions.append(f"m.tenant_id=${idx}::uuid")
            params.append(tenant_id)
            idx += 1
        if user_id:
            conditions.append(f"m.user_id=${idx}::uuid")
            params.append(user_id)
            idx += 1
    elif session.tenant_id:
        conditions.append(f"m.tenant_id=${idx}::uuid")
        params.append(session.tenant_id)
        idx += 1
        if not session.is_admin():
            # User sieht eigene + freigegebene Medien
            conditions.append(f"""(m.user_id=${idx}::uuid OR m.id IN (
                SELECT content_id FROM public.content_shares
                WHERE shared_with=${idx}::uuid AND content_type='media'
            ))""")
            params.append(session.user_id)
            idx += 1
        elif user_id:
            conditions.append(f"m.user_id=${idx}::uuid")
            params.append(user_id)
            idx += 1
    else:
        conditions.append(f"""(m.user_id=${idx}::uuid OR m.id IN (
            SELECT content_id FROM public.content_shares
            WHERE shared_with=${idx}::uuid AND content_type='media'
        ))""")
        params.append(session.user_id)
        idx += 1

    if folder:
        conditions.append(f"m.folder=${idx}")
        params.append(folder)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.fetch(f"""
        SELECT m.id, m.file_name, m.original_name, m.s3_key, m.s3_bucket,
               m.content_type, m.file_size, m.folder, m.description, m.is_public,
               m.created_at, m.tenant_id, m.user_id,
               t.slug AS tenant_slug, t.name AS tenant_name,
               u.display_name AS user_name
        FROM public.media_files m
        LEFT JOIN public.tenants t ON t.id=m.tenant_id
        LEFT JOIN public.users u ON u.id=m.user_id
        {where}
        ORDER BY m.created_at DESC
        LIMIT 500
    """, *params)

    items = []
    for r in rows:
        d = dict(r)
        d["url"] = presign_url(r['s3_key'], r['s3_bucket'])
        d["size_human"] = _human_size(r["file_size"])
        d["is_image"] = (r["content_type"] or "").startswith("image/")
        d["is_video"] = (r["content_type"] or "").startswith("video/")
        d["is_audio"] = (r["content_type"] or "").startswith("audio/")
        items.append(d)
    return items


@app.post("/api/media/upload")
async def upload_media(
    tenant_id: str = Form(...),
    file: UploadFile = File(...),
    folder: str = Form("media"),
    description: str = Form(""),
    session: SessionInfo = Depends(require_auth),
):
    if not S3_KEY:
        raise HTTPException(503, "S3 nicht konfiguriert")

    db = await get_db()
    effective_tenant = tenant_id
    if not session.is_superadmin():
        # Tenant direkt aus der DB lesen, nicht aus der Session
        user_row = await db.fetchrow(
            "SELECT tenant_id FROM public.users WHERE id=$1::uuid", session.user_id
        )
        db_tenant = str(user_row["tenant_id"]) if user_row and user_row["tenant_id"] else None
        if db_tenant:
            effective_tenant = db_tenant
            session.tenant_id = db_tenant
        else:
            raise HTTPException(403, "Kein Tenant zugewiesen — bitte Admin kontaktieren, damit Ihnen eine Firma zugewiesen wird")
    if not effective_tenant or not effective_tenant.strip():
        raise HTTPException(400, "Bitte zuerst eine Firma (Tenant) oben rechts auswählen")
    tenant = await db.fetchrow(
        "SELECT id, slug, s3_prefix FROM public.tenants WHERE id=$1::uuid AND status='active'",
        effective_tenant
    )
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_MEDIA_SIZE:
        raise HTTPException(413, f"Datei zu groß (max {MAX_MEDIA_SIZE // 1024 // 1024} MB)")

    content_type = file.content_type or "application/octet-stream"
    original_name = file.filename or "upload"
    folder = re.sub(r'[^a-zA-Z0-9_/-]', '', folder).strip("/") or "media"

    file_id = str(uuid.uuid4())[:8]
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', original_name)
    s3_key = f"{tenant['s3_prefix']}{folder}/{file_id}-{safe_name}"

    try:
        s3 = get_s3()
        s3.upload_fileobj(
            io.BytesIO(file_bytes), S3_BUCKET, s3_key,
            ExtraArgs={"ContentType": content_type},
        )
    except ClientError as e:
        raise HTTPException(502, f"S3-Upload fehlgeschlagen: {e}")

    # In DB tracken
    media_id = await db.fetchval("""
        INSERT INTO public.media_files (tenant_id, user_id, file_name, original_name, s3_key, s3_bucket,
                                         content_type, file_size, folder, description)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
    """, effective_tenant, session.user_id, safe_name, original_name,
        s3_key, S3_BUCKET, content_type, len(file_bytes), folder, description)

    return {
        "id": str(media_id), "s3_key": s3_key, "url": presign_url(s3_key),
        "content_type": content_type, "size_bytes": len(file_bytes),
        "size_human": _human_size(len(file_bytes)), "filename": original_name,
    }


@app.put("/api/media/{media_id}")
async def update_media(media_id: str, description: str = Form(None), folder: str = Form(None),
                       is_public: bool = Form(None), session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    media = await db.fetchrow("SELECT tenant_id, user_id FROM public.media_files WHERE id=$1::uuid", media_id)
    if not media:
        raise HTTPException(404, "Datei nicht gefunden")
    if not session.is_superadmin():
        if not session.can_access_tenant(str(media["tenant_id"])):
            raise HTTPException(403, "Kein Zugriff")
        if not session.is_admin() and str(media["user_id"]) != session.user_id:
            raise HTTPException(403, "Nur eigene Dateien bearbeiten")

    updates = []
    values = [media_id]
    i = 2
    if description is not None:
        updates.append(f"description=${i}")
        values.append(description)
        i += 1
    if folder is not None:
        updates.append(f"folder=${i}")
        values.append(folder)
        i += 1
    if is_public is not None:
        updates.append(f"is_public=${i}")
        values.append(is_public)
        i += 1
    if not updates:
        raise HTTPException(400, "Keine Änderungen")
    await db.execute(f"UPDATE public.media_files SET {', '.join(updates)} WHERE id=$1::uuid", *values)
    return {"message": "Datei aktualisiert"}


@app.delete("/api/media/{media_id}")
async def delete_media(media_id: str, session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    media = await db.fetchrow(
        "SELECT tenant_id, user_id, s3_key, s3_bucket FROM public.media_files WHERE id=$1::uuid", media_id
    )
    if not media:
        raise HTTPException(404, "Datei nicht gefunden")
    if not session.is_superadmin():
        if not session.can_access_tenant(str(media["tenant_id"])):
            raise HTTPException(403, "Kein Zugriff")
        if not session.is_admin() and str(media["user_id"]) != session.user_id:
            raise HTTPException(403, "Nur eigene Dateien löschen")

    # Aus S3 löschen
    try:
        get_s3().delete_object(Bucket=media["s3_bucket"], Key=media["s3_key"])
    except Exception:
        pass

    await db.execute("DELETE FROM public.media_files WHERE id=$1::uuid", media_id)
    return {"message": "Datei gelöscht"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Admin Content-Browser (Super-Admin sieht User-Inhalte)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/admin/tenant/{tenant_id}/content")
async def admin_tenant_content(tenant_id: str, session: SessionInfo = Depends(require_superadmin)):
    db = await get_db()
    tenant = await db.fetchrow(
        "SELECT id, slug, name, s3_prefix FROM public.tenants WHERE id=$1::uuid", tenant_id
    )
    if not tenant:
        raise HTTPException(404, "Tenant nicht gefunden")

    users = await db.fetch("""
        SELECT u.id, u.email, u.display_name, u.role, u.is_active,
               (SELECT COUNT(*) FROM public.sources s WHERE s.user_id=u.id)::int AS source_count,
               (SELECT COUNT(*) FROM public.media_files m WHERE m.user_id=u.id)::int AS media_count
        FROM public.users u
        WHERE u.tenant_id=$1::uuid
        ORDER BY u.display_name
    """, tenant_id)

    sources = await db.fetch("""
        SELECT s.id, s.name, s.source_type, s.status, s.s3_key, s.created_at, s.user_id,
               u.display_name AS user_name
        FROM public.sources s
        LEFT JOIN public.users u ON u.id=s.user_id
        WHERE s.tenant_id=$1::uuid
        ORDER BY s.created_at DESC
        LIMIT 100
    """, tenant_id)

    media = await db.fetch("""
        SELECT m.id, m.file_name, m.original_name, m.s3_key, m.content_type,
               m.file_size, m.folder, m.created_at, m.user_id,
               u.display_name AS user_name
        FROM public.media_files m
        LEFT JOIN public.users u ON u.id=m.user_id
        WHERE m.tenant_id=$1::uuid
        ORDER BY m.created_at DESC
        LIMIT 100
    """, tenant_id)

    return {
        "tenant": dict(tenant),
        "users": [dict(u) for u in users],
        "sources": [dict(s) for s in sources],
        "media": [{**dict(m), "url": presign_url(m['s3_key']),
                    "size_human": _human_size(m["file_size"]),
                    "is_image": (m["content_type"] or "").startswith("image/")}
                   for m in media],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: RAG Chat (direkt — Ollama Embedding + DB Search + Ollama LLM)
# ══════════════════════════════════════════════════════════════════════════════
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3-nothink")

SYSTEM_PROMPT = """Du bist Nexo, der KI-Assistent von EPPCOM Solutions.
Du beantwortest Fragen basierend auf dem bereitgestellten Kontext.
Wenn der Kontext keine Antwort enthält, sage ehrlich, dass du dazu keine Informationen hast.
Antworte auf Deutsch, präzise, kurz und verständlich. Keine Markdown-Überschriften.
Halte Antworten kompakt — maximal 3-4 Sätze wenn möglich."""


@app.post("/api/rag-chat")
async def rag_chat(body: RagChatRequest, session: SessionInfo = Depends(require_auth)):
    db = await get_db()
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Frage darf nicht leer sein")

    # Tenant bestimmen: Superadmin kann Tenant wählen, User hat festen Tenant
    tenant_id = body.tenant_id or session.tenant_id
    if not tenant_id:
        raise HTTPException(400, "Kein Tenant zugeordnet")
    if not session.can_access_tenant(tenant_id):
        raise HTTPException(403, "Kein Zugriff auf diesen Tenant")

    t_start = time.time()

    try:
        answer, sources_info, chunks_used = await _rag_pipeline(tenant_id, query)
    except httpx.TimeoutException:
        raise HTTPException(504, "Ollama Timeout")
    except httpx.ConnectError:
        raise HTTPException(502, f"Ollama nicht erreichbar unter {OLLAMA_URL}")

    elapsed = int((time.time() - t_start) * 1000)

    # Conversation speichern (mit Zusammenfassung)
    kernaussage, kernfrage = await _summarize_conversation(query, answer)
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO public.conversations
               (tenant_id, session_id, user_id, user_question, rag_answer,
                kernaussage, kernfrage, chunks_used, latency_ms, sources)
               VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10)""",
            uuid.UUID(tenant_id), f"ui_{session.user_id}",
            session.user_id, query, answer,
            kernaussage or None, kernfrage or None,
            chunks_used, elapsed, json.dumps(sources_info),
        )
    except Exception:
        pass

    return {
        "answer": answer,
        "sources": sources_info,
        "chunks_used": chunks_used,
        "latency_ms": elapsed,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Öffentlicher Chat für Typebot (API-Key Auth)
# ══════════════════════════════════════════════════════════════════════════════
SUMMARY_PROMPT = """Analysiere diese Konversation und extrahiere zwei Dinge:
1. KERNAUSSAGE: Die zentrale Aussage/Information aus der Antwort (1 Satz)
2. KERNFRAGE: Das eigentliche Anliegen/Bedürfnis hinter der Frage des Users (1 Satz)

Antworte NUR im folgenden Format, ohne weitere Erklärung:
KERNAUSSAGE: ...
KERNFRAGE: ..."""


async def _verify_api_key(tenant_id: str, api_key: str) -> bool:
    """Prüft API-Key gegen DB (SHA-256 Hash)."""
    db = await get_db()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    row = await db.fetchval(
        """SELECT 1 FROM public.api_keys
           WHERE tenant_id = $1 AND key_hash = $2 AND is_active = true""",
        uuid.UUID(tenant_id), key_hash,
    )
    return row is not None


async def _rag_pipeline(tenant_id: str, query: str):
    """Führt die RAG-Pipeline aus: Embed → Search → LLM. Gibt (answer, sources_info, chunks_used) zurück."""
    db = await get_db()

    # 1) Embedding (120s Timeout — Modell-Kaltstart kann dauern)
    async with httpx.AsyncClient(timeout=120) as client:
        embed_resp = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": query, "keep_alive": "30m"},
        )
        embed_data = embed_resp.json()
        embedding = embed_data.get("embeddings", [[]])[0] or embed_data.get("embedding", [])
        if not embedding:
            return "Embedding-Fehler: Ollama hat kein Ergebnis zurückgegeben.", [], 0

    # 2) Vektor-Suche
    vector_str = "[" + ",".join(str(round(x, 8)) for x in embedding) + "]"
    chunks = await db.fetch(
        """SELECT c.content, c.chunk_index, s.name AS source_name,
                  (1 - (e.embedding <=> $2::vector)) AS similarity
           FROM public.embeddings e
           JOIN public.chunks c ON c.id = e.chunk_id
           JOIN public.documents d ON d.id = c.document_id
           JOIN public.sources s ON s.id = d.source_id
           WHERE e.tenant_id = $1
             AND (1 - (e.embedding <=> $2::vector)) >= 0.3
           ORDER BY e.embedding <=> $2::vector
           LIMIT 5""",
        uuid.UUID(tenant_id), vector_str,
    )

    # 3) Kontext
    sources_info = []
    if chunks:
        context = "\n\n---\n\n".join(ch["content"] for ch in chunks)[:3000]
        sources_info = [{"source": ch["source_name"], "similarity": round(float(ch["similarity"]), 3)} for ch in chunks]
        user_msg = f"Kontext:\n{context}\n\nFrage: {query}"
    else:
        user_msg = f"Es wurden keine relevanten Dokumente gefunden. Frage: {query}"

    # 4) LLM (120s Timeout — Modell-Kaltstart kann dauern)
    async with httpx.AsyncClient(timeout=120) as client:
        llm_resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": CHAT_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "stream": False,
                "keep_alive": "30m",
            },
        )
        llm_data = llm_resp.json()
        answer = llm_data.get("message", {}).get("content", "")
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    return answer, sources_info, len(chunks)


async def _summarize_conversation(question: str, answer: str) -> tuple:
    """Extrahiert Kernaussage und Kernfrage via Ollama."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": CHAT_MODEL,
                    "messages": [
                        {"role": "system", "content": SUMMARY_PROMPT},
                        {"role": "user", "content": f"Frage: {question}\n\nAntwort: {answer[:2000]}"},
                    ],
                    "stream": False,
                },
            )
            text = resp.json().get("message", {}).get("content", "")
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

            kernaussage, kernfrage = "", ""
            for line in text.split("\n"):
                line = line.strip()
                if line.upper().startswith("KERNAUSSAGE:"):
                    kernaussage = line.split(":", 1)[1].strip()
                elif line.upper().startswith("KERNFRAGE:"):
                    kernfrage = line.split(":", 1)[1].strip()
            return kernaussage, kernfrage
    except Exception:
        return "", ""


async def _save_conversation_bg(
    tenant_id: str, session_id: str, query: str, answer: str,
    chunks_used: int, elapsed: int, sources_info: list,
    user_id: str = None,
):
    """Speichert Conversation + Summarization im Hintergrund (fire-and-forget)."""
    try:
        kernaussage, kernfrage = await _summarize_conversation(query, answer)
        db = await get_db()
        await db.execute(
            """INSERT INTO public.conversations
               (tenant_id, session_id, user_id, user_question, rag_answer,
                kernaussage, kernfrage, chunks_used, latency_ms, sources)
               VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10)""",
            uuid.UUID(tenant_id), session_id, user_id, query, answer,
            kernaussage or None, kernfrage or None,
            chunks_used, elapsed, json.dumps(sources_info),
        )
    except Exception:
        pass


async def _resolve_tenant_by_domain(origin: str) -> Optional[str]:
    """Findet den Tenant anhand der Domain aus dem Origin-Header."""
    if not origin:
        return None
    # Origin: "https://www.eppcom.de" → "www.eppcom.de"
    domain = re.sub(r"^https?://", "", origin).split("/")[0].split(":")[0].lower()
    db = await get_db()
    row = await db.fetchrow(
        """SELECT dw.tenant_id FROM public.domain_whitelist dw
           JOIN public.tenants t ON t.id = dw.tenant_id
           WHERE dw.domain = $1 AND dw.is_active = true AND t.status = 'active'""",
        domain,
    )
    return str(row["tenant_id"]) if row else None


@app.get("/api/public/media/{media_id}")
async def public_media(media_id: str):
    """Öffentlicher Media-Endpoint — leitet auf presigned S3-URL weiter, nur für is_public=true Medien."""
    db = await get_db()
    media = await db.fetchrow(
        "SELECT s3_key, s3_bucket, is_public FROM public.media_files WHERE id=$1::uuid", media_id
    )
    if not media:
        raise HTTPException(404, "Datei nicht gefunden")
    if not media["is_public"]:
        raise HTTPException(403, "Datei ist nicht öffentlich — Login erforderlich")
    url = presign_url(media["s3_key"], media["s3_bucket"], expires=7200)
    if not url:
        raise HTTPException(503, "S3 nicht verfügbar")
    return RedirectResponse(url=url, status_code=302)


@app.post("/api/public/widget-chat")
async def widget_chat(request: Request):
    """Öffentlicher Chat-Endpoint für Website-Widgets — Auth via Domain-Whitelist, kein API-Key nötig."""
    origin = request.headers.get("origin", "") or request.headers.get("referer", "")
    tenant_id = await _resolve_tenant_by_domain(origin)
    if not tenant_id:
        raise HTTPException(403, f"Domain nicht autorisiert")

    body = await request.json()
    query = (body.get("query") or "").strip()
    session_id = body.get("session_id", "anonymous")

    if not query:
        raise HTTPException(400, "query darf nicht leer sein")

    t_start = time.time()

    try:
        answer, sources_info, chunks_used = await _rag_pipeline(tenant_id, query)
    except httpx.TimeoutException:
        raise HTTPException(504, "Ollama Timeout")
    except httpx.ConnectError:
        raise HTTPException(502, "Ollama nicht erreichbar")

    elapsed = int((time.time() - t_start) * 1000)

    # Summarization + DB-Save im Hintergrund (nicht blockierend)
    asyncio.create_task(_save_conversation_bg(
        tenant_id, session_id, query, answer, chunks_used, elapsed, sources_info
    ))

    return {
        "answer": answer,
        "sources": sources_info,
        "chunks_used": chunks_used,
        "latency_ms": elapsed,
    }


@app.post("/api/public/voice-token")
async def public_voice_token(request: Request):
    """Öffentlicher Voice-Token-Endpoint für Widget — Auth via Domain-Whitelist."""
    origin = request.headers.get("origin", "") or request.headers.get("referer", "")
    tenant_id = await _resolve_tenant_by_domain(origin)
    if not tenant_id:
        raise HTTPException(403, "Domain nicht autorisiert")

    if not LIVEKIT_KEY or not LIVEKIT_SECRET:
        raise HTTPException(503, "LiveKit ist nicht konfiguriert")

    import hmac, base64, time as _time

    body = await request.json()
    identity = body.get("identity", f"widget-user-{uuid.uuid4().hex[:8]}")
    room_name = body.get("room", "eppcom-voice")

    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
    now = int(_time.time())
    payload_data = {
        "iss": LIVEKIT_KEY,
        "sub": identity,
        "iat": now,
        "exp": now + 3600,
        "nbf": now,
        "jti": str(uuid.uuid4()),
        "video": {
            "roomCreate": True,
            "roomJoin": True,
            "room": room_name,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
        "metadata": json.dumps({"name": identity}),
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=")
    signing_input = header + b"." + payload
    signature = base64.urlsafe_b64encode(
        hmac.new(LIVEKIT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")
    token = (signing_input + b"." + signature).decode()

    return {"token": token, "url": os.getenv("LIVEKIT_PUBLIC_URL", "wss://appdb.eppcom.de:7443")}


@app.post("/api/public/chat")
async def public_chat(request: Request):
    """Öffentlicher Endpoint für Typebot — Auth via X-API-Key + X-Tenant-ID Header."""
    tenant_id = request.headers.get("X-Tenant-ID", "")
    api_key = request.headers.get("X-API-Key", "")

    if not tenant_id or not api_key:
        raise HTTPException(401, "X-Tenant-ID und X-API-Key Header erforderlich")

    if not await _verify_api_key(tenant_id, api_key):
        raise HTTPException(403, "Ungültiger API-Key oder Tenant")

    body = await request.json()
    query = (body.get("query") or "").strip()
    session_id = body.get("session_id", "anonymous")

    if not query:
        raise HTTPException(400, "query darf nicht leer sein")

    t_start = time.time()

    try:
        answer, sources_info, chunks_used = await _rag_pipeline(tenant_id, query)
    except httpx.TimeoutException:
        raise HTTPException(504, "Ollama Timeout")
    except httpx.ConnectError:
        raise HTTPException(502, "Ollama nicht erreichbar")

    elapsed = int((time.time() - t_start) * 1000)

    # Summarization + DB-Save im Hintergrund (nicht blockierend)
    asyncio.create_task(_save_conversation_bg(
        tenant_id, session_id, query, answer, chunks_used, elapsed, sources_info
    ))

    return {
        "answer": answer,
        "sources": sources_info,
        "chunks_used": chunks_used,
        "latency_ms": elapsed,
    }


# ── Conversations Admin-Endpoint ─────────────────────────────────────────────
@app.get("/api/conversations")
async def list_conversations(
    tenant_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_auth),
):
    db = await get_db()
    if session.is_superadmin():
        conditions = []
        params = []
        idx = 1
        if tenant_id:
            conditions.append(f"c.tenant_id = ${idx}")
            params.append(uuid.UUID(tenant_id))
            idx += 1
        if user_id:
            conditions.append(f"c.user_id = ${idx}::uuid")
            params.append(user_id)
            idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = await db.fetch(
            f"""SELECT c.*, t.slug AS tenant_slug, u.display_name AS user_name, u.email AS user_email
                FROM public.conversations c
                JOIN public.tenants t ON t.id = c.tenant_id
                LEFT JOIN public.users u ON u.id = c.user_id
                {where} ORDER BY c.created_at DESC LIMIT 200""",
            *params,
        )
    elif session.is_admin() and session.tenant_id:
        if user_id:
            rows = await db.fetch(
                """SELECT c.*, t.slug AS tenant_slug, u.display_name AS user_name, u.email AS user_email
                   FROM public.conversations c
                   JOIN public.tenants t ON t.id = c.tenant_id
                   LEFT JOIN public.users u ON u.id = c.user_id
                   WHERE c.tenant_id = $1 AND c.user_id = $2::uuid
                   ORDER BY c.created_at DESC LIMIT 200""",
                uuid.UUID(session.tenant_id), user_id,
            )
        else:
            rows = await db.fetch(
                """SELECT c.*, t.slug AS tenant_slug, u.display_name AS user_name, u.email AS user_email
                   FROM public.conversations c
                   JOIN public.tenants t ON t.id = c.tenant_id
                   LEFT JOIN public.users u ON u.id = c.user_id
                   WHERE c.tenant_id = $1
                   ORDER BY c.created_at DESC LIMIT 200""",
                uuid.UUID(session.tenant_id),
            )
    else:
        # User sieht eigene + freigegebene Chats
        rows = await db.fetch(
            """SELECT c.*, t.slug AS tenant_slug, u.display_name AS user_name, u.email AS user_email
               FROM public.conversations c
               JOIN public.tenants t ON t.id = c.tenant_id
               LEFT JOIN public.users u ON u.id = c.user_id
               WHERE (c.user_id = $1::uuid OR c.id IN (
                   SELECT content_id FROM public.content_shares
                   WHERE shared_with = $1::uuid AND content_type = 'conversation'
               ))
               ORDER BY c.created_at DESC LIMIT 200""",
            session.user_id,
        )

    result = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        d["tenant_id"] = str(d["tenant_id"])
        if d.get("user_id"):
            d["user_id"] = str(d["user_id"])
        d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
        if isinstance(d.get("sources"), str):
            d["sources"] = json.loads(d["sources"])
        result.append(d)
    return result


@app.post("/api/conversations/delete")
async def delete_conversations(request: Request, session: SessionInfo = Depends(require_auth)):
    """Löscht mehrere Conversations anhand einer Liste von IDs."""
    body = await request.json()
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "Keine IDs angegeben")

    db = await get_db()
    deleted = 0
    for cid in ids:
        # Zugriffsprüfung pro Conversation
        row = await db.fetchrow("SELECT tenant_id FROM public.conversations WHERE id=$1::uuid", cid)
        if not row:
            continue
        if not session.is_superadmin() and not session.can_access_tenant(str(row["tenant_id"])):
            continue
        await db.execute("DELETE FROM public.conversations WHERE id=$1::uuid", cid)
        deleted += 1

    return {"deleted": deleted}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Domain-Whitelist Verwaltung
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/domains")
async def list_domains(
    tenant_id: str = Query(None),
    session: SessionInfo = Depends(require_auth),
):
    """Listet Domain-Whitelist-Einträge (Superadmin: alle, Admin: eigener Tenant)."""
    db = await get_db()
    if session.is_superadmin():
        if tenant_id:
            rows = await db.fetch(
                """SELECT dw.*, t.slug AS tenant_slug FROM public.domain_whitelist dw
                   JOIN public.tenants t ON t.id=dw.tenant_id
                   WHERE dw.tenant_id=$1::uuid ORDER BY dw.domain""", tenant_id)
        else:
            rows = await db.fetch(
                """SELECT dw.*, t.slug AS tenant_slug FROM public.domain_whitelist dw
                   JOIN public.tenants t ON t.id=dw.tenant_id ORDER BY t.slug, dw.domain""")
    elif session.tenant_id:
        rows = await db.fetch(
            """SELECT dw.*, t.slug AS tenant_slug FROM public.domain_whitelist dw
               JOIN public.tenants t ON t.id=dw.tenant_id
               WHERE dw.tenant_id=$1::uuid ORDER BY dw.domain""", session.tenant_id)
    else:
        return []
    return [dict(r) for r in rows]


@app.post("/api/domains")
async def add_domain(request: Request, session: SessionInfo = Depends(require_auth)):
    """Fügt eine Domain zur Whitelist hinzu."""
    if not session.is_superadmin() and not session.is_admin():
        raise HTTPException(403, "Nur Admins")
    body = await request.json()
    tenant_id = body.get("tenant_id", session.tenant_id or "")
    domain = (body.get("domain") or "").strip().lower()
    if not domain:
        raise HTTPException(400, "Domain erforderlich")
    if not tenant_id:
        raise HTTPException(400, "Tenant erforderlich")
    if not session.can_access_tenant(tenant_id):
        raise HTTPException(403, "Kein Zugriff auf Tenant")

    # Domain bereinigen
    domain = re.sub(r"^https?://", "", domain).split("/")[0].split(":")[0]

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO public.domain_whitelist (tenant_id, domain) VALUES ($1::uuid, $2)",
            tenant_id, domain,
        )
    except Exception:
        raise HTTPException(409, f"Domain '{domain}' existiert bereits für diesen Tenant")
    return {"domain": domain, "tenant_id": tenant_id}


@app.delete("/api/domains/{domain_id}")
async def delete_domain(domain_id: str, session: SessionInfo = Depends(require_auth)):
    """Entfernt eine Domain aus der Whitelist."""
    if not session.is_superadmin() and not session.is_admin():
        raise HTTPException(403, "Nur Admins")
    db = await get_db()
    row = await db.fetchrow("SELECT tenant_id FROM public.domain_whitelist WHERE id=$1::uuid", domain_id)
    if not row:
        raise HTTPException(404, "Domain nicht gefunden")
    if not session.can_access_tenant(str(row["tenant_id"])):
        raise HTTPException(403, "Kein Zugriff")
    await db.execute("DELETE FROM public.domain_whitelist WHERE id=$1::uuid", domain_id)
    return {"deleted": domain_id}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES: Terminverwaltung (Appointments)
# ══════════════════════════════════════════════════════════════════════════════

def _appointment_to_dict(row) -> dict:
    d = dict(row)
    for k in ("id", "user_id", "tenant_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("start_time", "end_time", "created_at", "updated_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


@app.get("/api/appointments")
async def list_appointments(
    user_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: SessionInfo = Depends(require_auth),
):
    """Termine auflisten. Superadmin sieht alle, sonst nur eigene."""
    db = await get_db()
    conditions = []
    params = []
    idx = 1

    if session.is_superadmin() and user_id:
        conditions.append(f"a.user_id = ${idx}::uuid")
        params.append(user_id)
        idx += 1
    elif not session.is_superadmin():
        conditions.append(f"a.user_id = ${idx}::uuid")
        params.append(session.user_id)
        idx += 1

    if start:
        conditions.append(f"a.start_time >= ${idx}::timestamptz")
        params.append(start)
        idx += 1
    if end:
        conditions.append(f"a.end_time <= ${idx}::timestamptz")
        params.append(end)
        idx += 1
    if status:
        conditions.append(f"a.status = ${idx}")
        params.append(status)
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await db.fetch(
        f"""SELECT a.*, u.display_name AS user_display_name
            FROM public.appointments a
            JOIN public.users u ON u.id = a.user_id
            {where}
            ORDER BY a.start_time ASC
            LIMIT 500""",
        *params,
    )
    return [_appointment_to_dict(r) for r in rows]


@app.post("/api/appointments")
async def create_appointment(request: Request, session: SessionInfo = Depends(require_auth)):
    """Neuen Termin erstellen."""
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "Titel erforderlich")

    start_time_raw = body.get("start_time")
    end_time_raw = body.get("end_time")
    if not start_time_raw or not end_time_raw:
        raise HTTPException(400, "Start- und Endzeit erforderlich")
    try:
        start_time = datetime.fromisoformat(start_time_raw) if isinstance(start_time_raw, str) else start_time_raw
        end_time = datetime.fromisoformat(end_time_raw) if isinstance(end_time_raw, str) else end_time_raw
    except (ValueError, TypeError):
        raise HTTPException(400, "Ungültiges Datums-Format")

    target_user_id = body.get("user_id", session.user_id)
    if target_user_id != session.user_id and not session.is_superadmin():
        raise HTTPException(403, "Nur Superadmin kann Termine fuer andere erstellen")

    status_val = body.get("status", "scheduled")
    if status_val not in ("scheduled", "completed", "cancelled", "blocked"):
        raise HTTPException(400, "Ungueltiger Status")

    db = await get_db()
    row = await db.fetchrow(
        """INSERT INTO public.appointments
           (user_id, tenant_id, title, description, start_time, end_time, status,
            customer_name, customer_email, customer_phone, customer_company,
            customer_address, customer_notes)
           VALUES ($1::uuid, $2, $3, $4, $5, $6, $7,
                   $8, $9, $10, $11, $12, $13)
           RETURNING *""",
        target_user_id,
        uuid.UUID(body["tenant_id"]) if body.get("tenant_id") else None,
        title,
        body.get("description", ""),
        start_time,
        end_time,
        status_val,
        body.get("customer_name", ""),
        body.get("customer_email", ""),
        body.get("customer_phone", ""),
        body.get("customer_company", ""),
        body.get("customer_address", ""),
        body.get("customer_notes", ""),
    )
    return _appointment_to_dict(row)


@app.put("/api/appointments/{appointment_id}")
async def update_appointment(appointment_id: str, request: Request, session: SessionInfo = Depends(require_auth)):
    """Termin aktualisieren."""
    db = await get_db()
    existing = await db.fetchrow("SELECT * FROM public.appointments WHERE id=$1::uuid", appointment_id)
    if not existing:
        raise HTTPException(404, "Termin nicht gefunden")
    if str(existing["user_id"]) != session.user_id and not session.is_superadmin():
        raise HTTPException(403, "Kein Zugriff")

    body = await request.json()
    start_val = body.get("start_time")
    end_val = body.get("end_time")
    start_dt = datetime.fromisoformat(start_val) if isinstance(start_val, str) else (start_val or existing["start_time"])
    end_dt = datetime.fromisoformat(end_val) if isinstance(end_val, str) else (end_val or existing["end_time"])
    await db.execute(
        """UPDATE public.appointments SET
           title=$2, description=$3, start_time=$4, end_time=$5,
           status=$6, customer_name=$7, customer_email=$8, customer_phone=$9,
           customer_company=$10, customer_address=$11, customer_notes=$12, tenant_id=$13
           WHERE id=$1::uuid""",
        appointment_id,
        body.get("title", existing["title"]),
        body.get("description", existing["description"]),
        start_dt,
        end_dt,
        body.get("status", existing["status"]),
        body.get("customer_name", existing["customer_name"]),
        body.get("customer_email", existing["customer_email"]),
        body.get("customer_phone", existing["customer_phone"]),
        body.get("customer_company", existing["customer_company"]),
        body.get("customer_address", existing["customer_address"]),
        body.get("customer_notes", existing["customer_notes"]),
        uuid.UUID(body["tenant_id"]) if body.get("tenant_id") else existing["tenant_id"],
    )
    updated = await db.fetchrow("SELECT * FROM public.appointments WHERE id=$1::uuid", appointment_id)
    return _appointment_to_dict(updated)


@app.delete("/api/appointments/{appointment_id}")
async def delete_appointment(appointment_id: str, session: SessionInfo = Depends(require_auth)):
    """Termin loeschen."""
    db = await get_db()
    existing = await db.fetchrow("SELECT user_id FROM public.appointments WHERE id=$1::uuid", appointment_id)
    if not existing:
        raise HTTPException(404, "Termin nicht gefunden")
    if str(existing["user_id"]) != session.user_id and not session.is_superadmin():
        raise HTTPException(403, "Kein Zugriff")

    await db.execute("DELETE FROM public.appointments WHERE id=$1::uuid", appointment_id)
    return {"deleted": appointment_id}


@app.get("/api/appointments/users")
async def list_appointment_users(session: SessionInfo = Depends(require_superadmin)):
    """Alle User mit Terminen auflisten (fuer Superadmin-Filter)."""
    db = await get_db()
    rows = await db.fetch(
        """SELECT DISTINCT u.id, u.display_name, u.email
           FROM public.users u
           WHERE u.is_active = true
           ORDER BY u.display_name"""
    )
    return [{"id": str(r["id"]), "display_name": r["display_name"], "email": r["email"]} for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# LiveKit Token Endpoint (Voice Bot)
# ══════════════════════════════════════════════════════════════════════════════
LIVEKIT_KEY    = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

@app.post("/api/livekit-token")
async def get_livekit_token(body: dict, session: SessionInfo = Depends(require_auth)):
    """LiveKit-Token generieren für Voice-Bot-Zugang."""
    if not LIVEKIT_KEY or not LIVEKIT_SECRET:
        raise HTTPException(503, "LiveKit ist nicht konfiguriert (LIVEKIT_API_KEY/SECRET fehlen)")

    import hmac, base64, time as _time

    # Manuelles JWT erstellen (ohne livekit-api Dependency)
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
    now = int(_time.time())
    identity = body.get("identity", f"user-{session.user_id}")
    room_name = body.get("room", "eppcom-voice")
    payload_data = {
        "iss": LIVEKIT_KEY,
        "sub": identity,
        "iat": now,
        "exp": now + 3600,
        "nbf": now,
        "jti": str(uuid.uuid4()),
        "video": {
            "roomCreate": True,
            "roomJoin": True,
            "room": room_name,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
        "metadata": json.dumps({"name": identity}),
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=")
    signing_input = header + b"." + payload
    signature = base64.urlsafe_b64encode(
        hmac.new(LIVEKIT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")
    token = (signing_input + b"." + signature).decode()

    return {"token": token, "url": os.getenv("LIVEKIT_PUBLIC_URL", "wss://appdb.eppcom.de:7443")}


# ══════════════════════════════════════════════════════════════════════════════
# Jitsi Meet Token Endpoint
# ══════════════════════════════════════════════════════════════════════════════
JITSI_APP_ID     = os.getenv("JITSI_APP_ID", "eppcom")
JITSI_APP_SECRET = os.getenv("JITSI_APP_SECRET", "")
JITSI_URL        = os.getenv("JITSI_URL", "https://meet.eppcom.de")

def _generate_jitsi_jwt(room: str, user_id: str, display_name: str, email: str, is_moderator: bool) -> str:
    """Erzeugt ein Jitsi-JWT für den gegebenen User und Raum."""
    import hmac, base64, time as _time
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
    now = int(_time.time())
    payload_data = {
        "iss": JITSI_APP_ID,
        "aud": "jitsi",
        "sub": "meet.jitsi",
        "iat": now,
        "exp": now + 7200,
        "nbf": now,
        "room": room,
        "moderator": is_moderator,
        "context": {
            "user": {
                "id": user_id,
                "name": display_name or email,
                "email": email,
                "avatar": "",
                "moderator": is_moderator,
            },
        },
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=")
    signing_input = header + b"." + payload
    signature = base64.urlsafe_b64encode(
        hmac.new(JITSI_APP_SECRET.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")
    return (signing_input + b"." + signature).decode()


@app.post("/api/jitsi-token")
async def get_jitsi_token(body: dict, session: SessionInfo = Depends(require_auth)):
    """JWT-Token fuer Jitsi Meet generieren — authentifiziert User mit ihren Platform-Credentials."""
    if not JITSI_APP_SECRET:
        raise HTTPException(503, "Jitsi ist nicht konfiguriert (JITSI_APP_SECRET fehlt)")

    room = body.get("room", "eppcom-meeting")
    room = re.sub(r'[^a-zA-Z0-9_-]', '', room) or "eppcom-meeting"

    display = (session.display_name or "").strip()
    email = (session.email or "").strip().lower()
    is_moderator = any(tag in display.upper() for tag in ["MARCEL", "EPPLER", "EPPCOM"]) or \
                   "eppler" in email or "eppcom" in email

    token = _generate_jitsi_jwt(room, session.user_id, session.display_name, session.email, is_moderator)

    return {
        "token": token,
        "room": room,
        "url": f"{JITSI_URL}/{room}?jwt={token}",
    }


@app.post("/api/jitsi-auth")
async def jitsi_auth_login(body: dict):
    """Öffentlicher Endpoint: Login + JWT-Token für Jitsi Meet (für meeting-auth Seite)."""
    if not JITSI_APP_SECRET:
        raise HTTPException(503, "Jitsi ist nicht konfiguriert")

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    room = body.get("room") or "eppcom-meeting"
    room = re.sub(r'[^a-zA-Z0-9_-]', '', room) or "eppcom-meeting"

    if not email or not password:
        raise HTTPException(400, "E-Mail und Passwort erforderlich")

    db = await get_db()
    user = await db.fetchrow(
        "SELECT id, email, password_hash, display_name, role, is_active FROM public.users WHERE email=$1",
        email
    )
    if not user:
        raise HTTPException(401, "E-Mail oder Passwort falsch")
    if not user["is_active"]:
        raise HTTPException(403, "Account deaktiviert")
    if not _verify_password(password, user["password_hash"]):
        raise HTTPException(401, "E-Mail oder Passwort falsch")

    # Nur admin/superadmin dürfen Moderator sein
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(403, "Nur Administratoren können als Moderator beitreten")

    token = _generate_jitsi_jwt(
        room, str(user["id"]), user["display_name"], user["email"], is_moderator=True
    )

    return {
        "token": token,
        "room": room,
        "url": f"{JITSI_URL}/{room}?jwt={token}",
        "display_name": user["display_name"],
    }


@app.get("/meeting-auth")
async def meeting_auth_page(room: str = "eppcom-meeting"):
    """Standalone Meeting-Auth Seite: Moderator-Login oder Gast-Beitritt."""
    room_safe = re.sub(r'[^a-zA-Z0-9_-]', '', room) or "eppcom-meeting"
    jitsi_guest_url = f"{JITSI_URL}/{room_safe}"
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meeting beitreten — EPPCOM</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  body {{ font-family: 'Inter', system-ui, sans-serif; }}
  .fade-in {{ animation: fadeIn .3s ease-out; }}
  @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
</style>
</head>
<body class="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 min-h-screen flex items-center justify-center p-4">
  <div id="app" class="w-full max-w-md">

    <!-- Step 1: Moderator-Frage -->
    <div id="step-question" class="bg-white rounded-2xl shadow-2xl p-8 fade-in">
      <div class="flex items-center gap-3 mb-6">
        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-lg">
          <span class="text-xl font-bold text-white">E</span>
        </div>
        <div>
          <h1 class="text-xl font-bold text-slate-900">Meeting beitreten</h1>
          <p class="text-sm text-slate-500">Raum: <span class="font-medium text-blue-600">{room_safe}</span></p>
        </div>
      </div>
      <p class="text-slate-700 mb-6">Sind Sie der Moderator dieses Meetings?</p>
      <div class="flex gap-3">
        <button onclick="showLogin()" class="flex-1 bg-blue-600 text-white py-3 px-4 rounded-xl font-semibold hover:bg-blue-500 transition-all shadow-sm">
          Ja, ich bin Moderator
        </button>
        <button onclick="joinAsGuest()" class="flex-1 bg-slate-100 text-slate-700 py-3 px-4 rounded-xl font-semibold hover:bg-slate-200 transition-all">
          Nein, als Gast beitreten
        </button>
      </div>
    </div>

    <!-- Step 2: Login-Formular -->
    <div id="step-login" class="bg-white rounded-2xl shadow-2xl p-8 fade-in" style="display:none;">
      <div class="flex items-center gap-3 mb-6">
        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-lg">
          <span class="text-xl font-bold text-white">E</span>
        </div>
        <div>
          <h1 class="text-xl font-bold text-slate-900">Moderator-Login</h1>
          <p class="text-sm text-slate-500">Raum: <span class="font-medium text-blue-600">{room_safe}</span></p>
        </div>
      </div>

      <div id="login-error" class="hidden mb-4 bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 text-sm"></div>

      <form onsubmit="doLogin(event)" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1.5">E-Mail</label>
          <input type="email" id="login-email" required placeholder="ihre@email.de"
            class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all">
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1.5">Passwort</label>
          <input type="password" id="login-password" required placeholder="Passwort"
            class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all">
        </div>
        <button type="submit" id="login-btn"
          class="w-full bg-blue-600 text-white py-3 px-4 rounded-xl font-semibold hover:bg-blue-500 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
          Als Moderator beitreten
        </button>
      </form>

      <div class="mt-4 pt-4 border-t border-slate-100 text-center">
        <button onclick="joinAsGuest()" class="text-sm text-slate-500 hover:text-blue-600 transition-colors">
          Stattdessen als Gast beitreten
        </button>
      </div>

      <div class="mt-3 text-center">
        <button onclick="showQuestion()" class="text-xs text-slate-400 hover:text-slate-600 transition-colors">
          Zurueck
        </button>
      </div>
    </div>

    <!-- Step 3: Fehler mit Gast-Option -->
    <div id="step-error" class="bg-white rounded-2xl shadow-2xl p-8 fade-in" style="display:none;">
      <div class="flex items-center gap-3 mb-6">
        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-lg">
          <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"></path></svg>
        </div>
        <div>
          <h1 class="text-xl font-bold text-slate-900">Anmeldung fehlgeschlagen</h1>
          <p class="text-sm text-slate-500" id="error-detail">Die Zugangsdaten sind nicht korrekt.</p>
        </div>
      </div>
      <p class="text-slate-700 mb-6">Moechten Sie stattdessen als Gast an der Konferenz teilnehmen?</p>
      <div class="flex gap-3">
        <button onclick="joinAsGuest()" class="flex-1 bg-blue-600 text-white py-3 px-4 rounded-xl font-semibold hover:bg-blue-500 transition-all shadow-sm">
          Als Gast beitreten
        </button>
        <button onclick="showLogin()" class="flex-1 bg-slate-100 text-slate-700 py-3 px-4 rounded-xl font-semibold hover:bg-slate-200 transition-all">
          Erneut versuchen
        </button>
      </div>
    </div>

  </div>

  <script>
    const ROOM = '{room_safe}';
    const GUEST_URL = '{jitsi_guest_url}';

    function showStep(id) {{
      document.querySelectorAll('#app > div').forEach(el => el.style.display = 'none');
      const el = document.getElementById(id);
      el.style.display = 'block';
      el.classList.remove('fade-in');
      void el.offsetWidth;
      el.classList.add('fade-in');
    }}

    function showQuestion() {{ showStep('step-question'); }}
    function showLogin() {{
      showStep('step-login');
      document.getElementById('login-error').classList.add('hidden');
      document.getElementById('login-email').focus();
    }}

    function joinAsGuest() {{
      // Hash-Config-Override verhindert erneuten Auto-Redirect zu dieser Auth-Seite
      window.location.href = GUEST_URL + '#config.tokenAuthUrl=%22%22';
    }}

    async function doLogin(e) {{
      e.preventDefault();
      const email = document.getElementById('login-email').value.trim();
      const password = document.getElementById('login-password').value;
      const btn = document.getElementById('login-btn');
      const errDiv = document.getElementById('login-error');

      btn.disabled = true;
      btn.textContent = 'Wird angemeldet...';
      errDiv.classList.add('hidden');

      try {{
        const res = await fetch('/api/jitsi-auth', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ email, password, room: ROOM }}),
        }});

        if (res.ok) {{
          const data = await res.json();
          window.location.href = data.url;
          return;
        }}

        const err = await res.json().catch(() => ({{ detail: 'Anmeldung fehlgeschlagen' }}));
        const msg = typeof err.detail === 'string' ? err.detail : 'Anmeldung fehlgeschlagen';

        document.getElementById('error-detail').textContent = msg;
        showStep('step-error');
      }} catch(err) {{
        document.getElementById('error-detail').textContent = 'Netzwerkfehler — bitte erneut versuchen.';
        showStep('step-error');
      }} finally {{
        btn.disabled = false;
        btn.textContent = 'Als Moderator beitreten';
      }}
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(html)


# ══════════════════════════════════════════════════════════════════════════════
# API Key Management (Admin-UI)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/api-keys")
async def list_api_keys(session: SessionInfo = Depends(require_superadmin)):
    """Liste aller API Keys (nur SuperAdmin)."""
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, key_preview, tenant_id, is_active, created_at, last_used_at
            FROM public.api_keys
            ORDER BY created_at DESC
        """)
        return [dict(r) for r in rows]


@app.post("/api/api-keys", status_code=201)
async def create_api_key(body: dict, session: SessionInfo = Depends(require_superadmin)):
    """Neuen API Key erstellen."""
    name = body.get("name", "").strip()
    tenant_id = body.get("tenant_id")
    expires_at = body.get("expires_at")

    if not name:
        raise HTTPException(400, "Name erforderlich")

    # Key generieren: sk-{32 Zeichen zufällig}
    key = "sk-" + secrets.token_urlsafe(32)[:32]
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_preview = key[-8:]  # Letzte 8 Zeichen

    async with _db_pool.acquire() as conn:
        key_id = await conn.fetchval("""
            INSERT INTO public.api_keys (name, key_hash, key_preview, tenant_id, created_by, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, name, key_hash, key_preview, tenant_id, session.user_id, expires_at)

    return {"id": key_id, "key": key, "key_preview": key_preview}


@app.delete("/api/api-keys/{key_id}")
async def revoke_api_key(key_id: str, session: SessionInfo = Depends(require_superadmin)):
    """API Key widerrufen."""
    async with _db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE public.api_keys SET is_active = false WHERE id = $1
        """, key_id)

    return {"status": "revoked"}


# ══════════════════════════════════════════════════════════════════════════════
# Audit Log (Admin-UI)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/audit-log")
async def list_audit_log(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    action: str = Query(None),
    user_id: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    session: SessionInfo = Depends(require_superadmin)
):
    """Audit Log mit Filtering."""
    where_clauses = []
    params = []
    param_count = 1

    if action:
        where_clauses.append(f"action = ${param_count}")
        params.append(action)
        param_count += 1

    if user_id:
        where_clauses.append(f"user_id = ${param_count}")
        params.append(user_id)
        param_count += 1

    if from_date:
        where_clauses.append(f"DATE(created_at) >= ${param_count}")
        params.append(from_date)
        param_count += 1

    if to_date:
        where_clauses.append(f"DATE(created_at) <= ${param_count}")
        params.append(to_date)
        param_count += 1

    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT * FROM public.audit_log
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """, *params, limit, offset)

        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# Platform Settings (Admin-UI)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/settings")
async def get_settings(session: SessionInfo = Depends(require_superadmin)):
    """Alle Platform-Einstellungen abrufen."""
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM public.platform_settings")
        result = {r['key']: r['value'] for r in rows}

    return result


@app.put("/api/settings")
async def update_settings(body: dict, session: SessionInfo = Depends(require_superadmin)):
    """Platform-Einstellungen aktualisieren."""
    async with _db_pool.acquire() as conn:
        for key, value in body.items():
            await conn.execute("""
                INSERT INTO public.platform_settings (key, value, updated_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_by = $3, updated_at = NOW()
            """, key, json.dumps(value) if not isinstance(value, str) else value, session.user_id)

    return {"status": "updated"}


# ══════════════════════════════════════════════════════════════════════════════
# Analytics (Admin-UI)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/analytics/conversations-per-day")
async def analytics_conversations_per_day(
    days: int = Query(30, ge=1, le=365),
    session: SessionInfo = Depends(require_superadmin)
):
    """Conversations pro Tag für die letzten N Tage."""
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as count
            FROM public.audit_log
            WHERE action LIKE '%conversation%' AND created_at >= NOW() - INTERVAL '1 day' * $1
            GROUP BY DATE(created_at)
            ORDER BY date
        """, days)

        return [{"date": str(r['date']), "count": r['count']} for r in rows]


@app.get("/api/analytics/documents-per-week")
async def analytics_documents_per_week(
    weeks: int = Query(8, ge=1, le=52),
    session: SessionInfo = Depends(require_superadmin)
):
    """Dokumente pro Woche für die letzten N Wochen."""
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                DATE_TRUNC('week', created_at) as week,
                COUNT(*) as count
            FROM public.audit_log
            WHERE resource_type = 'document' AND action = 'document.create'
              AND created_at >= NOW() - INTERVAL '1 week' * $1
            GROUP BY DATE_TRUNC('week', created_at)
            ORDER BY week
        """, weeks)

        return [{"week": str(r['week']), "count": r['count']} for r in rows]


@app.get("/api/analytics/tenant-usage")
async def analytics_tenant_usage(session: SessionInfo = Depends(require_superadmin)):
    """Nutzungsstatistiken pro Tenant."""
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                t.id,
                t.name,
                t.plan,
                COALESCE((SELECT COUNT(*) FROM public.audit_log
                          WHERE resource_type = 'tenant' AND resource_id = t.id::text), 0) as activity_count,
                COALESCE((SELECT COUNT(*) FROM public.api_keys WHERE tenant_id = t.id), 0) as api_keys_count,
                t.max_docs,
                t.max_chunks
            FROM public.tenants t
            WHERE t.status != 'deleted'
            ORDER BY t.created_at DESC
        """)

        return [dict(r) for r in rows]


@app.get("/api/analytics/summary")
async def analytics_summary(session: SessionInfo = Depends(require_superadmin)):
    """Dashboard Summary Statistics."""
    async with _db_pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM public.users WHERE is_active = true")
        tenants_count = await conn.fetchval("SELECT COUNT(*) FROM public.tenants WHERE status = 'active'")
        documents_count = await conn.fetchval("SELECT COUNT(*) FROM public.audit_log WHERE action = 'document.create'")
        api_calls_today = await conn.fetchval(
            "SELECT COUNT(*) FROM public.audit_log WHERE DATE(created_at) = CURRENT_DATE"
        )

    return {
        "users": users_count or 0,
        "tenants": tenants_count or 0,
        "documents": documents_count or 0,
        "api_calls_today": api_calls_today or 0
    }


# ══════════════════════════════════════════════════════════════════════════════
# Audit Logging Helper
# ══════════════════════════════════════════════════════════════════════════════

async def log_audit(
    user_id: str,
    user_email: str,
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    details: dict = None,
    ip_address: str = None
):
    """Hilfsfunktion zum Schreiben von Audit Log Einträgen."""
    async with _db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO public.audit_log (user_id, user_email, action, resource_type, resource_id, details, ip_address)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, user_id, user_email, action, resource_type, resource_id, json.dumps(details or {}), ip_address)


# ══════════════════════════════════════════════════════════════════════════════
# Voicebot Monitoring API
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/voicebot/metrics")
async def get_voicebot_metrics(session: SessionInfo = Depends(require_auth)):
    if not session.is_superadmin():
        raise HTTPException(403, "Nur SuperAdmin")
    db = await get_db()
    stats = await db.fetch("""
        SELECT step, COUNT(*) as total_calls,
               ROUND(AVG(duration_ms)) as avg_ms,
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)) as median_ms,
               ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)) as p95_ms,
               MIN(duration_ms) as min_ms, MAX(duration_ms) as max_ms
        FROM voicebot_metrics
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY step
        ORDER BY CASE step WHEN 'total' THEN 1 WHEN 'llm' THEN 2 WHEN 'rag' THEN 3 WHEN 'embedding' THEN 4 ELSE 5 END
    """)
    slow = await db.fetch("""
        SELECT session_id, user_query, total_duration_ms, timestamp
        FROM voicebot_slow_queries
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        ORDER BY timestamp DESC LIMIT 5
    """)
    hourly = await db.fetch("""
        SELECT DATE_TRUNC('hour', timestamp) as hour,
               COUNT(DISTINCT session_id) as sessions, COUNT(*) as total_calls
        FROM voicebot_metrics
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY hour ORDER BY hour DESC LIMIT 12
    """)
    return {
        "stats": [dict(r) for r in stats],
        "slow_queries": [dict(r) for r in slow],
        "hourly": [dict(r) for r in hourly]
    }


# ══════════════════════════════════════════════════════════════════════════════
# Statische Dateien
# ══════════════════════════════════════════════════════════════════════════════
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/widget", StaticFiles(directory="widget"), name="widget")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html") as f:
        content = f.read()
    return HTMLResponse(content, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"})
