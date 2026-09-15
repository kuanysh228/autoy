from __future__ import annotations

import asyncio
import logging

from autoy.channels import get_channel
from autoy.dedup import DuplicateNews
from autoy.pipeline.context import AppContext
from autoy.pipeline.shorts import DailyLimitReached, ShortsPipeline
from autoy.pipeline.weekly import WeeklyPipeline
from autoy.publish import ChannelPublisher

log = logging.getLogger(__name__)


def run_shorts_job(ctx: AppContext, channel_key: str, daily_limit: int | None = None) -> None:
    pipeline = ShortsPipeline(ctx, get_channel(channel_key))
    try:
        pipeline.ensure_daily_limit(daily_limit)
    except DailyLimitReached as exc:
        log.info("%s, skipping", exc)
        return
    topic = pipeline.choose_topic()
    try:
        result = pipeline.run(topic)
    except DuplicateNews as exc:
        log.warning("Skipped: %s", exc)
        return
    except Exception as exc:
        log.error("Shorts pipeline failed: %s", exc, exc_info=True)
        ctx.notifier.send(f"*Shorts pipeline failed*\n\nTopic: {topic}\nError: {exc}")
        return
    log.info("SUCCESS | %s | %s | %ds", result.draft.news.title, result.url, result.seconds)
    ctx.notifier.send(f"*Video uploaded!*\n\n*{result.draft.news.title}*\n{result.url}\n_Took {result.seconds}s_")


def run_weekly_job(ctx: AppContext, channel_key: str, max_topics: int, publish_at: str | None = None) -> None:
    channel = get_channel(channel_key)
    log.info("=== Weekly digest | %s ===", channel.name)
    try:
        result = WeeklyPipeline(ctx, channel).run(max_topics, publish_at=publish_at)
    except Exception as exc:
        log.error("Weekly pipeline failed: %s", exc, exc_info=True)
        ctx.notifier.send(f"*Weekly digest failed*\n\nError: {exc}")
        return
    if result is None:
        return
    log.info("DONE | %s (%ds)", result.url, result.seconds)
    ctx.notifier.send(
        f"*Weekly digest uploaded!*\n\n*{channel.name}*\n{result.url}\n_Segments: {len(result.draft.stories)} | Took {result.seconds}s_"
    )


def run_telegram_channel_job(ctx: AppContext, channel_key: str | None = None, topic: str | None = None) -> None:
    channel = get_channel(channel_key or ctx.settings.telegram_news_channel)
    publisher = ChannelPublisher(ctx.settings, ctx.registry, ctx.source)
    try:
        text = asyncio.run(publisher.post(channel, topic=topic))
    except Exception as exc:
        log.error("Telegram channel post failed: %s", exc, exc_info=True)
        ctx.notifier.send(f"*Telegram channel post failed*\n\nError: {exc}")
        return
    log.info("Telegram channel: %s", "posted" if text else "skipped (duplicate or no news)")
