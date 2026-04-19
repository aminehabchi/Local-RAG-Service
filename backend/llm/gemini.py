from typing import List, Dict
import httpx


async def call(name: str, api_key: str, messages: List[Dict]) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent?key={api_key}"

    system_parts = [{"text": m["content"]} for m in messages if m["role"] == "system"]
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    body: Dict = {"contents": contents}
    if system_parts:
        body["systemInstruction"] = {"parts": system_parts}

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
