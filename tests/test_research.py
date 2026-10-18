import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoy.config import find_font
from autoy.models import NewsItem
from autoy.research import ArticleParseError, ResearchError, ResearchPipeline, ResearchSettings, parse_article
from autoy.research.prompts import build_article_question, build_research_query, editor_prompt, normalize_language
from autoy.sources import research as research_source
from autoy.sources.research import ResearchSource
from autoy.text import TextQualityError

SCRIPT = (
    "Chips just got a new rival. A startup unveiled a processor three times faster than the market leader. "
    "Early benchmarks show it uses half the power. Major cloud providers already signed pilot contracts. "
    "Analysts expect the leader to cut prices within weeks. Who wins this race? And this is only the first round."
)
ARTICLE_JSON = json.dumps({"title": "Chips shock the market", "text": SCRIPT, "direction": "#Chips"})


def test_parse_article_accepts_fenced_json():
    article = parse_article(f"```json\n{ARTICLE_JSON}\n```")
    assert (article.title, article.direction) == ("Chips shock the market", "#Chips")


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", '{"title": "a", "text": "b"}', '{"title": "a", "text": " ", "direction": "#x"}'])
def test_parse_article_rejects_bad_payloads(raw: str):
    with pytest.raises(ArticleParseError):
        parse_article(raw)


def test_prompts_are_language_aware():
    assert normalize_language(None) == "en"
    assert normalize_language(" RU ") == "ru"
    with pytest.raises(ValueError):
        normalize_language("de")
    query = build_research_query("chips", "ru", today=date(2026, 5, 13))
    assert "2026-05-06 to 2026-05-13" in query
    assert "in Russian" in query
    question = build_article_question("chips", "en", rules="\nEXTRA RULE")
    assert "in English" in question
    assert editor_prompt("en") in question
    assert question.endswith("EXTRA RULE")


class FakeNotebookLM:
    def __init__(
        self,
        answer: str = ARTICLE_JSON,
        found: tuple = ({"url": "a"}, {"url": "b"}, {"url": "c"}),
        statuses: tuple = ("running", "completed"),
    ):
        self.answer = answer
        self.found = list(found)
        self.statuses = list(statuses)
        self.deleted: list[str] = []
        self.imported: list = []
        self.asked: list[str] = []
        self.configured: list[dict] = []
        self.notebooks = SimpleNamespace(create=self._create, delete=self._delete)
        self.research = SimpleNamespace(start=self._start, poll=self._poll, import_sources=self._import)
        self.sources = SimpleNamespace(get_fulltext=self._fulltext)
        self.chat = SimpleNamespace(ask=self._ask, configure=self._configure)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def _create(self, title):
        return SimpleNamespace(id="nb1")

    async def _delete(self, notebook_id):
        self.deleted.append(notebook_id)

    async def _start(self, notebook_id, query, source, mode):
        return {"task_id": "t1"}

    async def _poll(self, notebook_id):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return {"status": status, "sources": self.found}

    async def _import(self, notebook_id, task_id, sources):
        self.imported = sources
        return [{"id": f"s{i}"} for i, _ in enumerate(sources)]

    async def _fulltext(self, notebook_id, source_id):
        return {"content": "text"}

    async def _ask(self, notebook_id, question):
        self.asked.append(question)
        return SimpleNamespace(answer=self.answer)

    async def _configure(self, notebook_id, **kwargs):
        self.configured.append(kwargs)


def make_pipeline(client: FakeNotebookLM, **settings) -> ResearchPipeline:
    async def factory(timeout: float):
        return client

    return ResearchPipeline(ResearchSettings(poll_interval=0, **settings), client_factory=factory)


async def test_pipeline_returns_article_and_cleans_up():
    client = FakeNotebookLM()
    article = await make_pipeline(client).run("chips", language="en", rules="\nSHORT")
    assert article.title == "Chips shock the market"
    assert len(client.imported) == 2  # capped by max_sources
    assert client.asked[0].endswith("SHORT")
    assert client.configured[0]["custom_prompt"] == editor_prompt("en")
    assert client.deleted == ["nb1"]


async def test_pipeline_deletes_notebook_on_failure():
    client = FakeNotebookLM(answer="not json")
    with pytest.raises(ArticleParseError):
        await make_pipeline(client).run("chips")
    assert client.deleted == ["nb1"]


async def test_pipeline_fails_without_sources():
    client = FakeNotebookLM(found=(), statuses=("completed",))
    with pytest.raises(ResearchError, match="no sources"):
        await make_pipeline(client).run("chips")


async def test_pipeline_times_out_when_research_never_completes():
    client = FakeNotebookLM(statuses=("running",))
    with pytest.raises(TimeoutError):
        await make_pipeline(client, research_timeout=0).run("chips")
    assert client.deleted == ["nb1"]


async def test_pipeline_rejects_unsupported_language_before_any_call():
    client = FakeNotebookLM()
    with pytest.raises(ValueError):
        await make_pipeline(client).run("chips", language="de")
    assert client.deleted == []


class StubPipeline:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[tuple] = []

    async def run(self, topic, language="en", rules=""):
        self.calls.append((topic, language, rules))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def article(title: str, text: str = SCRIPT):
    return SimpleNamespace(title=title, text=text, direction="#Chips")


async def test_source_returns_clean_news_item():
    pipeline = StubPipeline(article("Chips shock the market"))
    news = await ResearchSource(pipeline=pipeline).fetch_short("chips", "en", max_chars=900)
    assert isinstance(news, NewsItem)
    assert news.title == "Chips shock the market"
    topic, language, rules = pipeline.calls[0]
    assert (topic, language) == ("chips", "en")
    assert "YOUTUBE SHORTS" in rules.upper()


async def test_source_retries_on_filler_and_weak_title():
    filler = article("Chips shock the market", "Furthermore, " + SCRIPT)
    weak = article("Russia imposes new chip tariffs")
    pipeline = StubPipeline(filler, weak, article("Chips shock the market"))
    news = await ResearchSource(pipeline=pipeline).fetch_short("chips", "en")
    assert news.title == "Chips shock the market"
    assert len(pipeline.calls) == 3


async def test_source_falls_back_to_rss(monkeypatch: pytest.MonkeyPatch):
    items = [SimpleNamespace(title="Chips rally", source="Wire", source_url="https://w.example/1", link="https://l.example/1")] * 3
    monkeypatch.setattr(research_source.google_news, "search", lambda topic, lang: items)
    pipeline = StubPipeline(RuntimeError("login expired"), RuntimeError("login expired"))
    news = await ResearchSource(attempts=2, pipeline=pipeline).fetch_short("chips", "en")
    assert news.title == "Chips rally"
    assert news.sources


async def test_rss_fallback_respects_the_script_limit(monkeypatch: pytest.MonkeyPatch):
    items = [SimpleNamespace(title="Chips rally as a very long headline keeps going", source="Wire", source_url="", link="")] * 3
    monkeypatch.setattr(research_source.google_news, "search", lambda topic, lang: items)
    news = await ResearchSource(attempts=1, pipeline=StubPipeline(RuntimeError("down"))).fetch_short("chips", "en", max_chars=450)
    assert len(news.text) <= 450


async def test_source_raises_when_rss_is_empty_too(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(research_source.google_news, "search", lambda topic, lang: [])
    with pytest.raises(TextQualityError):
        await ResearchSource(attempts=1, pipeline=StubPipeline(RuntimeError("boom"))).fetch_short("chips", "en")


async def test_weekly_skips_failed_topics():
    from autoy.channels import WeeklyTopic

    good = article("Weekly chips story", SCRIPT * 2)
    pipeline = StubPipeline(good, RuntimeError("boom"))
    topics = [WeeklyTopic("Chips", "chips news", "chip"), WeeklyTopic("Phones", "phone news", "phone")]
    stories = await ResearchSource(attempts=1, pipeline=pipeline).fetch_weekly(topics, "en", max_items=2)
    assert [s.label for s in stories] == ["Chips"]
    assert all(call[1] == "en" for call in pipeline.calls)


def test_find_font_prefers_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fonts = tmp_path / "liberation"
    fonts.mkdir()
    (fonts / "LiberationSans-Bold.ttf").write_bytes(b"")
    monkeypatch.setattr("autoy.config._FONT_DIRS", (str(tmp_path / "missing"), str(fonts)))
    assert find_font(bold=True) == str(fonts / "LiberationSans-Bold.ttf")
    assert find_font(bold=False).endswith("LiberationSans-Regular.ttf")
