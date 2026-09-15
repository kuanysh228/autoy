from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import random
from pathlib import Path

from autoy.models import Voice, WordEvent
from autoy.text import prepare_voiceover_text
from autoy.tts.base import Speech

log = logging.getLogger(__name__)

VOICE_POOL: dict[str, tuple[Voice, ...]] = {
    "ru": (
        Voice(id="dmitry", name="ru-RU-DmitryNeural", rate="-8%"),
        Voice(id="dmitry_newscast", name="ru-RU-DmitryNeural", rate="-8%", style="newscast"),
    ),
    "en": (
        Voice(id="aria", name="en-US-AriaNeural", rate="-5%"),
        Voice(id="emma", name="en-US-EmmaNeural", rate="-5%"),
    ),
}

GTTS_FALLBACK = Voice(id="gtts_fallback", name="gtts")


def voices_for(lang: str) -> tuple[Voice, ...]:
    return VOICE_POOL.get(lang, VOICE_POOL["ru"])


def find_voice(lang: str, voice_id: str) -> Voice | None:
    return next((v for v in voices_for(lang) if v.id == voice_id), None)


async def _stream(text: str, voice: Voice, output_path: Path) -> list[WordEvent]:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice.name, rate=voice.rate, pitch=voice.pitch, boundary="WordBoundary")
    subs = edge_tts.SubMaker()
    with output_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                subs.feed(chunk)
    return [WordEvent(cue.content, cue.start.total_seconds(), cue.end.total_seconds()) for cue in subs.cues]


def _run_isolated(coro, timeout: int = 90):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result(timeout=timeout)


class EdgeSynthesizer:
    name = "edge"

    def __init__(self, attempts: int = 3, gtts_fallback: bool = True) -> None:
        self.attempts = attempts
        self.gtts_fallback = gtts_fallback

    def synthesize(self, text: str, lang: str, output_path: Path, voice: Voice | None = None) -> Speech:
        voice = voice or random.choice(voices_for(lang))
        clean = prepare_voiceover_text(text, lang=lang)
        log.info("TTS input (%d chars): %s", len(clean), clean)

        for attempt in range(1, self.attempts + 1):
            try:
                words = _run_isolated(_stream(clean, voice, output_path))
                log.info("Audio [%s rate=%s]: %s | words=%d", voice.id, voice.rate, output_path.name, len(words))
                return Speech(output_path, words, voice)
            except Exception as exc:
                log.warning("edge-tts attempt %d/%d failed (%s): %s", attempt, self.attempts, voice.id, exc)

        if not self.gtts_fallback:
            raise RuntimeError("edge-tts failed after all attempts")
        return self._gtts(clean, lang, output_path)

    @staticmethod
    def _gtts(text: str, lang: str, output_path: Path) -> Speech:
        from gtts import gTTS

        try:
            gTTS(text=text, lang=lang, slow=False).save(str(output_path))
        except Exception as exc:
            raise RuntimeError(f"speech synthesis failed: {exc}") from exc
        log.info("Audio (gTTS fallback): %s", output_path.name)
        return Speech(output_path, [], GTTS_FALLBACK)
