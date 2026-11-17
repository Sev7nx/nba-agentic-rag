import sqlite3
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE = Path("data/extra")
OUT = Path("data/stats.sqlite")

TABLES = {
    "player_per_game": "Player Per Game.csv",
    "player_totals": "Player Totals.csv",
    "player_advanced": "Advanced.csv",
    "team_summaries": "Team Summaries.csv",
    "team_stats_per_game": "Team Stats Per Game.csv",
    "player_career_info": "Player Career Info.csv",
    "player_award_shares": "Player Award Shares.csv",
    "all_star_selections": "All-Star Selections.csv",
    "end_of_season_teams": "End of Season Teams.csv",
}


def player_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(name))
    return normalized.encode("ascii", "ignore").decode().lower().strip()


def season_label(season) -> str:
    year = int(season)
    return f"{year - 1}-{str(year)[-2:]}"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(OUT)
    conn.execute("DROP TABLE IF EXISTS meta")
    for table, filename in TABLES.items():
        df = pd.read_csv(BASE / filename)
        if "player" in df.columns:
            df["player_key"] = df["player"].map(player_key)
        if "season" in df.columns:
            df["season"] = pd.to_numeric(df["season"], errors="coerce")
            df["season_label"] = df["season"].map(
                lambda value: season_label(value) if pd.notna(value) else ""
            )
        df.to_sql(table, conn, if_exists="replace", index=False)
        max_season = df["season"].max() if "season" in df.columns else "-"
        print(f"{table}: rows={len(df)}, max_season={max_season}")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_ppg_player ON player_per_game(player_key, season)",
        "CREATE INDEX IF NOT EXISTS idx_totals_player ON player_totals(player_key, season)",
        "CREATE INDEX IF NOT EXISTS idx_advanced_player ON player_advanced(player_key, season)",
        "CREATE INDEX IF NOT EXISTS idx_team_season ON team_summaries(abbreviation, season)",
        "CREATE INDEX IF NOT EXISTS idx_awards_player ON player_award_shares(player_key, season)",
        "CREATE INDEX IF NOT EXISTS idx_allstar_player ON all_star_selections(player_key, season)",
        "CREATE INDEX IF NOT EXISTS idx_eos_player ON end_of_season_teams(player_key, season)",
    ]
    for sql in indexes:
        conn.execute(sql)
    conn.commit()
    conn.close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()