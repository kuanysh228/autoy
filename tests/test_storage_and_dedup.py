from pathlib import Path

import pytest

from autoy.dedup import find_similar, pick_fresh_topic
from autoy.models import NewsItem
from autoy.storage import BotStore, PendingReview, PostRegistry


@pytest.fixture
def registry(tmp_path: Path) -> PostRegistry:
    return PostRegistry(tmp_path / "pipeline.db")


@pytest.fixture
def store(tmp_path: Path) -> BotStore:
    return BotStore(tmp_path / "bot.db")


def test_registry_marks_and_counts(registry: PostRegistry):
    assert not registry.is_posted("Заголовок")
    registry.mark_posted("Заголовок", "vid1", channel="geo", voice_id="dmitry")
    registry.mark_posted("Дайджест", "vid2", channel="geo", kind="weekly")
    assert registry.is_posted("Заголовок")
    assert registry.shorts_posted_today() == 1
    assert registry.recent_titles("geo", hours=1) == ["заголовок", "дайджест"]
    assert [v.video_id for v in registry.all_videos()] == ["vid2", "vid1"]


def test_registry_telegram_dedup_is_case_insensitive(registry: PostRegistry):
    registry.mark_tg_posted("Big News", "geo")
    assert registry.is_tg_posted("  big news ")
    assert registry.recent_tg_titles(hours=1) == ["big news"]


def test_registry_migrates_legacy_schema(tmp_path: Path):
    import sqlite3

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE posted_news (id INTEGER PRIMARY KEY, title_hash TEXT UNIQUE, title TEXT, video_id TEXT, posted_at TEXT)")
    registry = PostRegistry(path)
    registry.mark_posted("x", "v", channel="geo")
    assert registry.shorts_posted_today() == 1


def test_bot_store_schedules_and_runs(store: BotStore):
    first = store.add_schedule("geo", "10:00")
    second = store.add_schedule("ai", "09:30")
    assert [e.run_time for e in store.list_schedules()] == ["09:30", "10:00"]
    assert store.set_schedule_enabled(second, False)
    assert store.list_schedules()[0].enabled is False
    assert store.claim_schedule_run(first)
    assert not store.claim_schedule_run(first)
    store.finish_schedule_run(first, "success", "ok")
    assert store.remove_schedule(first)
    assert not store.remove_schedule(999)
    store.clear_schedules()
    assert store.list_schedules() == []


def test_bot_store_settings_and_reviews(store: BotStore, tmp_path: Path):
    assert store.get_setting("review_enabled", "1") == "1"
    store.set_setting("review_enabled", "0")
    store.set_setting("review_enabled", "1")
    assert store.get_setting("review_enabled", "0") == "1"

    news = NewsItem(title="T", text="body", direction="#Tag")
    review = PendingReview("tok", tmp_path / "v.mp4", news, "geo", "dmitry", "topic")
    store.add_pending_review("tok", review)
    popped = store.pop_pending_review("tok")
    assert popped is not None
    assert popped.news == news
    assert popped.video_path == tmp_path / "v.mp4"
    assert store.pop_pending_review("tok") is None


def test_pick_fresh_topic_avoids_recent():
    topics = ["Bitcoin price news", "Ethereum crypto news"]
    assert pick_fresh_topic(topics, ["bitcoin hits new high"]) == "Ethereum crypto news"


def test_find_similar():
    recent = ["трамп ввёл санкции против ирана"]
    assert find_similar("Санкции против Ирана расширены", recent) == recent[0]
    assert find_similar("Биткоин обновил максимум", recent) is None
