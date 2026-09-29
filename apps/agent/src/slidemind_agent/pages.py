"""Local scaffolding adapter; does not claim to retrieve or infer project facts."""

from slidemind_agent.planner import PlannedPage
from slidemind_schemas.page import PageSpec, TextBlock


def scaffold_page(page: PlannedPage, page_count: int) -> PageSpec:
    layout = (
        "title"
        if page.page_no == 1
        else ("summary" if page.page_no == page_count else "two_column")
    )
    return PageSpec(
        page_no=page.page_no,
        layout=layout,
        title=page.title,
        subtitle=page.purpose[:160],
        content=[
            TextBlock(
                title="待补充内容",
                text="请根据项目资料填写本页内容，并核实数据与来源。",
            )
        ],
    )
