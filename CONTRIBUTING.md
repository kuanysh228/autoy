# Contributing

Thanks for your interest in autoy. Bug reports, fixes and new ideas are welcome.

## Development setup

```bash
git clone https://github.com/kuanysh228/autoy.git && cd autoy
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

You need Python 3.11+. `ffmpeg` is only required to render videos, not to run the tests.

## Before you open a pull request

```bash
ruff check src tests examples
ruff format src tests examples
pytest
```

CI runs the same checks on Python 3.11, 3.12 and 3.13.

## Guidelines

- Keep changes focused; one concern per pull request.
- Add or update tests for behaviour changes. Pure functions in `text/`, `dedup.py` and the metadata builders are cheap to test, so prefer testing there.
- Business flow lives in `pipeline/`. The CLI, scheduler and bot stay thin adapters.
- Everything user-facing is English by default. Locale-specific text belongs in `strings.py`, prompts in `sources/prompts.py`.
- Update `README.md`, `.env.example` or `channels.example.toml` when you change user-facing behaviour, and add a line to `CHANGELOG.md`.

## Common extension points

- **New TTS backend:** implement the `Synthesizer` protocol in `src/autoy/tts/` and register it in `BACKENDS`.
- **New channel:** add a profile to `channels.toml` (see `channels.example.toml`); built-in profiles live in `channels.py`.
- **New language:** add a `Strings` entry in `strings.py`, a script prompt in `sources/prompts.py`, a voice pool in `tts/edge.py` and a Google News locale in `sources/google_news.py`.

## Code of conduct

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
