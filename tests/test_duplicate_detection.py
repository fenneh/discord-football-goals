"""Test duplicate detection with various title formats."""

from datetime import datetime, timezone, timedelta

import pytest

from src.utils.score_utils import (
    is_duplicate_score,
    extract_goal_info,
    generate_canonical_key,
)
from src.services.reddit_service import find_team_in_title


@pytest.mark.parametrize(
    "title1,title2,should_match,time_diff",
    [
        (
            "Tottenham 1 - [4] Liverpool - Mohamed Salah 54'",
            "Tottenham 1 - [4] Liverpool - Mohamed Salah 54'",
            True,
            180,
        ),
        (
            "Tottenham 0 - [2] Liverpool - A. Mac Allister 36'",
            "Tottenham Hotspur 0 - [2] Liverpool - Alexis Mac Allister 36'",
            True,
            180,
        ),
        (
            "Tottenham [1] - 2 Liverpool - J. Maddison 41'",
            "Tottenham Hotspur [1] - 2 Liverpool - James Maddison 41'",
            True,
            180,
        ),
        (
            "Tottenham 0 - [2] Liverpool - A. Mac Allister 36'",
            "Tottenham [1] - 2 Liverpool - J. Maddison 41'",
            False,
            180,
        ),
        (
            "Tottenham 0 - [1] Liverpool - L. Díaz 23'",
            "Tottenham Hotspur 0 - [1] Liverpool - Luis Diaz 23'",
            True,
            180,
        ),
        (
            "Aston Villa [2] - 0 Manchester City - M. Rogers 65'",
            "Aston Villa [2] - 0 Manchester City - Morgan Rogers 65'",
            True,
            30,
        ),
        (
            "Crystal Palace 1 - [5] Arsenal - D. Rice 84'",
            "Crystal Palace 1 - [5] Arsenal - Declan Rice 84'",
            True,
            30,
        ),
        (
            "Crystal Palace 1 - [4] Arsenal - Gabriel Martinelli 60'",
            "Crystal Palace 1 - [4] Arsenal - Gabriel Martinelli 60'",
            True,
            30,
        ),
        (
            "Crystal Palace 1 - [4] Arsenal - Gabriel Martinelli 60'",
            "Crystal Palace 1 - [5] Arsenal - D. Rice 84'",
            False,
            30,
        ),
        (
            "Manchester Utd 0 - [1] Bournemouth - Dean Huijsen 29'",
            "Manchester United 0 - [1] Bournemouth - Dean Huijsen 29'",
            True,
            30,
        ),
        (
            "Leeds 0 - [2] Wolves - Rodrigo Gomes 36'",
            "Leeds United 0 - [2] Wolves - Rodrigo Gomes 36'",
            True,
            30,
        ),
        (
            "Tottenham 1 - [4] Liverpool - Mohamed Salah 54'",
            "Tottenham 1 - [4] Liverpool - Mohamed Salah 54'",
            True,
            5,
        ),
        (
            "Tottenham 1 - [3] Liverpool - Jota 45+4'",
            "Tottenham 1 - [4] Liverpool - Salah 54'",
            False,
            180,
        ),
    ],
)
def test_duplicate_detection(title1, title2, should_match, time_diff):
    posted_scores = {}
    base_time = datetime.now(timezone.utc)

    info1 = extract_goal_info(title1)
    assert info1
    key1 = generate_canonical_key(info1)
    assert key1
    posted_scores[key1] = {
        "timestamp": base_time.isoformat(),
        "url": "https://example.com/post1",
        "reddit_url": "https://reddit.com/post1",
        "original_title": title1,
    }

    current_time = base_time + timedelta(seconds=time_diff)
    is_duplicate = is_duplicate_score(
        title2,
        posted_scores,
        current_time,
        url="https://example.com/post2",
    )

    assert is_duplicate == should_match


def test_team_logo_detection():
    """Test that we get the correct team logo for goals."""
    test_cases = [
        {
            "title": "Leeds United 0 - [1] Hull City - Player 19'",
            "expected_team": "Hull City",
            "expected_logo": "https://a.espncdn.com/i/teamlogos/soccer/500/306.png",
            "expected_is_scoring": True,
        }
    ]

    for case in test_cases:
        # Get team data with metadata
        result = find_team_in_title(case["title"], include_metadata=True)

        assert result is not None, "Failed to find any team"
        assert result["name"] == case["expected_team"], (
            f"Expected {case['expected_team']}, got {result['name']}"
        )
        assert result["data"]["logo"] == case["expected_logo"], "Wrong logo URL"
        assert result["is_scoring"] == case["expected_is_scoring"], "Wrong scoring flag"
