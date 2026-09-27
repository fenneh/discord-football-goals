from datetime import datetime, timedelta, timezone

import pytest

from src.config.competitions import EPL
from src.services import match_notification_service as notifications


@pytest.mark.asyncio
async def test_failed_fixture_fetch_does_not_mark_schedule_posted(monkeypatch):
    service = notifications.MatchNotificationService.__new__(
        notifications.MatchNotificationService
    )
    service.daily_posted = {}
    service.password_reset_today = {}

    monkeypatch.setattr(
        notifications,
        "get_current_uk_time",
        lambda: datetime(2026, 9, 20, 8, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(notifications, "get_today_uk_date_str", lambda: "2026-09-20")

    def fail_fetch(competition):
        raise OSError("feed unavailable")

    monkeypatch.setattr(notifications, "fetch_todays_matches", fail_fetch)

    await service.check_and_notify()
    assert service.daily_posted == {}


@pytest.mark.asyncio
async def test_kickoff_posts_once(monkeypatch):
    service = notifications.MatchNotificationService.__new__(
        notifications.MatchNotificationService
    )
    service.notified_events = set()
    service._get_streams_password = lambda: None
    posted = []

    async def post_embed(**kwargs):
        posted.append(kwargs)
        return True

    service._post_embed = post_embed
    monkeypatch.setattr(notifications, "save_data", lambda *args: None)
    match = {
        "id": "123",
        "date": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "status": "STATUS_IN_PROGRESS",
        "home_team": {"name": "Coventry City"},
        "away_team": {"name": "Hull City"},
    }

    await service._check_kickoffs_by_time([match], EPL)
    await service._check_kickoffs_by_time([match], EPL)

    assert len(posted) == 1
    assert posted[0]["title"] == "KICK-OFF"
    assert "Coventry City vs Hull City" in posted[0]["description"]
    assert service.notified_events == {"123_kickoff"}
