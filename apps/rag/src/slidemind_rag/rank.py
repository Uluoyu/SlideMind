"""Small-corpus hybrid ranking after project and security filters are applied."""

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

from slidemind_rag.embeddings import validate_vectors

_WORDS = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*|[\u3400-\u9fff]+")
_CHINESE = re.compile(r"[\u3400-\u9fff]+\Z")
_CHINESE_STOPWORDS = re.compile(
    "为什么|如何|什么|怎样|怎么|哪些|是否|主要|原因|我们|这个|一个|进行|相关|"
    "可以|需要|以及|通过|为了|的|了|吗|呢"
)
_ENGLISH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "we", "what", "when", "where", "which", "who", "why", "with",
}


@dataclass(frozen=True)
class Candidate:
    chunk_id: int
    text: str
    embedding: list[float] | None
    similarity: float | None = None


@dataclass(frozen=True)
class RankedHit:
    chunk_id: int
    score: float
    similarity: float | None
    keyword_score: float


def tokenize(text: str) -> set[str]:
    """Retain exact Latin identifiers and Chinese bigrams without a remote tokenizer."""
    terms: set[str] = set()
    for token in _WORDS.findall(_CHINESE_STOPWORDS.sub(" ", text.casefold())):
        if _CHINESE.fullmatch(token):
            # Single-character overlaps are too weak to rescue an unrelated result.
            terms.update(token[index:index + 2] for index in range(len(token) - 1))
        elif token not in _ENGLISH_STOPWORDS:
            terms.add(token)
    return terms


def _keyword_match(query_terms: set[str], text: str) -> tuple[float, bool]:
    if not query_terms:
        return 0.0, False
    matched = query_terms & tokenize(text)
    coverage = len(matched) / len(query_terms)
    latin_match = any(not _CHINESE.fullmatch(term) and len(term) >= 2 for term in matched)
    chinese_match = len(matched) >= 2 or (len(query_terms) == 1 and bool(matched))
    return coverage, latin_match or (chinese_match and coverage >= 0.25)


def rank_candidates(
    query: str,
    query_vector: list[float],
    candidates: Iterable[Candidate],
    top_k: int = 5,
    min_similarity: float = 0.5,
) -> list[RankedHit]:
    """Fuse cosine (75%) with query-token coverage (25%) and filter weak evidence.

    A meaningful keyword match can recover an exact identifier or phrase below the
    semantic threshold. A supplied cosine supports pgvector ranking; otherwise cosine
    is computed locally. Corrupt stored vectors/scores are excluded, never scored as
    successful embeddings. Scores are ordering signals, not calibrated confidence.
    """
    if not query.strip() or top_k <= 0:
        return []
    if not math.isfinite(min_similarity) or not -1 <= min_similarity <= 1:
        raise ValueError("Minimum cosine similarity must be between -1 and 1")
    dimensions = len(query_vector)
    normalized_query = validate_vectors([query_vector], 1, dimensions)[0]
    query_terms = tokenize(query)
    hits: list[RankedHit] = []
    for candidate in candidates:
        similarity = candidate.similarity
        if candidate.embedding is not None:
            try:
                normalized = validate_vectors([candidate.embedding], 1, dimensions)[0]
            except ValueError:
                continue
            if similarity is None:
                similarity = math.fsum(
                    left * right for left, right in zip(normalized_query, normalized, strict=True)
                )
                similarity = max(-1.0, min(1.0, similarity))
        if similarity is not None and (
            not math.isfinite(similarity) or not -1 <= similarity <= 1
        ):
            continue
        keyword_score, meaningful_match = _keyword_match(query_terms, candidate.text)
        if not meaningful_match and (similarity is None or similarity < min_similarity):
            continue
        score = 0.75 * max(0.0, similarity or 0.0) + 0.25 * keyword_score
        hits.append(RankedHit(candidate.chunk_id, score, similarity, keyword_score))
    return sorted(hits, key=lambda hit: (-hit.score, hit.chunk_id))[:top_k]
