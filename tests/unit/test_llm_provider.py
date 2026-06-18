import pytest
from connectors.llm.base import Message
from connectors.llm.deepseek import DeepSeekProvider


class TestDeepSeekProvider:
    @pytest.fixture
    def provider(self):
        return DeepSeekProvider(
            model="deepseek-chat",
            api_base="http://localhost:8080/v1",
            api_key="test-key",
        )

    def test_build_payload_non_stream(self, provider):
        messages = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
        ]
        payload = provider._build_payload(messages, stream=False)
        assert payload["model"] == "deepseek-chat"
        assert payload["stream"] is False
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"

    def test_build_payload_stream(self, provider):
        messages = [Message(role="user", content="Hi")]
        payload = provider._build_payload(messages, stream=True)
        assert payload["stream"] is True

    def test_message_dataclass(self):
        msg = Message(role="user", content="test")
        assert msg.role == "user"
        assert msg.content == "test"

    def test_chat_response_dataclass(self):
        from connectors.llm.base import ChatResponse
        resp = ChatResponse(content="Hello", model="test", usage={"prompt_tokens": 10})
        assert resp.content == "Hello"
        assert resp.usage["prompt_tokens"] == 10
