from __future__ import annotations

import html
import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

_LOCALES = {"en": ("en-US", "US", "US:en"), "ru": ("ru", "RU", "RU:ru")}


@dataclass(frozen=True)
class RssItem:
    title: str
    description: str
    source: str
    source_url: str
    link: str
    published: str


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _clean_title(title: str) -> str:
    return re.sub(r"\s+-\s+[^-]{2,80}$", "", _strip_html(title)).strip()


def search(topic: str, lang: str, limit: int = 5, timeout: int = 20) -> list[RssItem]:
    hl, gl, ceid = _LOCALES.get(lang, _LOCALES["ru"])
    url = f"https://news.google.com/rss/search?q={quote_plus(f'{topic} when:7d')}&hl={hl}&gl={gl}&ceid={ceid}"
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as response:
        root = ElementTree.fromstring(response.read())

    items: list[RssItem] = []
    for node in root.findall("./channel/item")[:limit]:
        title = _clean_title(node.findtext("title") or "")
        if not title:
            continue
        source = node.find("source")
        try:
            published = parsedate_to_datetime(node.findtext("pubDate") or "").isoformat()
        except (TypeError, ValueError):
            published = ""
        items.append(
            RssItem(
                title=title,
                description=_strip_html(node.findtext("description") or ""),
                source=(source.text or "").strip() if source is not None else "",
                source_url=(source.attrib.get("url") or "").strip() if source is not None else "",
                link=(node.findtext("link") or "").strip(),
                published=published,
            )
        )
    return items
