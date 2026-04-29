import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import Json, RealDictCursor
except Exception:  # pragma: no cover - optional dependency in local dev
    psycopg2 = None
    Json = None
    RealDictCursor = None

try:
    import vertexai
    from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
except Exception:  # pragma: no cover - optional dependency in local dev
    vertexai = None
    TextEmbeddingInput = None
    TextEmbeddingModel = None

try:
    from google.cloud import storage
except Exception:  # pragma: no cover - optional dependency in local dev
    storage = None

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - optional dependency in local dev
    BeautifulSoup = None

try:
    from PyPDF2 import PdfReader
except Exception:  # pragma: no cover - optional dependency in local dev
    PdfReader = None

RAG_DATABASE_URL = str(os.getenv("RAG_DATABASE_URL", "")).strip()
RAG_GCS_BUCKET = str(os.getenv("RAG_GCS_BUCKET", "")).strip()
RAG_GCS_PREFIX = str(os.getenv("RAG_GCS_PREFIX", "knowledge").strip("/") or "knowledge")
RAG_GCP_PROJECT = str(
    os.getenv("RAG_GCP_PROJECT")
    or os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("GCP_PROJECT")
    or ""
).strip()
RAG_GCP_LOCATION = str(
    os.getenv("RAG_GCP_LOCATION")
    or os.getenv("VERTEX_LOCATION")
    or os.getenv("GOOGLE_CLOUD_LOCATION")
    or "us-central1"
).strip()
RAG_EMBEDDING_MODEL = str(os.getenv("RAG_EMBEDDING_MODEL", "gemini-embedding-001")).strip() or "gemini-embedding-001"
RAG_VECTOR_DIM = 768
_raw_embedding_dim = max(128, min(3072, int(os.getenv("RAG_EMBEDDING_DIM", "768") or 768)))
if _raw_embedding_dim != RAG_VECTOR_DIM:
    print(json.dumps({
        "event": "rag_embedding_dim_override_ignored",
        "requested_dim": _raw_embedding_dim,
        "effective_dim": RAG_VECTOR_DIM,
    }))
RAG_EMBEDDING_DIM = RAG_VECTOR_DIM
RAG_CHUNK_WORDS = max(
    200,
    min(
        4000,
        int(os.getenv("RAG_CHUNK_WORDS", os.getenv("RAG_CHUNK_TOKENS", "800")) or 800),
    ),
)
RAG_CHUNK_OVERLAP_WORDS = max(
    0,
    min(
        500,
        int(os.getenv("RAG_CHUNK_OVERLAP_WORDS", os.getenv("RAG_CHUNK_OVERLAP", "100")) or 100),
    ),
)

_SCHEMA_READY = False
_EMBED_MODEL = None

DEFAULT_RETRIEVAL_PROFILES = {
    "ppc-specialist": {
        "enabled": True,
        "top_k": 4,
        "min_score": 0.45,
        "hybrid_weight": 0.0,
        "rerank_enabled": False,
        "scope_mode": "filtered",
        "embedding_model": RAG_EMBEDDING_MODEL,
    },
    "ceo-strategy": {
        "enabled": True,
        "top_k": 4,
        "min_score": 0.42,
        "hybrid_weight": 0.0,
        "rerank_enabled": False,
        "scope_mode": "all",
        "embedding_model": RAG_EMBEDDING_MODEL,
    },
    "coo-operations": {
        "enabled": True,
        "top_k": 4,
        "min_score": 0.42,
        "hybrid_weight": 0.0,
        "rerank_enabled": False,
        "scope_mode": "all",
        "embedding_model": RAG_EMBEDDING_MODEL,
    },
    "life-coach": {
        "enabled": False,
        "top_k": 0,
        "min_score": 1.0,
        "hybrid_weight": 0.0,
        "rerank_enabled": False,
        "scope_mode": "none",
        "embedding_model": RAG_EMBEDDING_MODEL,
    },
}

SCHEMA_STATEMENTS = [
    """
    CREATE EXTENSION IF NOT EXISTS vector
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_bases (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (workspace_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collections (
        id TEXT PRIMARY KEY,
        kb_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        client_slug TEXT,
        description TEXT DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (kb_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        source_type TEXT NOT NULL,
        source_uri TEXT,
        filename TEXT NOT NULL,
        mime_type TEXT,
        checksum_sha256 TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_versions (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        gcs_path TEXT,
        size_bytes BIGINT DEFAULT 0,
        extracted_text_length INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (document_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        id TEXT PRIMARY KEY,
        document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        token_count INTEGER DEFAULT 0, -- NOTE: stores word count, not LLM tokens; rename in v2
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (document_version_id, chunk_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunk_embeddings (
        id TEXT PRIMARY KEY,
        chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
        embedding_model TEXT NOT NULL,
        embedding_dim INTEGER NOT NULL,
        embedding vector(768) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (chunk_id, embedding_model)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS retrieval_runs (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        client_id INTEGER,
        workspace_id TEXT,
        agent_slug TEXT NOT NULL,
        query TEXT NOT NULL,
        embedding_model TEXT,
        chunks_returned INTEGER DEFAULT 0,
        latency_ms INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        meta_json JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS retrieval_profiles (
        id TEXT PRIMARY KEY,
        agent_slug TEXT NOT NULL UNIQUE,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        top_k INTEGER NOT NULL DEFAULT 4,
        min_score DOUBLE PRECISION NOT NULL DEFAULT 0.45,
        hybrid_weight DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        rerank_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        scope_mode TEXT NOT NULL DEFAULT 'all',
        embedding_model TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS retrieval_profile_collections (
        profile_id TEXT NOT NULL REFERENCES retrieval_profiles(id) ON DELETE CASCADE,
        collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        PRIMARY KEY (profile_id, collection_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_bases_workspace ON knowledge_bases (workspace_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_collections_kb_client ON collections (kb_id, client_slug)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documents_collection_status ON documents (collection_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions (document_id, version DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chunks_version ON chunks (document_version_id, chunk_index)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings (embedding_model, chunk_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_retrieval_runs_user_created ON retrieval_runs (user_id, created_at DESC)
    """,
]


def rag_config():
    return {
        "enabled": bool(RAG_DATABASE_URL),
        "database_url": bool(RAG_DATABASE_URL),
        "gcs_bucket": RAG_GCS_BUCKET,
        "embedding_model": RAG_EMBEDDING_MODEL,
        "embedding_dim": int(RAG_EMBEDDING_DIM),
        "chunk_words": int(RAG_CHUNK_WORDS),
        "chunk_overlap_words": int(RAG_CHUNK_OVERLAP_WORDS),
        "project": RAG_GCP_PROJECT,
        "location": RAG_GCP_LOCATION,
    }


def rag_enabled():
    return bool(RAG_DATABASE_URL and psycopg2 is not None)


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def slugify_text(value):
    txt = str(value or "").strip().lower()
    txt = re.sub(r"[^a-z0-9]+", "-", txt)
    txt = re.sub(r"-{2,}", "-", txt).strip("-")
    return txt or "default"


def _vector_literal(values):
    vals = [float(v or 0.0) for v in (values or [])]
    return "[" + ",".join(f"{v:.10f}".rstrip("0").rstrip(".") for v in vals) + "]"


def _get_conn():
    if not RAG_DATABASE_URL:
        raise RuntimeError("rag_database_url_missing")
    if psycopg2 is None:
        raise RuntimeError("psycopg2_not_installed")
    return psycopg2.connect(RAG_DATABASE_URL, cursor_factory=RealDictCursor)


def ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY or not rag_enabled():
        return bool(_SCHEMA_READY)
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                for stmt in SCHEMA_STATEMENTS:
                    cur.execute(stmt)
                _ensure_chunk_embeddings_v1(cur)
                _seed_default_profiles(cur)
        _SCHEMA_READY = True
        return True
    finally:
        conn.close()


def _ensure_chunk_embeddings_v1(cur):
    cur.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS type_name
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'chunk_embeddings'
          AND a.attname = 'embedding'
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND n.nspname = current_schema()
        LIMIT 1
        """
    )
    row = cur.fetchone() or {}
    current_type = str(row.get("type_name") or "").strip().lower()
    target_type = f"vector({RAG_VECTOR_DIM})"
    if current_type and current_type != target_type:
        cur.execute("SELECT COUNT(*) AS total_rows FROM chunk_embeddings")
        total_rows = int((cur.fetchone() or {}).get("total_rows") or 0)
        if total_rows > 0:
            cur.execute(
                "SELECT COUNT(*) AS bad_rows FROM chunk_embeddings WHERE vector_dims(embedding) <> %s",
                (RAG_VECTOR_DIM,),
            )
            bad_rows = int((cur.fetchone() or {}).get("bad_rows") or 0)
            if bad_rows > 0:
                raise RuntimeError(f"rag_embedding_dim_mismatch:{bad_rows}")
        cur.execute(
            f"""
            ALTER TABLE chunk_embeddings
            ALTER COLUMN embedding TYPE vector({RAG_VECTOR_DIM})
            USING embedding::vector({RAG_VECTOR_DIM})
            """
        )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_cosine
        ON chunk_embeddings
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def _seed_default_profiles(cur):
    for agent_slug, cfg in DEFAULT_RETRIEVAL_PROFILES.items():
        cur.execute(
            """
            INSERT INTO retrieval_profiles (
                id, agent_slug, enabled, top_k, min_score, hybrid_weight,
                rerank_enabled, scope_mode, embedding_model
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (agent_slug) DO NOTHING
            """,
            (
                _uuid("rprof"),
                agent_slug,
                bool(cfg.get("enabled")),
                int(cfg.get("top_k") or 4),
                float(cfg.get("min_score") or 0.45),
                float(cfg.get("hybrid_weight") or 0.0),
                bool(cfg.get("rerank_enabled")),
                str(cfg.get("scope_mode") or "all"),
                str(cfg.get("embedding_model") or RAG_EMBEDDING_MODEL),
            ),
        )
    _sync_default_profile_links(cur)


def _sync_default_profile_links(cur):
    cur.execute("SELECT id, name FROM collections")
    collections = cur.fetchall() or []
    ppc_collection_ids = []
    for row in collections:
        name = str(row.get("name") or "").strip().lower()
        if "ppc" in name or "mcc" in name or "ads" in name:
            ppc_collection_ids.append(str(row["id"]))
    if not ppc_collection_ids:
        return
    cur.execute("SELECT id FROM retrieval_profiles WHERE agent_slug = %s LIMIT 1", ("ppc-specialist",))
    prof = cur.fetchone()
    if not prof:
        return
    profile_id = str(prof["id"])
    for collection_id in ppc_collection_ids:
        cur.execute(
            """
            INSERT INTO retrieval_profile_collections (profile_id, collection_id)
            VALUES (%s, %s)
            ON CONFLICT (profile_id, collection_id) DO NOTHING
            """,
            (profile_id, collection_id),
        )


def _guess_mime_type(filename, explicit_mime=None):
    mime = str(explicit_mime or "").strip().lower()
    if mime:
        return mime
    guessed, _enc = mimetypes.guess_type(str(filename or ""))
    return str(guessed or "application/octet-stream").lower()


def _extract_text_units(filename, mime_type, file_bytes):
    mime = _guess_mime_type(filename, mime_type)
    name = str(filename or "").strip().lower()
    data = file_bytes if isinstance(file_bytes, (bytes, bytearray)) else bytes(file_bytes or b"")
    if not data:
        raise ValueError("empty_file")

    if mime == "application/pdf" or name.endswith(".pdf"):
        if PdfReader is None:
            raise RuntimeError("PyPDF2_not_installed")
        reader = PdfReader(io.BytesIO(data))
        units = []
        for idx, page in enumerate(reader.pages, start=1):
            text = str(page.extract_text() or "").strip()
            if text:
                units.append({
                    "text": text,
                    "page_start": idx,
                    "page_end": idx,
                })
        return units

    if mime in ("text/plain", "text/markdown") or name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="ignore")
        return [{"text": text, "page_start": None, "page_end": None}]

    if mime == "text/csv" or name.endswith(".csv"):
        decoded = data.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(decoded))
        rows = [" | ".join([str(cell or "").strip() for cell in row if str(cell or "").strip()]) for row in reader]
        text = "\n".join([row for row in rows if row])
        return [{"text": text, "page_start": None, "page_end": None}]

    if mime == "text/html" or name.endswith((".html", ".htm")):
        decoded = data.decode("utf-8", errors="ignore")
        if BeautifulSoup is not None:
            text = BeautifulSoup(decoded, "html.parser").get_text("\n")
        else:
            text = re.sub(r"<[^>]+>", " ", decoded)
        return [{"text": text, "page_start": None, "page_end": None}]

    raise ValueError(f"unsupported_mime:{mime}")


def _normalize_text(text):
    txt = str(text or "")
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    return txt.strip()


def _chunk_units(units, chunk_words=RAG_CHUNK_WORDS, overlap_words=RAG_CHUNK_OVERLAP_WORDS):
    size = max(1, int(chunk_words or RAG_CHUNK_WORDS))
    overlap = max(0, min(size - 1, int(overlap_words or 0)))
    out = []
    chunk_index = 0
    for unit in units or []:
        text = _normalize_text(unit.get("text"))
        if not text:
            continue
        words = text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(len(words), start + size)
            chunk_words = words[start:end]
            content = " ".join(chunk_words).strip()
            if content:
                chunk_index += 1
                out.append({
                    "chunk_index": chunk_index,
                    "content": content,
                    "token_count": len(chunk_words),
                    "metadata": {
                        "page_start": unit.get("page_start"),
                        "page_end": unit.get("page_end"),
                    },
                })
            if end >= len(words):
                break
            start = max(start + 1, end - overlap)
    return out


def _get_embedding_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    if vertexai is None or TextEmbeddingModel is None:
        raise RuntimeError("vertex_ai_embedding_not_installed")
    if not RAG_GCP_PROJECT:
        raise RuntimeError("rag_gcp_project_missing")
    vertexai.init(project=RAG_GCP_PROJECT, location=RAG_GCP_LOCATION)
    _EMBED_MODEL = TextEmbeddingModel.from_pretrained(RAG_EMBEDDING_MODEL)
    return _EMBED_MODEL


def embed_texts(texts, task="RETRIEVAL_DOCUMENT"):
    if not texts:
        return []
    model = _get_embedding_model()
    kwargs = {}
    if RAG_EMBEDDING_DIM:
        kwargs["output_dimensionality"] = int(RAG_EMBEDDING_DIM)
    vectors = []
    for idx, text in enumerate(texts or [], start=1):
        clean = _normalize_text(text)[:20000]
        payload = [TextEmbeddingInput(clean, task)] if TextEmbeddingInput is not None else [clean]
        last_error = None
        for attempt in range(1, 4):
            started = time.perf_counter()
            try:
                rows = model.get_embeddings(payload, **kwargs)
                latency_ms = int((time.perf_counter() - started) * 1000)
                print(json.dumps({
                    "event": "rag_embedding_request",
                    "index": idx,
                    "attempt": attempt,
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "model": RAG_EMBEDDING_MODEL,
                }))
                item = (rows or [None])[0]
                values = list(getattr(item, "values", []) or [])
                if len(values) != RAG_VECTOR_DIM:
                    raise RuntimeError(f"unexpected_embedding_dim:{len(values)}")
                vectors.append(values)
                last_error = None
                break
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                last_error = exc
                print(json.dumps({
                    "event": "rag_embedding_request",
                    "index": idx,
                    "attempt": attempt,
                    "status": "error",
                    "latency_ms": latency_ms,
                    "model": RAG_EMBEDDING_MODEL,
                    "error": str(exc)[:240],
                }))
                if attempt >= 3:
                    break
                time.sleep(0.5 * (2 ** (attempt - 1)))
        if last_error is not None:
            raise last_error
    return vectors


def _gcs_client():
    if storage is None:
        raise RuntimeError("google_cloud_storage_not_installed")
    if not RAG_GCS_BUCKET:
        return None
    return storage.Client(project=RAG_GCP_PROJECT or None)


def upload_to_gcs(file_bytes, object_name, content_type=None):
    if not RAG_GCS_BUCKET:
        return None
    client = _gcs_client()
    bucket = client.bucket(RAG_GCS_BUCKET)
    blob = bucket.blob(object_name)
    blob.upload_from_string(file_bytes, content_type=content_type or "application/octet-stream")
    return f"gs://{RAG_GCS_BUCKET}/{object_name}"


def upsert_knowledge_base(cur, workspace_id, name, description=""):
    workspace = str(workspace_id or "").strip().lower() or "business"
    clean_name = str(name or "").strip() or "Default Knowledge Base"
    cur.execute(
        "SELECT * FROM knowledge_bases WHERE workspace_id = %s AND name = %s LIMIT 1",
        (workspace, clean_name),
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    kb_id = _uuid("kb")
    cur.execute(
        """
        INSERT INTO knowledge_bases (id, workspace_id, name, description)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (kb_id, workspace, clean_name, str(description or "").strip()),
    )
    return dict(cur.fetchone())


def upsert_collection(cur, kb_id, name, client_slug=None, description=""):
    clean_name = str(name or "").strip() or "General"
    clean_client_slug = str(client_slug or "").strip().lower() or None
    cur.execute(
        "SELECT * FROM collections WHERE kb_id = %s AND name = %s LIMIT 1",
        (str(kb_id), clean_name),
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    collection_id = _uuid("col")
    cur.execute(
        """
        INSERT INTO collections (id, kb_id, name, client_slug, description)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (collection_id, str(kb_id), clean_name, clean_client_slug, str(description or "").strip()),
    )
    row = dict(cur.fetchone())
    _sync_default_profile_links(cur)
    return row


def create_collection(workspace_id, kb_name, collection_name, client_slug=None, description=""):
    ensure_schema()
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                kb = upsert_knowledge_base(cur, workspace_id, kb_name, description="")
                collection = upsert_collection(cur, kb["id"], collection_name, client_slug=client_slug, description=description)
                return {"knowledge_base": kb, "collection": collection}
    finally:
        conn.close()


def list_collections(workspace_id=None):
    if not rag_enabled():
        return []
    ensure_schema()
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            params = []
            sql = """
                SELECT c.*, kb.workspace_id, kb.name AS kb_name
                FROM collections c
                JOIN knowledge_bases kb ON kb.id = c.kb_id
            """
            if workspace_id:
                sql += " WHERE kb.workspace_id = %s"
                params.append(str(workspace_id).strip().lower())
            sql += " ORDER BY kb.name ASC, c.name ASC"
            cur.execute(sql, tuple(params))
            return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def list_documents(workspace_id=None, collection_id=None, client_slug=None):
    if not rag_enabled():
        return []
    ensure_schema()
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            params = []
            sql = """
                SELECT
                    d.id,
                    d.collection_id,
                    d.source_type,
                    d.source_uri,
                    d.filename,
                    d.mime_type,
                    d.checksum_sha256,
                    d.status,
                    d.created_at,
                    d.updated_at,
                    c.name AS collection_name,
                    c.client_slug,
                    kb.workspace_id,
                    kb.name AS kb_name,
                    COALESCE(MAX(dv.version), 0) AS latest_version,
                    COALESCE(SUM(CASE WHEN dv.id IS NOT NULL THEN 1 ELSE 0 END), 0) AS version_count,
                    COALESCE(SUM(CASE WHEN ch.id IS NOT NULL THEN 1 ELSE 0 END), 0) AS chunk_count
                FROM documents d
                JOIN collections c ON c.id = d.collection_id
                JOIN knowledge_bases kb ON kb.id = c.kb_id
                LEFT JOIN document_versions dv ON dv.document_id = d.id
                LEFT JOIN chunks ch ON ch.document_version_id = dv.id
                WHERE 1 = 1
            """
            if workspace_id:
                sql += " AND kb.workspace_id = %s"
                params.append(str(workspace_id).strip().lower())
            if collection_id:
                sql += " AND d.collection_id = %s"
                params.append(str(collection_id))
            if client_slug:
                sql += " AND COALESCE(c.client_slug, '') IN ('', %s)"
                params.append(str(client_slug).strip().lower())
            sql += """
                GROUP BY d.id, c.name, c.client_slug, kb.workspace_id, kb.name
                ORDER BY d.created_at DESC
            """
            cur.execute(sql, tuple(params))
            return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def ingest_bytes(
    *,
    workspace_id,
    filename,
    file_bytes,
    mime_type=None,
    collection_id=None,
    knowledge_base_name=None,
    collection_name=None,
    client_slug=None,
    source_type="upload",
    source_uri=None,
):
    if not rag_enabled():
        raise RuntimeError("rag_database_not_configured")
    ensure_schema()

    clean_workspace = str(workspace_id or "").strip().lower() or "business"
    clean_filename = str(filename or "").strip() or "document.bin"
    clean_client_slug = str(client_slug or "").strip().lower() or None
    mime = _guess_mime_type(clean_filename, mime_type)
    data = file_bytes if isinstance(file_bytes, (bytes, bytearray)) else bytes(file_bytes or b"")
    if not data:
        raise ValueError("empty_file")
    checksum = hashlib.sha256(data).hexdigest()

    extracted_units = _extract_text_units(clean_filename, mime, data)
    chunks = _chunk_units(
        extracted_units,
        chunk_words=RAG_CHUNK_WORDS,
        overlap_words=RAG_CHUNK_OVERLAP_WORDS,
    )
    if not chunks:
        raise RuntimeError("no_chunks_extracted")
    embeddings = embed_texts([c["content"] for c in chunks], task="RETRIEVAL_DOCUMENT")
    if len(embeddings) != len(chunks):
        raise RuntimeError("embedding_count_mismatch")

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if collection_id:
                    cur.execute(
                        """
                        SELECT c.*, kb.workspace_id
                        FROM collections c
                        JOIN knowledge_bases kb ON kb.id = c.kb_id
                        WHERE c.id = %s
                        LIMIT 1
                        """,
                        (str(collection_id),),
                    )
                    collection = cur.fetchone()
                    if not collection:
                        raise RuntimeError("collection_not_found")
                    collection = dict(collection)
                else:
                    kb = upsert_knowledge_base(
                        cur,
                        clean_workspace,
                        knowledge_base_name or f"{clean_workspace.title()} Knowledge Base",
                        description="",
                    )
                    collection = upsert_collection(
                        cur,
                        kb["id"],
                        collection_name or (clean_client_slug.title().replace("-", " ") if clean_client_slug else "General"),
                        client_slug=clean_client_slug,
                        description="",
                    )

                cur.execute(
                    """
                    SELECT * FROM documents
                    WHERE collection_id = %s AND filename = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (str(collection["id"]), clean_filename),
                )
                document = cur.fetchone()
                if document:
                    document = dict(document)
                    document_id = str(document["id"])
                    cur.execute("SELECT COALESCE(MAX(version), 0) AS max_version FROM document_versions WHERE document_id = %s", (document_id,))
                    version_number = int((cur.fetchone() or {}).get("max_version") or 0) + 1
                    cur.execute(
                        """
                        UPDATE documents
                        SET source_type = %s, source_uri = %s, mime_type = %s, checksum_sha256 = %s, status = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (source_type, source_uri or clean_filename, mime, checksum, "processing", document_id),
                    )
                else:
                    document_id = _uuid("doc")
                    version_number = 1
                    cur.execute(
                        """
                        INSERT INTO documents (
                            id, collection_id, source_type, source_uri, filename, mime_type, checksum_sha256, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            document_id,
                            str(collection["id"]),
                            source_type,
                            source_uri or clean_filename,
                            clean_filename,
                            mime,
                            checksum,
                            "processing",
                        ),
                    )

                gcs_path = None
                if RAG_GCS_BUCKET:
                    object_name = f"{RAG_GCS_PREFIX}/{clean_workspace}/{collection['id']}/{document_id}/v{version_number}/{clean_filename}"
                    gcs_path = upload_to_gcs(data, object_name, content_type=mime)

                version_id = _uuid("dver")
                extracted_len = sum(len(_normalize_text(unit.get("text"))) for unit in extracted_units)
                cur.execute(
                    """
                    INSERT INTO document_versions (
                        id, document_id, version, gcs_path, size_bytes, extracted_text_length
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        version_id,
                        document_id,
                        int(version_number),
                        gcs_path,
                        int(len(data)),
                        int(extracted_len),
                    ),
                )

                for chunk, vector in zip(chunks, embeddings):
                    chunk_id = _uuid("chunk")
                    metadata = dict(chunk.get("metadata") or {})
                    metadata.update({
                        "filename": clean_filename,
                        "source_type": source_type,
                        "source_uri": source_uri or clean_filename,
                    })
                    cur.execute(
                        """
                        INSERT INTO chunks (
                            id, document_version_id, chunk_index, content, token_count, metadata_json
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            chunk_id,
                            version_id,
                            int(chunk["chunk_index"]),
                            str(chunk["content"]),
                            int(chunk["token_count"]),
                            Json(metadata) if Json is not None else json.dumps(metadata),
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO chunk_embeddings (
                            id, chunk_id, embedding_model, embedding_dim, embedding
                        ) VALUES (%s, %s, %s, %s, %s::vector)
                        """,
                        (
                            _uuid("emb"),
                            chunk_id,
                            RAG_EMBEDDING_MODEL,
                            int(len(vector)),
                            _vector_literal(vector),
                        ),
                    )

                cur.execute(
                    "UPDATE documents SET status = %s, updated_at = NOW() WHERE id = %s",
                    ("ready", document_id),
                )

                return {
                    "document_id": document_id,
                    "version_id": version_id,
                    "collection_id": str(collection["id"]),
                    "workspace_id": clean_workspace,
                    "filename": clean_filename,
                    "mime_type": mime,
                    "checksum_sha256": checksum,
                    "chunk_count": len(chunks),
                    "embedding_model": RAG_EMBEDDING_MODEL,
                    "embedding_dim": int(len(embeddings[0]) if embeddings else 0),
                    "gcs_path": gcs_path,
                    "status": "ready",
                }
    except Exception:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE documents
                        SET status = %s, updated_at = NOW()
                        WHERE collection_id = %s AND filename = %s
                        """,
                        ("failed", str(collection_id) if collection_id else None, clean_filename),
                    )
        except Exception:
            pass
        raise
    finally:
        conn.close()


def ingest_local_path(path, workspace_id, knowledge_base_name=None, collection_name=None, client_slug=None):
    src = Path(path).expanduser().resolve()
    data = src.read_bytes()
    return ingest_bytes(
        workspace_id=workspace_id,
        filename=src.name,
        file_bytes=data,
        mime_type=_guess_mime_type(src.name),
        knowledge_base_name=knowledge_base_name,
        collection_name=collection_name,
        client_slug=client_slug,
        source_type="local_path",
        source_uri=str(src),
    )


def _load_profile(cur, agent_slug):
    agent = str(agent_slug or "").strip().lower()
    cur.execute("SELECT * FROM retrieval_profiles WHERE agent_slug = %s LIMIT 1", (agent,))
    row = cur.fetchone()
    if row:
        return dict(row)
    cfg = DEFAULT_RETRIEVAL_PROFILES.get(agent)
    if not cfg:
        return None
    cur.execute(
        """
        INSERT INTO retrieval_profiles (
            id, agent_slug, enabled, top_k, min_score, hybrid_weight,
            rerank_enabled, scope_mode, embedding_model
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (agent_slug) DO NOTHING
        """,
        (
            _uuid("rprof"),
            agent,
            bool(cfg.get("enabled")),
            int(cfg.get("top_k") or 4),
            float(cfg.get("min_score") or 0.45),
            float(cfg.get("hybrid_weight") or 0.0),
            bool(cfg.get("rerank_enabled")),
            str(cfg.get("scope_mode") or "all"),
            str(cfg.get("embedding_model") or RAG_EMBEDDING_MODEL),
        ),
    )
    cur.execute("SELECT * FROM retrieval_profiles WHERE agent_slug = %s LIMIT 1", (agent,))
    row = cur.fetchone()
    return dict(row) if row else None


def _profile_collection_ids(cur, profile_id):
    cur.execute(
        "SELECT collection_id FROM retrieval_profile_collections WHERE profile_id = %s ORDER BY collection_id ASC",
        (str(profile_id),),
    )
    return [str(r["collection_id"]) for r in (cur.fetchall() or [])]


def semantic_search(query, *, workspace_id=None, agent_slug=None, user_id=None, client_id=None, client_slug=None, top_k=None):
    if not rag_enabled():
        return []
    ensure_schema()
    text = _normalize_text(query)
    if not text:
        return []

    started = time.time()
    conn = _get_conn()
    rows = []
    profile = None
    embedding_model = RAG_EMBEDDING_MODEL
    try:
        with conn:
            with conn.cursor() as cur:
                profile = _load_profile(cur, agent_slug or "")
                if profile and not bool(profile.get("enabled")):
                    return []
                scope_mode = str((profile or {}).get("scope_mode") or "all").strip().lower()
                if scope_mode == "none":
                    return []
                embedding_model = str((profile or {}).get("embedding_model") or RAG_EMBEDDING_MODEL)
                query_vector = embed_texts([text], task="RETRIEVAL_QUERY")[0]
                vector_literal = _vector_literal(query_vector)
                limit = max(1, min(int(top_k or (profile or {}).get("top_k") or 4), 12))
                min_score = float((profile or {}).get("min_score") or 0.0)
                params = [embedding_model, vector_literal, vector_literal]
                sql = """
                    SELECT
                        ch.id AS chunk_id,
                        ch.content,
                        ch.token_count,
                        ch.metadata_json,
                        d.filename,
                        d.source_uri,
                        d.mime_type,
                        d.id AS document_id,
                        dv.id AS document_version_id,
                        c.id AS collection_id,
                        c.name AS collection_name,
                        c.client_slug,
                        kb.id AS kb_id,
                        kb.name AS kb_name,
                        kb.workspace_id,
                        1 - (ce.embedding <=> %s::vector) AS score
                    FROM chunk_embeddings ce
                    JOIN chunks ch ON ch.id = ce.chunk_id
                    JOIN document_versions dv ON dv.id = ch.document_version_id
                    JOIN documents d ON d.id = dv.document_id
                    JOIN collections c ON c.id = d.collection_id
                    JOIN knowledge_bases kb ON kb.id = c.kb_id
                    WHERE ce.embedding_model = %s
                """
                # Reorder params for readability with psycopg2 placeholders below.
                params = [vector_literal, embedding_model]
                if workspace_id:
                    sql += " AND kb.workspace_id = %s"
                    params.append(str(workspace_id).strip().lower())
                if client_slug:
                    sql += " AND COALESCE(c.client_slug, '') IN ('', %s)"
                    params.append(str(client_slug).strip().lower())
                collection_ids = _profile_collection_ids(cur, (profile or {}).get("id")) if profile else []
                if collection_ids and scope_mode == "filtered":
                    sql += " AND c.id = ANY(%s)"
                    params.append(collection_ids)
                sql += " ORDER BY ce.embedding <=> %s::vector LIMIT %s"
                params.extend([vector_literal, limit * 3])
                cur.execute(sql, tuple(params))
                fetched = cur.fetchall() or []
                for row in fetched:
                    item = dict(row)
                    item["score"] = float(item.get("score") or 0.0)
                    if item["score"] < min_score:
                        continue
                    meta = item.get("metadata_json") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    item["metadata_json"] = meta
                    rows.append(item)
                    if len(rows) >= limit:
                        break

                latency_ms = int(round((time.time() - started) * 1000.0))
                cur.execute(
                    """
                    INSERT INTO retrieval_runs (
                        id, user_id, client_id, workspace_id, agent_slug, query,
                        embedding_model, chunks_returned, latency_ms, meta_json
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        _uuid("retr"),
                        int(user_id) if user_id is not None else None,
                        int(client_id) if client_id is not None else None,
                        str(workspace_id).strip().lower() if workspace_id else None,
                        str(agent_slug or "").strip().lower() or "unknown",
                        text[:4000],
                        embedding_model,
                        len(rows),
                        latency_ms,
                        Json({
                            "client_slug": str(client_slug or "").strip().lower() or None,
                            "top_k": limit,
                            "min_score": min_score,
                        }) if Json is not None else json.dumps({
                            "client_slug": str(client_slug or "").strip().lower() or None,
                            "top_k": limit,
                            "min_score": min_score,
                        }),
                    ),
                )
        return rows
    finally:
        conn.close()


def format_retrieval_excerpts(rows, max_chars_per_chunk=900):
    excerpts = []
    for idx, row in enumerate(rows or [], start=1):
        meta = row.get("metadata_json") or {}
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        page_txt = ""
        if page_start and page_end and page_start != page_end:
            page_txt = f" pp. {page_start}-{page_end}"
        elif page_start:
            page_txt = f" p. {page_start}"
        header = f"[KB {idx}] {row.get('filename') or row.get('collection_name') or 'Document'}{page_txt}"
        content = _normalize_text(row.get("content"))[:max_chars_per_chunk]
        excerpts.append(f"{header}\n{content}")
    return "\n\n".join(excerpts).strip()


def format_retrieval_citations(rows):
    citations = []
    for row in rows or []:
        meta = row.get("metadata_json") or {}
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        page_txt = ""
        if page_start and page_end and page_start != page_end:
            page_txt = f", pp. {page_start}-{page_end}"
        elif page_start:
            page_txt = f", p. {page_start}"
        score = float(row.get("score") or 0.0)
        citations.append(
            f"- {row.get('filename') or 'Document'} ({row.get('collection_name') or 'Collection'}{page_txt}, score {score:.2f})"
        )
    return "\n".join(citations)
