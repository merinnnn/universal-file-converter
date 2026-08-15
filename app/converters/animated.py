import asyncio
from pathlib import Path

from PIL import Image, ImageSequence

from .base import Converter, ConversionError
from .registry import register
from .video_audio import FfmpegConverter

GIF_TIMEOUT = 120

# video -> gif: reuse the ffmpeg converter
for _to_gif_from in ("mov", "avi", "mkv", "webm"):
    register(_to_gif_from, "gif")(FfmpegConverter)

class GifToVideoConverter(Converter):
    """Needs an even-dimensions filter that FfmpegConverter doesn't apply."""
    async def convert(self, input_path: Path, output_path: Path) -> None:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-hide_banner", "-loglevel", "error",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=GIF_TIMEOUT)
        if proc.returncode != 0:
            raise ConversionError(f"ffmpeg failed: {stderr.decode(errors='ignore')[:500]}")
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise ConversionError("ffmpeg produced no output")

for _to in ("mp4", "webm", "mov"):
    register("gif", _to)(GifToVideoConverter)


class GifToImageConverter(Converter):
    """GIF -> static image, taking the first frame."""
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            img = Image.open(input_path)
            img.seek(0)
            fmt = "JPEG" if self.to_ext in ("jpg", "jpeg") else "PNG"
            img = img.convert("RGB" if fmt == "JPEG" else "RGBA")
            img.save(output_path, format=fmt)
        except Exception as e:
            raise ConversionError(f"gif-to-image failed: {e}")

register("gif", "png")(GifToImageConverter)
register("gif", "jpg")(GifToImageConverter)

class ApngGifConverter(Converter):
    """apng <-> gif, preserving animation by extracting every frame 
    and re-encoding into the target container."""
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            img = Image.open(input_path)
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(img):
                frames.append(frame.convert("RGBA").copy())
                durations.append(frame.info.get("duration", 100))
            if not frames:
                raise ConversionError("no frames found in source file")

            if self.to_ext == "gif":
                p_frames = [f.convert("P", palette=Image.ADAPTIVE) for f in frames]
                p_frames[0].save(
                    output_path, format="GIF", save_all=True,
                    append_images=p_frames[1:], duration=durations,
                    loop=0, disposal=2,
                )
            else:  # apng
                frames[0].save(
                    output_path, format="PNG", save_all=True,
                    append_images=frames[1:], duration=durations, loop=0,
                )
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError(f"apng/gif conversion failed: {e}")

register("apng", "gif")(ApngGifConverter)
register("gif", "apng")(ApngGifConverter)
