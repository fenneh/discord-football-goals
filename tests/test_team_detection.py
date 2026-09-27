"""Tests for team detection functionality."""

import pytest
from src.services.reddit_service import find_team_in_title
from src.config.teams import premier_league_teams


@pytest.mark.parametrize(
    "title,expected_team",
    [
        # Basic team name matches
        ("Arsenal [2] - 1 Chelsea", "Arsenal"),
        ("Chelsea 1 - [2] Arsenal", "Arsenal"),
        ("Manchester United [1-0] Manchester City", "Manchester United"),
        # Team aliases
        ("The Gunners [1] - 0 Spurs", "Arsenal"),
        ("Man Utd [2] - 1 Man City", "Manchester United"),
        ("The Blues [1] - 0 Liverpool", "Chelsea"),
        ("Coventry City [1] - 0 Hull City", "Coventry City"),
        ("Ipswich Town [1] - 0 Arsenal", "Ipswich Town"),
        # Case insensitivity
        ("ARSENAL [1] - 0 Chelsea", "Arsenal"),
        ("arsenal [1] - 0 chelsea", "Arsenal"),
        # No false positives
        ("Villarreal [1] - 0 Real Madrid", None),  # Should not match Villa
        ("Aston Villa [1] - 0 Arsenal", "Aston Villa"),  # Should match Villa correctly
        ("Newcastle Jets [1] - 0 Sydney", None),  # Should not match Newcastle United
    ],
)
def test_team_detection(title: str, expected_team: str):
    """Test that team detection works correctly."""
    result = find_team_in_title(title)
    if expected_team is None:
        assert result is None
    else:
        assert result == expected_team


@pytest.mark.parametrize("team_name", premier_league_teams.keys())
def test_all_pl_teams_detectable(team_name: str):
    """Test that all Premier League teams can be detected."""
    title = f"{team_name} [1] - 0 Test Team"
    result = find_team_in_title(title)
    assert result == team_name


def test_team_with_brackets():
    """Test that team names with brackets are handled correctly."""
    title = "[Post Match Thread] Arsenal [2] - 1 Chelsea"
    result = find_team_in_title(title)
    assert result == "Arsenal"


def test_team_in_hashtags():
    """Test that team names in hashtags are not matched."""
    title = "#ARSCHE Arsenal [2] - 1 Chelsea"
    result = find_team_in_title(title)
    assert result == "Arsenal"


def test_partial_team_names():
    """Test that partial team names don't cause false matches."""
    for title in ["Villarreal", "Hampton", "Wolves", "West Ham United", "Burnley"]:
        assert find_team_in_title(f"{title} [1] - 0 Test Team") is None
