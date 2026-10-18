from __future__ import annotations

from dataclasses import dataclass, field

from autoy.config import Settings, get_settings
from autoy.media import PexelsClient, ShortsRenderer, ThumbnailMaker, WeeklyRenderer
from autoy.publish import Notifier
from autoy.sources import ResearchSource
from autoy.storage import PostRegistry
from autoy.tts import Synthesizer, build_synthesizer


@dataclass
class AppContext:
    settings: Settings
    registry: PostRegistry
    source: ResearchSource
    notifier: Notifier
    pexels: PexelsClient
    synthesizer: Synthesizer
    shorts_renderer: ShortsRenderer = field(init=False)
    weekly_renderer: WeeklyRenderer = field(init=False)
    thumbnails: ThumbnailMaker = field(init=False)

    def __post_init__(self) -> None:
        self.shorts_renderer = ShortsRenderer(self.settings, self.pexels)
        self.weekly_renderer = WeeklyRenderer(self.settings, self.pexels)
        self.thumbnails = ThumbnailMaker(self.settings, self.pexels)

    @classmethod
    def build(cls, tts_backend: str = "edge", settings: Settings | None = None) -> AppContext:
        settings = settings or get_settings()
        return cls(
            settings=settings,
            registry=PostRegistry(settings.paths.pipeline_db),
            source=ResearchSource(),
            notifier=Notifier.from_settings(settings),
            pexels=PexelsClient(settings.pexels_api_key, settings.paths.cache / "pexels"),
            synthesizer=build_synthesizer(tts_backend, settings),
        )
