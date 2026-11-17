import time
from datetime import datetime

from app.tools.base import SearchResult

_CACHE: dict = {"ts": 0.0, "data": []}
_CACHE_TTL_SECONDS = 30


def _fetch_scoreboard() -> list[dict]:
    from nba_api.live.nba.endpoints import scoreboard

    return scoreboard.ScoreBoard().games.get_dict()


def live_scoreboard(max_games: int = 8) -> list[SearchResult]:
    now = time.time()
    if _CACHE["data"] and now - _CACHE["ts"] < _CACHE_TTL_SECONDS:
        games = _CACHE["data"]
    else:
        try:
            games = _fetch_scoreboard()
        except Exception:
            return []
        _CACHE["ts"] = now
        _CACHE["data"] = games

    results: list[SearchResult] = []
    for game in games[:max_games]:
        home = game.get("homeTeam", {}) or {}
        away = game.get("awayTeam", {}) or {}
        game_id = game.get("gameId", "")
        title = f"{away.get('teamName', '')} vs {home.get('teamName', '')}".strip()
        snippet = (
            f"{game.get('gameStatusText', '')}；"
            f"{away.get('teamTricode', '')} {away.get('score', '')} - "
            f"{home.get('teamTricode', '')} {home.get('score', '')}"
        ).strip()
        url = (
            f"https://www.nba.com/game/{game_id}"
            if game_id
            else "https://www.nba.com/games"
        )
        results.append(
            SearchResult(
                title=title or "NBA live game",
                url=url,
                site="nba.com",
                snippet=snippet,
                published_date=datetime.now().strftime("%Y-%m-%d"),
                result_type="live",
            )
        )
    return results


def live_query(query: str) -> list[SearchResult]:
    return live_scoreboard()