from abc import ABC, abstractmethod
from pathlib import Path

class Converter(ABC):

    # Subclasses set these as class attributes, e.g.:
    # from_ext = "mp4"
    # to_ext = "mp3"
    from_ext: str = ""
    to_ext: str = ""

    @abstractmethod
    async def convert(self, input_path: Path, output_path: Path) -> None:
        """Perform the conversion. Must raise an error on failure"""
        raise NotImplementedError


class ConversionError(Exception):
    """Raised by converters when a conversion fails"""
    pass