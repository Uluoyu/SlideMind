from enum import StrEnum


class PresentationStatus(StrEnum):
    DRAFT = "DRAFT"
    OUTLINE_GENERATED = "OUTLINE_GENERATED"
    OUTLINE_CONFIRMED = "OUTLINE_CONFIRMED"
    CONTENT_GENERATED = "CONTENT_GENERATED"
    DESIGN_GENERATED = "DESIGN_GENERATED"
    RENDERING = "RENDERING"
    QA = "QA"
    REVISION = "REVISION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def can_generate_outline(status: str) -> bool:
    return status in {PresentationStatus.DRAFT, PresentationStatus.OUTLINE_GENERATED}
