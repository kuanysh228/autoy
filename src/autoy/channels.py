from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from autoy.config import Settings
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


CHANNELS: dict[str, Channel] = {
    "crypto": Channel(
        key="crypto",
        name="КРИПТО НОВОСТИ",
        lang="ru",
        accent=ORANGE,
        topics=(
            "Bitcoin price news today",
            "Ethereum crypto news",
            "крипто рынок новости",
            "BTC ETH курс сегодня",
            "DeFi blockchain news",
            "Binance Coinbase новости",
            "крипто регулирование",
        ),
        weekly_topics=_weekly(
            ("Биткоин", "Bitcoin BTC price market news this week", "bitcoin gold coin crypto"),
            ("Ethereum / DeFi", "Ethereum DeFi blockchain news this week", "ethereum blockchain digital finance"),
            ("Регулирование", "cryptocurrency regulation government ban news this week", "government law regulation finance"),
            ("Биржи", "Binance Coinbase Kraken crypto exchange news this week", "stock exchange trading screen finance"),
            ("Альткоины", "altcoin solana XRP dogecoin market news this week", "cryptocurrency digital coin technology"),
            ("Институционалы", "institutional bitcoin ETF investment hedge fund news week", "wall street finance investment bank"),
            ("Майнинг", "bitcoin mining hashrate energy news this week", "server data center technology mining"),
        ),
        hashtags=("криптовалюта", "биткоин", "крипто", "bitcoin", "crypto", "btc", "ethereum", "деньги"),
    ),
    "ai": Channel(
        key="ai",
        name="AI НОВОСТИ",
        lang="ru",
        accent=CYAN,
        topics=(
            "artificial intelligence news today",
            "OpenAI ChatGPT news",
            "Anthropic Claude новости",
            "Nvidia AI chips news",
            "Google DeepMind новости",
            "AI стартапы инвестиции",
            "нейросети новости сегодня",
        ),
        weekly_topics=_weekly(
            ("OpenAI", "OpenAI ChatGPT GPT model news this week", "artificial intelligence robot computer"),
            ("Google / DeepMind", "Google DeepMind Gemini AI news this week", "google technology search neural network"),
            ("Nvidia / железо", "Nvidia GPU chips AI hardware news this week", "gpu chip semiconductor technology"),
            ("Anthropic", "Anthropic Claude AI model news this week", "ai assistant robot technology future"),
            ("ИИ в бизнесе", "AI business enterprise automation investment news this week", "office automation technology business"),
            ("ИИ и закон", "AI regulation law ethics policy news this week", "law government policy technology"),
            ("Роботы", "robotics humanoid robot Boston Dynamics news this week", "robot humanoid technology future"),
        ),
        hashtags=("искусственныйинтеллект", "нейросети", "технологии", "ии", "chatgpt", "openai", "ai", "tech"),
    ),
    "geo": Channel(
        key="geo",
        name="ГЕОПОЛИТИКА",
        lang="ru",
        accent=RED,
        topics=(
            "Ukraine Russia war frontline news today",
            "Зеленский военные новости сегодня",
            "удары по Украине последние новости",
            "перемирие Украина Россия переговоры",
            "Трамп политика санкции новости сегодня",
            "Trump foreign policy decision today",
            "США Конгресс политика новости",
            "NATO military Europe defense news",
            "Европа оборона армия новости",
            "Израиль Газа конфликт новости сегодня",
            "Iran nuclear deal news today",
            "Ближний Восток геополитика новости",
            "Китай США торговая война новости",
            "China Taiwan military news today",
            "Северная Корея ракеты новости",
            "санкции против России последние новости",
            "Россия экономика война новости",
            "мировая политика кризис новости сегодня",
            "ООН дипломатия переговоры новости",
            "глобальная безопасность угрозы новости",
        ),
        weekly_topics=_weekly(
            ("Украина", "Ukraine Russia war frontline ceasefire news this week", "military soldiers ukraine conflict war"),
            ("Трамп", "Trump foreign policy sanctions deal news this week", "white house washington politics usa"),
            ("НАТО / Европа", "NATO Europe defense security news this week", "nato europe military alliance defense"),
            ("Ближний Восток", "Israel Gaza Iran Middle East conflict news this week", "middle east conflict military desert"),
            ("Китай / США", "China United States trade war tension Taiwan news this week", "china usa diplomacy trade economy"),
            ("Россия", "Russia sanctions economy military news this week", "russia kremlin politics military"),
            ("ООН / Дипломатия", "UN diplomacy peace negotiations summit news this week", "united nations diplomacy peace summit"),
        ),
        hashtags=("геополитика", "политика", "мировыеновости", "война", "украина", "россия", "новости", "сша"),
        client_secret_file="client_secret_geo.json",
    ),
    "geo_en": Channel(
        key="geo_en",
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
        client_secret_file="client_secret_geo_en.json",
    ),
    "business": Channel(
        key="business",
        name="БИЗНЕС",
        lang="ru",
        accent=GREEN,
        topics=(
            "startup funding news today",
            "venture capital инвестиции",
            "IPO новости бизнес",
            "бизнес новости сегодня",
            "миллиардеры Forbes новости",
            "экономика России новости",
            "рубль доллар курс",
        ),
        weekly_topics=_weekly(
            ("Стартапы", "startup funding venture capital investment news this week", "startup office technology investment"),
            ("IPO / M&A", "IPO merger acquisition deal market news this week", "stock exchange wall street finance"),
            ("Миллиардеры", "billionaire Forbes Musk Bezos wealth news this week", "luxury yacht private jet wealth"),
            ("Экономика РФ", "Russia economy ruble sanctions GDP news this week", "russia economy finance business city"),
            ("Мировая экономика", "global economy inflation recession GDP news this week", "economy finance global market trading"),
            ("Технологии бизнеса", "AI automation digital transformation business news week", "technology business innovation office"),
            ("Рынки", "stock market S&P500 Nasdaq Dow Jones news this week", "stock market trading finance chart"),
        ),
        hashtags=("бизнес", "стартапы", "инвестиции", "экономика", "деньги", "форбс", "миллиардер", "финансы"),
    ),
    "lifestyle": Channel(
        key="lifestyle",
        name="МИЛЛИАРДЕРЫ",
        lang="ru",
        accent=GOLD,
        topics=(
            "Elon Musk news today",
            "Jeff Bezos lifestyle news",
            "миллиардеры новости Forbes",
            "luxury lifestyle rich news",
            "Маск новости сегодня",
            "яхты самолёты миллиардеры",
            "богатейшие люди мира новости",
        ),
        weekly_topics=_weekly(
            ("Илон Маск", "Elon Musk Tesla SpaceX DOGE news this week", "elon musk tesla spacex rocket"),
            ("Безос / Amazon", "Jeff Bezos Amazon Blue Origin news this week", "amazon warehouse logistics technology"),
            ("Forbes 500", "Forbes billionaire wealth ranking news this week", "luxury wealth rich lifestyle yacht"),
            ("Яхты / джеты", "billionaire superyacht private jet luxury news this week", "luxury yacht private jet ocean"),
            ("Инвестиции", "billionaire investment portfolio stock buy sell news week", "investment finance portfolio wealth"),
            ("Стиль жизни", "billionaire mansion party art collection news this week", "luxury mansion interior design art"),
            ("Новые богачи", "new billionaire startup unicorn wealth news this week", "startup success entrepreneur wealth"),
        ),
        hashtags=("миллиардеры", "богатство", "маск", "роскошь", "успех", "лайфстайл", "luxury", "forbes"),
    ),
}

DEFAULT_CHANNEL = "geo"


class UnknownChannel(KeyError):
    pass


def get_channel(key: str | None = None) -> Channel:
    normalized = (key or DEFAULT_CHANNEL).lower().strip()
    try:
        return CHANNELS[normalized]
    except KeyError as exc:
        raise UnknownChannel(f"Unknown channel '{normalized}'. Available: {', '.join(CHANNELS)}") from exc
