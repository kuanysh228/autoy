from __future__ import annotations

import re


class TextQualityError(ValueError):
    pass


_TECH_LINE_RE = re.compile(
    r"""
    (?:^|\b)(
        audio|voice|tts|ssml|prosody|pitch|rate|style|voice_id|voice_name|
        config|configuration|settings|json|yaml|markdown|prompt|system|
        model|temperature|max_tokens|top_p|api_key|token|endpoint|
        озвучк\w*|голос|конфигурац\w*|настройк\w*|промпт|модель
    )(?:\b|:)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_CODEISH_RE = re.compile(
    r"""
    (```|</?\w+[^>]*>|[{][^}]*[:=][^}]*[}]|
     \b[a-zA-Z_]\w*\s*=\s*["'\w./:%+-]+|
     \b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*){1,4}\b|
     \b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b|
     --[a-z][\w-]+)
    """,
    re.VERBOSE,
)

_SOURCE_REF_RE = re.compile(r"\s*\[\d+(?:[-–,]\s*\d+)*\]")
_CODE_VALUE_RE = re.compile(r"^[a-z0-9_.\-]{1,20}$")
_NUM = r"\d+(?:[,.]\d+)?"

_SERVICE_PREFIXES = (
    "задача:",
    "требования:",
    "дополнительные требования:",
    "вариант ",
    "пример:",
    "output:",
    "ответ:",
    "формат:",
)

_CONFIG_PREFIXES = ("конфигурац", "настройк", "озвучк", "voice", "audio", "tts", "ssml")

_ABBREVIATIONS = (
    (r"\bИИ-(\w+)", r"искусственного интеллекта \1"),
    (r"\bИИ\b", "искусственный интеллект"),
    (r"\bЦБ\b", "Центральный банк"),
    (r"\bг\.\s", "года "),
    (r"\bSaaS\b", "саас"),
    (r"\bB2B\b", "бизнес для бизнеса"),
    (r"\bB2C\b", "бизнес для потребителя"),
    (r"\bIPO\b", "АйПиО"),
    (r"\bETF\b", "ЕТФ"),
)


def _drop_technical_lines(text: str) -> str:
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            kept.append(raw_line)
            continue
        lowered = line.lower()
        prefixless = lowered.lstrip("-*0123456789. )")
        if line.startswith(("```", "---", "{", "}", "[", "]")):
            continue
        is_tech = bool(_TECH_LINE_RE.search(line))
        if is_tech and (_CODEISH_RE.search(line) or ":" in line or "=" in line):
            continue
        if is_tech and prefixless.startswith(_CONFIG_PREFIXES):
            continue
        if lowered.startswith(_SERVICE_PREFIXES):
            continue
        kept.append(raw_line)
    return "\n".join(kept)


def _remove_technical_strings(text: str) -> str:
    text = re.sub(
        r"^\s*(?:текст\s+для\s+озвучки|сценарий|дикторский\s+текст|voiceover)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"[^.!?\n]*(?:конфигурац\w*|настройк\w*|voice|rate|pitch|style|ssml|tts)"
        r"[^.!?\n]*(?:=|ru-RU|en-US|Neural|newscast|%)[^.!?\n]*[.!?]?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = _drop_technical_lines(text)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\bwww\.\S+", "", text)
    text = re.sub(r"(?<!\w)/[\w/.?&=-]{3,}", "", text)
    text = re.sub(r"\S+@\S+\.\w{2,}", "", text)
    text = re.sub(r"<[^>]{1,100}>", "", text)
    text = re.sub(
        r"\bHTTPS?\s+(\d{3})(?:\s+[A-Za-z ]{1,40})?",
        lambda m: f"HTTP-ошибка {m.group(1)}",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:status|code|статус|код)\s+(\d{3})\b",
        lambda m: f"код {m.group(1)}",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\{[^}]{0,800}\}", "", text)
    text = re.sub(r"\[[^\]]{0,400}\]", "", text)
    text = re.sub(r"\bcurl\b[^\n.!?]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwget\b[^\n.!?]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[a-zA-Z_]\w*\s*=\s*[\w./\"'\-:%+]+", "", text)
    text = re.sub(r"=[\w./\"'\-:%+]+", "", text)
    text = re.sub(r"\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*){1,4}\b", "", text)
    text = re.sub(r"\b[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)+\b", "", text)
    text = re.sub(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", "", text)
    text = re.sub(r"\s--?[a-z][\w-]{1,}", " ", text)
    text = re.sub(r"\bv\d+\.\d+(?:\.\d+)?\b", "", text, flags=re.IGNORECASE)
    return text


def remove_source_refs(text: str) -> str:
    return _SOURCE_REF_RE.sub("", text)


def _normalize_space_thousands(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"(\d{1,3})\s(\d{3})(?=\D|$)", r"\1\2", text)
    return text


def _fix_quotes(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        if _CODE_VALUE_RE.match(content):
            return ""
        return f", цитирую, {content}"

    text = re.sub(r"[,:]?\s*«([^»]{1,300})»", replace, text)
    text = re.sub(r'[,:]?\s*"([^"]{1,300})"', replace, text)
    return text


def _fix_currency_and_units(text: str) -> str:
    text = re.sub(rf"\$\s*({_NUM})\s*млрд\b\.?", r"\1 миллиарда долларов", text, flags=re.I)
    text = re.sub(rf"\$\s*({_NUM})\s*млн\b\.?", r"\1 миллиона долларов", text, flags=re.I)
    text = re.sub(rf"\$\s*({_NUM})\s*тыс\b\.?", r"\1 тысячи долларов", text, flags=re.I)
    text = re.sub(rf"€\s*({_NUM})\s*млрд\b\.?", r"\1 миллиарда евро", text, flags=re.I)
    text = re.sub(rf"€\s*({_NUM})\s*млн\b\.?", r"\1 миллиона евро", text, flags=re.I)
    text = re.sub(rf"\$\s*({_NUM})", r"\1 долларов", text)
    text = re.sub(rf"€\s*({_NUM})", r"\1 евро", text)
    text = re.sub(rf"£\s*({_NUM})", r"\1 фунтов", text)
    text = re.sub(rf"₽\s*({_NUM})", r"\1 рублей", text)
    text = re.sub(rf"({_NUM})\s*млрд\b\.?", r"\1 миллиарда", text, flags=re.I)
    text = re.sub(rf"({_NUM})\s*млн\b\.?", r"\1 миллиона", text, flags=re.I)
    text = re.sub(rf"({_NUM})\s*тыс\b\.?", r"\1 тысячи", text, flags=re.I)
    text = re.sub(rf"({_NUM})\s*%", r"\1 процентов", text)
    return text


def _fix_punctuation(text: str) -> str:
    text = re.sub(r"\bв\s+(\d+)\s*[—–]\s*(\d+)\s+раз", r"в \1-\2 раз", text)
    text = re.sub(r"(\d+)\s*[—–]\s*(\d+)", r"от \1 до \2", text)
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"(?<![:/\d])([а-яёА-ЯЁa-zA-Z])\s*/\s*([а-яёА-ЯЁa-zA-Z])", r"\1 или \2", text)
    text = re.sub(r"\(([^)]{1,80})\)", r", \1,", text)
    return text


def _fix_abbreviations(text: str) -> str:
    for pattern, replacement in _ABBREVIATIONS:
        text = re.sub(pattern, replacement, text)
    return text


def _clean_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s*,\s*,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([.!?]){2,}", r"\1", text)
    return text.strip()


def assert_voiceover_safe(text: str, min_chars: int = 240) -> None:
    stripped = text.strip()
    if len(stripped) < min_chars:
        raise TextQualityError(f"text too short after cleanup: {len(stripped)} chars")
    tech_hits = len(_TECH_LINE_RE.findall(stripped))
    code_hits = len(_CODEISH_RE.findall(stripped))
    if tech_hits >= 2 or code_hits >= 2:
        raise TextQualityError(f"text looks like technical output (tech={tech_hits}, code={code_hits})")
    if not re.search(r"[.!?]$", stripped):
        raise TextQualityError("text does not end with a sentence terminator")


def assert_language_safe(text: str, lang: str) -> None:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if not letters:
        raise TextQualityError("text has no readable letters")
    cyrillic_ratio = len(re.findall(r"[А-Яа-яЁё]", text)) / len(letters)
    latin_ratio = len(re.findall(r"[A-Za-z]", text)) / len(letters)
    if lang == "en" and cyrillic_ratio > 0.05:
        raise TextQualityError(f"text is not English: cyrillic_ratio={cyrillic_ratio:.2f}")
    if lang == "ru" and latin_ratio > 0.35:
        raise TextQualityError(f"text is not Russian: latin_ratio={latin_ratio:.2f}")


def preprocess(text: str, lang: str = "en") -> str:
    text = _remove_technical_strings(text)
    text = remove_source_refs(text)
    if lang == "ru":
        text = _normalize_space_thousands(text)
        text = _fix_quotes(text)
        text = _fix_currency_and_units(text)
        text = _fix_punctuation(text)
        text = _fix_abbreviations(text)
    return _clean_whitespace(text)


def prepare_voiceover_text(text: str, lang: str = "en", min_chars: int = 240) -> str:
    clean = preprocess(text, lang=lang)
    assert_voiceover_safe(clean, min_chars=min_chars)
    assert_language_safe(clean, lang=lang)
    return clean
