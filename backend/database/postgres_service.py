import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict


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
# CONNECTION
# =========================
def create_connection():
    try:
        return psycopg2.connect(
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


# =========================
# INIT DB
# =========================
def init_db():
    conn = create_connection()
    if not conn:
        return

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
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            file_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,  -- later: VECTOR type (pgvector)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
        )
        """)

        conn.commit()

    except Exception as e:
        print(f"Init DB error: {e}")

    finally:
        conn.close()


# =========================
# INSERT FILE
# =========================
def insert_file(original_name: str, hashed_name: str, path: str, size: int = 0):
    conn = create_connection()
    if not conn:
        return

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
        print(f"Insert error: {e}")
    finally:
        conn.close()


# =========================
# UPDATE FILE STATUS
# =========================
def update_file_status(file_id: int, status: str):
    conn = create_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE files SET status = %s WHERE id = %s",
            (status, file_id)
        )
        conn.commit()
    except Exception as e:
        print(f"Update status error: {e}")
    finally:
        conn.close()


# =========================
# INSERT EMBEDDING
# =========================
def insert_embedding(document_id: int, content: str, embedding: List[float], chunk_index: int = 0):
    conn = create_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO document_chunks (file_id, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s)
        """, (document_id, chunk_index, content, str(embedding)))

        conn.commit()
    except Exception as e:
        print(f"Insert embedding error: {e}")
    finally:
        conn.close()


# =========================
# GET ALL FILES
# =========================
def get_all_files() -> List[Dict]:
    conn = create_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT f.id, f.original_name, f.hashed_name, f.path, f.size, f.created_at,
                   COUNT(dc.id) AS chunk_count
            FROM files f
            LEFT JOIN document_chunks dc ON dc.file_id = f.id
            GROUP BY f.id
            ORDER BY f.id DESC
        """)

        return cursor.fetchall()

    except Exception as e:
        print(f"Get all error: {e}")
        return []
    finally:
        conn.close()


# =========================
# GET FILE BY ID
# =========================
def get_file_by_id(file_id: int) -> Optional[Dict]:
    conn = create_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM files WHERE id = %s",
            (file_id,)
        )

        return cursor.fetchone()

    except Exception as e:
        print(f"Get by id error: {e}")
        return None
    finally:
        conn.close()


# =========================
# GET FILE BY NAME
# =========================
def get_file_by_name(name: str) -> Optional[Dict]:
    conn = create_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM files WHERE original_name = %s",
            (name,)
        )

        return cursor.fetchone()

    except Exception as e:
        print(f"Get by name error: {e}")
        return None
    finally:
        conn.close()


# =========================
# UPDATE FILE
# =========================
def update_file_db(file_id: int, new_name: str):
    conn = create_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE files
            SET original_name = %s
            WHERE id = %s
        """, (new_name, file_id))

        conn.commit()

    except Exception as e:
        print(f"Update error: {e}")
    finally:
        conn.close()


# =========================
# DELETE FILE
# =========================
def delete_file_db(file_id: int):
    conn = create_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM files WHERE id = %s",
            (file_id,)
        )

        conn.commit()

    except Exception as e:
        print(f"Delete error: {e}")
    finally:
        conn.close()