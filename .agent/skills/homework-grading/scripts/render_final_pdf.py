#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_grading(path: Path) -> dict:
    if not path.exists():
        fail(f"Grading JSON not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Failed to read grading JSON {path}: {exc}")


def format_score(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def deduction_reason(result: dict) -> str:
    score = float(result.get("score", 0) or 0)
    max_score = float(result.get("max_score", 0) or 0)
    if score >= max_score:
        return ""
    final_reason = (result.get("final_reason") or "").strip()
    if final_reason:
        return final_reason
    parts = []
    for detail in result.get("scoring_details", []):
        point_max = float(detail.get("max_score", 0) or 0)
        awarded = float(detail.get("score_awarded", 0) or 0)
        if awarded < point_max:
            reason = (detail.get("reason") or "").strip()
            point_id = detail.get("point_id", "")
            lost = format_score(point_max - awarded)
            if reason:
                parts.append(f"{point_id} lost {lost}: {reason}")
            else:
                parts.append(f"{point_id} lost {lost}.")
    return " ".join(parts) if parts else "Score is below maximum, but no detailed deduction reason was provided."


def register_fonts():
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        fail("Missing dependency ReportLab. Install with: pip install reportlab")

    normal_font = "STSong-Light"
    bold_font = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(normal_font))
    except Exception as exc:
        fail(f"Failed to register built-in CJK font {normal_font}: {exc}")

    font_candidates = [
        ("CJKBold", Path(r"C:\Windows\Fonts\simhei.ttf")),
        ("CJKBold", Path(r"C:\Windows\Fonts\msyhbd.ttc")),
        ("CJKBold", Path(r"C:\Windows\Fonts\NotoSansCJKsc-Bold.otf")),
    ]
    for name, font_path in font_candidates:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(font_path)))
                bold_font = name
                break
            except Exception:
                continue
    return normal_font, bold_font


def build_pdf(grading: dict, output_path: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        fail("Missing dependency ReportLab. Install with: pip install reportlab")

    normal_font, bold_font = register_fonts()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FinalTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontName=normal_font,
        fontSize=11,
        leading=16,
        spaceAfter=4,
    )
    total_style = ParagraphStyle(
        "Total",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=16,
        leading=22,
        spaceBefore=8,
        spaceAfter=14,
    )
    question_style = ParagraphStyle(
        "Question",
        parent=styles["Heading3"],
        fontName=bold_font,
        fontSize=12.5,
        leading=17,
        spaceBefore=10,
        spaceAfter=5,
    )
    reason_style = ParagraphStyle(
        "Reason",
        parent=styles["BodyText"],
        fontName=normal_font,
        fontSize=10.5,
        leading=15,
        leftIndent=8,
        rightIndent=4,
        spaceAfter=8,
    )

    student_id = grading.get("student_id", "")
    student_name = grading.get("student_name")
    total_score = grading.get("total_score", 0)
    max_total = sum(float(result.get("max_score", 0) or 0) for result in grading.get("results", []))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    story = [
        Paragraph("作业批改结果", title_style),
        Paragraph(f"student_id: {student_id}", meta_style),
    ]
    if student_name:
        story.append(Paragraph(f"student_name: {student_name}", meta_style))
    story.extend(
        [
            Paragraph(f"总分：{format_score(total_score)} / {format_score(max_total)}", total_style),
            HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#999999"), spaceAfter=8),
        ]
    )

    for result in grading.get("results", []):
        question_id = result.get("question_id", "")
        score = format_score(result.get("score", 0))
        max_score = format_score(result.get("max_score", 0))
        story.append(Paragraph(f"第{question_id}题：{score} / {max_score}", question_style))
        reason = deduction_reason(result)
        if reason:
            story.append(Paragraph(f"扣分原因：{reason}", reason_style))
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#DDDDDD"), spaceBefore=2, spaceAfter=6))

    try:
        doc.build(story)
    except Exception as exc:
        fail(f"Failed to render final PDF {output_path}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a final readable PDF from one student's grading JSON.")
    parser.add_argument("--grading", required=True, help="Input grading JSON path.")
    parser.add_argument("--output", required=True, help="Output final PDF path.")
    args = parser.parse_args()

    grading = load_grading(Path(args.grading))
    build_pdf(grading, Path(args.output))


if __name__ == "__main__":
    main()
