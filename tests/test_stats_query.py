import sqlite3

import pytest

from app.tools.stats_query import StatsDB, _season_from_query, stats_query


@pytest.fixture
def stats_db(tmp_path, monkeypatch):
    path = tmp_path / "stats.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE player_per_game (
            season INTEGER, season_label TEXT, player TEXT, player_key TEXT,
            team TEXT, lg TEXT, g INTEGER, pts_per_game REAL,
            trb_per_game REAL, ast_per_game REAL, stl_per_game REAL,
            blk_per_game REAL, x3p_per_game REAL, fg_percent REAL,
            x3p_percent REAL, ft_percent REAL
        );
        CREATE TABLE player_advanced (
            season INTEGER, player TEXT, player_key TEXT, team TEXT,
            ts_percent REAL, per REAL, ws REAL
        );
        CREATE TABLE player_totals (
            season INTEGER, player TEXT, player_key TEXT, team TEXT,
            g INTEGER, pts INTEGER, trb INTEGER, ast INTEGER
        );
        CREATE TABLE player_career_info (
            player TEXT, player_key TEXT, "from" INTEGER, "to" INTEGER, hof INTEGER
        );
        CREATE TABLE team_summaries (
            season INTEGER, team TEXT, abbreviation TEXT, w REAL, l REAL,
            o_rtg REAL, d_rtg REAL, n_rtg REAL, pace REAL, playoffs INTEGER
        );
        CREATE TABLE player_award_shares (
            season INTEGER, player TEXT, player_key TEXT, award TEXT,
            share REAL, winner INTEGER
        );
        CREATE TABLE all_star_selections (
            season INTEGER, player TEXT, player_key TEXT
        );
        CREATE TABLE end_of_season_teams (
            season INTEGER, player TEXT, player_key TEXT, type TEXT,
            number_tm INTEGER
        );
        """
    )
    conn.executemany(
        "INSERT INTO player_per_game VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (2027, "2026-27", "Stephen Curry", "stephen curry", "GSW", "NBA", 5, 29.2, 3.8, 4.0, 1.2, 0.3, 4.8, 0.47, 0.40, 0.91),
            (2026, "2025-26", "Stephen Curry", "stephen curry", "GSW", "NBA", 43, 26.6, 3.6, 4.7, 1.1, 0.4, 4.4, 0.45, 0.39, 0.93),
            (2027, "2026-27", "Luka Doncic", "luka doncic", "LAL", "NBA", 6, 33.0, 8.1, 9.2, 1.5, 0.5, 3.1, 0.49, 0.35, 0.78),
            (2027, "2026-27", None, None, None, "NBA", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ],
    )
    conn.executemany(
        "INSERT INTO player_advanced VALUES (?,?,?,?,?,?,?)",
        [
            (2027, "Stephen Curry", "stephen curry", "GSW", 0.62, 24.5, 1.2),
            (2026, "Stephen Curry", "stephen curry", "GSW", 0.60, 22.1, 4.8),
        ],
    )
    conn.executemany(
        "INSERT INTO player_totals VALUES (?,?,?,?,?,?,?,?)",
        [
            (2026, "Stephen Curry", "stephen curry", "GSW", 43, 1144, 155, 202),
            (2027, "Stephen Curry", "stephen curry", "GSW", 5, 146, 19, 20),
            (2025, "Stephen Curry", "stephen curry", "2TM", 70, 1715, 308, 420),
        ],
    )
    conn.execute(
        'INSERT INTO player_career_info VALUES (?,?,?,?,?)',
        ("Stephen Curry", "stephen curry", 2009, 2026, 0),
    )
    conn.executemany(
        "INSERT INTO team_summaries VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (2027, "Golden State Warriors", "GSW", 3, 3, 117.7, 116.4, 1.3, 100.2, 0),
            (2027, "Boston Celtics", "BOS", 5, 1, 121.0, 108.0, 13.0, 99.0, 0),
            (2027, "Los Angeles Lakers", "LAL", 4, 2, 115.0, 112.0, 3.0, 101.0, 0),
            (2027, "Defunct Team", None, 0, 0, 0, 0, 0, 0, 0),
        ],
    )
    conn.executemany(
        "INSERT INTO player_award_shares VALUES (?,?,?,?,?,?)",
        [
            (2025, "Stephen Curry", "stephen curry", "nba mvp", 1.00, 1),
            (2024, "Stephen Curry", "stephen curry", "nba mvp", 0.62, 0),
        ],
    )
    conn.execute(
        "INSERT INTO all_star_selections VALUES (?,?,?)",
        (2026, "Stephen Curry", "stephen curry"),
    )
    conn.execute(
        "INSERT INTO end_of_season_teams VALUES (?,?,?,?,?)",
        (2025, "Stephen Curry", "stephen curry", "All-NBA", 1),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        "app.tools.stats_query.get_stats_db", lambda: StatsDB(path)
    )
    return path


def test_season_from_query_variants():
    assert _season_from_query("2026-27 赛季") == 2027
    assert _season_from_query("2025-2026") == 2026
    assert _season_from_query("2025年") == 2025
    assert _season_from_query("本赛季") is None


def test_player_season_stats(stats_db):
    results = stats_query("库里 2026-27 场均多少分")
    assert len(results) == 1
    assert results[0].result_type == "stats"
    assert "29.2" in results[0].snippet
    assert "2026-27" in results[0].title


def test_team_record(stats_db):
    results = stats_query("勇士 2026-27 战绩")
    assert len(results) == 1
    assert "3 胜 3 负" in results[0].snippet
    assert "117.7" in results[0].snippet


def test_team_standings_when_no_specific_team(stats_db):
    results = stats_query("2026-27 球队排名")
    assert len(results) == 1
    assert "Boston Celtics" in results[0].snippet
    assert results[0].snippet.index("Boston Celtics") < results[0].snippet.index(
        "Golden State Warriors"
    )


def test_career_totals_excludes_combined_rows(stats_db):
    results = stats_query("库里生涯总得分")
    assert "48 场" in results[0].snippet
    assert "1290 分" in results[0].snippet


def test_awards(stats_db):
    results = stats_query("库里有哪些荣誉")
    assert "nba mvp" in results[0].snippet
    assert "全明星" in results[0].snippet
    assert "All-NBA" in results[0].snippet
    assert "2023-24 nba mvp" not in results[0].snippet


def test_awards_beat_career_when_both_present(stats_db):
    results = stats_query("库里生涯荣誉")
    assert "nba mvp" in results[0].snippet


def test_league_leaders(stats_db):
    results = stats_query("2026-27 得分王")
    assert "1. 东契奇" in results[0].snippet
    assert "库里" in results[0].snippet


def test_unknown_query_returns_empty(stats_db):
    assert stats_query("今天天气怎么样") == []


def test_missing_db_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.tools.stats_query.get_stats_db",
        lambda: StatsDB(tmp_path / "missing.sqlite"),
    )
    assert stats_query("库里场均多少分") == []