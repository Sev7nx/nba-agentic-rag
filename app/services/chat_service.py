import asyncio
from collections.abc import AsyncIterator

from app.models import ChatEvent, ChatRequest, ChatResponse, TraceStep


class ChatService:
    def __init__(self, graph):
        self._graph = graph

    def answer(self, request: ChatRequest) -> ChatResponse:
        profile = request.profile.model_dump() if request.profile else {}
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
        return ChatResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources") or [],
            trace=trace,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        try:
            response = self.answer(request)
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