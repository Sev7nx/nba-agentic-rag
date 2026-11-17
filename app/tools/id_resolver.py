import difflib
from functools import lru_cache

from nba_api.stats.static import players, teams

PLAYER_ALIASES = {
    "库里": "Stephen Curry",
    "斯蒂芬·库里": "Stephen Curry",
    "詹姆斯": "LeBron James",
    "勒布朗·詹姆斯": "LeBron James",
    "约基奇": "Nikola Jokic",
    "尼古拉·约基奇": "Nikola Jokic",
    "字母哥": "Giannis Antetokounmpo",
    "扬尼斯·阿德托昆博": "Giannis Antetokounmpo",
    "东契奇": "Luka Doncic",
    "卢卡·东契奇": "Luka Doncic",
    "塔图姆": "Jayson Tatum",
    "杜兰特": "Kevin Durant",
    "科比": "Kobe Bryant",
    "乔丹": "Michael Jordan",
    "恩比德": "Joel Embiid",
    "亚历山大": "Shai Gilgeous-Alexander",
    "文班亚马": "Victor Wembanyama",
}

TEAM_ALIASES = {
    "勇士": "GSW",
    "金州勇士": "GSW",
    "湖人": "LAL",
    "洛杉矶湖人": "LAL",
    "凯尔特人": "BOS",
    "波士顿凯尔特人": "BOS",
    "掘金": "DEN",
    "丹佛掘金": "DEN",
    "雄鹿": "MIL",
    "密尔沃基雄鹿": "MIL",
    "太阳": "PHX",
    "菲尼克斯太阳": "PHX",
    "独行侠": "DAL",
    "达拉斯独行侠": "DAL",
    "火箭": "HOU",
    "休斯顿火箭": "HOU",
    "尼克斯": "NYK",
    "热火": "MIA",
}


def _normalize(value: str) -> str:
    return value.strip().lower()


@lru_cache(maxsize=1)
def _all_players() -> list[dict]:
    return players.get_players()


@lru_cache(maxsize=1)
def _all_teams() -> list[dict]:
    return teams.get_teams()


def resolve_player(name: str) -> dict | None:
    query = PLAYER_ALIASES.get(name.strip(), name.strip())
    needle = _normalize(query)
    candidates = [
        player for player in _all_players() if _normalize(player["full_name"]) == needle
    ]
    if not candidates:
        names = [player["full_name"] for player in _all_players()]
        close = difflib.get_close_matches(query, names, n=1, cutoff=0.8)
        if close:
            candidates = [
                player for player in _all_players() if player["full_name"] == close[0]
            ]
    if not candidates:
        return None
    active = [player for player in candidates if player.get("is_active")]
    return (active or candidates)[0]


def resolve_team(name: str) -> dict | None:
    query = TEAM_ALIASES.get(name.strip(), name.strip())
    needle = _normalize(query)
    team_list = _all_teams()
    candidates = [
        team
        for team in team_list
        if _normalize(team["full_name"]) == needle
        or _normalize(team["abbreviation"]) == needle
    ]
    if not candidates:
        names = [team["full_name"] for team in team_list]
        close = difflib.get_close_matches(query, names, n=1, cutoff=0.8)
        if close:
            candidates = [team for team in team_list if team["full_name"] == close[0]]
    return candidates[0] if candidates else None