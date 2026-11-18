import html
import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from app.models import ChatEvent, Source, TraceStep

SOURCE_TYPE_LABELS = {
    "stats": "数据",
    "live": "比分",
    "news": "新闻",
    "doc": "文档",
    "video": "视频",
}


def format_source_date(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    for parser in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            return parser(text).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            continue
    return text


def render_sources(sources: list[Source]) -> str:
    if not sources:
        return "暂无来源"
    cards = []
    for source in sources:
        date = html.escape(format_source_date(source.date))
        type_label = html.escape(SOURCE_TYPE_LABELS.get(source.type, source.type))
        meta = html.escape(
            " · ".join(part for part in [type_label, source.site, date] if part)
        )
        warning = (
            '<span style="color:#dc2626;"> · 链接可能失效</span>'
            if source.link_status == "dead"
            else ""
        )
        cards.append(
            '<div style="border:1px solid #e5e7eb;border-radius:10px;'
            'padding:10px 12px;margin:8px 0;background:#fff;">'
            f'<span style="display:inline-block;min-width:1.9em;'
            f'color:#6b7280;font-weight:600;">[{source.id}]</span>'
            f'<a href="{html.escape(source.url)}" target="_blank" '
            'rel="noopener noreferrer" style="font-weight:600;">'
            f"{html.escape(source.title)}</a>"
            f'<div style="color:#6b7280;font-size:0.85em;'
            f'margin-top:4px;">{meta}{warning}</div>'
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