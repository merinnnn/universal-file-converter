import asyncio
import shutil
import uuid
from pathlib import Path

from PIL import Image

from .base import Converter, ConversionError
from .registry import register

LIBREOFFICE_TIMEOUT = 120
PANDOC_TIMEOUT = 120
POPPLER_TIMEOUT  = 60

class LibreOfficeConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        # Each invocation gets its own throwaway profile directory.
        # This is what actually lets multiple LibreOffice conversions run concurrently
        profile_dir = Path(f"/tmp/lo_profile_{uuid.uuid4().hex}")
        out_dir = output_path.parent
        target_format = self.to_ext

        cmd = [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to", target_format,
            "--outdir", str(out_dir),
            str(input_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=LIBREOFFICE_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            raise ConversionError("libreoffice conversion timed out")
        finally:
            shutil.rmtree(profile_dir, ignore_errors=True)

        if proc.returncode != 0:
            raise ConversionError(f"libreoffice failed: {stderr.decode(errors='ignore')[:500]}")

        # LibreOffice names its output after the input file's stem, so find and rename it
        produced = out_dir / f"{input_path.stem}.{target_format}"
        if not produced.exists():
            raise ConversionError("libreoffice produced no output file")
        if produced != output_path:
            produced.rename(output_path)

_LIBREOFFICE_PAIRS = [
    ("docx", "pdf"), ("pdf", "docx"),
    ("pptx", "pdf"),
    ("xlsx", "pdf"),
    ("odt", "pdf"), ("docx", "odt"), ("odt", "docx"),
]
for _from, _to in _LIBREOFFICE_PAIRS:
    register(_from, _to)(LibreOfficeConverter)


class PdfToImageConverter(Converter):
     """
    Renders a PDF to an image via Poppler's pdftoppm.
    MVP LIMITATION: only the first page is rendered.
    """
     async def convert(self, input_path: Path, output_path: Path) -> None:
        img_ext = "jpg" if self.to_ext in ("jpg", "jpeg") else "png"
        flag = "-jpeg" if img_ext == "jpg" else "-png"
        prefix = output_path.with_suffix("")

        cmd = ["pdftoppm", flag, "-f", "1", "-l", "1", str(input_path), str(prefix)]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=POPPLER_TIMEOUT)
        if proc.returncode != 0:
            raise ConversionError(f"pdftoppm failed: {stderr.decode(errors='ignore')[:500]}")

        # pdftoppm pads the page-number suffix based on total page count, 
        # so we don't know the exact filename in advance.
        # glob for whatever it actually produced.
        matches = sorted(prefix.parent.glob(f"{prefix.name}-*.{img_ext}"))
        if not matches:
            raise ConversionError("pdftoppm produced no output")
        matches[0].rename(output_path)

register("pdf", "jpg")(PdfToImageConverter)
register("pdf", "png")(PdfToImageConverter)


class ImageToPdfConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        try:
            img = Image.open(input_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, format="PDF")
        except Exception as e:
            raise ConversionError(f"image-to-pdf failed: {e}")

register("jpg", "pdf")(ImageToPdfConverter)
register("jpeg", "pdf")(ImageToPdfConverter)
register("png", "pdf")(ImageToPdfConverter)


class PandocConverter(Converter):
    """Ebook conversions. Uses weasyprint as pandoc's PDF engine since
    it's a Python library (pip-installable) rather than pulling in a
    full LaTeX distribution just to make PDFs."""
    async def convert(self, input_path: Path, output_path: Path) -> None:
        cmd = ["pandoc", str(input_path), "-o", str(output_path)]
        if self.to_ext == "pdf":
            cmd += ["--pdf-engine=weasyprint"]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=PANDOC_TIMEOUT)
        if proc.returncode != 0:
            raise ConversionError(f"pandoc failed: {stderr.decode(errors='ignore')[:500]}")
        if not output_path.exists():
            raise ConversionError("pandoc produced no output")

_PANDOC_PAIRS = [
    ("epub", "pdf"),
    ("epub", "docx"),
    ("docx", "epub"),
    ("epub", "html"),
]
for _from, _to in _PANDOC_PAIRS:
    register(_from, _to)(PandocConverter)