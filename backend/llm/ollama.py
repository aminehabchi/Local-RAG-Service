from urllib.parse import urlparse
from typing import List, Dict
import httpx

from llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, name: str, base_url: str):
        self.name = name
        raw = base_url or "http://localhost:11434"
        p = urlparse(raw)
        self.host = f"{p.scheme}://{p.netloc}"

    async def chat(self, messages: List[Dict]) -> str:
        parts = []
        for m in messages:
            if m["role"] == "system":
                parts.append(m["content"])
            elif m["role"] == "user":
                parts.append(f"User: {m['content']}")
            elif m["role"] == "assistant":
                parts.append(f"Assistant: {m['content']}")
        parts.append("Assistant:")
        prompt = "\n\n".join(parts)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.host}/api/generate",
                json={"model": self.name, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json()["response"]
