# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - Unreleased

### Added

- Shorts pipeline: topic selection, NewsScout research, script quality gates, neural TTS, karaoke-subtitle renderer and YouTube upload.
- Weekly digest with chapters, per-segment narration and thumbnails.
- Telegram control bot with review mode, SQLite schedule, daily limit, quota estimate and milestone alerts.
- Telegram channel auto-posting.
- Pluggable TTS backends: edge (with gTTS fallback), piper, silero.
- Five built-in English channel profiles and user-defined profiles via `channels.toml`.
- English and Russian locales for prompts, voices, text normalisation and metadata.
- Dockerfile, docker-compose file and systemd units.

### Fixed

- Badge on the video header no longer overflows its background box.
