import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

from database.retrieval.retrieval_service import embed_query, search_similar
from database.postgres_service import get_model_by_id, get_all_models
from llm import call_ollama, call_openai, call_anthropic, call_custom, call_gemini

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model_id: Optional[int] = None
    file_id: Optional[int] = None
    limit: int = 5


@router.post("/chat")
async def chat(request: ChatRequest) -> Dict:
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    last_user = next(
        (m.content for m in reversed(request.messages) if m.role == "user"), None
    )
    if not last_user:
        raise HTTPException(status_code=400, detail="No user message found")

    # Retrieve context (blocking calls run in thread pool to avoid blocking the event loop)
    loop = asyncio.get_event_loop()
    query_embedding = await loop.run_in_executor(None, embed_query, last_user)
    sources = await loop.run_in_executor(
        None, search_similar, query_embedding, request.limit, request.file_id
    )

    # Resolve model
    model = get_model_by_id(request.model_id) if request.model_id else None
    if not model:
        all_models = get_all_models()
        model = next((m for m in all_models if m["is_default"]), all_models[0] if all_models else None)
    if not model:
        raise HTTPException(status_code=400, detail="No model configured. Add one in the Models page.")

    # Build system prompt
    if sources:
        context = "\n\n".join(
            f"[{s['original_name']} — chunk #{s['chunk_index']}]\n"
            + (s["parent_content"] or s["content"])
            for s in sources
        )
        system_content = (
            "You are a helpful AI assistant. Answer the user's question using only the context below.\n\n"
            f"Context:\n{context}\n\n"
            "If the answer is not found in the context, say so clearly."
        )
    else:
        system_content = "You are a helpful AI assistant."

    messages = [{"role": "system", "content": system_content}]
    messages += [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        t    = model["type"]
        name = model["name"]
        key  = model["api_key"] or ""
        url  = model["base_url"] or ""

        if t in ("ollama", "local"):
            answer = await call_ollama(name, url, messages)
        elif t == "openai":
            answer = await call_openai(name, key, messages)
        elif t == "anthropic":
            answer = await call_anthropic(name, key, messages)
        elif t == "gemini":
            answer = await call_gemini(name, key, messages)
        elif t == "custom":
            answer = await call_custom(name, key, url, messages)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported model type: {t}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    return {"answer": answer, "sources": sources}
