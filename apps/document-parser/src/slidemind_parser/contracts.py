from dataclasses import dataclass, field
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class ParsedSection:
    text: str
    page_no: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class DocumentParser(Protocol):
    def parse(self, stream: BinaryIO) -> list[ParsedSection]: ...
