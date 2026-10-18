from pathlib import Path

import pytest

from autoy.channels import CHANNELS, InvalidChannelConfig, UnknownChannel, get_channel, load_channels
from autoy.config import Settings


def test_settings_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN='abc'\nSCHEDULE_TIMES=09:00, 21:00\nYOUTUBE_CHANNEL_IDS=world=UC1,ai=UC2\nMAX_DURATION_SEC=30\n# comment\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTOY_HOME", str(tmp_path))
    for name in ("TELEGRAM_BOT_TOKEN", "SCHEDULE_TIMES", "YOUTUBE_CHANNEL_IDS", "MAX_DURATION_SEC"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()
    assert settings.paths.home == tmp_path.resolve()
    assert settings.telegram_bot_token == "abc"
    assert settings.schedule_times == ("09:00", "21:00")
    assert settings.youtube_channel_ids == {"world": "UC1", "ai": "UC2"}
    assert settings.video.max_duration_sec == 30.0
    assert settings.paths.pipeline_db == tmp_path.resolve() / "data" / "pipeline.db"


def test_real_env_overrides_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / ".env").write_text("PEXELS_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("AUTOY_HOME", str(tmp_path))
    monkeypatch.setenv("PEXELS_API_KEY", "from-env")
    assert Settings.from_env().pexels_api_key == "from-env"


def test_channels_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTOY_HOME", str(tmp_path))
    settings = Settings.from_env()
    world = get_channel("WORLD ")
    assert world.key == "world"
    assert world.token_path(settings) == tmp_path.resolve() / "credentials" / "world_token.pickle"
    assert world.client_secret_path(settings).name == "client_secret.json"
    assert get_channel(None).key == "world"
    assert all(channel.topics and channel.weekly_topics for channel in CHANNELS.values())
    assert all(channel.is_english for channel in CHANNELS.values())
    with pytest.raises(UnknownChannel):
        get_channel("nope")


def test_load_channels_from_toml(tmp_path: Path):
    path = tmp_path / "channels.toml"
    path.write_text(
        """
default = "tech"

[channels.tech]
name = "TECH DAILY"
lang = "ru"
accent = "#ff8800"
topics = ["gadgets news today"]
hashtags = ["tech"]
client_secret_file = "client_secret_tech.json"

[[channels.tech.weekly_topics]]
label = "Phones"
query = "smartphone news this week"
pexels_query = "smartphone"
""",
        encoding="utf-8",
    )
    channels, default = load_channels(path)
    tech = channels["tech"]
    assert default == "tech"
    assert (tech.name, tech.lang, tech.accent) == ("TECH DAILY", "ru", (255, 136, 0))
    assert tech.weekly_topics[0].pexels_query == "smartphone"
    assert tech.client_secret_file == "client_secret_tech.json"


def test_load_channels_missing_file_is_empty(tmp_path: Path):
    assert load_channels(tmp_path / "channels.toml") == ({}, None)


@pytest.mark.parametrize(
    "body",
    [
        '[channels.x]\ntopics = ["a"]\n',
        '[channels.x]\nname = "X"\n',
        '[channels.x]\nname = "X"\ntopics = ["a"]\naccent = "red"\n',
        "[channels.x\n",
    ],
)
def test_load_channels_rejects_invalid(tmp_path: Path, body: str):
    path = tmp_path / "channels.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(InvalidChannelConfig):
        load_channels(path)


def test_example_channels_file_is_valid():
    channels, default = load_channels(Path(__file__).parent.parent / "channels.example.toml")
    assert default in channels
    assert channels["tech"].weekly_topics
