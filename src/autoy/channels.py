from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoy.config import Settings, resolve_home
from autoy.models import RGB

RED: RGB = (210, 25, 25)
ORANGE: RGB = (255, 140, 0)
CYAN: RGB = (0, 180, 255)
GREEN: RGB = (0, 200, 100)
GOLD: RGB = (210, 165, 0)
BLUE: RGB = (30, 105, 210)


@dataclass(frozen=True)
class WeeklyTopic:
    label: str
    query: str
    pexels_query: str


@dataclass(frozen=True)
class Channel:
    key: str
    name: str
    lang: str
    accent: RGB
    topics: tuple[str, ...]
    weekly_topics: tuple[WeeklyTopic, ...] = ()
    max_script_chars: int = 420
    badge: str = "BREAKING NEWS"
    show_banner: bool = True
    music: bool = True
    music_subdir: str | None = None
    pexels_queries: tuple[str, ...] = ()
    hashtags: tuple[str, ...] = ()
    client_secret_file: str = "client_secret.json"
    token_file: str = field(default="")
    oauth_client_id: str = ""

    @property
    def is_english(self) -> bool:
        return self.lang == "en"

    def client_secret_path(self, settings: Settings) -> Path:
        return settings.paths.credentials / self.client_secret_file

    def token_path(self, settings: Settings) -> Path:
        return settings.paths.credentials / (self.token_file or f"{self.key}_token.pickle")


def _weekly(*rows: tuple[str, str, str]) -> tuple[WeeklyTopic, ...]:
    return tuple(WeeklyTopic(*row) for row in rows)


BUILTIN_CHANNELS: dict[str, Channel] = {
    "world": Channel(
        key="world",
        name="WORLD NEWS",
        lang="en",
        accent=BLUE,
        max_script_chars=450,
        topics=(
            "Ukraine Russia war news today",
            "Trump foreign policy news today",
            "NATO geopolitics news",
            "Middle East conflict news today",
            "China US tensions news",
            "global politics breaking news",
            "world security news today",
        ),
        weekly_topics=_weekly(
            ("Ukraine", "Ukraine Russia war ceasefire frontline news this week", "military soldiers ukraine conflict war"),
            ("Trump", "Trump foreign policy tariffs deals news this week", "white house washington politics usa"),
            ("NATO / Europe", "NATO Europe defense security news this week", "nato europe military alliance defense"),
            ("Middle East", "Israel Gaza Iran Middle East conflict news this week", "middle east conflict military desert"),
            ("China / USA", "China United States trade war Taiwan tension news this week", "china usa diplomacy trade economy"),
            ("Russia", "Russia sanctions military economy news this week", "russia kremlin politics military"),
            ("UN / Diplomacy", "UN diplomacy peace negotiations summit ceasefire news week", "united nations diplomacy peace summit"),
        ),
        hashtags=("worldnews", "breakingnews", "geopolitics", "politics", "ukraine", "russia", "usa", "nato"),
    ),
    "crypto": Channel(
        key="crypto",
        name="CRYPTO NEWS",
        lang="en",
        accent=ORANGE,
        topics=(
            "Bitcoin price news today",
            "Ethereum crypto news",
            "crypto market news today",
            "BTC ETH price analysis",
            "DeFi blockchain news",
            "Binance Coinbase news",
            "crypto regulation news",
        ),
        weekly_topics=_weekly(
            ("Bitcoin", "Bitcoin BTC price market news this week", "bitcoin gold coin crypto"),
            ("Ethereum / DeFi", "Ethereum DeFi blockchain news this week", "ethereum blockchain digital finance"),
            ("Regulation", "cryptocurrency regulation government ban news this week", "government law regulation finance"),
            ("Exchanges", "Binance Coinbase Kraken crypto exchange news this week", "stock exchange trading screen finance"),
            ("Altcoins", "altcoin solana XRP dogecoin market news this week", "cryptocurrency digital coin technology"),
            ("Institutions", "institutional bitcoin ETF investment hedge fund news week", "wall street finance investment bank"),
            ("Mining", "bitcoin mining hashrate energy news this week", "server data center technology mining"),
        ),
        hashtags=("crypto", "bitcoin", "btc", "ethereum", "cryptocurrency", "blockchain", "defi", "money"),
    ),
    "ai": Channel(
        key="ai",
        name="AI NEWS",
        lang="en",
        accent=CYAN,
        topics=(
            "artificial intelligence news today",
            "OpenAI ChatGPT news",
            "Nvidia AI chips news",
            "Google DeepMind Gemini news",
            "AI startups funding news",
            "open source AI models news",
            "AI regulation news today",
        ),
        weekly_topics=_weekly(
            ("OpenAI", "OpenAI ChatGPT GPT model news this week", "artificial intelligence robot computer"),
            ("Google / DeepMind", "Google DeepMind Gemini AI news this week", "google technology search neural network"),
            ("Nvidia / Hardware", "Nvidia GPU chips AI hardware news this week", "gpu chip semiconductor technology"),
            ("Open Source", "open source AI model release Llama Mistral DeepSeek news this week", "programmer code laptop technology"),
            ("AI in Business", "AI business enterprise automation investment news this week", "office automation technology business"),
            ("AI & Law", "AI regulation law ethics policy news this week", "law government policy technology"),
            ("Robots", "robotics humanoid robot Boston Dynamics news this week", "robot humanoid technology future"),
        ),
        hashtags=("artificialintelligence", "ai", "chatgpt", "openai", "machinelearning", "technology", "tech", "nvidia"),
    ),
    "business": Channel(
        key="business",
        name="BUSINESS",
        lang="en",
        accent=GREEN,
        topics=(
            "startup funding news today",
            "venture capital investment news",
            "IPO market news today",
            "business news today",
            "stock market news today",
            "global economy inflation news",
            "Fed interest rates news",
        ),
        weekly_topics=_weekly(
            ("Startups", "startup funding venture capital investment news this week", "startup office technology investment"),
            ("IPO / M&A", "IPO merger acquisition deal market news this week", "stock exchange wall street finance"),
            ("Billionaires", "billionaire Forbes Musk Bezos wealth news this week", "luxury yacht private jet wealth"),
            ("Global Economy", "global economy inflation recession GDP news this week", "economy finance global market trading"),
            ("Central Banks", "Federal Reserve ECB interest rates inflation news this week", "bank building finance economy"),
            ("Business Tech", "AI automation digital transformation business news week", "technology business innovation office"),
            ("Markets", "stock market S&P500 Nasdaq Dow Jones news this week", "stock market trading finance chart"),
        ),
        hashtags=("business", "startups", "investing", "economy", "money", "finance", "markets", "stocks"),
    ),
    "billionaires": Channel(
        key="billionaires",
        name="BILLIONAIRES",
        lang="en",
        accent=GOLD,
        topics=(
            "Elon Musk news today",
            "Jeff Bezos lifestyle news",
            "billionaires news Forbes",
            "luxury lifestyle rich news",
            "superyachts private jets billionaires",
            "richest people in the world news",
        ),
        weekly_topics=_weekly(
            ("Elon Musk", "Elon Musk Tesla SpaceX DOGE news this week", "elon musk tesla spacex rocket"),
            ("Bezos / Amazon", "Jeff Bezos Amazon Blue Origin news this week", "amazon warehouse logistics technology"),
            ("Forbes 500", "Forbes billionaire wealth ranking news this week", "luxury wealth rich lifestyle yacht"),
            ("Yachts / Jets", "billionaire superyacht private jet luxury news this week", "luxury yacht private jet ocean"),
            ("Investments", "billionaire investment portfolio stock buy sell news week", "investment finance portfolio wealth"),
            ("Lifestyle", "billionaire mansion party art collection news this week", "luxury mansion interior design art"),
            ("New Money", "new billionaire startup unicorn wealth news this week", "startup success entrepreneur wealth"),
        ),
        hashtags=("billionaires", "wealth", "elonmusk", "luxury", "success", "lifestyle", "forbes", "rich"),
    ),
}

CHANNELS_FILE = "channels.toml"
BUILTIN_DEFAULT = "world"


class UnknownChannel(KeyError):
    pass


class InvalidChannelConfig(ValueError):
    pass


def _color(key: str, value: Any) -> RGB:
    if isinstance(value, str) and len(value.lstrip("#")) == 6:
        try:
            raw = value.lstrip("#")
            return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        except ValueError:
            pass
    if isinstance(value, list) and len(value) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in value):
        return value[0], value[1], value[2]
    raise InvalidChannelConfig(f"channel '{key}': accent must be '#rrggbb' or [r, g, b], got {value!r}")


def _channel_from_table(key: str, table: dict[str, Any]) -> Channel:
    missing = [field_name for field_name in ("name", "topics") if not table.get(field_name)]
    if missing:
        raise InvalidChannelConfig(f"channel '{key}': missing {', '.join(missing)}")

    weekly = tuple(WeeklyTopic(row["label"], row["query"], row.get("pexels_query", row["query"])) for row in table.get("weekly_topics", ()))
    optional = {
        name: table[name]
        for name in (
            "max_script_chars",
            "badge",
            "show_banner",
            "music",
            "music_subdir",
            "client_secret_file",
            "token_file",
            "oauth_client_id",
        )
        if name in table
    }
    return Channel(
        key=key,
        name=table["name"],
        lang=table.get("lang", "en"),
        accent=_color(key, table.get("accent", "#1e69d2")),
        topics=tuple(table["topics"]),
        weekly_topics=weekly,
        pexels_queries=tuple(table.get("pexels_queries", ())),
        hashtags=tuple(table.get("hashtags", ())),
        **optional,
    )


def load_channels(path: Path) -> tuple[dict[str, Channel], str | None]:
    """Read user-defined channel profiles from a TOML file; returns (channels, default key)."""
    if not path.is_file():
        return {}, None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise InvalidChannelConfig(f"{path.name}: {exc}") from exc
    channels = {key.lower(): _channel_from_table(key.lower(), table) for key, table in data.get("channels", {}).items()}
    return channels, data.get("default")


def _build_registry() -> tuple[dict[str, Channel], str]:
    custom, default = load_channels(resolve_home() / CHANNELS_FILE)
    registry = {**BUILTIN_CHANNELS, **custom}
    default = (default or BUILTIN_DEFAULT).lower()
    if default not in registry:
        raise InvalidChannelConfig(f"default channel '{default}' is not defined")
    return registry, default


CHANNELS, DEFAULT_CHANNEL = _build_registry()


def get_channel(key: str | None = None) -> Channel:
    normalized = (key or DEFAULT_CHANNEL).lower().strip()
    try:
        return CHANNELS[normalized]
    except KeyError as exc:
        raise UnknownChannel(f"Unknown channel '{normalized}'. Available: {', '.join(CHANNELS)}") from exc
