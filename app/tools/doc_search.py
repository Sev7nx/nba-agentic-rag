from functools import lru_cache
from urllib.parse import urlparse

from app.config import settings
from app.rag.embeddings import BGEEmbedder, Embedder
from app.rag.reranker import BGEReranker, Reranker
from app.tools.base import SearchResult
from app.tools.id_resolver import entity_terms

COLLECTION_NAME = "nba_docs"

_DOC_TYPE_KEYWORDS = (
    (
        "rules",
        ("规则", "三分线", "附加赛", "条款", "犯规", "判罚", "违例", "工资帽", "选秀"),
    ),
    ("game_report", ("比赛", "战报", "总决赛", "季后赛", "绝杀", "经典")),
    ("tactic", ("战术", "挡拆", "防守策略")),
    ("player_intro", ("球员", "生涯", "技术特点", "资料", "介绍")),
)


def _doc_type_filter(query: str) -> dict | None:
    for doc_type, keywords in _DOC_TYPE_KEYWORDS:
        if any(keyword in query for keyword in keywords):
            return {"doc_type": {"$eq": doc_type}}
    return None


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return BGEEmbedder(
        settings.embedding_model,
        local_files_only=settings.embedding_local_only,
    )


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return BGEReranker(
        settings.rerank_model,
        local_files_only=settings.embedding_local_only,
    )


def get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=settings.chroma_dir)
    return client.get_collection(COLLECTION_NAME)


def _site(url: str, source: str = "") -> str:
    if source:
        return source[4:] if source.startswith("www.") else source
    host = urlparse(url).netloc
    return host[4:] if host.startswith("www.") else host


def _snippet(text: str, terms: list[str], size: int = 400) -> str:
    lowered = text.lower()
    for term in terms:
        index = lowered.find(term)
        if index >= 0:
            start = max(0, index - size // 3)
            return text[start : start + size]
    return text[:size]


def doc_search(query: str, top_k: int = 12, limit: int = 5) -> list[SearchResult]:
    try:
        collection = get_collection()
        count = collection.count()
        if count == 0:
            return []
        embedding = get_embedder().embed([query])[0]
        where = _doc_type_filter(query)
        query_args = {
            "query_embeddings": [embedding],
            "n_results": min(top_k, count),
        }
        if where:
            query_args["where"] = where
        results = collection.query(**query_args)
        if where and not results.get("documents", [[]])[0]:
            query_args.pop("where")
            results = collection.query(**query_args)
    except Exception:
        return []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    if not documents:
        return []

    scores = None
    if settings.rerank_enabled:
        try:
            scores = get_reranker().rerank(query, documents)
        except Exception:
            scores = None
    if scores is None:
        distances = results.get("distances", [[]])[0]
        scores = (
            [-float(distance) for distance in distances]
            if distances
            else [0.0] * len(documents)
        )

    ranked = sorted(
        zip(scores, documents, metadatas),
        key=lambda item: item[0],
        reverse=True,
    )
    terms = [term.lower() for term in entity_terms(query)]
    if terms:
        ranked = sorted(
            ranked,
            key=lambda item: (
                any(
                    term
                    in f"{item[2].get('title', '')} {item[1]}".lower()
                    for term in terms
                ),
                item[0],
            ),
            reverse=True,
        )

    sources: list[SearchResult] = []
    seen_urls: set[str] = set()
    for _, text, metadata in ranked:
        metadata = metadata or {}
        url = str(metadata.get("url") or "")
        if not url.startswith(("http://", "https://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append(
            SearchResult(
                title=metadata.get("title") or "NBA 文档",
                url=url,
                site=_site(url, str(metadata.get("source") or "")),
                snippet=_snippet(text, terms),
                published_date=metadata.get("date"),
                result_type="doc",
            )
        )
        if len(sources) >= limit:
            break
    return sources