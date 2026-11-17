def test_live_query_returns_games(monkeypatch):
    from app.tools import nba_live

    games = [
        {
            "gameId": "0022500001",
            "gameStatusText": "Final",
            "homeTeam": {"teamName": "Celtics", "teamTricode": "BOS", "score": 102},
            "awayTeam": {"teamName": "Magic", "teamTricode": "ORL", "score": 98},
        }
    ]
    monkeypatch.setattr(nba_live, "_fetch_scoreboard", lambda: games)
    nba_live._CACHE["ts"] = 0.0
    nba_live._CACHE["data"] = []

    results = nba_live.live_query("今天有什么比赛")
    assert len(results) == 1
    assert results[0].result_type == "live"
    assert "102" in results[0].snippet


def test_live_query_returns_empty_on_error(monkeypatch):
    from app.tools import nba_live

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(nba_live, "_fetch_scoreboard", boom)
    nba_live._CACHE["ts"] = 0.0
    nba_live._CACHE["data"] = []

    assert nba_live.live_query("今天有什么比赛") == []