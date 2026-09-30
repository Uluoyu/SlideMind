"""Deterministic character windows that never cross a source section boundary."""

from collections.abc import Iterable

from slidemind_parser.contracts import ParsedSection


def chunk_sections(
    sections: Iterable[ParsedSection], max_chars: int = 900, overlap: int = 100
) -> list[ParsedSection]:
    """Split sections while preserving source metadata and exact text overlap.

    section_index and chunk_index are zero-based. char_start/char_end describe a
    half-open Python character range within the original section (not bytes).
    """
    if max_chars <= 0 or overlap < 0 or overlap >= max_chars:
        raise ValueError("分块大小必须大于 0，重叠字符数必须大于等于 0 且小于分块大小。")
    chunks = []
    for section_index, section in enumerate(sections):
        if not section.text.strip():
            continue
        start = 0
        chunk_index = 0
        while start < len(section.text):
            end = min(start + max_chars, len(section.text))
            chunks.append(ParsedSection(
                section.text[start:end],
                page_no=section.page_no,
                metadata={
                    **section.metadata,
                    "section_index": section_index,
                    "chunk_index": chunk_index,
                    "char_start": start,
                    "char_end": end,
                },
            ))
            if end == len(section.text):
                break
            start = end - overlap
            chunk_index += 1
    return chunks
