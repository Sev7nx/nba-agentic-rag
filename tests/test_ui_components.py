from app.models import Source, TraceStep
from app.ui.components import (
    build_history,
    format_api_error,
    format_trace,
    load_profile,
    parse_sse,
    render_sources,
    render_trace,
    save_profile,
)


def test_render_sources_contains_links():
    html = render_sources(
        [Source(id=1, title="标题", url="https://example.com", site="虎扑", type="news")]
    )
    assert "https://example.com" in html
    assert "虎扑" in html


def test_format_api_error_is_friendly():
    msg = format_api_error(RuntimeError("connection refused"))
    assert "服务" in msg


def test_parse_sse_returns_events():
    lines = ["event: token", 'data: {"text": "你"}', "event: done", "data: {}"]
    events = list(parse_sse(lines))
    assert events[0].type == "token"
    assert events[-1].type == "done"


def test_render_trace_contains_steps():
    text = render_trace([TraceStep(name="plan", detail="3 tools", duration_ms=12)])
    assert "plan" in text and "3 tools" in text


def test_format_trace_hides_empty():
    assert "暂无" in format_trace([])


def test_format_trace_contains_steps():
    text = format_trace([TraceStep(name="plan", detail="3 tools", duration_ms=12)])
    assert "plan" in text and "3 tools" in text


def test_render_sources_marks_dead_link():
    html = render_sources(
        [
            Source(
                id=1,
                title="t",
                url="https://example.com",
                site="x",
                type="news",
                link_status="dead",
            )
        ]
    )
    assert "链接可能失效" in html


def test_build_history_strips_sources_and_limits():
    messages = [
        {"role": "user", "content": "q1"},
        {
            "role": "assistant",
            "content": "a1",
            "sources": [
                Source(
                    id=1,
                    title="t",
                    url="https://example.com",
                    site="x",
                    type="news",
                )
            ],
        },
        {"role": "user", "content": "q2"},
    ]
    history = build_history(messages)
    assert history == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]
    import json

    json.dumps(history)


def test_load_profile_falls_back_on_error(monkeypatch):
    import httpx

    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    assert load_profile("http://api") == {
        "favorite_team": None,
        "favorite_players": [],
    }


def test_save_profile_calls_put(monkeypatch):
    import httpx

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_put(url, json=None, timeout=None):
        calls.append((url, json))
        return FakeResponse()

    monkeypatch.setattr(httpx, "put", fake_put)
    save_profile("http://api", {"favorite_team": "勇士", "favorite_players": []})
    assert calls[0][0] == "http://api/api/profile"
    assert calls[0][1]["favorite_team"] == "勇士"