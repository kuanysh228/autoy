from dataclasses import dataclass, field
from pathlib import Path

import pytest

from autoy.bot.commands import HELP_TEXT, CommandRouter
from autoy.config import Settings
from autoy.storage import BotStore, PostRegistry


@dataclass
class FakeContext:
    settings: Settings
    registry: PostRegistry


@dataclass
class FakeService:
    ctx: FakeContext
    store: BotStore
    sent: list[tuple[str, int]] = field(default_factory=list)
    started: list[tuple] = field(default_factory=list)

    @property
    def settings(self) -> Settings:
        return self.ctx.settings

    def is_authorized(self, chat_id: int) -> bool:
        return chat_id == 1

    def send(self, text: str, chat_id: int | None = None) -> None:
        self.sent.append((text, chat_id))

    def daily_limit(self) -> int:
        return int(self.store.get_setting("max_posts_per_day", "5"))

    def review_enabled(self) -> bool:
        return self.store.get_setting("review_enabled", "1") == "1"

    def weekly_setting(self, key: str, default: str) -> str:
        return self.store.get_setting(f"weekly_{key}", default)

    def run_shorts_background(self, channel: str, topic: str | None, chat_id: int, schedule_id=None) -> None:
        self.started.append(("shorts", channel, topic))

    def run_weekly_background(self, channel: str, chat_id: int) -> None:
        self.started.append(("weekly", channel))


@pytest.fixture
def router(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[CommandRouter, FakeService]:
    monkeypatch.setenv("AUTOY_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    settings = Settings.from_env()
    service = FakeService(FakeContext(settings, PostRegistry(tmp_path / "p.db")), BotStore(tmp_path / "b.db"))
    return CommandRouter(service), service


def last_reply(service: FakeService) -> str:
    return service.sent[-1][0]


def test_unauthorized(router):
    cmd, service = router
    cmd.dispatch(2, "/status")
    assert last_reply(service) == "Access denied."


def test_help_and_unknown(router):
    cmd, service = router
    cmd.dispatch(1, "/help@autoy_bot")
    assert last_reply(service) == HELP_TEXT
    cmd.dispatch(1, "/nope")
    assert last_reply(service) == "Unknown command. /help"


def test_schedule_lifecycle(router):
    cmd, service = router
    cmd.dispatch(1, "/schedule_add geo 10:00")
    assert "Added: id=1" in last_reply(service)
    cmd.dispatch(1, "/schedule_add geo 25:00")
    assert last_reply(service) == "Error: Invalid time"
    cmd.dispatch(1, "/schedule_add nope 10:00")
    assert last_reply(service).startswith("Error: Unknown channel")
    cmd.dispatch(1, "/schedule_off 1")
    cmd.dispatch(1, "/schedule")
    assert "1. 10:00 | geo | off" in last_reply(service)
    cmd.dispatch(1, "/schedule_remove 1")
    assert last_reply(service) == "Removed."
    cmd.dispatch(1, "/schedule_clear")
    assert last_reply(service) == "Schedule cleared."


def test_limit_review_and_weekly_settings(router):
    cmd, service = router
    cmd.dispatch(1, "/limit 3")
    assert last_reply(service) == "Daily video limit: 3"
    cmd.dispatch(1, "/limit 500")
    assert last_reply(service).startswith("Error")
    cmd.dispatch(1, "/review off")
    assert last_reply(service) == "Review mode: off"
    cmd.dispatch(1, "/weekly_set time 12:30")
    cmd.dispatch(1, "/weekly_set enabled off")
    cmd.dispatch(1, "/weekly")
    reply = last_reply(service)
    assert "Time:    12:30" in reply and "disabled" in reply


def test_create_and_weekly_now_spawn_background(router, monkeypatch: pytest.MonkeyPatch):
    cmd, service = router
    monkeypatch.setattr("autoy.bot.commands._spawn", lambda target, *args: target(*args))
    cmd.dispatch(1, "/create ai Nvidia earnings")
    cmd.dispatch(1, "/create custom topic")
    cmd.dispatch(1, "/weekly_now")
    assert service.started == [("shorts", "ai", "Nvidia earnings"), ("shorts", "geo", "custom topic"), ("weekly", "geo")]


def test_status_and_quota(router):
    cmd, service = router
    cmd.dispatch(1, "/status")
    assert "Posted today: 0/5" in last_reply(service)
    cmd.dispatch(1, "/quota")
    assert "Estimated usage: 0/10000 units" in last_reply(service)
    cmd.dispatch(1, "/stats")
    assert "YOUTUBE_CHANNEL_IDS" in last_reply(service)
