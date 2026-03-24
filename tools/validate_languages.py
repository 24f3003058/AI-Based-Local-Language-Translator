#!/usr/bin/env python3
"""
Validate language codes/names and domain labels against supported list.

Usage:
    python tools/validate_languages.py --lang hi
    python tools/validate_languages.py --lang "Hindi"
    python tools/validate_languages.py --domain medical
"""

import argparse
import json
import sys
from pathlib import Path

LANGUAGES_FILE = Path(__file__).parent.parent / "data" / "languages.json"


def load_languages():
    with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_language(lang_input: str) -> dict:
    data = load_languages()
    lang_lower = lang_input.strip().lower()

    for lang in data["languages"]:
        if (
            lang["code"] == lang_lower
            or lang["name"].lower() == lang_lower
            or lang_lower in [a.lower() for a in lang["aliases"]]
        ):
            return {
                "valid": True,
                "code": lang["code"],
                "name": lang["name"],
                "script": lang["script"],
            }

    return {
        "valid": False,
        "input": lang_input,
        "error": f"Language '{lang_input}' is not supported.",
        "supported": [l["code"] for l in data["languages"]],
    }


def validate_domain(domain_input: str) -> dict:
    data = load_languages()
    domain_lower = domain_input.strip().lower()

    if domain_lower in data["domains"]:
        return {"valid": True, "domain": domain_lower}

    return {
        "valid": False,
        "input": domain_input,
        "error": f"Domain '{domain_input}' is not supported.",
        "supported": data["domains"],
    }


def get_all_languages() -> list:
    data = load_languages()
    return data["languages"]


def main():
    parser = argparse.ArgumentParser(description="Validate language codes and domains")
    parser.add_argument("--lang", help="Language code or name to validate")
    parser.add_argument("--domain", help="Domain label to validate")
    args = parser.parse_args()

    if not args.lang and not args.domain:
        print(json.dumps({"error": "Provide --lang or --domain", "code": "MISSING_ARGS"}), file=sys.stderr)
        sys.exit(1)

    if args.lang:
        result = validate_language(args.lang)
        print(json.dumps(result))
        sys.exit(0 if result["valid"] else 1)

    if args.domain:
        result = validate_domain(args.domain)
        print(json.dumps(result))
        sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
