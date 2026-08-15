import asyncio
from pathlib import Path

import vtracer
from PIL import Image

from .base import Converter, ConversionError
from .registry import register


class VectorizeConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            # vtracer needs PNG input; convert if handed a jpg 
            src = input_path
            tmp_png = None
            if input_path.suffix.lower() not in (".png",):
                tmp_png = input_path.with_suffix(".vectorize_tmp.png")
                Image.open(input_path).convert("RGBA").save(tmp_png, format="PNG")
                src = tmp_png

            vtracer.convert_image_to_svg_py(str(src), str(output_path))

            if tmp_png is not None:
                tmp_png.unlink(missing_ok=True)
        except Exception as e:
            raise ConversionError(f"vectorization failed: {e}")

register("png", "svg")(VectorizeConverter)
register("jpg", "svg")(VectorizeConverter)