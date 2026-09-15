from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from autoy.config import Settings
from autoy.media import draw as d
from autoy.media.ffmpeg import concat, encode_frames, encode_still, media_duration, mix_music
from autoy.media.kenburns import Slideshow
from autoy.media.pexels import PexelsClient
from autoy.models import RGB, WeeklyStory
from autoy.text import split_sentences

log = logging.getLogger(__name__)

SIZE = (1920, 1080)
FPS = 24
KEN_BURNS_ZOOM = 0.18
CROSSFADE_SEC = 0.8
IMAGE_HOLD_SEC = 6.0
IMAGES_PER_SEGMENT = 12
CHAPTER_SEC = 1.3
INTRO_SEC = 5.5
OUTRO_SEC = 7.0
TAIL_SEC = 1.5
MUSIC_VOLUME = 0.07
PAD = 90
_LIGHT: RGB = (230, 230, 230)
_MUTED: RGB = (170, 170, 170)
_LIST_BLUE: RGB = (140, 180, 255)


@dataclass(frozen=True)
class WeeklyStyle:
    channel_name: str
    theme: str
    accent: RGB
    week_label: str


@dataclass(frozen=True)
class WeeklyVideo:
    path: Path
    segment_starts: list[float]


def _sentence_timeline(text: str, total: float) -> list[tuple[float, float, str]]:
    sentences = split_sentences(text) or [text]
    total_chars = max(1, sum(len(s) for s in sentences))
    timeline: list[tuple[float, float, str]] = []
    t = 0.0
    for sentence in sentences:
        duration = len(sentence) / total_chars * total
        timeline.append((t, t + duration, sentence))
        t += duration
    return timeline


def _sentence_at(timeline: list[tuple[float, float, str]], t: float) -> str:
    for start, end, sentence in timeline:
        if start <= t < end:
            return sentence
    return timeline[-1][2] if timeline else ""


class WeeklyRenderer:
    def __init__(self, settings: Settings, pexels: PexelsClient) -> None:
        self.settings = settings
        self.pexels = pexels

    def render(
        self,
        stories: list[WeeklyStory],
        audio_paths: list[Path],
        style: WeeklyStyle,
        output_path: Path,
        music_path: Path | None = None,
    ) -> WeeklyVideo:
        labels = [story.label for story in stories]
        parts: list[Path] = []
        segment_starts: list[float] = []
        elapsed = 0.0

        with tempfile.TemporaryDirectory(prefix="weekly_") as tmp_name:
            tmp = Path(tmp_name)

            log.info("Render: intro")
            intro_images = self.pexels.search(stories[0].pexels_query, 1, "landscape") if stories else []
            intro = tmp / "intro.mp4"
            encode_still(
                self._intro(style, labels, intro_images[0] if intro_images else None), seconds=INTRO_SEC, fps=FPS, output_path=intro
            )
            parts.append(intro)
            elapsed += INTRO_SEC

            for index, (story, audio_path) in enumerate(zip(stories, audio_paths, strict=False)):
                log.info("Render: chapter %d/%d — %s", index + 1, len(stories), story.label)
                chapter = tmp / f"chapter_{index:02d}.mp4"
                encode_still(self._chapter(story.label, style.accent), seconds=CHAPTER_SEC, fps=FPS, output_path=chapter)
                parts.append(chapter)
                elapsed += CHAPTER_SEC

                segment = tmp / f"segment_{index:02d}.mp4"
                self._segment(story, audio_path, style, segment)
                segment_starts.append(elapsed)
                elapsed += media_duration(segment)
                parts.append(segment)

            log.info("Render: outro")
            outro = tmp / "outro.mp4"
            encode_still(self._outro(style), seconds=OUTRO_SEC, fps=FPS, output_path=outro)
            parts.append(outro)

            log.info("Concatenating %d parts → %s", len(parts), output_path.name)
            concat(parts, output_path, tmp / "concat.txt")

        final_path = output_path
        if music_path:
            log.info("Mixing background music: %s (%.0f%%)", music_path.name, MUSIC_VOLUME * 100)
            final_path = mix_music(output_path, music_path, MUSIC_VOLUME)
        else:
            log.warning("No music file found, uploading without music")

        log.info(
            "Weekly video: %s (%.1f MB, %.1f min)",
            final_path.name,
            final_path.stat().st_size / 1024 / 1024,
            media_duration(final_path) / 60,
        )
        return WeeklyVideo(final_path, segment_starts)

    def _segment(self, story: WeeklyStory, audio_path: Path, style: WeeklyStyle, output: Path) -> None:
        total = media_duration(audio_path)
        frame_count = round((total + TAIL_SEC) * FPS)
        slideshow = Slideshow(
            images=self.pexels.search(story.pexels_query, IMAGES_PER_SEGMENT, "landscape"),
            size=SIZE,
            scene_seconds=IMAGE_HOLD_SEC,
            crossfade_seconds=CROSSFADE_SEC,
            zoom=KEN_BURNS_ZOOM,
            wide_pan=True,
            stretch_to_total=True,
        )
        timeline = _sentence_timeline(story.text, total)
        log.info("  Segment [%s]: %.1fs, %d frames, %d photos", story.label, total, frame_count, len(slideshow.images))

        def frames() -> Iterator[Image.Image]:
            for i in range(frame_count):
                t = i / FPS
                yield self._segment_frame(slideshow.frame_at(min(t, total - 0.01), total), story, _sentence_at(timeline, t), style)

        encode_frames(frames(), size=SIZE, fps=FPS, output_path=output, audio_path=audio_path, duration=total, video_bitrate="6000k")

    def _fonts(self) -> tuple[str, str]:
        return self.settings.font_bold, self.settings.font_regular

    def _photo_background(self, image: Image.Image | None, shade: int, fallback_top: RGB, fallback_bottom: RGB) -> Image.Image:
        if image is None:
            return d.vertical_gradient(SIZE, fallback_top, fallback_bottom)
        return d.composite(
            ImageOps.fit(image, SIZE, Image.LANCZOS),
            d.full_shade(SIZE, shade),
            d.top_shade(SIZE, 200, 160, 1.4),
            d.bottom_shade(SIZE, 400, 200, 1.4),
        )

    def _segment_frame(self, background: Image.Image | None, story: WeeklyStory, subtitle: str, style: WeeklyStyle) -> Image.Image:
        width, height = SIZE
        bold, regular = self._fonts()
        frame = self._photo_background(background, 130, (5, 10, 30), (2, 5, 15))
        draw = ImageDraw.Draw(frame)

        draw.text((PAD, 36), style.channel_name, font=d.load_font(bold, 30), fill=(200, 200, 200))
        week_font = d.load_font(regular, 28)
        draw.text((width - PAD - d.text_width(week_font, style.week_label), 40), style.week_label, font=week_font, fill=_MUTED)

        badge_bottom = d.draw_badge(draw, story.label, 100, d.load_font(bold, 46), style.accent, width, pad_x=28, pad_y=10)
        line_y = badge_bottom + 28
        draw.rectangle([PAD, line_y, width - PAD, line_y + 3], fill=style.accent)

        title_font = d.load_font(bold, 62)
        y = line_y + 28
        for line in d.wrap_text(story.title, title_font, width - PAD * 2)[:3]:
            d.draw_centered(draw, line, y, title_font, d.WHITE, width)
            y += title_font.size + 10

        if subtitle:
            sub_font = d.load_font(regular, 40)
            lines = d.wrap_text(subtitle, sub_font, width - PAD * 2)[:3]
            block_height = len(lines) * (sub_font.size + 6)
            sub_y = height - 80 - block_height
            draw.rectangle([PAD - 20, sub_y - 14, width - PAD + 20, height - 60], fill=(0, 0, 0, 160))
            for line in lines:
                d.draw_centered(draw, line, sub_y, sub_font, _LIGHT, width, shadow=False)
                sub_y += sub_font.size + 6
        return frame

    def _chapter(self, label: str, accent: RGB) -> Image.Image:
        width, height = SIZE
        frame = d.vertical_gradient(SIZE, (8, 8, 20), (3, 3, 10))
        draw = ImageDraw.Draw(frame)
        font = d.load_font(self.settings.font_bold, 80)
        mid = height // 2
        draw.rectangle([PAD * 2, mid - 50, width - PAD * 2, mid - 47], fill=accent)
        d.draw_centered(draw, label, mid - 20, font, d.WHITE, width)
        draw.rectangle([PAD * 2, mid + font.size + 14, width - PAD * 2, mid + font.size + 17], fill=accent)
        return frame

    def _intro(self, style: WeeklyStyle, labels: list[str], background: Image.Image | None) -> Image.Image:
        width, height = SIZE
        bold, regular = self._fonts()
        frame = self._photo_background(background, 180, (4, 8, 25), (2, 4, 14))
        draw = ImageDraw.Draw(frame)

        d.draw_centered(draw, "ИТОГИ НЕДЕЛИ", height // 2 - 200, d.load_font(bold, 96), d.WHITE, width)
        draw.rectangle([PAD * 3, height // 2 - 80, width - PAD * 3, height // 2 - 76], fill=style.accent)
        d.draw_badge(draw, style.theme, height // 2 - 52, d.load_font(bold, 60), style.accent, width, pad_x=30, pad_y=12)
        d.draw_centered(draw, style.week_label, height // 2 + 20, d.load_font(regular, 38), (180, 180, 180), width)

        story_font = d.load_font(regular, 30)
        y = height // 2 + 100
        for label in labels[:8]:
            d.draw_centered(draw, f"• {label}", y, story_font, _LIST_BLUE, width)
            y += story_font.size + 8
        return frame

    def _outro(self, style: WeeklyStyle) -> Image.Image:
        width, height = SIZE
        bold, regular = self._fonts()
        frame = d.vertical_gradient(SIZE, (4, 8, 25), (2, 4, 14))
        draw = ImageDraw.Draw(frame)
        sub_font = d.load_font(regular, 40)
        d.draw_centered(draw, "Спасибо за просмотр!", height // 2 - 80, d.load_font(bold, 72), d.WHITE, width)
        d.draw_centered(draw, "Подписывайтесь, чтобы не пропускать", height // 2 + 20, sub_font, (190, 190, 190), width)
        d.draw_centered(draw, "еженедельные итоги", height // 2 + 70, sub_font, (190, 190, 190), width)
        draw.rectangle([PAD * 3, height // 2 + 130, width - PAD * 3, height // 2 + 133], fill=style.accent)
        d.draw_centered(draw, style.channel_name, height // 2 + 160, d.load_font(bold, 48), d.WHITE, width)
        return frame
