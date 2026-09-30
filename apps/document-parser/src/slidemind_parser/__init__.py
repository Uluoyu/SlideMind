"""Document text extraction and source-preserving chunking."""

from slidemind_parser.chunking import chunk_sections
from slidemind_parser.contracts import DocumentParser, ParsedSection
from slidemind_parser.parsers import parse_document

__all__ = ["DocumentParser", "ParsedSection", "chunk_sections", "parse_document"]
