# NBA Scout — Agentic RAG NBA 问答助手

用一句中文提问，Agent 自己决定去结构化数据、新闻搜索还是视频搜索找答案，返回带引用和可点击来源的中文回答。

项目目标：个人使用 + AI 应用开发岗位简历项目。核心不是「查数据」，而是「帮你找」：把分散在虎扑、腾讯体育、B站和本地资料里的信息，变成一句回答加一组链接。

数据原则：**数字走 SQL，解释走向量检索**。球员场均、球队战绩、奖项、得分王这类精确数据直接查 `data/stats.sqlite`，不把数字切块塞进向量库；新闻、比赛回顾、球员介绍、规则和战术这类非结构化内容才走向量 RAG。

## 架构

```
Streamlit UI
  │  HTTP / SSE
  ▼
FastAPI 后端（/api/chat、/api/chat/stream、/api/profile、/docs）
  │
  ▼
LangGraph Agent
  analyze_query → plan → execute_tools → grade_evidence → synthesize → verify
                                   │
       ┌───────────────┬───────────┼────────────┬──────────────┐
       ▼               ▼           ▼            ▼              ▼
   stats_query     live_query   search_news  search_videos   local_rag
  data/stats.sqlite nba_api.live  Tavily       Tavily         Chroma + BGE
  1947–2026-27      今日比分      新闻/转会     B站/YouTube    本地文档
       │
       └─ 精确数字：球员赛季/生涯、球队战绩、奖项、得分王
```

## 功能

- 中文聊天界面，SSE 流式输出
- 查询分析：实体、意图、时效性、歧义
- Agent 规划：最多 4 个工具调用、2 轮检索
- 多源检索：结构化统计、今日比分、新闻、视频、网页正文
- 结构化数据精确查询：球员赛季/生涯、球队战绩、奖项、得分王；数字走 SQL，不做向量检索
- 今日比赛/实时比分：`nba_api.live`，30 秒缓存
- 证据去重、来源质量评分、结构化证据优先、BGE 重排
- 带行内引用 `[n]` 和可点击来源卡片
- 自检：引用覆盖、链接可达、无来源不编造
- 主队 / 喜欢的球员设置，影响检索排序
- SQLite 缓存 + slowapi 限流
- 20 题评测集 + 指标报告

## 技术栈

Python 3.11、FastAPI、Pydantic、Streamlit、LangGraph、DeepSeek/Qwen（OpenAI 兼容）、Tavily、SQLite、nba_api、Chroma、BGE-M3 / BGE-reranker、pytest、Docker Compose。

## 快速开始

### 1. 安装

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev,embeddings]"
```

PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev,embeddings]"
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```
LLM_API_KEY=你的模型 key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
TAVILY_API_KEY=你的 Tavily key
STATS_AS_OF=2026-11-01
```

`STATS_AS_OF` 要和 `data/stats.sqlite` 的数据截止日一致；重建数据后记得更新。

### 3. 准备结构化数据

项目用 [sumitrodatta/nba-aba-baa-stats](https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats) 的历史数据（1947–2026-27，含球员赛季/生涯、球队战绩、奖项、全明星、最佳阵容）建 SQLite：

```bash
kaggle datasets download -d sumitrodatta/nba-aba-baa-stats -p data/extra --unzip
python scripts/build_stats_db.py
```

生成 `data/stats.sqlite`。需要先配置 Kaggle CLI（`~/.kaggle/kaggle.json`）。

### 4. 本地知识库（可选）

把语料放到 `data/corpus/`（格式见 `data/corpus/README.md`），然后：

```bash
python scripts/ingest_corpus.py
```

首次运行会下载 BGE 模型，需要一些时间和磁盘空间。

### 5. 启动

```bash
uvicorn app.main:app --reload
```

另开一个终端：

```bash
streamlit run app/ui/streamlit_app.py
```

打开 `http://localhost:8501`；API 文档在 `http://localhost:8000/docs`。

## Docker

```bash
docker compose up --build
```

打开 `http://localhost:8501`。api 在 `http://localhost:8000`。

镜像包含 BGE 依赖，第一次构建会比较慢、体积较大。没有 Docker 时，用上面的本地启动方式即可。

## 评测

```bash
python scripts/eval.py --limit 5          # 用真实模型和搜索
python scripts/eval.py --limit 3 --fake   # 不调 API，检查报告格式
```

生成 `eval/report.md`，指标包括：

- `retrieval_hit_rate`：期望来源是否出现
- `citation_coverage`：关键事实是否有引用
- `link_validity`：来源链接是否有效
- `p95_latency_ms`：端到端延迟
- `avg_cost_cny`：单次问答平均成本

目标：命中率 ≥ 70%，引用覆盖 ≥ 90%，链接有效 ≥ 95%，P95 < 10 秒，单次成本 < 0.2 元。

把真实跑出来的结果填到 README 或简历里；不要用 `--fake` 的数字冒充真实指标。

## 项目结构

```
app/
  main.py            FastAPI 路由、SSE、限流
  models.py          Pydantic 模型
  agent/             查询分析、规划、执行、评分、自检
  tools/             搜索、正文提取、结构化统计、今日比分、本地 RAG
  rag/               语料切块、embedding、重排
  services/          ChatService、profile、缓存
  ui/                Streamlit 页面与组件
tests/               单元测试 + API 测试 + e2e
eval/                评测问题和报告
scripts/             建索引、跑评测
docs/                设计文档和实现计划
```

## 设计取舍（面试可以讲）

- **为什么 Agentic RAG，而不是普通 RAG**：问题需要多源路由（结构化数据 / 新闻 / 视频 / 文档），还要在证据不足时改写查询重试。普通 RAG 只做一次检索，覆盖不了这种问题。
- **为什么不把数字做成向量**：场均 29.2 分这种精确值需要 SQL 计算和聚合，向量检索只能找到「提到过数字的段落」，既不准也难更新。数字走 SQL，解释类内容走向量，最后合并证据。
- **为什么用 LangGraph**：状态机显式、可调试，后续可以加 Planner/Critic 演进到多 Agent。
- **检索质量**：切块 + 元数据 + 向量检索 + BGE 重排 + 来源质量评分。
- **防幻觉**：每个关键事实带引用；没有来源就明确说没找到；自检不过最多重试一次。
- **成本与延迟**：缓存、并行工具、最多 4 次调用 / 2 轮检索、便宜模型。
- **评测**：20 题评测集 + 自动指标，而不是「我觉得挺好」。

## 已知限制

- 结构化数据来自 Kaggle 快照，`STATS_AS_OF` 之前的赛季数据是精确的；之后的比赛以 `live_query` 或最新新闻为准。
- 今日比分来自 `nba_api.live`；NBA 官方 stats 接口在部分网络会被 Akamai 拦截，所以历史统计用离线快照，不依赖在线 stats 接口。
- nbadb 的 Kaggle 版本是原始 16 表、数据只到 2023，暂未作为主数据源；当前赛季统计以 sumitrodatta 快照为准。
- 单用户，无登录；公网 demo 需要限流。
- 本地知识库需要自己灌语料；BGE 模型首次运行会下载。
- 视频搜索优先 B站；YouTube 作为回退，国内网络可能不可达。
- B站/YouTube 链接可能受地区限制，UI 会标记或丢弃失效链接。