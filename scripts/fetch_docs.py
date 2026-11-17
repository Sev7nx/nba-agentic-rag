import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.tools.search import TavilySearchProvider

QUERIES = [
    {
        "doc_type": "game_report",
        "query": "NBA 比赛战报",
        "domains": ["hupu.com", "sports.qq.com", "espn.com"],
        "topic": "news",
    },
    {
        "doc_type": "game_report",
        "query": "勇士 比赛 战报",
        "domains": ["hupu.com", "sports.qq.com", "espn.com"],
        "topic": "news",
    },
    {
        "doc_type": "game_report",
        "query": "湖人 比赛 战报",
        "domains": ["hupu.com", "sports.qq.com", "espn.com"],
        "topic": "news",
    },
    {
        "doc_type": "game_report",
        "query": "掘金 比赛 战报",
        "domains": ["hupu.com", "sports.qq.com", "espn.com"],
        "topic": "news",
    },
    {
        "doc_type": "game_report",
        "query": "NBA game recap",
        "domains": ["espn.com", "hupu.com"],
        "topic": "news",
    },
    {
        "doc_type": "game_report",
        "query": "Warriors game recap",
        "domains": ["espn.com", "hupu.com"],
        "topic": "news",
    },
    {
        "doc_type": "game_report",
        "query": "Lakers game recap",
        "domains": ["espn.com", "hupu.com"],
        "topic": "news",
    },
    {
        "doc_type": "game_report",
        "query": "Nuggets game recap",
        "domains": ["espn.com", "hupu.com"],
        "topic": "news",
    },
    {
        "doc_type": "player_intro",
        "query": "斯蒂芬·库里 生涯 介绍",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
        "entity_aliases": ["库里", "Curry"],
    },
    {
        "doc_type": "player_intro",
        "query": "尼古拉·约基奇 生涯 介绍",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
        "entity_aliases": ["约基奇", "Jokic"],
    },
    {
        "doc_type": "player_intro",
        "query": "勒布朗·詹姆斯 生涯 介绍",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
        "entity_aliases": ["詹姆斯", "James", "LeBron"],
    },
    {
        "doc_type": "player_intro",
        "query": "扬尼斯·阿德托昆博 生涯 介绍",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
        "entity_aliases": ["字母哥", "Antetokounmpo", "Giannis"],
    },
    {
        "doc_type": "player_intro",
        "query": "卢卡·东契奇 生涯 介绍",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
        "entity_aliases": ["东契奇", "Doncic", "Luka"],
    },
    {
        "doc_type": "rules",
        "query": "NBA 三分线 规则",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "rules",
        "query": "NBA 附加赛 规则",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "rules",
        "query": "NBA 排名规则",
        "domains": ["baike.baidu.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "rules",
        "query": "NBA 罗斯条款 规则",
        "domains": ["baike.baidu.com", "hupu.com", "nba.com"],
        "topic": "general",
    },
    {
        "doc_type": "rules",
        "query": "Derrick Rose rule NBA rookie extension",
        "domains": ["nba.com", "espn.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "rules",
        "query": "罗斯条款",
        "domains": [
            "baike.baidu.com",
            "hupu.com",
            "hoopsrumors.com",
            "nba.com",
        ],
        "topic": "general",
    },
    {
        "doc_type": "tactic",
        "query": "NBA 挡拆 战术 分析",
        "domains": ["hupu.com", "sports.qq.com", "espn.com"],
        "topic": "general",
    },
    {
        "doc_type": "tactic",
        "query": "勇士 传切 战术 分析",
        "domains": ["hupu.com", "sports.qq.com", "espn.com"],
        "topic": "general",
    },
    {
        "doc_type": "tactic",
        "query": "NBA 区域联防 战术",
        "domains": ["hupu.com", "sports.qq.com", "espn.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "2016 NBA Finals Game 7 Cavaliers Warriors recap",
        "domains": ["espn.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "2016 总决赛 第七场 骑士 勇士 欧文 三分",
        "domains": ["hupu.com", "sports.qq.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "Stephen Curry 2016 Thunder game winner",
        "domains": ["espn.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "库里 2016 雷霆 绝杀",
        "domains": ["hupu.com", "sports.qq.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "Kobe Bryant 60 points final game 2016 recap",
        "domains": ["espn.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "科比 退役战 60 分 比赛回顾",
        "domains": ["hupu.com", "sports.qq.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "Michael Jordan last shot 1998 NBA Finals",
        "domains": ["espn.com", "nba.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "乔丹 最后一投",
        "domains": ["hupu.com", "baike.baidu.com", "sports.qq.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "San Antonio Spurs last championship 2014 Finals",
        "domains": ["espn.com", "nba.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "马刺 上一次 夺冠 2014 总决赛",
        "domains": ["hupu.com", "baike.baidu.com", "sports.qq.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "Kobe Bryant 81 points Raptors 2006",
        "domains": ["espn.com", "nba.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "Ray Allen 2013 NBA Finals Game 6 three pointer",
        "domains": ["espn.com", "nba.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "LeBron James block Andre Iguodala 2016 Finals Game 7",
        "domains": ["espn.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "NBA 经典比赛 历史 回顾 总决赛",
        "domains": ["hupu.com", "sports.qq.com", "baike.baidu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "Warriors 73 wins 2016 season",
        "domains": ["espn.com", "nba.com", "hupu.com"],
        "topic": "general",
    },
    {
        "doc_type": "game_report",
        "query": "库里 经典比赛 回顾",
        "domains": ["hupu.com", "sports.qq.com", "baike.baidu.com"],
        "topic": "general",
    },
]

BAD_GAME_TITLES = ["how to watch", "collection", "比分直播", "文字直播", "直播"]
GOOD_GAME_TITLES = [
    "game recap",
    "战报",
    "数据统计",
    "比赛回顾",
    "game 7",
    "finals",
    "经典",
    "最后一投",
    "60 points",
    "60 分",
    "81 points",
    "last shot",
    "flu game",
    "73 wins",
    "加时",
    "绝杀",
]


def _is_nba_url(url: str) -> bool:
    if "espn.com" in url and "/nba/" not in url:
        return False
    return True


def _is_useful(doc_type: str, title: str, text: str, item: dict) -> bool:
    lower = title.lower()
    if doc_type == "game_report":
        if any(bad in lower for bad in BAD_GAME_TITLES):
            return False
        return any(good in lower for good in GOOD_GAME_TITLES)
    if doc_type == "player_intro":
        aliases = item.get("entity_aliases") or [item.get("entity", "")]
        haystack = f"{title}\n{text[:2000]}".lower()
        return any(alias and alias.lower() in haystack for alias in aliases)
    if doc_type == "rules":
        return any(
            word in title for word in ["规则", "三分线", "附加赛", "条款", "罗斯"]
        )
    if doc_type == "tactic":
        return len(text) >= 500
    return len(text) >= 300


def fetch_documents(
    search_fn,
    extract_fn,
    queries,
    max_docs: int = 100,
    max_results: int = 3,
    pause: float = 1.0,
) -> list[dict]:
    docs: list[dict] = []
    seen: set[str] = set()

    for item in queries:
        if len(docs) >= max_docs:
            break
        results = search_fn(
            item["query"],
            item["domains"],
            max_results,
            item["topic"],
        )
        selected = []
        for result in results:
            if not _is_nba_url(result.url) or result.url in seen:
                continue
            seen.add(result.url)
            selected.append(result)
        if not selected:
            continue

        extracted = extract_fn([result.url for result in selected])
        for result in selected:
            text = (extracted.get(result.url) or "").strip()
            if not text or not _is_useful(item["doc_type"], result.title, text, item):
                continue
            docs.append(
                {
                    "doc_id": hashlib.sha256(
                        result.url.encode("utf-8")
                    ).hexdigest()[:12],
                    "doc_type": item["doc_type"],
                    "title": result.title,
                    "url": result.url,
                    "source": result.site
                    or urlparse(result.url).netloc,
                    "date": result.published_date or "",
                    "text": text,
                    "query": item["query"],
                    "as_of": date.today().isoformat(),
                }
            )
            if len(docs) >= max_docs:
                break
        time.sleep(pause)

    return docs


def main() -> None:
    provider = TavilySearchProvider(settings.tavily_api_key)
    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.tavily_api_key)

    def search(query, domains, max_results, topic):
        return provider.search(
            query,
            include_domains=domains,
            max_results=max_results,
            topic=topic,
        )

    def extract(urls):
        response = client.extract(
            urls=urls,
            extract_depth="advanced",
            format="markdown",
        )
        return {
            item["url"]: item.get("raw_content", "")
            for item in response.get("results", [])
        }

    docs = fetch_documents(search, extract, QUERIES)
    out = Path("data/docs/documents.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for doc in docs:
        counts[doc["doc_type"]] = counts.get(doc["doc_type"], 0) + 1
    print(f"wrote {len(docs)} documents to {out}")
    print("by type:", counts)
    for doc in docs[:10]:
        print("-", doc["doc_type"], "|", doc["source"], "|", doc["title"][:80])


if __name__ == "__main__":
    main()