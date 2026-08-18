"""
DELIBERATELY NOT SUPPORTED: true ttf <-> otf conversion.
Requires FontForge, which includes much heavier dependency.
"""

import asyncio
from pathlib import Path

from fontTools.ttLib import TTFont

from .base import Converter, ConversionError
from .registry import register

_WOFF_FLAVOR = {"woff": "woff", "woff2": "woff2"}

class FontContainerConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            font = TTFont(input_path)
            has_cff = "CFF " in font or "CFF2" in font
            has_glyf = "glyf" in font

            if self.to_ext == "otf" and not has_cff:
                raise ConversionError(
                    "source font uses TrueType outlines, not PostScript/CFF, "
                    "can't relabel it as .otf without lossy outline conversion (not supported)"
                )
            if self.to_ext == "ttf" and not has_glyf:
                raise ConversionError(
                    "source font uses PostScript/CFF outlines, not TrueType, "
                    "can't relabel it as .ttf without lossy outline conversion (not supported)"
                )

            font.flavor = _WOFF_FLAVOR.get(self.to_ext)  # None for ttf/otf targets
            font.save(output_path)
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError(f"font conversion failed: {e}")

_FONT_PAIRS = [
    ("ttf", "woff"), ("ttf", "woff2"),
    ("otf", "woff"), ("otf", "woff2"),
    ("woff", "ttf"), ("woff2", "ttf"),
    ("woff", "otf"), ("woff2", "otf"),
    ("woff", "woff2"), ("woff2", "woff"),
]
for _from, _to in _FONT_PAIRS:
    register(_from, _to)(FontContainerConverter)