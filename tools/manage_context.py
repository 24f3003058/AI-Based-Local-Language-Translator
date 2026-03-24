#!/usr/bin/env python3
"""
Manage conversation history for interactive translation sessions.
All session state lives in .tmp/context_sessions/session_<id>.json

Usage:
    python tools/manage_context.py --action load   --session-id abc
    python tools/manage_context.py --action append --session-id abc --role user --text "..."
    python tools/manage_context.py --action append --session-id abc --role assistant --text "..."
    python tools/manage_context.py --action summarize --session-id abc
    python tools/manage_context.py --action list
    python tools/manage_context.py --action delete --session-id abc
    python tools/manage_context.py --action new
        --session-id abc --source-lang hi --target-lang ta --domain medical
"""

import argparse
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

# Support Render.com persistent disk at /data, else fall back to .tmp/
_DATA_ROOT = Path(os.getenv("PERSISTENT_DATA_DIR", "")) if os.getenv("PERSISTENT_DATA_DIR") else None
if _DATA_ROOT is None:
    _DATA_ROOT = Path("/data") if Path("/data").exists() else Path(__file__).parent.parent / ".tmp"
SESSIONS_DIR = _DATA_ROOT / "context_sessions"
MAX_HISTORY_TURNS = 20
SUMMARIZE_THRESHOLD = 20


def session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"session_{session_id}.json"


def load_session(session_id: str) -> dict:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = session_path(session_id)
    if not path.exists():
        return {"error": f"Session '{session_id}' not found.", "code": "CONTEXT_LOAD_FAILED"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_session(session_id: str, data: dict):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    with open(session_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def action_new(args) -> dict:
    session_id = args.session_id or str(uuid.uuid4())[:8]
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    session = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_lang": args.source_lang or "auto",
        "target_lang": args.target_lang or "hi",
        "domain": args.domain or "casual",
        "summary": "",
        "history": [],
    }
    save_session(session_id, session)
    return session


def action_load(args) -> dict:
    if not args.session_id:
        return {"error": "Missing --session-id", "code": "MISSING_ARGS"}
    return load_session(args.session_id)


def action_append(args) -> dict:
    if not args.session_id or not args.role or not args.text:
        return {"error": "Missing --session-id, --role, or --text", "code": "MISSING_ARGS"}
    if args.role not in ("user", "assistant"):
        return {"error": "Role must be 'user' or 'assistant'", "code": "INVALID_ARGS"}

    session = load_session(args.session_id)
    if "error" in session:
        return session

    session["history"].append({
        "role": args.role,
        "text": args.text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_session(args.session_id, session)
    return {
        "success": True,
        "session_id": args.session_id,
        "history_length": len(session["history"]),
        "needs_summarize": len(session["history"]) >= SUMMARIZE_THRESHOLD,
    }


def action_summarize(args) -> dict:
    """Summarize oldest turns to keep context window lean."""
    if not args.session_id:
        return {"error": "Missing --session-id", "code": "MISSING_ARGS"}

    session = load_session(args.session_id)
    if "error" in session:
        return session

    if len(session["history"]) < SUMMARIZE_THRESHOLD:
        return {"success": True, "message": "No summarization needed yet.", "history_length": len(session["history"])}

    # Take oldest half to summarize
    to_summarize = session["history"][:10]
    remaining = session["history"][10:]

    # Build a text representation to summarize
    convo_text = "\n".join([f"{t['role'].upper()}: {t['text']}" for t in to_summarize])

    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    f"Summarize this translation session excerpt in 2-3 sentences. "
                    f"Focus on: what was being translated, what domain/context, any specific terms discussed or decided.\n\n"
                    f"{convo_text}"
                ),
            }],
        )
        new_summary_part = response.content[0].text.strip()
        existing_summary = session.get("summary", "")
        session["summary"] = (existing_summary + "\n\n" + new_summary_part).strip() if existing_summary else new_summary_part
        session["history"] = remaining
        save_session(args.session_id, session)

        return {
            "success": True,
            "summarized_turns": len(to_summarize),
            "remaining_turns": len(remaining),
            "summary_preview": session["summary"][:200],
        }
    except Exception as e:
        return {"error": str(e), "code": "API_ERROR"}


def action_list(args) -> list:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append({
                "session_id": data.get("session_id"),
                "created_at": data.get("created_at"),
                "source_lang": data.get("source_lang"),
                "target_lang": data.get("target_lang"),
                "domain": data.get("domain"),
                "history_length": len(data.get("history", [])),
                "has_summary": bool(data.get("summary")),
            })
        except Exception:
            continue
    return sessions


def action_delete(args) -> dict:
    if not args.session_id:
        return {"error": "Missing --session-id", "code": "MISSING_ARGS"}
    path = session_path(args.session_id)
    if not path.exists():
        return {"error": f"Session '{args.session_id}' not found.", "code": "CONTEXT_LOAD_FAILED"}
    path.unlink()
    return {"success": True, "deleted_session": args.session_id}


def main():
    parser = argparse.ArgumentParser(description="Manage translation session context")
    parser.add_argument("--action", required=True, choices=["new", "load", "append", "summarize", "list", "delete"])
    parser.add_argument("--session-id")
    parser.add_argument("--role", choices=["user", "assistant"])
    parser.add_argument("--text")
    parser.add_argument("--source-lang")
    parser.add_argument("--target-lang")
    parser.add_argument("--domain")
    args = parser.parse_args()

    actions = {
        "new": action_new,
        "load": action_load,
        "append": action_append,
        "summarize": action_summarize,
        "list": action_list,
        "delete": action_delete,
    }

    result = actions[args.action](args)

    if isinstance(result, dict) and "error" in result:
        print(json.dumps(result), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
