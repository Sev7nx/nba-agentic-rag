def test_cache_hit_and_miss(tmp_path):
    from app.services.cache import Cache

    cache = Cache(tmp_path / "c.db")
    assert cache.get("x") is None
    cache.set("x", "y", ttl_seconds=60)
    assert cache.get("x") == "y"


def test_cache_expiry(tmp_path):
    from app.services.cache import Cache

    cache = Cache(tmp_path / "c.db")
    cache.set("x", "y", ttl_seconds=-1)
    assert cache.get("x") is None


def test_chat_service_uses_cache(fake_llm, fake_tools, tmp_path):
    from app.agent.graph import build_graph
    from app.models import ChatRequest
    from app.services.cache import Cache
    from app.services.chat_service import ChatService

    graph = build_graph(fake_llm, fake_tools)
    service = ChatService(graph, Cache(tmp_path / "cache.db"))
    first = service.answer(ChatRequest(question="库里"))
    second = service.answer(ChatRequest(question="库里"))
    assert first.cached is False
    assert second.cached is True


def test_cache_not_used_for_multiturn(fake_llm, fake_tools, tmp_path):
    from app.agent.graph import build_graph
    from app.models import ChatRequest, ChatTurn
    from app.services.cache import Cache
    from app.services.chat_service import ChatService

    graph = build_graph(fake_llm, fake_tools)
    service = ChatService(graph, Cache(tmp_path / "cache.db"))
    history = [ChatTurn(role="user", content="库里")]
    first = service.answer(
        ChatRequest(question="他上一场得了多少分？", history=history)
    )
    second = service.answer(
        ChatRequest(question="他上一场得了多少分？", history=history)
    )
    assert first.cached is False
    assert second.cached is False


def test_rate_limit_returns_429(fake_service):
    from fastapi.testclient import TestClient

    from app.main import create_app, get_chat_service

    test_app = create_app(rate_limit="1/hour")
    test_app.dependency_overrides[get_chat_service] = lambda: fake_service
    client = TestClient(test_app)
    first = client.post("/api/chat", json={"question": "库里"})
    second = client.post("/api/chat", json={"question": "库里"})
    assert first.status_code == 200
    assert second.status_code == 429