import asyncio
from pathlib import Path

import pillow_heif
from PIL import Image

from .base import Converter, ConversionError
from .registry import register

pillow_heif.register_heif_opener()

_HEIF_FORMAT = {
    "heic": "HEIF",
    "heif": "HEIF",
}
# Reuse the same target-format map images.py uses, so heic can convert
# to anything Pillow already supports on the output side.
_OUTPUT_FORMAT = {
    "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "jfif": "JPEG",
    "webp": "WEBP", "bmp": "BMP", "tiff": "TIFF",
}

class HeicConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            img = Image.open(input_path)
            if self.to_ext in _HEIF_FORMAT:
                # converting INTO heic
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                img.save(output_path, format="HEIF")
            else:
                target_format = _OUTPUT_FORMAT[self.to_ext]
                if target_format in ("JPEG", "BMP") and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output_path, format=target_format)
        except Exception as e:
            raise ConversionError(f"heic conversion failed: {e}")

_HEIC_PAIRS = [
    ("heic", "jpg"), ("heic", "png"), ("heic", "webp"),
    ("heif", "jpg"), ("heif", "png"),
    ("jpg", "heic"), ("png", "heic"),
]
for _from, _to in _HEIC_PAIRS:
    register(_from, _to)(HeicConverter)
