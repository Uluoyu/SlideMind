"""Optional acceptance against configured model services; never substitutes model output."""

import os

import pytest

from slidemind_api.config import Settings
from slidemind_rag.rank import Candidate, rank_candidates
from slidemind_rag.remote import HttpEmbedder, HttpReranker

pytestmark = pytest.mark.skipif(
    os.environ.get("SLIDEMIND_TEST_REMOTE_MODELS") != "1",
    reason="Set SLIDEMIND_TEST_REMOTE_MODELS=1 for actual model services",
)

CASES = [
    ("第二季度收入增长情况", "第二季度营业收入三千万元，同比增长百分之二十。"),
    ("改善用户售后体验", "客户投诉集中在售后等待时间，应缩短响应时间。"),
    ("订单任务如何异步执行", "系统采用微服务架构，通过消息队列异步处理订单。"),
    ("新版软件有什么功能", "下一版本增加离线编辑和团队协作能力。"),
    ("海外业务优先进入哪", "海外市场优先拓展东南亚，通过当地合作伙伴营销。"),
    ("研发部门招募哪些岗位", "研发团队招聘三位后端工程师和两位设计师。"),
    ("客户拖欠款项怎么处理", "应收账款逾期增加，需要加强催收并控制现金流。"),
    ("如何保护机密资料", "敏感文件必须加密存储，并按角色控制访问权限。"),
    ("原料供货延迟怎么办", "核心原材料交付延迟，建议增加备用供应商。"),
    ("办公场所怎样减少能源消耗", "办公楼用电量降低百分之十五，并更换高效照明。"),
]


def test_remote_embedding_chinese_recall_and_no_match():
    settings = Settings()
    model = HttpEmbedder(
        settings.embedding_url,
        settings.embedding_model,
        settings.embedding_dimensions,
        query_instruction=settings.embedding_query_instruction,
        api_key=settings.embedding_api_key.get_secret_value(),
    )
    try:
        vectors = model.embed([document for _, document in CASES])
        candidates = [Candidate(index, case[1], vectors[index]) for index, case in enumerate(CASES)]
        matched = 0
        for index, (query, _) in enumerate(CASES):
            hits = rank_candidates(
                query,
                model.embed_query(query),
                candidates,
                min_similarity=settings.retrieval_min_similarity,
            )
            matched += index in [hit.chunk_id for hit in hits]
        assert matched >= 8, f"Recall@5={matched}/10"
        assert (
            rank_candidates(
                "草莓蛋糕烘焙配方",
                model.embed_query("草莓蛋糕烘焙配方"),
                candidates,
                min_similarity=settings.retrieval_min_similarity,
            )
            == []
        )
        print(f"Actual embedding Recall@5={matched}/10; dimensions={model.dimensions}")
    finally:
        model.close()


def test_remote_reranker_ranks_actual_evidence_first():
    settings = Settings()
    if not settings.reranker_url:
        pytest.skip("Reranker endpoint not configured")
    model = HttpReranker(
        settings.reranker_url,
        settings.reranker_model,
        input_format=settings.reranker_input_format,
        api_key=settings.reranker_api_key.get_secret_value(),
    )
    try:
        results = model.rerank("订单任务如何异步执行", ["草莓蛋糕制作配方", CASES[2][1]])
        assert results and results[0][0] == 1
        print(f"Actual reranker evidence score={results[0][1]}")
    finally:
        model.close()


@pytest.mark.parametrize(
    "storage_backend",
    [
        "local",
        pytest.param(
            "minio",
            marks=pytest.mark.skipif(
                os.environ.get("SLIDEMIND_TEST_MINIO") != "1",
                reason="Set SLIDEMIND_TEST_MINIO=1 to write and clean up a test object",
            ),
        ),
    ],
)
def test_pdf_upload_to_remote_rag_keeps_real_page_and_excerpt(
    tmp_path, monkeypatch, storage_backend
):
    import pymupdf
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient

    from slidemind_api.main import create_app
    from slidemind_api.models import Document

    database_url = f"sqlite:///{tmp_path / 'pdf-rag.db'}"
    monkeypatch.setenv("SLIDEMIND_DATABASE_URL", database_url)
    command.upgrade(Config("alembic.ini"), "head")
    settings = Settings(
        database_url=database_url,
        storage_root=tmp_path / "storage",
        storage_backend=storage_backend,
        ingestion_enabled=False,
    )
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 60), "Project evidence")
        pdf.new_page().insert_text((50, 60), "AI违规检测准确率达到百分之九十。", fontname="china-s")
        content = pdf.tobytes()
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/ppt/projects", json={"name": "PDF来源验收"}).json()["id"]
        base = f"/api/ppt/projects/{project}"
        uploaded = client.post(f"{base}/documents", files={"file": ("测试报告.pdf", content)})
        assert uploaded.status_code == 201, uploaded.text
        document = uploaded.json()
        with client.app.state.sessions() as db:
            key = db.get(Document, document["id"]).storage_path
        try:
            assert client.app.state.store.get(key) == content
            assert client.app.state.ingestor.process_next()
            assert client.get(f"{base}/documents").json()[0]["status"] == "READY"
            response = client.post(f"{base}/search", json={"query": "AI违规检测准确率是多少"})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["mode"] == "hybrid-rerank" and result["warning"] is None
            hit = result["hits"][0]
            assert hit["source"]["document_id"] == document["id"]
            assert hit["source"]["page_no"] == 2
            assert "百分之九十" in hit["source"]["excerpt"]
            source = client.get(f"{base}/documents/{document['id']}/chunks/{hit['chunkId']}")
            assert source.json()["pageNo"] == 2
            assert source.json()["content"] == hit["source"]["excerpt"]
        finally:
            # Delete only the random object just uploaded by this isolated test.
            client.app.state.store.delete(key)


@pytest.mark.skipif(
    Settings().planner_provider != "http", reason="Configure SLIDEMIND_PLANNER_* for the model"
)
def test_remote_planner_outline_follows_request_and_feedback():
    from slidemind_agent.planner import Evidence, ModelPlanner, PlanningRequest
    from slidemind_rag.remote import HttpChatModel

    settings = Settings()
    chat = HttpChatModel(
        settings.planner_url,
        settings.planner_model,
        max_tokens=settings.planner_max_tokens,
        temperature=settings.planner_temperature,
        timeout=settings.planner_timeout_seconds,
        api_key=settings.planner_api_key.get_secret_value(),
    )
    evidence = [
        Evidence(101, "方案.docx", "第 3 页", "人员轨迹系统定位精度达到 1 米，覆盖 8 个洁净室。")
    ]
    request = PlanningRequest(
        title="洁净室人员管理项目汇报",
        page_count=6,
        audience="公司领导",
        style="专业、简洁",
        requirements=["突出人员轨迹", "突出 AI 违规检测"],
        evidence=evidence,
    )
    try:
        planner = ModelPlanner(chat)
        pages = planner.plan(request)
        assert [p.page_no for p in pages] == list(range(1, 7))
        assert all(set(p.source_ids) <= {101} for p in pages)
        assert any("轨迹" in p.title + p.purpose for p in pages)
        revised = planner.plan(
            PlanningRequest(
                **{**request.__dict__, "feedback": "删除最后一页", "current_pages": pages}
            )
        )
        assert len(revised) == 5
    finally:
        chat.close()
