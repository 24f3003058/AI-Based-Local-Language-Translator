#!/usr/bin/env python3
"""
Batch translation from CSV or TXT files.
Groups segments into batches of N to minimize API calls.

Usage:
    python tools/translate_batch.py
        --input-file .tmp/batch_input/my_file.csv
        --output-file .tmp/batch_output/my_file_translated.csv
        --source-lang en
        --target-lang bn
        --domain legal
        --batch-size 10

Input CSV columns: id, source_text, source_lang (optional), target_lang (optional), domain (optional)
Input TXT: one segment per line

Output JSON to stdout: {total, succeeded, failed, output_file, failures}
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def read_csv_input(file_path: Path, source_lang: str, target_lang: str, domain: str) -> list[dict]:
    segments = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"id", "source_text"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError(f"CSV must have columns: {required}. Found: {reader.fieldnames}")

        for i, row in enumerate(reader):
            segments.append({
                "id": row["id"],
                "source_text": row["source_text"].strip(),
                "source_lang": row.get("source_lang", source_lang) or source_lang,
                "target_lang": row.get("target_lang", target_lang) or target_lang,
                "domain": row.get("domain", domain) or domain,
            })
    return segments


def read_txt_input(file_path: Path, source_lang: str, target_lang: str, domain: str) -> list[dict]:
    segments = []
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                segments.append({"id": str(i + 1), "source_text": "", "source_lang": source_lang,
                                  "target_lang": target_lang, "domain": domain, "skip": True})
                continue
            segments.append({
                "id": str(i + 1),
                "source_text": line,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "domain": domain,
            })
    return segments


def translate_batch_with_claude(batch: list[dict]) -> list[dict]:
    """Translate a batch of segments in a single Claude API call."""
    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError as e:
        raise RuntimeError(f"Missing dependency: {e}")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env file.")

    # Use the first segment's lang/domain for the batch (segments are pre-grouped)
    source_lang = batch[0]["source_lang"]
    target_lang = batch[0]["target_lang"]
    domain = batch[0]["domain"]

    # Build numbered list prompt
    items_text = "\n".join([f"{i+1}. {seg['source_text']}" for i, seg in enumerate(batch)])

    system_prompt = (
        f"You are an expert translator from {source_lang.upper()} to {target_lang.upper()}. "
        f"Domain: {domain.upper()}. "
        f"Translate each numbered item and return ONLY a JSON array with objects having "
        f"'index' (1-based integer) and 'translated_text' (string) fields. "
        f"Do not add any other text or explanation."
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"Translate these {len(batch)} items:\n\n{items_text}",
        }],
    )

    raw = response.content[0].text.strip()

    # Parse JSON response
    # Handle potential markdown code blocks
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

    translations = json.loads(raw)

    # Map back to batch
    results = []
    index_map = {t["index"]: t["translated_text"] for t in translations}
    for i, seg in enumerate(batch):
        translated = index_map.get(i + 1, "")
        results.append({
            "id": seg["id"],
            "source_text": seg["source_text"],
            "translated_text": translated,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "domain": domain,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens if i == 0 else 0,
        })
    return results


def group_segments_by_lang_pair(segments: list[dict]) -> dict:
    """Group segments by (source_lang, target_lang, domain) for coherent batches."""
    groups = {}
    for seg in segments:
        key = (seg["source_lang"], seg["target_lang"], seg["domain"])
        groups.setdefault(key, []).append(seg)
    return groups


def main():
    parser = argparse.ArgumentParser(description="Batch translate from file")
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--source-lang", default="en")
    parser.add_argument("--target-lang", required=True)
    parser.add_argument("--domain", default="casual")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    if not input_path.exists():
        print(json.dumps({"error": f"Input file not found: {args.input_file}", "code": "FILE_NOT_FOUND"}), file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read input
    try:
        if input_path.suffix.lower() == ".csv":
            segments = read_csv_input(input_path, args.source_lang, args.target_lang, args.domain)
        else:
            segments = read_txt_input(input_path, args.source_lang, args.target_lang, args.domain)
    except Exception as e:
        print(json.dumps({"error": str(e), "code": "FILE_PARSE_ERROR"}), file=sys.stderr)
        sys.exit(1)

    total = len(segments)
    all_results = []
    failures = []

    # Group by lang pair for coherent batching
    groups = group_segments_by_lang_pair([s for s in segments if not s.get("skip")])

    for (src, tgt, dom), group_segs in groups.items():
        # Split into batches
        for batch_start in range(0, len(group_segs), args.batch_size):
            batch = group_segs[batch_start: batch_start + args.batch_size]
            try:
                results = translate_batch_with_claude(batch)
                all_results.extend(results)
            except Exception as e:
                for seg in batch:
                    failures.append({"id": seg["id"], "error": str(e)})
                    all_results.append({
                        "id": seg["id"],
                        "source_text": seg["source_text"],
                        "translated_text": "",
                        "error": str(e),
                        "source_lang": src,
                        "target_lang": tgt,
                        "domain": dom,
                    })

    # Add skipped (empty) lines back
    skipped = [s for s in segments if s.get("skip")]
    for s in skipped:
        all_results.append({
            "id": s["id"],
            "source_text": "",
            "translated_text": "",
            "source_lang": args.source_lang,
            "target_lang": args.target_lang,
            "domain": args.domain,
        })

    # Sort by ID (string sort, works for numeric IDs from TXT)
    try:
        all_results.sort(key=lambda r: int(r["id"]))
    except ValueError:
        all_results.sort(key=lambda r: r["id"])

    # Write output CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "source_lang", "target_lang", "domain", "source_text", "translated_text"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    summary = {
        "total": total,
        "succeeded": total - len(failures),
        "failed": len(failures),
        "output_file": str(output_path),
        "failures": failures,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
