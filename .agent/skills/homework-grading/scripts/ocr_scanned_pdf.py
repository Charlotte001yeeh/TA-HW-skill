#!/usr/bin/env python
import argparse
import json
import shutil
import sys
from pathlib import Path


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR scanned PDFs to per-page JSON.")
    parser.add_argument("--input", required=True, help="Input scanned PDF path.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        fail(f"Input PDF not found: {input_path}")
    if input_path.suffix.lower() != ".pdf":
        fail(f"Input must be a PDF: {input_path}")

    missing = []
    try:
        import fitz
    except ImportError:
        missing.append("PyMuPDF (pip install pymupdf)")
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        missing.append("pytesseract and pillow (pip install pytesseract pillow)")
    if shutil.which("tesseract") is None:
        missing.append("Tesseract executable on PATH")
    if missing:
        fail("Missing OCR dependencies: " + "; ".join(missing))

    pages = []
    try:
        with fitz.open(input_path) as doc:
            if doc.page_count == 0:
                fail(f"PDF has no pages: {input_path}")
            for index, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                words = []
                confidences = []
                for text, conf in zip(data.get("text", []), data.get("conf", [])):
                    if text and text.strip():
                        words.append(text)
                        try:
                            conf_value = float(conf)
                            if conf_value >= 0:
                                confidences.append(conf_value)
                        except ValueError:
                            pass
                text = " ".join(words)
                avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
                pages.append(
                    {
                        "page_number": index,
                        "text": text,
                        "text_length": len(text.strip()),
                        "extraction_method": "tesseract_ocr",
                        "confidence": round(avg_conf, 4),
                    }
                )
    except Exception as exc:
        fail(f"Failed to OCR PDF {input_path}: {exc}")

    result = {
        "source_file": str(input_path),
        "pages": pages,
        "needs_ocr": False,
        "ocr_low_confidence": any(page["confidence"] < 0.75 for page in pages),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
