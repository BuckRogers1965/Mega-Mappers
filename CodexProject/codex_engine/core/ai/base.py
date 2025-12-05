from abc import ABC, abstractmethod
from typing import Dict, Any

class AIProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def generate_text(self, prompt: str, context: str = "") -> str:
        pass

    @abstractmethod
    def generate_json(self, prompt: str, schema_hint: str = "") -> Dict[str, Any]:
        pass
