from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

RGB = tuple[int, int, int]


@dataclass
class NewsItem:
    title: str
    text: str
    direction: str = ""
    sources: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NewsItem:
        return cls(
            title=data["title"],
            text=data["text"],
            direction=data.get("direction", ""),
            sources=list(data.get("sources", [])),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class WeeklyStory:
    label: str
    title: str
    text: str
    direction: str
    pexels_query: str


@dataclass(frozen=True)
class WordEvent:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    rate: str = "+0%"
    pitch: str = "+0Hz"
    style: str | None = None
