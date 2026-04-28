from typing import List, Dict
import httpx

from llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    _BASE_URL = "https://api.openai.com"

    def __init__(self, name: str, api_key: str):
        self.name = name
        self.api_key = api_key

    async def chat(self, messages: List[Dict]) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._BASE_URL}/v1/chat/completions",
                json={"model": self.name, "messages": messages},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
