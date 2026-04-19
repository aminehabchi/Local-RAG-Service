from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import httpx

from database.postgres_service import (
    get_all_models, get_model_by_id, insert_model,
    update_model, set_default_model, delete_model,
)

router = APIRouter()


class ModelBody(BaseModel):
    name: str
    type: str = "local"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_default: bool = False


# =========================
# LIST
# =========================
@router.get("/models")
async def list_models() -> List[Dict]:
    return get_all_models()


# =========================
# OLLAMA MODELS
# =========================
@router.get("/models/ollama-tags")
async def ollama_tags(base_url: str = "http://localhost:11434") -> List[str]:
    try:
        from urllib.parse import urlparse
        p = urlparse(base_url)
        host = f"{p.scheme}://{p.netloc}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{host}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


# =========================
# CREATE
# =========================
@router.post("/models", status_code=201)
async def create_model(body: ModelBody):
    model_id = insert_model(body.name, body.type, body.api_key, body.base_url, body.is_default)
    if model_id is None:
        raise HTTPException(status_code=500, detail="Failed to create model")
    return get_model_by_id(model_id)


# =========================
# UPDATE
# =========================
@router.put("/models/{model_id}")
async def update_model_route(model_id: int, body: ModelBody):
    if not get_model_by_id(model_id):
        raise HTTPException(status_code=404, detail="Model not found")
    update_model(model_id, body.name, body.type, body.api_key, body.base_url, body.is_default)
    return get_model_by_id(model_id)


# =========================
# SET DEFAULT
# =========================
@router.patch("/models/{model_id}/default")
async def set_default(model_id: int):
    if not get_model_by_id(model_id):
        raise HTTPException(status_code=404, detail="Model not found")
    set_default_model(model_id)
    return get_model_by_id(model_id)


# =========================
# DELETE
# =========================
@router.delete("/models/{model_id}")
async def delete_model_route(model_id: int):
    if not get_model_by_id(model_id):
        raise HTTPException(status_code=404, detail="Model not found")
    delete_model(model_id)
    return {"message": "Model deleted"}
