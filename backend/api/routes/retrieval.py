from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict

from retrieval.retrieval_service import embed_query, search_similar


router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


# =========================
# SEARCH SIMILAR CHUNKS
# =========================
@router.post("/search")
async def search(request: SearchRequest) -> List[Dict]:
    try:
        query_embedding = embed_query(request.query)
        results = search_similar(query_embedding, limit=request.limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
