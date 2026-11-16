import html
import json
from collections.abc import Iterable, Iterator

from app.models import ChatEvent, Source, TraceStep


def render_sources(sources: list[Source]) -> str:
    if not sources:
        return "暂无来源"
    cards = []
    for source in sources:
        date = html.escape(source.date or "")
        cards.append(
            '<div class="source-card">'
            f'<a href="{html.escape(source.url)}" target="_blank">{html.escape(source.title)}</a>'
            f'<span>{html.escape(source.site)} · {date}</span>'
            "</div>"
        )
    return "\n".join(cards)


def render_trace(trace: list[TraceStep]) -> str:
    if not trace:
        return "暂无调试信息"
    return "\n".join(
        f"- {step.name}: {step.detail} ({step.duration_ms}ms)" for step in trace
    )


def format_api_error(exc: Exception) -> str:
    return f"服务暂时不可用：{exc}。请确认 FastAPI 已启动，或稍后重试。"


def parse_sse(lines: Iterable[str]) -> Iterator[ChatEvent]:
    event_type = None
    for line in lines:
        line = line.strip()
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:") and event_type:
            payload = line.removeprefix("data:").strip()
            try:
                data = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                data = {"raw": payload}
            yield ChatEvent(type=event_type, data=data)
            event_type = None