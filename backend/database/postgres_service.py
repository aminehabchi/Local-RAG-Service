import psycopg2
import psycopg2.pool
import numpy as np
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Tuple


# =========================
# DB CONFIG
# =========================
DB_CONFIG = {
    "host": "localhost",
    "database": "rag_db",
    "user": "postgres",
    "password": "postgres",
    "port": 5432
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

        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        _ensure_vector(conn)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            file_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(384),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
        )
        """)

        # Migrate existing TEXT column to vector(384)
        cursor.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_chunks'
                AND column_name = 'embedding'
                AND data_type = 'text'
            ) THEN
                ALTER TABLE document_chunks
                ALTER COLUMN embedding TYPE vector(384)
                USING embedding::vector;
            END IF;
        END $$
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
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
        print(f"Update chunk count error: {e}")
    finally:
        _put_conn(conn)


# =========================
# BATCH INSERT EMBEDDINGS
# Single connection for all chunks — much faster than one conn per chunk
# =========================
def batch_insert_embeddings(file_id: int, items: List[Tuple[int, str, List[float]]]) -> None:
    """items: list of (chunk_index, content, embedding)"""
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO document_chunks (file_id, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s)
        """, [(file_id, idx, content, np.array(emb, dtype=np.float32)) for idx, content, emb in items])
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Batch insert error: {e}")
        raise
    finally:
        _put_conn(conn)


# =========================
# INSERT EMBEDDING (single — kept for compatibility)
# =========================
def insert_embedding(document_id: int, content: str, embedding: List[float], chunk_index: int = 0):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO document_chunks (file_id, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s)
        """, (document_id, chunk_index, content, np.array(embedding, dtype=np.float32)))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Insert embedding error: {e}")
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
            SELECT id, original_name, hashed_name, path, size, status, chunk_count, created_at, ingested_at
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
            SELECT id, chunk_index, content
            FROM document_chunks
            WHERE file_id = %s
            ORDER BY chunk_index ASC
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
