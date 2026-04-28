from __future__ import annotations

from typing import List, Dict, Optional

from database.embedding.embeddings_model import embed_texts
from database.retrieval.cleaning import clean_query
from database.retrieval.search import search_similar, search_keyword, search_hybrid


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    mode: str = "hybrid",
    limit: int = 5,
    file_id: Optional[int] = None,
) -> List[Dict]:
    """
    Full retrieval pipeline: clean → embed → search.
    mode: "semantic" | "keyword" | "hybrid"
    """
    cleaned = clean_query(query)

    if mode == "keyword":
        return search_keyword(cleaned, limit=limit, file_id=file_id)

    query_embedding = embed_query(cleaned)

    if mode == "semantic":
        return search_similar(query_embedding, limit=limit, file_id=file_id)

    return search_hybrid(cleaned, query_embedding, limit=limit, file_id=file_id)


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]


# ---------------------------------------------------------------------------
# Re-exports for API route compatibility
# ---------------------------------------------------------------------------

__all__ = [
    "retrieve",
    "embed_query",
    "search_similar",
    "search_keyword",
    "search_hybrid",
]
