from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Strings:
    shorts_hashtags: str
    shorts_tags: tuple[str, ...]
    weekly_title_tail: str
    weekly_title_fallback: str
    weekly_heading: str
    weekly_contents: str
    weekly_chapters: str
    weekly_intro_chapter: str
    weekly_cta: tuple[str, str, str]
    weekly_hashtags: str
    weekly_tags: tuple[str, ...]
    weekly_card: str
    weekly_thumbnail_title: str
    outro_title: str
    outro_lines: tuple[str, str]


EN = Strings(
    shorts_hashtags="#Shorts #News #WorldNews",
    shorts_tags=("shorts", "news", "world news"),
    weekly_title_tail=" — your world this week",
    weekly_title_fallback="The week in review | {channel}",
    weekly_heading="📰 The week's top stories {week}",
    weekly_contents="In this issue:",
    weekly_chapters="🕐 CHAPTERS",
    weekly_intro_chapter="Intro",
    weekly_cta=(
        "🔔 Subscribe so you never miss a weekly recap!",
        "👍 Like the video if it was useful",
        "💬 Tell us in the comments which story hit you the most",
    ),
    weekly_hashtags="#{channel} #WeeklyRecap #WeeklyNews #News #WorldNews #Weekly",
    weekly_tags=("weekly recap", "weekly news", "news of the week", "world news", "news roundup"),
    weekly_card="WEEKLY RECAP",
    weekly_thumbnail_title="Top stories of the week {week}",
    outro_title="Thanks for watching!",
    outro_lines=("Subscribe so you never miss", "a weekly recap"),
)

RU = Strings(
    shorts_hashtags="#Shorts #Новости #News",
    shorts_tags=("shorts", "новости", "news"),
    weekly_title_tail=" — твой мир за неделю",
    weekly_title_fallback="Главное за неделю | {channel}",
    weekly_heading="📰 Главные события недели {week}",
    weekly_contents="В этом выпуске:",
    weekly_chapters="🕐 ТАЙМКОДЫ",
    weekly_intro_chapter="Введение",
    weekly_cta=(
        "🔔 Подписывайтесь, чтобы не пропускать еженедельные итоги!",
        "👍 Ставьте лайк, если было полезно",
        "💬 Пишите в комментариях — какая тема вас задела больше всего?",
    ),
    weekly_hashtags="#{channel} #ИтогиНедели #НовостиНедели #МировыеНовости #Новости #Weekly",
    weekly_tags=("итоги недели", "новости недели", "еженедельный обзор", "главные новости", "мировые новости"),
    weekly_card="ИТОГИ НЕДЕЛИ",
    weekly_thumbnail_title="Главные события недели {week}",
    outro_title="Спасибо за просмотр!",
    outro_lines=("Подписывайтесь, чтобы не пропускать", "еженедельные итоги"),
)

_LOCALES: dict[str, Strings] = {"en": EN, "ru": RU}


def strings_for(lang: str) -> Strings:
    return _LOCALES.get(lang, EN)
