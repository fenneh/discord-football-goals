"""Tests for the competition registry, competition-scoped team lookup and
competition-prefixed canonical keys."""


from src.config.competitions import EPL, get_competition, list_competitions
from src.config.teams import get_teams_for_competition
from src.services.reddit_service import find_team_in_title
from src.utils.score_utils import (
    extract_goal_info,
    generate_canonical_key,
    migrate_legacy_scores,
)


def test_registry_has_only_epl():
    ids = {c.id for c in list_competitions()}
    assert ids == {"epl"}


def test_get_competition_lookup():
    assert get_competition("epl") is EPL


def test_epl_competition_fields():
    assert EPL.espn_league == "eng.1"
    assert EPL.schedule_title == "Premier League"


def test_teams_dict_lookup_by_competition_id():
    epl_teams = get_teams_for_competition(EPL.id)
    assert "Arsenal" in epl_teams


def test_2026_27_epl_teams():
    teams = get_teams_for_competition(EPL.id)
    assert len(teams) == 20
    assert {"Coventry City", "Hull City", "Ipswich Town"} <= teams.keys()
    assert not {"Burnley", "West Ham", "Wolves"} & teams.keys()


def test_find_team_in_title_returns_epl_competition():
    result = find_team_in_title(
        "Arsenal [2] - 0 Chelsea - Saka 45'", include_metadata=True
    )
    assert result is not None
    assert isinstance(result, dict)
    assert result["competition"].id == "epl"


def test_find_team_in_title_ignores_national_teams():
    """National teams aren't tracked — no competition should match them."""
    result = find_team_in_title(
        "Argentina [1] - 0 Brazil - Messi 23'", include_metadata=True
    )
    assert result is None


def test_find_team_in_title_no_match():
    assert find_team_in_title("Some random title with no team", include_metadata=True) is None


def test_canonical_key_carries_competition_prefix():
    info = extract_goal_info("Arsenal [1] - 0 Chelsea - Saka 45'")
    assert info is not None
    key = generate_canonical_key(info, "epl")
    assert key is not None
    assert key.startswith("epl:")


def test_migrate_legacy_scores_adds_epl_prefix():
    legacy = {"arsenal_vs_chelsea_1-0_45": {"timestamp": "x"}}
    assert migrate_legacy_scores(legacy) is True
    assert "epl:arsenal_vs_chelsea_1-0_45" in legacy
    assert "arsenal_vs_chelsea_1-0_45" not in legacy


def test_migrate_legacy_scores_is_idempotent():
    already = {"epl:arsenal_vs_chelsea_1-0_45": {"timestamp": "x"}}
    assert migrate_legacy_scores(already) is False
    assert "epl:arsenal_vs_chelsea_1-0_45" in already
