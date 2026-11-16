import pytest
from pydantic import ValidationError

from app.models import ChatRequest, Source, ChatResponse


def test_empty_question_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(question="   ")


def test_source_requires_http_url():
    with pytest.raises(ValidationError):
        Source(id=1, title="x", url="not-a-url", site="x", type="news")


def test_chat_response_serializes_sources():
    source = Source(id=1, title="t", url="https://example.com", site="example", type="news")
    data = ChatResponse(answer="a", sources=[source], trace=[]).model_dump()
    assert data["sources"][0]["url"] == "https://example.com"