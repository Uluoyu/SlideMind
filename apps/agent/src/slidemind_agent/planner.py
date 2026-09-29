from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlanningRequest:
    title: str
    page_count: int
    audience: str
    style: str
    requirements: list[str]


@dataclass(frozen=True)
class PlannedPage:
    page_no: int
    title: str
    purpose: str


class Planner(Protocol):
    def plan(self, request: PlanningRequest) -> list[PlannedPage]: ...


class LocalPlanner:
    """Deterministic starter outline. Never claims to have read project documents."""

    def plan(self, request: PlanningRequest) -> list[PlannedPage]:
        topics = ["项目背景", "业务痛点", "整体方案", "实施路径", "项目成果", "总结与展望"]
        pages = []
        for index in range(request.page_count):
            if index == 0:
                title = request.title[:80]
                purpose = "介绍汇报主题与目标"
            elif index == request.page_count - 1:
                title, purpose = "总结与下一步", "总结价值，列出需要补充或确认的后续计划"
            else:
                topic_index = index - 1
                title = (
                    request.requirements[topic_index][:80]
                    if topic_index < len(request.requirements)
                    else topics[topic_index % len(topics)]
                )
                purpose = "请结合项目资料补充本页核心观点与证据"
            pages.append(PlannedPage(index + 1, title or "待完善主题", purpose))
        return pages
