from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from autoy.models import NewsItem


def _hash_title(title: str) -> str:
    return hashlib.md5(title.encode()).hexdigest()


def _hash_title_normalized(title: str) -> str:
    return hashlib.md5(title.strip().lower().encode()).hexdigest()


class _SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _migrate(self) -> None:
        raise NotImplementedError

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        with suppress(sqlite3.OperationalError):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@dataclass(frozen=True)
class PostedVideo:
    channel: str
    video_id: str
    title: str
    posted_at: str


class PostRegistry(_SQLiteStore):
    def _migrate(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posted_news (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title_hash  TEXT NOT NULL UNIQUE,
                    title       TEXT,
                    video_id    TEXT,
                    voice_id    TEXT,
                    platform    TEXT DEFAULT 'youtube',
                    channel     TEXT,
                    kind        TEXT DEFAULT 'short',
                    posted_at   TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tg_posts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title_hash  TEXT NOT NULL UNIQUE,
                    title       TEXT,
                    channel     TEXT,
                    posted_at   TEXT NOT NULL
                )
                """
            )
            self._add_column(conn, "posted_news", "voice_id", "TEXT")
            self._add_column(conn, "posted_news", "channel", "TEXT")
            self._add_column(conn, "posted_news", "kind", "TEXT DEFAULT 'short'")

    def is_posted(self, title: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM posted_news WHERE title_hash=?", (_hash_title(title),)).fetchone()
        return row is not None

    def mark_posted(self, title: str, video_id: str, *, channel: str, voice_id: str = "", kind: str = "short") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO posted_news (title_hash, title, video_id, voice_id, channel, kind, posted_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (_hash_title(title), title, video_id, voice_id, channel, kind, datetime.now().isoformat()),
            )

    def shorts_posted_today(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM posted_news WHERE posted_at LIKE ? AND (kind IS NULL OR kind != 'weekly')",
                (f"{date.today().isoformat()}%",),
            ).fetchone()
        return int(row[0])

    def recent_titles(self, channel: str, hours: int) -> list[str]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT title FROM posted_news WHERE channel=? AND posted_at >= ?",
                (channel, cutoff),
            ).fetchall()
        return [row[0].lower() for row in rows if row[0]]

    def all_videos(self) -> list[PostedVideo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT channel, video_id, title, posted_at FROM posted_news WHERE video_id IS NOT NULL ORDER BY posted_at DESC"
            ).fetchall()
        return [PostedVideo(*row) for row in rows]

    def is_tg_posted(self, title: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM tg_posts WHERE title_hash=?", (_hash_title_normalized(title),)).fetchone()
        return row is not None

    def mark_tg_posted(self, title: str, channel: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO tg_posts (title_hash, title, channel, posted_at) VALUES (?,?,?,?)",
                (_hash_title_normalized(title), title, channel, datetime.now().isoformat()),
            )

    def recent_tg_titles(self, hours: int) -> list[str]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self._connect() as conn:
            rows = conn.execute("SELECT title FROM tg_posts WHERE posted_at >= ?", (cutoff,)).fetchall()
        return [row[0].lower() for row in rows if row[0]]


@dataclass(frozen=True)
class ScheduleEntry:
    id: int
    channel: str
    run_time: str
    enabled: bool


@dataclass(frozen=True)
class PendingReview:
    token: str
    video_path: Path
    news: NewsItem
    channel: str
    voice_id: str
    topic: str | None


class BotStore(_SQLiteStore):
    def _migrate(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel     TEXT NOT NULL,
                    run_time    TEXT NOT NULL,
                    enabled     INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule_runs (
                    schedule_id INTEGER NOT NULL,
                    run_date    TEXT NOT NULL,
                    started_at  TEXT NOT NULL,
                    status      TEXT NOT NULL,
                    message     TEXT,
                    PRIMARY KEY (schedule_id, run_date)
                )
                """
            )
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_reviews (
                    token       TEXT PRIMARY KEY,
                    video_path  TEXT NOT NULL,
                    news_json   TEXT NOT NULL,
                    channel     TEXT NOT NULL,
                    voice_id    TEXT,
                    topic       TEXT,
                    created_at  TEXT NOT NULL
                )
                """
            )
            self._add_column(conn, "pending_reviews", "voice_id", "TEXT")

    def get_setting(self, key: str, default: str) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def list_schedules(self) -> list[ScheduleEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, channel, run_time, enabled FROM schedules ORDER BY run_time, channel").fetchall()
        return [ScheduleEntry(row[0], row[1], row[2], bool(row[3])) for row in rows]

    def add_schedule(self, channel: str, run_time: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO schedules(channel, run_time, enabled, created_at) VALUES(?,?,1,?)",
                (channel, run_time, datetime.now().isoformat()),
            )
            return int(cursor.lastrowid or 0)

    def remove_schedule(self, schedule_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
            conn.execute("DELETE FROM schedule_runs WHERE schedule_id=?", (schedule_id,))
            return cursor.rowcount > 0

    def set_schedule_enabled(self, schedule_id: int, enabled: bool) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("UPDATE schedules SET enabled=? WHERE id=?", (int(enabled), schedule_id))
            return cursor.rowcount > 0

    def clear_schedules(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM schedules")
            conn.execute("DELETE FROM schedule_runs")

    def claim_schedule_run(self, schedule_id: int) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO schedule_runs(schedule_id, run_date, started_at, status, message) VALUES(?,?,?,?,?)",
                    (schedule_id, date.today().isoformat(), datetime.now().isoformat(), "running", ""),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def finish_schedule_run(self, schedule_id: int, status: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE schedule_runs SET status=?, message=? WHERE schedule_id=? AND run_date=?",
                (status, message[:1000], schedule_id, date.today().isoformat()),
            )

    def add_pending_review(self, token: str, review: PendingReview) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pending_reviews(token, video_path, news_json, channel, voice_id, topic, created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    token,
                    str(review.video_path),
                    json.dumps(review.news.to_dict(), ensure_ascii=False),
                    review.channel,
                    review.voice_id,
                    review.topic or "",
                    datetime.now().isoformat(),
                ),
            )

    def pop_pending_review(self, token: str) -> PendingReview | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT video_path, news_json, channel, voice_id, topic FROM pending_reviews WHERE token=?",
                (token,),
            ).fetchone()
            if not row:
                return None
            conn.execute("DELETE FROM pending_reviews WHERE token=?", (token,))
        return self._review_from_row(token, row)

    @staticmethod
    def _review_from_row(token: str, row: tuple[Any, ...]) -> PendingReview:
        return PendingReview(
            token=token,
            video_path=Path(row[0]),
            news=NewsItem.from_dict(json.loads(row[1])),
            channel=row[2],
            voice_id=row[3] or "",
            topic=row[4] or None,
        )
