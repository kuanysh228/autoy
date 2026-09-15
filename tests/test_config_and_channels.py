from pathlib import Path

import pytest

from autoy.channels import CHANNELS, UnknownChannel, get_channel
from autoy.config import Settings


def test_settings_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN='abc'\nSCHEDULE_TIMES=09:00, 21:00\nYOUTUBE_CHANNEL_IDS=geo=UC1,ai=UC2\nMAX_DURATION_SEC=30\n# comment\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTOY_HOME", str(tmp_path))
    for name in ("TELEGRAM_BOT_TOKEN", "SCHEDULE_TIMES", "YOUTUBE_CHANNEL_IDS", "MAX_DURATION_SEC"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()
    assert settings.paths.home == tmp_path.resolve()
    assert settings.telegram_bot_token == "abc"
    assert settings.schedule_times == ("09:00", "21:00")
    assert settings.youtube_channel_ids == {"geo": "UC1", "ai": "UC2"}
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
    geo = get_channel("GEO ")
    assert geo.key == "geo"
    assert geo.token_path(settings) == tmp_path.resolve() / "credentials" / "geo_token.pickle"
    assert geo.client_secret_path(settings).name == "client_secret_geo.json"
    assert get_channel(None).key == "geo"
    assert all(channel.topics for channel in CHANNELS.values())
    with pytest.raises(UnknownChannel):
        get_channel("nope")
