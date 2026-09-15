from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from autoy.config import Settings
from autoy.media.ffmpeg import media_duration
from autoy.models import Voice
from autoy.text import shorten_script
from autoy.tts.base import Speech, Synthesizer, timestamped_path
from autoy.tts.edge import EdgeSynthesizer, find_voice

log = logging.getLogger(__name__)

BACKENDS = ("edge", "piper", "silero")
_SECONDS_PER_DROPPED_SENTENCE = 4.5


def build_synthesizer(backend: str, settings: Settings) -> Synthesizer:
    if backend == "edge":
        return EdgeSynthesizer()
    if backend == "piper":
        from autoy.tts.piper import PiperSynthesizer

        return PiperSynthesizer(settings.paths.models)
    if backend == "silero":
        from autoy.tts.silero import SileroSynthesizer

        return SileroSynthesizer(settings.paths.models)
    raise ValueError(f"Unknown TTS backend '{backend}'. Available: {', '.join(BACKENDS)}")


def resolve_voice(backend: str, lang: str, voice_id: str | None) -> Voice | None:
    if not voice_id:
        return None
    if backend == "edge":
        voice = find_voice(lang, voice_id)
        if voice is None:
            log.warning("Voice '%s' not in the %s pool, using a random one", voice_id, lang)
        return voice
    return Voice(id=voice_id, name=voice_id)


@dataclass(frozen=True)
class CappedSpeech:
    speech: Speech
    text: str

    @property
    def path(self) -> Path:
        return self.speech.path


def synthesize(
    synthesizer: Synthesizer,
    text: str,
    lang: str,
    audio_dir: Path,
    voice: Voice | None = None,
) -> Speech:
    return synthesizer.synthesize(text, lang, timestamped_path(audio_dir, f"audio_{synthesizer.name}"), voice)


def synthesize_within(
    synthesizer: Synthesizer,
    text: str,
    lang: str,
    audio_dir: Path,
    max_seconds: float,
    voice: Voice | None = None,
    attempts: int = 3,
) -> CappedSpeech:
    current = text
    for attempt in range(1, attempts + 1):
        speech = synthesize(synthesizer, current, lang, audio_dir, voice)
        duration = media_duration(speech.path)
        if duration <= max_seconds:
            if attempt > 1:
                log.info("Script trimmed to %.1fs (limit %.0fs)", duration, max_seconds)
            return CappedSpeech(speech, current)
        drop = max(1, round((duration - max_seconds) / _SECONDS_PER_DROPPED_SENTENCE))
        shorter = shorten_script(current, drop=drop)
        if shorter is None or shorter == current:
            break
        log.warning(
            "Audio %.1fs exceeds %.0fs: dropping %d sentence(s), retry %d/%d",
            duration,
            max_seconds,
            drop,
            attempt,
            attempts,
        )
        current = shorter
        voice = speech.voice
    raise RuntimeError(f"could not fit the script into {max_seconds:.0f}s")


__all__ = [
    "BACKENDS",
    "CappedSpeech",
    "Speech",
    "Synthesizer",
    "build_synthesizer",
    "resolve_voice",
    "synthesize",
    "synthesize_within",
]
