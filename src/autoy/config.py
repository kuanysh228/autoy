from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def resolve_home() -> Path:
    return Path(os.environ.get("AUTOY_HOME") or Path.cwd()).resolve()


_FONT_DIRS = (
    "/usr/share/fonts/liberation",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/liberation-sans",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
)


def find_font(bold: bool) -> str:
    names = ("LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf") if bold else ("LiberationSans-Regular.ttf", "DejaVuSans.ttf")
    candidates = [Path(directory) / name for name in names for directory in _FONT_DIRS]
    return str(next((path for path in candidates if path.is_file()), candidates[0]))


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.strip().startswith("#") else ""
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


class Env:
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = values

    def str(self, name: str, default: str = "") -> str:
        return self._values.get(name, default).strip()

    def int(self, name: str, default: int) -> int:
        raw = self.str(name)
        return int(raw) if raw else default

    def float(self, name: str, default: float) -> float:
        raw = self.str(name)
        return float(raw) if raw else default

    def list(self, name: str, default: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.str(name, default).split(",") if item.strip())

    def map(self, name: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for pair in self.str(name).split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                result[key.strip()] = value.strip()
        return result


@dataclass(frozen=True)
class Paths:
    home: Path

    @property
    def output(self) -> Path:
        return self.home / "output"

    @property
    def videos(self) -> Path:
        return self.output / "videos"

    @property
    def audio(self) -> Path:
        return self.output / "audio"

    @property
    def logs(self) -> Path:
        return self.output / "logs"

    @property
    def thumbnails(self) -> Path:
        return self.output / "thumbnails"

    @property
    def data(self) -> Path:
        return self.home / "data"

    @property
    def music(self) -> Path:
        return self.data / "music"

    @property
    def models(self) -> Path:
        return self.home / "models"

    @property
    def credentials(self) -> Path:
        return self.home / "credentials"

    @property
    def cache(self) -> Path:
        return self.home / "cache"

    @property
    def pipeline_db(self) -> Path:
        return self.data / "pipeline.db"

    @property
    def bot_db(self) -> Path:
        return self.data / "telegram_bot.db"

    def ensure(self) -> None:
        for directory in (
            self.videos,
            self.audio,
            self.logs,
            self.thumbnails,
            self.data,
            self.credentials,
            self.cache,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class VideoSettings:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    max_duration_sec: float = 34.0
    scene_duration_sec: float = 2.2
    music_volume: float = 0.13


@dataclass(frozen=True)
class Settings:
    paths: Paths
    video: VideoSettings
    font_bold: str
    font_regular: str
    audio_lang: str
    max_posts_per_day: int
    schedule_times: tuple[str, ...]
    weekly_time: str
    weekly_channel: str
    weekly_max_topics: int
    telegram_channel_times: tuple[str, ...]
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_channel_id: str
    telegram_news_channel: str
    youtube_api_key: str
    youtube_daily_quota_units: int
    youtube_upload_quota_cost: int
    youtube_channel_ids: dict[str, str]
    pexels_api_key: str

    @classmethod
    def from_env(cls) -> Settings:
        home = resolve_home()
        env = Env({**read_env_file(home / ".env"), **os.environ})
        paths = Paths(home=home)
        return cls(
            paths=paths,
            video=VideoSettings(
                fps=env.int("VIDEO_FPS", 30),
                max_duration_sec=env.float("MAX_DURATION_SEC", 34.0),
                scene_duration_sec=env.float("SCENE_DURATION_SEC", 2.2),
            ),
            font_bold=env.str("FONT_BOLD") or find_font(bold=True),
            font_regular=env.str("FONT_REGULAR") or find_font(bold=False),
            audio_lang=env.str("AUDIO_LANG", "en"),
            max_posts_per_day=env.int("MAX_POSTS_PER_DAY", 5),
            schedule_times=env.list("SCHEDULE_TIMES", "10:00,19:00"),
            weekly_time=env.str("WEEKLY_TIME", "10:00"),
            weekly_channel=env.str("WEEKLY_CHANNEL", "world"),
            weekly_max_topics=env.int("WEEKLY_MAX_TOPICS", 8),
            telegram_channel_times=env.list("TELEGRAM_CHANNEL_TIMES", "09:00,12:00,15:00,18:00,21:00"),
            telegram_bot_token=env.str("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=env.str("TELEGRAM_CHAT_ID"),
            telegram_channel_id=env.str("TELEGRAM_CHANNEL_ID"),
            telegram_news_channel=env.str("TELEGRAM_NEWS_CHANNEL", "world"),
            youtube_api_key=env.str("YOUTUBE_API_KEY"),
            youtube_daily_quota_units=env.int("YOUTUBE_DAILY_QUOTA_UNITS", 10_000),
            youtube_upload_quota_cost=env.int("YOUTUBE_UPLOAD_QUOTA_COST", 1_600),
            youtube_channel_ids=env.map("YOUTUBE_CHANNEL_IDS"),
            pexels_api_key=env.str("PEXELS_API_KEY"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings.from_env()
    settings.paths.ensure()
    return settings
