import math
import os
import sys
from types import SimpleNamespace

import pytest


def test_validate_vectors_normalizes_without_mutating_input():
    from slidemind_rag.embeddings import validate_vectors

    original = [[3, 4], [0, -2]]
    assert validate_vectors(original, expected_count=2, dimensions=2) == [[0.6, 0.8], [0.0, -1.0]]
    assert original == [[3, 4], [0, -2]]


@pytest.mark.parametrize(
    "vectors, count, dimensions",
    [
        ([[1, 0]], 2, 2),
        ([[1, 0], [1]], 2, 2),
        ([[float("nan"), 1]], 1, 2),
        ([[float("inf"), 1]], 1, 2),
        ([[0, 0]], 1, 2),
        ([["invalid", 1]], 1, 2),
        ([[True, 1]], 1, 2),
        ([None], 1, 2),
        ([], 0, 0),
    ],
)
def test_validate_vectors_rejects_malformed_batches(vectors, count, dimensions):
    from slidemind_rag.embeddings import validate_vectors

    with pytest.raises(ValueError):
        validate_vectors(vectors, expected_count=count, dimensions=dimensions)


def test_embedder_is_lazy_normalizes_and_uses_query_embedding(monkeypatch, tmp_path):
    from slidemind_rag.embeddings import FastEmbedder

    class Model:
        @classmethod
        def get_embedding_size(cls, model_name):
            return 2

        def __init__(self, **kwargs):
            if not model_loading_allowed:
                pytest.fail("Constructing an embedder must not load/download the model")
            assert kwargs["threads"] == 2
            assert kwargs["cache_dir"] == str(tmp_path)

        def embed(self, texts):
            return iter([[3.0, 4.0] for _ in texts])

        def query_embed(self, query):
            return iter([[0.0, -2.0]])

    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=Model))
    model_loading_allowed = False
    embedder = FastEmbedder(cache_dir=tmp_path)
    assert embedder.model_id == "BAAI/bge-small-zh-v1.5"
    assert embedder.dimensions == 2
    assert embedder.embed([]) == []
    model_loading_allowed = True
    assert embedder.embed(["客户需求", "市场规模"]) == [[0.6, 0.8], [0.6, 0.8]]
    assert embedder.embed_query("客户关注什么") == [0.0, -1.0]


def test_embedder_propagates_load_errors_without_fake_vectors(monkeypatch):
    from slidemind_rag.embeddings import FastEmbedder

    class UnavailableModel:
        @classmethod
        def get_embedding_size(cls, model_name):
            return 2

        def __init__(self, **kwargs):
            raise RuntimeError("model unavailable")

    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=UnavailableModel))
    with pytest.raises(RuntimeError, match="model unavailable"):
        FastEmbedder().embed(["业务文档"])


def test_hybrid_rank_combines_hand_derived_cosine_and_keyword_scores():
    from slidemind_rag.rank import Candidate, rank_candidates

    hits = rank_candidates(
        "revenue",
        [1, 0],
        [Candidate(1, "sales totals", [1, 0]), Candidate(2, "Revenue increased", [3, 4])],
    )
    assert [hit.chunk_id for hit in hits] == [1, 2]
    assert hits[0].similarity == pytest.approx(1.0)
    assert hits[0].keyword_score == 0
    assert hits[1].similarity == pytest.approx(0.6)
    assert hits[1].keyword_score == 1
    assert 0.6 < hits[1].score < hits[0].score


def test_keywords_rescue_chinese_terms_and_case_insensitive_identifiers():
    from slidemind_rag.rank import Candidate, rank_candidates

    candidates = [
        Candidate(1, "客户流失主要来自服务响应缓慢。", [0, 1]),
        Candidate(2, "产品 AX-900 支持每小时处理 1500 件。", None),
        Candidate(3, "下午去公园散步。", [0, 1]),
    ]
    assert [hit.chunk_id for hit in rank_candidates("客户流失原因", [1, 0], candidates)] == [1]
    hits = rank_candidates("ax-900 的处理能力", [1, 0], candidates)
    assert [hit.chunk_id for hit in hits] == [2]
    assert hits[0].similarity is None
    assert rank_candidates("AX-90", [1, 0], candidates) == []


def test_rank_drops_unrelated_content_and_common_question_words():
    from slidemind_rag.rank import Candidate, rank_candidates

    candidates = [
        Candidate(1, "如何制作红烧肉？", [0, 1]),
        Candidate(2, "这个是什么品种的猫？", [-1, 0]),
        Candidate(3, "主要原因是天气炎热。", [0, 1]),
    ]
    assert rank_candidates("如何提升客户满意度是什么主要原因", [1, 0], candidates) == []
    assert rank_candidates("太阳发生核聚变的条件", [1, 0], candidates) == []


@pytest.mark.parametrize("vector", [[0, 0], [math.nan, 1], [math.inf, 1], [1], [True, 0]])
def test_rank_skips_corrupt_stored_vectors_even_with_matching_keywords(vector):
    from slidemind_rag.rank import Candidate, rank_candidates

    assert rank_candidates("客户满意度", [1, 0], [Candidate(1, "客户满意度", vector)]) == []


def test_rank_supports_database_cosines_limits_and_stable_ties():
    from slidemind_rag.rank import Candidate, rank_candidates

    candidates = [
        Candidate(3, "topic", None, similarity=0.8),
        Candidate(1, "topic", None, similarity=0.8),
        Candidate(2, "topic", None, similarity=0.7),
        Candidate(4, "topic", None, similarity=math.nan),
    ]
    hits = rank_candidates("semantic paraphrase", [1, 0], candidates, top_k=2)
    assert [hit.chunk_id for hit in hits] == [1, 3]
    assert hits[0].similarity == 0.8
    assert rank_candidates(" ", [1, 0], candidates) == []
    assert rank_candidates("semantic paraphrase", [1, 0], candidates, top_k=0) == []
    with pytest.raises(ValueError):
        rank_candidates("topic", [math.nan, 0], candidates)


@pytest.mark.skipif(
    os.environ.get("SLIDEMIND_TEST_REAL_EMBEDDINGS") != "1",
    reason="Set SLIDEMIND_TEST_REAL_EMBEDDINGS=1 to download/run the local Chinese model",
)
def test_real_chinese_model_retrieval_quality():
    from slidemind_rag.embeddings import FastEmbedder
    from slidemind_rag.rank import Candidate, rank_candidates

    documents = [
        "销售业绩：第二季度营收达到三千万元，同比增长百分之二十。",
        "客户服务：用户投诉最多的问题是售后等待时间过长，应缩短响应时间。",
        "技术架构：系统采用微服务，通过消息队列异步处理订单。",
        "产品规划：下一版本增加离线编辑和团队协作能力。",
        "市场策略：优先拓展东南亚，通过当地合作伙伴开展渠道营销。",
        "人才招聘：研发团队计划招聘三位后端工程师和两位设计师。",
        "财务风险：应收账款逾期增加，需要加强催收并控制现金流。",
        "信息安全：所有敏感文件必须加密存储，并按角色控制访问权限。",
        "供应链：核心原材料交付延迟，建议增加备用供应商。",
        "节能目标：明年办公楼用电量降低百分之十五，并更换高效照明。",
    ]
    queries = [
        "第二季度的收入增长情况如何？",
        "怎样改善用户的售后体验？",
        "订单任务使用什么方式异步执行？",
        "新版软件将提供哪些功能？",
        "海外业务优先进入哪个地区？",
        "今年研发部门需要招募哪些岗位？",
        "怎样处理客户拖欠款项的问题？",
        "机密资料应该怎样保护？",
        "原料供货不及时有什么解决办法？",
        "办公场所明年如何减少能源消耗？",
    ]
    embedder = FastEmbedder(cache_dir=os.environ.get("SLIDEMIND_EMBEDDING_CACHE_DIR"))
    vectors = embedder.embed(documents)
    candidates = [Candidate(index, text, vectors[index]) for index, text in enumerate(documents)]
    successes = sum(
        index
        in {hit.chunk_id for hit in rank_candidates(query, embedder.embed_query(query), candidates)}
        for index, query in enumerate(queries)
    )
    assert successes >= 8
    assert (
        rank_candidates(
            "怎样烘焙草莓奶油蛋糕？", embedder.embed_query("怎样烘焙草莓奶油蛋糕？"), candidates
        )
        == []
    )
