import json

import httpx
import pytest


def test_http_embeddings_preserve_input_order_and_normalize():
    from slidemind_rag.remote import HttpEmbedder

    def respond(request):
        body = json.loads(request.content)
        assert body["model"] == "qwen3_embedding"
        assert body["input"] == ["甲资料", "乙资料"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 4, 0]},
                    {"index": 0, "embedding": [3, 0, 0]},
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = HttpEmbedder("http://model/v1/embeddings", "qwen3_embedding", 3, client=client)
        assert model.embed(["甲资料", "乙资料"]) == [[1, 0, 0], [0, 1, 0]]


def test_http_embedding_query_instruction_is_not_added_to_documents():
    from slidemind_rag.remote import HttpEmbedder

    def respond(request):
        inputs = json.loads(request.content)["input"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 0,
                        "embedding": [1, 0]
                        if inputs == ["Instruct: 找到项目证据\nQuery: 系统架构"]
                        else [0, 1],
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = HttpEmbedder(
            "http://model/v1/embeddings",
            "qwen3",
            2,
            query_instruction="找到项目证据",
            client=client,
        )
        assert model.embed_query("系统架构") == [1, 0]
        assert model.embed(["系统架构"]) == [[0, 1]]


@pytest.mark.parametrize(
    "payload",
    [
        {"data": []},
        {"data": [{"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [1, 0]}]},
        {"data": [{"index": -1, "embedding": [1, 0]}]},
        {"data": [{"index": 0, "embedding": [1]}]},
        {"data": [{"index": 0, "embedding": [0, 0]}]},
    ],
)
def test_http_embedding_rejects_incomplete_or_malformed_results(payload):
    from slidemind_rag.remote import HttpEmbedder

    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as c:
        model = HttpEmbedder("http://model/v1/embeddings", "qwen3", 2, client=c)
        with pytest.raises(ValueError):
            model.embed(["原文"])


def test_reranker_validates_indexes_and_returns_sorted_scores():
    from slidemind_rag.remote import HttpReranker

    def respond(request):
        body = json.loads(request.content)
        assert body["query"] == "系统架构"
        assert body["documents"] == ["聚餐", "微服务架构"]
        assert body["top_n"] == 2
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 0, "relevance_score": 0.01},
                    {"index": 1, "relevance_score": 0.97},
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        reranker = HttpReranker("http://model/v1/rerank", client=client)
        assert reranker.rerank("系统架构", ["聚餐", "微服务架构"]) == [(1, 0.97), (0, 0.01)]


def test_qwen3_reranker_formats_paired_input_with_judgement_prompt():
    from slidemind_rag.remote import HttpReranker

    def respond(request):
        body = json.loads(request.content)
        assert body["query"].startswith("<|im_start|>system\nJudge whether")
        assert "<Query>: 订单怎么处理\n<Document>: " in body["query"]
        assert body["documents"][0].startswith("消息队列<|im_end|>")
        assert body["documents"][0].endswith("<think>\n\n</think>\n\n")
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.99}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        reranker = HttpReranker("http://model/rerank", input_format="qwen3", client=client)
        assert reranker.rerank("订单怎么处理", ["消息队列"]) == [(0, 0.99)]


@pytest.mark.parametrize(
    "results",
    [
        [{"index": 2, "relevance_score": 0.7}],
        [{"index": 0, "relevance_score": "0.7"}],
        [{"index": 0, "relevance_score": 0.7}, {"index": 0, "relevance_score": 0.5}],
    ],
)
def test_reranker_rejects_bad_indexes_or_scores(results):
    from slidemind_rag.remote import HttpReranker

    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": results}))
    ) as client:
        with pytest.raises(ValueError):
            HttpReranker("http://model/v1/rerank", client=client).rerank("查询", ["原文"])


def test_remote_http_failure_is_not_returned_as_a_valid_empty_result():
    from slidemind_rag.remote import HttpEmbedder, HttpReranker

    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(502))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            HttpEmbedder("http://model/embed", "qwen3", 2, client=client).embed(["原文"])
        with pytest.raises(httpx.HTTPStatusError):
            HttpReranker("http://model/rerank", client=client).rerank("查询", ["原文"])
