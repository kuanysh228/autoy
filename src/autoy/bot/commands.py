from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable

from autoy.bot.core import BotService
from autoy.channels import CHANNELS
from autoy.publish.channel_stats import MONETIZATION_SUBSCRIBERS, MONETIZATION_WATCH_SECONDS, fetch_realtime_stats

log = logging.getLogger(__name__)

HELP_TEXT = """Commands:
/status - bot state and schedule
/stats [channel] - channel statistics (subscribers, views)
/channels - list channels
/create [channel] [topic] - produce and publish a video now
/schedule - show schedule
/schedule_add <channel> <HH:MM> - add a slot
/schedule_remove <id> - remove a slot
/schedule_on <id> - enable a slot
/schedule_off <id> - disable a slot
/schedule_clear - clear the schedule
/weekly - weekly digest settings
/weekly_set <time|channel|topics|enabled> <value> - change a weekly setting
/weekly_now [channel] - run the weekly digest now
/review [on|off] - manual review before publishing
/limit [number] - show or set the daily video limit
/quota - local estimate of the YouTube API quota
/help - this help
"""

COMMANDS = (
    "start",
    "help",
    "channels",
    "status",
    "stats",
    "quota",
    "limit",
    "review",
    "create",
    "schedule",
    "schedule_add",
    "schedule_remove",
    "schedule_on",
    "schedule_off",
    "schedule_clear",
    "weekly",
    "weekly_set",
    "weekly_now",
)

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

Handler = Callable[["CommandRouter", int, list[str]], str | None]


def _validate_time(value: str) -> str:
    if not _TIME_RE.fullmatch(value):
        raise ValueError("Time must be HH:MM")
    hours, minutes = map(int, value.split(":"))
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError("Invalid time")
    return value


def _validate_channel(value: str) -> str:
    if value not in CHANNELS:
        raise ValueError(f"Unknown channel. Available: {', '.join(CHANNELS)}")
    return value


def _spawn(target: Callable[..., None], *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


class CommandRouter:
    def __init__(self, service: BotService) -> None:
        self.service = service
        self._handlers: dict[str, Handler] = {
            "/start": CommandRouter.help,
            "/help": CommandRouter.help,
            "/channels": CommandRouter.channels,
            "/status": CommandRouter.status,
            "/stats": CommandRouter.stats,
            "/quota": CommandRouter.quota,
            "/limit": CommandRouter.limit,
            "/review": CommandRouter.review,
            "/create": CommandRouter.create,
            "/schedule": CommandRouter.schedule,
            "/schedule_add": CommandRouter.schedule_add,
            "/schedule_remove": CommandRouter.schedule_remove,
            "/schedule_on": CommandRouter.schedule_on,
            "/schedule_off": CommandRouter.schedule_off,
            "/schedule_clear": CommandRouter.schedule_clear,
            "/weekly": CommandRouter.weekly,
            "/weekly_set": CommandRouter.weekly_set,
            "/weekly_now": CommandRouter.weekly_now,
        }

    def dispatch(self, chat_id: int, text: str) -> None:
        if not self.service.is_authorized(chat_id):
            self.service.send("Access denied.", chat_id)
            return
        parts = text.strip().split()
        command = parts[0].split("@", 1)[0].lower()
        handler = self._handlers.get(command)
        try:
            reply = handler(self, chat_id, parts[1:]) if handler else "Unknown command. /help"
        except Exception as exc:
            log.warning("Command failed: %s", exc, exc_info=True)
            reply = f"Error: {exc}"
        if reply:
            self.service.send(reply, chat_id)

    def help(self, chat_id: int, args: list[str]) -> str:
        return HELP_TEXT

    def channels(self, chat_id: int, args: list[str]) -> str:
        return "Channels:\n" + "\n".join(f"- {key}: {channel.name}" for key, channel in CHANNELS.items())

    def status(self, chat_id: int, args: list[str]) -> str:
        posted = self.service.ctx.registry.shorts_posted_today()
        return (
            f"Bot is running.\nReview mode: {'on' if self.service.review_enabled() else 'off'}\n"
            f"Posted today: {posted}/{self.service.daily_limit()}\n\n{self._schedule_text()}"
        )

    def stats(self, chat_id: int, args: list[str]) -> str:
        channel_ids = self.service.settings.youtube_channel_ids
        key = args[0] if args and args[0] in channel_ids else "geo"
        channel_id = channel_ids.get(key)
        if not channel_id:
            return f"No YouTube channel id configured for '{key}' (YOUTUBE_CHANNEL_IDS)."
        stats = fetch_realtime_stats(channel_id)
        if stats is None:
            return "Could not fetch statistics, try again later."
        next_subs, next_views = stats.next_subscriber_milestone(), stats.next_view_milestone()
        return "\n".join(
            [
                f"Channel {key.upper()}",
                f"Subscribers: {stats.subscribers:,}" + (f" → next goal: {next_subs:,}" if next_subs else " 🏆"),
                f"Views: {stats.views:,}" + (f" → next goal: {next_views:,}" if next_views else " 🏆"),
                f"To monetization: {max(0, MONETIZATION_SUBSCRIBERS - stats.subscribers):,} subs / "
                f"{max(0, MONETIZATION_WATCH_SECONDS - stats.views):,} watch-seconds",
            ]
        )

    def quota(self, chat_id: int, args: list[str]) -> str:
        settings = self.service.settings
        posted = self.service.ctx.registry.shorts_posted_today()
        used = posted * settings.youtube_upload_quota_cost
        left = max(settings.youtube_daily_quota_units - used, 0)
        remaining_uploads = left // settings.youtube_upload_quota_cost if settings.youtube_upload_quota_cost else 0
        return (
            "YouTube API quota (local estimate):\n"
            f"Posted today: {posted}\n"
            f"Estimated usage: {used}/{settings.youtube_daily_quota_units} units\n"
            f"Configured cost per upload: {settings.youtube_upload_quota_cost} units\n"
            f"Uploads left: ~{remaining_uploads}\n\n"
            "This is computed from the local database; the real consumption is shown in Google Cloud Console."
        )

    def limit(self, chat_id: int, args: list[str]) -> str:
        if args:
            value = int(args[0])
            if not 0 <= value <= 100:
                raise ValueError("Limit must be between 0 and 100")
            self.service.store.set_setting("max_posts_per_day", str(value))
        return f"Daily video limit: {self.service.daily_limit()}"

    def review(self, chat_id: int, args: list[str]) -> str:
        if args:
            value = args[0].lower()
            if value not in ("on", "off"):
                raise ValueError("Usage: /review on|off")
            self.service.store.set_setting("review_enabled", "1" if value == "on" else "0")
        return f"Review mode: {'on' if self.service.review_enabled() else 'off'}"

    def create(self, chat_id: int, args: list[str]) -> None:
        if args and args[0] in CHANNELS:
            channel, topic = args[0], " ".join(args[1:]).strip() or None
        else:
            channel, topic = "geo", " ".join(args).strip() or None
        _spawn(self.service.run_shorts_background, channel, topic, chat_id)
        return None

    def schedule(self, chat_id: int, args: list[str]) -> str:
        return self._schedule_text()

    def schedule_add(self, chat_id: int, args: list[str]) -> str:
        if len(args) != 2:
            raise ValueError("Usage: /schedule_add <channel> <HH:MM>")
        schedule_id = self.service.store.add_schedule(_validate_channel(args[0]), _validate_time(args[1]))
        return f"Added: id={schedule_id}\n\n{self._schedule_text()}"

    def schedule_remove(self, chat_id: int, args: list[str]) -> str:
        return "Removed." if self.service.store.remove_schedule(self._single_id(args, "/schedule_remove")) else "No such id."

    def schedule_on(self, chat_id: int, args: list[str]) -> str:
        return "Enabled." if self.service.store.set_schedule_enabled(self._single_id(args, "/schedule_on"), True) else "No such id."

    def schedule_off(self, chat_id: int, args: list[str]) -> str:
        return "Disabled." if self.service.store.set_schedule_enabled(self._single_id(args, "/schedule_off"), False) else "No such id."

    def schedule_clear(self, chat_id: int, args: list[str]) -> str:
        self.service.store.clear_schedules()
        return "Schedule cleared."

    def weekly(self, chat_id: int, args: list[str]) -> str:
        weekly = self.service.weekly_setting
        return (
            "Weekly digest (every Sunday):\n"
            f"  Channel: {weekly('channel', 'geo')}\n"
            f"  Time:    {weekly('time', '11:00')}\n"
            f"  Topics:  {weekly('topics', '7')}\n"
            f"  Status:  {'enabled' if weekly('enabled', '1') == '1' else 'disabled'}\n\n"
            "Change with: /weekly_set <time|channel|topics|enabled> <value>"
        )

    def weekly_set(self, chat_id: int, args: list[str]) -> str:
        if len(args) != 2:
            raise ValueError("Usage: /weekly_set <time|channel|topics|enabled> <value>")
        key, value = args[0].lower(), args[1]
        if key == "time":
            stored = _validate_time(value)
        elif key == "channel":
            stored = _validate_channel(value)
        elif key == "topics":
            if not 1 <= int(value) <= 10:
                raise ValueError("topics: 1..10")
            stored = str(int(value))
        elif key == "enabled":
            if value not in ("0", "1", "on", "off"):
                raise ValueError("enabled: 0/1 or on/off")
            stored = "1" if value in ("1", "on") else "0"
        else:
            raise ValueError("Key must be one of: time, channel, topics, enabled")
        self.service.store.set_setting(f"weekly_{key}", stored)
        return f"Saved: weekly_{key} = {stored}"

    def weekly_now(self, chat_id: int, args: list[str]) -> None:
        channel = args[0] if args and args[0] in CHANNELS else self.service.weekly_setting("channel", "geo")
        _spawn(self.service.run_weekly_background, channel, chat_id)
        return None

    def _schedule_text(self) -> str:
        entries = self.service.store.list_schedules()
        if not entries:
            return "Schedule is empty."
        lines = ["Schedule:"] + [f"{e.id}. {e.run_time} | {e.channel} | {'on' if e.enabled else 'off'}" for e in entries]
        return "\n".join(lines)

    @staticmethod
    def _single_id(args: list[str], usage: str) -> int:
        if len(args) != 1:
            raise ValueError(f"Usage: {usage} <id>")
        return int(args[0])
