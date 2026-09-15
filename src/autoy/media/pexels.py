from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import requests
from PIL import Image

log = logging.getLogger(__name__)

Orientation = Literal["portrait", "landscape"]

_SEARCH_URL = "https://api.pexels.com/v1/search"
_MAX_PER_PAGE = 80


class PexelsClient:
    def __init__(self, api_key: str, cache_dir: Path, timeout: int = 20) -> None:
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, count: int, orientation: Orientation) -> list[Image.Image]:
        if not self.enabled:
            return []
        cache = self.cache_dir / orientation
        cache.mkdir(parents=True, exist_ok=True)
        try:
            response = requests.get(
                _SEARCH_URL,
                headers={"Authorization": self.api_key},
                params={"query": query, "per_page": min(count + 3, _MAX_PER_PAGE), "orientation": orientation},
                timeout=self.timeout,
            )
            response.raise_for_status()
            photos = response.json().get("photos", [])[:count]
        except requests.RequestException as exc:
            log.warning("Pexels [%s]: %s", query, exc)
            return []

        images: list[Image.Image] = []
        for photo in photos:
            path = cache / f"{photo['id']}.jpg"
            if not path.exists() and not self._download(photo, path):
                continue
            try:
                images.append(Image.open(path).convert("RGB"))
            except OSError:
                path.unlink(missing_ok=True)
        log.info("Pexels: %d photos for '%s'", len(images), query)
        return images

    def _download(self, photo: dict, path: Path) -> bool:
        url = photo["src"].get("large2x") or photo["src"]["large"]
        try:
            path.write_bytes(requests.get(url, timeout=30).content)
        except requests.RequestException as exc:
            log.warning("Pexels download %s: %s", photo["id"], exc)
            return False
        return True
