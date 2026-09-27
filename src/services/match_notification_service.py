"""Match notification service. ESPN-driven daily schedule, kickoff, full-time,
and goal-fallback posts. Iterates configured competitions; per-fixture state is
keyed by ESPN match id (globally unique) and per-competition where it isn't."""

import asyncio
import os
import random
from datetime import datetime, timezone
from typing import Dict, Set, Any, Optional, List

import aiohttp

from src.config import (
    DISCORD_WEBHOOK_URL,
    DISCORD_USERNAME,
    DISCORD_AVATAR_URL,
    DATA_DIR,
    POSTED_SCORES_FILE,
    POST_DELAY_SECONDS,
    STREAMS_URL,
    STREAMS_PASSWORD_FILE,
)
from src.config.competitions import Competition, EPL, list_competitions
from src.services.espn_service import (
    fetch_todays_matches,
    get_match_display_name,
    get_match_score_display,
    espn_logger,
)
from src.utils.match_utils import (
    map_espn_team_to_config,
    format_match_time_uk,
    get_current_uk_time,
    get_today_uk_date_str,
)
from src.utils.persistence import save_data, load_data
from src.utils.logger import webhook_logger
from src.utils.score_utils import normalize_team_name, normalize_player_name

# Persistence files (single-file shared across competitions; keys partitioned
# either by globally-unique match id or by an explicit competition prefix).
MATCH_STATE_FILE = os.path.join(DATA_DIR, "match_states.pkl")
DAILY_POSTED_FILE = os.path.join(DATA_DIR, "daily_schedule_posted.pkl")
NOTIFIED_EVENTS_FILE = os.path.join(DATA_DIR, "notified_events.pkl")
KNOWN_GOALS_FILE = os.path.join(DATA_DIR, "known_goals.pkl")
PENDING_GOALS_FILE = os.path.join(DATA_DIR, "pending_goals.pkl")
ESPN_COVERED_GOALS_FILE = os.path.join(DATA_DIR, "espn_covered_goals.pkl")

# Goal fallback timing
GOAL_FALLBACK_SECONDS = 30


def _daily_posted_key(date_str: str, competition: Competition) -> str:
    return f"{date_str}:{competition.id}"


class MatchNotificationService:
    """Service for managing match notifications across all configured competitions."""

    def __init__(self):
        # match_id keys are globally unique across ESPN leagues, so a single dict is fine.
        self.match_states: Dict[str, str] = load_data(MATCH_STATE_FILE, {})
        # Keyed "{date}:{competition_id}" so each competition posts its own schedule daily.
        self.daily_posted: Dict[str, bool] = load_data(DAILY_POSTED_FILE, {})
        self.notified_events: Set[str] = set(load_data(NOTIFIED_EVENTS_FILE, []))
        self.known_goals: Dict[str, List[str]] = load_data(KNOWN_GOALS_FILE, {})
        self.pending_goals: Dict[str, Dict[str, Any]] = load_data(
            PENDING_GOALS_FILE, {}
        )
        self.password_reset_today: Dict[str, bool] = {}

    def _generate_streams_password(self) -> str:
        """Generate a new streams password and save to file."""
        password = f"imperium{random.randint(1000, 9999)}"
        today = get_today_uk_date_str()
        try:
            with open(STREAMS_PASSWORD_FILE, "w") as f:
                f.write(f"{today}\n{password}\n")
            espn_logger.info("Generated new streams password")
        except Exception as e:
            espn_logger.error(f"Error writing streams password: {e}")
        return password

    def _get_streams_password(self) -> Optional[str]:
        """Read current streams password from file."""
        try:
            with open(STREAMS_PASSWORD_FILE, "r") as f:
                lines = f.read().strip().split("\n")
                if len(lines) >= 2:
                    return lines[1]
        except FileNotFoundError:
            pass
        except Exception as e:
            espn_logger.error(f"Error reading streams password: {e}")
        return None

    async def _reset_streams_password(self) -> Optional[str]:
        """Reset the streams password and post to Discord webhook."""
        today_str = get_today_uk_date_str()

        if self.password_reset_today.get(today_str):
            return None

        password = f"imperium{random.randint(1000, 9999)}"

        try:
            with open(STREAMS_PASSWORD_FILE, "w") as f:
                f.write(f"{today_str}\n{password}\n")
            espn_logger.info(f"Reset streams password for {today_str}")
        except Exception as e:
            espn_logger.error(f"Failed to write password: {e}")
            return None

        await self._post_password_webhook(password)
        self.password_reset_today[today_str] = True
        return password

    async def _post_password_webhook(self, password: str) -> None:
        if not DISCORD_WEBHOOK_URL:
            return

        streams_url = STREAMS_URL or "https://sports.imperium-eu.com"

        embed = {
            "title": "Daily Password Reset",
            "description": f"**Password:** `{password}`\n\n**Watch:** {streams_url}",
            "color": EPL.color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        webhook_data = {
            "username": DISCORD_USERNAME,
            "avatar_url": DISCORD_AVATAR_URL,
            "embeds": [embed],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DISCORD_WEBHOOK_URL, json=webhook_data
                ) as response:
                    if response.status == 204:
                        espn_logger.info("Posted password reset to Discord")
                    else:
                        espn_logger.error(
                            f"Failed to post password reset: {response.status}"
                        )
        except Exception as e:
            espn_logger.error(f"Error posting password webhook: {e}")

    async def check_and_notify(self) -> None:
        """Main check method — called from periodic loop."""
        try:
            now_uk = get_current_uk_time()
            today_str = get_today_uk_date_str()

            # Password reset stays bound to EPL streams (Imperium-specific).
            if now_uk.hour == 7 and now_uk.minute >= 50:
                await self._reset_streams_password()

            for competition in list_competitions():
                matches = fetch_todays_matches(competition)
                espn_logger.info(
                    f"ESPN check ({competition.id}): found {len(matches)} matches"
                )

                if now_uk.hour >= 8 and _daily_posted_key(
                    today_str, competition
                ) not in self.daily_posted:
                    await self._post_daily_schedule(today_str, competition, matches)

                await self._check_kickoffs_by_time(matches, competition)

                for match in matches:
                    try:
                        await self._check_for_fulltime(match, competition)
                        await self._check_for_goals(match, competition)
                    except Exception as e:
                        espn_logger.error(
                            f"Error checking match {match.get('id')}: {e}"
                        )

            await self._process_pending_goals()

        except Exception as e:
            espn_logger.error(f"Error in match notification check: {e}")

    async def _post_daily_schedule(
        self, date_str: str, competition: Competition, matches: List[Dict[str, Any]]
    ) -> None:
        """Post the daily schedule of matches for one competition."""
        try:
            posted_key = _daily_posted_key(date_str, competition)
            if not matches:
                espn_logger.info(
                    f"No {competition.id} matches scheduled for {date_str}"
                )
                self.daily_posted[posted_key] = True
                save_data(self.daily_posted, DAILY_POSTED_FILE)
                return

            schedule_lines = []
            for match in sorted(matches, key=lambda m: m.get("date", "")):
                kick_off = format_match_time_uk(match.get("date", ""))
                match_name = get_match_display_name(match)
                schedule_lines.append(f"**{kick_off}** - {match_name}")

            description = "\n".join(schedule_lines)

            streams_url = STREAMS_URL or "https://sports.imperium-eu.com"
            password = self._get_streams_password()
            if password:
                description += (
                    f"\n\n**Watch Live:** {streams_url}\n**Password:** `{password}`"
                )

            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                formatted_date = dt.strftime("%-d %b %Y")
            except Exception:
                formatted_date = date_str

            success = await self._post_embed(
                title=f"{competition.schedule_title} - {formatted_date}",
                description=description,
                color=competition.color,
                thumbnail_url=competition.logo,
            )

            if success:
                self.daily_posted[posted_key] = True
                save_data(self.daily_posted, DAILY_POSTED_FILE)
                espn_logger.info(
                    f"Posted {competition.id} daily schedule for {date_str}"
                )

        except Exception as e:
            espn_logger.error(f"Error posting daily schedule: {e}")

    def _parse_match_time(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            return datetime.fromisoformat(date_str)
        except Exception:
            return None

    async def _check_kickoffs_by_time(
        self, matches: List[Dict[str, Any]], competition: Competition
    ) -> None:
        """Check for kick-offs based on scheduled time and post batched by time slot."""
        now = datetime.now(timezone.utc)
        time_slots: Dict[str, List[Dict[str, Any]]] = {}

        for match in matches:
            match_id = match.get("id")
            if not match_id:
                continue

            event_key = f"{match_id}_kickoff"
            if event_key in self.notified_events:
                continue

            scheduled_time = self._parse_match_time(match.get("date"))
            if not scheduled_time:
                continue

            status = match.get("status")
            if now >= scheduled_time and status != "STATUS_FULL_TIME":
                time_key = scheduled_time.isoformat()
                if time_key not in time_slots:
                    time_slots[time_key] = []
                time_slots[time_key].append(match)

        for _time_key, slot_matches in time_slots.items():
            await self._notify_kickoffs_batched(slot_matches, competition)

    async def _notify_kickoffs_batched(
        self, matches: List[Dict[str, Any]], competition: Competition
    ) -> None:
        if not matches:
            return

        match_names = [get_match_display_name(m) for m in matches]
        description = "\n".join(match_names)

        streams_url = STREAMS_URL or "https://sports.imperium-eu.com"
        password = self._get_streams_password()
        if password:
            description += (
                f"\n\n**Watch Live:** {streams_url}\n**Password:** `{password}`"
            )

        title = "KICK-OFF" if len(matches) == 1 else "KICK-OFFS"

        success = await self._post_embed(
            title=title,
            description=description,
            color=0x00FF00,  # Keep green for kick-off across competitions
            thumbnail_url=competition.logo,
        )

        if success:
            for match in matches:
                match_id = match.get("id")
                event_key = f"{match_id}_kickoff"
                self.notified_events.add(event_key)
            save_data(list(self.notified_events), NOTIFIED_EVENTS_FILE)
            espn_logger.info(
                f"Posted {competition.id} kick-offs: {', '.join(match_names)}"
            )

    async def _check_for_fulltime(
        self, match: Dict[str, Any], competition: Competition
    ) -> None:
        match_id = match.get("id")
        if not match_id:
            return

        current_status = match.get("status")
        previous_status = self.match_states.get(match_id)

        if (
            current_status == "STATUS_FULL_TIME"
            and previous_status != "STATUS_FULL_TIME"
        ):
            espn_logger.info(
                f"Match {match_id} ended: {previous_status} -> {current_status}"
            )
            await self._notify_final_score(match, competition)

        if previous_status != current_status and current_status is not None:
            self.match_states[match_id] = current_status
            save_data(self.match_states, MATCH_STATE_FILE)

    async def _notify_final_score(
        self, match: Dict[str, Any], competition: Competition
    ) -> None:
        match_id = match.get("id")
        event_key = f"{match_id}_fulltime"

        if event_key in self.notified_events:
            return

        score_display = get_match_score_display(match)

        success = await self._post_embed(
            title="FULL TIME",
            description=score_display,
            color=0x808080,
            thumbnail_url=competition.logo,
        )

        if success:
            self.notified_events.add(event_key)
            save_data(list(self.notified_events), NOTIFIED_EVENTS_FILE)
            espn_logger.info(f"Posted full time ({competition.id}): {score_display}")

    async def _check_for_goals(
        self, match: Dict[str, Any], competition: Competition
    ) -> None:
        """Check for new goals in a match and add to pending if not covered by Reddit."""
        match_id = match.get("id")
        if not match_id:
            return

        status = match.get("status")
        if status not in (
            "STATUS_FIRST_HALF",
            "STATUS_SECOND_HALF",
            "STATUS_HALFTIME",
        ):
            return

        home_team = match.get("home_team", {})
        away_team = match.get("away_team", {})
        home_name = home_team.get("name", "Unknown")
        away_name = away_team.get("name", "Unknown")
        home_score = home_team.get("score", "0")
        away_score = away_team.get("score", "0")

        goals = match.get("goals", [])
        if not goals:
            return

        if match_id not in self.known_goals:
            self.known_goals[match_id] = []

        for goal in goals:
            try:
                goal_key = self._generate_goal_key(match, goal, competition)
                if not goal_key:
                    continue

                if goal_key in self.known_goals[match_id]:
                    continue

                espn_logger.info(f"New goal detected: {goal_key}")
                self.known_goals[match_id].append(goal_key)
                save_data(self.known_goals, KNOWN_GOALS_FILE)

                posted_scores = load_data(POSTED_SCORES_FILE, {})
                if self._reddit_posted_goal(goal_key, {}, posted_scores):
                    espn_logger.info(
                        f"Reddit already covered goal, skipping pending: {goal_key}"
                    )
                    continue

                self.pending_goals[goal_key] = {
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "match_id": match_id,
                    "competition_id": competition.id,
                    "home_team": home_name,
                    "away_team": away_name,
                    "home_score": home_score,
                    "away_score": away_score,
                    "scorer": goal.get("scorer", "Unknown"),
                    "minute": goal.get("minute", ""),
                    "scoring_team": goal.get("team", ""),
                }
                save_data(self.pending_goals, PENDING_GOALS_FILE)
                espn_logger.info(f"Added goal to pending: {goal_key}")

            except Exception as e:
                espn_logger.error(f"Error processing goal: {e}")

    def _generate_goal_key(
        self,
        match: Dict[str, Any],
        goal: Dict[str, Any],
        competition: Competition,
    ) -> Optional[str]:
        """Format: {competition_id}:{team_a}_vs_{team_b}_{scorer}_{minute}.

        Mirrors the canonical-key prefix used by Reddit-side dedup so
        _reddit_posted_goal can match across both sources.
        """
        try:
            home_team = match.get("home_team", {})
            away_team = match.get("away_team", {})
            home_name = normalize_team_name(home_team.get("name", ""))
            away_name = normalize_team_name(away_team.get("name", ""))
            scorer = normalize_player_name(goal.get("scorer", ""))
            minute = goal.get("minute", "").split("+")[0]

            if not home_name or not away_name or not minute or not scorer:
                return None

            teams_key = "_vs_".join(sorted([home_name, away_name]))
            return f"{competition.id}:{teams_key}_{scorer}_{minute}"

        except Exception as e:
            espn_logger.error(f"Error generating goal key: {e}")
            return None

    async def _process_pending_goals(self) -> None:
        if not self.pending_goals:
            return

        now = datetime.now(timezone.utc)
        posted_scores = load_data(POSTED_SCORES_FILE, {})
        goals_to_remove = []

        for goal_key, goal_data in self.pending_goals.items():
            try:
                detected_at = datetime.fromisoformat(goal_data["detected_at"])
                elapsed = (now - detected_at).total_seconds()

                if self._reddit_posted_goal(goal_key, goal_data, posted_scores):
                    espn_logger.info(f"Reddit covered goal: {goal_key}")
                    goals_to_remove.append(goal_key)
                    continue

                if elapsed < GOAL_FALLBACK_SECONDS:
                    continue

                espn_logger.info(
                    f"Reddit didn't cover goal after {GOAL_FALLBACK_SECONDS}s, posting fallback: {goal_key}"
                )
                await self._post_goal_fallback(goal_data)
                goals_to_remove.append(goal_key)

            except Exception as e:
                espn_logger.error(f"Error processing pending goal {goal_key}: {e}")
                goals_to_remove.append(goal_key)

        for key in goals_to_remove:
            if key in self.pending_goals:
                del self.pending_goals[key]

        if goals_to_remove:
            save_data(self.pending_goals, PENDING_GOALS_FILE)

    def _reddit_posted_goal(
        self, goal_key: str, goal_data: Dict[str, Any], posted_scores: Dict[str, Dict]
    ) -> bool:
        """Check if Reddit posted a matching goal.

        Both ESPN and Reddit keys carry the same {competition_id}: prefix, so
        comparing parts[0] verbatim implicitly also requires same competition.
        """
        if not posted_scores:
            return False

        parts = goal_key.rsplit("_", 2)
        if len(parts) != 3:
            return False

        teams_key, _, minute = parts

        try:
            goal_minute = int(minute)
        except ValueError:
            return False

        for reddit_key in posted_scores.keys():
            reddit_parts = reddit_key.rsplit("_", 2)
            if len(reddit_parts) != 3:
                continue

            reddit_teams, _, reddit_minute = reddit_parts

            if reddit_teams != teams_key:
                continue

            try:
                reddit_min = int(reddit_minute)
                if abs(reddit_min - goal_minute) <= 2:
                    espn_logger.debug(
                        f"Found Reddit match: {reddit_key} for ESPN goal at minute {goal_minute}"
                    )
                    return True
            except ValueError:
                continue

        return False

    async def _post_goal_fallback(self, goal_data: Dict[str, Any]) -> None:
        from src.config.competitions import get_competition

        home_team = goal_data.get("home_team", "Unknown")
        away_team = goal_data.get("away_team", "Unknown")
        home_score = goal_data.get("home_score", "0")
        away_score = goal_data.get("away_score", "0")
        scorer = goal_data.get("scorer", "Unknown")
        minute = goal_data.get("minute", "")
        scoring_team = goal_data.get("scoring_team", "")
        comp_id = goal_data.get("competition_id", EPL.id)

        try:
            competition = get_competition(comp_id)
        except KeyError:
            competition = EPL

        team_data = map_espn_team_to_config(scoring_team, competition)

        score_line = f"{home_team} {home_score} - {away_score} {away_team}"
        scorer_line = f"{scorer} {minute}'" if minute else scorer
        description = f"{score_line}\n{scorer_line}"

        color = 0x00FF00
        thumbnail_url = competition.logo
        if team_data and "data" in team_data:
            color = team_data["data"].get("color", color)
            thumbnail_url = team_data["data"].get("logo", thumbnail_url)

        # Pre-mark covered_key so the Reddit path won't duplicate this goal
        # while we wait out POST_DELAY_SECONDS.
        home_norm = normalize_team_name(home_team)
        away_norm = normalize_team_name(away_team)
        teams_key = "_vs_".join(sorted([home_norm, away_norm]))
        base_minute = minute.split("+")[0] if minute else ""
        if teams_key and base_minute:
            covered_key = f"{competition.id}:{teams_key}_{base_minute}"
            covered_goals = load_data(ESPN_COVERED_GOALS_FILE, {})
            covered_goals[covered_key] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scorer": scorer,
                "score": f"{home_score}-{away_score}",
            }
            save_data(covered_goals, ESPN_COVERED_GOALS_FILE)
            espn_logger.info(f"Tracked ESPN-covered goal: {covered_key}")

        if POST_DELAY_SECONDS > 0:
            espn_logger.info(f"Delaying ESPN fallback post by {POST_DELAY_SECONDS}s")
            await asyncio.sleep(POST_DELAY_SECONDS)

        await self._post_embed(
            title="GOAL!",
            description=description,
            color=color,
            thumbnail_url=thumbnail_url,
        )

    async def _post_embed(
        self,
        title: str,
        description: str,
        color: int = 0x808080,
        thumbnail_url: Optional[str] = None,
    ) -> bool:
        if not DISCORD_WEBHOOK_URL:
            webhook_logger.error("Discord webhook URL not configured")
            return False

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}

        webhook_data = {
            "username": DISCORD_USERNAME,
            "avatar_url": DISCORD_AVATAR_URL,
            "embeds": [embed],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DISCORD_WEBHOOK_URL, json=webhook_data
                ) as response:
                    if response.status == 429:
                        webhook_logger.warning(
                            f"Rate limited by Discord. Retry after: {response.headers.get('Retry-After', 'unknown')} seconds"
                        )
                        return False

                    if response.status != 204:
                        response_text = await response.text()
                        webhook_logger.error(
                            f"Failed to post to Discord. Status: {response.status}, Response: {response_text}"
                        )
                        return False

                    webhook_logger.info(f"Successfully posted embed: {title}")
                    return True

        except Exception as e:
            webhook_logger.error(f"Error posting embed to Discord: {e}")
            return False

    def cleanup_old_states(self, days: int = 7) -> None:
        today = get_today_uk_date_str()
        old_keys = [
            k for k in self.daily_posted.keys() if k.split(":", 1)[0] < today
        ]
        for key in old_keys:
            del self.daily_posted[key]
        if old_keys:
            save_data(self.daily_posted, DAILY_POSTED_FILE)
            espn_logger.debug(
                f"Cleaned up {len(old_keys)} old daily_posted entries"
            )


# Global service instance
match_notification_service = MatchNotificationService()
