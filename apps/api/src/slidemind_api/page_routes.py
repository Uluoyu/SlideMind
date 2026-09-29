import logging
from io import BytesIO

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from slidemind_agent.pages import scaffold_page
from slidemind_agent.planner import PlannedPage
from slidemind_api.contracts import PagesView, PageUpdate, PageView, RenderView
from slidemind_api.models import Document, Page, Presentation, utcnow
from slidemind_api.rendering import PPTX_MEDIA_TYPE, RenderInputTooLarge, encode_deck, validate_pptx
from slidemind_api.routes import DB, ProjectId, presentation_or_404
from slidemind_api.storage import object_key
from slidemind_common.security import allowed_levels
from slidemind_schemas.page import DeckSpec, PageSpec

router = APIRouter(prefix="/api/ppt/documents", tags=["pages"])
logger = logging.getLogger(__name__)


def pages_for(db: Session, presentation: Presentation) -> list[Page]:
    return list(
        db.scalars(select(Page).where(Page.ppt_id == presentation.id).order_by(Page.page_no))
    )


def require_confirmed(presentation: Presentation):
    if presentation.status in {"DRAFT", "OUTLINE_GENERATED"}:
        raise HTTPException(409, "请先确认大纲")


def lock_changes(db: Session, presentation: Presentation):
    """Serialize writes also on SQLite; retain the transaction through rendering.

    A process crash rolls back the transient RENDERING status. PostgreSQL additionally
    holds the row lock acquired by presentation_or_404. Stale SQLite snapshots conflict.
    """
    result = db.execute(
        update(Presentation)
        .where(
            Presentation.id == presentation.id,
            Presentation.updated_at == presentation.updated_at,
        )
        .values(updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "PPT 已发生变化，请刷新后重试")
    db.refresh(presentation)


def check_sources(db: Session, request: Request, project_id: int, specs, status_code=403):
    refs = [source for spec in specs for block in spec.content for source in block.sources]
    if not refs:
        return
    documents = {
        doc.id: doc
        for doc in db.scalars(
            select(Document).where(
                Document.id.in_({source.document_id for source in refs}),
                Document.project_id == project_id,
                Document.security_level.in_(
                    allowed_levels(request.app.state.settings.security_clearance)
                ),
            )
        )
    }
    if any(
        source.document_id not in documents
        or source.file_name != documents[source.document_id].file_name
        for source in refs
    ):
        raise HTTPException(status_code, "页面引用了当前项目之外或无权访问的资料")


def specs_for(pages: list[Page]) -> list[PageSpec]:
    return [PageSpec.model_validate(page.page_json) for page in pages if page.page_json is not None]


def view(presentation: Presentation, pages: list[Page]) -> PagesView:
    return PagesView(status=presentation.status, pages=[PageView.model_validate(p) for p in pages])


def cleanup(request: Request, key: str | None):
    if key:
        try:
            request.app.state.store.delete(key)
        except Exception:
            logger.exception("Failed to remove obsolete presentation artifact")


def save_pages(db: Session, request: Request, presentation: Presentation, pages: list[Page]):
    old_key = presentation.ppt_path
    presentation.ppt_path = None
    presentation.status = (
        "DESIGN_GENERATED"
        if all(page.page_json is not None for page in pages)
        else "OUTLINE_CONFIRMED"
    )
    db.commit()
    cleanup(request, old_key)


@router.get("/{document_id}/pages", response_model=PagesView)
def get_pages(document_id: int, project_id: ProjectId, db: DB, request: Request):
    presentation = presentation_or_404(db, document_id, project_id)
    pages = pages_for(db, presentation)
    check_sources(db, request, project_id, specs_for(pages))
    return view(presentation, pages)


@router.post("/{document_id}/pages/generate", response_model=PagesView)
def generate_pages(document_id: int, project_id: ProjectId, db: DB, request: Request):
    presentation = presentation_or_404(db, document_id, project_id)
    require_confirmed(presentation)
    lock_changes(db, presentation)
    pages = pages_for(db, presentation)
    check_sources(db, request, project_id, specs_for(pages))
    missing = [page for page in pages if page.page_json is None]
    for page in missing:
        fill_page(page, presentation.page_count)
    if missing:
        save_pages(db, request, presentation, pages)
    return view(presentation, pages)


def fill_page(page: Page, page_count: int):
    spec = scaffold_page(PlannedPage(page.page_no, page.title, page.purpose), page_count)
    page.page_json = spec.model_dump()
    page.page_type = spec.layout
    page.status = "DESIGN_GENERATED"
    page.version += 1


@router.post("/{document_id}/pages/{page_no}/generate", response_model=PageView)
def generate_page(document_id: int, page_no: int, project_id: ProjectId, db: DB, request: Request):
    presentation = presentation_or_404(db, document_id, project_id)
    require_confirmed(presentation)
    lock_changes(db, presentation)
    pages = pages_for(db, presentation)
    page = next((p for p in pages if p.page_no == page_no), None)
    if page is None:
        raise HTTPException(404, "页面不存在")
    if page.page_json is not None:
        raise HTTPException(409, "页面已生成，请编辑现有内容")
    fill_page(page, presentation.page_count)
    save_pages(db, request, presentation, pages)
    return page


@router.post("/{document_id}/pages/{page_no}", response_model=PageView)
def update_page(
    document_id: int,
    page_no: int,
    project_id: ProjectId,
    body: PageUpdate,
    db: DB,
    request: Request,
):
    presentation = presentation_or_404(db, document_id, project_id)
    require_confirmed(presentation)
    lock_changes(db, presentation)
    pages = pages_for(db, presentation)
    page = next((p for p in pages if p.page_no == page_no), None)
    if page is None:
        raise HTTPException(404, "页面不存在")
    if body.page.page_no != page_no:
        raise HTTPException(422, "页面编号与请求路径不一致")
    if page.version != body.version:
        raise HTTPException(409, "页面已被更新，请刷新后再编辑")
    check_sources(db, request, project_id, [body.page], status_code=422)
    page.page_json = body.page.model_dump()
    page.page_type = body.page.layout
    page.status = "DESIGN_GENERATED"
    page.version += 1
    save_pages(db, request, presentation, pages)
    return page


@router.post("/{document_id}/render", response_model=RenderView)
def render(document_id: int, project_id: ProjectId, db: DB, request: Request):
    presentation = presentation_or_404(db, document_id, project_id)
    require_confirmed(presentation)
    lock_changes(db, presentation)
    pages = pages_for(db, presentation)
    if len(pages) != presentation.page_count or any(page.page_json is None for page in pages):
        raise HTTPException(409, "请先生成全部页面")
    specs = specs_for(pages)
    check_sources(db, request, project_id, specs)
    deck = DeckSpec(title=presentation.title, pages=specs)
    try:
        encode_deck(deck)
    except RenderInputTooLarge as exc:
        raise HTTPException(422, str(exc)) from exc
    old_key = presentation.ppt_path
    key = object_key(f"projects/{project_id}/presentations/{document_id}", "pptx")
    presentation.status = "RENDERING"
    db.flush()
    try:
        output = request.app.state.renderer.render(deck)
        validate_pptx(output)
        request.app.state.store.put(key, BytesIO(output), len(output))
    except Exception as exc:
        logger.exception("Presentation rendering failed")
        presentation.status = "FAILED"
        presentation.ppt_path = None
        db.commit()
        cleanup(request, key)
        cleanup(request, old_key)
        raise HTTPException(503, "PPT 导出失败，请检查渲染服务和存储后重试；页面已保留") from exc
    presentation.status = "COMPLETED"
    presentation.ppt_path = key
    try:
        db.commit()
    except Exception:
        db.rollback()
        cleanup(request, key)
        raise
    cleanup(request, old_key)
    return RenderView(
        status=presentation.status,
        download_url=f"/api/ppt/documents/{document_id}/download?projectId={project_id}",
    )


@router.get("/{document_id}/download")
def download(document_id: int, project_id: ProjectId, db: DB, request: Request):
    presentation = presentation_or_404(db, document_id, project_id)
    if presentation.status != "COMPLETED" or not presentation.ppt_path:
        raise HTTPException(409, "当前内容尚未导出，请先生成 PPTX")
    check_sources(db, request, project_id, specs_for(pages_for(db, presentation)))
    try:
        output = request.app.state.store.get(presentation.ppt_path)
    except Exception as exc:
        raise HTTPException(503, "导出文件暂不可用，请重新生成 PPTX") from exc
    return Response(
        output,
        media_type=PPTX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="slidemind-{document_id}.pptx"',
            "Cache-Control": "no-store",
        },
    )
