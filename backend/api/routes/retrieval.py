from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Literal

from database.retrieval.retrieval_service import (
    embed_query, search_similar, search_keyword, search_hybrid,
)


router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    file_id: Optional[int] = None
    search_type: Literal["semantic", "keyword", "hybrid"] = "semantic"


@router.post("/search")
async def search(request: SearchRequest) -> List[Dict]:
    try:
        if request.search_type == "keyword":
            return search_keyword(request.query, limit=request.limit, file_id=request.file_id)

        query_embedding = embed_query(request.query)

        if request.search_type == "hybrid":
            return search_hybrid(
                request.query, query_embedding,
                limit=request.limit, file_id=request.file_id,
            )

        return search_similar(query_embedding, limit=request.limit, file_id=request.file_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
