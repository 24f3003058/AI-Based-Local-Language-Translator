#!/usr/bin/env python3
"""
Detect the language of input text using langdetect (offline, no API cost).
Falls back to Claude if confidence is below threshold.

Usage:
    python tools/detect_language.py --text "यह एक परीक्षण है"
    python tools/detect_language.py --text "Hello world"
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

CONFIDENCE_THRESHOLD = 0.85
SUPPORTED_CODES = {"hi", "ta", "bn", "te", "mr", "gu", "kn", "ml", "pa", "or", "en"}

# langdetect -> our code mapping
LANGDETECT_MAP = {
    "hi": "hi",
    "ta": "ta",
    "bn": "bn",
    "te": "te",
    "mr": "mr",
    "gu": "gu",
    "kn": "kn",
    "ml": "ml",
    "pa": "pa",
    "or": "or",
    "en": "en",
}


def detect_with_langdetect(text: str) -> tuple[str, float]:
    """Returns (lang_code, confidence). Raises ImportError if not installed."""
    from langdetect import detect_langs

    results = detect_langs(text)
    if not results:
        return "unknown", 0.0

    top = results[0]
    lang_code = top.lang
    confidence = top.prob
    return lang_code, confidence


def detect_with_claude(text: str) -> dict:
    """Fallback: ask Claude to identify the language."""
    try:
        import anthropic
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {"detected_lang": "unknown", "confidence": 0.0, "method": "claude_fallback_failed", "supported": False}

        client = anthropic.Anthropic(api_key=api_key)
        supported_list = ", ".join(SUPPORTED_CODES)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Identify the language of this text. Reply with ONLY the ISO 639-1 language code "
                        f"(e.g. 'hi', 'ta', 'en'). Supported codes: {supported_list}. "
                        f"If the language is not in the supported list, reply 'unknown'.\n\nText: {text}"
                    ),
                }
            ],
        )
        detected = response.content[0].text.strip().lower()
        code = LANGDETECT_MAP.get(detected, detected)
        supported = code in SUPPORTED_CODES
        return {
            "detected_lang": code,
            "confidence": 0.90,
            "method": "claude_fallback",
            "supported": supported,
        }
    except Exception as e:
        return {
            "detected_lang": "unknown",
            "confidence": 0.0,
            "method": "claude_fallback_failed",
            "supported": False,
            "error": str(e),
        }


def detect_language(text: str) -> dict:
    if not text or len(text.strip()) < 3:
        return {
            "detected_lang": "unknown",
            "confidence": 0.0,
            "method": "too_short",
            "supported": False,
            "error": "Text too short to detect language reliably.",
        }

    try:
        raw_code, confidence = detect_with_langdetect(text)
        mapped_code = LANGDETECT_MAP.get(raw_code, raw_code)
        supported = mapped_code in SUPPORTED_CODES

        if confidence >= CONFIDENCE_THRESHOLD and supported:
            return {
                "detected_lang": mapped_code,
                "confidence": round(confidence, 4),
                "method": "langdetect",
                "supported": True,
            }

        # Low confidence or unsupported — try Claude fallback
        if confidence < CONFIDENCE_THRESHOLD:
            return detect_with_claude(text)

        # Supported detection but code not in our list
        return {
            "detected_lang": mapped_code,
            "confidence": round(confidence, 4),
            "method": "langdetect",
            "supported": False,
            "error": f"Detected language '{mapped_code}' is not in the supported language list.",
        }

    except ImportError:
        # langdetect not installed — go straight to Claude
        return detect_with_claude(text)
    except Exception as e:
        return {
            "detected_lang": "unknown",
            "confidence": 0.0,
            "method": "error",
            "supported": False,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Detect language of input text")
    parser.add_argument("--text", required=True, help="Text to detect language for")
    args = parser.parse_args()

    result = detect_language(args.text)
    print(json.dumps(result))
    sys.exit(0 if result.get("supported") else 1)


if __name__ == "__main__":
    main()
