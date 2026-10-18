from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from autoy.models import RGB

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)
GOLD: RGB = (255, 215, 0)


@lru_cache(maxsize=64)
def load_font(path: str, size: int) -> Font:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def text_width(font: Font, text: str) -> int:
    box = font.getbbox(text)
    return box[2] - box[0]


def wrap_text(text: str, font: Font, max_width: int) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    for word in text.split():
        candidate = " ".join([*current, word])
        if current and font.getbbox(candidate)[2] > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def vertical_gradient(size: tuple[int, int], top: RGB, bottom: RGB) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def bottom_shade(size: tuple[int, int], height: int, alpha: int, power: float) -> Image.Image:
    width, full_height = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for i in range(height):
        a = int(alpha * (i / height) ** power)
        draw.line([(0, full_height - height + i), (width, full_height - height + i)], fill=(0, 0, 0, a))
    return overlay


def top_shade(size: tuple[int, int], height: int, alpha: int, power: float) -> Image.Image:
    width, _ = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for i in range(height):
        a = int(alpha * ((height - i) / height) ** power)
        draw.line([(0, i), (width, i)], fill=(0, 0, 0, a))
    return overlay


def full_shade(size: tuple[int, int], alpha: int) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, alpha))


def composite(base: Image.Image, *layers: Image.Image) -> Image.Image:
    result = base.convert("RGBA")
    for layer in layers:
        result = Image.alpha_composite(result, layer)
    return result.convert("RGB")


def draw_shadowed(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: Font, fill: RGB, offset: int = 2) -> None:
    x, y = xy
    draw.text((x + offset, y + offset), text, font=font, fill=BLACK)
    draw.text((x, y), text, font=font, fill=fill)


def draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font: Font, fill: RGB, width: int, shadow: bool = True) -> None:
    x = (width - text_width(font, text)) // 2
    if shadow:
        draw_shadowed(draw, (x, y), text, font, fill)
    else:
        draw.text((x, y), text, font=font, fill=fill)


def draw_stroked(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: Font, fill: RGB = WHITE, stroke_width: int = 6) -> None:
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=BLACK)


def draw_badge(draw: ImageDraw.ImageDraw, text: str, y: int, font: Font, accent: RGB, width: int, pad_x: int, pad_y: int) -> int:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = (width - (right - left)) // 2 - left
    draw.rectangle([x + left - pad_x, y + top - pad_y, x + right + pad_x, y + bottom + pad_y], fill=accent)
    draw_shadowed(draw, (x, y), text, font, WHITE)
    return y + bottom
