from app.tools.id_resolver import entity_terms, resolve_player, resolve_team


def test_resolve_player_english():
    player = resolve_player("Stephen Curry")
    assert player is not None
    assert player["id"] == 201939


def test_resolve_player_chinese_alias():
    player = resolve_player("库里")
    assert player is not None
    assert player["id"] == 201939


def test_resolve_team_chinese_alias():
    team = resolve_team("勇士")
    assert team is not None
    assert team["abbreviation"] == "GSW"


def test_resolve_unknown_returns_none():
    assert resolve_player("不存在的球员") is None


def test_entity_terms_include_player_alias_and_english():
    terms = entity_terms("库里哪场比赛最经典")
    assert "库里" in terms
    assert "Stephen" in terms
    assert "Curry" in terms


def test_entity_terms_include_team_abbreviation():
    terms = entity_terms("勇士这赛季战绩怎么样")
    assert "勇士" in terms
    assert "GSW" in terms
    assert "Warriors" in terms