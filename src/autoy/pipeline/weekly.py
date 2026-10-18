from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from autoy.channels import Channel
from autoy.media import WeeklyStyle, WeeklyVideo, pick_music
from autoy.models import WeeklyStory
from autoy.pipeline.context import AppContext
from autoy.publish import VideoMetadata, YouTubeClient, watch_url
from autoy.strings import strings_for
from autoy.tts import synthesize

log = logging.getLogger(__name__)

_LEAD_MAX_CHARS = 62
_TITLE_MAX_CHARS = 100


@dataclass(frozen=True)
class WeekLabel:
    start: datetime
    end: datetime

    @classmethod
    def current(cls) -> WeekLabel:
        now = datetime.now()
        return cls(now - timedelta(days=now.weekday()), now)

    @property
    def compact(self) -> str:
        return f"{self.start.strftime('%d.%m')}–{self.end.strftime('%d.%m.%Y')}"

    @property
    def spaced(self) -> str:
        return f"{self.start.strftime('%d.%m')} – {self.end.strftime('%d.%m.%Y')}"


@dataclass(frozen=True)
class WeeklyDraft:
    channel: Channel
    stories: list[WeeklyStory]
    video: WeeklyVideo
    thumbnail_path: Path


@dataclass(frozen=True)
class WeeklyPublished:
    draft: WeeklyDraft
    video_id: str
    seconds: int

    @property
    def url(self) -> str:
        return watch_url(self.video_id)


def _timestamp(seconds: float) -> str:
    whole = int(seconds)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def weekly_title(stories: list[WeeklyStory], channel: Channel) -> str:
    text = strings_for(channel.lang)
    lead = (stories[0].title if stories else "").strip().rstrip(".")
    if len(lead) > _LEAD_MAX_CHARS:
        lead = lead[:_LEAD_MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    title = f"{lead}{text.weekly_title_tail}" if lead else text.weekly_title_fallback.format(channel=channel.name)
    return title if len(title) <= _TITLE_MAX_CHARS else title[: _TITLE_MAX_CHARS - 1] + "…"


def weekly_metadata(stories: list[WeeklyStory], channel: Channel, segment_starts: list[float], week: WeekLabel) -> VideoMetadata:
    text = strings_for(channel.lang)
    lines = [text.weekly_heading.format(week=week.compact), "", text.weekly_contents]
    lines += [f"  • {story.label}: {story.title[:70]}" for story in stories]
    lines += ["", "─" * 45, "", text.weekly_chapters, f"0:00 {text.weekly_intro_chapter}"]
    for index, story in enumerate(stories):
        start = segment_starts[index] if index < len(segment_starts) else 0.0
        lines.append(f"{_timestamp(start)} {story.label}: {story.title[:60]}")
    lines += [
        "",
        "─" * 45,
        "",
        *text.weekly_cta,
        "",
        text.weekly_hashtags.format(channel=channel.name.replace(" ", "")),
    ]
    tags = [*text.weekly_tags, *channel.hashtags, channel.name.lower(), week.compact]
    return VideoMetadata(title=weekly_title(stories, channel), description="\n".join(lines), tags=tags)


class WeeklyPipeline:
    def __init__(self, ctx: AppContext, channel: Channel) -> None:
        self.ctx = ctx
        self.channel = channel

    def produce(self, max_topics: int) -> WeeklyDraft | None:
        settings = self.ctx.settings
        if not self.channel.weekly_topics:
            log.error("Channel '%s' has no weekly topics", self.channel.key)
            return None

        log.info("[1/3] Fetching up to %d stories for %s", max_topics, self.channel.name)
        stories = asyncio.run(self.ctx.source.fetch_weekly(self.channel.weekly_topics, self.channel.lang, max_topics))
        if not stories:
            log.error("No stories fetched")
            return None
        for index, story in enumerate(stories, 1):
            log.info("  %d. [%s] %s", index, story.label, story.title[:70])

        log.info("[2/3] Synthesizing %d segments", len(stories))
        audio_paths = []
        for story in stories:
            speech = synthesize(self.ctx.synthesizer, story.text, self.channel.lang, settings.paths.audio)
            audio_paths.append(speech.path)
            log.info("  Audio: %s [%s]", speech.path.name, speech.voice.id)

        log.info("[3/3] Rendering 1920×1080")
        week = WeekLabel.current()
        style = WeeklyStyle(self.channel.name, self.channel.name, self.channel.accent, week.spaced, self.channel.lang)
        output = settings.paths.videos / f"weekly_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        video = self.ctx.weekly_renderer.render(stories, audio_paths, style, output, music_path=pick_music(settings.paths.music))
        thumbnail = self._thumbnail(stories, week)
        log.info("Thumbnail: %s", thumbnail)
        return WeeklyDraft(self.channel, stories, video, thumbnail)

    def _thumbnail(self, stories: list[WeeklyStory], week: WeekLabel) -> Path:
        labels = [story.label for story in stories]
        try:
            return self.ctx.thumbnails.story(
                self.channel.name,
                week.compact,
                labels,
                self.channel.accent,
                stories[0].pexels_query,
                tag=strings_for(self.channel.lang).weekly_card,
            )
        except Exception as exc:
            log.warning("Story thumbnail failed (%s), falling back to minimalist", exc)
            return self.ctx.thumbnails.minimalist(
                strings_for(self.channel.lang).weekly_thumbnail_title.format(week=week.compact),
                self.channel.name,
                week.compact,
                labels,
                self.channel.accent,
                tag=strings_for(self.channel.lang).weekly_card,
            )

    def publish(self, draft: WeeklyDraft, publish_at: str | None = None) -> str:
        client = YouTubeClient(self.ctx.settings, self.channel)
        metadata = weekly_metadata(draft.stories, self.channel, draft.video.segment_starts, WeekLabel.current())
        video_id = client.upload(draft.video.path, metadata, publish_at=publish_at, chunk_mb=4)
        if draft.thumbnail_path.exists():
            client.set_thumbnail(video_id, draft.thumbnail_path)
        for story in draft.stories:
            if not self.ctx.registry.is_posted(story.title):
                self.ctx.registry.mark_posted(
                    story.title, video_id, channel=self.channel.key, voice_id=self.ctx.synthesizer.name, kind="weekly"
                )
        log.info("Published: %s", watch_url(video_id))
        return video_id

    def run(self, max_topics: int, publish_at: str | None = None) -> WeeklyPublished | None:
        started = time.time()
        draft = self.produce(max_topics)
        if draft is None:
            return None
        video_id = self.publish(draft, publish_at=publish_at)
        return WeeklyPublished(draft, video_id, int(time.time() - started))
