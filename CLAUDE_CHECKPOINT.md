# Claude Code Checkpoint - Chem169 LLM Grader

**Last Updated:** 2026-01-25 (overnight batch run started)

## Project Overview

This is an LLM-powered grading tool for CHEM169 course Jupyter notebook assignments. It parses assignment instructions ("routes"), extracts exercises, and uses LLMs to grade student submissions.

## Current State

### Grading Progress

| Route | Status | Notes |
|-------|--------|-------|
| RID_001 | IN PROGRESS | Running overnight with Anthropic (~31/81 when left) |
| RID_002 | COMPLETED | 72/72 successful |
| RID_003 | PENDING | Queued for overnight run |
| RID_004 | PENDING | Queued for overnight run |
| RID_005 | PENDING | Queued for overnight run |
| RID_006 | SKIPPED | Uses .txt deliverables (git log), not notebooks |
| RID_007 | PENDING | Queued for overnight run |
| RID_008 | SKIPPED | Uses .txt deliverables, not notebooks |
| RID_009 | PENDING | Queued for overnight run |

### Overnight Batch Script

A script `run_overnight.sh` was created to run all pending routes sequentially using Anthropic. Check if it completed by looking at:
- `nohup.out` for logs
- Each route's `results/summary.json` for completion status

## Key Code Changes Made This Session

### 1. Route Parser Fix (`graderbot/route_parser.py`)
- Changed regex from `#{2,4}` to `#{1,4}` to detect single `#` headers
- Added Part A/B/C/D pattern for RID_002 format
- Added optional exercise detection (bonus, dyno, extra practice, anchor challenge)

### 2. Retry Logic (`graderbot/llm_client.py`)
- Added exponential backoff retry for 429 rate limit errors
- Config: MAX_RETRIES=5, INITIAL_BACKOFF=2s, MAX_BACKOFF=60s

### 3. Python 3.9 Compatibility
- Added `from __future__ import annotations` to all files using `str | None` syntax:
  - `llm_client.py`, `route_parser.py`, `grader.py`, `notebook_view.py`
  - `prompts.py`, `report.py`, `web.py`

### 4. Optional Exercise Handling (`graderbot/schema.py`, `graderbot/prompts.py`)
- Added `optional: bool` field to Exercise schema
- Added grading instructions for optional exercises (don't penalize if not attempted)

### 5. Non-standard Filename Tracking (`graderbot/dashboard.py`)
- `extract_student_name()` handles Route-prefixed files (e.g., `Route_002_ColabWarmUp_Tiwary`)
- `NON_STANDARD_FILES` list tracks oddly-named submissions

## API Keys

Both are configured in `.env`:
- `OPENAI_API_KEY` - GPT-4o (fast, but hit rate limits with parallel jobs)
- `ANTHROPIC_API_KEY` - Claude Sonnet 4 (slower but reliable, $50 credit added)

## Commands Reference

```bash
# Grade single notebook
source .env && /usr/bin/python3 -m graderbot.cli grade \
  --route assignments/RID_XXX/instructions.md \
  --notebook "path/to/notebook.ipynb" \
  --out "path/to/output.json" \
  --provider anthropic

# Batch grade a route
source .env && /usr/bin/python3 -m graderbot.cli batch \
  --route assignments/RID_XXX/instructions.md \
  --submissions assignments/RID_XXX/submissions \
  --out assignments/RID_XXX/results \
  --provider anthropic

# Parse route to see exercises
/usr/bin/python3 -m graderbot.cli parse-route assignments/RID_XXX/instructions.md
```

## Next Steps (When You Resume)

1. **Check overnight results:**
   ```bash
   cat nohup.out | tail -100
   ls -la assignments/RID_*/results/summary.json
   ```

2. **Verify completion for each route:**
   ```bash
   for dir in assignments/RID_*/results; do
     echo "=== $dir ==="
     cat "$dir/summary.json" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Success: {d[\"successful\"]}/{d[\"total\"]}')" 2>/dev/null || echo "Not complete"
   done
   ```

3. **If any failed, re-run:**
   ```bash
   source .env  # Load API keys from .env file
   /usr/bin/python3 -m graderbot.cli batch --route assignments/RID_XXX/instructions.md --submissions assignments/RID_XXX/submissions --out assignments/RID_XXX/results --provider anthropic
   ```

4. **Generate dashboard** (once all grading complete):
   ```bash
   /usr/bin/python3 -m graderbot.dashboard
   ```

5. **RID_006 and RID_008** need a different approach - they grade git logs (.txt files), not notebooks. The current grader doesn't support this.

## Known Issues

- OpenAI rate limits when running multiple routes in parallel
- RID_006/RID_008 use text file deliverables, not supported yet
- Some students have non-standard filenames (tracked in dashboard.py)
