from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from autoy import __version__
from autoy.channels import CHANNELS, DEFAULT_CHANNEL, get_channel
from autoy.config import get_settings
from autoy.tts import BACKENDS

_LOG_FORMAT = "[%(asctime)s] %(levelname)s | %(message)s"
_QUIET_LOGGERS = ("notebooklm", "httpx", "httpcore")


def setup_logging(log_file: str | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(get_settings().paths.logs / log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S", handlers=handlers)
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _add_channel_arg(parser: argparse.ArgumentParser, default: str | None = None) -> None:
    parser.add_argument("--channel", default=default, help=f"channel key: {', '.join(CHANNELS)}")


def cmd_shorts(args: argparse.Namespace) -> int:
    from autoy.dedup import DuplicateNews
    from autoy.pipeline import AppContext, ShortsPipeline
    from autoy.tts import resolve_voice

    setup_logging()
    channel = get_channel(args.channel)
    ctx = AppContext.build(tts_backend=args.tts)
    pipeline = ShortsPipeline(ctx, channel)
    voice = resolve_voice(args.tts, channel.lang, args.voice)
    log = logging.getLogger("autoy")
    try:
        draft = pipeline.produce(args.topic, voice=voice)
    except DuplicateNews as exc:
        log.warning("%s — run again, the topic will differ", exc)
        return 1
    if args.no_upload:
        log.info("Upload skipped (--no-upload). Video: %s", draft.video_path)
        return 0
    video_id = pipeline.publish(draft, publish_at=args.publish_at)
    log.info("Done: https://youtube.com/shorts/%s", video_id)
    return 0


def cmd_weekly(args: argparse.Namespace) -> int:
    from autoy.pipeline import AppContext, WeeklyPipeline

    setup_logging("weekly.log")
    ctx = AppContext.build()
    pipeline = WeeklyPipeline(ctx, get_channel(args.channel))
    log = logging.getLogger("autoy")
    draft = pipeline.produce(args.topics)
    if draft is None:
        return 1
    if args.no_upload:
        log.info("Upload skipped (--no-upload). Video: %s | Thumbnail: %s", draft.video.path, draft.thumbnail_path)
        return 0
    video_id = pipeline.publish(draft, publish_at=args.publish_at)
    log.info("Done: https://youtube.com/watch?v=%s", video_id)
    return 0


def cmd_authorize(args: argparse.Namespace) -> int:
    from autoy.publish import YouTubeClient

    settings = get_settings()
    if not args.channel:
        print("\nAvailable channels:\n")
        for key, channel in CHANNELS.items():
            print(f"  autoy authorize {key:12s}  —  {channel.name} ({YouTubeClient(settings, channel).token_status()})")
        print()
        return 0
    channel = get_channel(args.channel)
    client = YouTubeClient(settings, channel)
    if not client.client_secret_path.exists():
        print(f"\nClient secret not found: {client.client_secret_path}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client")
        return 1
    print(f"\nChannel: {channel.name}\nToken:   {client.token_path}\n")
    print("A browser window will open. Sign in with the Google account that owns THIS channel.\n")
    token = client.authorize_interactively(port=args.port)
    print(f"\nToken saved: {token}\n")
    return 0


def cmd_thumbnail(args: argparse.Namespace) -> int:
    from autoy.media import PexelsClient, ThumbnailMaker
    from autoy.pipeline.weekly import WeekLabel

    setup_logging()
    settings = get_settings()
    channel = get_channel(args.channel)
    maker = ThumbnailMaker(settings, PexelsClient(settings.pexels_api_key, settings.paths.cache / "pexels"))
    week = args.week or WeekLabel.current().compact
    labels = args.labels or [topic.label for topic in channel.weekly_topics[:3]]
    paths = [maker.minimalist(args.title, channel.name, week, labels, channel.accent)]
    if args.query:
        paths.append(maker.story(channel.name, week, labels, channel.accent, args.query))
    print("\nSaved:")
    for path in paths:
        print(f"  {path}")
    return 0


def cmd_tg_post(args: argparse.Namespace) -> int:
    from autoy.pipeline import AppContext
    from autoy.publish import ChannelPublisher

    setup_logging()
    ctx = AppContext.build()
    channel = get_channel(args.channel or ctx.settings.telegram_news_channel)
    publisher = ChannelPublisher(ctx.settings, ctx.registry, ctx.source)
    asyncio.run(publisher.post(channel, topic=args.topic, dry_run=args.dry_run))
    return 0


def cmd_scheduler(args: argparse.Namespace) -> int:
    from autoy.pipeline import AppContext
    from autoy.scheduler import build_schedule, run_forever

    setup_logging("pipeline.log")
    ctx = AppContext.build()
    keys = [get_channel(key).key for key in (args.channels or list(CHANNELS))]
    run_forever(build_schedule(ctx, keys, weekly=not args.no_weekly, telegram_channel=not args.no_telegram))
    return 0


def cmd_bot(args: argparse.Namespace) -> int:
    from autoy.bot import run_bot
    from autoy.pipeline import AppContext

    setup_logging("telegram_bot.log")
    run_bot(AppContext.build())
    return 0


def cmd_analytics(args: argparse.Namespace) -> int:
    from autoy.analytics import YouTubeAnalytics, render_report, render_summary
    from autoy.storage import PostRegistry

    settings = get_settings()
    if not settings.youtube_api_key:
        print("YOUTUBE_API_KEY is not set")
        return 1
    reports = YouTubeAnalytics(settings.youtube_api_key).build_reports(PostRegistry(settings.paths.pipeline_db))
    if not reports:
        print("No published videos in the database yet")
        return 0
    for report in reports:
        print(render_report(report))
        print()
    print(render_summary(reports))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoy", description="News → YouTube Shorts / weekly digest automation")
    parser.add_argument("--version", action="version", version=f"autoy {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    shorts = sub.add_parser("shorts", help="produce (and upload) one Shorts video")
    shorts.add_argument("topic", nargs="?", default=None)
    _add_channel_arg(shorts)
    shorts.add_argument("--no-upload", action="store_true")
    shorts.add_argument("--publish-at", default=None, help="RFC3339 UTC, e.g. 2026-05-13T16:00:00Z")
    shorts.add_argument("--voice", default=None, help="voice id (edge: dmitry/aria; silero: ruslan/aidar/...; piper: ruslan)")
    shorts.add_argument("--tts", default="edge", choices=BACKENDS)
    shorts.set_defaults(func=cmd_shorts)

    weekly = sub.add_parser("weekly", help="produce (and upload) the weekly digest")
    _add_channel_arg(weekly, default=DEFAULT_CHANNEL)
    weekly.add_argument("--no-upload", action="store_true")
    weekly.add_argument("--topics", type=int, default=8)
    weekly.add_argument("--publish-at", default=None)
    weekly.set_defaults(func=cmd_weekly)

    authorize = sub.add_parser("authorize", help="run the YouTube OAuth flow for a channel")
    authorize.add_argument("channel", nargs="?", default=None)
    authorize.add_argument("--port", type=int, default=8080)
    authorize.set_defaults(func=cmd_authorize)

    thumbnail = sub.add_parser("thumbnail", help="render weekly thumbnail variants")
    thumbnail.add_argument("title")
    _add_channel_arg(thumbnail, default=DEFAULT_CHANNEL)
    thumbnail.add_argument("--week", default=None)
    thumbnail.add_argument("--labels", nargs="*", default=None)
    thumbnail.add_argument("--query", default=None, help="Pexels query for the photo-backed variant")
    thumbnail.set_defaults(func=cmd_thumbnail)

    tg_post = sub.add_parser("tg-post", help="post one news item to the Telegram channel")
    _add_channel_arg(tg_post)
    tg_post.add_argument("--topic", default=None)
    tg_post.add_argument("--dry-run", action="store_true")
    tg_post.set_defaults(func=cmd_tg_post)

    scheduler = sub.add_parser("scheduler", help="run the standalone scheduler")
    scheduler.add_argument("channels", nargs="*")
    scheduler.add_argument("--no-weekly", action="store_true")
    scheduler.add_argument("--no-telegram", action="store_true")
    scheduler.set_defaults(func=cmd_scheduler)

    bot = sub.add_parser("bot", help="run the Telegram control bot")
    bot.set_defaults(func=cmd_bot)

    analytics = sub.add_parser("analytics", help="print YouTube statistics for published videos")
    analytics.set_defaults(func=cmd_analytics)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
