from typing import List, Dict
import httpx

from llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    _BASE_URL = "https://api.anthropic.com"

    def __init__(self, name: str, api_key: str):
        self.name = name
        self.api_key = api_key

    async def chat(self, messages: List[Dict]) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        chat_msgs = [m for m in messages if m["role"] != "system"]

        payload: Dict = {"model": self.name, "max_tokens": 2048, "messages": chat_msgs}
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._BASE_URL}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
