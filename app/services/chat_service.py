from app.models import ChatRequest, ChatResponse, TraceStep


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