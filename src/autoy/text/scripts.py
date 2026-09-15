from __future__ import annotations

import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_BANNED_FILLER = (
    "additionally,",
    "furthermore,",
    "moreover,",
    "in this video",
    "in this short",
    "let's explore",
    "we will discuss",
    "it is important to note",
    "plays a crucial role",
    "in conclusion",
    "кроме того,",
    "более того,",
    "также стоит отметить",
    "важно отметить",
    "играет ключевую роль",
    "в заключение",
    "в этом видео",
    "по сообщениям сми",
    "как сообщает",
)

_WEAK_TITLE_STARTS = (
    "россия",
    "украина",
    "сша",
    "китай",
    "евросоюз",
    "ес ",
    "нато",
    "кндр",
    "russia",
    "ukraine",
    "the us",
    "us ",
    "china",
    "nato",
    "eu ",
)

_TOPIC_STOP_WORDS = {"news", "today", "latest", "новости", "сегодня", "and", "the", "war"}

_TITLE_STOP_WORDS = {
    "и",
    "в",
    "на",
    "с",
    "по",
    "не",
    "из",
    "от",
    "для",
    "что",
    "как",
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "are",
    "was",
    "your",
    "you",
    "they",
    "them",
    "their",
    "have",
    "been",
    "will",
    "does",
}


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text.strip()) if part.strip()]


def _clip_tail(text: str, limit: int, min_sentence_end: int) -> str:
    clipped = text[:limit].rstrip()
    sentence_end = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if sentence_end >= min_sentence_end:
        return clipped[: sentence_end + 1]
    return clipped.rsplit(" ", 1)[0].rstrip(" ,;:") + "."


def truncate_to_limit(text: str, limit: int, min_sentence_end: int = 240) -> str:
    if len(text) <= limit:
        return text
    sentences = split_sentences(text)
    if len(sentences) >= 4:
        head, tail = sentences[:1], sentences[-2:]
        middle = sentences[1:-2]
        while middle and len(" ".join(head + middle + tail)) > limit:
            middle.pop()
        candidate = " ".join(head + middle + tail)
        if len(candidate) <= limit:
            return candidate
    return _clip_tail(text, limit, min_sentence_end)


def truncate_tail(text: str, limit: int, min_sentence_end: int) -> str:
    if len(text) <= limit:
        return text
    return _clip_tail(text, limit, min_sentence_end)


def shorten_script(text: str, drop: int = 1) -> str | None:
    sentences = split_sentences(text)
    if len(sentences) - drop < 3:
        return None
    head, tail = sentences[:1], sentences[-2:]
    middle = sentences[1:-2]
    if len(middle) <= drop:
        return None
    return " ".join(head + middle[: len(middle) - drop] + tail)


def has_filler(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _BANNED_FILLER)


def is_weak_title(title: str) -> bool:
    stripped = title.strip().strip('"«»')
    if not stripped:
        return True
    if len(stripped.split()) > 9:
        return True
    return stripped.lower().startswith(_WEAK_TITLE_STARTS)


def topic_key(topic: str) -> str:
    words = [w.lower() for w in topic.split() if w.lower() not in _TOPIC_STOP_WORDS and len(w) > 3]
    return words[0] if words else topic.split()[0].lower()


def _content_words(text: str) -> set[str]:
    return {w for w in text.lower().split() if len(w) > 3 and w not in _TITLE_STOP_WORDS}


def title_overlap(a: str, b: str) -> float:
    words_a, words_b = _content_words(a), _content_words(b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / min(len(words_a), len(words_b))


def is_latin(text: str, threshold: float = 0.6) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if ord(c) < 256) / len(letters) > threshold


def clean_for_description(text: str) -> str:
    text = re.sub(r"\s*\[\d+(?:[-–,]\s*\d+)*\]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\bwww\.\S+", "", text)
    text = re.sub(r"\S+@\S+\.\w{2,}", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def clip_title(title: str, limit: int = 100) -> str:
    return title if len(title) <= limit else title[: limit - 3] + "..."
