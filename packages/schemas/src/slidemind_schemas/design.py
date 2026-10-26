"""Extracted company-template design system; the source of truth for DesignSystem.design_json."""

from typing import Literal

from pydantic import Field

from slidemind_schemas.page import Contract

HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"
EMU_PER_INCH = 914400
# Mirrors DeckSpec.slide_size bounds; rejects corrupt or nonsensical template geometry.
MIN_SLIDE_EMU = 5 * EMU_PER_INCH
MAX_SLIDE_EMU = 56 * EMU_PER_INCH


class LayoutInfo(Contract):
    """A slide-layout entry recorded from the template; informational until later phases use it."""

    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=32)


class TemplateDesign(Contract):
    """Theme-level facts extracted from a company PPTX template.

    Maps to rendering via DeckSpec.theme (accent1 -> primary, lt1 -> background, dk1 -> text) and
    DeckSpec.slide_size. Optional slots absent from the template stay None; nothing is fabricated.
    """

    schema_version: Literal["1.0"] = "1.0"
    slide_width_emu: int = Field(ge=MIN_SLIDE_EMU, le=MAX_SLIDE_EMU)
    slide_height_emu: int = Field(ge=MIN_SLIDE_EMU, le=MAX_SLIDE_EMU)
    dk1: str = Field(pattern=HEX_COLOR)
    lt1: str = Field(pattern=HEX_COLOR)
    accent1: str = Field(pattern=HEX_COLOR)
    dk2: str | None = Field(default=None, pattern=HEX_COLOR)
    lt2: str | None = Field(default=None, pattern=HEX_COLOR)
    accent2: str | None = Field(default=None, pattern=HEX_COLOR)
    accent3: str | None = Field(default=None, pattern=HEX_COLOR)
    accent4: str | None = Field(default=None, pattern=HEX_COLOR)
    accent5: str | None = Field(default=None, pattern=HEX_COLOR)
    accent6: str | None = Field(default=None, pattern=HEX_COLOR)
    title_font: str = Field(min_length=1, max_length=100)
    body_font: str = Field(min_length=1, max_length=100)
    layouts: list[LayoutInfo] = Field(min_length=1, max_length=100)
