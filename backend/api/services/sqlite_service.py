# sqlite service for managing the SQLite database
import sqlite3
from sqlite3 import Error
from typing import Optional, List, Dict

from pathlib import Path as _Path
DB_PATH = str(_Path(__file__).parent.parent.parent / "storage" / "sqlite" / "app.db")


def create_connection():
    """Create and return SQLite connection."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
        return None
    
    
def init_db():
    """Create file storage table if not exists."""
    conn = create_connection()
    if conn is None:
        return

    try:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            hashed_name TEXT NOT NULL UNIQUE,
            path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()

    except Error as e:
        print(f"Init DB error: {e}")


def insert_file(original_name: str, hashed_name: str, path: str):
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO files (original_name, hashed_name, path)
        VALUES (?, ?, ?)
    """, (original_name, hashed_name, path))

    conn.commit()
    conn.close()
    
def get_all_files() -> List[Dict]:
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, original_name, hashed_name, path, replace(created_at, ' ', 'T') || 'Z' AS created_at FROM files")
    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]



def get_file_by_id(file_id: int) -> Optional[Dict]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_file_by_name(name: str) -> Optional[Dict]:
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM files WHERE original_name = ?",
        (name,)
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None

def update_file(file_id: int, new_name: str):
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE files
        SET original_name = ?
        WHERE id = ?
    """, (new_name, file_id))

    conn.commit()
    conn.close()
    


def delete_file(file_id: int):
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM files WHERE id = ?
    """, (file_id,))

    conn.commit()
    conn.close()
    
