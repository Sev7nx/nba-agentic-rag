from urllib.parse import urlparse

from app.tools.base import SearchProvider, SearchResult

NEWS_DOMAINS = ["hupu.com", "sports.qq.com", "nba.com", "espn.com"]
BILIBILI_DOMAINS = ["bilibili.com"]
YOUTUBE_DOMAINS = ["youtube.com"]
VIDEO_DOMAINS = BILIBILI_DOMAINS + YOUTUBE_DOMAINS


def _site_from_url(url: str) -> str:
    host = urlparse(url).netloc
    return host[4:] if host.startswith("www.") else host


def _result_type(url: str, topic: str) -> str:
    if topic == "news":
        return "news"
    if any(domain in url for domain in VIDEO_DOMAINS):
        return "video"
    return "doc"


class TavilySearchProvider:
    def __init__(self, api_key: str, client=None):
        if client is None:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
        self._client = client

    def search(
        self,
        query: str,
        include_domains: list[str],
        max_results: int = 5,
        topic: str = "general",
    ) -> list[SearchResult]:
        try:
            response = self._client.search(
                query=query,
                include_domains=include_domains,
                max_results=max_results,
                topic=topic,
                search_depth="basic",
            )
        except Exception:
            return []

        results: list[SearchResult] = []
        for item in response.get("results", []):
            url = item.get("url", "")
            if not url:
                continue
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    site=item.get("site") or _site_from_url(url),
                    snippet=item.get("content", ""),
                    published_date=item.get("published_date"),
                    result_type=_result_type(url, topic),
                )
            )
        return results


def _is_nba_source(result: SearchResult) -> bool:
    if "espn.com" in result.url and "/nba/" not in result.url:
        return False
    return True


def news_search(provider: SearchProvider, query: str, days: int = 30) -> list[SearchResult]:
    try:
        results = provider.search(
            query,
            include_domains=NEWS_DOMAINS,
            max_results=5,
            topic="news",
        )
    except Exception:
        return []
    return [result for result in results if _is_nba_source(result)]


def video_search(provider: SearchProvider, query: str) -> list[SearchResult]:
    try:
        results = provider.search(
            query,
            include_domains=BILIBILI_DOMAINS,
            max_results=5,
            topic="general",
        )
    except Exception:
        results = []
    if results:
        return results
    try:
        return provider.search(
            query,
            include_domains=YOUTUBE_DOMAINS,
            max_results=5,
            topic="general",
        )
    except Exception:
        return []