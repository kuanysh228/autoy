from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from contextvars import ContextVar

from autoy.channels import WeeklyTopic
from autoy.models import NewsItem, WeeklyStory
from autoy.sources import google_news
from autoy.sources.prompts import shorts_rules
from autoy.text import (
    TextQualityError,
    has_filler,
    is_latin,
    is_weak_title,
    prepare_voiceover_text,
    remove_source_refs,
    truncate_tail,
    truncate_to_limit,
)

log = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 900
WEEKLY_MAX_CHARS = 1700
WEEKLY_MIN_CHARS = 200
_ATTEMPTS = 3
_article_rules: ContextVar[str] = ContextVar("autoy_article_rules", default="")


def _install_prompt_hook() -> None:
    from newsscout import pipeline, prompts

    if getattr(pipeline.build_article_question, "autoy_hook", False):
        return

    def with_rules(user_query: str, language: str | None = None) -> str:
        return prompts.build_article_question(user_query, language=language) + _article_rules.get()

    with_rules.autoy_hook = True
    pipeline.build_article_question = with_rules


def _fallback_from_rss(topic: str, lang: str, reason: Exception) -> NewsItem:
    items = google_news.search(topic, lang)
    if not items:
        raise TextQualityError(f"RSS fallback found nothing: {reason}") from reason

    lead = items[0]
    sources = ", ".join(dict.fromkeys(item.source for item in items[:3] if item.source)) or "several outlets"

    if lang == "en":
        others = [item.title.rstrip(".") for item in items[1:3]]
        context = "; ".join(others) if others else lead.title
        title = lead.title
        text = (
            f"{sources} report the main headline: {lead.title.rstrip('.')}. "
            f"Other reports point to the same pressure line: {context}. "
            "Analysts note this reflects a broader struggle over leverage, security guarantees, and core national interests. "
            "Even small signals now matter: one failed message can quickly turn diplomacy into escalation. "
            "For now, this looks less like a finished deal and more like a tense pause before the next move."
        )
    else:
        ru_lead = next((item for item in items if not is_latin(item.title)), lead)
        others = [item.title.rstrip(".") for item in items[1:3] if not is_latin(item.title)]
        context = f" {'; '.join(others)}." if others else ""
        title = ru_lead.title
        text = (
            f"Редакции {sources} выделяют эту тему как главную на этой неделе.{context} "
            "Эксперты отмечают, что ситуация отражает борьбу за влияние, гарантии безопасности и ключевые национальные интересы. "
            "Каждый сигнал сейчас имеет значение: одно неверное решение может превратить дипломатию в эскалацию. "
            "Пока это больше похоже на напряжённую паузу, чем на окончательное урегулирование."
        )

    log.warning("NewsScout fallback: using Google News RSS after error: %s", reason)
    return NewsItem(
        title=title,
        text=prepare_voiceover_text(truncate_tail(text, DEFAULT_MAX_CHARS, 240), lang=lang),
        direction=f"#{topic.split()[0].capitalize()}",
        sources=[item.source_url or item.link for item in items[:4] if item.source_url or item.link],
    )


class NewsScoutSource:
    def __init__(self, attempts: int = _ATTEMPTS) -> None:
        self.attempts = attempts

    @staticmethod
    def _client():
        from newsscout import NewsScout

        _install_prompt_hook()
        return NewsScout()

    async def fetch_short(self, topic: str, lang: str, max_chars: int = DEFAULT_MAX_CHARS) -> NewsItem:
        log.info("NewsScout: '%s' [%s] max_chars=%d", topic, lang, max_chars)
        scout = self._client()
        last_error: Exception | None = None

        for attempt in range(1, self.attempts + 1):
            try:
                token = _article_rules.set(shorts_rules(lang))
                try:
                    article = await scout.generate(topic, language=lang)
                finally:
                    _article_rules.reset(token)
                candidate = prepare_voiceover_text(remove_source_refs(article.text), lang=lang)
                text = prepare_voiceover_text(truncate_to_limit(candidate, max_chars), lang=lang)
                if has_filler(text):
                    raise TextQualityError("filler phrases detected")
                if attempt < self.attempts and is_weak_title(article.title):
                    raise TextQualityError(f"weak newswire title: {article.title}")
                log.info("Script (%d chars, %d words): %s…", len(text), len(text.split()), text[:80])
                return NewsItem(title=article.title, text=text, direction=article.direction)
            except TextQualityError as exc:
                last_error = exc
                log.warning("NewsScout: unusable script, attempt %d/%d: %s", attempt, self.attempts, exc)
            except Exception as exc:
                last_error = exc
                log.warning("NewsScout: generation failed, attempt %d/%d: %s", attempt, self.attempts, exc)

        return _fallback_from_rss(topic, lang, last_error or TextQualityError("unknown NewsScout error"))

    async def fetch_story(self, topic: WeeklyTopic, lang: str) -> WeeklyStory | None:
        scout = self._client()
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                article = await scout.generate(topic.query)
                candidate = prepare_voiceover_text(remove_source_refs(article.text), lang=lang)
                text = prepare_voiceover_text(truncate_tail(candidate, WEEKLY_MAX_CHARS, 400), lang=lang)
                if len(text) < WEEKLY_MIN_CHARS:
                    raise TextQualityError(f"story too short: {len(text)} chars")
                log.info("  [%s] %s…", topic.label, article.title[:70])
                return WeeklyStory(topic.label, article.title, text, article.direction, topic.pexels_query)
            except Exception as exc:
                last_error = exc
                log.warning("  [%s] attempt %d/%d failed: %s", topic.label, attempt, self.attempts, exc)
        log.error("  [%s] gave up: %s", topic.label, last_error)
        return None

    async def fetch_weekly(self, topics: Sequence[WeeklyTopic], lang: str, max_items: int) -> list[WeeklyStory]:
        selected = list(topics[:max_items])
        log.info("Weekly digest: fetching %d stories in parallel", len(selected))
        results = await asyncio.gather(*(self.fetch_story(topic, lang) for topic in selected), return_exceptions=True)
        stories = [r for r in results if isinstance(r, WeeklyStory)]
        for result in results:
            if isinstance(result, Exception):
                log.warning("Story task crashed: %s", result)
        log.info("Fetched %d/%d stories", len(stories), len(selected))
        return stories
