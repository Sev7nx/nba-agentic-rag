import html
import json
from collections.abc import Iterable, Iterator

import httpx

from app.models import ChatEvent, Source, TraceStep


def render_sources(sources: list[Source]) -> str:
    if not sources:
        return "暂无来源"
    cards = []
    for source in sources:
        date = html.escape(source.date or "")
        warning = " · 链接可能失效" if source.link_status == "dead" else ""
        cards.append(
            '<div class="source-card">'
            f'<a href="{html.escape(source.url)}" target="_blank">{html.escape(source.title)}</a>'
            f'<span>{html.escape(source.site)} · {date}{warning}</span>'
            "</div>"
        )
    return "\n".join(cards)


def format_trace(trace: list[TraceStep]) -> str:
    if not trace:
        return "暂无调试信息"
    lines = []
    for step in trace:
        line = f"- {step.name}: {step.detail} ({step.duration_ms}ms"
        if step.tokens:
            line += f", {step.tokens} tokens"
        if step.cost_cny:
            line += f", ¥{step.cost_cny:.4f}"
        line += ")"
        lines.append(line)
    return "\n".join(lines)


def render_trace(trace: list[TraceStep]) -> str:
    return format_trace(trace)


def format_api_error(exc: Exception) -> str:
    return f"服务暂时不可用：{exc}。请确认 FastAPI 已启动，或稍后重试。"


def load_profile(api_url: str) -> dict:
    try:
        response = httpx.get(f"{api_url.rstrip('/')}/api/profile", timeout=3.0)
        response.raise_for_status()
        data = response.json()
        return {
            "favorite_team": data.get("favorite_team"),
            "favorite_players": data.get("favorite_players", []),
        }
    except Exception:
        return {"favorite_team": None, "favorite_players": []}


def save_profile(api_url: str, profile: dict) -> None:
    try:
        httpx.put(
            f"{api_url.rstrip('/')}/api/profile",
            json=profile,
            timeout=3.0,
        )
    except Exception:
        pass


def build_history(messages: list[dict], limit: int = 10) -> list[dict]:
    return [
        {"role": message["role"], "content": message["content"]}
        for message in messages[-limit:]
        if message.get("content")
    ]


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