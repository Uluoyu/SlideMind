"""Document text extraction and source-preserving chunking."""

from slidemind_parser.chunking import chunk_sections
from slidemind_parser.contracts import DocumentParser, ParsedSection
from slidemind_parser.parsers import parse_document
from slidemind_parser.template_design import extract_template_design

__all__ = [
    "DocumentParser",
    "ParsedSection",
    "chunk_sections",
    "extract_template_design",
    "parse_document",
]
