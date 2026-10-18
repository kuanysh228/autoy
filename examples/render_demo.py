"""Render a sample Shorts video without any API keys.

Uses the real renderer and edge-tts narration, with generated abstract backgrounds
instead of Pexels photos. Output: output/videos/demo.mp4 under the project home.

    python examples/render_demo.py
"""

from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFilter

from autoy.channels import get_channel
from autoy.config import Settings
from autoy.media import PexelsClient, ShortsRenderer
from autoy.media.shorts import ShortsStyle
from autoy.models import NewsItem
from autoy.tts import build_synthesizer, synthesize

SCRIPT = (
    "This video was made without a camera, a voice actor, or an editor. "
    "A program researched the story, wrote the script, and recorded the narration. "
    "Every word you hear is timed to the subtitles on screen. "
    "Then it rendered the frames and uploaded the finished video by itself. "
    "Would you trust a robot to run your news channel? "
    "Follow, because the next one is even faster."
)

PALETTES = [((0, 120, 255), (120, 0, 255)), ((0, 200, 255), (0, 80, 160)), ((255, 80, 160), (80, 0, 200)), ((0, 220, 180), (0, 60, 140))]


class AbstractBackgrounds(PexelsClient):
    """Drop-in replacement for PexelsClient that paints blurred colour blobs."""

    @property
    def enabled(self) -> bool:
        return True

    def search(self, query: str, count: int, orientation: str) -> list[Image.Image]:
        rng = random.Random(7)
        images = []
        for i in range(count):
            first, second = PALETTES[i % len(PALETTES)]
            image = Image.new("RGB", (1080, 1920), (6, 8, 22))
            draw = ImageDraw.Draw(image)
            for _ in range(7):
                radius = rng.randint(220, 520)
                x, y = rng.randint(-100, 1180), rng.randint(0, 1920)
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=first if rng.random() < 0.5 else second)
            images.append(image.filter(ImageFilter.GaussianBlur(160)))
        return images


def main() -> None:
    settings = Settings.from_env()
    settings.paths.ensure()
    channel = get_channel("ai")
    news = NewsItem("Nobody edited this video", SCRIPT, "#Automation")

    speech = synthesize(build_synthesizer("edge", settings), SCRIPT, "en", settings.paths.audio)
    renderer = ShortsRenderer(settings, AbstractBackgrounds("demo", settings.paths.cache / "pexels"))
    output = settings.paths.videos / "demo.mp4"
    renderer.render(news, speech.path, speech.words, ShortsStyle(channel.name, channel.accent, "AUTOMATED", True), output)
    print(output)


if __name__ == "__main__":
    main()
