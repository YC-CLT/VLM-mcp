from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VLMResponse:
    text: str
    tokens_used: int
    model: str
    cache_hit: bool = False


class BaseProvider(ABC):
    @abstractmethod
    def analyze(self, image, prompt: str) -> VLMResponse:
        ...

    @abstractmethod
    def chat(self, messages: list[dict]) -> VLMResponse:
        ...