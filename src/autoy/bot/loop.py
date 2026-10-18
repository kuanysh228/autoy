from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from autoy.bot.core import BotService
from autoy.channels import DEFAULT_CHANNEL
from autoy.pipeline.jobs import run_telegram_channel_job
from autoy.publish.channel_stats import SUBSCRIBER_MILESTONES, VIEW_MILESTONES, fetch_realtime_stats

log = logging.getLogger(__name__)

_TICK_SECONDS = 30
_MILESTONE_INTERVAL = 30 * 60


class ScheduleLoop:
    def __init__(self, service: BotService) -> None:
        self.service = service
        self._weekly_fired_on = ""
        self._channel_post_fired_at = ""
        self._last_milestone_check = 0.0

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, daemon=True, name="schedule-loop")
        thread.start()
        return thread

    def run(self) -> None:
        log.info("Schedule loop started")
        while True:
            try:
                self.tick(datetime.now())
            except Exception as exc:
                log.error("Schedule loop error: %s", exc, exc_info=True)
            time.sleep(_TICK_SECONDS)

    def tick(self, now: datetime) -> None:
        hhmm = now.strftime("%H:%M")
        today = now.date().isoformat()
        owner = self.service.owner_chat_id or 0

        if (
            now.weekday() == 6
            and hhmm == self.service.weekly_setting("time", "11:00")
            and self._weekly_fired_on != today
            and self.service.weekly_setting("enabled", "1") == "1"
        ):
            self._weekly_fired_on = today
            channel = self.service.weekly_setting("channel", DEFAULT_CHANNEL)
            log.info("Starting weekly digest (Sunday %s)", hhmm)
            threading.Thread(target=self.service.run_weekly_background, args=(channel, owner), daemon=True).start()

        stamp = f"{today} {hhmm}"
        settings = self.service.settings
        if settings.telegram_channel_id and hhmm in settings.telegram_channel_times and self._channel_post_fired_at != stamp:
            self._channel_post_fired_at = stamp
            log.info("Posting to the Telegram channel (%s)", hhmm)
            threading.Thread(target=run_telegram_channel_job, args=(self.service.ctx,), daemon=True).start()

        if time.time() - self._last_milestone_check >= _MILESTONE_INTERVAL:
            self._last_milestone_check = time.time()
            threading.Thread(target=self.check_milestones, daemon=True).start()

        for entry in self.service.store.list_schedules():
            if not entry.enabled or entry.run_time != hhmm:
                continue
            if self.service.ctx.registry.shorts_posted_today() >= self.service.daily_limit():
                log.info("Daily limit reached, skipping schedule id=%s", entry.id)
                continue
            if not self.service.store.claim_schedule_run(entry.id):
                continue
            threading.Thread(
                target=self.service.run_shorts_background,
                args=(entry.channel, None, owner, entry.id),
                daemon=True,
            ).start()

    def check_milestones(self) -> None:
        for key, channel_id in self.service.settings.youtube_channel_ids.items():
            try:
                stats = fetch_realtime_stats(channel_id)
            except Exception as exc:
                log.debug("Milestone check failed for %s: %s", key, exc)
                continue
            if stats is None:
                continue
            for milestone in SUBSCRIBER_MILESTONES:
                self._announce(
                    key, f"milestone_subs_{key}_{milestone}", stats.subscribers >= milestone, f"{milestone:,} subscribers", stats
                )
            for milestone in VIEW_MILESTONES:
                self._announce(key, f"milestone_views_{key}_{milestone}", stats.views >= milestone, f"{milestone:,} views", stats)

    def _announce(self, key: str, setting_key: str, reached: bool, label: str, stats) -> None:
        if not reached or self.service.store.get_setting(setting_key, "0") != "0":
            return
        self.service.store.set_setting(setting_key, "1")
        self.service.send(
            f"🎉 Milestone on {key.upper()}!\nReached {label}!\nNow: {stats.subscribers:,} subscribers / {stats.views:,} views"
        )
        log.info("Milestone: %s on channel %s", label, key)
