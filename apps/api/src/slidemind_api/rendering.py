"""Transport boundary for the independent Node renderer."""

from io import BytesIO
from typing import Protocol
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

from slidemind_schemas.page import DeckSpec

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
MAX_RENDER_BYTES = 50 * 1024 * 1024
MAX_REQUEST_BYTES = 2 * 1024 * 1024


class RenderInputTooLarge(ValueError):
    pass


def encode_deck(deck: DeckSpec) -> bytes:
    payload = deck.model_dump_json().encode("utf-8")
    if len(payload) > MAX_REQUEST_BYTES:
        raise RenderInputTooLarge("页面与引用总量超过 2 MiB，请缩短摘录或减少引用后导出")
    return payload


class Renderer(Protocol):
    def render(self, deck: DeckSpec) -> bytes: ...


class HttpRenderer:
    def __init__(self, url: str, timeout: int):
        self.url = url.rstrip("/") + "/render"
        self.timeout = timeout

    def render(self, deck: DeckSpec) -> bytes:
        request = Request(
            self.url,
            data=encode_deck(deck),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Internal service traffic must not inherit a developer's public proxy.
        with build_opener(ProxyHandler({})).open(request, timeout=self.timeout) as response:
            if response.headers.get_content_type() != PPTX_MEDIA_TYPE:
                raise ValueError("Renderer returned an unexpected content type")
            output = response.read(MAX_RENDER_BYTES + 1)
        validate_pptx(output)
        return output


def validate_pptx(output: bytes) -> None:
    if len(output) > MAX_RENDER_BYTES:
        raise ValueError("Rendered presentation exceeds 50 MB")
    try:
        with ZipFile(BytesIO(output)) as archive:
            required = {"[Content_Types].xml", "ppt/presentation.xml"}
            if not required.issubset(archive.namelist()):
                raise ValueError("Renderer did not return a PPTX package")
    except BadZipFile as exc:
        raise ValueError("Renderer did not return a PPTX package") from exc
