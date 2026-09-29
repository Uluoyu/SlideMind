from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class ParsedSection:
    text: str
    page_no: int | None = None


class DocumentParser(Protocol):
    def parse(self, stream: BinaryIO) -> list[ParsedSection]: ...
