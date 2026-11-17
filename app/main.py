import json
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.agent.graph import build_graph
from app.config import settings
from app.llm import OpenAICompatibleLLM
from app.models import ChatRequest, ChatResponse, UserProfile
from app.services.cache import Cache
from app.services.chat_service import ChatService
from app.services.profile import ProfileStore
from app.tools.doc_search import doc_search
from app.tools.fetch import fetch_page_tool
from app.tools.nba_live import live_query
from app.tools.search import TavilySearchProvider, news_search, video_search
from app.tools.stats_query import stats_query

profile_store = ProfileStore(settings.profile_path)
_service: ChatService | None = None


def build_default_service(use_cache: bool = True) -> ChatService:
    llm = OpenAICompatibleLLM(
        settings.llm_api_key,
        settings.llm_base_url,
        settings.llm_model,
        input_price_cny=settings.llm_input_price_cny,
        output_price_cny=settings.llm_output_price_cny,
    )
    provider = (
        TavilySearchProvider(settings.tavily_api_key)
        if settings.tavily_api_key
        else None
    )
    tools = {
        "doc_search": doc_search,
        "search_news": lambda q: news_search(provider, q) if provider else [],
        "search_videos": lambda q: video_search(provider, q) if provider else [],
        "fetch_page": fetch_page_tool,
        "live_query": live_query,
        "stats_query": stats_query,
    }
    return ChatService(
        build_graph(llm, tools),
        Cache(settings.cache_path) if use_cache else None,
    )


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        try:
            _service = build_default_service()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"服务未配置：{exc}",
            ) from exc
    return _service


def get_profile_store() -> ProfileStore:
    return profile_store


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


def create_app(rate_limit: str | None = None) -> FastAPI:
    limit = rate_limit or settings.rate_limit
    limiter = Limiter(key_func=get_remote_address)
    application = FastAPI(title="NBA Agentic RAG")
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/chat", response_model=ChatResponse)
    @limiter.limit(limit)
    def chat(
        request: Request,
        payload: ChatRequest,
        service: ChatService = Depends(get_chat_service),
    ) -> ChatResponse:
        return service.answer(payload)

    @application.post("/api/chat/stream")
    @limiter.limit(limit)
    async def chat_stream(
        request: Request,
        payload: ChatRequest,
        service: ChatService = Depends(get_chat_service),
    ) -> StreamingResponse:
        return StreamingResponse(
            _event_stream(service, payload),
            media_type="text/event-stream",
        )

    @application.get("/api/profile", response_model=UserProfile)
    def get_profile(store: ProfileStore = Depends(get_profile_store)) -> UserProfile:
        return store.get()

    @application.put("/api/profile", response_model=UserProfile)
    def put_profile(
        profile: UserProfile,
        store: ProfileStore = Depends(get_profile_store),
    ) -> UserProfile:
        store.save(profile)
        return profile

    return application


app = create_app()