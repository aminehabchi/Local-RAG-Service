from abc import ABC, abstractmethod
from typing import List, Dict


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[Dict]) -> str: ...
