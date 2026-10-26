from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceReference(Contract):
    document_id: int = Field(gt=0)
    file_name: str = Field(min_length=1, max_length=255)
    page_no: int | None = Field(default=None, gt=0)
    excerpt: str = Field(min_length=1, max_length=2000)


class TextBlock(Contract):
    type: Literal["text"] = "text"
    title: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1, max_length=500)
    sources: list[SourceReference] = Field(
        default_factory=list, max_length=20, json_schema_extra={"default": []}
    )


class PageSpec(Contract):
    schema_version: Literal["1.0"] = "1.0"
    page_no: int = Field(ge=1)
    layout: Literal["title", "two_column", "summary"]
    title: str = Field(min_length=1, max_length=80)
    subtitle: str = Field(default="", max_length=160)
    content: list[TextBlock] = Field(
        default_factory=list, max_length=4, json_schema_extra={"default": []}
    )


class Theme(Contract):
    name: str = Field(default="SlideMind Starter", min_length=1, max_length=100)
    primary_color: str = Field(default="#315C4E", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(default="#F5F5F0", pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field(default="#182A23", pattern=r"^#[0-9A-Fa-f]{6}$")
    title_font_family: str = Field(default="Microsoft YaHei", min_length=1, max_length=100)
    body_font_family: str = Field(default="Microsoft YaHei", min_length=1, max_length=100)
    footer: str = Field(default="SlideMind", max_length=100)


class SlideSize(Contract):
    """Slide geometry in inches (PptxGenJS defineLayout units); 5-56in covers PowerPoint's range."""

    width: float = Field(default=13.3333, ge=5, le=56)
    height: float = Field(default=7.5, ge=5, le=56)


class DeckSpec(Contract):
    title: str = Field(min_length=1, max_length=255)
    theme: Theme = Field(default_factory=Theme, json_schema_extra={"default": Theme().model_dump()})
    slide_size: SlideSize = Field(
        default_factory=SlideSize, json_schema_extra={"default": SlideSize().model_dump()}
    )
    pages: list[PageSpec] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def sequential_pages(self):
        if [page.page_no for page in self.pages] != list(range(1, len(self.pages) + 1)):
            raise ValueError("Page numbers must be sequential, starting at 1.")
        return self
