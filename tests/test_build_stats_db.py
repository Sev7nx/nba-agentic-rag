from scripts.build_stats_db import player_key, season_label


def test_player_key_strips_accents_and_case():
    assert player_key("Nikola Jokić") == "nikola jokic"
    assert player_key("Luka Dončić") == "luka doncic"


def test_season_label_uses_end_year():
    assert season_label(2027) == "2026-27"
    assert season_label("2025") == "2024-25"