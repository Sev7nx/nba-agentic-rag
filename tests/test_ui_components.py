from app.models import Source, TraceStep
from app.ui.components import format_api_error, parse_sse, render_sources, render_trace


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