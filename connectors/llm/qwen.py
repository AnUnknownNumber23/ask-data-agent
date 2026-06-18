import json
import httpx
from .base import BaseLLMProvider, ChatResponse, Message
from typing import AsyncIterator


class QwenProvider(BaseLLMProvider):
    """Qwen (Tongyi Qianwen) API adapter (OpenAI-compatible endpoint)."""

    def _build_payload(self, messages: list[Message], stream: bool = False, **kwargs) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "temperature": kwargs.get("temperature", self.extra.get("temperature", 0.1)),
            "max_tokens": kwargs.get("max_tokens", self.extra.get("max_tokens", 4096)),
        }

    async def chat(self, messages: list[Message], **kwargs) -> ChatResponse:
        payload = self._build_payload(messages, stream=False, **kwargs)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return ChatResponse(
                content=choice["message"]["content"],
                model=data.get("model", self.model),
                usage=data.get("usage", {}),
            )

    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        payload = self._build_payload(messages, stream=True, **kwargs)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
