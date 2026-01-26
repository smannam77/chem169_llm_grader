# Claude Code Checkpoint - Chem169 LLM Grader

**Last Updated:** 2026-01-26

## Project Overview

This is an LLM-powered grading tool for CHEM169 course Jupyter notebook assignments. It parses assignment instructions ("routes"), extracts exercises, and uses LLMs (OpenAI GPT-4o or Anthropic Claude) to grade student submissions.

## Current State: ALL GRADING COMPLETE

### Grading Summary

| Route | Type | Graded | Status |
|-------|------|--------|--------|
| RID_001 | Notebooks | 81/81 | ✅ Complete |
| RID_002 | Notebooks | 72/72 | ✅ Complete |
| RID_003 | Notebooks | 80/80 | ✅ Complete |
| RID_004 | Notebooks | 75/75 | ✅ Complete |
| RID_005 | Notebooks | 73/73 | ✅ Complete |
| RID_006 | Text (.txt) | 73/74 | ✅ Complete |
| RID_007 | Notebooks | 56/56 | ✅ Complete |
| RID_008 | Text (.txt) | 32/36 | ✅ Complete |
| RID_009 | Notebooks | 29/29 | ✅ Complete |

**Total: ~571 submissions graded**

### Generated Outputs

- **Dashboard:** `docs/index.html` (also `dashboard.html` locally)
- **Student Reports:** `assignments/RID_XXX/results/*_grade.txt` (574 reports)
- **JSON Results:** `assignments/RID_XXX/results/*_grade.json`
- **Summaries:** `assignments/RID_XXX/results/summary.json`

### GitHub Pages

- **Status:** Waiting for smannam77 to enable (requires admin access)
- **URL (once enabled):** https://smannam77.github.io/chem169_llm_grader/
- **Settings:** Branch `main`, folder `/docs`

## Key Features Implemented

### 1. Route Parser (`graderbot/route_parser.py`)
- Detects `# Exercise N`, `## Exercise N`, `### Part A/B/C/D` formats
- Detects optional exercises (bonus, dyno, extra practice, anchor challenge)
- Works with single `#` headers (changed from `#{2,4}` to `#{1,4}`)

### 2. Text File Grading (`graderbot/text_view.py`)
- Added `batch-text` CLI command for .txt submissions (RID_006, RID_008)
- Grades git log deliverables and logbook reflections
- Custom system prompt for evaluating git workflows

### 3. Retry Logic (`graderbot/llm_client.py`)
- Exponential backoff for 429 rate limit errors
- MAX_RETRIES=5, INITIAL_BACKOFF=2s, MAX_BACKOFF=60s

### 4. Resume Support (`graderbot/cli.py`)
- Both `batch` and `batch-text` skip already-graded submissions
- Safe to interrupt and restart - won't re-grade existing results

### 5. Python 3.9 Compatibility
- `from __future__ import annotations` in all modules

## API Keys

Configured in `.env` (not committed to git):
```
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Commands Reference

```bash
# Grade notebooks (batch)
source .env && /usr/bin/python3 -m graderbot.cli batch \
  --route assignments/RID_XXX/instructions.md \
  --submissions assignments/RID_XXX/submissions \
  --out assignments/RID_XXX/results \
  --provider anthropic

# Grade text files (batch) - for RID_006, RID_008
source .env && /usr/bin/python3 -m graderbot.cli batch-text \
  --route assignments/RID_XXX/instructions.md \
  --submissions assignments/RID_XXX/submissions \
  --out assignments/RID_XXX/results \
  --provider anthropic

# Generate dashboard
/usr/bin/python3 -m graderbot.dashboard

# Generate student report from JSON
/usr/bin/python3 -m graderbot.report assignments/RID_XXX/results/StudentName_grade.json

# Parse route to see detected exercises
/usr/bin/python3 -m graderbot.cli parse-route assignments/RID_XXX/instructions.md
```

## GitHub CLI

Installed at `~/bin/gh` (authenticated). Useful commands:
```bash
~/bin/gh auth status
~/bin/gh api repos/smannam77/chem169_llm_grader
```

## File Structure

```
chem169_llm_grader/
├── graderbot/
│   ├── cli.py          # Main CLI (grade, batch, batch-text, etc.)
│   ├── grader.py       # Grading logic
│   ├── llm_client.py   # OpenAI/Anthropic clients with retry
│   ├── route_parser.py # Exercise extraction from markdown
│   ├── text_view.py    # Text file submission handling
│   ├── dashboard.py    # Statistics and visualization
│   ├── report.py       # Human-readable report generation
│   └── schema.py       # Pydantic models
├── assignments/
│   └── RID_XXX/
│       ├── instructions.md
│       ├── submissions/
│       └── results/
├── docs/
│   └── index.html      # Dashboard for GitHub Pages
├── .env                # API keys (not in git)
└── CLAUDE_CHECKPOINT.md # This file
```

## Potential Next Steps

1. **Enable GitHub Pages** - Need smannam77 to enable in repo settings
2. **Aggregate statistics** - Cross-route analysis of student performance
3. **Identify struggling students** - Flag students with multiple NEEDS_WORK ratings
4. **Export to CSV** - For importing into course gradebook
5. **Add more routes** - RID_010, RID_011, RID_012 when available

## Known Issues

- Some students have non-standard filenames (tracked in `NON_STANDARD_FILES` list)
- 4 students missing deliverables in RID_008
- 1 student missing deliverable in RID_006
