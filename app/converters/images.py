import asyncio
from pathlib import Path

from PIL import Image

from .base import Converter, ConversionError
from .registry import register

_PILLOW_FORMAT = {
    "jpg": "JPEG", "jpeg": "JPEG", "jfif": "JPEG", "png": "PNG",
    "webp": "WEBP", "bmp": "BMP", "tiff": "TIFF", "ico": "ICO",
}

class PillowConverter(Converter):
    def __init__(slef):
        pass

    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            img = Image.open(input_path)
            target_format = _PILLOW_FORMAT[self.to_ext]
            if target_format in ("JPEG", "BMP") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, format=target_format)
        except Exception as e:
            raise ConversionError(f"image conversion failed: {e}")

_RASTER_PAIRS = [
    ("png", "jpg"), ("jpg", "png"),
    ("png", "webp"), ("webp", "png"),
    ("jpg", "webp"), ("webp", "jpg"),
    ("png", "bmp"), ("bmp", "png"),
    ("png", "ico"), ("jpg", "ico"),
    ("tiff", "png"), ("png", "tiff"),
    ("jfif", "png"), ("jfif", "jpg"), ("jfif", "webp"),
    ("png", "jfif"), ("jpg", "jfif"),
]

for _from, _to in _RASTER_PAIRS:
    register(_from, _to)(PillowConverter)