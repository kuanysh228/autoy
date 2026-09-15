from __future__ import annotations

import io
import logging
import wave
from pathlib import Path

from autoy.media.ffmpeg import wav_to_mp3
from autoy.models import Voice
from autoy.text import prepare_voiceover_text, split_sentences
from autoy.tts.base import Speech

log = logging.getLogger(__name__)

MODEL_URL = "https://models.silero.ai/models/tts/multi/v2_multi.pt"
MODEL_FILENAME = "v2_multi.pt"
SAMPLE_RATE = 16_000
DEFAULT_SPEAKER = "ruslan"
SPEAKERS = frozenset({"aidar", "baya", "kseniya", "irina", "ruslan", "natasha"})
_CHUNK_PAUSE_SEC = 0.25
_MAX_CHUNK_CHARS = 300


def _chunk_text(text: str, max_len: int = _MAX_CHUNK_CHARS) -> list[str]:
    chunks: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_len:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def _wav_bytes(audio, sample_rate: int) -> bytes:
    pcm = (audio.numpy() * 32767).clip(-32768, 32767).astype("int16")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


class SileroSynthesizer:
    name = "silero"

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir / "silero"
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        import torch

        self.models_dir.mkdir(parents=True, exist_ok=True)
        model_path = self.models_dir / MODEL_FILENAME
        if not model_path.exists():
            log.info("Downloading Silero model: %s", MODEL_URL)
            torch.hub.download_url_to_file(MODEL_URL, str(model_path), progress=True)
        model = torch.package.PackageImporter(str(model_path)).load_pickle("tts_models", "model")
        model.to(torch.device("cpu"))
        self._model = model
        return model

    def synthesize(self, text: str, lang: str, output_path: Path, voice: Voice | None = None) -> Speech:
        import torch

        speaker = voice.id if voice else DEFAULT_SPEAKER
        if speaker not in SPEAKERS:
            raise ValueError(f"Silero speaker '{speaker}' not in {sorted(SPEAKERS)}")
        clean = prepare_voiceover_text(text, lang="ru")
        log.info("Silero [%s] (%d chars): %s…", speaker, len(clean), clean[:80])

        model = self._load()
        silence = torch.zeros(int(SAMPLE_RATE * _CHUNK_PAUSE_SEC))
        parts = []
        for chunk in _chunk_text(clean):
            try:
                parts.append(model.apply_tts(texts=[chunk], speakers=[speaker], sample_rate=SAMPLE_RATE)[0])
            except Exception as exc:
                log.warning("Silero failed on chunk '%s': %s", chunk[:60], exc)
        if not parts:
            raise RuntimeError("Silero produced no audio")

        combined = parts[0]
        for part in parts[1:]:
            combined = torch.cat([combined, silence, part])
        wav_to_mp3(_wav_bytes(combined, SAMPLE_RATE), output_path)
        log.info("Silero audio: %s (%d KB)", output_path.name, output_path.stat().st_size // 1024)
        return Speech(output_path, [], Voice(id=f"silero_{speaker}", name=speaker))
