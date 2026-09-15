from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
from collections.abc import Coroutine
from typing import Any, TypeVar

from telegram import Bot

from autoy.channels import Channel
from autoy.config import Settings
from autoy.dedup import pick_fresh_topic
from autoy.models import NewsItem
from autoy.sources import NewsScoutSource
from autoy.storage import PostRegistry
from autoy.text import truncate_tail

log = logging.getLogger(__name__)

T = TypeVar("T")
MAX_MESSAGE = 4096
_POST_BODY_CHARS = 700
_TOPIC_COOLDOWN_HOURS = 6


def _run_isolated(coro: Coroutine[Any, Any, T], timeout: int) -> T:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result(timeout=timeout)


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Notifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    @classmethod
    def from_settings(cls, settings: Settings) -> Notifier:
        return cls(settings.telegram_bot_token, settings.telegram_chat_id)

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str, parse_mode: str | None = "Markdown") -> None:
        if not self.enabled:
            return
        try:
            _run_isolated(self._send(message[:MAX_MESSAGE], parse_mode), timeout=15)
        except Exception as exc:
            log.warning("Telegram notification failed: %s", exc)

    async def _send(self, text: str, parse_mode: str | None) -> None:
        await Bot(self.token).send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode=parse_mode,
            read_timeout=10,
            write_timeout=10,
            connect_timeout=10,
            pool_timeout=10,
        )


def format_channel_post(news: NewsItem) -> str:
    parts = [f"🔴 <b>{escape_html(news.title.strip())}</b>", "", escape_html(truncate_tail(news.text.strip(), _POST_BODY_CHARS, 200))]
    tag = news.direction.strip()
    if re.match(r"^#\w", tag):
        parts += ["", escape_html(tag)]
    return "\n".join(parts)


class ChannelPublisher:
    def __init__(self, settings: Settings, registry: PostRegistry, source: NewsScoutSource) -> None:
        self.settings = settings
        self.registry = registry
        self.source = source

    async def post(self, channel: Channel, topic: str | None = None, dry_run: bool = False) -> str | None:
        chosen = topic or pick_fresh_topic(channel.topics, self.registry.recent_tg_titles(_TOPIC_COOLDOWN_HOURS))
        log.info("Telegram channel: topic '%s' [%s]", chosen, channel.lang)
        news = await self.source.fetch_short(chosen, lang=channel.lang)

        if not dry_run and self.registry.is_tg_posted(news.title):
            log.warning("Telegram channel: duplicate, skipping: %s", news.title)
            return None

        text = format_channel_post(news)
        if dry_run:
            log.info("Telegram channel [dry-run]:\n%s", text)
            return text

        message_id = await self._send(text)
        self.registry.mark_tg_posted(news.title, channel.key)
        log.info("Telegram channel: posted (message_id=%s): %s", message_id, news.title)
        return text

    async def _send(self, text: str) -> int:
        message = await Bot(self.settings.telegram_bot_token).send_message(
            chat_id=self.settings.telegram_channel_id,
            text=text[:MAX_MESSAGE],
            parse_mode="HTML",
            disable_web_page_preview=True,
            read_timeout=15,
            write_timeout=15,
            connect_timeout=15,
            pool_timeout=15,
        )
        return message.message_id
