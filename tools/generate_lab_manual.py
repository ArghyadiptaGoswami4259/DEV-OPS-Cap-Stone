"""Generate the DevOps lab manual PDF, DOCX and Markdown from original content.

The supplied IPCV PDF was used only as a visual template: cover composition, colour palette,
running header/footer, blue section headings, code panels and output tables. No inner text is reused.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from generate_diagrams import main as generate_diagrams
from lab_manual_data import (
    APPENDICES,
    EXPERIMENTS,
    FOOTER_TITLE,
    IMPLEMENTATION_SCREENSHOTS,
    REPOSITORY_URL,
    RUNNING_HEADER,
    STUDENT,
    SUBJECT,
)
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import (
    Image as RLImage,
)

ROOT = Path(__file__).resolve().parents[1]
LAB_DIR = ROOT / "docs" / "lab-manual"
PDF_PATH = LAB_DIR / "DevOps-and-Automation-Lab-Manual.pdf"
DOCX_PATH = LAB_DIR / "DevOps-and-Automation-Lab-Manual.docx"
MD_PATH = LAB_DIR / "DevOps-and-Automation-Lab-Manual.md"
SHOWCASE_DIR = ROOT / "docs" / "implementation-showcase"
EVIDENCE_PDF_PATH = SHOWCASE_DIR / "Implementation-Evidence-Screenshots.pdf"
LOGO = LAB_DIR / "assets" / "university-logo.png"

BLUE = colors.HexColor("#1B4F72")
ACCENT = colors.HexColor("#2E75B6")
PALE = colors.HexColor("#EAF2FB")
GREY = colors.HexColor("#888888")
BODY_GREY = colors.HexColor("#555555")
BORDER = colors.HexColor("#B8C7D9")

DOCX_BLUE = RGBColor(0x1B, 0x4F, 0x72)
DOCX_ACCENT = RGBColor(0x2E, 0x75, 0xB6)
DOCX_GREY = RGBColor(0x88, 0x88, 0x88)
DOCX_BODY_GREY = RGBColor(0x55, 0x55, 0x55)

TOC_ENTRIES = [(item["key"], item["title"]) for item in EXPERIMENTS + APPENDICES]


def clean_code(lines: list[str]) -> list[str]:
    """Normalise escaped regex characters used in displayed code snippets."""
    return [
        line.replace(r"\\(", r"\(").replace(r"\\)", r"\)")
        for line in lines
    ]


def pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles = {
        "TocTitle": ParagraphStyle(
            "TocTitle", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=16.9, leading=20, textColor=BLUE, alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "TocEntry": ParagraphStyle(
            "TocEntry", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.4, leading=16.6, textColor=colors.black,
        ),
        "TocPage": ParagraphStyle(
            "TocPage", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.4, leading=16.6, alignment=TA_CENTER,
        ),
        "ExperimentTitle": ParagraphStyle(
            "ExperimentTitle", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=15, leading=18, textColor=BLUE, spaceAfter=3,
        ),
        "Aim": ParagraphStyle(
            "Aim", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=9.3, leading=12, textColor=BODY_GREY, spaceAfter=8,
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=12.2, leading=15, textColor=ACCENT,
            spaceBefore=8, spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "Body", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.4, leading=14.2, spaceAfter=5,
        ),
        "Bullet": ParagraphStyle(
            "Bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.4, leading=13.8, leftIndent=17, firstLineIndent=-11,
            spaceAfter=2,
        ),
        "Number": ParagraphStyle(
            "Number", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.4, leading=13.8, leftIndent=20, firstLineIndent=-14,
            spaceAfter=2,
        ),
        "Code": ParagraphStyle(
            "Code", parent=base["Normal"], fontName="Courier",
            fontSize=8.4, leading=9.8, textColor=colors.HexColor("#1E3A5F"),
        ),
        "OutputHeading": ParagraphStyle(
            "OutputHeading", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=12.2, leading=15, textColor=ACCENT, spaceAfter=7,
        ),
        "OutputLabel": ParagraphStyle(
            "OutputLabel", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=10.4, leading=13, alignment=TA_CENTER,
        ),
        "Caption": ParagraphStyle(
            "Caption", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8.8, leading=11, textColor=BODY_GREY,
            alignment=TA_CENTER, spaceBefore=5, spaceAfter=8,
        ),
        "AppendixTitle": ParagraphStyle(
            "AppendixTitle", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=15, leading=18, textColor=BLUE, spaceAfter=3,
        ),
        "ScreenshotTitle": ParagraphStyle(
            "ScreenshotTitle", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=11.4, leading=14, textColor=ACCENT,
            alignment=TA_CENTER, spaceBefore=4, spaceAfter=8,
        ),
    }
    return styles


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def bullet(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph("&bull; " + escape(text), style)


def numbered(index: int, text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(f"{index}. " + escape(text), style)


def code_table(lines: list[str], styles: dict[str, ParagraphStyle]) -> Table:
    pre = Preformatted("\n".join(clean_code(lines)), styles["Code"])
    table = Table([[pre]], colWidths=[424.8])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E6F3")),
    ]))
    return table


def output_table(exp: dict, styles: dict[str, ParagraphStyle]) -> Table:
    image_path = ROOT / exp["image"]
    with PILImage.open(image_path) as image:
        width, height = image.size
    scale = min(325 / width, 215 / height)
    picture = RLImage(str(image_path), width=width * scale, height=height * scale)
    table = Table(
        [[Paragraph(escape(exp["output_label"]), styles["OutputLabel"]), picture]],
        colWidths=[95, 329.8],
    )
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.7, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def draw_cover(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setTitle("Dev Ops and Automation Lab Manual")
    canvas.setAuthor(STUDENT["name"])
    canvas.setSubject(SUBJECT)
    canvas.setFillColor(BLUE)
    canvas.setFont("Helvetica-Bold", 20.6)
    canvas.drawCentredString(306, 654, "DEV OPS AND")
    canvas.drawCentredString(306, 628, "AUTOMATION")
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica-BoldOblique", 15)
    canvas.drawCentredString(306, 600, "Lab Manual")
    canvas.setFont("Helvetica-Oblique", 9.2)
    canvas.drawCentredString(306, 580, f"Subject: {SUBJECT}")
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(0.7)
    canvas.line(93.6, 566, 518.4, 566)
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Oblique", 10.4)
    canvas.drawCentredString(306, 547, "Submitted in partial fulfilment of the requirement of the degree of")
    canvas.setFont("Helvetica-Bold", 12.2)
    canvas.drawCentredString(306, 527, STUDENT["degree"])
    canvas.setFont("Helvetica-Bold", 11.3)
    canvas.drawCentredString(306, 509, STUDENT["program"])
    canvas.setFont("Helvetica-Oblique", 10.4)
    canvas.drawCentredString(306, 491, "To")
    canvas.setFont("Helvetica-Bold", 12.2)
    canvas.drawCentredString(306, 471, STUDENT["university"])
    canvas.setFont("Helvetica-Oblique", 10.4)
    canvas.drawCentredString(306, 453, "by")
    canvas.setFont("Helvetica-Bold", 12.2)
    canvas.drawCentredString(306, 433, f"{STUDENT['name']} (Roll {STUDENT['roll']})")
    canvas.setFont("Helvetica-Bold", 11.3)
    canvas.drawCentredString(306, 414, f"B.Tech CSE Section - {STUDENT['section']} | Year {STUDENT['year']}")
    if LOGO.exists():
        with PILImage.open(LOGO) as logo:
            lw, lh = logo.size
        width = 84
        height = width * lh / lw
        canvas.drawImage(
            ImageReader(str(LOGO)), 306 - width / 2, 302,
            width=width, height=height, mask="auto",
        )
    canvas.setFont("Helvetica-Bold", 11.3)
    canvas.drawCentredString(306, 264, STUDENT["department"])
    canvas.drawCentredString(306, 244, STUDENT["school"])
    canvas.drawCentredString(306, 224, STUDENT["address"])
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica", 8.6)
    canvas.drawCentredString(306, 204, f"Repository: {REPOSITORY_URL}")
    canvas.linkURL(REPOSITORY_URL, (93.6, 196, 518.4, 212), relative=0, thickness=0)
    canvas.restoreState()


def draw_footer(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("Helvetica", 8.4)
    canvas.setFillColor(GREY)
    canvas.drawCentredString(306, 40, f"{FOOTER_TITLE}  |  Page {doc.page}")
    canvas.restoreState()


def draw_toc_page(canvas, doc) -> None:  # noqa: ANN001
    draw_footer(canvas, doc)


def draw_body_page(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("Helvetica-Oblique", 8.4)
    canvas.setFillColor(GREY)
    canvas.drawString(93.6, 759, RUNNING_HEADER)
    canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
    canvas.setLineWidth(0.5)
    canvas.line(93.6, 749, 518.4, 749)
    draw_footer(canvas, doc)
    canvas.restoreState()


class ManualDocTemplate(BaseDocTemplate):
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        BaseDocTemplate.__init__(self, *args, **kwargs)
        self.toc_pages: dict[str, int] = {}

    def afterFlowable(self, flowable) -> None:  # noqa: ANN001
        marker = getattr(flowable, "_toc_marker", None)
        if marker:
            self.toc_pages[marker] = self.page


def toc_table(toc_map: dict[str, int], styles: dict[str, ParagraphStyle]) -> Table:
    rows = []
    font_name, font_size = "Helvetica", 10.4
    dot_width = pdfmetrics.stringWidth(".", font_name, font_size)
    for key, label in TOC_ENTRIES:
        text_width = pdfmetrics.stringWidth(label + " ", font_name, font_size)
        count = max(3, int((390 - text_width) / dot_width))
        left = f"{label} " + "." * count
        rows.append([
            Paragraph(escape(left), styles["TocEntry"]),
            Paragraph(str(toc_map.get(key, 0)), styles["TocPage"]),
        ])
    table = Table(rows, colWidths=[395, 29.8])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def experiment_content(exp: dict, styles: dict[str, ParagraphStyle]) -> list:
    title = p(exp["title"], styles["ExperimentTitle"])
    title._toc_marker = exp["key"]
    story = [
        Spacer(1, 10),
        title,
        HRFlowable(width="100%", thickness=0.7, color=ACCENT,
                   spaceBefore=1, spaceAfter=6, hAlign="LEFT"),
        p(exp["aim"], styles["Aim"]),
        p("Theory", styles["SectionHeading"]),
    ]
    story.extend(p(paragraph, styles["Body"]) for paragraph in exp["theory"])
    story.append(p("Tools Required", styles["SectionHeading"]))
    story.append(p(exp["tools"], styles["Body"]))
    story.append(p("Algorithm / Procedure", styles["SectionHeading"]))
    story.extend(
        numbered(index, step, styles["Number"])
        for index, step in enumerate(exp["procedure"], start=1)
    )
    story.append(p(exp["code_title"], styles["SectionHeading"]))
    story.append(code_table(exp["code"], styles))
    story.append(p("Verification", styles["SectionHeading"]))
    story.extend(bullet(item, styles["Bullet"]) for item in exp["verification"])
    return story


def output_content(exp: dict, styles: dict[str, ParagraphStyle]) -> list:
    story = [
        Spacer(1, 4),
        p("Output", styles["OutputHeading"]),
        output_table(exp, styles),
        p(exp["output_caption"], styles["Caption"]),
        p("Observations", styles["SectionHeading"]),
    ]
    story.extend(bullet(item, styles["Bullet"]) for item in exp["expected_output"])
    story.append(p("Result", styles["SectionHeading"]))
    story.append(p(exp["result"], styles["Body"]))
    story.append(p("Viva Questions", styles["SectionHeading"]))
    story.extend(
        numbered(index, question, styles["Number"])
        for index, question in enumerate(exp["viva"], start=1)
    )
    return story


def screenshot_flowable(path: Path) -> RLImage:
    """Scale one screenshot to the manual body frame while preserving aspect ratio."""
    if not path.exists():
        raise FileNotFoundError(f"Missing implementation screenshot: {path}")
    with PILImage.open(path) as image:
        width, height = image.size
    frame_width = 424.8
    frame_height = 555.0
    scale = min(frame_width / width, frame_height / height)
    flowable = RLImage(str(path), width=width * scale, height=height * scale)
    flowable.hAlign = "CENTER"
    return flowable


def appendix_content(ap: dict, styles: dict[str, ParagraphStyle]) -> list:
    title = p(ap["title"], styles["AppendixTitle"])
    title._toc_marker = ap["key"]
    story = [
        Spacer(1, 10),
        title,
        HRFlowable(width="100%", thickness=0.7, color=ACCENT,
                   spaceBefore=1, spaceAfter=6, hAlign="LEFT"),
        p(ap["intro"], styles["Aim"]),
    ]
    for heading, items in ap["sections"]:
        story.append(p(heading, styles["SectionHeading"]))
        story.extend(bullet(item, styles["Bullet"]) for item in items)
    story.append(p("Quick Reference", styles["SectionHeading"]))
    story.append(code_table(ap["code"], styles))
    for index, shot in enumerate(ap.get("screenshots", []), start=1):
        story.append(PageBreak())
        story.append(p(f"Figure C.{index} - {shot['title']}", styles["ScreenshotTitle"]))
        story.append(screenshot_flowable(ROOT / shot["path"]))
        story.append(p(shot["caption"], styles["Caption"]))
    return story


def build_story(toc_map: dict[str, int]) -> list:
    styles = pdf_styles()
    story = [NextPageTemplate("toc"), PageBreak()]
    story.append(p("Table of Contents", styles["TocTitle"]))
    story.append(HRFlowable(width="100%", thickness=0.7, color=ACCENT,
                            spaceBefore=1, spaceAfter=10, hAlign="LEFT"))
    story.append(toc_table(toc_map, styles))
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())
    for exp in EXPERIMENTS:
        story.extend(experiment_content(exp, styles))
        story.append(PageBreak())
        story.extend(output_content(exp, styles))
        story.append(PageBreak())
    for index, ap in enumerate(APPENDICES):
        story.extend(appendix_content(ap, styles))
        if index < len(APPENDICES) - 1:
            story.append(PageBreak())
    return story


def build_pdf(toc_map: dict[str, int]) -> dict[str, int]:
    cover_frame = Frame(0, 0, 612, 792, leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0, id="cover")
    toc_frame = Frame(93.6, 55, 424.8, 665, leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, id="toc")
    body_frame = Frame(93.6, 55, 424.8, 665, leftPadding=0, rightPadding=0,
                       topPadding=0, bottomPadding=0, id="body")
    doc = ManualDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        title="Dev Ops and Automation Lab Manual",
        author=STUDENT["name"],
        subject="End-to-end DevOps automation capstone",
        pageTemplates=[
            PageTemplate(id="cover", frames=[cover_frame], onPage=draw_cover),
            PageTemplate(id="toc", frames=[toc_frame], onPage=draw_toc_page),
            PageTemplate(id="body", frames=[body_frame], onPage=draw_body_page),
        ],
    )
    doc.build(build_story(toc_map))
    return dict(doc.toc_pages)


def generate_pdf() -> dict[str, int]:
    toc_map: dict[str, int] = {}
    for _ in range(3):
        pages = build_pdf(toc_map)
        if pages == toc_map:
            break
        toc_map = pages
    missing = [key for key, _ in TOC_ENTRIES if key not in toc_map]
    if missing:
        raise RuntimeError(f"Could not resolve TOC page numbers for: {missing}")
    return toc_map


def build_evidence_pdf() -> None:
    """Create a screenshots-only companion PDF from the same captured evidence."""
    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(EVIDENCE_PDF_PATH),
        pagesize=letter,
        title="TaskFlow Implementation Evidence Screenshots",
        author=STUDENT["name"],
        subject=f"{SUBJECT} local-host implementation evidence",
    )
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "EvidenceTitle", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=20, leading=24, textColor=BLUE, alignment=TA_CENTER,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "EvidenceBody", parent=base["Normal"], fontName="Helvetica",
        fontSize=10.5, leading=15, textColor=BODY_GREY,
        alignment=TA_CENTER, spaceAfter=8,
    )
    styles = pdf_styles()
    story = [
        Spacer(1, 86),
        p("TaskFlow Implementation Evidence", title_style),
        p("Dev Ops and Automation Lab Manual - Screenshot Companion", body_style),
        Spacer(1, 18),
        p(f"Submitted by: {STUDENT['name']} (Roll {STUDENT['roll']})", body_style),
        p(f"Section {STUDENT['section']} | Year {STUDENT['year']}", body_style),
        p("Local host: 0.0.0.0:8010 | Evidence showcase: 0.0.0.0:8011", body_style),
        Paragraph(
            f'<a href="{REPOSITORY_URL}">{escape(REPOSITORY_URL)}</a>',
            body_style,
        ),
        Spacer(1, 16),
        p(
            "This direct PDF contains every screenshot embedded in Appendix C of the "
            "full lab manual. It complements, but does not replace, the template-styled "
            "capstone manual.",
            body_style,
        ),
    ]
    for index, shot in enumerate(IMPLEMENTATION_SCREENSHOTS, start=1):
        story.append(PageBreak())
        story.append(p(f"Figure C.{index} - {shot['title']}", styles["ScreenshotTitle"]))
        story.append(screenshot_flowable(ROOT / shot["path"]))
        story.append(p(shot["caption"], styles["Caption"]))
    doc.build(story)


def write_markdown(toc_map: dict[str, int]) -> None:
    lines = [
        f"# {SUBJECT}",
        "",
        "**Lab Manual**",
        "",
        f"**Submitted by:** {STUDENT['name']} (Roll {STUDENT['roll']})<br>",
        f"**Section:** {STUDENT['section']} | **Year:** {STUDENT['year']}<br>",
        f"**Subject:** {SUBJECT}<br>",
        f"**Degree:** {STUDENT['degree']} ({STUDENT['program']})<br>",
        f"**University:** {STUDENT['university']}<br>",
        f"**Repository:** [{REPOSITORY_URL}]({REPOSITORY_URL})",
        "",
        "---",
        "",
        "## Table of Contents",
        "",
    ]
    for key, label in TOC_ENTRIES:
        lines.append(f"- {label} ... {toc_map[key]}")
    lines.append("")
    lines.append("---")
    lines.append("")
    for exp in EXPERIMENTS:
        lines.extend([
            f"## {exp['title']}",
            "",
            f"*{exp['aim']}*",
            "",
            "### Theory",
            "",
        ])
        for paragraph in exp["theory"]:
            lines.extend([paragraph, ""])
        lines.extend(["### Tools Required", "", exp["tools"], "",
                      "### Algorithm / Procedure", ""])
        lines.extend(f"{i}. {step}" for i, step in enumerate(exp["procedure"], 1))
        lines.extend(["", f"### {exp['code_title']}", "", "```text"])
        lines.extend(clean_code(exp["code"]))
        lines.extend(["```", "", "### Verification", ""])
        lines.extend(f"- {item}" for item in exp["verification"])
        lines.extend(["", "## Output", ""])
        lines.append(f"| {exp['output_label']} | Expected evidence |")
        lines.append("|---|---|")
        lines.append(f"| **{exp['output_label']}** | ![{exp['output_caption']}](../diagrams/{Path(exp['image']).name}) |")
        lines.extend(["", f"*{exp['output_caption']}*", "", "### Observations", ""])
        lines.extend(f"- {item}" for item in exp["expected_output"])
        lines.extend(["", "### Result", "", exp["result"], "",
                      "### Viva Questions", ""])
        lines.extend(f"{i}. {q}" for i, q in enumerate(exp["viva"], 1))
        lines.extend(["", "---", ""])
    for ap in APPENDICES:
        lines.extend([f"## {ap['title']}", "", ap["intro"], ""])
        for heading, items in ap["sections"]:
            lines.extend([f"### {heading}", ""])
            lines.extend(f"- {item}" for item in items)
            lines.append("")
        lines.extend(["### Quick Reference", "", "```text"])
        lines.extend(clean_code(ap["code"]))
        lines.extend(["```", ""])
        for index, shot in enumerate(ap.get("screenshots", []), start=1):
            image = f"../implementation-showcase/screenshots/{Path(shot['path']).name}"
            lines.extend([
                f"### Figure C.{index} - {shot['title']}",
                "",
                f"![{shot['caption']}]({image})",
                "",
                f"*{shot['caption']}*",
                "",
                "---",
                "",
            ])
        lines.append("---")
        lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_border(cell, color: str = "B8C7D9", size: str = "6") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def set_bottom_border(paragraph, color: str = "2E75B6", size: str = "6") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instruction, separate, text, end):
        run._r.append(element)


def configure_section(section) -> None:
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.left_margin = Inches(1.3)
    section.right_margin = Inches(1.3)
    section.top_margin = Inches(0.95)
    section.bottom_margin = Inches(0.75)
    section.header_distance = Inches(0.38)
    section.footer_distance = Inches(0.45)


def add_docx_style(doc: Document, name: str, size: float, *, bold: bool = False,
                   italic: bool = False, color: RGBColor | None = None,
                   align=None, before: float = 0, after: float = 4,
                   font: str = "Calibri") -> None:
    style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    style.font.name = font
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    if color is not None:
        style.font.color.rgb = color
    if align is not None:
        style.paragraph_format.alignment = align
    style.paragraph_format.space_before = Pt(before)
    style.paragraph_format.space_after = Pt(after)


def docx_cover(doc: Document) -> None:
    add_docx_style(doc, "CoverTitle", 20.6, bold=True, color=DOCX_BLUE,
                   align=WD_ALIGN_PARAGRAPH.CENTER, before=72, after=0)
    add_docx_style(doc, "CoverSubtitle", 15, bold=True, italic=True,
                   color=DOCX_ACCENT, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=4)
    add_docx_style(doc, "CoverItalic", 10.4, italic=True,
                   align=WD_ALIGN_PARAGRAPH.CENTER, after=6)
    add_docx_style(doc, "CoverBold", 11.3, bold=True,
                   align=WD_ALIGN_PARAGRAPH.CENTER, after=5)
    add_docx_style(doc, "CoverDegree", 12.2, bold=True,
                   align=WD_ALIGN_PARAGRAPH.CENTER, after=5)

    doc.add_paragraph("DEV OPS AND", style="CoverTitle")
    doc.add_paragraph("AUTOMATION", style="CoverTitle").paragraph_format.space_before = Pt(0)
    doc.add_paragraph("Lab Manual", style="CoverSubtitle")
    doc.add_paragraph(f"Subject: {SUBJECT}", style="CoverItalic")
    line = doc.add_paragraph()
    set_bottom_border(line, "2E75B6", "6")
    doc.add_paragraph(
        "Submitted in partial fulfilment of the requirement of the degree of",
        style="CoverItalic",
    )
    doc.add_paragraph(STUDENT["degree"], style="CoverDegree")
    doc.add_paragraph(STUDENT["program"], style="CoverBold")
    doc.add_paragraph("To", style="CoverItalic")
    doc.add_paragraph(STUDENT["university"], style="CoverDegree")
    doc.add_paragraph("by", style="CoverItalic")
    doc.add_paragraph(f"{STUDENT['name']} (Roll {STUDENT['roll']})", style="CoverDegree")
    doc.add_paragraph(
        f"B.Tech CSE Section - {STUDENT['section']} | Year {STUDENT['year']}",
        style="CoverBold",
    )
    logo = doc.add_paragraph()
    logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo.paragraph_format.space_before = Pt(16)
    logo.paragraph_format.space_after = Pt(55)
    logo.add_run().add_picture(str(LOGO), width=Inches(1.18))
    doc.add_paragraph(STUDENT["department"], style="CoverBold")
    doc.add_paragraph(STUDENT["school"], style="CoverBold")
    doc.add_paragraph(STUDENT["address"], style="CoverBold")
    doc.add_paragraph(f"Repository: {REPOSITORY_URL}", style="CoverItalic")


def docx_toc(doc: Document, toc_map: dict[str, int]) -> None:
    title = doc.add_paragraph("Table of Contents")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.runs[0].font.name = "Calibri"
    title.runs[0].font.size = Pt(16.9)
    title.runs[0].font.bold = True
    title.runs[0].font.color.rgb = DOCX_BLUE
    set_bottom_border(title, "2E75B6", "6")
    table = doc.add_table(rows=0, cols=2)
    table.autofit = False
    table.columns[0].width = Inches(5.45)
    table.columns[1].width = Inches(0.45)
    for key, label in TOC_ENTRIES:
        cells = table.add_row().cells
        dots = "." * max(3, 105 - len(label))
        left = cells[0].paragraphs[0]
        left.add_run(f"{label} {dots}")
        cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        cells[1].paragraphs[0].add_run(str(toc_map[key]))
        for cell in cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "Calibri"
                    run.font.size = Pt(10.4)


def docx_header_footer(section, header: bool) -> None:
    section.different_first_page_header_footer = False
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    hp = section.header.paragraphs[0]
    hp.text = RUNNING_HEADER if header else ""
    for run in hp.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(8.4)
        run.font.italic = True
        run.font.color.rgb = DOCX_GREY
    if header:
        set_bottom_border(hp, "D9E2EC", "4")
    fp = section.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run(f"{FOOTER_TITLE}  |  Page ")
    run.font.name = "Calibri"
    run.font.size = Pt(8.4)
    run.font.color.rgb = DOCX_GREY
    add_page_field(fp)


def docx_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.4)
    normal.paragraph_format.space_after = Pt(5)
    add_docx_style(doc, "LabTitle", 15, bold=True, color=DOCX_BLUE, after=3)
    add_docx_style(doc, "LabAim", 9.3, italic=True, color=DOCX_BODY_GREY, after=7)
    add_docx_style(doc, "LabHeading", 12.2, bold=True, color=DOCX_ACCENT,
                   before=8, after=4)
    add_docx_style(doc, "LabOutput", 12.2, bold=True, color=DOCX_ACCENT, after=7)
    add_docx_style(doc, "LabCaption", 8.8, italic=True, color=DOCX_BODY_GREY,
                   align=WD_ALIGN_PARAGRAPH.CENTER, before=4, after=8)
    add_docx_style(doc, "LabCode", 8.4, color=RGBColor(0x1E, 0x3A, 0x5F),
                   after=0, font="Consolas")


def docx_title(doc: Document, text: str, marker_style: str = "LabTitle") -> None:
    paragraph = doc.add_paragraph(text, style=marker_style)
    set_bottom_border(paragraph, "2E75B6", "6")


def docx_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def docx_numbers(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Number")


def docx_code(doc: Document, lines: list[str]) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    set_cell_shading(cell, "EAF2FB")
    set_cell_border(cell, "D9E6F3", "4")
    for index, line in enumerate(clean_code(lines)):
        paragraph = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        paragraph.style = doc.styles["LabCode"]
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.add_run(line)


def docx_output_table(doc: Document, exp: dict) -> None:
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    table.columns[0].width = Inches(1.25)
    table.columns[1].width = Inches(5.15)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    left, right = table.rows[0].cells
    left.text = exp["output_label"]
    left.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    left.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in left.paragraphs[0].runs:
        run.font.bold = True
        run.font.size = Pt(10.4)
    right.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    right.paragraphs[0].add_run().add_picture(
        str(ROOT / exp["image"]), width=Inches(5.0)
    )
    for cell in (left, right):
        set_cell_border(cell, "B8C7D9", "6")


def docx_experiment(doc: Document, exp: dict) -> None:
    docx_title(doc, exp["title"])
    doc.add_paragraph(exp["aim"], style="LabAim")
    doc.add_paragraph("Theory", style="LabHeading")
    for paragraph in exp["theory"]:
        doc.add_paragraph(paragraph)
    doc.add_paragraph("Tools Required", style="LabHeading")
    doc.add_paragraph(exp["tools"])
    doc.add_paragraph("Algorithm / Procedure", style="LabHeading")
    docx_numbers(doc, exp["procedure"])
    doc.add_paragraph(exp["code_title"], style="LabHeading")
    docx_code(doc, exp["code"])
    doc.add_paragraph("Verification", style="LabHeading")
    docx_bullets(doc, exp["verification"])
    doc.add_page_break()
    doc.add_paragraph("Output", style="LabOutput")
    docx_output_table(doc, exp)
    doc.add_paragraph(exp["output_caption"], style="LabCaption")
    doc.add_paragraph("Observations", style="LabHeading")
    docx_bullets(doc, exp["expected_output"])
    doc.add_paragraph("Result", style="LabHeading")
    doc.add_paragraph(exp["result"])
    doc.add_paragraph("Viva Questions", style="LabHeading")
    docx_numbers(doc, exp["viva"])
    doc.add_page_break()


def docx_appendix(doc: Document, ap: dict) -> None:
    docx_title(doc, ap["title"])
    doc.add_paragraph(ap["intro"], style="LabAim")
    for heading, items in ap["sections"]:
        doc.add_paragraph(heading, style="LabHeading")
        docx_bullets(doc, items)
    doc.add_paragraph("Quick Reference", style="LabHeading")
    docx_code(doc, ap["code"])
    for index, shot in enumerate(ap.get("screenshots", []), start=1):
        doc.add_page_break()
        doc.add_paragraph(f"Figure C.{index} - {shot['title']}", style="LabHeading")
        picture = doc.add_paragraph()
        picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
        picture.add_run().add_picture(str(ROOT / shot["path"]), width=Inches(6.3))
        caption = doc.add_paragraph(shot["caption"], style="LabAim")
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER


def build_docx(toc_map: dict[str, int]) -> None:
    doc = Document()
    doc.core_properties.title = "Dev Ops and Automation Lab Manual"
    doc.core_properties.author = STUDENT["name"]
    doc.core_properties.subject = SUBJECT
    doc.core_properties.keywords = "DevOps, CI/CD, Kubernetes, GitOps, Observability"
    configure_section(doc.sections[0])
    doc.sections[0].different_first_page_header_footer = True
    docx_styles(doc)
    docx_cover(doc)

    toc_section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(toc_section)
    docx_header_footer(toc_section, header=False)
    docx_toc(doc, toc_map)

    body_section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(body_section)
    docx_header_footer(body_section, header=True)
    for exp in EXPERIMENTS:
        docx_experiment(doc, exp)
    for index, ap in enumerate(APPENDICES):
        docx_appendix(doc, ap)
        if index < len(APPENDICES) - 1:
            doc.add_page_break()
    doc.save(DOCX_PATH)


def main() -> None:
    LAB_DIR.mkdir(parents=True, exist_ok=True)
    generate_diagrams()
    toc_map = generate_pdf()
    write_markdown(toc_map)
    build_docx(toc_map)
    build_evidence_pdf()
    print(f"Generated PDF:  {PDF_PATH.relative_to(ROOT)}")
    print(f"Generated DOCX: {DOCX_PATH.relative_to(ROOT)}")
    print(f"Generated MD:   {MD_PATH.relative_to(ROOT)}")
    print(f"Generated evidence PDF: {EVIDENCE_PDF_PATH.relative_to(ROOT)}")
    print(f"Resolved {len(toc_map)} table-of-contents page numbers")


if __name__ == "__main__":
    main()
