import argparse
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from scripts.build_stats_db import player_key

DATASET = "eoinamoore/historical-nba-data-and-player-box-scores"
CURRENT_DIR = ROOT / "data/current"
TEAM_CSV = CURRENT_DIR / "TeamStatistics.csv"
ESPN_PLAYERS = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/"
    "nba/statistics/byathlete?region=us&lang=en&contentorigin=espn"
    "&isqualified=false&page=1&limit=1000&sort=offensive.avgPoints%3Adesc"
)
ESPN_STANDINGS = (
    "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings"
    "?region=us&lang=en&contentorigin=espn"
)
SEASON = 2027
SEASON_LABEL = "2026-27"
SEASON_START = "2026-09-01"
TEAM_COLUMNS = [
    "gameId",
    "gameDateTimeEst",
    "teamCity",
    "teamName",
    "teamId",
    "opponentTeamId",
    "win",
    "teamScore",
    "opponentScore",
    "fieldGoalsAttempted",
    "freeThrowsAttempted",
    "reboundsOffensive",
    "turnovers",
    "seasonWins",
    "seasonLosses",
    "gameType",
    "numMinutes",
]


def _kaggle_command() -> list[str]:
    executable = Path(sys.executable).with_name(
        "kaggle.exe" if sys.platform == "win32" else "kaggle"
    )
    if executable.exists():
        return [str(executable)]
    return [sys.executable, "-m", "kaggle"]


def download_team_stats(force: bool = False) -> None:
    if (
        not force
        and TEAM_CSV.exists()
        and time.time() - TEAM_CSV.stat().st_mtime < 12 * 3600
    ):
        return
    CURRENT_DIR.mkdir(parents=True, exist_ok=True)
    command = _kaggle_command() + [
        "datasets",
        "download",
        "-d",
        DATASET,
        "-f",
        "TeamStatistics.csv",
        "-p",
        str(CURRENT_DIR),
        "--force" if force else "--quiet",
    ]
    try:
        subprocess.run(command, check=True)
    except Exception as exc:
        if not TEAM_CSV.exists():
            raise SystemExit(
                "无法下载 TeamStatistics.csv，请先手动运行 kaggle datasets download"
            ) from exc
        print(f"下载失败，继续使用已有文件：{exc}", file=sys.stderr)


def fetch_json(url: str) -> dict:
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def build_team_maps(
    conn: sqlite3.Connection,
    standings: dict,
) -> tuple[dict[str, str], dict[str, str]]:
    name_to_abbr: dict[str, str] = {}
    abbr_to_full: dict[str, str] = {}
    rows = conn.execute(
        "SELECT DISTINCT team, abbreviation FROM team_summaries "
        "WHERE season >= 2026 AND abbreviation IS NOT NULL AND team IS NOT NULL"
    ).fetchall()
    for team, abbreviation in rows:
        full = str(team)
        nickname = full.split()[-1]
        name_to_abbr[full.lower()] = abbreviation
        name_to_abbr[nickname.lower()] = abbreviation
        abbr_to_full.setdefault(abbreviation, full)
    for conference in standings.get("children", []):
        for entry in conference.get("standings", {}).get("entries", []):
            team = entry.get("team", {})
            abbreviation = team.get("abbreviation")
            display = team.get("displayName") or team.get("name")
            if not abbreviation or not display:
                continue
            short = team.get("shortDisplayName") or team.get("name") or ""
            name_to_abbr.setdefault(display.lower(), abbreviation)
            if short:
                name_to_abbr.setdefault(short.lower(), abbreviation)
            abbr_to_full.setdefault(abbreviation, display)
    return name_to_abbr, abbr_to_full


def _category_values(item: dict, definitions: dict[str, list[str]]) -> dict:
    values: dict = {}
    for category in item.get("categories", []):
        name = category.get("name")
        values[name] = dict(
            zip(definitions.get(name, []), category.get("values", []))
        )
    return values


def _number(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent(value):
    if value is None:
        return None
    return _number(value) / 100


def parse_players(payload: dict, name_to_abbr: dict[str, str]) -> list[dict]:
    definitions = {
        category.get("name"): category.get("names", [])
        for category in payload.get("categories", [])
    }
    players: list[dict] = []
    for item in payload.get("athletes", []):
        athlete = item.get("athlete", {})
        name = athlete.get("displayName") or " ".join(
            part
            for part in [athlete.get("firstName"), athlete.get("lastName")]
            if part
        )
        team_name = str(athlete.get("teamName") or "").strip()
        if not name or not team_name:
            continue
        nickname = team_name.split()[-1].lower()
        abbreviation = (
            name_to_abbr.get(nickname)
            or name_to_abbr.get(team_name.lower())
        )
        if not abbreviation:
            continue
        stats = _category_values(item, definitions)
        general = stats.get("general", {})
        offensive = stats.get("offensive", {})
        defensive = stats.get("defensive", {})
        games = int(_number(general.get("gamesPlayed")))
        if games <= 0:
            continue
        players.append(
            {
                "player": name,
                "player_key": player_key(name),
                "team": abbreviation,
                "g": games,
                "pts_per_game": _number(offensive.get("avgPoints")),
                "trb_per_game": _number(general.get("avgRebounds")),
                "ast_per_game": _number(offensive.get("avgAssists")),
                "stl_per_game": _number(defensive.get("avgSteals")),
                "blk_per_game": _number(defensive.get("avgBlocks")),
                "x3p_per_game": _number(
                    offensive.get("avgThreePointFieldGoalsMade")
                ),
                "fg_percent": _percent(offensive.get("fieldGoalPct")),
                "x3p_percent": _percent(
                    offensive.get("threePointFieldGoalPct")
                ),
                "ft_percent": _percent(offensive.get("freeThrowPct")),
                "pts": _number(offensive.get("points")),
                "trb": _number(general.get("rebounds")),
                "ast": _number(offensive.get("assists")),
            }
        )
    return players


def build_team_rows(
    frame: pd.DataFrame,
    name_to_abbr: dict[str, str],
    abbr_to_full: dict[str, str],
) -> tuple[list[dict], str]:
    frame = frame.copy()
    frame["gameDateTimeEst"] = pd.to_datetime(
        frame["gameDateTimeEst"], errors="coerce"
    )
    current = frame[
        (frame["gameDateTimeEst"] >= pd.Timestamp(SEASON_START))
        & (frame["gameType"] == "Regular Season")
    ].copy()
    if current.empty:
        return [], ""
    current["poss"] = (
        current["fieldGoalsAttempted"]
        + 0.44 * current["freeThrowsAttempted"]
        - current["reboundsOffensive"]
        + current["turnovers"]
    ).clip(lower=1)
    opponents = current[["gameId", "teamId", "poss"]].rename(
        columns={"teamId": "opponentTeamId", "poss": "opp_poss"}
    )
    current = current.merge(opponents, on=["gameId", "opponentTeamId"], how="left")
    current["opp_poss"] = current["opp_poss"].fillna(current["poss"])
    current["o_rtg"] = 100 * current["teamScore"] / current["poss"]
    current["d_rtg"] = 100 * current["opponentScore"] / current["opp_poss"]
    current["pace"] = (
        48
        * (current["poss"] + current["opp_poss"])
        / 2
        / (current["numMinutes"].fillna(240) / 5).clip(lower=1)
    )
    latest = current.sort_values("gameDateTimeEst").groupby("teamName").tail(1)
    latest = latest.set_index("teamName")
    aggregate = current.groupby("teamName").agg(
        teamCity=("teamCity", "first"),
        o_rtg=("o_rtg", "mean"),
        d_rtg=("d_rtg", "mean"),
        pace=("pace", "mean"),
    )
    rows: list[dict] = []
    for nickname, item in aggregate.iterrows():
        if nickname not in latest.index:
            continue
        abbreviation = (
            name_to_abbr.get(str(nickname).split()[-1].lower())
            or name_to_abbr.get(str(nickname).lower())
            or name_to_abbr.get(
                f"{item['teamCity']} {nickname}".lower()
            )
        )
        if not abbreviation:
            continue
        last = latest.loc[nickname]
        if isinstance(last, pd.DataFrame):
            last = last.iloc[-1]
        wins = int(_number(last.get("seasonWins")))
        losses = int(_number(last.get("seasonLosses")))
        o_rtg = float(item["o_rtg"])
        d_rtg = float(item["d_rtg"])
        rows.append(
            {
                "team": abbr_to_full.get(
                    abbreviation, f"{item['teamCity']} {nickname}"
                ),
                "abbreviation": abbreviation,
                "w": wins,
                "l": losses,
                "o_rtg": o_rtg,
                "d_rtg": d_rtg,
                "n_rtg": o_rtg - d_rtg,
                "pace": float(item["pace"]),
            }
        )
    as_of = current["gameDateTimeEst"].max()
    as_of_text = as_of.strftime("%Y-%m-%d") if pd.notna(as_of) else ""
    return rows, as_of_text


def update_db(
    db_path: Path,
    players: list[dict],
    teams: list[dict],
    as_of: str,
) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.execute("DELETE FROM player_per_game WHERE season=?", (SEASON,))
    conn.execute("DELETE FROM player_totals WHERE season=?", (SEASON,))
    conn.execute("DELETE FROM player_advanced WHERE season=?", (SEASON,))
    conn.execute(
        "DELETE FROM team_summaries WHERE season=? AND playoffs=0",
        (SEASON,),
    )
    conn.executemany(
        "INSERT INTO player_per_game "
        "(season, season_label, player, player_key, team, lg, g, "
        "pts_per_game, trb_per_game, ast_per_game, stl_per_game, "
        "blk_per_game, x3p_per_game, fg_percent, x3p_percent, ft_percent) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                SEASON,
                SEASON_LABEL,
                player["player"],
                player["player_key"],
                player["team"],
                "NBA",
                player["g"],
                player["pts_per_game"],
                player["trb_per_game"],
                player["ast_per_game"],
                player["stl_per_game"],
                player["blk_per_game"],
                player["x3p_per_game"],
                player["fg_percent"],
                player["x3p_percent"],
                player["ft_percent"],
            )
            for player in players
        ],
    )
    conn.executemany(
        "INSERT INTO player_totals "
        "(season, player, player_key, team, g, pts, trb, ast) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [
            (
                SEASON,
                player["player"],
                player["player_key"],
                player["team"],
                player["g"],
                player["pts"],
                player["trb"],
                player["ast"],
            )
            for player in players
        ],
    )
    conn.executemany(
        "INSERT INTO team_summaries "
        "(season, lg, team, abbreviation, playoffs, w, l, o_rtg, d_rtg, "
        "n_rtg, pace, season_label) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                SEASON,
                "NBA",
                team["team"],
                team["abbreviation"],
                0,
                team["w"],
                team["l"],
                team["o_rtg"],
                team["d_rtg"],
                team["n_rtg"],
                team["pace"],
                SEASON_LABEL,
            )
            for team in teams
        ],
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('as_of', ?)",
        (as_of,),
    )
    conn.commit()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="force re-download of TeamStatistics.csv",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="use the cached TeamStatistics.csv",
    )
    args = parser.parse_args()

    if not args.skip_download:
        download_team_stats(force=args.refresh)
    if not TEAM_CSV.exists():
        raise SystemExit(f"缺少 {TEAM_CSV}，请先下载 TeamStatistics.csv")

    players_payload = fetch_json(ESPN_PLAYERS)
    standings = fetch_json(ESPN_STANDINGS)
    db_path = Path(settings.stats_db_path)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    conn = sqlite3.connect(db_path)
    name_to_abbr, abbr_to_full = build_team_maps(conn, standings)
    conn.close()

    players = parse_players(players_payload, name_to_abbr)
    frame = pd.read_csv(TEAM_CSV, usecols=TEAM_COLUMNS)
    teams, as_of = build_team_rows(frame, name_to_abbr, abbr_to_full)
    if not players or not teams:
        raise SystemExit("没有解析到当前赛季数据")
    update_db(db_path, players, teams, as_of)
    print(
        f"updated {len(players)} players, {len(teams)} teams, "
        f"as_of {as_of}"
    )


if __name__ == "__main__":
    main()