from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps


def prefit(images: list[Image.Image], size: tuple[int, int]) -> list[Image.Image]:
    return [ImageOps.fit(image, size, Image.LANCZOS) for image in images]


def _pan(direction: int, progress: float, wide: bool) -> tuple[float, float]:
    if not wide:
        x = 0.5 * progress if direction % 2 == 0 else 1 - 0.5 * progress
        return x, 0.4 * progress
    mode = direction % 4
    if mode == 0:
        return 0.9 * progress, 0.3
    if mode == 1:
        return 1 - 0.9 * progress, 0.7
    if mode == 2:
        return 0.6 * progress, 0.6 * progress
    return 1 - 0.6 * progress, 1 - 0.6 * progress


def ken_burns(image: Image.Image, progress: float, direction: int, size: tuple[int, int], zoom: float, wide: bool) -> Image.Image:
    width, height = size
    scale = 1.0 + zoom * progress
    crop_w, crop_h = int(width / scale), int(height / scale)
    max_x, max_y = width - crop_w, height - crop_h
    px, py = _pan(direction, progress, wide)
    x = max(0, min(int(max_x * px), max_x))
    y = max(0, min(int(max_y * py), max_y))
    cropped = image.crop((x, y, x + crop_w, y + crop_h))
    if crop_w < width or crop_h < height:
        return cropped.resize(size, Image.BILINEAR)
    return cropped


@dataclass
class Slideshow:
    images: list[Image.Image]
    size: tuple[int, int]
    scene_seconds: float
    crossfade_seconds: float
    zoom: float
    wide_pan: bool = False
    stretch_to_total: bool = False

    def __post_init__(self) -> None:
        self.images = prefit(self.images, self.size)

    def __bool__(self) -> bool:
        return bool(self.images)

    def _scene_count(self, total: float) -> int:
        if not self.stretch_to_total:
            return len(self.images)
        return min(len(self.images), max(1, round(total / self.scene_seconds)))

    def frame_at(self, t: float, total: float) -> Image.Image | None:
        if not self.images:
            return None
        scenes = self._scene_count(total)
        scene_len = total / scenes if self.stretch_to_total else self.scene_seconds
        index = min(int(t / scene_len), scenes - 1)
        local = (t - index * scene_len) / scene_len
        current = self.images[index % len(self.images)]
        frame = ken_burns(current, local, index, self.size, self.zoom, self.wide_pan)

        fade_fraction = self.crossfade_seconds / self.scene_seconds
        if local >= 1.0 - fade_fraction and index < scenes - 1:
            alpha = min(1.0, (local - (1.0 - fade_fraction)) / fade_fraction)
            following = self.images[(index + 1) % len(self.images)]
            frame = Image.blend(frame, ken_burns(following, 0.0, index + 1, self.size, self.zoom, self.wide_pan), alpha)
        return frame
