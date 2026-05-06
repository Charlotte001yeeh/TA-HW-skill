#!/usr/bin/env python3
"""Render review_report.md to PDF when local PDF tooling is available."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def try_pandoc(markdown: Path, pdf: Path) -> tuple[bool, bool]:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return False, False
    text = markdown.read_text(encoding="utf-8", errors="replace").replace("\\", "/")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        commands = [[pandoc, str(temp_path), "-o", str(pdf)]]
        for engine in ("xelatex", "lualatex"):
            if shutil.which(engine):
                commands.insert(0, [pandoc, str(temp_path), "--pdf-engine", engine, "-o", str(pdf)])
        for command in commands:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and pdf.exists():
                return True, True
        if result.stderr:
            print(result.stderr.strip())
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    return False, True


def try_reportlab(markdown: Path, pdf: Path) -> bool:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except Exception:
        return False

    styles = getSampleStyleSheet()
    story = []
    for raw in markdown.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + line[2:], styles["BodyText"]))
        elif line.startswith("|"):
            story.append(Paragraph(line.replace("|", " | "), styles["Code"]))
        else:
            story.append(Paragraph(line, styles["BodyText"]))
    doc = SimpleDocTemplate(str(pdf), pagesize=letter)
    doc.build(story)
    return pdf.exists()


def escape_pdf_text(text: str) -> str:
    ascii_text = text.encode("latin-1", errors="replace").decode("latin-1")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def try_simple_pdf(markdown: Path, pdf: Path) -> bool:
    """Create a dependency-free, text-only PDF fallback using PDF core fonts."""
    raw_lines = markdown.read_text(encoding="utf-8", errors="replace").splitlines()
    lines: list[str] = []
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            lines.append("")
        elif line.startswith("|"):
            lines.append(line[:130])
        elif line.startswith("#"):
            lines.append(line.lstrip("#").strip()[:130])
        else:
            lines.append(line[:130])

    pages = [lines[index : index + 58] for index in range(0, len(lines), 58)] or [[]]
    objects: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    font_id = 3
    page_ids: list[int] = []
    for page_lines in pages:
        commands = ["BT", "/F1 9 Tf", "50 760 Td", "12 TL"]
        for line in page_lines:
            commands.append(f"({escape_pdf_text(line)}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        content_id = len(objects) + 1
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = len(objects) + 1
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        objects.append(page.encode("ascii"))
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode("ascii"))
        data.extend(obj)
        data.extend(b"\nendobj\n")
    xref_offset = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    pdf.write_bytes(data)
    return pdf.exists()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    review_dir = root / "work" / "review"
    markdown = review_dir / "review_report.md"
    pdf = review_dir / "review_report.pdf"

    if not markdown.exists():
        print(f"Missing {rel(markdown, root)}. Run render_review_report.py first.")
        return 1

    pandoc_ok, pandoc_available = try_pandoc(markdown, pdf)
    if pandoc_ok or try_reportlab(markdown, pdf) or try_simple_pdf(markdown, pdf):
        print(f"Wrote review PDF to {rel(pdf, root)}")
        return 0

    if pandoc_available:
        print("PDF rendering skipped: pandoc failed and no fallback renderer succeeded.")
    else:
        print("PDF rendering skipped: neither pandoc nor reportlab is available, and simple fallback failed.")
    print(f"Markdown report remains available at {rel(markdown, root)}")
    print("Install pandoc or reportlab if a PDF artifact is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
