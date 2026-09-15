from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

_VIDEO_CODEC = ("-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p")
_AUDIO_CODEC = ("-c:a", "aac", "-b:a", "192k")


class FFmpegError(RuntimeError):
    pass


def media_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def _run(cmd: Sequence[str], *, stdin: bytes | None = None, label: str) -> None:
    result = subprocess.run(cmd, input=stdin, capture_output=True)
    if result.returncode != 0:
        raise FFmpegError(f"{label}:\n{result.stderr.decode(errors='replace')[-800:]}")


def wav_to_mp3(wav_bytes: bytes, output_path: Path) -> None:
    _run(
        ["ffmpeg", "-y", "-f", "wav", "-i", "pipe:0", "-codec:a", "libmp3lame", "-b:a", "192k", str(output_path)],
        stdin=wav_bytes,
        label="wav→mp3",
    )


def _raw_input(size: tuple[int, int], fps: int) -> list[str]:
    return [
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-s",
        f"{size[0]}x{size[1]}",
        "-pix_fmt",
        "rgb24",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
    ]


def _pipe_frames(cmd: Sequence[str], frames: Iterable[bytes]) -> None:
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None and process.stderr is not None
    try:
        for frame in frames:
            try:
                process.stdin.write(frame)
            except BrokenPipeError:
                break
        process.stdin.close()
        stderr = process.stderr.read()
        process.wait()
        if process.returncode != 0:
            raise FFmpegError(f"ffmpeg:\n{stderr.decode(errors='replace')[-1000:]}")
    except Exception:
        process.kill()
        process.wait()
        raise


def encode_frames(
    frames: Iterable[Image.Image],
    *,
    size: tuple[int, int],
    fps: int,
    output_path: Path,
    audio_path: Path | None = None,
    music_path: Path | None = None,
    music_volume: float = 0.0,
    duration: float | None = None,
    video_bitrate: str = "4000k",
) -> None:
    cmd: list[str] = ["ffmpeg", "-y", *_raw_input(size, fps)]
    if audio_path:
        cmd += ["-i", str(audio_path)]
    if audio_path and music_path:
        cmd += [
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
            "-filter_complex",
            f"[2:a]volume={music_volume}[music];[1:a][music]amix=inputs=2:duration=first[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
        ]
    cmd += [*_VIDEO_CODEC, "-b:v", video_bitrate, "-r", str(fps)]
    if audio_path:
        cmd += [*_AUDIO_CODEC, "-ar", "44100", "-ac", "2"]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd.append(str(output_path))
    _pipe_frames(cmd, (frame.convert("RGB").tobytes() for frame in frames))


def encode_still(
    image: Image.Image,
    *,
    seconds: float,
    fps: int,
    output_path: Path,
    video_bitrate: str = "6000k",
) -> None:
    size = image.size
    cmd = [
        "ffmpeg",
        "-y",
        *_raw_input(size, fps),
        "-f",
        "lavfi",
        "-i",
        f"aevalsrc=0:s=44100:c=stereo:d={seconds:.3f}",
        *_VIDEO_CODEC,
        "-b:v",
        video_bitrate,
        *_AUDIO_CODEC,
        "-t",
        f"{seconds:.3f}",
        str(output_path),
    ]
    raw = image.convert("RGB").tobytes()
    _pipe_frames(cmd, (raw for _ in range(round(seconds * fps))))


def concat(parts: Sequence[Path], output_path: Path, list_path: Path) -> None:
    list_path.write_text("".join(f"file '{part}'\n" for part in parts), encoding="utf-8")
    _run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output_path)],
        label="concat",
    )


def mix_music(video_path: Path, music_path: Path, volume: float) -> Path:
    output = video_path.with_name(f"{video_path.stem}_music.mp4")
    try:
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-stream_loop",
                "-1",
                "-i",
                str(music_path),
                "-filter_complex",
                f"[1:a]volume={volume}[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=5[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                *_AUDIO_CODEC,
                str(output),
            ],
            label="music mix",
        )
    except FFmpegError as exc:
        log.warning("Music mix failed, keeping the dry video: %s", exc)
        return video_path
    video_path.unlink(missing_ok=True)
    return output
