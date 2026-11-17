import re
import sqlite3
import unicodedata
from pathlib import Path

from app.config import settings
from app.tools.base import SearchResult
from app.tools.id_resolver import (
    PLAYER_ALIASES,
    TEAM_ALIASES,
    resolve_player,
    resolve_team,
)

SOURCE_URL = "https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats"
SOURCE_SITE = "kaggle.com"


def _as_of() -> str:
    return settings.stats_as_of


def _stamp(snippet: str) -> str:
    return f"数据截至 {_as_of()}。{snippet}"


def _norm(value) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    return normalized.encode("ascii", "ignore").decode().lower().strip()


def _season_from_query(query: str) -> int | None:
    match = re.search(r"(20\d{2})\s*[-–/]\s*(\d{2,4})", query)
    if match:
        return int(match.group(1)) + 1
    match = re.search(r"(19|20)\d{2}", query)
    if match:
        return int(match.group(0))
    return None


def _fmt(value, digits=1, scale=1.0) -> str:
    try:
        return f"{float(value) * scale:.{digits}f}"
    except (TypeError, ValueError):
        return "-"


class StatsDB:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._conn = None
        self._player_names = None
        self._team_names = None

    def _connect(self):
        if self._conn is None:
            if not self._path.exists():
                raise FileNotFoundError(self._path)
            self._conn = sqlite3.connect(self._path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def current_season(self) -> int:
        row = self._connect().execute(
            "SELECT MAX(season) FROM player_per_game"
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 2027

    def _season_label(self, season: int) -> str:
        return f"{season - 1}-{str(season)[-2:]}"

    def find_player_name(self, query: str) -> str | None:
        for alias in sorted(PLAYER_ALIASES, key=len, reverse=True):
            if alias in query:
                player = resolve_player(alias)
                if player:
                    return player["full_name"]
        if self._player_names is None:
            rows = self._connect().execute(
                "SELECT DISTINCT player FROM player_per_game"
            ).fetchall()
            self._player_names = [row[0] for row in rows]
        lowered = query.lower()
        for name in self._player_names:
            if name and name.lower() in lowered:
                return name
        player = resolve_player(query.strip())
        return player["full_name"] if player else None

    def find_team(self, query: str) -> dict | None:
        for alias in sorted(TEAM_ALIASES, key=len, reverse=True):
            if alias in query:
                team = resolve_team(alias)
                if team:
                    return team
        if self._team_names is None:
            rows = self._connect().execute(
                "SELECT DISTINCT team, abbreviation FROM team_summaries"
            ).fetchall()
            self._team_names = [(row[0], row[1]) for row in rows]
        lowered = query.lower()
        for name, abbreviation in self._team_names:
            if not name or not abbreviation:
                continue
            if name.lower() in lowered or abbreviation.lower() in lowered:
                return {"full_name": name, "abbreviation": abbreviation}
        return None

    def player_season(self, player_name: str, season: int):
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM player_per_game WHERE player_key=? AND season=? "
            "ORDER BY CASE WHEN team LIKE '%TM' THEN 0 ELSE 1 END LIMIT 1",
            (_norm(player_name), season),
        ).fetchone()
        if row is None:
            return None
        advanced = conn.execute(
            "SELECT * FROM player_advanced WHERE player_key=? AND season=? "
            "ORDER BY CASE WHEN team LIKE '%TM' THEN 0 ELSE 1 END LIMIT 1",
            (_norm(player_name), season),
        ).fetchone()
        label = self._season_label(season)
        parts = [
            f"{row['player']}（{row['team']}），{label} 赛季：",
            f"{row['g']} 场，场均 {_fmt(row['pts_per_game'])} 分、"
            f"{_fmt(row['trb_per_game'])} 篮板、{_fmt(row['ast_per_game'])} 助攻",
            f"投篮 {_fmt(row['fg_percent'], scale=100)}%、"
            f"三分 {_fmt(row['x3p_percent'], scale=100)}%、"
            f"罚球 {_fmt(row['ft_percent'], scale=100)}%",
        ]
        if advanced is not None:
            parts.append(
                f"TS% {_fmt(advanced['ts_percent'], scale=100)}%、"
                f"PER {_fmt(advanced['per'])}、WS {_fmt(advanced['ws'])}"
            )
        return SearchResult(
            title=f"{row['player']} {label} 赛季数据",
            url=SOURCE_URL,
            site=SOURCE_SITE,
            snippet=_stamp(" ".join(parts)),
            published_date=_as_of(),
            result_type="stats",
        )

    def player_career(self, player_name: str):
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM player_totals WHERE player_key=? "
            "AND team NOT LIKE '%TM' ORDER BY season",
            (_norm(player_name),),
        ).fetchall()
        if not rows:
            return None
        total_g = sum(row["g"] or 0 for row in rows)
        total_pts = sum(row["pts"] or 0 for row in rows)
        total_trb = sum(row["trb"] or 0 for row in rows)
        total_ast = sum(row["ast"] or 0 for row in rows)
        info = conn.execute(
            'SELECT "from" AS from_year, "to" AS to_year, hof '
            "FROM player_career_info WHERE player_key=? LIMIT 1",
            (_norm(player_name),),
        ).fetchone()
        name = rows[-1]["player"]
        span = ""
        if info and info["from_year"] and info["to_year"]:
            span = f"，{int(info['from_year'])}-{int(info['to_year'])}"
        snippet = (
            f"{name} 生涯{span}：{int(total_g)} 场，{int(total_pts)} 分、"
            f"{int(total_trb)} 篮板、{int(total_ast)} 助攻"
        )
        if info is not None:
            snippet += f"；名人堂：{'是' if info['hof'] else '否'}"
        return SearchResult(
            title=f"{name} 生涯数据",
            url=SOURCE_URL,
            site=SOURCE_SITE,
            snippet=_stamp(snippet),
            published_date=_as_of(),
            result_type="stats",
        )

    def team_summary(self, abbreviation: str, season: int):
        row = self._connect().execute(
            "SELECT * FROM team_summaries WHERE abbreviation=? AND season=? "
            "AND playoffs=0 LIMIT 1",
            (abbreviation, season),
        ).fetchone()
        if row is None:
            return None
        label = self._season_label(season)
        snippet = (
            f"{row['team']}，{label} 常规赛：{int(row['w'] or 0)} 胜 "
            f"{int(row['l'] or 0)} 负，进攻效率 {_fmt(row['o_rtg'])}，"
            f"防守效率 {_fmt(row['d_rtg'])}，净效率 {_fmt(row['n_rtg'])}，"
            f"节奏 {_fmt(row['pace'])}"
        )
        return SearchResult(
            title=f"{row['team']} {label} 战绩",
            url=SOURCE_URL,
            site=SOURCE_SITE,
            snippet=_stamp(snippet),
            published_date=_as_of(),
            result_type="stats",
        )

    def team_standings(self, season: int):
        rows = self._connect().execute(
            "SELECT * FROM team_summaries WHERE season=? AND playoffs=0 "
            "ORDER BY w DESC, n_rtg DESC LIMIT 8",
            (season,),
        ).fetchall()
        if not rows:
            return None
        label = self._season_label(season)
        parts = [
            f"{index + 1}. {row['team']} {int(row['w'] or 0)}-{int(row['l'] or 0)}"
            for index, row in enumerate(rows)
        ]
        return SearchResult(
            title=f"{label} 球队战绩前 8",
            url=SOURCE_URL,
            site=SOURCE_SITE,
            snippet=_stamp("；".join(parts)),
            published_date=_as_of(),
            result_type="stats",
        )

    def player_awards(self, player_name: str):
        conn = self._connect()
        key = _norm(player_name)
        rows = conn.execute(
            "SELECT * FROM player_award_shares WHERE player_key=? AND winner=1 "
            "ORDER BY season DESC LIMIT 8",
            (key,),
        ).fetchall()
        allstars = conn.execute(
            "SELECT COUNT(*) AS count, MAX(season) AS latest "
            "FROM all_star_selections WHERE player_key=?",
            (key,),
        ).fetchone()
        teams = conn.execute(
            "SELECT season, type, number_tm FROM end_of_season_teams "
            "WHERE player_key=? ORDER BY season DESC LIMIT 8",
            (key,),
        ).fetchall()
        if not rows and not (allstars and allstars["count"]) and not teams:
            return None
        parts = []
        for row in rows:
            parts.append(
                f"{self._season_label(row['season'])} {row['award']}"
                f"（share {_fmt(row['share'], 2)}）"
            )
        if allstars and allstars["count"]:
            latest = self._season_label(allstars["latest"])
            parts.append(f"全明星 {int(allstars['count'])} 次（最近 {latest}）")
        for row in teams:
            parts.append(
                f"{self._season_label(row['season'])} {row['type']} "
                f"{row['number_tm']}"
            )
        return SearchResult(
            title=f"{player_name} 荣誉",
            url=SOURCE_URL,
            site=SOURCE_SITE,
            snippet=_stamp("；".join(parts[:10])),
            published_date=_as_of(),
            result_type="stats",
        )

    def league_leaders(self, metric: str, season: int):
        columns = {
            "得分": "pts_per_game",
            "篮板": "trb_per_game",
            "助攻": "ast_per_game",
            "抢断": "stl_per_game",
            "盖帽": "blk_per_game",
            "三分": "x3p_per_game",
        }
        column = columns.get(metric, "pts_per_game")
        rows = self._connect().execute(
            f"SELECT player, team, {column} AS value FROM player_per_game "
            "WHERE season=? AND lg='NBA' ORDER BY value DESC LIMIT 5",
            (season,),
        ).fetchall()
        if not rows:
            return None
        label = self._season_label(season)
        parts = [
            f"{index + 1}. {row['player']}（{row['team']}）{_fmt(row['value'])}"
            for index, row in enumerate(rows)
        ]
        return SearchResult(
            title=f"{label} {metric}榜前 5",
            url=SOURCE_URL,
            site=SOURCE_SITE,
            snippet=_stamp("；".join(parts)),
            published_date=_as_of(),
            result_type="stats",
        )


def get_stats_db() -> StatsDB:
    return StatsDB(settings.stats_db_path)


def stats_query(query: str) -> list[SearchResult]:
    try:
        db = get_stats_db()
        season = _season_from_query(query) or db.current_season()
        player = db.find_player_name(query)
        team = db.find_team(query)
        if any(word in query for word in ["排名", "战绩", "第几", "standings"]):
            if team:
                result = db.team_summary(team["abbreviation"], season)
                if result:
                    return [result]
            result = db.team_standings(season)
            return [result] if result else []
        if any(
            word in query
            for word in ["奖", "全明星", "MVP", "最佳阵容", "荣誉"]
        ):
            if player:
                result = db.player_awards(player)
                if result:
                    return [result]
        if any(word in query for word in ["生涯", "career"]):
            if player:
                result = db.player_career(player)
                if result:
                    return [result]
        if any(
            word in query
            for word in ["得分王", "助攻王", "篮板王", "三分王", "领先"]
        ):
            metric = next(
                (
                    word
                    for word in ["得分", "助攻", "篮板", "三分"]
                    if word in query
                ),
                "得分",
            )
            result = db.league_leaders(metric, season)
            return [result] if result else []
        if player:
            result = db.player_season(player, season)
            return [result] if result else []
        if team:
            result = db.team_summary(team["abbreviation"], season)
            return [result] if result else []
    except Exception:
        return []
    return []