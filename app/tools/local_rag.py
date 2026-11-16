import os
from functools import lru_cache
from urllib.parse import urlparse

from app.rag.embeddings import BGEEmbedder, Embedder
from app.rag.reranker import BGEReranker, Reranker
from app.tools.base import SearchResult


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return BGEEmbedder()


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return BGEReranker()


def _site_from_url(url: str) -> str:
    host = urlparse(url).netloc
    return host[4:] if host.startswith("www.") else host


def local_rag(query: str, top_k: int = 20, rerank_top_n: int = 5) -> list[SearchResult]:
    persist_dir = os.getenv("CHROMA_DIR", "data/chroma")
    try:
        import chromadb

        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_collection(name="nba")
    except Exception:
        return []

    try:
        query_embedding = get_embedder().embed([query])[0]
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    except Exception:
        return []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    if not documents:
        return []

    scores = get_reranker().rerank(query, documents)
    ranked = sorted(
        zip(scores, documents, metadatas),
        key=lambda item: item[0],
        reverse=True,
    )[:rerank_top_n]

    sources: list[SearchResult] = []
    for _, text, metadata in ranked:
        metadata = metadata or {}
        url = metadata.get("url", "")
        if not url:
            continue
        sources.append(
            SearchResult(
                title=metadata.get("title", ""),
                url=url,
                site=metadata.get("site") or _site_from_url(url),
                snippet=text[:300],
                published_date=metadata.get("date"),
                result_type="doc",
            )
        )
    return sources