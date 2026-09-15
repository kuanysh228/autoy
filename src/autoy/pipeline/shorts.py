from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from autoy.channels import Channel
from autoy.dedup import DuplicateNews, find_similar, pick_fresh_topic
from autoy.media import ShortsStyle, pick_music
from autoy.models import NewsItem, Voice
from autoy.pipeline.context import AppContext
from autoy.publish import YouTubeClient, shorts_metadata, shorts_url
from autoy.tts import synthesize_within

log = logging.getLogger(__name__)

TOPIC_COOLDOWN_HOURS = 6
SIMILARITY_WINDOW_HOURS = 12


class DailyLimitReached(RuntimeError):
    pass


@dataclass(frozen=True)
class ShortsDraft:
    channel: Channel
    topic: str
    news: NewsItem
    video_path: Path
    voice: Voice


@dataclass(frozen=True)
class ShortsPublished:
    draft: ShortsDraft
    video_id: str
    seconds: int

    @property
    def url(self) -> str:
        return shorts_url(self.video_id)


class ShortsPipeline:
    def __init__(self, ctx: AppContext, channel: Channel) -> None:
        self.ctx = ctx
        self.channel = channel

    def choose_topic(self) -> str:
        recent = self.ctx.registry.recent_titles(self.channel.key, TOPIC_COOLDOWN_HOURS)
        return pick_fresh_topic(self.channel.topics, recent)

    def fetch(self, topic: str) -> NewsItem:
        news = asyncio.run(self.ctx.source.fetch_short(topic, lang=self.channel.lang, max_chars=self.channel.max_script_chars))
        log.info("Headline: %s | %d words", news.title, len(news.text.split()))
        if self.ctx.registry.is_posted(news.title):
            raise DuplicateNews(f"already posted: {news.title}")
        recent = self.ctx.registry.recent_titles(self.channel.key, SIMILARITY_WINDOW_HOURS)
        similar = find_similar(news.title, recent)
        if similar:
            raise DuplicateNews(f"similar story posted recently: {similar}")
        return news

    def produce(self, topic: str | None = None, voice: Voice | None = None) -> ShortsDraft:
        settings = self.ctx.settings
        topic = topic or self.choose_topic()
        log.info("=== Shorts | %s | %s ===", self.channel.name, topic)

        news = self.fetch(topic)
        capped = synthesize_within(
            self.ctx.synthesizer,
            news.text,
            self.channel.lang,
            settings.paths.audio,
            settings.video.max_duration_sec,
            voice=voice,
        )
        news.text = capped.text
        log.info("Voice: %s", capped.speech.voice.id)

        music = pick_music(settings.paths.music, self.channel.music_subdir) if self.channel.music else None
        pexels_query = random.choice(self.channel.pexels_queries) if self.channel.pexels_queries else None
        output = settings.paths.videos / f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        video_path = self.ctx.shorts_renderer.render(
            news,
            capped.path,
            capped.speech.words,
            ShortsStyle(self.channel.name, self.channel.accent, self.channel.badge, self.channel.show_banner),
            output,
            music_path=music,
            pexels_query=pexels_query,
        )
        return ShortsDraft(self.channel, topic, news, video_path, capped.speech.voice)

    def publish(self, draft: ShortsDraft, publish_at: str | None = None) -> str:
        client = YouTubeClient(self.ctx.settings, self.channel)
        video_id = client.upload(draft.video_path, shorts_metadata(draft.news, self.channel), publish_at=publish_at)
        self.ctx.registry.mark_posted(draft.news.title, video_id, channel=self.channel.key, voice_id=draft.voice.id)
        log.info("Published: %s", shorts_url(video_id))
        return video_id

    def run(self, topic: str | None = None, publish_at: str | None = None, voice: Voice | None = None) -> ShortsPublished:
        started = time.time()
        draft = self.produce(topic, voice=voice)
        video_id = self.publish(draft, publish_at=publish_at)
        return ShortsPublished(draft, video_id, int(time.time() - started))

    def ensure_daily_limit(self, limit: int | None = None) -> None:
        limit = self.ctx.settings.max_posts_per_day if limit is None else limit
        posted = self.ctx.registry.shorts_posted_today()
        if posted >= limit:
            raise DailyLimitReached(f"daily limit reached: {posted}/{limit}")
