#!/usr/bin/env python3
"""
Core single-text translation via Claude API.
Handles context injection, glossary constraints, and domain-specific prompting.

Usage:
    python tools/translate_text.py
        --text "यह एक परीक्षण है"
        --source-lang hi
        --target-lang ta
        --domain medical
        --session-id abc          (optional: load conversation context)
        --glossary-file data/glossary.json  (optional)
"""

import argparse
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


DOMAIN_INSTRUCTIONS = {
    "casual": (
        "Use everyday conversational language. Prefer common vocabulary. "
        "Mirror the informal tone of the original text. "
        "Avoid overly formal or archaic expressions."
    ),
    "medical": (
        "Use clinical medical terminology as used in Indian medical institutions. "
        "Do NOT simplify technical terms — preserve drug names, anatomical terms, "
        "and procedure names exactly. Use the same register as a doctor would use "
        "when speaking to colleagues."
    ),
    "legal": (
        "Use formal legal language. Preserve legal terms of art. "
        "Where a direct equivalent exists in the target language, use it. "
        "If no direct equivalent exists, transliterate and add a parenthetical explanation. "
        "Maintain the formal register throughout."
    ),
    "technical": (
        "Use precise technical vocabulary. Prefer established translated terms "
        "from Indian technical education contexts (IIT/NIT syllabi) where available. "
        "Do not simplify technical concepts."
    ),
    "religious": (
        "Use traditional scriptural register. Preserve Sanskrit-origin terms in their "
        "established form in the target language. Use respectful, elevated language "
        "appropriate for religious texts."
    ),
}

SCRIPT_INSTRUCTIONS = {
    "hi": "Output must use Devanagari script. Do not use romanized transliteration.",
    "mr": "Output must use Devanagari script. Do not use romanized transliteration.",
    "ta": "Output must use Tamil script. Do not use romanized transliteration.",
    "bn": "Output must use Bengali script. Do not use romanized transliteration.",
    "te": "Output must use Telugu script. Do not use romanized transliteration.",
    "gu": "Output must use Gujarati script. Do not use romanized transliteration.",
    "kn": "Output must use Kannada script. Do not use romanized transliteration.",
    "ml": "Output must use Malayalam script. Do not use romanized transliteration.",
    "pa": "Output must use Gurmukhi (Punjabi) script. Do not use romanized transliteration.",
    "or": "Output must use Odia script. Do not use romanized transliteration.",
    "en": "Output must use the Latin alphabet.",
}


def build_system_prompt(source_lang: str, target_lang: str, domain: str, glossary_matches: list, summary: str) -> str:
    domain_instruction = DOMAIN_INSTRUCTIONS.get(domain, DOMAIN_INSTRUCTIONS["casual"])
    script_instruction = SCRIPT_INSTRUCTIONS.get(target_lang, "")

    glossary_constraints = ""
    if glossary_matches:
        constraints = [
            f'  - You MUST translate the term "{e["source_term"]}" as "{e["target_term"]}"'
            for e in glossary_matches
        ]
        glossary_constraints = "\n\nMandatory term overrides (apply these exactly):\n" + "\n".join(constraints)

    context_summary = ""
    if summary:
        context_summary = f"\n\nConversation context (summary of prior exchanges):\n{summary}"

    return f"""You are an expert translator specializing in Indian languages.

Task: Translate text from {source_lang.upper()} to {target_lang.upper()}.

Domain: {domain.upper()}
{domain_instruction}

Script requirement: {script_instruction}

Rules:
1. Translate ONLY the text. Do not explain, add comments, or add transliterations unless asked.
2. Preserve the original meaning, tone, and nuance faithfully.
3. Output ONLY the translated text — nothing else.{context_summary}{glossary_constraints}"""


def build_messages(history: list, text: str) -> list:
    """Build Claude messages array from session history + new user turn."""
    messages = []

    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("text", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": text})
    return messages


def load_session_context(session_id: str) -> tuple[list, str]:
    """Load history and summary from a session file. Returns (history, summary)."""
    session_file = PROJECT_ROOT / ".tmp" / "context_sessions" / f"session_{session_id}.json"
    if not session_file.exists():
        return [], ""

    with open(session_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    history = data.get("history", [])
    summary = data.get("summary", "")
    return history, summary


def load_glossary_matches(text: str, source_lang: str, target_lang: str, domain: str) -> list:
    """Find glossary entries relevant to the input text."""
    glossary_file = PROJECT_ROOT / "data" / "glossary.json"
    if not glossary_file.exists():
        return []

    with open(glossary_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    text_lower = text.lower()
    matches = []
    for entry in data.get("entries", []):
        if entry["source_lang"] != source_lang:
            continue
        if entry["target_lang"] != target_lang:
            continue
        if domain != "casual" and entry["domain"] not in (domain, "casual"):
            continue
        if entry["source_term"].lower() in text_lower:
            matches.append(entry)

    return matches


def translate(text: str, source_lang: str, target_lang: str, domain: str, session_id: str = None) -> dict:
    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError as e:
        return {"error": f"Missing dependency: {e}. Run: pip install anthropic python-dotenv", "code": "IMPORT_ERROR"}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return {"error": "ANTHROPIC_API_KEY not set in .env file.", "code": "API_KEY_MISSING"}

    # Load context
    history, summary = load_session_context(session_id) if session_id else ([], "")

    # Load glossary matches
    glossary_matches = load_glossary_matches(text, source_lang, target_lang, domain)

    # Build prompt
    system_prompt = build_system_prompt(source_lang, target_lang, domain, glossary_matches, summary)
    messages = build_messages(history, text)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )

        translated_text = response.content[0].text.strip()
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        return {
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "domain": domain,
            "original_text": text,
            "tokens_used": tokens_used,
            "glossary_applied": len(glossary_matches),
            "session_id": session_id,
        }

    except anthropic.APIStatusError as e:
        if e.status_code == 429:
            return {"error": "Rate limit reached. Please wait and try again.", "code": "RATE_LIMITED"}
        return {"error": f"API error: {e.message}", "code": "API_ERROR"}
    except Exception as e:
        return {"error": str(e), "code": "API_ERROR"}


def main():
    parser = argparse.ArgumentParser(description="Translate text using Claude API")
    parser.add_argument("--text", required=True, help="Text to translate")
    parser.add_argument("--source-lang", required=True, help="Source language code (e.g. hi, en)")
    parser.add_argument("--target-lang", required=True, help="Target language code (e.g. ta, bn)")
    parser.add_argument("--domain", default="casual", help="Domain context (casual/medical/legal/technical/religious)")
    parser.add_argument("--session-id", help="Session ID for context continuity")
    args = parser.parse_args()

    result = translate(
        text=args.text,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        domain=args.domain,
        session_id=args.session_id,
    )

    if "error" in result:
        print(json.dumps(result), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
