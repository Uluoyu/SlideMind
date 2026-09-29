import logging
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from slidemind_agent.planner import LocalPlanner, PlanningRequest
from slidemind_agent.workflow import can_generate_outline
from slidemind_api.contracts import (
    FileView,
    OutlineInput,
    OutlinePage,
    OutlineView,
    PresentationCreate,
    PresentationView,
    ProjectCreate,
    ProjectView,
)
from slidemind_api.models import Asset, Document, Page, Presentation, Project, Template
from slidemind_api.storage import inspect_upload, object_key
from slidemind_common.security import SecurityLevel, allowed_levels

router = APIRouter(prefix="/api/ppt")
logger = logging.getLogger(__name__)


def session(request: Request):
    with request.app.state.sessions() as db:
        yield db


DB = Annotated[Session, Depends(session)]
ProjectId = Annotated[int, Query(alias="projectId", gt=0)]


def project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    return project


def presentation_or_404(db: Session, document_id: int, project_id: int) -> Presentation:
    presentation = db.scalar(
        select(Presentation)
        .where(
            Presentation.id == document_id,
            Presentation.project_id == project_id,
        )
        .with_for_update()
    )
    if presentation is None:
        raise HTTPException(404, "当前项目下不存在此 PPT")
    return presentation


@router.get("/projects", response_model=list[ProjectView])
def list_projects(db: DB):
    return db.scalars(select(Project).order_by(Project.updated_at.desc())).all()


@router.post("/projects", response_model=ProjectView, status_code=201)
def create_project(body: ProjectCreate, db: DB, request: Request):
    if body.template_id is not None:
        template = db.get(Template, body.template_id)
        levels = allowed_levels(request.app.state.settings.security_clearance)
        if template is None or template.security_level not in levels:
            raise HTTPException(404, "模板不存在或不可访问")
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    return project


@router.get("/projects/{project_id}", response_model=ProjectView)
def get_project(project_id: int, db: DB):
    return project_or_404(db, project_id)


def list_files(db: Session, request: Request, model, project_id: int | None = None):
    statement = select(model).where(
        model.security_level.in_(allowed_levels(request.app.state.settings.security_clearance))
    )
    if project_id is not None:
        project_or_404(db, project_id)
        statement = statement.where(model.project_id == project_id)
    return db.scalars(statement.order_by(model.created_at.desc())).all()


def save_file(
    db: Session,
    request: Request,
    file: UploadFile,
    level: SecurityLevel,
    model,
    prefix: str,
    extensions: set[str],
    **fields,
):
    settings = request.app.state.settings
    if level.value not in allowed_levels(settings.security_clearance):
        raise HTTPException(403, "文件安全等级高于当前工作空间权限")
    metadata = inspect_upload(file, extensions, settings.max_upload_mb)
    key = object_key(prefix, metadata["file_type"])
    store = request.app.state.store
    try:
        store.put(key, file.file, metadata["size_bytes"])
    except Exception as exc:
        logger.exception("Object storage upload failed")
        raise HTTPException(503, "文件存储暂不可用，请检查配置后重试") from exc
    record = model(**metadata, **fields, storage_path=key, security_level=level.value)
    try:
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        try:
            store.delete(key)
        except Exception:
            logger.exception("Failed to clean up an uncommitted upload")
        raise
    return record


@router.get("/projects/{project_id}/documents", response_model=list[FileView])
def list_documents(project_id: int, db: DB, request: Request):
    return list_files(db, request, Document, project_id)


@router.post("/projects/{project_id}/documents", response_model=FileView, status_code=201)
def upload_document(
    project_id: int,
    file: UploadFile,
    db: DB,
    request: Request,
    security_level: SecurityLevel = Form(SecurityLevel.INTERNAL, alias="securityLevel"),
):
    project_or_404(db, project_id)
    return save_file(
        db,
        request,
        file,
        security_level,
        Document,
        f"projects/{project_id}/documents",
        {"pdf", "docx", "pptx", "xlsx", "txt", "md"},
        project_id=project_id,
    )


@router.get("/projects/{project_id}/assets", response_model=list[FileView])
def list_assets(project_id: int, db: DB, request: Request):
    return list_files(db, request, Asset, project_id)


@router.post("/projects/{project_id}/assets", response_model=FileView, status_code=201)
def upload_asset(
    project_id: int,
    file: UploadFile,
    db: DB,
    request: Request,
    security_level: SecurityLevel = Form(SecurityLevel.INTERNAL, alias="securityLevel"),
):
    project_or_404(db, project_id)
    return save_file(
        db,
        request,
        file,
        security_level,
        Asset,
        f"projects/{project_id}/assets",
        {"png", "jpg", "jpeg", "webp"},
        project_id=project_id,
    )


@router.get("/templates", response_model=list[FileView])
def list_templates(db: DB, request: Request):
    return list_files(db, request, Template)


@router.post("/templates", response_model=FileView, status_code=201)
def upload_template(
    file: UploadFile,
    db: DB,
    request: Request,
    security_level: SecurityLevel = Form(SecurityLevel.INTERNAL, alias="securityLevel"),
):
    return save_file(
        db,
        request,
        file,
        security_level,
        Template,
        "templates",
        {"pptx"},
        name=(file.filename or "公司模板").replace("\\", "/").split("/")[-1][:128],
    )


@router.get("/projects/{project_id}/presentations", response_model=list[PresentationView])
def list_presentations(project_id: int, db: DB):
    project_or_404(db, project_id)
    return db.scalars(
        select(Presentation)
        .where(Presentation.project_id == project_id)
        .order_by(Presentation.created_at.desc())
    ).all()


@router.post("/documents", response_model=PresentationView, status_code=201)
def create_presentation(body: PresentationCreate, db: DB):
    project_or_404(db, body.project_id)
    if any(not text.strip() or len(text) > 500 for text in body.requirements):
        raise HTTPException(422, "重点要求不能为空或超过 500 字")
    presentation = Presentation(**body.model_dump())
    db.add(presentation)
    db.commit()
    return presentation


@router.get("/documents/{document_id}", response_model=PresentationView)
def get_presentation(document_id: int, project_id: ProjectId, db: DB):
    return presentation_or_404(db, document_id, project_id)


def outline_view(db: Session, presentation: Presentation) -> OutlineView:
    pages = db.scalars(
        select(Page).where(Page.ppt_id == presentation.id).order_by(Page.page_no)
    ).all()
    return OutlineView(
        status=presentation.status, pages=[OutlinePage.model_validate(p) for p in pages]
    )


@router.get("/documents/{document_id}/outline", response_model=OutlineView)
def get_outline(document_id: int, project_id: ProjectId, db: DB):
    presentation = presentation_or_404(db, document_id, project_id)
    if presentation.status == "DRAFT":
        raise HTTPException(409, "请先生成大纲")
    return outline_view(db, presentation)


@router.post("/documents/{document_id}/outline/generate", response_model=OutlineView)
def generate_outline(document_id: int, project_id: ProjectId, db: DB):
    presentation = presentation_or_404(db, document_id, project_id)
    if not can_generate_outline(presentation.status):
        raise HTTPException(409, "大纲已经确认，不能覆盖；请创建新的 PPT 任务")
    pages = LocalPlanner().plan(
        PlanningRequest(
            title=presentation.title,
            page_count=presentation.page_count,
            audience=presentation.audience,
            style=presentation.style,
            requirements=presentation.requirements,
        )
    )
    db.execute(delete(Page).where(Page.ppt_id == presentation.id))
    db.add_all(Page(ppt_id=presentation.id, **asdict(page)) for page in pages)
    presentation.status = "OUTLINE_GENERATED"
    db.commit()
    return outline_view(db, presentation)


@router.post("/documents/{document_id}/outline/confirm", response_model=OutlineView)
def confirm_outline(document_id: int, project_id: ProjectId, body: OutlineInput, db: DB):
    presentation = presentation_or_404(db, document_id, project_id)
    if presentation.status != "OUTLINE_GENERATED":
        raise HTTPException(409, "当前状态不允许确认大纲")
    if [p.page_no for p in body.pages] != list(range(1, len(body.pages) + 1)):
        raise HTTPException(422, "页码必须从 1 开始连续排列")
    db.execute(delete(Page).where(Page.ppt_id == presentation.id))
    db.add_all(
        Page(ppt_id=presentation.id, **page.model_dump(), status="OUTLINE_CONFIRMED")
        for page in body.pages
    )
    presentation.page_count = len(body.pages)
    presentation.status = "OUTLINE_CONFIRMED"
    db.commit()
    return outline_view(db, presentation)
