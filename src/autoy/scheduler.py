from __future__ import annotations

import logging
import time
from collections.abc import Sequence

import schedule

from autoy.pipeline.context import AppContext
from autoy.pipeline.jobs import run_shorts_job, run_telegram_channel_job, run_weekly_job

log = logging.getLogger(__name__)

_POLL_SECONDS = 60


def build_schedule(
    ctx: AppContext, channel_keys: Sequence[str], *, weekly: bool = True, telegram_channel: bool = True
) -> schedule.Scheduler:
    settings = ctx.settings
    scheduler = schedule.Scheduler()

    for key in channel_keys:
        for at in settings.schedule_times:
            scheduler.every().day.at(at).do(run_shorts_job, ctx, key)
        log.info("Channel %-12s → %s", key, ", ".join(settings.schedule_times))

    if weekly:
        scheduler.every().sunday.at(settings.weekly_time).do(run_weekly_job, ctx, settings.weekly_channel, settings.weekly_max_topics)
        log.info("Weekly digest: Sundays at %s (%s)", settings.weekly_time, settings.weekly_channel)

    if telegram_channel and settings.telegram_channel_id:
        for at in settings.telegram_channel_times:
            scheduler.every().day.at(at).do(run_telegram_channel_job, ctx)
        log.info("Telegram channel: %s", ", ".join(settings.telegram_channel_times))

    log.info("%d jobs scheduled", len(scheduler.jobs))
    return scheduler


def run_forever(scheduler: schedule.Scheduler) -> None:
    while True:
        scheduler.run_pending()
        time.sleep(_POLL_SECONDS)
