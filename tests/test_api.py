def test_chat_endpoint_returns_answer_and_sources(client):
    response = client.post("/api/chat", json={"question": "库里最经典的比赛"})
    assert response.status_code == 200
    assert response.json()["answer"] == "answer [1]"
    assert response.json()["sources"][0]["url"] == "https://example.com"


def test_profile_roundtrip(client):
    response = client.put(
        "/api/profile",
        json={"favorite_team": "勇士", "favorite_players": ["库里"]},
    )
    assert response.status_code == 200
    assert client.get("/api/profile").json()["favorite_team"] == "勇士"


def test_chat_endpoint_rejects_empty_question(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422


def test_chat_without_config_returns_503(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main

    def boom():
        raise RuntimeError("LLM_API_KEY missing")

    monkeypatch.setattr(main, "_service", None)
    monkeypatch.setattr(main, "build_default_service", boom)
    response = TestClient(main.create_app()).post(
        "/api/chat", json={"question": "库里"}
    )
    assert response.status_code == 503
    assert "服务未配置" in response.json()["detail"]