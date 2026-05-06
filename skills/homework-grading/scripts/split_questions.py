#!/usr/bin/env python
import argparse
import json
import re
import sys
from pathlib import Path


QUESTION_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?P<label>(?:第\s*(?P<cnum>\d+)\s*题)|(?:Question\s*(?P<qnum>\d+))|(?:Q\s*(?P<qshort>\d+))|(?P<num>\d+)\s*[\.\)\）]|(?P<zh>[一二三四五六七八九十]+)\s*[、.])"
)
ZH_NUMS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def zh_to_int(text: str) -> int:
    if text in ZH_NUMS:
        return ZH_NUMS[text]
    if text.startswith("十") and len(text) == 2:
        return 10 + ZH_NUMS.get(text[1], 0)
    if text.endswith("十") and len(text) == 2:
        return ZH_NUMS.get(text[0], 0) * 10
    if "十" in text:
        left, right = text.split("十", 1)
        return ZH_NUMS.get(left, 1) * 10 + ZH_NUMS.get(right, 0)
    return 0


def page_texts(data: dict) -> list[tuple[int, str, float]]:
    if "pages" in data:
        return [(int(p.get("page_number", i + 1)), p.get("text", ""), float(p.get("confidence", 0.8))) for i, p in enumerate(data["pages"])]
    if "full_text" in data:
        return [(1, data.get("full_text", ""), 0.9)]
    fail("Input JSON must contain either pages[] or full_text.")


def question_id(match: re.Match) -> str:
    raw = match.group("cnum") or match.group("qnum") or match.group("qshort") or match.group("num")
    if raw:
        return str(int(raw))
    return str(zh_to_int(match.group("zh") or "0"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Roughly split extracted text into questions.")
    parser.add_argument("--input", required=True, help="Input extracted JSON path.")
    parser.add_argument("--output", required=True, help="Output questions JSON path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        fail(f"Input JSON not found: {input_path}")
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Failed to read input JSON {input_path}: {exc}")

    combined = ""
    offsets = []
    for page_number, text, confidence in page_texts(data):
        start = len(combined)
        combined += f"\n{text}\n"
        offsets.append((start, len(combined), page_number, confidence))

    matches = list(QUESTION_RE.finditer(combined))
    questions = []
    if not matches:
        questions.append(
            {
                "question_id": "unmatched",
                "text": combined.strip(),
                "source_pages": sorted({p for _, _, p, _ in offsets}),
                "confidence": 0.2,
            }
        )
    else:
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(combined)
            text = combined[start:end].strip()
            pages = []
            confs = []
            for span_start, span_end, page_number, confidence in offsets:
                if span_start < end and span_end > start:
                    pages.append(page_number)
                    confs.append(confidence)
            questions.append(
                {
                    "question_id": question_id(match),
                    "text": text,
                    "source_pages": sorted(set(pages)),
                    "confidence": round((sum(confs) / len(confs)) if confs else 0.5, 4),
                }
            )

    result = {"source_file": data.get("source_file", str(input_path)), "questions": questions}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
