from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

import httpx

from autoy.storage import PostRegistry

_API = "https://www.googleapis.com/youtube/v3"
_BATCH = 50
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


@dataclass(frozen=True)
class VideoStats:
    id: str
    title: str
    channel_id: str
    channel_title: str
    views: int
    likes: int
    comments: int
    duration: int
    posted_at: str


@dataclass(frozen=True)
class ChannelInfo:
    title: str
    subscribers: int
    total_views: int
    video_count: int
    created: str


@dataclass(frozen=True)
class ChannelReport:
    key: str
    info: ChannelInfo | None
    videos: list[VideoStats]

    @property
    def count(self) -> int:
        return len(self.videos)

    @property
    def views(self) -> list[int]:
        return [v.views for v in self.videos]

    @property
    def avg_views(self) -> float:
        return sum(self.views) / self.count

    @property
    def median_views(self) -> int:
        return sorted(self.views)[self.count // 2]

    @property
    def like_rate(self) -> float:
        total_views = sum(self.views)
        return sum(v.likes for v in self.videos) / total_views * 100 if total_views else 0.0

    @property
    def trend(self) -> float:
        mid = self.count // 2
        newer, older = self.videos[:mid], self.videos[mid:]
        avg_new = sum(v.views for v in newer) / len(newer) if newer else 0
        avg_old = sum(v.views for v in older) / len(older) if older else 0
        return (avg_new - avg_old) / avg_old * 100 if avg_old else 0.0

    @property
    def posts_per_day(self) -> float:
        dates = [datetime.fromisoformat(v.posted_at) for v in self.videos]
        span = (dates[0] - dates[-1]).total_seconds() / 86400
        return self.count / span if span > 0 else 0.0

    def share(self, predicate) -> str:
        hits = sum(1 for v in self.views if predicate(v))
        return f"{hits} ({hits / self.count * 100:.0f}%)"


def parse_duration(value: str) -> int:
    match = _DURATION_RE.match(value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    return hours * 3600 + minutes * 60 + seconds


class YouTubeAnalytics:
    def __init__(self, api_key: str, timeout: int = 20) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, endpoint: str, **params) -> dict:
        response = httpx.get(f"{_API}/{endpoint}", params={**params, "key": self.api_key}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def videos(self, ids: list[str]) -> dict[str, dict]:
        found: dict[str, dict] = {}
        for start in range(0, len(ids), _BATCH):
            data = self._get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[start : start + _BATCH]))
            for item in data.get("items", []):
                found[item["id"]] = item
        return found

    def channel(self, channel_id: str) -> ChannelInfo | None:
        items = self._get("channels", part="snippet,statistics", id=channel_id).get("items", [])
        if not items:
            return None
        snippet, stats = items[0].get("snippet", {}), items[0].get("statistics", {})
        return ChannelInfo(
            title=snippet.get("title", ""),
            subscribers=int(stats.get("subscriberCount", 0)),
            total_views=int(stats.get("viewCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
            created=snippet.get("publishedAt", "")[:10],
        )

    def build_reports(self, registry: PostRegistry) -> list[ChannelReport]:
        posted = registry.all_videos()
        raw = self.videos([video.video_id for video in posted])
        by_channel: dict[str, list[VideoStats]] = defaultdict(list)
        for video in posted:
            item = raw.get(video.video_id)
            if not item:
                continue
            snippet, stats = item.get("snippet", {}), item.get("statistics", {})
            by_channel[video.channel].append(
                VideoStats(
                    id=video.video_id,
                    title=snippet.get("title", ""),
                    channel_id=snippet.get("channelId", ""),
                    channel_title=snippet.get("channelTitle", ""),
                    views=int(stats.get("viewCount", 0)),
                    likes=int(stats.get("likeCount", 0)),
                    comments=int(stats.get("commentCount", 0)),
                    duration=parse_duration(item.get("contentDetails", {}).get("duration", "")),
                    posted_at=video.posted_at,
                )
            )
        reports = []
        for key, videos in by_channel.items():
            info = self.channel(videos[0].channel_id) if videos[0].channel_id else None
            reports.append(ChannelReport(key, info, videos))
        return reports


def _duration_bucket(videos: list[VideoStats], label: str) -> str:
    if not videos:
        return f"  {label:<7} 0"
    return f"  {label:<7} {len(videos)} videos, avg views: {sum(v.views for v in videos) / len(videos):.0f}"


def render_report(report: ChannelReport) -> str:
    lines = ["=" * 65, f"CHANNEL: {(report.info.title if report.info else '') or report.key}  [{report.key}]", "=" * 65]
    if report.info:
        lines += [
            "",
            "--- CHANNEL ---",
            f"  Subscribers:  {report.info.subscribers:,}",
            f"  Total views:  {report.info.total_views:,}",
            f"  Videos:       {report.info.video_count}",
            f"  Created:      {report.info.created}",
        ]
    lines += [
        "",
        f"--- LAST {report.count} UPLOADS ---",
        f"  {'#':<3} {'Views':>7} {'Likes':>6} {'Comm':>5} {'Dur':>5}s  Date        Title",
    ]
    for index, video in enumerate(report.videos, 1):
        lines.append(
            f"  {index:<3} {video.views:>7,} {video.likes:>6,} {video.comments:>5,} {video.duration:>5}  {video.posted_at[:10]}  {video.title[:45]}"
        )

    mid = report.count // 2
    lines += [
        "",
        "--- ANALYTICS ---",
        f"  Avg views:      {report.avg_views:,.1f}",
        f"  Median views:   {report.median_views:,}",
        f"  Max / min:      {max(report.views):,} / {min(report.views):,}",
        f"  Avg duration:   {sum(v.duration for v in report.videos) / report.count:.0f}s",
        f"  Avg likes:      {sum(v.likes for v in report.videos) / report.count:.1f}",
        f"  Avg comments:   {sum(v.comments for v in report.videos) / report.count:.1f}",
        f"  Like rate:      {report.like_rate:.3f}%",
        "",
        f"  0 views:        {report.share(lambda v: v == 0)}",
        f"  < 100 views:    {report.share(lambda v: v < 100)}",
        f"  < 500 views:    {report.share(lambda v: v < 500)}",
        f"  ≥ 1 000 views:  {report.share(lambda v: v >= 1000)}",
        f"  ≥ 5 000 views:  {report.share(lambda v: v >= 5000)}",
        f"  ≥ 10 000 views: {report.share(lambda v: v >= 10000)}",
        "",
        "--- TREND ---",
        f"  Newer half (#1–{mid}) vs older half (#{mid + 1}–{report.count}): {report.trend:+.1f}%",
        f"  Frequency: {report.posts_per_day:.1f} videos/day ({report.posts_per_day * 7:.1f}/week)",
        "",
        "--- TOP 5 ---",
    ]
    lines += [
        f"  {v.views:>7,}  {v.posted_at[:10]}  {v.title[:50]}" for v in sorted(report.videos, key=lambda v: v.views, reverse=True)[:5]
    ]
    lines += ["", "--- BOTTOM 5 ---"]
    lines += [f"  {v.views:>7,}  {v.posted_at[:10]}  {v.title[:50]}" for v in sorted(report.videos, key=lambda v: v.views)[:5]]
    lines += [
        "",
        "--- DURATION ---",
        _duration_bucket([v for v in report.videos if v.duration < 45], "< 45s:"),
        _duration_bucket([v for v in report.videos if 45 <= v.duration <= 60], "45–60s:"),
        _duration_bucket([v for v in report.videos if v.duration > 60], "> 60s:"),
    ]
    return "\n".join(lines)


def render_summary(reports: list[ChannelReport]) -> str:
    lines = ["=" * 65, "SUMMARY", "=" * 65]
    for report in reports:
        subs = report.info.subscribers if report.info else "?"
        lines.append(
            f"  {report.key:<10} | subs: {subs:>6} | avg views: {report.avg_views:>7,.0f} | "
            f"median: {report.median_views:>5,} | trend: {report.trend:>+5.0f}% | like rate: {report.like_rate:.3f}%"
        )
    return "\n".join(lines)
