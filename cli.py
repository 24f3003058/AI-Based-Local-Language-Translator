#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-Based Local Language Translator with Context
Main CLI entry point — orchestrates all tools per WAT framework.

Usage:
    python cli.py interactive
    python cli.py batch --input my_file.csv --target-lang ta --domain legal
    python cli.py glossary --action add
    python cli.py glossary --action list [--domain medical]
    python cli.py session --action list
    python cli.py session --action resume --id abc
    python cli.py session --action delete --id abc
    python cli.py detect --text "some text"
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

# Ensure UTF-8 output on Windows for Indian language scripts
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # Will fail later with a helpful message at API call time

SUPPORTED_LANGS = {
    "hi": "Hindi", "ta": "Tamil", "bn": "Bengali", "te": "Telugu",
    "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "or": "Odia", "en": "English",
}
SUPPORTED_DOMAINS = ["casual", "medical", "legal", "technical", "religious"]


def print_header():
    try:
        from rich.console import Console
        from rich.text import Text
        console = Console()
        console.print("\n[bold blue]╔══════════════════════════════════════════════════╗[/bold blue]")
        console.print("[bold blue]║   AI Local Language Translator with Context      ║[/bold blue]")
        console.print("[bold blue]╚══════════════════════════════════════════════════╝[/bold blue]\n")
        lang_list = " | ".join([f"[cyan]{k}[/cyan]({v})" for k, v in SUPPORTED_LANGS.items()])
        console.print(f"Supported: {lang_list}\n")
    except ImportError:
        print("\n" + "="*52)
        print("  AI Local Language Translator with Context")
        print("="*52)
        print(f"Supported: {', '.join([f'{k}({v})' for k, v in SUPPORTED_LANGS.items()])}\n")


def prompt_user(prompt: str, default: str = None) -> str:
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    try:
        value = input(full_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        sys.exit(0)
    return value if value else (default or "")


def validate_lang(code: str) -> bool:
    from tools.validate_languages import validate_language
    result = validate_language(code)
    return result.get("valid", False)


def validate_domain(domain: str) -> bool:
    return domain in SUPPORTED_DOMAINS


def run_interactive(args):
    """Interactive translation session with context."""
    from tools.translate_text import translate
    from tools.manage_context import action_new, action_append, action_load, action_summarize, load_session, save_session
    from tools.detect_language import detect_language
    from tools.format_output import mode_cli
    from tools.manage_glossary import action_lookup

    print_header()

    # Determine session
    session_id = getattr(args, "id", None)
    if session_id:
        print(f"Resuming session: {session_id}")
        session_data = load_session(session_id)
        if "error" in session_data:
            print(f"Session not found: {session_id}. Starting new session.")
            session_id = None

    if not session_id:
        # Gather parameters
        print("Starting new translation session.\n")
        target_lang = prompt_user("Target language code (e.g. hi, ta, en)", os.getenv("DEFAULT_TARGET_LANG", "hi"))
        while not validate_lang(target_lang):
            print(f"  Unsupported: {target_lang}. Options: {', '.join(SUPPORTED_LANGS.keys())}")
            target_lang = prompt_user("Target language code")

        source_lang = prompt_user("Source language code (or 'auto' to detect)", "auto")
        if source_lang != "auto" and not validate_lang(source_lang):
            print(f"  Unsupported source lang. Using 'auto'.")
            source_lang = "auto"

        domain = prompt_user("Domain (casual/medical/legal/technical/religious)", os.getenv("DEFAULT_DOMAIN", "casual"))
        if not validate_domain(domain):
            print(f"  Invalid domain. Using 'casual'.")
            domain = "casual"

        session_id = str(uuid.uuid4())[:8]

        # Create mock args for action_new
        class NewArgs:
            pass
        new_args = NewArgs()
        new_args.session_id = session_id
        new_args.source_lang = source_lang
        new_args.target_lang = target_lang
        new_args.domain = domain

        from tools.manage_context import action_new
        session_data = action_new(new_args)
        print(f"\nSession ID: [bold]{session_id}[/bold] (use to resume later)")
        print(f"Translating: {source_lang} → {target_lang} | Domain: {domain}")
        print("Type your text and press Enter. Type 'quit' or 'exit' to end.\n")

    else:
        source_lang = session_data.get("source_lang", "auto")
        target_lang = session_data.get("target_lang", "hi")
        domain = session_data.get("domain", "casual")
        print(f"Session: {source_lang} → {target_lang} | Domain: {domain}")
        print("Type your text and press Enter. Type 'quit' or 'exit' to end.\n")

    # Interactive loop
    exchange_count = 0
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            break

        # Detect source language if auto
        actual_source = source_lang
        if source_lang == "auto":
            detection = detect_language(text)
            if detection.get("supported"):
                actual_source = detection["detected_lang"]
                print(f"  [Detected: {SUPPORTED_LANGS.get(actual_source, actual_source)}]")
            else:
                print(f"  [Could not detect language. Defaulting to 'en']")
                actual_source = "en"

        if actual_source == target_lang:
            print("  Source and target language are the same. Skipping translation.\n")
            continue

        # Translate
        result = translate(
            text=text,
            source_lang=actual_source,
            target_lang=target_lang,
            domain=domain,
            session_id=session_id,
        )

        if "error" in result:
            print(f"  Error: {result['error']}\n")
            continue

        # Display result
        mode_cli(result)

        # Save to context
        class AppendArgs:
            pass

        u_args = AppendArgs()
        u_args.session_id = session_id
        u_args.role = "user"
        u_args.text = text

        a_args = AppendArgs()
        a_args.session_id = session_id
        a_args.role = "assistant"
        a_args.text = result["translated_text"]

        append_result = action_append(u_args)
        action_append(a_args)

        exchange_count += 1

        # Auto-summarize if needed
        if append_result.get("needs_summarize"):
            print("  [Summarizing older context to keep memory lean...]\n")

            class SumArgs:
                pass
            s_args = SumArgs()
            s_args.session_id = session_id
            action_summarize(s_args)

    print(f"\nSession ended. {exchange_count} exchange(s). Session ID: {session_id}")
    print("Resume with: python cli.py interactive --id", session_id)


def run_batch(args):
    """Batch translation from file."""
    import subprocess

    if not args.input:
        print("Error: --input file required for batch mode.")
        sys.exit(1)
    if not args.target_lang:
        print("Error: --target-lang required for batch mode.")
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    output_path = Path(".tmp/batch_output") / f"{input_path.stem}_translated.csv"
    domain = getattr(args, "domain", "casual") or "casual"
    source_lang = getattr(args, "source_lang", "en") or "en"

    print(f"Batch translating: {args.input}")
    print(f"Target: {SUPPORTED_LANGS.get(args.target_lang, args.target_lang)} | Domain: {domain}")
    print(f"Output: {output_path}\n")

    from tools.translate_batch import main as batch_main

    # Directly call the batch tool
    sys.argv = [
        "translate_batch.py",
        "--input-file", str(input_path),
        "--output-file", str(output_path),
        "--source-lang", source_lang,
        "--target-lang", args.target_lang,
        "--domain", domain,
    ]
    batch_main()


def run_glossary(args):
    """Glossary management."""
    from tools.manage_glossary import (
        action_add, action_lookup, action_list, action_delete, action_import, action_export
    )

    action = getattr(args, "action", None)
    if not action:
        print("Error: --action required (add/list/delete/import/export)")
        sys.exit(1)

    actions = {
        "add": action_add,
        "lookup": action_lookup,
        "list": action_list,
        "delete": action_delete,
        "import": action_import,
        "export": action_export,
    }

    if action == "add":
        # Interactive add if missing fields
        if not args.source_lang:
            args.source_lang = prompt_user("Source language code")
        if not args.source_term:
            args.source_term = prompt_user("Source term")
        if not args.target_lang:
            args.target_lang = prompt_user("Target language code")
        if not args.target_term:
            args.target_term = prompt_user("Target term (translation)")
        if not args.domain:
            args.domain = prompt_user("Domain (casual/medical/legal/technical/religious)", "casual")
        if not args.notes:
            args.notes = prompt_user("Notes (optional)", "")

    result = actions[action](args)

    if isinstance(result, dict) and "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    if action == "list":
        if not result:
            print("No glossary entries found.")
            return
        try:
            from rich.console import Console
            from rich.table import Table
            console = Console()
            table = Table(show_header=True, header_style="bold magenta", title="Glossary Entries")
            table.add_column("ID", width=10)
            table.add_column("Source Lang", width=8)
            table.add_column("Source Term", style="white")
            table.add_column("Target Lang", width=8)
            table.add_column("Target Term", style="green")
            table.add_column("Domain", width=10)
            table.add_column("Uses", width=5)
            for e in result:
                table.add_row(
                    e["id"][:8], e["source_lang"], e["source_term"],
                    e["target_lang"], e["target_term"], e["domain"], str(e.get("use_count", 0))
                )
            console.print(table)
        except ImportError:
            for e in result:
                print(f"[{e['id'][:8]}] {e['source_lang']}:{e['source_term']} → {e['target_lang']}:{e['target_term']} ({e['domain']})")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def run_session(args):
    """Session management."""
    from tools.manage_context import action_list, action_delete

    action = getattr(args, "action", "list")

    if action == "list":
        class ListArgs:
            pass
        sessions = action_list(ListArgs())
        if not sessions:
            print("No sessions found.")
            return
        try:
            from rich.console import Console
            from rich.table import Table
            console = Console()
            table = Table(show_header=True, header_style="bold cyan", title="Translation Sessions")
            table.add_column("Session ID", style="cyan")
            table.add_column("Source", width=8)
            table.add_column("Target", width=8)
            table.add_column("Domain", width=10)
            table.add_column("Exchanges", width=9)
            table.add_column("Created")
            for s in sessions:
                table.add_row(
                    s["session_id"], s["source_lang"], s["target_lang"],
                    s["domain"], str(s["history_length"]), s["created_at"][:19]
                )
            console.print(table)
        except ImportError:
            for s in sessions:
                print(f"[{s['session_id']}] {s['source_lang']}→{s['target_lang']} | {s['domain']} | {s['history_length']} exchanges")

        print("\nResume with: python cli.py interactive --id <session-id>")

    elif action == "resume":
        session_id = getattr(args, "id", None)
        if not session_id:
            print("Error: --id required for resume")
            sys.exit(1)
        # Launch interactive with session
        args.id = session_id
        run_interactive(args)

    elif action == "delete":
        session_id = getattr(args, "id", None)
        if not session_id:
            print("Error: --id required for delete")
            sys.exit(1)

        class DelArgs:
            pass
        d = DelArgs()
        d.session_id = session_id
        result = action_delete(d)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Deleted session: {session_id}")


def run_detect(args):
    """Language detection."""
    from tools.detect_language import detect_language
    if not args.text:
        print("Error: --text required")
        sys.exit(1)
    result = detect_language(args.text)
    lang_name = SUPPORTED_LANGS.get(result.get("detected_lang", ""), result.get("detected_lang", "Unknown"))
    print(f"Detected: {lang_name} ({result.get('detected_lang', '?')}) | Confidence: {result.get('confidence', 0):.2%} | Method: {result.get('method', '?')}")
    if not result.get("supported"):
        print(f"Warning: {result.get('error', 'Language not supported')}")


def main():
    parser = argparse.ArgumentParser(
        description="AI-Based Local Language Translator with Context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py interactive
  python cli.py interactive --id abc123
  python cli.py batch --input input.csv --target-lang ta --domain legal
  python cli.py batch --input sentences.txt --target-lang hi --source-lang en --domain medical
  python cli.py glossary --action add
  python cli.py glossary --action list --domain medical
  python cli.py glossary --action delete --entry-id <id>
  python cli.py glossary --action import --file my_terms.csv
  python cli.py glossary --action export --output-file exported.csv
  python cli.py session --action list
  python cli.py session --action resume --id abc123
  python cli.py session --action delete --id abc123
  python cli.py detect --text "यह एक परीक्षण है"
        """
    )

    subparsers = parser.add_subparsers(dest="command")

    # Interactive
    p_interactive = subparsers.add_parser("interactive", help="Start an interactive translation session")
    p_interactive.add_argument("--id", help="Resume existing session by ID")

    # Batch
    p_batch = subparsers.add_parser("batch", help="Batch translate from file")
    p_batch.add_argument("--input", required=True, help="Input CSV or TXT file")
    p_batch.add_argument("--target-lang", required=True, help="Target language code")
    p_batch.add_argument("--source-lang", default="en", help="Source language code (default: en)")
    p_batch.add_argument("--domain", default="casual", help="Domain context")
    p_batch.add_argument("--batch-size", type=int, default=10, help="Segments per API call")

    # Glossary
    p_glossary = subparsers.add_parser("glossary", help="Manage translation glossary")
    p_glossary.add_argument("--action", required=True, choices=["add", "lookup", "list", "delete", "import", "export"])
    p_glossary.add_argument("--source-lang")
    p_glossary.add_argument("--source-term")
    p_glossary.add_argument("--target-lang")
    p_glossary.add_argument("--target-term")
    p_glossary.add_argument("--domain")
    p_glossary.add_argument("--notes")
    p_glossary.add_argument("--entry-id")
    p_glossary.add_argument("--file")
    p_glossary.add_argument("--output-file")
    p_glossary.add_argument("--text")

    # Session
    p_session = subparsers.add_parser("session", help="Manage translation sessions")
    p_session.add_argument("--action", required=True, choices=["list", "resume", "delete"])
    p_session.add_argument("--id", help="Session ID")

    # Detect
    p_detect = subparsers.add_parser("detect", help="Detect language of text")
    p_detect.add_argument("--text", required=True, help="Text to detect language for")

    args = parser.parse_args()

    if not args.command:
        print_header()
        parser.print_help()
        sys.exit(0)

    commands = {
        "interactive": run_interactive,
        "batch": run_batch,
        "glossary": run_glossary,
        "session": run_session,
        "detect": run_detect,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
