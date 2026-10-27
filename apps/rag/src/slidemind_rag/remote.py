"""HTTP model adapters. Service addresses and credentials are server configuration."""

import math
from numbers import Real

import httpx

from slidemind_rag.embeddings import validate_vectors


class _RemoteModel:
    def __init__(self, endpoint, *, timeout=30, api_key="", client=None):
        self.endpoint = endpoint
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 5)),
            trust_env=False,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    def _post(self, body):
        response = self.client.post(self.endpoint, json=body)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Model response must be an object")
        return payload

    def close(self):
        if self._owns_client:
            self.client.close()


class HttpEmbedder(_RemoteModel):
    def __init__(
        self,
        endpoint,
        model,
        dimensions,
        *,
        query_instruction="",
        revision="",
        timeout=30,
        api_key="",
        client=None,
    ):
        super().__init__(endpoint, timeout=timeout, api_key=api_key, client=client)
        self.model = model
        self.dimensions = dimensions
        self.model_id = f"http:{model}" + (f":{revision}" if revision else "")
        self.query_instruction = query_instruction

    def embed(self, texts):
        if not texts:
            return []
        payload = self._post({"model": self.model, "input": texts, "encoding_format": "float"})
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise ValueError("Embedding response count does not match input")
        ordered = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid embedding entry")
            index = row.get("index")
            if type(index) is not int or not 0 <= index < len(texts) or index in ordered:
                raise ValueError("Invalid or duplicated embedding index")
            ordered[index] = row.get("embedding")
        return validate_vectors(
            [ordered[i] for i in range(len(texts))], len(texts), self.dimensions
        )

    def embed_query(self, query):
        if self.query_instruction:
            query = f"Instruct: {self.query_instruction}\nQuery: {query}"
        return self.embed([query])[0]


class ChatTruncated(ValueError):
    truncated = True


class HttpChatModel(_RemoteModel):
    """OpenAI-compatible /v1/chat/completions; returns the first choice's text."""

    def __init__(
        self,
        endpoint,
        model,
        *,
        max_tokens=4096,
        temperature=0.3,
        timeout=120,
        api_key="",
        client=None,
    ):
        super().__init__(endpoint, timeout=timeout, api_key=api_key, client=client)
        self.model = model
        self.max_tokens, self.temperature = max_tokens, temperature

    def complete(self, messages):
        body = {
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        if self.model:
            body["model"] = self.model
        choices = self._post(body).get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("Chat response must contain choices")
        if choices[0].get("finish_reason") == "length":
            raise ChatTruncated("Chat response stopped at max_tokens")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Chat response content is empty")
        return content


class HttpReranker(_RemoteModel):
    def __init__(
        self, endpoint, model="", *, input_format="plain", timeout=15, api_key="", client=None
    ):
        super().__init__(endpoint, timeout=timeout, api_key=api_key, client=client)
        self.model = model
        if input_format not in ("plain", "qwen3"):
            raise ValueError("Unsupported reranker input format")
        self.input_format = input_format

    def rerank(self, query, documents):
        if not documents:
            return []
        if self.input_format == "qwen3":
            # Qwen/Qwen3-Reranker-0.6B judgement format for vLLM paired scoring.
            # The service used here concatenates query/document without a chat template.
            prefix = (
                "<|im_start|>system\nJudge whether the Document meets the requirements based "
                "on the Query and the Instruct provided. Note that the answer can only be "
                '"yes" or "no".<|im_end|>\n<|im_start|>user\n'
            )
            query = (
                prefix + "<Instruct>: Given a query, retrieve relevant passages that answer "
                f"the query\n<Query>: {query}\n<Document>: "
            )
            suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
            documents = [document + suffix for document in documents]
        body = {"query": query, "documents": documents, "top_n": len(documents)}
        if self.model:
            body["model"] = self.model
        payload = self._post(body)
        rows = payload.get("results", payload.get("data"))
        if not isinstance(rows, list):
            raise ValueError("Reranker response must contain results")
        results, seen = [], set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid reranker entry")
            index, score = row.get("index"), row.get("relevance_score")
            if (
                type(index) is not int
                or not 0 <= index < len(documents)
                or index in seen
                or isinstance(score, bool)
                or not isinstance(score, Real)
                or not math.isfinite(score)
            ):
                raise ValueError("Invalid reranker index or score")
            seen.add(index)
            results.append((index, float(score)))
        return sorted(results, key=lambda item: (-item[1], item[0]))
