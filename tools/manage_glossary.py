#!/usr/bin/env python3
"""
CRUD operations on the translation memory/glossary stored in data/glossary.json.

Usage:
    python tools/manage_glossary.py --action add
        --source-lang en --source-term "myocardial infarction"
        --target-lang hi --target-term "हृदयाघात"
        --domain medical --notes "Standard AIIMS terminology"

    python tools/manage_glossary.py --action lookup
        --source-lang en --target-lang hi --domain medical
        --text "The patient had a myocardial infarction"

    python tools/manage_glossary.py --action list [--domain medical] [--source-lang en]
    python tools/manage_glossary.py --action delete --entry-id <uuid>
    python tools/manage_glossary.py --action import --file my_terms.csv
    python tools/manage_glossary.py --action export --output-file my_terms.csv
"""

import argparse
import csv
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

GLOSSARY_FILE = Path(__file__).parent.parent / "data" / "glossary.json"


def load_glossary() -> dict:
    if not GLOSSARY_FILE.exists():
        return {"entries": []}
    with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_glossary(data: dict):
    with open(GLOSSARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def action_add(args) -> dict:
    required = ["source_lang", "source_term", "target_lang", "target_term", "domain"]
    for field in required:
        if not getattr(args, field, None):
            return {"error": f"Missing required field: --{field.replace('_', '-')}", "code": "MISSING_ARGS"}

    data = load_glossary()
    entry = {
        "id": str(uuid.uuid4()),
        "source_lang": args.source_lang,
        "source_term": args.source_term,
        "target_lang": args.target_lang,
        "target_term": args.target_term,
        "domain": args.domain,
        "notes": args.notes or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "use_count": 0,
    }
    data["entries"].append(entry)
    save_glossary(data)
    return {"success": True, "entry": entry}


def action_lookup(args) -> list:
    if not args.text:
        return []

    data = load_glossary()
    text_lower = args.text.lower()
    matches = []

    for entry in data["entries"]:
        # Filter by language pair
        if args.source_lang and entry["source_lang"] != args.source_lang:
            continue
        if args.target_lang and entry["target_lang"] != args.target_lang:
            continue
        # Filter by domain (domain "casual" matches everything; specific domains are strict)
        if args.domain and args.domain != "casual" and entry["domain"] not in (args.domain, "casual"):
            continue
        # Check if term appears in text
        if entry["source_term"].lower() in text_lower:
            matches.append(entry)
            # Increment use count
            entry["use_count"] = entry.get("use_count", 0) + 1

    if matches:
        save_glossary(data)

    return matches


def action_list(args) -> list:
    data = load_glossary()
    entries = data["entries"]

    if args.domain:
        entries = [e for e in entries if e["domain"] == args.domain]
    if args.source_lang:
        entries = [e for e in entries if e["source_lang"] == args.source_lang]
    if args.target_lang:
        entries = [e for e in entries if e["target_lang"] == args.target_lang]

    return entries


def action_delete(args) -> dict:
    if not args.entry_id:
        return {"error": "Missing --entry-id", "code": "MISSING_ARGS"}

    data = load_glossary()
    original_count = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["id"] != args.entry_id]

    if len(data["entries"]) == original_count:
        return {"error": f"Entry '{args.entry_id}' not found.", "code": "GLOSSARY_NOT_FOUND"}

    save_glossary(data)
    return {"success": True, "deleted_id": args.entry_id}


def action_import(args) -> dict:
    if not args.file:
        return {"error": "Missing --file", "code": "MISSING_ARGS"}

    file_path = Path(args.file)
    if not file_path.exists():
        return {"error": f"File not found: {args.file}", "code": "FILE_NOT_FOUND"}

    data = load_glossary()
    added = 0
    errors = []

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            required_cols = {"source_lang", "source_term", "target_lang", "target_term", "domain"}
            if not required_cols.issubset(row.keys()):
                errors.append(f"Row {i+1}: missing required columns")
                continue

            entry = {
                "id": str(uuid.uuid4()),
                "source_lang": row["source_lang"].strip(),
                "source_term": row["source_term"].strip(),
                "target_lang": row["target_lang"].strip(),
                "target_term": row["target_term"].strip(),
                "domain": row["domain"].strip(),
                "notes": row.get("notes", "").strip(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "use_count": 0,
            }
            data["entries"].append(entry)
            added += 1

    save_glossary(data)
    return {"success": True, "added": added, "errors": errors}


def action_export(args) -> dict:
    output_path = Path(args.output_file) if args.output_file else Path("glossary_export.csv")
    data = load_glossary()

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "source_lang", "source_term", "target_lang", "target_term", "domain", "notes", "created_at", "use_count"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in data["entries"]:
            writer.writerow({k: entry.get(k, "") for k in fieldnames})

    return {"success": True, "output_file": str(output_path), "total_entries": len(data["entries"])}


def main():
    parser = argparse.ArgumentParser(description="Manage translation glossary")
    parser.add_argument("--action", required=True, choices=["add", "lookup", "list", "delete", "import", "export"])
    parser.add_argument("--source-lang")
    parser.add_argument("--source-term")
    parser.add_argument("--target-lang")
    parser.add_argument("--target-term")
    parser.add_argument("--domain")
    parser.add_argument("--notes")
    parser.add_argument("--text", help="Input text for lookup action")
    parser.add_argument("--entry-id", help="Entry ID for delete action")
    parser.add_argument("--file", help="CSV file for import action")
    parser.add_argument("--output-file", help="Output CSV for export action")
    args = parser.parse_args()

    # Normalize dashes to underscores for attribute access
    if hasattr(args, "source_lang") and args.source_lang is None:
        pass  # already None

    actions = {
        "add": action_add,
        "lookup": action_lookup,
        "list": action_list,
        "delete": action_delete,
        "import": action_import,
        "export": action_export,
    }

    result = actions[args.action](args)

    if isinstance(result, dict) and "error" in result:
        print(json.dumps(result), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
