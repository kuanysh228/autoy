from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Article:
    title: str
    text: str
    direction: str


class ArticleParseError(ValueError):
    pass


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    if text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    return text


def parse_article(raw: str) -> Article:
    try:
        data = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as exc:
        raise ArticleParseError("model returned invalid JSON for the article") from exc
    if not isinstance(data, dict):
        raise ArticleParseError("article output must be a JSON object")

    fields: dict[str, str] = {}
    for name in ("title", "text", "direction"):
        if name not in data:
            raise ArticleParseError(f"missing required article field: {name}")
        fields[name] = str(data[name]).strip()
    if not all(fields.values()):
        raise ArticleParseError("article fields title, text and direction must not be empty")
    return Article(**fields)
