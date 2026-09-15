from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from autoy.config import Settings
from autoy.media import draw as d
from autoy.media.pexels import PexelsClient
from autoy.models import RGB

log = logging.getLogger(__name__)

SIZE = (1280, 720)
_TAG = "ИТОГИ НЕДЕЛИ"


def _output(directory: Path, kind: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"thumbnail_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{kind}.jpg"


class ThumbnailMaker:
    def __init__(self, settings: Settings, pexels: PexelsClient) -> None:
        self.settings = settings
        self.pexels = pexels

    def story(
        self,
        channel_name: str,
        week_label: str,
        story_labels: list[str],
        accent: RGB,
        pexels_query: str,
        output_path: Path | None = None,
    ) -> Path:
        output_path = output_path or _output(self.settings.paths.thumbnails, "story")
        images = self.pexels.search(pexels_query, 1, "landscape")
        if not images:
            raise RuntimeError(f"Pexels returned no photo for '{pexels_query}'")

        width, height = SIZE
        background = ImageOps.fit(images[0], SIZE, Image.LANCZOS).convert("RGBA")
        shade = Image.new("RGBA", SIZE, (0, 0, 0, 0))
        shade_draw = ImageDraw.Draw(shade)
        for y in range(height):
            shade_draw.line([(0, y), (width, y)], fill=(0, 0, 0, int(60 + 170 * (y / height) ** 1.3)))
        image = Image.alpha_composite(background, shade).convert("RGB")
        draw = ImageDraw.Draw(image)
        bold, regular = self.settings.font_bold, self.settings.font_regular
        pad = 56

        d.draw_stroked(draw, (pad, 28), channel_name.upper(), d.load_font(bold, 30), stroke_width=4)
        week_font = d.load_font(regular, 26)
        d.draw_stroked(
            draw, (width - pad - d.text_width(week_font, week_label), 32), week_label, week_font, fill=(235, 235, 235), stroke_width=4
        )

        tag_font = d.load_font(bold, 40)
        tag_y = 84
        draw.rectangle([pad - 12, tag_y - 8, pad + d.text_width(tag_font, _TAG) + 16, tag_y + tag_font.size + 10], fill=accent)
        draw.text((pad + 2, tag_y), _TAG, font=tag_font, fill=d.WHITE)

        keywords = [label.upper() for label in story_labels[:3]]
        size = 108
        keyword_font = d.load_font(bold, size)
        while size > 60 and any(d.text_width(keyword_font, k) > width - pad * 2 for k in keywords):
            size -= 8
            keyword_font = d.load_font(bold, size)
        line_height = keyword_font.size + 8
        y = height - 56 - line_height * len(keywords)
        for keyword in keywords:
            d.draw_stroked(draw, (pad, y), keyword, keyword_font, stroke_width=7)
            keyword_width = min(d.text_width(keyword_font, keyword), width - pad * 2)
            draw.rectangle([pad, y + keyword_font.size + 2, pad + keyword_width, y + keyword_font.size + 8], fill=accent)
            y += line_height

        image.save(output_path, "JPEG", quality=92)
        log.info("Story thumbnail saved: %s", output_path)
        return output_path

    def minimalist(
        self,
        title: str,
        channel_name: str,
        week_label: str,
        story_labels: list[str],
        accent: RGB,
        output_path: Path | None = None,
    ) -> Path:
        output_path = output_path or _output(self.settings.paths.thumbnails, "minimal")
        width, height = SIZE
        bold, regular = self.settings.font_bold, self.settings.font_regular
        pad = 56

        image = d.vertical_gradient(SIZE, (8, 8, 18), (4, 4, 10))
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, width, 5], fill=accent)

        header_font = d.load_font(regular, 28)
        draw.text((pad, 28), channel_name.upper(), font=header_font, fill=(160, 160, 180))
        draw.text((width - pad - d.text_width(header_font, week_label), 28), week_label, font=header_font, fill=(160, 160, 180))

        d.draw_centered(draw, _TAG, 110, d.load_font(bold, 44), accent, width, shadow=False)
        draw.rectangle([pad, 174, width - pad, 176], fill=accent)

        title_font = d.load_font(bold, 80)
        lines = d.wrap_text(title, title_font, width - pad * 2)
        if len(lines) > 2:
            title_font = d.load_font(bold, 60)
            lines = d.wrap_text(title, title_font, width - pad * 2)
        lines = lines[:2]
        line_height = title_font.size + 12
        y = (height - line_height * len(lines)) // 2 - 20
        for line in lines:
            draw.text((pad, y), line, font=title_font, fill=(245, 245, 255))
            y += line_height

        separator_y = y + 24
        draw.rectangle([pad, separator_y, width - pad, separator_y + 2], fill=accent)

        if story_labels:
            label_font = d.load_font(regular, 30)
            per_column = (len(story_labels) + 1) // 2
            column_width = (width - pad * 2) // 2
            for i, label in enumerate(story_labels[:8]):
                x = pad + (i // per_column) * column_width
                label_y = separator_y + 30 + (i % per_column) * (label_font.size + 10)
                draw.text((x, label_y), f"• {label}", font=label_font, fill=(180, 180, 200))

        draw.rectangle([0, height - 5, width, height], fill=accent)
        image.save(output_path, "JPEG", quality=95)
        log.info("Minimalist thumbnail saved: %s", output_path)
        return output_path
