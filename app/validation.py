from typing import Callable, Dict

def _has_riff_subtype(data: bytes, subtype: bytes) -> bool:
    return len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == subtype

def _is_isobmff(data: bytes) -> bool:
    return len(data) >= 12 and data[4:8] == b"ftyp"

def _is_ebml(data: bytes) -> bool:
    return len(data) >= 4 and data[0:4] == b"\x1a\x45\xdf\xa3"

def _is_mp3(data: bytes) -> bool:
    if len(data) >= 3 and data[0:3] == b"ID3":
        return True
    return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0

CHECKS: Dict[str, Callable[[bytes], bool]] = {
    "png": lambda d: d[:8] == b"\x89PNG\r\n\x1a\n",
    "jpg": lambda d: d[:3] == b"\xff\xd8\xff",
    "jpeg": lambda d: d[:3] == b"\xff\xd8\xff",
    "webp": lambda d: _has_riff_subtype(d, b"WEBP"),
    "bmp": lambda d: d[:2] == b"BM",
    "tiff": lambda d: d[:4] in (b"II*\x00", b"MM\x00*"),
    "ico": lambda d: d[:4] == b"\x00\x00\x01\x00",
    "mp4": _is_isobmff,
    "mov": _is_isobmff,
    "m4a": _is_isobmff,
    "avi": lambda d: _has_riff_subtype(d, b"AVI "),
    "mkv": _is_ebml,
    "webm": _is_ebml,
    "wav": lambda d: _has_riff_subtype(d, b"WAVE"),
    "mp3": _is_mp3,
    "flac": lambda d: d[:4] == b"fLaC",
}

SNIFF_BYTES_NEEDED = 16

def sniff_matches(claimed_ext: str, header:  bytes) -> bool:
    check = CHECKS.get(claimed_ext.lower())
    if check is None:
        return True
    try:
        return bool(check(header))
    except Exception:
        return False