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
from fastapi.responses import HTMLResponse, JSONResponse
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
            resp = await client.post(f"{OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": batch})
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
    return session.to_dict()


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
async def change_password(user_id: str, body: PasswordChange, session: SessionInfo = Depends(require_auth)):
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

    if len(body.new_password) < 6:
        raise HTTPException(400, "Passwort muss mindestens 6 Zeichen haben")

    pw_hash = _hash_password(body.new_password)
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
        conditions.append(f"s.user_id=${idx}::uuid")
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
    # Tenant-Zugriff prüfen
    effective_tenant = tenant_id.strip() if tenant_id else ""
    if not session.is_superadmin():
        if session.tenant_id:
            effective_tenant = session.tenant_id
        else:
            raise HTTPException(403, "Kein Tenant zugewiesen")
    if not effective_tenant:
        raise HTTPException(400, "Kein Tenant ausgewählt")
    if not session.can_access_tenant(effective_tenant):
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
            conditions.append(f"m.user_id=${idx}::uuid")
            params.append(session.user_id)
            idx += 1
        elif user_id:
            conditions.append(f"m.user_id=${idx}::uuid")
            params.append(user_id)
            idx += 1
    else:
        conditions.append(f"m.user_id=${idx}::uuid")
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

    effective_tenant = tenant_id
    if not session.is_superadmin():
        if session.tenant_id:
            effective_tenant = session.tenant_id
        else:
            raise HTTPException(403, "Kein Tenant zugewiesen")

    db = await get_db()
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

SYSTEM_PROMPT = """Du bist ein freundlicher und hilfreicher KI-Assistent.
Du beantwortest Fragen ausschließlich basierend auf dem bereitgestellten Kontext.
Wenn der Kontext keine Antwort enthält, sage ehrlich, dass du dazu keine Informationen hast.
Antworte auf Deutsch, präzise und verständlich. Verwende keine Markdown-Überschriften."""


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
               (tenant_id, session_id, user_question, rag_answer,
                kernaussage, kernfrage, chunks_used, latency_ms, sources)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            uuid.UUID(tenant_id), f"ui_{session.user_id}", query, answer,
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

    # 1) Embedding
    async with httpx.AsyncClient(timeout=30) as client:
        embed_resp = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": query},
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
        context = "\n\n---\n\n".join(ch["content"] for ch in chunks)[:6000]
        sources_info = [{"source": ch["source_name"], "similarity": round(float(ch["similarity"]), 3)} for ch in chunks]
        user_msg = f"Kontext:\n{context}\n\nFrage: {query}"
    else:
        user_msg = f"Es wurden keine relevanten Dokumente gefunden. Frage: {query}"

    # 4) LLM
    async with httpx.AsyncClient(timeout=90) as client:
        llm_resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": CHAT_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "stream": False,
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

    # Zusammenfassung im Hintergrund (nicht blockierend für Antwort)
    kernaussage, kernfrage = await _summarize_conversation(query, answer)

    # In conversations-Tabelle speichern
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO public.conversations
               (tenant_id, session_id, user_question, rag_answer,
                kernaussage, kernfrage, chunks_used, latency_ms, sources)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            uuid.UUID(tenant_id), session_id, query, answer,
            kernaussage or None, kernfrage or None,
            chunks_used, elapsed, json.dumps(sources_info),
        )
    except Exception:
        pass  # Speichern darf Antwort nicht blockieren

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
    session: SessionInfo = Depends(require_auth),
):
    db = await get_db()
    if session.is_superadmin():
        if tenant_id:
            rows = await db.fetch(
                """SELECT c.*, t.slug AS tenant_slug FROM public.conversations c
                   JOIN public.tenants t ON t.id = c.tenant_id
                   WHERE c.tenant_id = $1 ORDER BY c.created_at DESC LIMIT 200""",
                uuid.UUID(tenant_id),
            )
        else:
            rows = await db.fetch(
                """SELECT c.*, t.slug AS tenant_slug FROM public.conversations c
                   JOIN public.tenants t ON t.id = c.tenant_id
                   ORDER BY c.created_at DESC LIMIT 200""",
            )
    elif session.tenant_id:
        rows = await db.fetch(
            """SELECT c.*, t.slug AS tenant_slug FROM public.conversations c
               JOIN public.tenants t ON t.id = c.tenant_id
               WHERE c.tenant_id = $1 ORDER BY c.created_at DESC LIMIT 200""",
            uuid.UUID(session.tenant_id),
        )
    else:
        return []

    result = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        d["tenant_id"] = str(d["tenant_id"])
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
# Statische Dateien
# ══════════════════════════════════════════════════════════════════════════════
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html") as f:
        return f.read()
