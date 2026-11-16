import asyncio
from collections.abc import AsyncIterator

from app.models import ChatEvent, ChatRequest, ChatResponse, TraceStep
from app.services.cache import Cache


class ChatService:
    def __init__(self, graph, cache: Cache | None = None):
        self._graph = graph
        self._cache = cache

    def answer(self, request: ChatRequest) -> ChatResponse:
        profile = request.profile.model_dump() if request.profile else {}
        cache_key = None
        if self._cache and not request.history:
            cache_key = self._cache.make_key(request.question, profile)
            cached = self._cache.get(cache_key)
            if cached:
                return ChatResponse.model_validate_json(cached).model_copy(
                    update={"cached": True}
                )
        state = {
            "question": request.question,
            "history": [turn.model_dump() for turn in request.history],
            "profile": profile,
            "rounds": 0,
        }
        result = self._graph.invoke(state)
        trace = [
            step if isinstance(step, TraceStep) else TraceStep(**step)
            for step in result.get("trace") or []
        ]
        response = ChatResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources") or [],
            trace=trace,
        )
        if self._cache and cache_key:
            self._cache.set(cache_key, response.model_dump_json())
        return response

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        try:
            response = await asyncio.to_thread(self.answer, request)
        except Exception as exc:
            yield ChatEvent(type="error", data={"message": str(exc)})
            return
        for index in range(0, len(response.answer), 20):
            yield ChatEvent(
                type="token",
                data={"text": response.answer[index : index + 20]},
            )
            await asyncio.sleep(0)
        yield ChatEvent(
            type="sources",
            data={"sources": [source.model_dump() for source in response.sources]},
        )
        yield ChatEvent(
            type="trace",
            data={"trace": [step.model_dump() for step in response.trace]},
        )
        yield ChatEvent(type="done", data={"cached": response.cached})