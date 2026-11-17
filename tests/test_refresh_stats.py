import sqlite3

import pandas as pd

from app.tools.stats_query import StatsDB
from scripts.refresh_stats import build_team_rows, parse_players


def _payload():
    return {
        "categories": [
            {
                "name": "general",
                "names": ["gamesPlayed", "avgRebounds", "rebounds"],
            },
            {
                "name": "offensive",
                "names": [
                    "avgPoints",
                    "avgAssists",
                    "avgThreePointFieldGoalsMade",
                    "fieldGoalPct",
                    "threePointFieldGoalPct",
                    "freeThrowPct",
                    "points",
                    "assists",
                ],
            },
            {
                "name": "defensive",
                "names": ["avgSteals", "avgBlocks"],
            },
        ],
        "athletes": [
            {
                "athlete": {
                    "displayName": "Stephen Curry",
                    "teamName": "Warriors",
                },
                "categories": [
                    {
                        "name": "general",
                        "values": [10, 3.7, 37],
                    },
                    {
                        "name": "offensive",
                        "values": [27.8, 3.9, 4.3, 50.0, 45.7, 98.7, 278, 39],
                    },
                    {
                        "name": "defensive",
                        "values": [0.9, 0.1],
                    },
                ],
            }
        ],
    }


def test_parse_players_maps_espn_values():
    rows = parse_players(_payload(), {"warriors": "GSW"})
    assert len(rows) == 1
    row = rows[0]
    assert row["player"] == "Stephen Curry"
    assert row["team"] == "GSW"
    assert row["g"] == 10
    assert row["pts_per_game"] == 27.8
    assert row["trb_per_game"] == 3.7
    assert row["ast_per_game"] == 3.9
    assert row["fg_percent"] == 0.5
    assert row["pts"] == 278
    assert row["trb"] == 37
    assert row["ast"] == 39


def test_build_team_rows_aggregates_record_and_efficiency():
    frame = pd.DataFrame(
        [
            {
                "gameId": 1,
                "gameDateTimeEst": "2026-11-01 19:00:00",
                "teamCity": "Golden State",
                "teamName": "Warriors",
                "teamId": 1,
                "opponentTeamId": 2,
                "win": 1,
                "teamScore": 110,
                "opponentScore": 100,
                "fieldGoalsAttempted": 80,
                "freeThrowsAttempted": 20,
                "reboundsOffensive": 10,
                "turnovers": 12,
                "seasonWins": 1,
                "seasonLosses": 0,
                "gameType": "Regular Season",
                "numMinutes": 240,
            },
            {
                "gameId": 1,
                "gameDateTimeEst": "2026-11-01 19:00:00",
                "teamCity": "Boston",
                "teamName": "Celtics",
                "teamId": 2,
                "opponentTeamId": 1,
                "win": 0,
                "teamScore": 100,
                "opponentScore": 110,
                "fieldGoalsAttempted": 85,
                "freeThrowsAttempted": 18,
                "reboundsOffensive": 9,
                "turnovers": 14,
                "seasonWins": 0,
                "seasonLosses": 1,
                "gameType": "Regular Season",
                "numMinutes": 240,
            },
        ]
    )
    rows, as_of = build_team_rows(
        frame,
        {"warriors": "GSW", "celtics": "BOS"},
        {"GSW": "Golden State Warriors", "BOS": "Boston Celtics"},
    )
    assert as_of == "2026-11-01"
    by_team = {row["abbreviation"]: row for row in rows}
    assert by_team["GSW"]["w"] == 1
    assert by_team["GSW"]["l"] == 0
    assert by_team["GSW"]["o_rtg"] > by_team["GSW"]["d_rtg"]
    assert by_team["BOS"]["w"] == 0


def test_stats_db_as_of_reads_meta(tmp_path):
    path = tmp_path / "stats.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('as_of', '2026-11-15')")
    conn.commit()
    conn.close()
    assert StatsDB(path).as_of() == "2026-11-15"