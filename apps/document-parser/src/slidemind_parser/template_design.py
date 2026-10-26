"""Company-template theme extraction into a TemplateDesign for rendering."""

import posixpath
import re
from io import BytesIO
from typing import BinaryIO
from xml.etree import ElementTree
from zipfile import ZipFile

from slidemind_parser.parsers import MAX_INPUT_BYTES, _DocumentError, _validate_archive
from slidemind_schemas.design import MAX_SLIDE_EMU, MIN_SLIDE_EMU, LayoutInfo, TemplateDesign

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NAMESPACES = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
HEX_VALUE = re.compile(r"^[0-9A-Fa-f]{6}$")
THEME_PART = re.compile(r"^ppt/theme/theme(\d+)\.xml$")
LAYOUT_PART = re.compile(r"^ppt/slideLayouts/slideLayout(\d+)\.xml$")
COLOR_SLOTS = (
    "dk1",
    "lt1",
    "dk2",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
)
REQUIRED_SLOTS = ("dk1", "lt1", "accent1")


def _slide_size(archive: ZipFile) -> tuple[int, int]:
    if "ppt/presentation.xml" not in archive.namelist():
        raise _DocumentError("模板缺少 presentation.xml，无法读取幻灯片尺寸。")
    root = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
    size = root.find(".//p:sldSz", NAMESPACES)
    try:
        width, height = int(size.get("cx")), int(size.get("cy"))
    except (AttributeError, TypeError, ValueError) as error:
        raise _DocumentError("模板缺少有效的幻灯片尺寸。") from error
    if width <= 0 or height <= 0:
        raise _DocumentError("模板缺少有效的幻灯片尺寸。")
    if not all(MIN_SLIDE_EMU <= value <= MAX_SLIDE_EMU for value in (width, height)):
        raise _DocumentError("模板页面尺寸超出支持范围（5–56 英寸）。")
    return width, height


def _theme_part(members: list[str]) -> str:
    if "ppt/theme/theme1.xml" in members:
        return "ppt/theme/theme1.xml"
    numbered = sorted(
        (name for name in members if THEME_PART.match(name)),
        key=lambda name: int(THEME_PART.match(name).group(1)),
    )
    if not numbered:
        raise _DocumentError("模板缺少主题文件（theme1.xml）。")
    return numbered[0]


def _slot_color(slot) -> str | None:
    if slot is None:
        return None
    srgb = slot.find("a:srgbClr", NAMESPACES)
    if srgb is not None and HEX_VALUE.match(srgb.get("val") or ""):
        return f"#{srgb.get('val').upper()}"
    system = slot.find("a:sysClr", NAMESPACES)
    if system is not None and HEX_VALUE.match(system.get("lastClr") or ""):
        return f"#{system.get('lastClr').upper()}"
    return None


def _colors(theme) -> dict[str, str | None]:
    scheme = theme.find(".//a:clrScheme", NAMESPACES)
    slots = {slot: None for slot in COLOR_SLOTS}
    if scheme is not None:
        for slot in COLOR_SLOTS:
            slots[slot] = _slot_color(scheme.find(f"a:{slot}", NAMESPACES))
    if any(slots[slot] is None for slot in REQUIRED_SLOTS):
        raise _DocumentError("模板缺少必需的主题颜色（主色/文字色/背景色），无法生成设计系统。")
    return slots


def _typeface(font) -> str | None:
    if font is None:
        return None
    for tag in ("a:ea", "a:latin"):
        for node in font.findall(tag, NAMESPACES):
            typeface = (node.get("typeface") or "").strip()
            if typeface:
                return typeface
    return None


def _fonts(theme) -> dict[str, str]:
    major = theme.find(".//a:majorFont", NAMESPACES)
    minor = theme.find(".//a:minorFont", NAMESPACES)
    if major is None or minor is None:
        raise _DocumentError("模板缺少主题字体方案。")
    fonts = {"title_font": _typeface(major), "body_font": _typeface(minor)}
    if fonts["title_font"] is None or fonts["body_font"] is None:
        raise _DocumentError("模板未声明可用的标题或正文字体。")
    return fonts


def _relationships(archive: ZipFile, part: str) -> dict[str, str]:
    """Map rId → archive member for a part's .rels; empty when the part has no relationships."""
    folder, name = posixpath.split(part)
    rels = posixpath.join(folder, "_rels", f"{name}.rels")
    if rels not in archive.namelist():
        return {}
    targets = {}
    for rel in ElementTree.fromstring(archive.read(rels)).findall("rel:Relationship", NAMESPACES):
        target = rel.get("Target") or ""
        if rel.get("TargetMode") == "External" or not target:
            continue
        resolved = target.lstrip("/") if target.startswith("/") else posixpath.join(folder, target)
        targets[rel.get("Id")] = posixpath.normpath(resolved)
    return targets


def _primary_master_layouts(archive: ZipFile) -> list[str] | None:
    """Layout parts of the first slide master, in its declared order; None when unresolvable.

    Corporate templates often carry dozens of duplicate masters (slides pasted with "keep
    source formatting"), so counting every slideLayoutN part overstates the real layout set.
    """
    presentation = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
    first = presentation.find("p:sldMasterIdLst/p:sldMasterId", NAMESPACES)
    if first is None:
        return None
    master = _relationships(archive, "ppt/presentation.xml").get(first.get(f"{{{R_NS}}}id"))
    if master is None or master not in archive.namelist():
        return None
    master_rels = _relationships(archive, master)
    root = ElementTree.fromstring(archive.read(master))
    members = set(archive.namelist())
    layouts = [
        master_rels.get(entry.get(f"{{{R_NS}}}id"))
        for entry in root.findall("p:sldLayoutIdLst/p:sldLayoutId", NAMESPACES)
    ]
    layouts = [part for part in layouts if part in members]
    return layouts or None


def _layouts(archive: ZipFile) -> list[LayoutInfo]:
    parts = _primary_master_layouts(archive) or sorted(
        (name for name in archive.namelist() if LAYOUT_PART.match(name)),
        key=lambda name: int(LAYOUT_PART.match(name).group(1)),
    )
    if not parts:
        raise _DocumentError("模板缺少幻灯片版式，文件可能已损坏。")
    if len(parts) > 100:
        raise _DocumentError("模板版式数量超过限制。")
    layouts = []
    for name in parts:
        root = ElementTree.fromstring(archive.read(name))
        slide = root.find("p:cSld", NAMESPACES)
        layout_name = (slide.get("name") if slide is not None else None) or name.rsplit("/", 1)[-1][
            :-4
        ]
        layouts.append(
            LayoutInfo(name=layout_name[:100], type=(root.get("type") or "unknown")[:32])
        )
    return layouts


def extract_template_design(stream: BinaryIO) -> TemplateDesign:
    """Read theme facts (geometry, colors, fonts, layouts) straight from the OOXML parts.

    No python-pptx: the extractor only needs three small XML parts per template. Optional
    slots absent from the theme stay None; nothing is fabricated or defaulted.
    """
    try:
        data = stream.read(MAX_INPUT_BYTES + 1)
        if not data:
            raise _DocumentError("模板文件为空，请上传有效的 PPTX 模板。")
        if len(data) > MAX_INPUT_BYTES:
            raise _DocumentError("模板文件大小超过解析限制。")
        _validate_archive(data)
        with ZipFile(BytesIO(data)) as archive:
            width, height = _slide_size(archive)
            theme = ElementTree.fromstring(archive.read(_theme_part(archive.namelist())))
            design = {"slide_width_emu": width, "slide_height_emu": height}
            design.update(_colors(theme))
            design.update(_fonts(theme))
            design["layouts"] = _layouts(archive)
        return TemplateDesign(**design)
    except _DocumentError:
        raise
    except Exception as error:
        raise _DocumentError(
            "PPTX 模板损坏或格式不匹配，请确认文件能正常打开后重新上传。"
        ) from error
