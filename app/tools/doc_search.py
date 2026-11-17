import re
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
        (
            "规则",
            "三分线",
            "附加赛",
            "条款",
            "犯规",
            "判罚",
            "违例",
            "工资帽",
            "选秀",
        ),
    ),
    (
        "game_report",
        (
            "比赛",
            "战报",
            "总决赛",
            "季后赛",
            "绝杀",
            "经典",
            "最后一投",
            "退役战",
            "夺冠",
            "60 分",
            "60分",
            "81 分",
            "经典比赛",
            "game 7",
            "finals",
        ),
    ),
    ("tactic", ("战术", "挡拆", "防守策略")),
    ("player_intro", ("球员", "生涯", "技术特点", "资料", "介绍")),
)

_HISTORY_TERMS = (
    ("总决赛", ("finals", "nba finals")),
    ("最后一投", ("last shot", "final shot")),
    ("退役战", ("final game", "retirement", "farewell")),
    ("夺冠", ("championship", "champion", "title")),
    ("绝杀", ("game winner", "buzzer", "clutch")),
    ("经典", ("classic", "iconic", "greatest")),
    ("第七场", ("game 7", "game seven")),
    ("加时", ("overtime",)),
    ("60 分", ("60 points", "60-point")),
    ("60分", ("60 points", "60-point")),
    ("81 分", ("81 points", "81-point")),
    ("罗斯条款", ("rose rule", "derrick rose rule")),
)


def _history_terms(query: str) -> list[str]:
    terms: list[str] = []
    for chinese, english in _HISTORY_TERMS:
        if chinese in query:
            terms.append(chinese)
            terms.extend(english)
    for year in re.findall(r"(?:19|20)\d{2}", query):
        terms.append(year)
    return terms


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


def _snippet(
    text: str,
    terms: list[str],
    query: str = "",
    size: int = 600,
) -> str:
    if any(word in query for word in ("多少分", "几分", "得分")):
        match = re.search(r"(\d{2,3})\s*(?:points|分)", text)
        if match:
            start = max(0, match.start() - 200)
            return text[start : start + size]
    lowered = text.lower()
    for term in terms:
        index = lowered.find(term)
        if index >= 0:
            start = max(0, index - size // 3)
            return text[start : start + size]
    return text[:size]


def doc_search(query: str, top_k: int = 50, limit: int = 5) -> list[SearchResult]:
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
    terms = [
        term.lower()
        for term in [
            *entity_terms(query),
            *_history_terms(query),
        ]
    ]
    terms = list(dict.fromkeys(term for term in terms if term))
    topic_terms = [
        term.lower() for term in _history_terms(query) if term
    ]
    entity_terms_list = [
        term.lower() for term in entity_terms(query) if term
    ]
    if topic_terms or entity_terms_list:
        def _score(item):
            metadata = item[2] or {}
            title = str(metadata.get("title") or "").lower()
            body = item[1].lower()

            def hits(candidates, haystack):
                return sum(term in haystack for term in candidates)

            return (
                hits(topic_terms, title),
                hits(topic_terms, body),
                hits(entity_terms_list, title),
                hits(entity_terms_list, body),
                item[0],
            )

        ranked = sorted(ranked, key=_score, reverse=True)

    sources: list[SearchResult] = []
    seen_urls: set[str] = set()
    for _, text, metadata in ranked:
        metadata = metadata or {}
        url = str(metadata.get("url") or "")
        if not url.startswith(("http://", "https://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        snippet = _snippet(text, terms, query)
        if (
            any(word in query for word in ("多少分", "几分", "得分"))
            and metadata.get("doc_id")
        ):
            try:
                first = collection.get(
                    ids=[f"{metadata['doc_id']}-0"],
                    include=["documents"],
                )
                first_docs = first.get("documents") or []
                if first_docs:
                    snippet = first_docs[0][:800]
            except Exception:
                pass
        sources.append(
            SearchResult(
                title=metadata.get("title") or "NBA 文档",
                url=url,
                site=_site(url, str(metadata.get("source") or "")),
                snippet=snippet,
                published_date=metadata.get("date"),
                result_type="doc",
            )
        )
        if len(sources) >= limit:
            break
    return sources