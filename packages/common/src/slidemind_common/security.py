from enum import StrEnum


class SecurityLevel(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    TOP_SECRET = "TOP_SECRET"


def allowed_levels(clearance: SecurityLevel) -> list[str]:
    levels = list(SecurityLevel)
    return [level.value for level in levels[: levels.index(clearance) + 1]]
