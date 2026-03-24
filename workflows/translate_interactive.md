# Translate Interactive — SOP

## Objective
Run a context-aware interactive translation session where each exchange builds on prior conversation history.

## Required Inputs
| Input | Default | Notes |
|-------|---------|-------|
| target_lang | hi | Must be a valid code from languages.json |
| source_lang | auto | "auto" triggers language detection per message |
| domain | casual | casual / medical / legal / technical / religious |
| session_id | (auto-generated) | 8-char UUID prefix; provide to resume |

## Tool Execution Sequence

### Step 1: Start or resume session
```bash
# New session
python tools/manage_context.py --action new \
  --session-id <id> \
  --source-lang <src> \
  --target-lang <tgt> \
  --domain <domain>

# Resume existing
python tools/manage_context.py --action load --session-id <id>
```

### Step 2 (per message): Detect language if source is "auto"
```bash
python tools/detect_language.py --text "<user_text>"
```
- If `supported: false` → warn user, ask them to specify source language
- If confidence < 0.85 → use Claude fallback (happens automatically inside tool)

### Step 3 (per message): Validate source and target
```bash
python tools/validate_languages.py --lang <source_lang>
python tools/validate_languages.py --lang <target_lang>
```
- If either is invalid → surface error to user, do not proceed

### Step 4: Check for same-language scenario
- If `source_lang == target_lang` after detection → skip translation, warn user

### Step 5 (per message): Look up glossary
```bash
python tools/manage_glossary.py --action lookup \
  --source-lang <src> \
  --target-lang <tgt> \
  --domain <domain> \
  --text "<user_text>"
```
Glossary matches are automatically injected into the system prompt by `translate_text.py`.

### Step 6 (per message): Translate
```bash
python tools/translate_text.py \
  --text "<user_text>" \
  --source-lang <src> \
  --target-lang <tgt> \
  --domain <domain> \
  --session-id <session_id>
```
The tool handles: context injection from session file, glossary constraint embedding, domain prompting, script enforcement.

### Step 7 (per message): Save to context
```bash
python tools/manage_context.py --action append \
  --session-id <id> --role user --text "<user_text>"

python tools/manage_context.py --action append \
  --session-id <id> --role assistant --text "<translated_text>"
```

### Step 8 (per message): Display output
```bash
python tools/format_output.py --mode cli --input-json '<result_json>'
```

### Step 9: Check if summarization is needed
After each append, check `needs_summarize` in the response.
If `true`:
```bash
python tools/manage_context.py --action summarize --session-id <id>
```
This compresses the oldest 10 turns into a summary paragraph stored in the session file. Future prompts use the summary + remaining history to maintain context without growing the token count unboundedly.

## Edge Cases

| Situation | Action |
|-----------|--------|
| Source == target language | Skip API call. Print: "Source and target are the same." |
| Language detection confidence < 0.85 | Trigger Claude fallback in detect_language.py |
| Unsupported language detected | Ask user to specify source language explicitly |
| API rate limit (429) | Retry after 30s (up to 3 times). Print wait message. |
| History >= 20 exchanges | Auto-summarize via manage_context.py --action summarize |
| Empty input | Skip silently, re-prompt |
| User types "quit"/"exit"/"q" | End session gracefully, print session ID for resumption |
| Session file corrupted/missing | Start fresh session, warn user |

## Context Architecture

**Three layers of context:**

1. **Session History** (conversation turns) — last N turns from `.tmp/context_sessions/session_<id>.json`
2. **Summary** — compressed digest of older turns, injected into system prompt
3. **Domain Instructions** — per-domain register embedded in system prompt for every call
4. **Glossary Constraints** — hard-coded term overrides injected as "MUST translate X as Y" rules

This layering ensures:
- Short-term context (recent turns) is always available
- Long-term context (session summary) prevents context loss on long sessions
- Domain consistency regardless of how many turns have passed
- Term consistency via glossary (overrides Claude's defaults for specific vocabulary)

## Session Resumption
Sessions are stored indefinitely. To resume:
```bash
python cli.py interactive --id <session_id>
```
The full history and summary are loaded. The user continues as if the session never ended.

## Known Constraints
- Sessions are stored in `.tmp/context_sessions/` as plain JSON. Do not delete this directory between sessions.
- Token cost scales with history length. Sessions longer than 50 turns will incur higher per-call costs due to history included in every prompt. Auto-summarization mitigates this but does not eliminate it.
- `langdetect` struggles with code-switched text (e.g., Hinglish). For mixed-language input, recommend the user set `source_lang` explicitly.
