"""ESPN API service for fetching match data, per competition."""

import json
from datetime import date
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.config.competitions import Competition, EPL
from src.utils.logger import setup_logger
from src.utils.match_utils import get_current_uk_time

espn_logger = setup_logger("espn_service", "espn.log")

SCOREBOARD_URL = "https://cdn.espn.com/core/soccer/scoreboard"


def fetch_matches_for_date(
    target_date: date, competition: Competition = EPL
) -> List[Dict[str, Any]]:
    """Fetch matches for a specific date in the given competition."""
    try:
        params = urlencode(
            {"xhr": "1", "league": competition.espn_league, "date": target_date.strftime("%Y%m%d")}
        )
        request = Request(f"{SCOREBOARD_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            data = json.load(response)["content"]["sbData"]
        matches = _parse_events(data["events"], competition)
        espn_logger.debug(
            f"Fetched {len(matches)} {competition.id} matches for {target_date}"
        )
        return matches
    except Exception as e:
        espn_logger.error(f"ESPN API request failed ({competition.id}): {e}")
        raise


def fetch_todays_matches(competition: Competition = EPL) -> List[Dict[str, Any]]:
    """Fetch matches in the given competition for today (UK timezone)."""
    today_uk = get_current_uk_time().date()
    return fetch_matches_for_date(today_uk, competition)


def _parse_events(
    events: List[Dict], competition: Competition
) -> List[Dict[str, Any]]:
    matches = []
    for event in events:
        try:
            match = _parse_single_event(event)
            if match:
                match["competition_id"] = competition.id
                matches.append(match)
        except Exception as e:
            espn_logger.error(f"Error parsing event {event.get('id', 'unknown')}: {e}")
    return matches


def _parse_single_event(event: Dict) -> Optional[Dict[str, Any]]:
    status_info = event.get("status", {}).get("type", {})

    match = {
        "id": event.get("id"),
        "name": event.get("name"),
        "short_name": event.get("shortName"),
        "date": event.get("date"),
        "status": status_info.get("name"),
        "status_description": status_info.get("description"),
        "home_team": None,
        "away_team": None,
        "goals": [],
    }

    competitions = event.get("competitions", [])
    if not competitions:
        return match

    competition = competitions[0]
    competitors = competition.get("competitors", [])
    for comp in competitors:
        team_data = comp.get("team", {})
        team_info = {
            "name": team_data.get("displayName"),
            "short_name": team_data.get("shortDisplayName"),
            "abbreviation": team_data.get("abbreviation"),
            "score": comp.get("score"),
            "logo": team_data.get("logo"),
        }

        if comp.get("homeAway") == "home":
            match["home_team"] = team_info
        else:
            match["away_team"] = team_info

    details = competition.get("details", [])
    team_names = {
        str(comp.get("team", {}).get("id")): comp.get("team", {}).get("displayName", "")
        for comp in competitors
    }
    match["goals"] = _parse_goal_events(details, team_names)

    return match


def _parse_goal_events(
    details: List[Dict], team_names: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    goals = []
    for detail in details:
        try:
            event_type = detail.get("type", {}).get("text", "").lower()
            if "goal" not in event_type:
                continue

            if "own goal" in event_type:
                continue

            clock = detail.get("clock", {})
            minute = clock.get("displayValue", "").replace("'", "").strip()

            scoring_team_data = detail.get("team", {})
            scoring_team = scoring_team_data.get("displayName") or (
                (team_names or {}).get(str(scoring_team_data.get("id")), "")
            )

            athletes = detail.get("athletesInvolved", [])
            scorer = (
                athletes[0].get("displayName", "Unknown") if athletes else "Unknown"
            )

            score_value = detail.get("scoreValue", 1)

            goal = {
                "minute": minute,
                "scorer": scorer,
                "team": scoring_team,
                "type": event_type,
                "score_value": score_value,
            }
            goals.append(goal)

        except Exception as e:
            espn_logger.error(f"Error parsing goal event: {e}")

    return goals


def get_match_display_name(match: Dict[str, Any]) -> str:
    home = match.get("home_team", {})
    away = match.get("away_team", {})
    home_name = home.get("name", "Unknown") if home else "Unknown"
    away_name = away.get("name", "Unknown") if away else "Unknown"
    return f"{home_name} vs {away_name}"


def get_match_score_display(match: Dict[str, Any]) -> str:
    home = match.get("home_team", {})
    away = match.get("away_team", {})
    home_name = home.get("name", "Unknown") if home else "Unknown"
    away_name = away.get("name", "Unknown") if away else "Unknown"
    home_score = home.get("score", "0") if home else "0"
    away_score = away.get("score", "0") if away else "0"
    return f"{home_name} {home_score} - {away_score} {away_name}"
