# Translate Batch — SOP

## Objective
Translate an entire file (CSV or plain TXT) efficiently using batched Claude API calls.

## Required Inputs
| Input | Required | Notes |
|-------|----------|-------|
| input_file | Yes | CSV or TXT path |
| target_lang | Yes | Target language code |
| source_lang | No (default: en) | Source language code |
| domain | No (default: casual) | Translation domain |
| batch_size | No (default: 10) | Segments per API call |

## Input File Formats

### CSV Format
Required columns: `id`, `source_text`
Optional columns: `source_lang`, `target_lang`, `domain` (override defaults per row)
```csv
id,source_text,source_lang,target_lang,domain
1,"Hello, how are you?",en,hi,casual
2,"The patient has a fever.",en,ta,medical
```

### TXT Format
One segment per line. Line number becomes the ID. Empty lines are preserved as empty in output.
```
Hello, how are you?
The patient has a fever.

(empty line above preserved)
```

## Tool Execution Sequence

### Step 1: Validate inputs
```bash
python tools/validate_languages.py --lang <source_lang>
python tools/validate_languages.py --lang <target_lang>
python tools/validate_languages.py --domain <domain>
```
If validation fails: halt and report which input is invalid.

### Step 2: Check input file exists
If file not found → print error with the expected path, exit with code 1.

### Step 3: Parse input file
- CSV: check for required columns `id` and `source_text`. Halt if missing, report which columns are absent.
- TXT: read all lines, assign sequential IDs, skip empty lines (mark as skip=True for position preservation).

### Step 4: Group by language pair
For CSV files that may contain mixed language pairs:
- Group rows by `(source_lang, target_lang, domain)` tuples
- Each group is batched independently to maintain prompt coherence
- This ensures Claude sees homogeneous language pairs in each call

### Step 5: Batch translate
For each group, split into batches of `batch_size` (default 10):
```bash
python tools/translate_batch.py \
  --input-file <path> \
  --output-file .tmp/batch_output/<name>_translated.csv \
  --source-lang <src> \
  --target-lang <tgt> \
  --domain <domain> \
  --batch-size 10
```

The tool packs segments as a numbered list and requests a JSON array response. Claude returns:
```json
[{"index": 1, "translated_text": "..."}, ...]
```

### Step 6: Write output
Output CSV is written to `.tmp/batch_output/<input_stem>_translated.csv`.
Columns: `id`, `source_lang`, `target_lang`, `domain`, `source_text`, `translated_text`

### Step 7: Report summary
Print to stdout:
```json
{
  "total": 500,
  "succeeded": 498,
  "failed": 2,
  "output_file": ".tmp/batch_output/my_file_translated.csv",
  "failures": [{"id": "12", "error": "..."}, ...]
}
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Empty lines in TXT | Skip translation, preserve empty row in output |
| CSV missing `id` or `source_text` | Halt with clear error listing missing columns |
| Mixed language pairs in CSV | Group by lang pair before batching |
| Batch API failure | Mark all IDs in that batch as failed; continue with next batch |
| Rate limit (429) | Retry batch after exponential backoff (30s, 60s, 120s); log failure if all retries exhausted |
| Claude returns malformed JSON | Retry that batch once with a stricter prompt; if still fails, mark as failed |
| Very long segments (>500 words) | Reduce batch_size to 5 for that group to stay within Claude's optimal coherence range |

## Why Batch Size of 10?
Empirically, numbered-list prompts with >10 items show degraded translation accuracy and ID/result misalignment. 10 is the safe upper bound. For very long individual segments (>200 words), prefer batch_size=5.

## Performance Notes
- At batch_size=10, a 500-line file requires ~50 API calls instead of 500 (10x reduction)
- Each Claude call has overhead of ~200-300 input tokens for the system prompt
- Batching amortizes this overhead across 10 segments
- For files >1000 lines, consider splitting into parallel runs if latency is a concern

## Output
The output CSV is written to `.tmp/batch_output/`. This directory is disposable — regenerate as needed.
If you need to persist results, copy the output CSV to a permanent location or upload to cloud storage.
