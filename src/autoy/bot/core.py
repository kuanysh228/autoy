from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from autoy.channels import get_channel
from autoy.models import Voice
from autoy.pipeline import AppContext, DailyLimitReached, ShortsDraft, ShortsPipeline, WeeklyPipeline
from autoy.publish import shorts_url
from autoy.storage import BotStore, PendingReview

log = logging.getLogger(__name__)

AUTO_APPROVE_SECONDS = 5 * 60
_MESSAGE_LIMIT = 3900
_CAPTION_LIMIT = 1024


def review_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Publish", callback_data=f"approve:{token}"),
                InlineKeyboardButton("Remake", callback_data=f"remake:{token}"),
            ],
            [InlineKeyboardButton("Delete", callback_data=f"delete:{token}")],
        ]
    )


class BotService:
    def __init__(self, ctx: AppContext, store: BotStore) -> None:
        self.ctx = ctx
        self.store = store
        self.app: Application | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._run_lock = threading.Lock()

    @property
    def settings(self):
        return self.ctx.settings

    @property
    def owner_chat_id(self) -> str:
        return self.settings.telegram_chat_id

    def is_authorized(self, chat_id: int | str) -> bool:
        return not self.owner_chat_id or str(chat_id) == self.owner_chat_id

    def daily_limit(self) -> int:
        return int(self.store.get_setting("max_posts_per_day", str(self.settings.max_posts_per_day)))

    def review_enabled(self) -> bool:
        return self.store.get_setting("review_enabled", "1") == "1"

    def weekly_setting(self, key: str, default: str) -> str:
        return self.store.get_setting(f"weekly_{key}", default)

    def _submit(self, coro: Coroutine[Any, Any, Any]) -> None:
        if self.loop is None:
            raise RuntimeError("Telegram event loop is not running")
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self.loop.create_task(coro)
            return
        asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def _bot(self):
        if self.app is None:
            raise RuntimeError("Telegram application is not initialized")
        return self.app.bot

    def send(self, text: str, chat_id: int | str | None = None) -> None:
        target = chat_id or self.owner_chat_id
        if not target:
            log.warning("No chat id configured, dropping message: %s", text[:120])
            return
        self._submit(self._bot().send_message(chat_id=target, text=text[:_MESSAGE_LIMIT]))

    def send_video(self, video_path: Path, caption: str, markup: InlineKeyboardMarkup, chat_id: int | str | None = None) -> None:
        target = chat_id or self.owner_chat_id
        if not target:
            log.warning("No chat id configured, dropping video: %s", video_path)
            return

        async def _send() -> None:
            with video_path.open("rb") as handle:
                await self._bot().send_video(
                    chat_id=target,
                    video=handle,
                    caption=caption[:_CAPTION_LIMIT],
                    supports_streaming=True,
                    reply_markup=markup,
                    read_timeout=180,
                    write_timeout=180,
                    connect_timeout=30,
                    pool_timeout=30,
                )

        self._submit(_send())

    def edit_caption(self, chat_id: int, message_id: int, text: str) -> None:
        self._submit(self._bot().edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text[:_CAPTION_LIMIT]))

    def produce_draft(self, channel_key: str, topic: str | None) -> ShortsDraft:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("A pipeline is already running, wait for it to finish")
        try:
            pipeline = ShortsPipeline(self.ctx, get_channel(channel_key))
            pipeline.ensure_daily_limit(self.daily_limit())
            return pipeline.produce(topic)
        finally:
            self._run_lock.release()

    def publish_draft(self, draft: ShortsDraft) -> str:
        return ShortsPipeline(self.ctx, draft.channel).publish(draft)

    def publish_review(self, review: PendingReview) -> str:
        channel = get_channel(review.channel)
        draft = ShortsDraft(channel, review.topic or "", review.news, review.video_path, Voice(id=review.voice_id, name=review.voice_id))
        return ShortsPipeline(self.ctx, channel).publish(draft)

    def submit_for_review(self, channel_key: str, topic: str | None, chat_id: int | str | None) -> str:
        draft = self.produce_draft(channel_key, topic)
        token = f"{int(time.time())}_{random.randint(100000, 999999)}"
        self.store.add_pending_review(token, PendingReview(token, draft.video_path, draft.news, channel_key, draft.voice.id, topic))
        caption = (
            f"{draft.news.title}\n\nChannel: {channel_key}\n"
            f"Review the video and pick an action. Auto-publishes in {AUTO_APPROVE_SECONDS // 60} min."
        )
        self.send_video(draft.video_path, caption, review_keyboard(token), chat_id)
        threading.Thread(target=self._auto_approve, args=(token, chat_id), daemon=True).start()
        return token

    def _auto_approve(self, token: str, chat_id: int | str | None) -> None:
        time.sleep(AUTO_APPROVE_SECONDS)
        review = self.store.pop_pending_review(token)
        if review is None:
            return
        try:
            video_id = self.publish_review(review)
        except Exception as exc:
            log.error("Auto-approve upload failed: %s", exc, exc_info=True)
            self.send(f"Auto-publish failed:\n{exc}", chat_id)
            return
        self.send(f"Auto-published (no answer in 5 min):\n{shorts_url(video_id)}\n\n{review.news.title}", chat_id)

    def run_shorts_background(self, channel_key: str, topic: str | None, chat_id: int | str, schedule_id: int | None = None) -> None:
        started = time.time()
        try:
            mode = "for review" if self.review_enabled() else "with auto-publish"
            self.send(f"Starting video {mode}: {channel_key}" + (f"\nTopic: {topic}" if topic else ""), chat_id)
            if self.review_enabled():
                token = self.submit_for_review(channel_key, topic, chat_id)
                result = f"Video sent for review. token={token}"
            else:
                draft = self.produce_draft(channel_key, topic)
                video_id = self.publish_draft(draft)
                result = f"{shorts_url(video_id)}\n{draft.news.title}"
            self.send(f"Done in {int(time.time() - started)}s:\n{result}", chat_id)
            if schedule_id:
                self.store.finish_schedule_run(schedule_id, "success", result)
        except DailyLimitReached as exc:
            self.send(str(exc), chat_id)
            if schedule_id:
                self.store.finish_schedule_run(schedule_id, "skipped", str(exc))
        except Exception as exc:
            log.error("Pipeline failed: %s", exc, exc_info=True)
            self.send(f"Pipeline failed:\n{exc}", chat_id)
            if schedule_id:
                self.store.finish_schedule_run(schedule_id, "error", str(exc))

    def run_weekly_background(self, channel_key: str, chat_id: int | str) -> None:
        self.send(f"Starting weekly digest for {channel_key}. This takes ~10 minutes.", chat_id)
        try:
            result = WeeklyPipeline(self.ctx, get_channel(channel_key)).run(int(self.weekly_setting("topics", "7")))
        except Exception as exc:
            log.error("Weekly pipeline failed: %s", exc, exc_info=True)
            self.send(f"Weekly digest failed:\n{exc}", chat_id)
            return
        self.send("Weekly digest uploaded!" + (f"\n{result.url}" if result else ""), chat_id)

    def handle_approve(self, token: str, chat_id: int, message_id: int) -> None:
        review = self.store.pop_pending_review(token)
        if review is None:
            self.edit_caption(chat_id, message_id, "Already handled or not found.")
            return
        try:
            video_id = self.publish_review(review)
        except Exception as exc:
            log.error("Approve upload failed: %s", exc, exc_info=True)
            self.edit_caption(chat_id, message_id, f"Upload failed:\n{exc}")
            return
        self.edit_caption(chat_id, message_id, f"Published:\n{shorts_url(video_id)}\n\n{review.news.title}")

    def handle_remake(self, token: str, chat_id: int, message_id: int) -> None:
        review = self.store.pop_pending_review(token)
        if review is None:
            self.edit_caption(chat_id, message_id, "Already handled or not found.")
            return
        _delete_file(review.video_path)
        self.edit_caption(chat_id, message_id, "Remaking: generating a new video...")
        self.run_shorts_background(review.channel, review.topic, chat_id)

    def handle_delete(self, token: str, chat_id: int, message_id: int) -> None:
        review = self.store.pop_pending_review(token)
        if review is None:
            self.edit_caption(chat_id, message_id, "Already handled or not found.")
            return
        _delete_file(review.video_path)
        self.edit_caption(chat_id, message_id, "Deleted. Nothing was uploaded.")


def _delete_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Could not delete %s: %s", path, exc)
