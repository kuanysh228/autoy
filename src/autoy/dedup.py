from __future__ import annotations

import logging
import random
from collections.abc import Sequence

from autoy.text import title_overlap, topic_key

log = logging.getLogger(__name__)


class DuplicateNews(RuntimeError):
    pass


def pick_fresh_topic(topics: Sequence[str], recent_titles: Sequence[str]) -> str:
    shuffled = list(topics)
    random.shuffle(shuffled)
    for topic in shuffled:
        key = topic_key(topic)
        if not any(key in title for title in recent_titles):
            return topic
    log.warning("All topics were used recently, picking a random one")
    return random.choice(shuffled)


def find_similar(title: str, recent_titles: Sequence[str], threshold: float = 0.5) -> str | None:
    for recent in recent_titles:
        overlap = title_overlap(title, recent)
        if overlap >= threshold:
            log.warning("Similar story posted recently (%.0f%% overlap): %s", overlap * 100, recent)
            return recent
    return None
