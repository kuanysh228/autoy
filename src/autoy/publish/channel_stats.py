from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

SUBSCRIBER_MILESTONES = (200, 250, 300, 400, 500, 750, 1_000, 1_500, 2_000, 5_000, 10_000, 50_000, 100_000)
VIEW_MILESTONES = (100_000, 150_000, 200_000, 300_000, 500_000, 1_000_000, 2_000_000, 5_000_000)
MONETIZATION_SUBSCRIBERS = 1_000
MONETIZATION_WATCH_SECONDS = 4_000 * 3_600


@dataclass(frozen=True)
class ChannelStats:
    subscribers: int
    views: int
    videos: int

    def next_subscriber_milestone(self) -> int | None:
        return next((m for m in SUBSCRIBER_MILESTONES if m > self.subscribers), None)

    def next_view_milestone(self) -> int | None:
        return next((m for m in VIEW_MILESTONES if m > self.views), None)


def fetch_realtime_stats(channel_id: str, timeout: int = 15) -> ChannelStats | None:
    url = f'https://socialblade.com/api/trpc/creator.realtime?input={{"json":{{"platform":"youtube","id":"{channel_id}"}}}}'
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Referer": f"https://socialblade.com/youtube/channel/{channel_id}/realtime",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode().strip()
            if not line.startswith("data:"):
                continue
            data = json.loads(line[5:].strip()).get("json", {})
            if "stats" in data:
                stats = data["stats"]
                return ChannelStats(
                    subscribers=int(stats.get("subscribers") or 0),
                    views=int(stats.get("views") or 0),
                    videos=int(stats.get("videos") or 0),
                )
    return None
