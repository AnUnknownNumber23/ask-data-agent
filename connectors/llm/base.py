from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Pluggable LLM provider interface."""

    def __init__(self, model: str, api_base: str, api_key: str, **kwargs):
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.extra = kwargs

    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> ChatResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        """Stream a chat completion response token by token."""
        ...
