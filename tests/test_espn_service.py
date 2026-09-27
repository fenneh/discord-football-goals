"""Tests for ESPN service parsing functions."""

import io
import json
from datetime import date

import pytest

from src.config.competitions import EPL
from src.services import espn_service
from src.services.espn_service import (
    _parse_goal_events,
    _parse_single_event,
    get_match_display_name,
    get_match_score_display,
)


def test_fetch_matches_uses_cdn_scoreboard(monkeypatch):
    event = {
        "id": "123",
        "date": "2026-09-20T13:00Z",
        "status": {"type": {"name": "STATUS_SCHEDULED"}},
        "competitions": [],
    }
    response = {"content": {"sbData": {"events": [event]}}}

    def fake_urlopen(request, timeout):
        assert request.full_url == (
            "https://cdn.espn.com/core/soccer/scoreboard"
            "?xhr=1&league=eng.1&date=20260920"
        )
        assert timeout == 15
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(espn_service, "urlopen", fake_urlopen)
    matches = espn_service.fetch_matches_for_date(date(2026, 9, 20))
    assert [match["id"] for match in matches] == ["123"]


def test_fetch_failure_is_not_an_empty_match_day(monkeypatch):
    def fail_urlopen(request, timeout):
        raise OSError("feed unavailable")

    monkeypatch.setattr(espn_service, "urlopen", fail_urlopen)
    with pytest.raises(OSError, match="feed unavailable"):
        espn_service.fetch_matches_for_date(date(2026, 9, 20), EPL)


def _make_detail(event_type: str, minute: str, team: str, athletes: list, score_value: int = 1) -> dict:
    return {
        "type": {"text": event_type},
        "clock": {"displayValue": minute},
        "team": {"displayName": team},
        "athletesInvolved": athletes,
        "scoreValue": score_value,
    }


def _make_athlete(name: str) -> dict:
    return {"displayName": name}


class TestParseGoalEvents:
    def test_regular_goal_included(self):
        details = [_make_detail("Goal", "45'", "Arsenal", [_make_athlete("Bukayo Saka")])]
        goals = _parse_goal_events(details)
        assert len(goals) == 1
        assert goals[0]["scorer"] == "Bukayo Saka"
        assert goals[0]["minute"] == "45"
        assert goals[0]["team"] == "Arsenal"

    def test_own_goal_excluded(self):
        details = [_make_detail("Own Goal", "32'", "Chelsea", [_make_athlete("Reece James")])]
        goals = _parse_goal_events(details)
        assert len(goals) == 0

    def test_own_goal_case_insensitive(self):
        details = [_make_detail("own goal", "60'", "Liverpool", [_make_athlete("Someone")])]
        goals = _parse_goal_events(details)
        assert len(goals) == 0

    def test_non_goal_event_excluded(self):
        details = [_make_detail("Yellow Card", "12'", "Arsenal", [_make_athlete("Saka")])]
        goals = _parse_goal_events(details)
        assert len(goals) == 0

    def test_penalty_goal_included(self):
        details = [_make_detail("Penalty Goal", "74'", "Manchester City", [_make_athlete("Erling Haaland")])]
        goals = _parse_goal_events(details)
        assert len(goals) == 1
        assert goals[0]["scorer"] == "Erling Haaland"

    def test_minute_stripped_of_apostrophe(self):
        details = [_make_detail("Goal", "67'", "Tottenham", [_make_athlete("Son Heung-Min")])]
        goals = _parse_goal_events(details)
        assert goals[0]["minute"] == "67"

    def test_injury_time_minute_preserved(self):
        details = [_make_detail("Goal", "90+3'", "Liverpool", [_make_athlete("Mohamed Salah")])]
        goals = _parse_goal_events(details)
        assert goals[0]["minute"] == "90+3"

    def test_no_athletes_yields_unknown_scorer(self):
        details = [_make_detail("Goal", "55'", "Chelsea", [])]
        goals = _parse_goal_events(details)
        assert len(goals) == 1
        assert goals[0]["scorer"] == "Unknown"

    def test_multiple_goals_all_included(self):
        details = [
            _make_detail("Goal", "23'", "Arsenal", [_make_athlete("Kai Havertz")]),
            _make_detail("Goal", "67'", "Arsenal", [_make_athlete("Bukayo Saka")]),
        ]
        goals = _parse_goal_events(details)
        assert len(goals) == 2

    def test_mixed_events_only_goals_returned(self):
        details = [
            _make_detail("Yellow Card", "10'", "Arsenal", [_make_athlete("Saka")]),
            _make_detail("Goal", "23'", "Arsenal", [_make_athlete("Kai Havertz")]),
            _make_detail("Own Goal", "45'", "Chelsea", [_make_athlete("Gusto")]),
            _make_detail("Red Card", "78'", "Chelsea", [_make_athlete("Chalobah")]),
            _make_detail("Goal", "89'", "Chelsea", [_make_athlete("Cole Palmer")]),
        ]
        goals = _parse_goal_events(details)
        assert len(goals) == 2
        assert goals[0]["scorer"] == "Kai Havertz"
        assert goals[1]["scorer"] == "Cole Palmer"

    def test_score_value_included(self):
        details = [_make_detail("Goal", "55'", "Arsenal", [_make_athlete("Saka")], score_value=2)]
        goals = _parse_goal_events(details)
        assert goals[0]["score_value"] == 2

    def test_empty_details_returns_empty(self):
        assert _parse_goal_events([]) == []


class TestParseEvent:
    def _make_event(self, home_name: str, away_name: str, home_score: str = "1", away_score: str = "0") -> dict:
        return {
            "id": "abc123",
            "name": f"{home_name} vs {away_name}",
            "shortName": f"{home_name[:3].upper()} @ {away_name[:3].upper()}",
            "date": "2026-04-30T15:00Z",
            "status": {"type": {"name": "STATUS_FIRST_HALF", "description": "1st Half"}},
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": home_score,
                            "team": {
                                "displayName": home_name,
                                "shortDisplayName": home_name[:6],
                                "abbreviation": home_name[:3].upper(),
                                "logo": f"https://example.com/{home_name}.png",
                            },
                        },
                        {
                            "homeAway": "away",
                            "score": away_score,
                            "team": {
                                "displayName": away_name,
                                "shortDisplayName": away_name[:6],
                                "abbreviation": away_name[:3].upper(),
                                "logo": f"https://example.com/{away_name}.png",
                            },
                        },
                    ],
                    "details": [],
                }
            ],
        }

    def test_home_away_assigned_correctly(self):
        event = self._make_event("Arsenal", "Chelsea")
        match = _parse_single_event(event)
        assert match["home_team"]["name"] == "Arsenal"
        assert match["away_team"]["name"] == "Chelsea"

    def test_scores_populated(self):
        event = self._make_event("Arsenal", "Chelsea", home_score="2", away_score="1")
        match = _parse_single_event(event)
        assert match["home_team"]["score"] == "2"
        assert match["away_team"]["score"] == "1"

    def test_match_id_and_date(self):
        event = self._make_event("Liverpool", "Tottenham")
        match = _parse_single_event(event)
        assert match["id"] == "abc123"
        assert match["date"] == "2026-04-30T15:00Z"

    def test_goals_parsed_from_details(self):
        event = self._make_event("Arsenal", "Chelsea")
        event["competitions"][0]["details"] = [
            _make_detail("Goal", "30'", "Arsenal", [_make_athlete("Saka")])
        ]
        match = _parse_single_event(event)
        assert len(match["goals"]) == 1

    def test_goal_team_id_resolves_to_team_name(self):
        event = self._make_event("Arsenal", "Chelsea")
        event["competitions"][0]["competitors"][0]["team"]["id"] = "359"
        event["competitions"][0]["details"] = [
            {
                "type": {"text": "Goal"},
                "clock": {"displayValue": "30'"},
                "team": {"id": "359"},
                "athletesInvolved": [_make_athlete("Saka")],
            }
        ]
        match = _parse_single_event(event)
        assert match["goals"][0]["team"] == "Arsenal"

    def test_no_competitions_returns_match_with_none_teams(self):
        event = {
            "id": "x",
            "name": "Test",
            "shortName": "T",
            "date": "2026-04-30T15:00Z",
            "status": {"type": {"name": "STATUS_SCHEDULED", "description": "Scheduled"}},
            "competitions": [],
        }
        match = _parse_single_event(event)
        assert match["home_team"] is None
        assert match["away_team"] is None


class TestMatchDisplayHelpers:
    def _make_match(self, home: str, away: str, home_score: str = "0", away_score: str = "0") -> dict:
        return {
            "home_team": {"name": home, "score": home_score},
            "away_team": {"name": away, "score": away_score},
        }

    def test_display_name(self):
        match = self._make_match("Arsenal", "Chelsea")
        assert get_match_display_name(match) == "Arsenal vs Chelsea"

    def test_score_display(self):
        match = self._make_match("Arsenal", "Chelsea", "2", "1")
        assert get_match_score_display(match) == "Arsenal 2 - 1 Chelsea"

    def test_missing_teams_use_unknown(self):
        match = {"home_team": None, "away_team": None}
        assert get_match_display_name(match) == "Unknown vs Unknown"
        assert get_match_score_display(match) == "Unknown 0 - 0 Unknown"
