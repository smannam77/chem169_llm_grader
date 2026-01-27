# Claude Code Checkpoint - Chem169 LLM Grader

**Last Updated:** 2026-01-26 (evening)

## Project Overview

This is an LLM-powered grading tool for CHEM169 course Jupyter notebook assignments. It parses assignment instructions ("routes"), extracts exercises, and uses LLMs (OpenAI GPT-4o or Anthropic Claude) to grade student submissions.

---

## 🚨 IMMEDIATE NEXT STEP: GRADE NEW SUBMISSIONS

**Status:** Submissions synced from Google Drive → local. Ready to grade ~50 new submissions.

### What needs to be done:

1. **Load environment variables:**
   ```bash
   set -a && source .env && set +a
   ```

2. **Grade notebook routes (one by one to monitor progress):**
   ```bash
   # R001 - 12 ungraded
   /usr/bin/python3 -m graderbot.cli batch --route assignments/RID_001/instructions.md --submissions assignments/RID_001/submissions --out assignments/RID_001/results --provider anthropic

   # R002 - 10 ungraded
   /usr/bin/python3 -m graderbot.cli batch --route assignments/RID_002/instructions.md --submissions assignments/RID_002/submissions --out assignments/RID_002/results --provider anthropic

   # R003 - 1 ungraded
   /usr/bin/python3 -m graderbot.cli batch --route assignments/RID_003/instructions.md --submissions assignments/RID_003/submissions --out assignments/RID_003/results --provider anthropic

   # R004 - 1 ungraded
   /usr/bin/python3 -m graderbot.cli batch --route assignments/RID_004/instructions.md --submissions assignments/RID_004/submissions --out assignments/RID_004/results --provider anthropic

   # R009 - 10 ungraded
   /usr/bin/python3 -m graderbot.cli batch --route assignments/RID_009/instructions.md --submissions assignments/RID_009/submissions --out assignments/RID_009/results --provider anthropic

   # R012 - 1 ungraded
   /usr/bin/python3 -m graderbot.cli batch --route assignments/RID_012/instructions.md --submissions assignments/RID_012/submissions --out assignments/RID_012/results --provider anthropic
   ```

3. **Grade text route (R008 - 12 ungraded):**
   ```bash
   /usr/bin/python3 -m graderbot.cli batch-text \
     --route assignments/RID_008/instructions.md \
     --submissions assignments/RID_008/submissions \
     --out assignments/RID_008/results \
     --provider anthropic
   ```

   **Skip R005, R006, R007** - already complete or free pass.

4. **Regenerate dashboard:**
   ```bash
   /usr/bin/python3 -m graderbot.dashboard
   ```

5. **Push to GitHub Pages** (optional):
   ```bash
   git add docs/index.html && git commit -m "Update dashboard" && git push
   ```

### Accurate grading status (as of 2026-01-26 evening):
| Route | Type | Submitted | Graded | Ungraded |
|-------|------|-----------|--------|----------|
| RID_001 | Notebooks | 95 | 83 | **12** |
| RID_002 | Notebooks | 83 | 73 | **10** |
| RID_003 | Notebooks | 82 | 81 | **1** |
| RID_004 | Notebooks | 77 | 76 | **1** |
| RID_005 | Notebooks | 73 | 74 | 0 ✅ |
| RID_006 | Text | 73 | 74 | 0 ✅ |
| RID_007 | - | - | - | **FREE PASS** |
| RID_008 | Text | 47 | 35 | **12** |
| RID_009 | Notebooks | 40 | 30 | **10** |
| RID_012 | Notebooks | 1 | 0 | **1** |

**Total ungraded: ~47 submissions**

**Estimated time:** 30-45 minutes (grader auto-skips already-graded files)

**IMPORTANT:** Dashboard shows inconsistent numbers because of ungraded submissions. Grade first, then regenerate dashboard - numbers will match.

**Note:** R007 is a free pass - all students get credit regardless of submission. Code change in `dashboard.py` handles this via `FREE_PASS_ROUTES` constant.

---

## Current State: SUBMISSIONS SYNCED, READY TO GRADE

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

## Google Form Migration ✅ COMPLETE

Migrated from shared Google Drive folders to Google Forms for submissions.

**All routes now have forms created and tested:**
- R001, R002, R003, R004, R005: Notebook + logbook
- R006, R007, R008: Text deliverable + logbook (git-based routes)
- R009, R012: Notebook + logbook

**Portal updated:** All route `.md` files now link to their Google Forms.

**Form folder structure:**
```
google_form_based_submissions/
├── R001_Submission_File_responses/
│   ├── Notebook File (.ipynb) (File responses)/
│   └── Logbook File (.txt) (File responses)/
├── R006_submissions (File responses)/
│   ├── Deliverable file (.txt) (File responses)/   # git log output
│   └── Logbook File (.txt) (File responses)/
...
```

**File format issues found:**
- R002: 19 PDF notebooks (18%) - students confused
- Various routes: docx, rtf submissions instead of txt
- Need Canvas announcement about correct formats

## Repo Sync (SOLVED)

**Portal is source of truth** for route instructions.

| Repo | Path |
|------|------|
| Portal (source) | `/Users/ajinich/Documents/repos/climbing-gym-app/content/routes/R001_*.md` |
| Grader (synced) | `/Users/ajinich/Documents/repos/chem169_llm_grader/assignments/RID_001/instructions.md` |

**Sync command:**
```bash
./sync_instructions.sh
```

Run this after updating any route instructions in the portal repo.

## rclone Setup

Installed at `~/bin/rclone`, configured with `gdrive:` remote.

**Key paths:**
```
gdrive:TheJinichLab/teaching/Chem169/Chem169_269_v2/04_Submissions/
├── google_form_based_submissions/    # NEW form-based submissions
├── RID_003_submission/               # OLD shared folders (to be deprecated)
├── RID_004_submission/
...
```

## Potential Next Steps

1. ~~**Complete form migration**~~ ✅ DONE
2. ~~**Sync repos**~~ ✅ DONE (use `./sync_instructions.sh`)
3. ~~**Sync new submissions**~~ ✅ DONE (2026-01-26 evening)
4. **🚨 Grade new submissions** ← YOU ARE HERE (~50 new, ~20-40 min)
5. **Regenerate dashboard** - Update with new grades
6. **Canvas announcement** - Correct file formats (.ipynb, .txt only)
7. **Handle wrong format submissions** - Contact students with PDF/docx to resubmit

## Storage Usage (as of 2026-01-26)

**Total assignments folder: 58 MB** (10 routes, ~1,300 files)

| Route | Size | Notes |
|-------|------|-------|
| RID_001 | 20 MB | Large notebooks with outputs |
| RID_009 | 17 MB | Large notebooks with outputs |
| Others | <6 MB each | Text routes are tiny (<1 MB) |

**Projections:** 100 routes → ~580 MB, still manageable on MacBook.

## R007 Free Pass (IMPLEMENTED)

R007 had confusing instructions (originally asked for .ipynb, then changed to .txt deliverable). Students submitted wrong formats through no fault of their own.

**Decision:** All R007 submissions count as "sent" regardless of actual grade.

**Implementation:** Added `FREE_PASS_ROUTES = {'RID_007'}` in `dashboard.py`. The `is_soft_send()` function now returns `True` for any route in this set.

## Known Issues

- Plotly heatmap click events not working reliably (dropdown selector as fallback)
- Some students submit with names swapped (handled by NAME_ALIASES)
- Google Forms appends " - Name" to filenames (need to handle in extract_student_name)
- ~~R007 had 46% send rate due to unclear instructions~~ → Now free pass (see above)
