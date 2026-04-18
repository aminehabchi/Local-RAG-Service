from typing import List, Dict
import httpx

BASE_URL = "https://api.openai.com"


async def call(name: str, api_key: str, messages: List[Dict]) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json={"model": name, "messages": messages},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
