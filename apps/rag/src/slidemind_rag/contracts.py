from dataclasses import dataclass
from typing import Protocol

from slidemind_common.security import SecurityLevel
from slidemind_schemas.page import SourceReference


@dataclass(frozen=True)
class RetrievalContext:
    project_id: int
    clearance: SecurityLevel
    top_k: int = 5


class Retriever(Protocol):
    """Implementations MUST filter by project and server-issued clearance before ranking."""

    def search(self, query: str, context: RetrievalContext) -> list[SourceReference]: ...


class Embedder(Protocol):
    @property
    def model_id(self) -> str: ...
    @property
    def dimensions(self) -> int: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, query: str) -> list[float]: ...
