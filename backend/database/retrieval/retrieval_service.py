import numpy as np
from typing import List, Dict, Optional
from database.postgres_service import _get_conn, _put_conn
from database.embeddings import get_embeddings_model


def embed_query(text: str) -> List[float]:
    return list(list(get_embeddings_model().embed([text]))[0])


def search_similar(
    query_embedding: List[float],
    limit: int = 5,
    file_id: Optional[int] = None,
) -> List[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        q_vec = np.array(query_embedding, dtype=np.float32)
        where = "AND dc.file_id = %s " if file_id is not None else ""
        extra = (file_id,) if file_id is not None else ()

        cursor.execute(f"""
            SELECT dc.id, dc.file_id, dc.chunk_index, dc.content,
                   dc.parent_content, dc.concept_title, dc.chunk_type,
                   dc.keywords, dc.page_number, dc.section_title,
                   f.original_name,
                   1 - (dc.embedding <=> %s) AS score
            FROM document_chunks dc
            JOIN files f ON f.id = dc.file_id
            WHERE dc.embedding IS NOT NULL {where}
            ORDER BY dc.embedding <=> %s
            LIMIT %s
        """, (q_vec, *extra, q_vec, limit))

        return _rows(cursor.fetchall())
    except Exception as e:
        print(f"Semantic search error: {e}")
        raise
    finally:
        _put_conn(conn)


def search_keyword(
    query: str,
    limit: int = 5,
    file_id: Optional[int] = None,
) -> List[Dict]:
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        where = "AND dc.file_id = %s " if file_id is not None else ""
        extra = (file_id,) if file_id is not None else ()

        # Use content_tsv generated column when available, fall back to inline
        cursor.execute(f"""
            SELECT dc.id, dc.file_id, dc.chunk_index, dc.content,
                   dc.parent_content, dc.concept_title, dc.chunk_type,
                   dc.keywords, dc.page_number, dc.section_title,
                   f.original_name,
                   ts_rank(
                       COALESCE(dc.content_tsv, to_tsvector('english', dc.content)),
                       plainto_tsquery('english', %s)
                   ) AS score
            FROM document_chunks dc
            JOIN files f ON f.id = dc.file_id
            WHERE COALESCE(dc.content_tsv, to_tsvector('english', dc.content))
                  @@ plainto_tsquery('english', %s)
            {where}
            ORDER BY score DESC
            LIMIT %s
        """, (query, query, *extra, limit))

        rows = _rows(cursor.fetchall())
        return _normalize(rows)
    except Exception as e:
        print(f"Keyword search error: {e}")
        raise
    finally:
        _put_conn(conn)


def search_hybrid(
    query: str,
    query_embedding: List[float],
    limit: int = 5,
    file_id: Optional[int] = None,
) -> List[Dict]:
    fetch = max(limit * 3, 20)
    sem = search_similar(query_embedding, limit=fetch, file_id=file_id)
    try:
        kw = search_keyword(query, limit=fetch, file_id=file_id)
    except Exception:
        kw = []

    k = 60
    rrf: dict[int, float] = {}
    meta: dict[int, dict] = {}

    for rank, r in enumerate(sem):
        rrf[r["id"]] = rrf.get(r["id"], 0.0) + 1.0 / (k + rank + 1)
        meta[r["id"]] = r

    for rank, r in enumerate(kw):
        rrf[r["id"]] = rrf.get(r["id"], 0.0) + 1.0 / (k + rank + 1)
        meta[r["id"]] = r

    ranked = sorted(rrf.items(), key=lambda x: x[1], reverse=True)[:limit]
    max_score = ranked[0][1] if ranked else 1.0
    return [{**meta[rid], "score": round(score / max_score, 4)} for rid, score in ranked]


# ── helpers ──────────────────────────────────────────────────────────────────

def _rows(rows) -> List[Dict]:
    return [
        {
            "id":            row["id"],
            "file_id":       row["file_id"],
            "chunk_index":   row["chunk_index"],
            "content":       row["content"],
            "parent_content": row.get("parent_content"),
            "concept_title": row.get("concept_title"),
            "chunk_type":    row.get("chunk_type"),
            "keywords":      row.get("keywords"),
            "page_number":   row.get("page_number"),
            "section_title": row.get("section_title"),
            "score":         float(row["score"]),
            "original_name": row["original_name"],
        }
        for row in rows
    ]


def _normalize(results: List[Dict]) -> List[Dict]:
    if not results:
        return results
    max_s = max(r["score"] for r in results) or 1.0
    for r in results:
        r["score"] = round(r["score"] / max_s, 4)
    return results
