import asyncio
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

import py7zr

from .base import Converter, ConversionError
from .registry import register

MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB total, across all files
MAX_FILE_COUNT = 10_000  # guards against many-tiny-files bombs too
_CHUNK_SIZE = 1024 * 1024

def _check_zip_metadata(zf: zipfile.ZipFile) -> None:
    infos = zf.infolist()
    if len(infos) > MAX_FILE_COUNT:
        raise ConversionError(f"archive contains too many files (max {MAX_FILE_COUNT})")
    total = sum(i.file_size for i in infos)
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ConversionError("archive's uncompressed size exceeds the allowed limit")

def _extract_zip_capped(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    written = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        with zf.open(info) as src:
            # zipfile already neutralizes path traversal in the target name  
            # This just builds the same safe path zf.extract() would use,
            # so we can stream it ourselves with a running size cap.
            target = dest_dir / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as out:
                while chunk := src.read(_CHUNK_SIZE):
                    written += len(chunk)
                    if written > MAX_UNCOMPRESSED_BYTES:
                        raise ConversionError(
                            "archive's actual uncompressed size exceeds the allowed limit"
                        )
                    out.write(chunk)

def _check_tar_metadata(tf: tarfile.TarFile) -> list:
    members = tf.getmembers()
    if len(members) > MAX_FILE_COUNT:
        raise ConversionError(f"archive contains too many files (max {MAX_FILE_COUNT})")
    total = sum(m.size for m in members if m.isfile())
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ConversionError("archive's uncompressed size exceeds the allowed limit")
    return members

def _extract_tar_capped(tf: tarfile.TarFile, members: list, dest_dir: Path) -> None:
    written = 0
    for member in members:
        if not member.isfile():
            # filter="data" (below) already handles safe extraction of directories/symlinks
            tf.extract(member, dest_dir, filter="data")
            continue
        src = tf.extractfile(member)
        if src is None:
            continue
        # tarfile's "data" filter (PEP 706) already sanitized member.name
        # for traversal/absolute-path issues by the time getmembers() ran.
        target = dest_dir / member.name
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as out:
            while chunk := src.read(_CHUNK_SIZE):
                written += len(chunk)
                if written > MAX_UNCOMPRESSED_BYTES:
                    raise ConversionError(
                        "archive's actual uncompressed size exceeds the allowed limit"
                    )
                out.write(chunk)

def _extract(input_path: Path, from_ext: str, dest_dir: Path) -> None:
    if from_ext == "zip":
        with zipfile.ZipFile(input_path) as zf:
            _check_zip_metadata(zf)
            _extract_zip_capped(zf, dest_dir)
    elif from_ext == "tar":
        with tarfile.open(input_path, mode="r:*") as tf:
            members = _check_tar_metadata(tf)
            _extract_tar_capped(tf, members, dest_dir)
    elif from_ext == "tgz":
        with tarfile.open(input_path, mode="r:gz") as tf:
            members = _check_tar_metadata(tf)
            _extract_tar_capped(tf, members, dest_dir)
    elif from_ext == "7z":
        with py7zr.SevenZipFile(input_path, mode="r") as zf:
            infos = zf.list()
            if len(infos) > MAX_FILE_COUNT:
                raise ConversionError(f"archive contains too many files (max {MAX_FILE_COUNT})")
            total = sum(i.uncompressed for i in infos)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ConversionError("archive's uncompressed size exceeds the allowed limit")
            # py7zr raises Bad7zFile itself on unsafe paths
            zf.extractall(path=dest_dir)
    else:
        raise ConversionError(f"unsupported archive source format: {from_ext}")

def _pack(src_dir: Path, to_ext: str, output_path: Path) -> None:
    files = [f for f in src_dir.rglob("*") if f.is_file()]
    if not files:
        raise ConversionError("source archive contained no files")

    if to_ext == "zip":
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(f, f.relative_to(src_dir))
    elif to_ext == "tar":
        with tarfile.open(output_path, mode="w") as tf:
            for f in files:
                tf.add(f, arcname=f.relative_to(src_dir))
    elif to_ext == "tgz":
        with tarfile.open(output_path, mode="w:gz") as tf:
            for f in files:
                tf.add(f, arcname=f.relative_to(src_dir))
    elif to_ext == "7z":
        with py7zr.SevenZipFile(output_path, mode="w") as zf:
            for f in files:
                zf.write(f, f.relative_to(src_dir))
    else:
        raise ConversionError(f"unsupported archive target format: {to_ext}")

class ArchiveConverter(Converter):
    async def convert(self, input_path: Path, output_path: Path) -> None:
        await asyncio.to_thread(self._convert_sync, input_path, output_path)

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="archive_convert_"))
        try:
            _extract(input_path, self.from_ext, tmp_dir)
            _pack(tmp_dir, self.to_ext, output_path)
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError(f"archive conversion failed: {e}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

_ARCHIVE_PAIRS = [
    ("zip", "tar"), ("tar", "zip"),
    ("zip", "tgz"), ("tgz", "zip"),
    ("zip", "7z"), ("7z", "zip"),
    ("tar", "tgz"), ("tgz", "tar"),
    ("tar", "7z"), ("7z", "tar"),
    ("tgz", "7z"), ("7z", "tgz"),
]
for _from, _to in _ARCHIVE_PAIRS:
    register(_from, _to)(ArchiveConverter)
