import ast
import math
from typing import List, Dict, Optional
from database.postgres_service import _get_conn, _put_conn
from database.embeddings import get_embeddings_model


def embed_query(text: str) -> List[float]:
    return list(list(get_embeddings_model().embed([text]))[0])


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_similar(
    query_embedding: List[float],
    limit: int = 5,
    file_id: Optional[int] = None,
) -> List[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()

        if file_id is not None:
            cursor.execute("""
                SELECT dc.id, dc.file_id, dc.chunk_index, dc.content, dc.embedding,
                       f.original_name
                FROM document_chunks dc
                JOIN files f ON f.id = dc.file_id
                WHERE dc.file_id = %s
            """, (file_id,))
        else:
            cursor.execute("""
                SELECT dc.id, dc.file_id, dc.chunk_index, dc.content, dc.embedding,
                       f.original_name
                FROM document_chunks dc
                JOIN files f ON f.id = dc.file_id
            """)

        rows = cursor.fetchall()

        scored = []
        for row in rows:
            try:
                stored_embedding = ast.literal_eval(row["embedding"])
                score = _cosine_similarity(query_embedding, stored_embedding)
                scored.append({
                    "id": row["id"],
                    "file_id": row["file_id"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "score": float(score),
                    "original_name": row["original_name"],
                })
            except Exception:
                continue

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    except Exception as e:
        print(f"Search error: {e}")
        return []
    finally:
        _put_conn(conn)
