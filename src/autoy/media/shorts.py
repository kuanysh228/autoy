from __future__ import annotations

import logging
import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from autoy.config import Settings
from autoy.media import draw as d
from autoy.media.ffmpeg import encode_frames, media_duration
from autoy.media.kenburns import Slideshow
from autoy.media.pexels import PexelsClient
from autoy.models import RGB, NewsItem, WordEvent
from autoy.text import is_latin

log = logging.getLogger(__name__)

WORDS_PER_LINE = 3
KEN_BURNS_ZOOM = 0.06
CROSSFADE_SEC = 0.25
HOOK_SEC = 2.0
PROGRESS_BAR_PX = 8
TAIL_SEC = 1.5
PAD = 70
_DIM: RGB = (140, 140, 150)
_TAG_BLUE: RGB = (100, 195, 255)
_MAX_PEXELS_IMAGES = 15

_TAG_TO_QUERY: dict[str, str] = {
    "openai": "artificial intelligence robot future",
    "ai": "artificial intelligence technology",
    "bitcoin": "bitcoin cryptocurrency gold",
    "btc": "bitcoin crypto coin",
    "crypto": "cryptocurrency blockchain digital",
    "trump": "white house politics washington",
    "politics": "government politics world",
    "война": "military soldiers conflict",
    "war": "military soldiers conflict",
    "перемирие": "peace agreement handshake diplomacy",
    "space": "space rocket stars nasa",
    "tech": "technology innovation digital",
    "science": "science laboratory research",
    "cybersecurity": "hacker cyber security dark",
    "economy": "economy finance stock market",
    "health": "health medicine hospital",
    "sports": "sports stadium competition",
}

_KEYWORD_TO_QUERY: tuple[tuple[tuple[str, ...], str], ...] = (
    (("чип", "полупроводник", "процессор", "nvidia", "semiconductor", "gpu"), "semiconductor chip factory technology"),
    (("торгов", "пошлин", "тариф", "экспорт", "импорт", "trade", "tariff", "export"), "cargo port containers shipping trade"),
    (("теракт", "террор", "взрыв", "attack", "terror"), "police emergency city night"),
    (("ракет", "дрон", "бпла", "missile", "drone"), "missile rocket launch military"),
    (("удар", "обстрел", "бомб", "strike", "bombing"), "explosion smoke destroyed building"),
    (("санкц", "sanction", "эмбарго"), "cargo port containers trade"),
    (("нато", "nato", "альянс"), "nato military alliance flags"),
    (("ядерн", "nuclear", "атомн"), "nuclear power plant reactor"),
    (("израил", "газа", "хамас", "israel", "gaza"), "middle east conflict soldiers desert"),
    (("иран", "хезболла", "iran"), "middle east city protest flag"),
    (("украин", "ukraine", "зеленск", "киев"), "ukraine soldiers military conflict"),
    (("росси", "кремл", "путин", "russia", "kremlin"), "kremlin moscow russia politics"),
    (("трамп", "trump", "белый дом", "white house"), "white house washington politics"),
    (("кита", "тайван", "china", "taiwan"), "china beijing flag politics"),
    (("кндр", "корея", "korea"), "north korea military parade"),
    (("оон", "дипломат", "переговор", "саммит", "un ", "summit", "diplomacy"), "united nations diplomacy summit"),
    (("перемир", "мирн", "ceasefire", "peace"), "peace negotiation handshake diplomacy"),
    (("войн", "фронт", "арми", "war", "military", "troops"), "military soldiers war conflict"),
    (("экономик", "рынк", "инфляц", "economy", "market"), "stock market trading finance"),
    (("нефт", "газ", "энерг", "oil", "energy"), "oil refinery pipeline energy"),
    (("выбор", "парламент", "election", "parliament"), "parliament government election"),
    (("ии", "нейросет", "чип", "ai", "chip"), "artificial intelligence technology"),
)

_POWER_STEMS = (
    "войн",
    "сделк",
    "удар",
    "санкц",
    "ядерн",
    "ракет",
    "атак",
    "взрыв",
    "миллиард",
    "миллион",
    "трлн",
    "триллион",
    "побед",
    "пораж",
    "кризис",
    "крах",
    "обвал",
    "рекорд",
    "запрет",
    "угроз",
    "смерт",
    "гибел",
    "катастроф",
    "срочн",
    "впервые",
    "шок",
    "переговор",
    "перемир",
    "наступл",
    "оборон",
    "вторжен",
    "эскалац",
    "договор",
    "конфликт",
    "war",
    "deal",
    "strike",
    "sanction",
    "nuclear",
    "missile",
    "attack",
    "billion",
    "million",
    "trillion",
    "record",
    "ban",
    "threat",
    "death",
    "crisis",
    "crash",
    "breaking",
    "shock",
    "first",
    "ceasefire",
    "invasion",
    "escalat",
    "conflict",
    "control",
    "power",
    "secret",
    "never",
    "always",
    "hidden",
    "trick",
    "trap",
    "lie",
    "fear",
    "danger",
)


def pexels_query_for(news: NewsItem) -> str:
    tag = news.direction.lstrip("#").lower().strip()
    if tag in _TAG_TO_QUERY:
        return _TAG_TO_QUERY[tag]
    haystack = f"{news.title} {tag} {news.text}".lower()
    for stems, query in _KEYWORD_TO_QUERY:
        if any(stem in haystack for stem in stems):
            return query
    if tag and is_latin(tag, threshold=0.99):
        return tag
    return "breaking news world politics"


def is_power_word(word: str) -> bool:
    bare = word.strip(".,!?;:—–\"'»«()[]").lower()
    if not bare:
        return False
    if any(ch.isdigit() for ch in bare) or any(symbol in word for symbol in "%$€₽"):
        return True
    return bare.startswith(_POWER_STEMS)


def pick_music(music_dir: Path, subdir: str | None = None) -> Path | None:
    patterns = ("*.mp3", "*.ogg", "*.wav")
    folders = [music_dir / subdir, music_dir] if subdir else [music_dir]
    for folder in folders:
        files = [f for pattern in patterns for f in folder.glob(pattern)]
        if files:
            return random.choice(files)
    return None


@dataclass(frozen=True)
class KaraokeWindow:
    before: list[str]
    current: str
    after: list[str]

    @property
    def words(self) -> list[str]:
        return [w for w in (*self.before, self.current, *self.after) if w]


def karaoke_window(words: list[WordEvent], t: float) -> KaraokeWindow:
    if not words:
        return KaraokeWindow([], "", [])
    index = next((i for i in range(len(words) - 1, -1, -1) if words[i].start <= t), 0)
    line_start = (index // WORDS_PER_LINE) * WORDS_PER_LINE
    return KaraokeWindow(
        before=[w.word for w in words[line_start:index]],
        current=words[index].word,
        after=[w.word for w in words[index + 1 : line_start + WORDS_PER_LINE]],
    )


@dataclass(frozen=True)
class ShortsStyle:
    channel_name: str
    accent: RGB
    badge: str = "BREAKING NEWS"
    show_banner: bool = True


class ShortsRenderer:
    def __init__(self, settings: Settings, pexels: PexelsClient) -> None:
        self.settings = settings
        self.pexels = pexels
        self.size = (settings.video.width, settings.video.height)

    def render(
        self,
        news: NewsItem,
        audio_path: Path,
        words: list[WordEvent],
        style: ShortsStyle,
        output_path: Path,
        music_path: Path | None = None,
        pexels_query: str | None = None,
    ) -> Path:
        video = self.settings.video
        total = media_duration(audio_path)
        render_seconds = total + TAIL_SEC
        frame_count = round(render_seconds * video.fps)
        scene_count = max(8, math.ceil(render_seconds / video.scene_duration_sec) + 2)
        log.info("Render: %.1fs + %.1fs tail × %dfps = %d frames | ~%d scenes", total, TAIL_SEC, video.fps, frame_count, scene_count)

        query = pexels_query or pexels_query_for(news)
        slideshow = Slideshow(
            images=self.pexels.search(query, min(scene_count, _MAX_PEXELS_IMAGES), "portrait"),
            size=self.size,
            scene_seconds=video.scene_duration_sec,
            crossfade_seconds=CROSSFADE_SEC,
            zoom=KEN_BURNS_ZOOM,
        )
        if music_path:
            log.info("Background music [%.0f%%]: %s", video.music_volume * 100, music_path.name)

        def frames() -> Iterator[Image.Image]:
            for i in range(frame_count):
                t = i / video.fps
                background = slideshow.frame_at(min(t, total - 0.01), total)
                yield self._frame(news, background, karaoke_window(words, t), style, t, total)

        encode_frames(
            frames(),
            size=self.size,
            fps=video.fps,
            output_path=output_path,
            audio_path=audio_path,
            music_path=music_path,
            music_volume=video.music_volume,
            duration=total,
        )
        log.info("Video: %s (%.1f MB)", output_path, output_path.stat().st_size / 1024 / 1024)
        return output_path

    def _frame(
        self,
        news: NewsItem,
        background: Image.Image | None,
        window: KaraokeWindow,
        style: ShortsStyle,
        t: float,
        total: float,
    ) -> Image.Image:
        width, height = self.size
        if background is not None:
            frame = d.composite(background, d.full_shade(self.size, 148), d.bottom_shade(self.size, 700, 230, 1.4))
        else:
            frame = d.vertical_gradient(self.size, (5, 15, 45), (0, 0, 0))
        draw = ImageDraw.Draw(frame)

        if style.show_banner:
            subtitle_y, subtitle_size = self._banner(draw, news, style)
        else:
            frame = self._watermark(frame, style)
            draw = ImageDraw.Draw(frame)
            subtitle_y, subtitle_size = (height // 2 - 120, 82) if t < HOOK_SEC else (height - 260, 62)

        self._karaoke(draw, window, subtitle_y, subtitle_size)

        if total > 0:
            filled = int(width * min(t / total, 1.0))
            draw.rectangle([0, height - PROGRESS_BAR_PX, width, height], fill=(45, 45, 45))
            draw.rectangle([0, height - PROGRESS_BAR_PX, filled, height], fill=style.accent)
        return frame

    def _banner(self, draw: ImageDraw.ImageDraw, news: NewsItem, style: ShortsStyle) -> tuple[int, int]:
        width, height = self.size
        bold, regular = self.settings.font_bold, self.settings.font_regular
        draw.text((PAD, 48), style.channel_name, font=d.load_font(bold, 34), fill=(190, 190, 190))

        badge_font = d.load_font(bold, 50)
        badge_bottom = d.draw_badge(draw, style.badge, 108, badge_font, style.accent, width, pad_x=22, pad_y=10)

        if news.direction:
            tag_font = d.load_font(regular, 34)
            d.draw_centered(draw, news.direction, badge_bottom + 18, tag_font, _TAG_BLUE, width, shadow=False)

        line_y = badge_bottom + 62
        draw.rectangle([PAD, line_y, width - PAD, line_y + 4], fill=style.accent)

        title_font = d.load_font(bold, 60)
        y = line_y + 38
        for line in d.wrap_text(news.title, title_font, width - PAD * 2):
            d.draw_shadowed(draw, (PAD, y), line, title_font, d.WHITE)
            y += title_font.size + 8
        return height - 180, 54

    def _watermark(self, frame: Image.Image, style: ShortsStyle) -> Image.Image:
        overlay = Image.new("RGBA", self.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).text(
            (PAD, 44), style.channel_name, font=d.load_font(self.settings.font_bold, 26), fill=(*style.accent, 160)
        )
        return d.composite(frame, overlay)

    def _karaoke(self, draw: ImageDraw.ImageDraw, window: KaraokeWindow, y: int, base_size: int) -> None:
        words = window.words
        if not words:
            return
        width = self.size[0]
        max_width = width - PAD * 2
        font = self._fit_font(words, base_size, max_width)
        space = max(d.text_width(font, " "), 6)
        total_width = sum(d.text_width(font, w) for w in words) + space * (len(words) - 1)
        x = max(PAD, (width - total_width) // 2)

        def put(word: str, color: RGB, underline: bool) -> None:
            nonlocal x
            word_width = d.text_width(font, word)
            fill = d.GOLD if is_power_word(word) else color
            d.draw_shadowed(draw, (x, y), word, font, fill)
            if underline:
                draw.rectangle([x, y + font.size + 3, x + word_width, y + font.size + 8], fill=d.GOLD)
            x += word_width + space

        for word in window.before:
            put(word, _DIM, underline=False)
        if window.current:
            put(window.current, d.WHITE, underline=True)
        for word in window.after:
            put(word, _DIM, underline=False)

    def _fit_font(self, words: list[str], base_size: int, max_width: int) -> d.Font:
        bold = self.settings.font_bold
        for size in range(base_size, 28, -4):
            font = d.load_font(bold, size)
            space = max(font.getbbox(" ")[2] - font.getbbox("")[2], 6)
            if sum(d.text_width(font, w) for w in words) + space * (len(words) - 1) <= max_width:
                return font
        return d.load_font(bold, 30)
