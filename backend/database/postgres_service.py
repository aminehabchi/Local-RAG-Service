import logging
import os
import psycopg2
import psycopg2.pool
import numpy as np
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor, execute_values
from typing import Optional, List, Dict, Tuple

_log = logging.getLogger(__name__)


# =========================
# DB CONFIG
# =========================
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "database": os.getenv("DB_NAME",     "rag_db"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
    "port":     int(os.getenv("DB_PORT", "5432")),
}


# =========================
# CONNECTION POOL (30 conns, opened once)
# =========================
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=30,
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            cursor_factory=RealDictCursor,
        )
    return _pool


_vector_ready = False


def _get_conn():
    global _vector_ready
    conn = _get_pool().getconn()
    if _vector_ready:
        register_vector(conn)
    return conn


def _ensure_vector(conn) -> None:
    """Call after the vector extension is confirmed to exist."""
    global _vector_ready
    register_vector(conn)
    _vector_ready = True


def _put_conn(conn) -> None:
    _get_pool().putconn(conn)


# =========================
# INIT DB
# =========================
def init_db():
    conn = _get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id SERIAL PRIMARY KEY,
            original_name TEXT NOT NULL UNIQUE,
            hashed_name TEXT NOT NULL UNIQUE,
            path TEXT NOT NULL,
            size BIGINT NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'processing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        ALTER TABLE files ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'processing'
        """)

        cursor.execute("""
        ALTER TABLE files ADD COLUMN IF NOT EXISTS chunk_count INTEGER NOT NULL DEFAULT 0
        """)

        cursor.execute("""
        ALTER TABLE files ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP
        """)

        cursor.execute("""
        ALTER TABLE files ADD COLUMN IF NOT EXISTS start_at TIMESTAMP
        """)

        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        _ensure_vector(conn)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS parent_chunks (
            id SERIAL PRIMARY KEY,
            file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            page_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS parent_chunks_file_id
        ON parent_chunks (file_id)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS child_chunks (
            id SERIAL PRIMARY KEY,
            file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            parent_id INTEGER NOT NULL REFERENCES parent_chunks(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(384),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS child_chunks_embedding_hnsw
        ON child_chunks USING hnsw (embedding vector_cosine_ops)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS child_chunks_file_id
        ON child_chunks (file_id, chunk_index)
        """)

        # Generated tsvector for full-text search on child content
        cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'child_chunks' AND column_name = 'content_tsv'
            ) THEN
                ALTER TABLE child_chunks
                ADD COLUMN content_tsv TSVECTOR
                    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
            END IF;
        END $$
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS child_chunks_tsv_gin
        ON child_chunks USING GIN (content_tsv)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'local',
            api_key TEXT,
            base_url TEXT,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"Init DB error: {e}")
    finally:
        _put_conn(conn)


# =========================
# MODELS
# =========================
def get_all_models() -> List[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM models ORDER BY created_at DESC")
        return cursor.fetchall()
    except Exception as e:
        print(f"Get models error: {e}")
        return []
    finally:
        _put_conn(conn)


def get_model_by_id(model_id: int) -> Optional[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM models WHERE id = %s", (model_id,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Get model error: {e}")
        return None
    finally:
        _put_conn(conn)


def insert_model(name: str, type: str, api_key: Optional[str], base_url: Optional[str], is_default: bool) -> Optional[int]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        if is_default:
            cursor.execute("UPDATE models SET is_default = FALSE")
        cursor.execute("""
            INSERT INTO models (name, type, api_key, base_url, is_default)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (name, type, api_key or None, base_url or None, is_default))
        model_id = cursor.fetchone()["id"]
        conn.commit()
        return model_id
    except Exception as e:
        conn.rollback()
        print(f"Insert model error: {e}")
        return None
    finally:
        _put_conn(conn)


def update_model(model_id: int, name: str, type: str, api_key: Optional[str], base_url: Optional[str], is_default: bool):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        if is_default:
            cursor.execute("UPDATE models SET is_default = FALSE WHERE id != %s", (model_id,))
        cursor.execute("""
            UPDATE models SET name=%s, type=%s, api_key=%s, base_url=%s,
                             is_default=%s, updated_at=NOW()
            WHERE id = %s
        """, (name, type, api_key or None, base_url or None, is_default, model_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Update model error: {e}")
    finally:
        _put_conn(conn)


def set_default_model(model_id: int):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE models SET is_default = FALSE")
        cursor.execute("UPDATE models SET is_default = TRUE, updated_at = NOW() WHERE id = %s", (model_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Set default error: {e}")
    finally:
        _put_conn(conn)


def delete_model(model_id: int):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM models WHERE id = %s", (model_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Delete model error: {e}")
    finally:
        _put_conn(conn)


# =========================
# MARK STALE PROCESSING FILES AS FAILED
# =========================
def fail_processing_files():
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE files SET status = 'failed' WHERE status = 'processing'"
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Fail processing files error: {e}")
    finally:
        _put_conn(conn)


# =========================
# INSERT FILE
# =========================
def insert_file(original_name: str, hashed_name: str, path: str, size: int = 0):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO files (original_name, hashed_name, path, size)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (original_name, hashed_name, path, size))
        file_id = cursor.fetchone()["id"]
        conn.commit()
        return file_id
    except Exception as e:
        conn.rollback()
        print(f"Insert error: {e}")
    finally:
        _put_conn(conn)


# =========================
# UPDATE FILE STATUS
# =========================
def update_file_status(file_id: int, status: str):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        if status == "ready":
            cursor.execute(
                "UPDATE files SET status = %s, ingested_at = NOW() WHERE id = %s",
                (status, file_id)
            )
        elif status == "processing":
            cursor.execute(
                "UPDATE files SET status = %s, start_at = NOW() WHERE id = %s",
                (status, file_id)
            )
        else:
            cursor.execute(
                "UPDATE files SET status = %s WHERE id = %s",
                (status, file_id)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Update status error: {e}")
    finally:
        _put_conn(conn)


# =========================
# UPDATE CHUNK COUNT
# =========================
def update_file_chunk_count(file_id: int, count: int):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE files SET chunk_count = %s WHERE id = %s",
            (count, file_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        _log.exception("Update chunk count error for file_id=%s", file_id)
    finally:
        _put_conn(conn)


# =========================
# BATCH INSERT PARENT + CHILD CHUNKS
# =========================
def batch_insert_chunks(file_id: int, chunks: List[Dict]) -> None:
    """
    Insert parent chunks first, then child chunks linked to their parent.
    chunks: list of records with content, parent_content, page_number, chunk_index, embedding.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()

        # Deduplicate parents preserving insertion order
        unique_parents: dict[str, int | None] = {}  # content -> page_number
        for c in chunks:
            if c["parent_content"] not in unique_parents:
                unique_parents[c["parent_content"]] = c.get("page_number")

        parent_rows = execute_values(
            cursor,
            "INSERT INTO parent_chunks (file_id, chunk_index, content, page_number) VALUES %s RETURNING id, content",
            [
                (file_id, idx, pc, pg)
                for idx, (pc, pg) in enumerate(unique_parents.items())
            ],
            fetch=True,
        )
        seen: dict[str, int] = {row["content"]: row["id"] for row in parent_rows}

        # Insert children linked to their parent
        cursor.executemany("""
            INSERT INTO child_chunks (file_id, parent_id, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s, %s)
        """, [
            (
                file_id,
                seen[c["parent_content"]],
                c["chunk_index"],
                c["content"],
                np.array(c["embedding"], dtype=np.float32) if c.get("embedding") is not None else None,
            )
            for c in chunks
        ])

        conn.commit()
    except Exception:
        conn.rollback()
        _log.exception("Batch insert chunks error for file_id=%s", file_id)
        raise
    finally:
        _put_conn(conn)


# =========================
# GET ALL FILES
# =========================
def get_all_files() -> List[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, original_name, hashed_name, path, size, status, chunk_count, created_at, start_at, ingested_at
            FROM files
            ORDER BY id DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        print(f"Get all error: {e}")
        return []
    finally:
        _put_conn(conn)


# =========================
# DELETE CHUNKS BY FILE ID
# =========================
def delete_chunks_by_file_id(file_id: int) -> None:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        # Deleting parent_chunks cascades to child_chunks
        cursor.execute("DELETE FROM parent_chunks WHERE file_id = %s", (file_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Delete chunks error: {e}")
    finally:
        _put_conn(conn)


# =========================
# RESET FILE FOR REINDEX
# =========================
def reset_file_for_reindex(file_id: int) -> None:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM parent_chunks WHERE file_id = %s", (file_id,))
        cursor.execute("""
            UPDATE files
            SET status = 'processing', chunk_count = 0, start_at = NOW(), ingested_at = NULL
            WHERE id = %s
        """, (file_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Reset for reindex error: {e}")
    finally:
        _put_conn(conn)


# =========================
# GET FILE BY ID
# =========================
def get_file_by_id(file_id: int) -> Optional[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE id = %s", (file_id,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Get by id error: {e}")
        return None
    finally:
        _put_conn(conn)


# =========================
# GET FILE BY NAME
# =========================
def get_file_by_name(name: str) -> Optional[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE original_name = %s", (name,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Get by name error: {e}")
        return None
    finally:
        _put_conn(conn)


# =========================
# UPDATE FILE
# =========================
def update_file_db(file_id: int, new_name: str):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE files SET original_name = %s WHERE id = %s",
            (new_name, file_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Update error: {e}")
    finally:
        _put_conn(conn)


# =========================
# GET CHUNKS BY FILE ID
# =========================
def get_chunks_by_file_id(file_id: int) -> List[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cc.id, cc.chunk_index, cc.content,
                   pc.content AS parent_content, pc.page_number
            FROM child_chunks cc
            JOIN parent_chunks pc ON pc.id = cc.parent_id
            WHERE cc.file_id = %s
            ORDER BY cc.chunk_index ASC
        """, (file_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Get chunks error: {e}")
        return []
    finally:
        _put_conn(conn)


# =========================
# DELETE FILE
# =========================
def delete_file_db(file_id: int):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Delete error: {e}")
    finally:
        _put_conn(conn)
