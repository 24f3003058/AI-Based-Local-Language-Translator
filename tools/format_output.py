#!/usr/bin/env python3
"""
Format translation results for CLI display or file output.
Separates presentation logic from translation logic.

Usage:
    python tools/format_output.py --mode cli   --input-json '{"translated_text": "...", ...}'
    python tools/format_output.py --mode file  --input-file result.json --output-file result.csv
    python tools/format_output.py --mode table --input-file result.json
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

LANG_NAMES = {
    "hi": "Hindi", "ta": "Tamil", "bn": "Bengali", "te": "Telugu",
    "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "or": "Odia", "en": "English",
}


def get_lang_name(code: str) -> str:
    return LANG_NAMES.get(code, code.upper())


def mode_cli(data: dict):
    """Render a styled panel in the terminal."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from rich import box

        console = Console()
        src = get_lang_name(data.get("source_lang", "?"))
        tgt = get_lang_name(data.get("target_lang", "?"))
        domain = data.get("domain", "casual").upper()
        tokens = data.get("tokens_used", "?")
        glossary = data.get("glossary_applied", 0)

        original = data.get("original_text", "")
        translated = data.get("translated_text", "")

        header = f"[bold cyan]{src}[/bold cyan] → [bold green]{tgt}[/bold green]  [dim]| Domain: {domain} | Tokens: {tokens}"
        if glossary:
            header += f" | Glossary terms: {glossary}[/dim]"
        else:
            header += "[/dim]"

        content = Text()
        content.append("Original:\n", style="bold dim")
        content.append(original + "\n\n", style="white")
        content.append("Translation:\n", style="bold green")
        content.append(translated, style="bold white")

        console.print(Panel(content, title=header, border_style="blue", box=box.ROUNDED))

    except ImportError:
        # Fallback: plain text output
        src = get_lang_name(data.get("source_lang", "?"))
        tgt = get_lang_name(data.get("target_lang", "?"))
        print(f"\n{'='*60}")
        print(f"  {src} → {tgt}  |  Domain: {data.get('domain', '?').upper()}")
        print(f"{'='*60}")
        print(f"Original:    {data.get('original_text', '')}")
        print(f"Translation: {data.get('translated_text', '')}")
        print(f"Tokens used: {data.get('tokens_used', '?')}")
        if data.get("glossary_applied"):
            print(f"Glossary terms applied: {data['glossary_applied']}")
        print(f"{'='*60}\n")


def mode_table(data_list: list):
    """Render a comparison table."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Source", style="white")
        table.add_column("Target Lang", style="cyan", width=10)
        table.add_column("Translation", style="green")

        for item in data_list:
            table.add_row(
                str(item.get("id", "")),
                item.get("source_text", ""),
                get_lang_name(item.get("target_lang", "")),
                item.get("translated_text", ""),
            )

        console.print(table)

    except ImportError:
        print("ID | Source | Target | Translation")
        print("-" * 60)
        for item in data_list:
            print(f"{item.get('id','')} | {item.get('source_text','')} | "
                  f"{get_lang_name(item.get('target_lang',''))} | {item.get('translated_text','')}")


def mode_file(data_list: list, output_file: str):
    """Write results to CSV."""
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["id", "source_lang", "target_lang", "domain", "source_text", "translated_text"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in data_list:
            writer.writerow({k: item.get(k, "") for k in fieldnames})

    print(json.dumps({"success": True, "output_file": str(path), "rows": len(data_list)}))


def main():
    parser = argparse.ArgumentParser(description="Format translation output")
    parser.add_argument("--mode", required=True, choices=["cli", "file", "table"])
    parser.add_argument("--input-json", help="JSON string (for cli mode)")
    parser.add_argument("--input-file", help="JSON file path (for file/table mode)")
    parser.add_argument("--output-file", help="Output CSV path (for file mode)")
    args = parser.parse_args()

    if args.mode == "cli":
        if not args.input_json:
            print(json.dumps({"error": "Missing --input-json for cli mode"}), file=sys.stderr)
            sys.exit(1)
        data = json.loads(args.input_json)
        mode_cli(data)

    elif args.mode == "table":
        if not args.input_file:
            print(json.dumps({"error": "Missing --input-file for table mode"}), file=sys.stderr)
            sys.exit(1)
        with open(args.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data_list = data if isinstance(data, list) else [data]
        mode_table(data_list)

    elif args.mode == "file":
        if not args.input_file or not args.output_file:
            print(json.dumps({"error": "Missing --input-file or --output-file for file mode"}), file=sys.stderr)
            sys.exit(1)
        with open(args.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data_list = data if isinstance(data, list) else [data]
        mode_file(data_list, args.output_file)


if __name__ == "__main__":
    main()
