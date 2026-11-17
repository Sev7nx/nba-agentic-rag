import pytest

from app.tools.base import SearchResult


class FakeLLM:
    def __init__(self):
        self.payload = {}

    def chat_json(self, system, user, schema):
        return schema(**self.payload)

    def chat_text(self, system, user):
        return "answer [1]"


@pytest.fixture(autouse=True)
def _fast_link_check(monkeypatch):
    monkeypatch.setattr("app.agent.nodes.is_link_alive", lambda url: True)


@pytest.fixture
def fake_llm():
    llm = FakeLLM()
    llm.payload = {
        "entities": ["库里"],
        "intent": "history",
        "time_sensitivity": "classic",
        "language": "zh",
        "plan": [
            {"tool": "doc_search", "query": "库里 最经典 比赛", "reason": "history"},
            {"tool": "search_news", "query": "库里 新闻", "reason": "news"},
        ],
    }
    return llm


@pytest.fixture
def fake_tools():
    return {
        "doc_search": lambda q: [
            SearchResult(
                title="库里经典比赛",
                url="https://example.com/curry",
                site="example",
                snippet="2016 年总决赛",
                result_type="doc",
            )
        ],
        "search_news": lambda q: [
            SearchResult(
                title="勇士交易消息",
                url="https://example.com/news",
                site="example",
                snippet="交易传闻",
                result_type="news",
            )
        ],
        "search_videos": lambda q: [
            SearchResult(
                title="库里集锦",
                url="https://example.com/video",
                site="example",
                snippet="集锦",
                result_type="video",
            )
        ],
        "fetch_page": lambda q: [],
    }


@pytest.fixture
def fake_service():
    from app.models import ChatResponse, Source

    class FakeService:
        def answer(self, request):
            return ChatResponse(
                answer="answer [1]",
                sources=[
                    Source(
                        id=1,
                        title="t",
                        url="https://example.com",
                        site="example",
                        type="news",
                        snippet="交易",
                    )
                ],
                trace=[],
            )

    return FakeService()


@pytest.fixture
def client(fake_service, tmp_path):
    from fastapi.testclient import TestClient

    from app.main import app, get_chat_service, get_profile_store
    from app.services.profile import ProfileStore

    app.dependency_overrides[get_chat_service] = lambda: fake_service
    app.dependency_overrides[get_profile_store] = lambda: ProfileStore(
        tmp_path / "profile.json"
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_streaming_service():
    from app.models import ChatEvent

    class FakeStreamingService:
        async def stream(self, request):
            yield ChatEvent(type="token", data={"text": "你"})
            yield ChatEvent(type="sources", data={"sources": []})
            yield ChatEvent(type="trace", data={"trace": []})
            yield ChatEvent(type="done", data={})

    return FakeStreamingService()


@pytest.fixture
def fake_failing_service():
    class FakeFailingService:
        async def stream(self, request):
            raise RuntimeError("boom")
            yield  # pragma: no cover

    return FakeFailingService()


@pytest.fixture
def stream_client(fake_streaming_service):
    from fastapi.testclient import TestClient

    from app.main import app, get_chat_service

    app.dependency_overrides[get_chat_service] = lambda: fake_streaming_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def failing_stream_client(fake_failing_service):
    from fastapi.testclient import TestClient

    from app.main import app, get_chat_service

    app.dependency_overrides[get_chat_service] = lambda: fake_failing_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()