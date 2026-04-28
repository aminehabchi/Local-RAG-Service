from typing import Dict

from llm.base import LLMProvider
from llm.anthropic import AnthropicProvider
from llm.openai import OpenAIProvider
from llm.gemini import GeminiProvider
from llm.ollama import OllamaProvider
_REGISTRY = {
    "openai":    lambda m: OpenAIProvider(m["name"], m["api_key"] or ""),
    "anthropic": lambda m: AnthropicProvider(m["name"], m["api_key"] or ""),
    "gemini":    lambda m: GeminiProvider(m["name"], m["api_key"] or ""),
    "ollama":    lambda m: OllamaProvider(m["name"], m["base_url"] or ""),
    "local":     lambda m: OllamaProvider(m["name"], m["base_url"] or ""),
}


def get_provider(model: Dict) -> LLMProvider:
    factory = _REGISTRY.get(model["type"])
    if not factory:
        raise ValueError(f"Unsupported model type: {model['type']}")
    return factory(model)


__all__ = ["get_provider", "LLMProvider"]
