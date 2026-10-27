from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from slidemind_common.security import SecurityLevel
from slidemind_schemas.page import PageSpec


class DTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
        extra="forbid",
        str_strip_whitespace=True,
    )


class ProjectCreate(DTO):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)
    template_id: int | None = Field(default=None, gt=0)


class ProjectView(ProjectCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class FileView(DTO):
    id: int
    file_name: str
    file_type: str
    size_bytes: int
    sha256: str
    security_level: SecurityLevel
    status: str
    created_at: datetime


class DocumentView(FileView):
    processing_error: str | None
    chunk_count: int
    processed_at: datetime | None


class TemplateView(FileView):
    processing_error: str | None


class ProjectTemplateInput(DTO):
    template_id: int | None = Field(default=None, gt=0)


class PresentationCreate(DTO):
    project_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    page_count: int = Field(default=8, ge=1, le=50)
    audience: str = Field(default="", max_length=128)
    style: str = Field(default="专业、简洁", max_length=255)
    requirements: list[str] = Field(default_factory=list, max_length=20)


class PresentationView(PresentationCreate):
    id: int
    status: str
    created_at: datetime


class OutlinePage(DTO):
    page_no: int = Field(ge=1, le=50)
    title: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=500)
    # Clients cite evidence by chunk id only; the server rebuilds the snapshot it stores.
    source_chunk_ids: list[int] = Field(default_factory=list, max_length=16)
    # Echoed back from OutlineView by clients; never trusted, always rebuilt from the ids.
    sources: list[dict] = Field(default_factory=list, max_length=16, exclude=True)


class OutlineInput(DTO):
    pages: list[OutlinePage] = Field(min_length=1, max_length=50)


class OutlineGenerateInput(OutlineInput):
    feedback: str = Field(min_length=1, max_length=1000)


class OutlineSource(DTO):
    chunk_id: int
    document_id: int
    file_name: str
    page_no: int | None
    location: str
    excerpt: str


class OutlinePageView(OutlinePage):
    sources: list[OutlineSource] = Field(default_factory=list, max_length=16)


class OutlineView(DTO):
    status: str
    pages: list[OutlinePageView]
    planner: str = "local-scaffold"
    warning: str | None = None


class PageView(DTO):
    page_no: int
    status: str
    version: int
    page_json: PageSpec | None


class PagesView(DTO):
    status: str
    pages: list[PageView]
    generator: str = "local-scaffold"


class PageUpdate(DTO):
    version: int = Field(ge=1)
    page: PageSpec


class RenderView(DTO):
    status: str
    download_url: str
    theme_source: Literal["default", "template"] = "default"
    theme_name: str = "SlideMind Starter"
