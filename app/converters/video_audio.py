import asyncio
from pathlib import Path

from .base import Converter, ConversionError
from .registry import register

class FfmpegConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        cmd = [
            "ffmpeg",
            "-y",  # overwrite output if present
            "-i", str(input_path),
            "-hide_banner",
            "-loglevel", "error",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        if proc.returncode != 0:
            raise ConversionError(f"ffmpeg failed: {stderr.decode(errors='ignore')[:500]}")
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise ConversionError("ffmpeg produced no output")


_AUDIO_VIDEO_PAIRS = [
    ("mp4", "mp3"), ("mp4", "wav"), ("mp4", "webm"), ("mp4", "gif"),
    ("mov", "mp4"), ("mov", "mp3"),
    ("avi", "mp4"), ("avi", "mp3"),
    ("mkv", "mp4"), ("mkv", "mp3"),
    ("webm", "mp4"), ("webm", "mp3"),
    ("wav", "mp3"), ("mp3", "wav"),
    ("flac", "mp3"), ("m4a", "mp3"),
]

for _from, _to in _AUDIO_VIDEO_PAIRS:
    register(_from, _to)(FfmpegConverter)