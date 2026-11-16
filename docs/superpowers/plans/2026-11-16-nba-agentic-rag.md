# NBA Agentic RAG 助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在两周内交付一个可演示、可评测的 NBA Agentic RAG 问答助手：FastAPI 后端 + Streamlit 前端，支持多源检索、带引用回答、自检重试和评测。

**Architecture:** Streamlit 通过 HTTP/SSE 调用 FastAPI；FastAPI 调用 LangGraph 状态机。Agent 依次做查询分析、工具规划、并行检索（本地 RAG / 新闻 / 视频 / 正文提取）、证据重排、带引用生成、自检重试。所有外部调用都有超时和降级。

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Streamlit, LangGraph, DeepSeek/Qwen（OpenAI 兼容）, Tavily, Chroma, BGE-M3 / BGE-reranker, RAGAS, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-16-nba-agentic-rag-design.md`

## Global Constraints

- Python 3.11+；所有应用代码放在 `app/` 下。
- API：`POST /api/chat`、`POST /api/chat/stream`、`GET/PUT /api/profile`、`GET /health`。
- 单次问答最多 4 个工具调用、2 轮检索。
- 中文回答；英文来源保留原标题；每个关键事实必须有引用。
- 不提交任何密钥；使用 `.env` 和 `.env.example`。
- 单用户，无登录；公网 demo 用 slowapi 限流。
- 来源只存标题、短摘要和链接，不转载全文。
- 每个任务完成后提交一次，使用 conventional commit。
- `pytest -q` 必须在没有网络和 API key 的情况下通过；联网测试标记 `integration`。
- 单次问答成本目标 < 0.2 元，P95 延迟 < 10 秒。

## Review Focus

1. 空问题 / 无意义输入 → 友好提示，不调用工具，不崩溃。
2. 搜索 0 结果或 API 超时 → 明确说没找到，建议换问法，不编造。
3. 链接失效 / 地区限制 → 链接检查后标记或丢弃，答案不依赖死链。
4. 来源冲突（例如交易流言）→ 同时呈现分歧，不给单一结论。
5. 同名 / 歧义实体（例如「库里」）→ 消歧或追问，不默认某一位。

## File Structure

```
nba-agentic-rag/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + routes + SSE
│   ├── config.py               # pydantic-settings
│   ├── models.py               # Pydantic schemas
│   ├── llm.py                  # LLM client protocol + OpenAI-compatible impl
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py            # AgentState TypedDict
│   │   ├── prompts.py          # prompt templates
│   │   ├── nodes.py            # analyze/plan/execute/grade/synthesize/verify
│   │   └── graph.py            # LangGraph wiring
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py             # SearchProvider / Reranker protocols
│   │   ├── search.py           # Tavily provider + news/video tools
│   │   ├── fetch.py            # page extraction + link check
│   │   └── local_rag.py        # Chroma retrieval + rerank tool
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingest.py           # load/chunk/index corpus
│   │   ├── embeddings.py       # Embedder protocol + BGE impl
│   │   └── reranker.py         # Reranker protocol + BGE impl
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat_service.py     # answer() + stream()
│   │   ├── profile.py          # profile.json store
│   │   └── cache.py            # SQLite cache
│   └── ui/
│       ├── __init__.py
│       ├── streamlit_app.py    # Streamlit page
│       └── components.py       # source cards / trace / errors
├── data/
│   ├── corpus/                 # seed docs (markdown/json)
│   ├── chroma/                 # persisted index (gitignored)
│   └── profile.json            # gitignored
├── eval/
│   └── questions.jsonl
├── scripts/
│   ├── ingest_corpus.py
│   └── eval.py
├── tests/
│   ├── test_health.py
│   ├── test_models.py
│   ├── test_search_tool.py
│   ├── test_fetch.py
│   ├── test_analysis.py
│   ├── test_ingest.py
│   ├── test_local_rag.py
│   ├── test_graph.py
│   ├── test_verifier.py
│   ├── test_api.py
│   ├── test_stream.py
│   ├── test_ui_components.py
│   ├── test_cache.py
│   ├── test_eval.py
│   └── test_e2e.py
├── .env.example
├── .gitignore
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### Test Fixtures（`tests/conftest.py`）

在写第一个测试前，先建立共享 fixture，避免每个测试重复造数据：

- `fake_llm`：实现 `chat_json(system, user, schema)`，返回 `schema(**payload)`；payload 由测试通过 `fake_llm.payload` 设置。
- `fake_tools`：`{"local_rag": lambda q: [...], "search_news": ..., "search_videos": ..., "fetch_page": ...}`，默认返回 1-2 条 `SearchResult`。
- `fake_service`：有 `answer(request) -> ChatResponse` 的对象，返回固定答案和一条 source。
- `fake_streaming_service`：`stream(request)` 异步生成 `token`、`done` 事件。
- `fake_failing_service`：`stream(request)` 生成 `error` 事件。
- `client`：`TestClient(app)`，并用 `app.dependency_overrides[get_chat_service] = lambda: fake_service`。

这些 fixture 只用于测试，不进入生产代码。

---

### Task 1: 项目骨架、配置与健康检查

**Files:**
- Create: `pyproject.toml`, `.env.example`, `.gitignore`, `app/__init__.py`, `app/config.py`, `app/main.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Produces: `Settings`（`llm_api_key`, `llm_base_url`, `llm_model`, `tavily_api_key`, `chroma_dir`, `cache_path`, `profile_path`, `api_url`）；`app.main:app` FastAPI 实例。

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from app.main import app

def test_health_returns_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.main'`。

- [ ] **Step 3: Implement `Settings` 和 `app/main.py`**

`Settings` 用 `pydantic-settings` 从 `.env` 读取；`app/main.py` 创建 `FastAPI(title="NBA Agentic RAG")` 并实现 `GET /health`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS。

- [ ] **Step 5: Add config files and commit**

`.env.example` 列出 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`TAVILY_API_KEY`、`API_URL`；`.gitignore` 覆盖 `.env`、`data/chroma/`、`data/profile.json`、`__pycache__/`、`.pytest_cache/`。

```bash
git add pyproject.toml .env.example .gitignore app tests
git commit -m "chore: scaffold fastapi project"
```

---

### Task 2: Pydantic 数据模型

**Files:**
- Create: `app/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Source(id, title, url, site, date, type, snippet)`；`TraceStep(name, detail, duration_ms, tokens, cost_cny)`；`ChatTurn(role, content)`；`ChatRequest(question, history, profile)`；`ChatResponse(answer, sources, trace, cached)`；`UserProfile(favorite_team, favorite_players)`；`ChatEvent(type, data)`。

- [ ] **Step 1: Write failing tests**

```python
import pytest
from pydantic import ValidationError
from app.models import ChatRequest, Source, ChatResponse

def test_empty_question_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(question="   ")

def test_source_requires_http_url():
    with pytest.raises(ValidationError):
        Source(id=1, title="x", url="not-a-url", site="x", type="news")

def test_chat_response_serializes_sources():
    source = Source(id=1, title="t", url="https://example.com", site="example", type="news")
    data = ChatResponse(answer="a", sources=[source], trace=[]).model_dump()
    assert data["sources"][0]["url"] == "https://example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL，`ModuleNotFoundError`。

- [ ] **Step 3: Implement models**

`ChatRequest.question` 使用 `min_length=1`，并在 validator 中 `strip()` 后检查非空；`Source.url` 使用 `HttpUrl`；`type` 用 `Literal["news", "video", "doc"]`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: add pydantic models"
```

---

### Task 3: Tavily 搜索工具与来源过滤

**Files:**
- Create: `app/tools/__init__.py`, `app/tools/base.py`, `app/tools/search.py`
- Test: `tests/test_search_tool.py`

**Interfaces:**
- Produces:
  - `NEWS_DOMAINS = ["hupu.com", "sports.qq.com", "nba.com", "espn.com"]`
  - `VIDEO_DOMAINS = ["bilibili.com", "youtube.com"]`
  - `SearchProvider` protocol：`search(query, include_domains, max_results=5, topic="general") -> list[SearchResult]`
  - `SearchResult(title, url, site, snippet, published_date, result_type)`；`result_type` 为 `news|video|doc`。
  - `TavilySearchProvider(api_key)` 实现该 protocol。
  - `news_search(provider, query, days=30) -> list[SearchResult]`
  - `video_search(provider, query) -> list[SearchResult]`

- [ ] **Step 1: Write failing tests**

```python
from app.tools.search import NEWS_DOMAINS, VIDEO_DOMAINS, news_search, video_search

class FakeProvider:
    def __init__(self):
        self.calls = []
    def search(self, query, include_domains, max_results=5, topic="general"):
        self.calls.append({"query": query, "domains": include_domains, "topic": topic})
        return []

def test_news_search_uses_news_domains():
    provider = FakeProvider()
    news_search(provider, "勇士 交易")
    assert provider.calls[0]["domains"] == NEWS_DOMAINS

def test_video_search_uses_video_domains():
    provider = FakeProvider()
    video_search(provider, "库里 集锦")
    assert provider.calls[0]["domains"] == VIDEO_DOMAINS

def test_empty_results_returns_empty_list():
    assert news_search(FakeProvider(), "不存在的问题") == []

def test_provider_error_returns_empty_list(monkeypatch):
    class BrokenProvider:
        def search(self, *args, **kwargs):
            raise RuntimeError("network down")
    assert news_search(BrokenProvider(), "x") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_search_tool.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement provider and wrappers**

`TavilySearchProvider.search` 调用 Tavily Python SDK；捕获异常并返回 `[]`；把结果映射成 `SearchResult`（`title, url, site, snippet, published_date, result_type`）。`news_search` 传 `topic="news"` 和最近 30 天；`video_search` 传 `topic="general"`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search_tool.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/tools tests/test_search_tool.py
git commit -m "feat: add tavily search tools with source filters"
```

---

### Task 4: 正文提取与链接检查

**Files:**
- Create: `app/tools/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces: `fetch_page(url: str, max_chars: int = 4000) -> str`；`is_link_alive(url: str, timeout: float = 3.0) -> bool`。

- [ ] **Step 1: Write failing tests**

```python
from app.tools.fetch import fetch_page, is_link_alive

def test_fetch_page_truncates(monkeypatch):
    monkeypatch.setattr("app.tools.fetch._extract", lambda url: "x" * 10000)
    assert len(fetch_page("https://example.com", max_chars=100)) == 100

def test_fetch_page_returns_empty_on_error(monkeypatch):
    def boom(url):
        raise RuntimeError("timeout")
    monkeypatch.setattr("app.tools.fetch._extract", boom)
    assert fetch_page("https://example.com") == ""

def test_is_link_alive_false_on_timeout(monkeypatch):
    import httpx
    def boom(*args, **kwargs):
        raise httpx.TimeoutException("timeout")
    monkeypatch.setattr(httpx, "head", boom)
    assert is_link_alive("https://example.com") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement fetch and link check**

`_extract` 用 Tavily extract（或 httpx + 简单正文提取）；`fetch_page` 捕获异常、截断到 `max_chars`；`is_link_alive` 用 `httpx.head`，3 秒超时，异常返回 `False`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fetch.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/tools/fetch.py tests/test_fetch.py
git commit -m "feat: add page fetch and link check"
```

---

### Task 5: LLM 客户端与查询分析/规划

**Files:**
- Create: `app/llm.py`, `app/agent/__init__.py`, `app/agent/state.py`, `app/agent/prompts.py`, `app/agent/nodes.py`
- Test: `tests/test_analysis.py`

**Interfaces:**
- Produces:
  - `LLMClient` protocol：`chat_json(system: str, user: str, schema: type[BaseModel]) -> BaseModel`；`chat_text(system: str, user: str) -> str`。
  - `OpenAICompatibleLLM(api_key, base_url, model)` 实现该 protocol。
  - `AgentState`（TypedDict）：`question, history, profile, analysis, plan, tool_results, evidence, answer, sources, trace, rounds, verified`。
  - `analyze_query(state) -> {"analysis": {"entities": [...], "intent": "...", "time_sensitivity": "latest|classic|none", "language": "zh|en", "ambiguous": bool}}`
  - `plan_tools(state) -> {"plan": [{"tool": "...", "query": "...", "reason": "..."}]}`
  - `TOOL_NAMES = {"local_rag", "search_news", "search_videos", "fetch_page"}`

- [ ] **Step 1: Write failing tests**

```python
from app.agent.nodes import analyze_query, plan_tools

class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
    def chat_json(self, system, user, schema):
        return schema(**self.payload)
    def chat_text(self, system, user):
        return "answer"

def test_analyze_query_extracts_entity_and_intent():
    state = {"question": "库里哪场比赛最经典", "history": [], "profile": {}}
    out = analyze_query(state, FakeLLM({"entities": ["库里"], "intent": "history", "time_sensitivity": "classic", "language": "zh"}))
    assert out["analysis"]["entities"] == ["库里"]

def test_plan_tools_caps_at_four():
    state = {"question": "x", "analysis": {"entities": [], "intent": "news", "time_sensitivity": "latest", "language": "zh"}}
    plan = [{"tool": "search_news", "query": "x", "reason": "r"}] * 6
    out = plan_tools(state, FakeLLM({"plan": plan}))
    assert len(out["plan"]) == 4

def test_plan_tools_rejects_unknown_tool():
    state = {"question": "x", "analysis": {"entities": [], "intent": "news", "time_sensitivity": "latest", "language": "zh"}}
    out = plan_tools(state, FakeLLM({"plan": [{"tool": "rm_rf", "query": "x", "reason": "r"}]}))
    assert out["plan"] == []

def test_analysis_marks_ambiguous_entity():
    state = {"question": "库里最近怎么样", "history": [], "profile": {}}
    out = analyze_query(state, FakeLLM({"entities": ["库里"], "intent": "news", "time_sensitivity": "latest", "language": "zh", "ambiguous": True}))
    assert out["analysis"]["ambiguous"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analysis.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement LLM client, state, prompts, analyze/plan**

分析 prompt 要求输出严格 JSON；计划 prompt 要求从 `TOOL_NAMES` 中选工具并给理由；`plan_tools` 截断到 4 条并过滤未知工具。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analysis.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/llm.py app/agent tests/test_analysis.py
git commit -m "feat: add llm client and query analysis"
```

---

### Task 6: 语料摄入、切块与向量索引

**Files:**
- Create: `app/rag/__init__.py`, `app/rag/embeddings.py`, `app/rag/ingest.py`, `scripts/ingest_corpus.py`, `data/corpus/README.md`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Produces:
  - `Document(doc_id, title, url, text, source_type, entity_type, entity_name, date)`
  - `load_documents(corpus_dir: Path) -> list[Document]`
  - `Chunk(id, text, metadata)`；`chunk_document(doc: Document, chunk_size: int = 600, overlap: int = 100) -> list[Chunk]`
  - `Embedder` protocol：`embed(texts: list[str]) -> list[list[float]]`；`BGEEmbedder(model_name)` 实现。
  - `build_index(chunks, embedder, persist_dir) -> Chroma`

- [ ] **Step 1: Write failing tests**

```python
from app.rag.ingest import Document, chunk_document

def test_chunk_overlap_and_metadata():
    doc = Document(doc_id="1", title="库里", url="https://example.com", text="a" * 1500,
                   source_type="doc", entity_type="player", entity_name="库里", date=None)
    chunks = chunk_document(doc, chunk_size=600, overlap=100)
    assert len(chunks) >= 3
    assert chunks[0].metadata["entity_name"] == "库里"
    assert chunks[0].text[:10] == "a" * 10

def test_load_documents_skips_unknown_files(tmp_path):
    (tmp_path / "a.md").write_text("# 标题\n正文", encoding="utf-8")
    (tmp_path / "b.exe").write_bytes(b"x")
    from app.rag.ingest import load_documents
    docs = load_documents(tmp_path)
    assert len(docs) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement load/chunk/index**

`load_documents` 读取 `.md` / `.json`；`chunk_document` 按字符切块并保留元数据；`build_index` 用 Chroma 的 `collection.add`，ID 用 `f"{doc_id}-{i}"`。测试中使用 `FakeEmbedder`，不下载模型。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ingest.py -v`
Expected: PASS。

- [ ] **Step 5: Add ingest script and commit**

`scripts/ingest_corpus.py` 读取 `data/corpus/`，调用 `build_index`，输出索引到 `data/chroma/`。

```bash
git add app/rag scripts/ingest_corpus.py data/corpus/README.md tests/test_ingest.py
git commit -m "feat: add corpus ingestion and vector index"
```

---

### Task 7: 本地 RAG 检索与重排

**Files:**
- Create: `app/tools/local_rag.py`, `app/rag/reranker.py`
- Test: `tests/test_local_rag.py`

**Interfaces:**
- Produces:
  - `Reranker` protocol：`rerank(query: str, texts: list[str]) -> list[float]`；`BGEReranker(model_name)` 实现。
  - `local_rag(query: str, top_k: int = 20, rerank_top_n: int = 5) -> list[SearchResult]`
  - 返回的 `SearchResult.result_type = "doc"`。

- [ ] **Step 1: Write failing tests**

```python
from app.tools.local_rag import local_rag

class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]

class FakeReranker:
    def rerank(self, query, texts):
        return [float(len(t)) for t in texts]

def test_local_rag_returns_top_n(monkeypatch, tmp_path):
    from app.rag.ingest import Chunk, build_index
    chunks = [
        Chunk(id="1", text="库里 三分", metadata={"title": "a", "url": "https://a", "site": "x"}),
        Chunk(id="2", text="库里 冠军", metadata={"title": "b", "url": "https://b", "site": "x"}),
        Chunk(id="3", text="勇士 交易", metadata={"title": "c", "url": "https://c", "site": "x"}),
    ]
    build_index(chunks, FakeEmbedder(), tmp_path)
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path))
    monkeypatch.setattr("app.tools.local_rag.get_reranker", lambda: FakeReranker())
    results = local_rag("库里", top_k=3, rerank_top_n=2)
    assert len(results) == 2
    assert all(r.url.startswith("https://") for r in results)

def test_local_rag_returns_empty_when_index_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "missing"))
    assert local_rag("库里") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_local_rag.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement retrieval and rerank**

`local_rag` 先向量检索 `top_k`，再用 reranker 排序取 `rerank_top_n`；索引不存在时返回 `[]`；每条结果带 `title/url/site/snippet` 元数据。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_local_rag.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/tools/local_rag.py app/rag/reranker.py tests/test_local_rag.py
git commit -m "feat: add local rag retrieval and reranking"
```

---

### Task 8: Agent 图骨架

**Files:**
- Create: `app/agent/graph.py`
- Modify: `app/agent/nodes.py`, `app/agent/state.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Produces:
  - `ToolRegistry`：`{"local_rag": callable, "search_news": callable, "search_videos": callable, "fetch_page": callable}`
  - `build_graph(llm, tools) -> CompiledGraph`
  - 节点：`analyze_query`、`plan_tools`、`execute_tools`、`synthesize`
  - `synthesize` 把 `SearchResult` 转成 `Source`（`id` 按 1..n，`type=result_type`）。

- [ ] **Step 1: Write failing tests**

```python
from app.agent.graph import build_graph

def test_graph_runs_with_fake_tools(fake_llm, fake_tools):
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "库里最经典的比赛", "history": [], "profile": {}, "rounds": 0})
    assert out["answer"]
    assert isinstance(out["sources"], list)

def test_execute_tools_skips_failed_tool(fake_llm, fake_tools):
    fake_tools["search_news"] = lambda q: (_ for _ in ()).throw(RuntimeError("down"))
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "勇士交易", "history": [], "profile": {}, "rounds": 0})
    assert out["answer"]

def test_graph_respects_max_tool_calls(fake_llm, fake_tools):
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "x", "history": [], "profile": {}, "rounds": 0})
    assert len(out.get("tool_results", [])) <= 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_graph.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement graph and execute/synthesize nodes**

`execute_tools` 按 `plan` 调用 registry，每个工具包 try/except，失败记录到 trace 并继续；`synthesize` 用证据生成中文答案和 sources，答案不超过 8 句。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_graph.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/agent tests/test_graph.py
git commit -m "feat: add agent graph skeleton"
```

---

### Task 9: 证据评分、自检与重试

**Files:**
- Modify: `app/agent/nodes.py`, `app/agent/graph.py`
- Test: `tests/test_verifier.py`

**Interfaces:**
- Produces:
  - `grade_evidence(state) -> {"evidence": [...]}`：按 URL 去重，按来源质量/时效/相关性排序，保留 5-8 条。
  - `verify(state) -> {"verified": bool, "verification_notes": str}`：检查引用覆盖和答案非空。
  - 图增加条件边：未通过且 `rounds < 2` → `refine_query` → `execute_tools`；否则 END。

- [ ] **Step 1: Write failing tests**

```python
from app.agent.nodes import grade_evidence, verify

def test_grade_evidence_dedupes_urls():
    state = {"tool_results": [
        {"title": "a", "url": "https://x", "site": "hupu", "snippet": "s"},
        {"title": "a2", "url": "https://x", "site": "hupu", "snippet": "s2"},
    ]}
    out = grade_evidence(state)
    assert len(out["evidence"]) == 1

def test_verify_fails_without_citations():
    state = {"answer": "库里很强。", "sources": []}
    assert verify(state)["verified"] is False

def test_no_sources_produces_caveat(fake_llm, fake_tools):
    empty_tools = {name: (lambda q: []) for name in fake_tools}
    graph = build_graph(fake_llm, empty_tools)
    out = graph.invoke({"question": "一个没人知道的问题", "history": [], "profile": {}, "rounds": 0})
    assert "没找到" in out["answer"]

def test_conflicting_sources_are_both_kept():
    state = {"tool_results": [
        {"title": "A 说交易", "url": "https://a", "site": "hupu", "snippet": "会交易", "claim": "trade"},
        {"title": "B 说不会", "url": "https://b", "site": "qq", "snippet": "不会交易", "claim": "no-trade"},
    ]}
    out = grade_evidence(state)
    assert len(out["evidence"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_verifier.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement grading, verification, retry edge**

`grade_evidence` 用来源质量分（官方 > 媒体 > 论坛）+ 相关性分排序；`verify` 检查答案里是否至少有一个 `[n]` 且 sources 非空；重试只在 `rounds < 2` 时发生。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_verifier.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/agent tests/test_verifier.py
git commit -m "feat: add evidence grading and verification"
```

---

### Task 10: ChatService、`/api/chat` 与 `/api/profile`

**Files:**
- Create: `app/services/__init__.py`, `app/services/chat_service.py`, `app/services/profile.py`
- Modify: `app/main.py`, `app/models.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces:
  - `ChatService(graph).answer(request: ChatRequest) -> ChatResponse`
  - `ProfileStore(path).get() -> UserProfile`；`.save(profile: UserProfile) -> None`
  - `POST /api/chat` → `ChatResponse`；`GET /api/profile` / `PUT /api/profile` → `UserProfile`

- [ ] **Step 1: Write failing tests**

```python
from fastapi.testclient import TestClient
from app.main import app

def test_chat_endpoint_returns_answer_and_sources(fake_service):
    app.dependency_overrides[get_chat_service] = lambda: fake_service
    client = TestClient(app)
    r = client.post("/api/chat", json={"question": "库里最经典的比赛"})
    assert r.status_code == 200
    assert r.json()["answer"]

def test_profile_roundtrip(client):
    r = client.put("/api/profile", json={"favorite_team": "勇士", "favorite_players": ["库里"]})
    assert r.status_code == 200
    assert client.get("/api/profile").json()["favorite_team"] == "勇士"

def test_chat_endpoint_rejects_empty_question(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement service, profile store, routes**

用 FastAPI dependency injection 提供 `ChatService`；测试中用 `dependency_overrides` 替换成 fake。`ProfileStore` 读写 `data/profile.json`，文件不存在时返回默认空 profile。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/services app/main.py app/models.py tests/test_api.py
git commit -m "feat: add chat api and profile"
```

---

### Task 11: SSE 流式接口

**Files:**
- Modify: `app/main.py`, `app/services/chat_service.py`, `app/models.py`
- Test: `tests/test_stream.py`

**Interfaces:**
- Produces:
  - `ChatService.stream(request) -> AsyncIterator[ChatEvent]`
  - `POST /api/chat/stream` 返回 `text/event-stream`，事件：`token`、`sources`、`trace`、`done`、`error`。

- [ ] **Step 1: Write failing tests**

```python
def test_stream_emits_token_then_done(fake_streaming_service):
    client = TestClient(app)
    with client.stream("POST", "/api/chat/stream", json={"question": "库里"}) as r:
        body = "".join(r.iter_text())
    assert "event: token" in body
    assert "event: done" in body

def test_stream_emits_error_event_on_failure(fake_failing_service):
    ...
    assert "event: error" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stream.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement streaming**

`ChatService.stream` 先 yield `token`（逐段），再 `sources`、`trace`，最后 `done`；异常时 yield `error` 后结束。FastAPI 用 `StreamingResponse` 和 `media_type="text/event-stream"`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stream.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/services/chat_service.py app/models.py tests/test_stream.py
git commit -m "feat: add sse streaming endpoint"
```

---

### Task 12: Streamlit 聊天页、来源卡片与设置

**Files:**
- Create: `app/ui/__init__.py`, `app/ui/streamlit_app.py`, `app/ui/components.py`
- Test: `tests/test_ui_components.py`

**Interfaces:**
- Produces:
  - `render_sources(sources: list[Source]) -> str`（HTML/markdown，包含标题、站点、链接）
  - `parse_sse(lines: Iterable[str]) -> Iterator[ChatEvent]`：把 `event:` / `data:` 行解析成 `ChatEvent`。
  - `render_trace(trace: list[TraceStep]) -> str`
  - `format_api_error(exc: Exception) -> str`
  - Streamlit 页面：侧栏设置 + 聊天输入 + 流式输出。

- [ ] **Step 1: Write failing tests**

```python
from app.models import Source
from app.ui.components import render_sources, format_api_error

def test_render_sources_contains_links():
    html = render_sources([Source(id=1, title="标题", url="https://example.com", site="虎扑", type="news")])
    assert "https://example.com" in html
    assert "虎扑" in html

def test_format_api_error_is_friendly():
    msg = format_api_error(RuntimeError("connection refused"))
    assert "服务" in msg

def test_parse_sse_returns_events():
    from app.ui.components import parse_sse
    lines = ["event: token", 'data: {"text": "你"}', "event: done", "data: {}"]
    events = list(parse_sse(lines))
    assert events[0].type == "token"
    assert events[-1].type == "done"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui_components.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement components and Streamlit page**

页面用 `st.chat_message` / `st.chat_input`；调用 `/api/chat/stream` 用 `httpx.stream`，逐行解析 `event:` / `data:`；侧栏用 `st.selectbox` 选主队、`st.multiselect` 选球员；API URL 从 `API_URL` 环境变量读取。

- [ ] **Step 4: Run tests and manual smoke**

Run: `pytest tests/test_ui_components.py -v` → PASS。
Run: `streamlit run app/ui/streamlit_app.py`，问一个问题，确认流式回答和来源卡片出现。

- [ ] **Step 5: Commit**

```bash
git add app/ui tests/test_ui_components.py
git commit -m "feat: add streamlit chat ui"
```

---

### Task 13: Trace 面板与错误状态

**Files:**
- Modify: `app/ui/streamlit_app.py`, `app/ui/components.py`
- Test: `tests/test_ui_components.py`

**Interfaces:**
- Produces:
  - `format_trace(trace: list[TraceStep]) -> str`：展示 plan、工具调用、耗时、token、成本。
  - 错误状态：API 不可达、超时、0 结果、死链。

- [ ] **Step 1: Write failing tests**

```python
from app.models import TraceStep
from app.ui.components import format_trace

def test_format_trace_hides_empty():
    assert "暂无" in format_trace([])

def test_format_trace_contains_steps():
    text = format_trace([TraceStep(name="plan", detail="3 tools", duration_ms=12)])
    assert "plan" in text and "3 tools" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui_components.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement trace and error states**

用 `st.expander("调试轨迹")` 展示；API 不可达时显示 `format_api_error`；0 结果时显示「没找到可靠来源，试试换个问法」；死链在来源卡片上标记「链接可能失效」。

- [ ] **Step 4: Run tests and manual check**

Run: `pytest tests/test_ui_components.py -v` → PASS。
Manual: 停掉 FastAPI，刷新页面，确认显示友好错误而不是堆栈。

- [ ] **Step 5: Commit**

```bash
git add app/ui tests/test_ui_components.py
git commit -m "feat: add trace panel and error states"
```

---

### Task 14: 缓存与限流

**Files:**
- Create: `app/services/cache.py`
- Modify: `app/main.py`, `app/services/chat_service.py`
- Test: `tests/test_cache.py`

**Interfaces:**
- Produces:
  - `Cache(path).get(key) -> str | None`；`.set(key, value, ttl_seconds=86400)`；`.make_key(question, profile) -> str`。
  - `POST /api/chat` 和 `/api/chat/stream` 加 slowapi 限流：每 IP 每小时 20 次。

- [ ] **Step 1: Write failing tests**

```python
from app.services.cache import Cache

def test_cache_hit_and_miss(tmp_path):
    cache = Cache(tmp_path / "c.db")
    assert cache.get("x") is None
    cache.set("x", "y", ttl_seconds=60)
    assert cache.get("x") == "y"

def test_cache_expiry(tmp_path):
    cache = Cache(tmp_path / "c.db")
    cache.set("x", "y", ttl_seconds=-1)
    assert cache.get("x") is None

def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1/hour")
    # 如果 limiter 在 import 时初始化，测试用 importlib.reload(app.main)，或把 limiter 做成可注入依赖
    first = client.post("/api/chat", json={"question": "库里"})
    second = client.post("/api/chat", json={"question": "库里"})
    assert first.status_code == 200
    assert second.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement cache and limiter**

SQLite 表 `cache(key TEXT PRIMARY KEY, value TEXT, created_at REAL)`；`get` 检查 TTL；`make_key` 用 `hashlib.sha256` 把 question + profile 归一化后哈希。slowapi `Limiter(key_func=get_remote_address, default_limits=["20/hour"])`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cache.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/services/cache.py app/main.py app/services/chat_service.py tests/test_cache.py
git commit -m "feat: add cache and rate limiting"
```

---

### Task 15: 评测集与评测脚本

**Files:**
- Create: `eval/questions.jsonl`, `scripts/eval.py`
- Test: `tests/test_eval.py`

**Interfaces:**
- Produces:
  - `EvalQuestion(id, question, expected_facts, expected_source_types, needs_link)`
  - `evaluate(questions, chat_service) -> EvalReport`
  - 指标：`retrieval_hit_rate`、`citation_coverage`、`link_validity`、`p95_latency_ms`、`avg_cost_cny`
  - 输出 `eval/report.md`。

- [ ] **Step 1: Write failing tests**

```python
from scripts.eval import EvalQuestion, evaluate

def test_retrieval_hit_rate_counts_expected_source(fake_service):
    q = EvalQuestion(id="1", question="勇士交易", expected_facts=["交易"], expected_source_types=["news"], needs_link=True)
    report = evaluate([q], fake_service)
    assert 0 <= report.retrieval_hit_rate <= 1

def test_report_markdown_contains_metrics(fake_service, tmp_path):
    report = evaluate([], fake_service)
    text = report.to_markdown()
    assert "retrieval_hit_rate" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL。

- [ ] **Step 3: Implement eval**

`questions.jsonl` 先放 20 条，覆盖 5 类；`evaluate` 调 `ChatService.answer`，统计指标；`to_markdown` 输出表格。RAGAS 作为可选依赖，未安装时跳过。

- [ ] **Step 4: Run tests and a small eval**

Run: `pytest tests/test_eval.py -v` → PASS。
Run: `python scripts/eval.py --limit 3`（用 fake 或已配置的 API），确认生成 `eval/report.md`。

- [ ] **Step 5: Commit**

```bash
git add eval scripts/eval.py tests/test_eval.py
git commit -m "feat: add evaluation harness"
```

---

### Task 16: Docker、README 与最终验收

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `README.md`
- Test: `tests/test_e2e.py`

**Interfaces:**
- Produces: `docker compose up --build` 同时启动 `api`（8000）和 `ui`（8501）；README 包含架构图、启动步骤、评测结果和面试说明。

- [ ] **Step 1: Write failing e2e test**

```python
def test_e2e_question_to_answer(fake_service):
    client = TestClient(app)
    r = client.post("/api/chat", json={"question": "库里最经典的比赛"})
    assert r.status_code == 200
    assert r.json()["answer"]
    assert r.json()["sources"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_e2e.py -v`
Expected: FAIL（如果前面的依赖还没接好）。

- [ ] **Step 3: Add Dockerfile, compose, README**

`Dockerfile`：`python:3.11-slim` + `pip install -e .` + `uvicorn app.main:app --host 0.0.0.0 --port 8000`。`docker-compose.yml`：`api` 和 `ui` 两个服务，`ui` 设置 `API_URL=http://api:8000`。README 包含架构图、环境变量、启动命令、评测结果、面试要点。

- [ ] **Step 4: Run full verification**

Run: `pytest -q` → 全部通过。
Run: `docker compose up --build` → 打开 `http://localhost:8501`，问 3 个问题，确认回答、来源、trace 正常。
Run: `python scripts/eval.py` → 生成评测报告。

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml README.md tests/test_e2e.py
git commit -m "chore: add docker, docs, and e2e test"
```

---

## Self-Review Checklist

- [ ] 每个设计目标都有对应任务：FastAPI、Streamlit、Agent、工具、RAG、引用、评测、部署。
- [ ] 每个任务都有独立的测试或手动验收标准。
- [ ] 类型和函数名在任务之间一致（`ChatRequest`、`ChatResponse`、`Source`、`SearchResult`、`local_rag`、`build_graph`）。
- [ ] Review Focus 的 5 个失败模式都有对应测试或手动检查。
- [ ] 没有把完整实现写进计划；只保留测试、签名和验收命令。

## Open Questions

1. 项目名字：仓库名 `nba-agentic-rag`，界面名暂用「NBA Scout」，可以随时改。
2. 演示用的主队和喜欢的球员：先填勇士 + 库里，用于截图和录屏。
3. 首批语料：50 位球员 + 30 支球队 + 20 篇经典比赛/规则，先从 30 篇开始。