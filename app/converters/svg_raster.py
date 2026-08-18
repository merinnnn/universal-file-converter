import asyncio
from pathlib import Path

import cairosvg

from .base import Converter, ConversionError
from .registry import register

class SvgRasterConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            if self.to_ext == "png":
                cairosvg.svg2png(url=str(input_path), write_to=str(output_path))
            elif self.to_ext == "pdf":
                cairosvg.svg2pdf(url=str(input_path), write_to=str(output_path))
            else:
                raise ConversionError(f"unsupported svg target: {self.to_ext}")
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError(f"svg conversion failed: {e}")

register("svg", "png")(SvgRasterConverter)
register("svg", "pdf")(SvgRasterConverter)