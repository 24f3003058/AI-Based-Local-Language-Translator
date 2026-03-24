#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask web server for AI Local Language Translator.
Provides REST API consumed by the frontend.
"""

import json
import os
import sys
import uuid
from pathlib import Path

# UTF-8 for Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.validate_languages import validate_language, validate_domain, get_all_languages
from tools.detect_language import detect_language
from tools.translate_text import translate
from tools.manage_glossary import (
    action_add, action_list, action_delete, action_lookup, load_glossary, save_glossary
)
from tools.manage_context import (
    action_new, action_load, action_append, action_list as list_sessions,
    action_delete as delete_session, action_summarize, load_session
)

app = Flask(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def err(msg, code=400):
    return jsonify({"error": msg}), code


def ok(data):
    return jsonify(data)


# ── pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── languages ─────────────────────────────────────────────────────────────────

@app.route("/api/languages")
def api_languages():
    langs = get_all_languages()
    return ok({"languages": langs, "domains": ["casual", "medical", "legal", "technical", "religious"]})


# ── detect ────────────────────────────────────────────────────────────────────

@app.route("/api/detect", methods=["POST"])
def api_detect():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return err("text is required")
    result = detect_language(text)
    return ok(result)


# ── translate ─────────────────────────────────────────────────────────────────

@app.route("/api/translate", methods=["POST"])
def api_translate():
    data = request.get_json(force=True)
    text        = (data.get("text") or "").strip()
    source_lang = (data.get("source_lang") or "auto").strip()
    target_lang = (data.get("target_lang") or "").strip()
    domain      = (data.get("domain") or "casual").strip()
    session_id  = (data.get("session_id") or "").strip() or None

    if not text:
        return err("text is required")
    if not target_lang:
        return err("target_lang is required")

    # Validate target
    tv = validate_language(target_lang)
    if not tv["valid"]:
        return err(f"Unsupported target language: {target_lang}")

    # Auto-detect source
    if source_lang == "auto":
        det = detect_language(text)
        if det.get("supported"):
            source_lang = det["detected_lang"]
        else:
            source_lang = "en"

    # Validate source
    sv = validate_language(source_lang)
    if not sv["valid"]:
        source_lang = "en"

    if source_lang == target_lang:
        return err("Source and target language are the same.")

    # Validate domain
    dv = validate_domain(domain)
    if not dv["valid"]:
        domain = "casual"

    result = translate(
        text=text,
        source_lang=source_lang,
        target_lang=target_lang,
        domain=domain,
        session_id=session_id,
    )

    if "error" in result:
        return err(result["error"], 500)

    # Save context if session
    if session_id:
        class A:
            pass

        ua = A(); ua.session_id = session_id; ua.role = "user"; ua.text = text
        aa = A(); aa.session_id = session_id; aa.role = "assistant"; aa.text = result["translated_text"]
        append_r = action_append(ua)
        action_append(aa)

        if append_r.get("needs_summarize"):
            sa = A(); sa.session_id = session_id
            action_summarize(sa)

    return ok(result)


# ── sessions ──────────────────────────────────────────────────────────────────

@app.route("/api/sessions", methods=["GET"])
def api_sessions_list():
    class A:
        pass
    sessions = list_sessions(A())
    return ok(sessions)


@app.route("/api/sessions", methods=["POST"])
def api_session_new():
    data = request.get_json(force=True)

    class A:
        pass
    a = A()
    a.session_id = str(uuid.uuid4())[:8]
    a.source_lang = data.get("source_lang", "auto")
    a.target_lang = data.get("target_lang", "hi")
    a.domain      = data.get("domain", "casual")

    result = action_new(a)
    return ok(result)


@app.route("/api/sessions/<session_id>", methods=["GET"])
def api_session_load(session_id):
    result = load_session(session_id)
    if "error" in result:
        return err(result["error"], 404)
    return ok(result)


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def api_session_delete(session_id):
    class A:
        pass
    a = A(); a.session_id = session_id
    result = delete_session(a)
    if "error" in result:
        return err(result["error"], 404)
    return ok(result)


# ── glossary ──────────────────────────────────────────────────────────────────

@app.route("/api/glossary", methods=["GET"])
def api_glossary_list():
    class A:
        pass
    a = A()
    a.domain      = request.args.get("domain") or None
    a.source_lang = request.args.get("source_lang") or None
    a.target_lang = request.args.get("target_lang") or None
    result = action_list(a)
    return ok(result)


@app.route("/api/glossary", methods=["POST"])
def api_glossary_add():
    data = request.get_json(force=True)

    class A:
        pass
    a = A()
    a.source_lang  = data.get("source_lang", "").strip()
    a.source_term  = data.get("source_term", "").strip()
    a.target_lang  = data.get("target_lang", "").strip()
    a.target_term  = data.get("target_term", "").strip()
    a.domain       = data.get("domain", "casual").strip()
    a.notes        = data.get("notes", "").strip()

    result = action_add(a)
    if "error" in result:
        return err(result["error"])
    return ok(result), 201


@app.route("/api/glossary/<entry_id>", methods=["DELETE"])
def api_glossary_delete(entry_id):
    class A:
        pass
    a = A(); a.entry_id = entry_id
    result = action_delete(a)
    if "error" in result:
        return err(result["error"], 404)
    return ok(result)


# ── batch ─────────────────────────────────────────────────────────────────────

@app.route("/api/batch", methods=["POST"])
def api_batch():
    """
    Accept a JSON body with:
      {
        "segments": [{"id":"1","source_text":"..."},...],
        "source_lang": "en",
        "target_lang": "hi",
        "domain": "casual"
      }
    Translates each segment individually (small batches from UI).
    For large file batches use the CLI.
    """
    data = request.get_json(force=True)
    segments    = data.get("segments", [])
    source_lang = data.get("source_lang", "en")
    target_lang = data.get("target_lang", "hi")
    domain      = data.get("domain", "casual")

    if not segments:
        return err("segments array is required")
    if not target_lang:
        return err("target_lang is required")

    results = []
    for seg in segments[:50]:  # cap at 50 for web UI
        text = (seg.get("source_text") or "").strip()
        if not text:
            results.append({**seg, "translated_text": "", "skipped": True})
            continue

        r = translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            domain=domain,
        )
        if "error" in r:
            results.append({**seg, "translated_text": "", "error": r["error"]})
        else:
            results.append({**seg, "translated_text": r["translated_text"], "tokens_used": r.get("tokens_used", 0)})

    return ok({"results": results, "total": len(results)})


# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"
    print(f"Starting translator server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
