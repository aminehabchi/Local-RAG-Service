# retrival service for the RAG system, responsible for fetching relevant documents based on user queries and providing them to the LLM for response generation.

import ast
import math
from typing import List, Dict
from fastembed import TextEmbedding
from database.postgres_service import create_connection

_embeddings = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def embed_query(text: str) -> List[float]:
    return list(list(_embeddings.embed([text]))[0])


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_similar(query_embedding: List[float], limit: int = 5) -> List[Dict]:
    conn = create_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
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
        conn.close()
