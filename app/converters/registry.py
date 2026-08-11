"""
Central registry mapping (from_ext, to_ext) -> Converter instance.
"""

from collections import deque
from typing import Dict, List, Tuple, Type

from .base import Converter

# (from_ext, to_ext) -> Converter instance
_REGISTRY: Dict[Tuple[str, str], Converter] = {}

def register(from_ext: str, to_ext: str):
    """Class decorator: @register("mp4", "mp3")"""
    def _decorator(cls: Type[Converter]):
        instance = cls()
        instance.from_ext = from_ext.lower()
        instance.to_ext = to_ext.lower()
        _REGISTRY[(instance.from_ext, instance.to_ext)] = instance
        return cls
    return _decorator

def get_direct(from_ext: str, to_ext: str) -> Converter | None:
    return _REGISTRY.get((from_ext.lower(), to_ext.lower()))

def find_path(from_ext: str, to_ext: str) -> List[Converter] | None:
    from_ext, to_ext = from_ext.lower(), to_ext.lower()
    if from_ext == to_ext:
        return []

    # direct hit fast path
    direct = get_direct(from_ext, to_ext)
    if direct:
        return [direct]

    # BFS
    start = from_ext
    visited = {start}
    queue = deque([(start, [])])
    while queue:
        node, path = queue.popleft()
        for (f, t), converter in _REGISTRY.items():
            if f == node and t not in visited:
                new_path = path + [converter]
                if t == to_ext:
                    return new_path
                visited.add(t)
                queue.append((t, new_path))
    return None

def all_pairs() -> List[Tuple[str, str]]:
    return list(_REGISTRY.keys())