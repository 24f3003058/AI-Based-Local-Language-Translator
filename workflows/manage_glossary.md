# Manage Glossary — SOP

## Objective
Maintain a translation memory/glossary that ensures domain-specific terms are translated consistently across all sessions and batch runs.

## Why a Glossary?
Domain-specific terms must be translated consistently regardless of how Claude interprets them in different prompts. Without a glossary:
- "habeas corpus" might be translated differently in each session
- Medical abbreviations might be handled inconsistently
- Brand names, drug names, or legal entities might be romanized in some calls and translated in others

The glossary injects hard constraints ("MUST translate X as Y") into every translation prompt, overriding Claude's default behavior for those specific terms.

## Glossary File
`data/glossary.json` — plain JSON, human-readable, editable directly if needed.

Schema per entry:
```json
{
  "id": "uuid4",
  "source_lang": "en",
  "source_term": "myocardial infarction",
  "target_lang": "hi",
  "target_term": "हृदयाघात",
  "domain": "medical",
  "notes": "Standard AIIMS terminology",
  "created_at": "ISO8601",
  "use_count": 14
}
```

## Operations

### Add a term
```bash
python tools/manage_glossary.py --action add \
  --source-lang en \
  --source-term "habeas corpus" \
  --target-lang hi \
  --target-term "बंदी प्रत्यक्षीकरण" \
  --domain legal \
  --notes "Constitutional law term"
```
Or interactively via CLI:
```bash
python cli.py glossary --action add
```

### Look up matching terms
```bash
python tools/manage_glossary.py --action lookup \
  --source-lang en \
  --target-lang hi \
  --domain medical \
  --text "The patient had a myocardial infarction"
```
Returns all glossary entries whose `source_term` appears (case-insensitive substring match) in the text, filtered by language pair and domain.

### List entries
```bash
python cli.py glossary --action list
python cli.py glossary --action list --domain medical
python cli.py glossary --action list --source-lang en
```

### Delete an entry
```bash
python cli.py glossary --action delete --entry-id <uuid>
```

### Bulk import from CSV
CSV must have columns: `source_lang`, `source_term`, `target_lang`, `target_term`, `domain`
Optional: `notes`
```bash
python cli.py glossary --action import --file my_terms.csv
```

### Export to CSV
```bash
python cli.py glossary --action export --output-file my_terms.csv
```

## Lookup Logic (How Terms Are Injected)

1. `translate_text.py` calls the glossary lookup internally before each API call
2. Matching entries are formatted as hard constraints in the system prompt:
   ```
   You MUST translate the term "myocardial infarction" as "हृदयाघात" in your translation.
   ```
3. These constraints override Claude's default for that specific term
4. The `use_count` field increments each time a term is matched and used

## Domain Filtering
- Entries with domain `casual` match ANY domain query
- Entries with domain `medical` only match queries with domain `medical` (or `casual`)
- This prevents, for example, a legal term override from contaminating a medical translation

## Scaling Notes
Current implementation: JSON file with in-memory substring scan.
- Works well up to ~5,000 entries
- For >5,000 entries: migrate to SQLite with a simple FTS (full-text search) index
- This is the known scaling point — document in this workflow when migration is needed

## Best Practices
1. One entry per term per language pair — don't duplicate
2. Always specify `domain` precisely — don't use `casual` for technical terms
3. Use `notes` to record the source/authority for the term (e.g., "per MCI guidelines", "per IPC 2023")
4. Periodically export and review the glossary, especially after domain-specific projects
5. For drug names and anatomical terms: add entries in both en→hi and hi→en directions
