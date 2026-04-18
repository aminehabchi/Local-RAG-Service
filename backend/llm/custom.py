from typing import List, Dict
import httpx


async def call(name: str, api_key: str, base_url: str, messages: List[Dict]) -> str:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            json={"model": name, "messages": messages},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
