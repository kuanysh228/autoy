# autoy

Autonomous news-to-video pipeline. It picks a topic, researches a story, writes a 30-second script, voices it with a neural TTS, renders a vertical video with karaoke subtitles and stock footage, and uploads it to YouTube Shorts — several times a day, per channel, with a Telegram bot as the control panel. Once a week it assembles the stories into a 1080p digest with chapters and a thumbnail.

```
 topic ──► NewsScout (LLM research) ──► script cleanup ──► edge-tts ──► ffmpeg render ──► YouTube
                                              │                │              │
                                        quality gates    duration cap    Pexels footage
                                                                              │
                          Telegram bot ◄── review / approve / remake ◄────────┘
```

## Features

- **Multi-channel** — each channel is a declarative profile (`autoy/channels.py`): language, topics, accent colour, hashtags, weekly rundown, own OAuth credentials.
- **Script quality gates** — technical junk, URLs, source refs and LLM filler are stripped; scripts with weak newswire titles or banned phrases are regenerated; wrong-language output is rejected.
- **Retention-first format** — hook → 3–5 facts → question → loop line. Audio longer than `MAX_DURATION_SEC` is re-synthesised with middle sentences dropped, keeping the hook and the ending.
- **Renderer** — Ken Burns slideshow over Pexels photos (keyword → English query mapping), word-level karaoke subtitles from edge-tts boundaries, power-word highlighting, progress bar, background music mix. Frames are streamed straight into ffmpeg; nothing touches disk until the final MP4.
- **Weekly digest** — parallel story research, per-segment audio, intro/chapter/outro cards, chapter timestamps in the description, photo-backed thumbnail with a minimalist fallback.
- **Telegram control bot** — `/create`, review mode with Publish / Remake / Delete buttons and 5-minute auto-approve, per-slot schedule stored in SQLite, daily limit, quota estimate, subscriber/view milestone alerts.
- **Telegram channel auto-posting** — the same research pipeline formatted as a text post, with its own dedup table.
- **Dedup** — exact title hash, 12-hour fuzzy title overlap, 6-hour topic cooldown.
- **Pluggable TTS** — `edge` (default, with gTTS fallback), `piper` and `silero` behind one `Synthesizer` protocol.

## Requirements

- Python 3.11+
- `ffmpeg` / `ffprobe` on `PATH`
- A TrueType font (defaults to Liberation Sans; override with `FONT_BOLD` / `FONT_REGULAR`)
- [NewsScout](https://github.com/kuanysh228/NewsScout) for research (`pip install "autoy[newsscout]"`)
- Google Cloud project with **YouTube Data API v3** enabled and an OAuth 2.0 desktop client
- Optional: [Pexels](https://www.pexels.com/api/) key for stock footage, Telegram bot token

## Quick start

```bash
git clone https://github.com/kuanysh228/autoy.git && cd autoy
python -m venv .venv && source .venv/bin/activate
pip install -e ".[newsscout,dev]"

cp .env.example .env            # fill in tokens and keys
mkdir -p credentials            # put client_secret*.json here
autoy authorize geo             # one-time OAuth flow per channel
autoy shorts --no-upload        # render a video locally
autoy shorts "Iran nuclear deal news today" --channel geo_en
```

The working directory is the project home (`AUTOY_HOME` overrides it): `credentials/`, `data/`, `cache/` and `output/` live there and are git-ignored.

## CLI

| Command | What it does |
|---|---|
| `autoy shorts [topic] [--channel K] [--no-upload] [--publish-at RFC3339] [--tts edge\|piper\|silero] [--voice ID]` | Produce one Shorts video and upload it |
| `autoy weekly [--channel K] [--topics N] [--no-upload] [--publish-at …]` | Produce the weekly digest |
| `autoy authorize [channel]` | List token status or run the OAuth flow |
| `autoy scheduler [channels…] [--no-weekly] [--no-telegram]` | Headless scheduler (`SCHEDULE_TIMES`, `WEEKLY_TIME`, `TELEGRAM_CHANNEL_TIMES`) |
| `autoy bot` | Telegram control bot with its own DB-backed schedule |
| `autoy tg-post [--topic …] [--dry-run]` | Post one story to the Telegram channel |
| `autoy thumbnail "Title" [--query "pexels query"]` | Render thumbnail variants |
| `autoy analytics` | Per-channel stats for every uploaded video (needs `YOUTUBE_API_KEY`) |

### Bot commands

```
/create [channel] [topic]     produce a video now (review mode → inline buttons)
/schedule_add geo 10:00       add a daily slot        /schedule, /schedule_on|off|remove <id>
/review on|off                manual review vs auto-publish
/limit [n]                    daily upload limit      /quota   local quota estimate
/weekly, /weekly_set …        digest settings         /weekly_now
/stats [channel]              live subscribers/views  /status  /channels  /help
```

## Configuration

Everything is read from the environment, with `.env` in the project home as a fallback. See [`.env.example`](.env.example) for the full list.

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Bot token and the owner chat (commands are accepted only from it) |
| `TELEGRAM_CHANNEL_ID`, `TELEGRAM_NEWS_CHANNEL` | Public channel for text posts and which profile feeds it |
| `PEXELS_API_KEY` | Stock photos; without it backgrounds fall back to a gradient |
| `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_IDS` | Read-only key for analytics, `key=UC…` pairs for `/stats` and milestones |
| `SCHEDULE_TIMES`, `WEEKLY_TIME`, `WEEKLY_CHANNEL`, `TELEGRAM_CHANNEL_TIMES` | Scheduler slots |
| `MAX_POSTS_PER_DAY`, `MAX_DURATION_SEC`, `SCENE_DURATION_SEC`, `VIDEO_FPS` | Publishing and render limits |

Per-channel OAuth files are expected in `credentials/`: `client_secret.json` (or a channel-specific one, see `Channel.client_secret_file`) and the generated `<channel>_token.pickle`.

## Project layout

```
src/autoy/
├── cli/            argparse entry point (`autoy …`)
├── config.py       Settings / Paths from env + .env
├── channels.py     channel profiles
├── models.py       NewsItem, WeeklyStory, WordEvent, Voice
├── storage.py      SQLite: PostRegistry (dedup, history) and BotStore (schedule, settings, reviews)
├── dedup.py        topic cooldown and fuzzy title matching
├── text/           voiceover preprocessing and script shaping (pure functions, fully tested)
├── sources/        NewsScout adapter with prompt rules, Google News RSS fallback
├── tts/            Synthesizer protocol, edge / piper / silero backends, duration capping
├── media/          ffmpeg piping, drawing helpers, Pexels client, Ken Burns, Shorts & weekly renderers, thumbnails
├── publish/        YouTube client + metadata, Telegram notifier / channel publisher, channel stats
├── pipeline/       AppContext wiring, ShortsPipeline, WeeklyPipeline, scheduler jobs
├── bot/            Telegram bot: service, command router, schedule loop, application
├── scheduler.py    headless `schedule`-based runner
└── analytics.py    YouTube Data API reports
```

The pipeline objects (`ShortsPipeline.produce()` → `ShortsDraft` → `publish()`) are the only place business flow lives; the CLI, the headless scheduler and the bot are thin adapters over them.

## Deployment

Systemd units are in [`deploy/`](deploy/). They assume the project is installed in `/opt/autoy` with a virtualenv and a `.env`:

```bash
sudo cp deploy/autoy-bot.service deploy/autoy-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now autoy-bot autoy-scheduler
```

## Development

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format --check src tests
pytest
```

Tests cover the text pipeline, dedup, storage migrations, config parsing, metadata builders, Ken Burns timing, duration capping and the bot command router — everything that does not require network or ffmpeg.

## License

MIT
