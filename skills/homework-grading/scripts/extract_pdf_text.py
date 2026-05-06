#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract per-page text from a PDF with PyMuPDF.")
    parser.add_argument("--input", required=True, help="Input PDF path.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        fail(f"Input PDF not found: {input_path}")
    if input_path.suffix.lower() != ".pdf":
        fail(f"Input must be a PDF: {input_path}")

    try:
        import fitz
    except ImportError:
        fail("Missing dependency PyMuPDF. Install with: pip install pymupdf")

    pages = []
    try:
        with fitz.open(input_path) as doc:
            if doc.page_count == 0:
                fail(f"PDF has no pages: {input_path}")
            for index, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                text_length = len(text.strip())
                confidence = 0.99 if text_length >= 80 else (0.6 if text_length >= 20 else 0.2)
                pages.append(
                    {
                        "page_number": index,
                        "text": text,
                        "text_length": text_length,
                        "extraction_method": "pymupdf_text",
                        "confidence": confidence,
                    }
                )
    except Exception as exc:
        fail(f"Failed to extract PDF text from {input_path}: {exc}")

    avg_length = sum(page["text_length"] for page in pages) / max(len(pages), 1)
    result = {
        "source_file": str(input_path),
        "pages": pages,
        "needs_ocr": avg_length < 40,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
