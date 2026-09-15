from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from autoy.models import Voice, WordEvent


@dataclass(frozen=True)
class Speech:
    path: Path
    words: list[WordEvent]
    voice: Voice


class Synthesizer(Protocol):
    name: str

    def synthesize(self, text: str, lang: str, output_path: Path, voice: Voice | None = None) -> Speech: ...


def timestamped_path(directory: Path, prefix: str, suffix: str = ".mp3") -> Path:
    return directory / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{suffix}"
