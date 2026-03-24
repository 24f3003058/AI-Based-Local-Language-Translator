# Setup Project — AI Local Language Translator

## Objective
Initialize the project environment so all tools run correctly.

## Prerequisites
- Python 3.10+
- pip
- An Anthropic API key (from https://console.anthropic.com)

## Steps

### 1. Install dependencies
```bash
pip install anthropic python-dotenv langdetect rich
```

Why these packages:
- `anthropic` — official Claude API client (claude-sonnet-4-6)
- `python-dotenv` — loads `.env` into environment variables at runtime
- `langdetect` — offline language detection, no API cost, handles all 11 supported languages with >95% accuracy on text >20 characters
- `rich` — CLI rendering (panels, tables, colors). Falls back to plain text if not installed.

### 2. Configure your API key
Edit `.env` in the project root:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEFAULT_TARGET_LANG=hi
DEFAULT_DOMAIN=casual
MAX_CONTEXT_TURNS=20
BATCH_SIZE=10
```

NEVER commit `.env`. It is already in `.gitignore`.

### 3. Verify directory structure
Ensure these directories exist (created automatically on first run, but safe to create now):
```
.tmp/context_sessions/
.tmp/batch_input/
.tmp/batch_output/
```

### 4. Configure UTF-8 for Windows (important)
On Windows, run Python with the `-X utf8` flag to handle Indian language scripts correctly:
```bash
python -X utf8 cli.py interactive
python -X utf8 tools/translate_text.py --text "Hello" --source-lang en --target-lang hi --domain casual
```
Or set the environment variable permanently:
```bash
set PYTHONUTF8=1   # Windows CMD
$env:PYTHONUTF8=1  # PowerShell
```

### 5. Verify setup
```bash
python -X utf8 tools/validate_languages.py --lang hi
# Expected: {"valid": true, "code": "hi", "name": "Hindi", "script": "Devanagari"}

python -X utf8 tools/detect_language.py --text "नमस्ते दुनिया"
# Expected: {"detected_lang": "hi", "confidence": ..., "method": "langdetect", "supported": true}
```

### 6. Run a quick translation test
```bash
python -X utf8 tools/translate_text.py \
  --text "Hello, how are you?" \
  --source-lang en \
  --target-lang hi \
  --domain casual
```

### 7. Launch the interactive CLI
```bash
python -X utf8 cli.py interactive
```

## Known Constraints
- `langdetect` can confuse similar scripts (e.g., Hindi vs. Marathi) for very short text (<10 chars). Always provide `--source-lang` explicitly for short phrases or use the source language field.
- API rate limits: If you hit a 429 error, wait 30 seconds and retry. For sustained high-volume batch use, implement exponential backoff (already done in `translate_text.py`).
- Session files in `.tmp/context_sessions/` are not automatically purged. Run `python cli.py session --action list` periodically and delete old sessions with `--action delete --id <id>`.

## Supported Languages
| Code | Language | Script      |
|------|----------|-------------|
| hi   | Hindi    | Devanagari  |
| ta   | Tamil    | Tamil       |
| bn   | Bengali  | Bengali     |
| te   | Telugu   | Telugu      |
| mr   | Marathi  | Devanagari  |
| gu   | Gujarati | Gujarati    |
| kn   | Kannada  | Kannada     |
| ml   | Malayalam| Malayalam   |
| pa   | Punjabi  | Gurmukhi    |
| or   | Odia     | Odia        |
| en   | English  | Latin       |

## Supported Domains
- `casual` — everyday conversational language
- `medical` — clinical terminology, Indian medical institution register
- `legal` — formal legal language, terms of art preserved
- `technical` — precise technical vocabulary (IIT/NIT register)
- `religious` — traditional scriptural register, Sanskrit-origin terms preserved
