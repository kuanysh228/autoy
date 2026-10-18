from __future__ import annotations

from datetime import date, timedelta

SUPPORTED_LANGUAGES = ("en", "ru")

_LANGUAGE_NAMES = {"en": "English", "ru": "Russian"}

_EDITOR_PROMPTS = {
    "en": (
        "You are a news editor. Write concisely, concretely, and without fluff. "
        "Choose the freshest, most important, and most verifiable news item. "
        "Do not invent facts; rely only on the provided sources."
    ),
    "ru": (
        "Ты новостной редактор. Пиши кратко, конкретно, без воды. "
        "Выбирай самую свежую, важную и проверяемую новость. "
        "Не придумывай факты, опирайся только на источники."
    ),
}


def normalize_language(language: str | None) -> str:
    normalized = (language or "en").strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language!r}. Supported: {', '.join(SUPPORTED_LANGUAGES)}")
    return normalized


def editor_prompt(language: str | None = None) -> str:
    return _EDITOR_PROMPTS[normalize_language(language)]


def build_research_query(topic: str, language: str | None = None, today: date | None = None) -> str:
    today = today or date.today()
    week_ago = today - timedelta(days=7)
    label = _LANGUAGE_NAMES[normalize_language(language)]
    return f"""
Find recent news sources for the following request:

{topic}

Time range: {week_ago.isoformat()} to {today.isoformat()}.

Write the research notes and source selection in {label}.
Prefer reliable, established news outlets and primary sources.
Avoid advertisements, duplicated stories, and low-quality content.
""".strip()


def build_article_question(topic: str, language: str | None = None, rules: str = "") -> str:
    normalized = normalize_language(language)
    question = f"""
Based on the provided sources, answer the following request:

{topic}

Select one most important, fresh, and interesting news item from the last week.

Write the final article in {_LANGUAGE_NAMES[normalized]}.
Follow this editorial guidance:

{_EDITOR_PROMPTS[normalized]}

Return strictly JSON, with no markdown block, no explanations, and no text before or after the JSON.

Format:

{{
  "title": "...",
  "text": "...",
  "direction": "#..."
}}

Requirements:
- text must be 4-7 sentences
- do not invent facts
- use only the provided sources
- direction must be a short hashtag
""".strip()
    return question + rules
