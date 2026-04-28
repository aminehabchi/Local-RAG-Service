from __future__ import annotations

from typing import List, Dict

from database.embedding.embeddings_model import embed_texts
from database.postgres_service import batch_insert_chunks, update_file_chunk_count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_and_insert(file_id: int, records: List[Dict]) -> int:
    """
    Embed child content in each record, attach vectors, insert parents + children to DB.
    Returns the number of child chunks inserted.
    """
    child_texts = [r["content"] for r in records]
    embeddings  = embed_texts(child_texts)

    update_file_chunk_count(file_id, len(embeddings))

    chunks: List[Dict] = []
    for i, rec in enumerate(records):
        chunks.append({
            **rec,
            "embedding": embeddings[i],
        })

    batch_insert_chunks(file_id, chunks)
    return len(chunks)
