from typing import Literal, Protocol

from pydantic import BaseModel


class QualityIssue(BaseModel):
    page_no: int
    severity: Literal["low", "medium", "high"]
    kind: str
    message: str


class VisionInspector(Protocol):
    def inspect(self, png: bytes, page_no: int) -> list[QualityIssue]: ...
