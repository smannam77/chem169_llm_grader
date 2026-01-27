# Claude Code Checkpoint - Chem169 LLM Grader

**Last Updated:** 2026-01-26

## Project Overview

This is an LLM-powered grading tool for CHEM169 course Jupyter notebook assignments. It parses assignment instructions ("routes"), extracts exercises, and uses LLMs (OpenAI GPT-4o or Anthropic Claude) to grade student submissions.

## Current State: ALL GRADING COMPLETE + DASHBOARD LIVE

### Grading Summary

| Route | Type | Graded | Send Rate | Status |
|-------|------|--------|-----------|--------|
| RID_001 | Notebooks | 76 | 95% | ✅ Complete |
| RID_002 | Notebooks | 71 | 100% | ✅ Complete |
| RID_003 | Notebooks | 80 | 96% | ✅ Complete |
| RID_004 | Notebooks | 75 | 99% | ✅ Complete |
| RID_005 | Notebooks | 73 | 95% | ✅ Complete |
| RID_006 | Text (.txt) | 73 | 97% | ✅ Complete |
| RID_007 | Notebooks | 56 | **46%** | ⚠️ Needs attention |
| RID_008 | Text (.txt) | 32 | 94% | ✅ Complete |
| RID_009 | Notebooks | 29 | 100% | ✅ Complete |
| RID_010-012 | - | 0 | - | No submissions yet |

**Total: 83 students, ~565 submissions graded**

**Key Finding:** RID_007 has only 46% send rate - Exercise 1 (cloning) and Exercise 3 (pushing) have 50%+ failure rates. Students not showing their work.

### GitHub Pages - LIVE!

- **URL:** https://smannam77.github.io/chem169_llm_grader/
- **Settings:** Branch `main`, folder `/docs`
- **Status:** ✅ Enabled and working

## Dashboard Features

### 1. Student Lookup
- Search by name to see individual student progress
- Shows **Sent** (green, 80%+ OK), **Submitted** (yellow, needs work), **Missing** (red)
- Expandable grading feedback per route with exercise-level ratings

### 2. Global Statistics (2x2 Grid)
- **Top row:** Histograms of routes submitted vs routes sent
- **Bottom row:** Scatter plots by student rank
- Median + 25th/75th percentile lines
- "Sent" = 80%+ exercises rated EXCELLENT or OK

### 3. Route Health Heatmap
- Color-coded tiles: red (0%) → yellow (50%) → green (100%)
- Shows route ID, send rate %, and submission count (n=X)
- Click any route (or use dropdown) to see detailed analysis

### 4. Route Analysis Panel
- Exercise success rate bars (green/yellow/red)
- Common issues with sample feedback from grader
- Helps diagnose: hard content, unclear instructions, or grading issues

## Key Modules

### `graderbot/dashboard.py`
- `scan_submissions()` - Count submissions per student
- `scan_grading_results()` - Load all grading JSON files
- `is_soft_send()` - Check if 80%+ exercises are OK
- `get_route_stats()` - Calculate per-route send rates
- `plot_interactive_dashboard()` - Generate full HTML dashboard

### `graderbot/route_analysis.py` (NEW)
- `collect_route_feedback()` - Aggregate feedback by exercise
- `get_common_issues()` - Find exercises with high failure rates
- `summarize_with_llm()` - Use Claude/GPT to analyze patterns
- `generate_route_report()` - Human-readable route analysis

### Configuration in `dashboard.py`
```python
# Students excluded from tracking (not enrolled)
EXCLUDED_STUDENTS = {
    'wagner_eli',
    'schaap_tamar',
    'cruz_jade',
}

# Name normalization for inconsistent submissions
NAME_ALIASES = {
    'jaramilo_jonathan': 'jaramillo_jonathan',
    'tiwary': 'tiwary_ayush',
    'huang': 'huang_terry',
    'pineda': 'pineda_leo',
    # ... more aliases
}
```

## Commands Reference

```bash
# Load environment variables
set -a && source .env && set +a

# Generate dashboard (outputs dashboard.html + docs/index.html)
/usr/bin/python3 -m graderbot.dashboard

# Analyze a specific route (with LLM summary)
/usr/bin/python3 -m graderbot.route_analysis RID_007

# Analyze without LLM call
/usr/bin/python3 -m graderbot.route_analysis RID_007 --no-llm

# Grade notebooks (batch)
/usr/bin/python3 -m graderbot.cli batch \
  --route assignments/RID_XXX/instructions.md \
  --submissions assignments/RID_XXX/submissions \
  --out assignments/RID_XXX/results \
  --provider anthropic

# Grade text files (batch) - for RID_006, RID_008
/usr/bin/python3 -m graderbot.cli batch-text \
  --route assignments/RID_XXX/instructions.md \
  --submissions assignments/RID_XXX/submissions \
  --out assignments/RID_XXX/results \
  --provider anthropic
```

## API Keys

Configured in `.env` (not committed to git):
```
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
```

## File Structure

```
chem169_llm_grader/
├── graderbot/
│   ├── cli.py           # Main CLI (grade, batch, batch-text, etc.)
│   ├── grader.py        # Grading logic
│   ├── llm_client.py    # OpenAI/Anthropic clients with retry
│   ├── route_parser.py  # Exercise extraction from markdown
│   ├── text_view.py     # Text file submission handling
│   ├── dashboard.py     # Interactive dashboard generation
│   ├── route_analysis.py # Route-level feedback analysis (NEW)
│   ├── report.py        # Human-readable report generation
│   └── schema.py        # Pydantic models
├── assignments/
│   └── RID_XXX/
│       ├── instructions.md
│       ├── submissions/
│       └── results/
├── docs/
│   └── index.html       # Dashboard for GitHub Pages
├── .env                 # API keys (not in git)
└── CLAUDE_CHECKPOINT.md # This file
```

## Low Completion Students (≤3 routes)

Identified 9 students needing outreach:
- Fu, Zhengyuan (1 route)
- Pham, Richie (1 route)
- Allam, Emile (3 routes)
- Amaral, Javier (3 routes)
- Garduno, Fernando (3 routes)
- Ouyang, Christina (3 routes)
- Tapia, Tito (3 routes)
- Zhang, Jinyi (3 routes)
- Zhao, Jingru (3 routes)

See `low_completion_students.csv` for details.

## Potential Next Steps

1. **Fix RID_007** - Add clearer instructions for showing git commands/output
2. **Grade RID_010-012** - When submissions come in
3. **Export grades to CSV** - For course gradebook import
4. **Add LLM summaries to dashboard** - Pre-generate route analysis with AI insights

## Known Issues

- Plotly heatmap click events not working reliably (dropdown selector as fallback)
- Some students submit with names swapped (handled by NAME_ALIASES)
- RID_010, RID_011, RID_012 have instructions but no submissions yet
