from pathlib import Path

import pytest

from autoy.models import Voice
from autoy.text import split_sentences
from autoy.tts import Speech, synthesize_within
from autoy.tts.base import timestamped_path


class FakeSynthesizer:
    name = "fake"

    def __init__(self, seconds_per_sentence: float) -> None:
        self.seconds_per_sentence = seconds_per_sentence
        self.calls: list[str] = []

    def synthesize(self, text: str, lang: str, output_path: Path, voice: Voice | None = None) -> Speech:
        self.calls.append(text)
        output_path.write_text(str(len(split_sentences(text)) * self.seconds_per_sentence))
        return Speech(output_path, [], voice or Voice("fake", "fake"))


@pytest.fixture
def fake_duration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("autoy.tts.media_duration", lambda path: float(Path(path).read_text()))


SCRIPT = "Hook. Fact one. Fact two. Fact three. Fact four. Question? Loop."


def test_synthesize_within_trims_until_it_fits(tmp_path: Path, fake_duration):
    synth = FakeSynthesizer(seconds_per_sentence=6.0)
    result = synthesize_within(synth, SCRIPT, "en", tmp_path, max_seconds=34)
    assert len(synth.calls) == 2
    assert split_sentences(result.text)[-2:] == ["Question?", "Loop."]
    assert split_sentences(result.text)[0] == "Hook."
    assert len(split_sentences(result.text)) == 5


def test_synthesize_within_returns_first_when_short(tmp_path: Path, fake_duration):
    synth = FakeSynthesizer(seconds_per_sentence=1.0)
    result = synthesize_within(synth, SCRIPT, "en", tmp_path, max_seconds=34)
    assert synth.calls == [SCRIPT]
    assert result.text == SCRIPT


def test_synthesize_within_gives_up(tmp_path: Path, fake_duration):
    synth = FakeSynthesizer(seconds_per_sentence=40.0)
    with pytest.raises(RuntimeError):
        synthesize_within(synth, "Hook. Question? Loop.", "en", tmp_path, max_seconds=34)


def test_timestamped_path(tmp_path: Path):
    path = timestamped_path(tmp_path, "audio_edge")
    assert path.parent == tmp_path
    assert path.name.startswith("audio_edge_") and path.suffix == ".mp3"
