from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

from database.retrieval.retrieval_service import embed_query, search_similar


router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    file_id: Optional[int] = None


# =========================
# SEARCH SIMILAR CHUNKS
# =========================
@router.post("/search")
async def search(request: SearchRequest) -> List[Dict]:
    try:
        query_embedding = embed_query(request.query)
        results = search_similar(query_embedding, limit=request.limit, file_id=request.file_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
