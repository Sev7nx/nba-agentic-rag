import json
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse

from app.agent.graph import build_graph
from app.config import settings
from app.llm import OpenAICompatibleLLM
from app.models import ChatEvent, ChatRequest, ChatResponse, UserProfile
from app.services.chat_service import ChatService
from app.services.profile import ProfileStore
from app.tools.fetch import fetch_page
from app.tools.local_rag import local_rag
from app.tools.search import TavilySearchProvider, news_search, video_search

app = FastAPI(title="NBA Agentic RAG")
profile_store = ProfileStore(settings.profile_path)
_service: ChatService | None = None


def build_default_service() -> ChatService:
    llm = OpenAICompatibleLLM(
        settings.llm_api_key,
        settings.llm_base_url,
        settings.llm_model,
    )
    provider = (
        TavilySearchProvider(settings.tavily_api_key)
        if settings.tavily_api_key
        else None
    )
    tools = {
        "local_rag": local_rag,
        "search_news": lambda q: news_search(provider, q) if provider else [],
        "search_videos": lambda q: video_search(provider, q) if provider else [],
        "fetch_page": fetch_page,
    }
    return ChatService(build_graph(llm, tools))


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = build_default_service()
    return _service


def get_profile_store() -> ProfileStore:
    return profile_store


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return service.answer(request)


async def _event_stream(
    service: ChatService,
    request: ChatRequest,
) -> AsyncIterator[str]:
    try:
        async for event in service.stream(request):
            payload = json.dumps(event.data, ensure_ascii=False)
            yield f"event: {event.type}\ndata: {payload}\n\n"
    except Exception as exc:
        payload = json.dumps({"message": str(exc)}, ensure_ascii=False)
        yield f"event: error\ndata: {payload}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(service, request),
        media_type="text/event-stream",
    )


@app.get("/api/profile", response_model=UserProfile)
def get_profile(store: ProfileStore = Depends(get_profile_store)) -> UserProfile:
    return store.get()


@app.put("/api/profile", response_model=UserProfile)
def put_profile(
    profile: UserProfile,
    store: ProfileStore = Depends(get_profile_store),
) -> UserProfile:
    store.save(profile)
    return profile