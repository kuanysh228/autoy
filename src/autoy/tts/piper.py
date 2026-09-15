from __future__ import annotations

import io
import logging
import struct
import wave
from pathlib import Path

from autoy.media.ffmpeg import wav_to_mp3
from autoy.models import Voice
from autoy.text import prepare_voiceover_text, split_sentences
from autoy.tts.base import Speech

log = logging.getLogger(__name__)

PIPER_MODELS: dict[str, tuple[str, str]] = {
    "ruslan": ("piper/ru_RU-ruslan-medium.onnx", "ru"),
}
DEFAULT_VOICE = "ruslan"

_PAUSE_BY_TERMINATOR = {"!": 0.35, "?": 0.50}
_DEFAULT_PAUSE = 0.45


def _silence(sample_rate: int, seconds: float) -> bytes:
    frames = int(sample_rate * seconds)
    return struct.pack(f"<{frames}h", *([0] * frames))


def _pcm(voice, sentence: str) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(voice.config.sample_rate)
        voice.synthesize_wav(sentence, wav)
    buffer.seek(0)
    with wave.open(buffer, "rb") as wav:
        return wav.readframes(wav.getnframes())


def _render_wav(voice, text: str) -> bytes:
    sample_rate = voice.config.sample_rate
    sentences = split_sentences(text)
    parts: list[bytes] = []
    for index, sentence in enumerate(sentences):
        parts.append(_pcm(voice, sentence))
        if index < len(sentences) - 1:
            pause = _PAUSE_BY_TERMINATOR.get(sentence[-1], _DEFAULT_PAUSE)
            parts.append(_silence(sample_rate, pause))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(parts))
    return buffer.getvalue()


class PiperSynthesizer:
    name = "piper"

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir

    def _load(self, voice_key: str):
        from piper.voice import PiperVoice

        if voice_key not in PIPER_MODELS:
            raise ValueError(f"Piper voice '{voice_key}' is not registered")
        relative, _ = PIPER_MODELS[voice_key]
        model_path = self.models_dir / relative
        if not model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {model_path}. Download from https://huggingface.co/rhasspy/piper-voices")
        return PiperVoice.load(str(model_path))

    def synthesize(self, text: str, lang: str, output_path: Path, voice: Voice | None = None) -> Speech:
        voice_key = voice.id if voice else DEFAULT_VOICE
        relative, model_lang = PIPER_MODELS.get(voice_key, PIPER_MODELS[DEFAULT_VOICE])
        clean = prepare_voiceover_text(text, lang=model_lang)
        log.info("Piper [%s] (%d chars): %s…", voice_key, len(clean), clean[:80])
        wav_to_mp3(_render_wav(self._load(voice_key), clean), output_path)
        log.info("Piper audio: %s (%d KB)", output_path.name, output_path.stat().st_size // 1024)
        return Speech(output_path, [], Voice(id=voice_key, name=relative))
