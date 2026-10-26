from io import BytesIO
from zipfile import ZipFile

import pytest

from slidemind_parser.template_design import extract_template_design

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

DEFAULT_COLORS = {
    "dk1": "182A23",
    "lt1": "F5F5F0",
    "accent1": "315C4E",
    "dk2": "42575B",
    "lt2": "FBFBFC",
    "accent2": "8AA79B",
}
DEFAULT_FONTS = (("微软雅黑", "Arial"), ("", "Calibri"))


def theme_xml(colors=None, fonts=DEFAULT_FONTS):
    colors = DEFAULT_COLORS if colors is None else colors
    slots = []
    for slot, value in colors.items():
        if value is None:
            continue
        if isinstance(value, tuple):
            slots.append(f"<a:{slot}><a:sysClr val='windowText' lastClr='{value[1]}'/></a:{slot}>")
        else:
            slots.append(f"<a:{slot}><a:srgbClr val='{value}'/></a:{slot}>")
    (major_ea, major_latin), (minor_ea, minor_latin) = fonts
    major = f"<a:majorFont><a:latin typeface='{major_latin}'/><a:ea typeface='{major_ea}'/>"
    minor = f"<a:minorFont><a:latin typeface='{minor_latin}'/><a:ea typeface='{minor_ea}'/>"
    return (
        f"<a:theme xmlns:a='{A_NS}' name='Office'><a:themeElements>"
        f"<a:clrScheme name='Custom'>{''.join(slots)}</a:clrScheme>"
        f"<a:fontScheme name='Custom'>{major}</a:majorFont>{minor}</a:minorFont>"
        "</a:fontScheme></a:themeElements></a:theme>"
    )


def layout_xml(name, layout_type):
    type_attr = f" type='{layout_type}'" if layout_type is not None else ""
    named = f"<p:cSld name='{name}'>" if name is not None else "<p:cSld>"
    return f"<p:sldLayout xmlns:p='{P_NS}'{type_attr}>{named}</p:cSld></p:sldLayout>"


def make_template_pptx(
    colors=None,
    fonts=DEFAULT_FONTS,
    layouts=None,
    slide_size=(12192000, 6858000),
    parts=None,
    omit=(),
):
    """Minimal OOXML template; layouts is {number: (name, type)} keyed by slideLayoutN number."""
    if layouts is None:
        # Inserted out of numeric order on purpose: 10 must never sort before 2.
        layouts = {10: ("空白", "blank"), 2: ("标题和内容", "obj"), 1: ("标题幻灯片", "title")}
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        if "ppt/presentation.xml" not in omit:
            archive.writestr(
                "ppt/presentation.xml",
                f"<p:presentation xmlns:p='{P_NS}'><p:sldSz cx='{slide_size[0]}' "
                f"cy='{slide_size[1]}'/></p:presentation>",
            )
        if "ppt/theme/theme1.xml" not in omit:
            archive.writestr("ppt/theme/theme1.xml", theme_xml(colors, fonts))
        for number, (name, layout_type) in layouts.items():
            part = f"ppt/slideLayouts/slideLayout{number}.xml"
            archive.writestr(part, layout_xml(name, layout_type))
        for part, content in (parts or {}).items():
            archive.writestr(part, content)
    return output.getvalue()


def extract(data: bytes):
    return extract_template_design(BytesIO(data))


def test_happy_path_extracts_colors_fonts_and_numeric_layout_order():
    design = extract(make_template_pptx())
    assert design.schema_version == "1.0"
    assert (design.slide_width_emu, design.slide_height_emu) == (12192000, 6858000)
    assert design.dk1 == "#182A23"
    assert design.lt1 == "#F5F5F0"
    assert design.accent1 == "#315C4E"
    assert design.dk2 == "#42575B"
    assert design.lt2 == "#FBFBFC"
    assert design.accent2 == "#8AA79B"
    assert design.accent3 is None
    assert design.title_font == "微软雅黑"
    assert design.body_font == "Calibri"
    assert [(layout.name, layout.type) for layout in design.layouts] == [
        ("标题幻灯片", "title"),
        ("标题和内容", "obj"),
        ("空白", "blank"),
    ]


def test_system_colors_use_last_clr():
    colors = {**DEFAULT_COLORS, "dk1": ("sys", "000000"), "lt1": ("sys", "FFFFFF")}
    design = extract(make_template_pptx(colors=colors))
    assert design.dk1 == "#000000"
    assert design.lt1 == "#FFFFFF"


def test_lowercase_hex_values_are_normalized_to_uppercase():
    design = extract(make_template_pptx(colors={**DEFAULT_COLORS, "accent1": "a1b2c3"}))
    assert design.accent1 == "#A1B2C3"


@pytest.mark.parametrize("slot", ["accent1", "dk1"])
def test_missing_required_color_is_actionable(slot):
    colors = {key: value for key, value in DEFAULT_COLORS.items() if key != slot}
    with pytest.raises(ValueError, match="必需的主题颜色"):
        extract(make_template_pptx(colors=colors))


def test_missing_parts_have_specific_errors():
    with pytest.raises(ValueError, match="presentation.xml"):
        extract(make_template_pptx(omit={"ppt/presentation.xml"}))
    with pytest.raises(ValueError, match="theme1"):
        extract(make_template_pptx(omit={"ppt/theme/theme1.xml"}))
    with pytest.raises(ValueError, match="幻灯片版式"):
        extract(make_template_pptx(layouts={}))


def test_slide_size_outside_supported_range_is_rejected():
    with pytest.raises(ValueError, match="支持范围"):
        extract(make_template_pptx(slide_size=(1000, 6858000)))


def test_theme1_wins_over_numbered_alternatives():
    second = theme_xml({**DEFAULT_COLORS, "accent1": "FF0000"})
    design = extract(make_template_pptx(parts={"ppt/theme/theme2.xml": second}))
    assert design.accent1 == "#315C4E"
    fallback = extract(
        make_template_pptx(omit={"ppt/theme/theme1.xml"}, parts={"ppt/theme/theme2.xml": second})
    )
    assert fallback.accent1 == "#FF0000"


def test_layouts_without_name_or_type_use_part_fallbacks():
    design = extract(make_template_pptx(layouts={1: (None, None), 2: ("节标题", "secHead")}))
    assert [(layout.name, layout.type) for layout in design.layouts] == [
        ("slideLayout1", "unknown"),
        ("节标题", "secHead"),
    ]


def multi_master_parts(master_count, layouts_per_master):
    """Duplicate masters as left behind by slides pasted with "keep source formatting"."""
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    master_ids = "".join(
        f"<p:sldMasterId id='{2147483648 + m}' r:id='rId{m}'/>" for m in range(1, master_count + 1)
    )
    presentation_rels = "".join(
        f"<Relationship Id='rId{m}' Target='slideMasters/slideMaster{m}.xml'/>"
        for m in range(1, master_count + 1)
    )
    parts = {
        "ppt/presentation.xml": (
            f"<p:presentation xmlns:p='{P_NS}' xmlns:r='{r_ns}'>"
            f"<p:sldMasterIdLst>{master_ids}</p:sldMasterIdLst>"
            "<p:sldSz cx='12192000' cy='6858000'/></p:presentation>"
        ),
        "ppt/_rels/presentation.xml.rels": (
            f"<Relationships xmlns='{rel_ns}'>{presentation_rels}</Relationships>"
        ),
    }
    layouts = {}
    for m in range(1, master_count + 1):
        numbers = [(m - 1) * layouts_per_master + i for i in range(1, layouts_per_master + 1)]
        # Declared order deliberately differs from numeric order.
        numbers = numbers[1:] + numbers[:1]
        ids = "".join(f"<p:sldLayoutId id='{2147483700 + n}' r:id='rId{n}'/>" for n in numbers)
        rels = "".join(
            f"<Relationship Id='rId{n}' Target='../slideLayouts/slideLayout{n}.xml'/>"
            for n in numbers
        )
        parts[f"ppt/slideMasters/slideMaster{m}.xml"] = (
            f"<p:sldMaster xmlns:p='{P_NS}' xmlns:r='{r_ns}'>"
            f"<p:sldLayoutIdLst>{ids}</p:sldLayoutIdLst></p:sldMaster>"
        )
        parts[f"ppt/slideMasters/_rels/slideMaster{m}.xml.rels"] = (
            f"<Relationships xmlns='{rel_ns}'>{rels}</Relationships>"
        )
        layouts.update({n: (f"母版{m}-版式{n}", "obj") for n in numbers})
    return parts, layouts


def test_duplicate_masters_list_only_primary_master_layouts_in_declared_order():
    # 21 masters × 10 layouts mirrors a real company template that tripped the 100-layout cap.
    parts, layouts = multi_master_parts(21, 10)
    design = extract(
        make_template_pptx(layouts=layouts, parts=parts, omit={"ppt/presentation.xml"})
    )
    assert [layout.name for layout in design.layouts] == [
        f"母版1-版式{n}" for n in (2, 3, 4, 5, 6, 7, 8, 9, 10, 1)
    ]


def test_layout_cap_still_applies_without_resolvable_master():
    layouts = {n: (f"版式{n}", "obj") for n in range(1, 102)}
    with pytest.raises(ValueError, match="版式数量超过限制"):
        extract(make_template_pptx(layouts=layouts))


def test_fonts_without_usable_typefaces_are_rejected():
    with pytest.raises(ValueError, match="字体"):
        extract(make_template_pptx(fonts=(("", ""), ("", ""))))


def test_corrupt_template_has_actionable_chinese_error():
    with pytest.raises(ValueError, match="损坏|格式"):
        extract(b"not a zip")
    with pytest.raises(ValueError, match="损坏|格式"):
        extract(make_template_pptx(parts={"ppt/slideLayouts/slideLayout9.xml": "<not-xml"}))
