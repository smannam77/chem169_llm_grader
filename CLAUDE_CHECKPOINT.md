# Claude Code Checkpoint - Chem169 LLM Grader

**Last Updated:** 2026-01-29

## Project Overview

This is an LLM-powered grading tool for CHEM169 course Jupyter notebook assignments. It parses assignment instructions ("routes"), extracts exercises, and uses LLMs (OpenAI GPT-4o or Anthropic Claude) to grade student submissions.

---

## IMMEDIATE NEXT STEP: WRITE MIDTERM ROUTES

**Status:** Midterm description doc is polished and ready to share with students (tomorrow in class). Now need to write the actual routes.

### Midterm Plan

- **Date:** Thursday, February 6, 2026, 12:30-1:50 PM
- **Format:** Bouldering comp — many short routes, collect points
- **Routes needed:** ~40 total (20 practice + 20 exam)
- **Route style:** Boulder problems (1-3 exercises, 5-10 min each)
- **Scoring:** Easy=1pt, Medium=2pt, Hard=3pt. Half credit for attempted but not sent.
- **Grade thresholds:** A≥10, B≥7, C≥4, D≥1
- **Part 2:** Process Snapshot — students submit copy-paste transcript of AI conversation (one route)
- **Doc location:** `mid_term_description_doc.md` (also on GitHub)

### What needs to be done:

1. **Pick topics/skills** for the 40 boulder problems (across all quarter material)
2. **Write 20 practice routes** (can remix existing R001-R009 exercises into standalone boulders)
3. **Write 20 midterm routes** (fresh problems, same skills)
4. **Record contrastive example videos** (Style A: copy-paster vs Style B: explorer)
5. **Test-solve a sample** to calibrate difficulty/timing
6. **Set up Google Forms** for midterm submissions
7. **Load routes into grading pipeline** and test

### Key decisions made:
- Collaboration allowed (discuss approaches, share tips) but individual submissions
- Any AI tool allowed (Gemini, ChatGPT, Claude, etc.)
- Practice routes released before midterm so students can prep
- Exact point thresholds already published (A≥10, B≥7, C≥4, D≥1)

---

## Current State: GRADING CAUGHT UP, DASHBOARD LIVE

### Grading Status (as of 2026-01-29)

All submissions graded. 85 students tracked.

| Route | Type | Status |
|-------|------|--------|
| RID_001 | Notebooks | All graded |
| RID_002 | Notebooks | All graded |
| RID_003 | Notebooks | All graded |
| RID_004 | Notebooks | All graded |
| RID_005 | Notebooks | All graded |
| RID_006 | Text | All graded |
| RID_007 | - | FREE PASS |
| RID_008 | Text | All graded |
| RID_009 | Notebooks | All graded |
| RID_012 | Notebooks | All graded |

### GitHub Pages Dashboard - LIVE

- **URL:** https://smannam77.github.io/chem169_llm_grader/
- **Password:** `Chem169269!!!`
- **Settings:** Branch `main`, folder `/docs`

---

## Bugs Fixed This Session (2026-01-29)

### 1. Name extraction: "Zhou Daojia Route"
- **Cause:** Student typed `Route_001` instead of `RID_001` in filename
- **Fix:** Updated regex in `extract_student_name()` to handle `Route_XXX` pattern
- **File:** `graderbot/dashboard.py:104`

### 2. Completed vs Sent inconsistency (Abigail Chiu)
- **Cause:** `completed` came from `scan_submissions()` (file types), `sent` came from grading results. Student submitted `.ipynb` for text route RID_006 — wrong format but still graded.
- **Fix:** `completed_set` now merges submissions + grading results. If grades exist, route counts as completed.
- **File:** `graderbot/dashboard.py:775-798`

### 3. Count mismatch
- **Cause:** `count` field used `len(routes)` from scan_submissions instead of `len(completed_set)`
- **Fix:** Changed to `len(completed_set)`
- **File:** `graderbot/dashboard.py:811`

### 4. FREE_PASS routes showing as "not sent" (Olivia Zhang)
- **Cause:** Ungraded FREE_PASS routes fell through to `not_sent_routes` because free pass logic only ran inside the grading results loop
- **Fix:** Added FREE_PASS check in the "ungraded routes" fallback block
- **File:** `graderbot/dashboard.py:800-806`

### 5. Missing student: Srikumaran Sarayu
- **Cause:** Submission file had no `.ipynb` extension. `glob("*.ipynb")` didn't find it.
- **Fix:** Renamed file to add `.ipynb`, graded it. (Manual fix — many other wrong-format files exist.)

---

## Dashboard Architecture (Single Source of Truth)

After multiple bugs from inconsistent data sources, the dashboard now uses:

- **`completed`** = `scan_submissions()` UNION grading results (if grades exist, it's completed)
- **`sent`** = from grading results via `is_soft_send()` + FREE_PASS routes
- **`not_sent`** = completed minus sent
- **`missing`** = all routes minus completed
- **Route stats** = counted from `student_grades` only (not scan_submissions)

This ensures: `completed = sent + not_sent` always.

---

## Key Documents

| File | Purpose |
|------|---------|
| `mid_term_description_doc.md` | Midterm description for students (ready to share) |
| `SCALING_PLAN.md` | Long-term architecture plan (Supabase, student portal, etc.) |
| `CLAUDE_CHECKPOINT.md` | This file |

---

## Key Modules

### `graderbot/dashboard.py`
- `extract_student_name()` - Name extraction with regex, aliases, exclusions
- `scan_submissions()` - Count submissions per student
- `scan_grading_results()` - Load all grading JSON files
- `is_soft_send()` - Check if 80%+ exercises are OK (+ FREE_PASS)
- `get_route_stats()` - Calculate per-route send rates
- `plot_interactive_dashboard()` - Generate full HTML dashboard with password gate

### `graderbot/route_analysis.py`
- `collect_route_feedback()` - Aggregate feedback by exercise
- `get_common_issues()` - Find exercises with high failure rates

### Configuration in `dashboard.py`
```python
FREE_PASS_ROUTES = {'RID_007'}
EXCLUDED_STUDENTS = {'wagner_eli', 'schaap_tamar', 'cruz_jade'}
NAME_ALIASES = {
    'jaramilo_jonathan': 'jaramillo_jonathan',
    'tiwary': 'tiwary_ayush',
    # ... ~20 aliases
}
```

---

## Commands Reference

```bash
# Load environment variables
set -a && source .env && set +a

# Generate dashboard (outputs dashboard.html + docs/index.html)
/usr/bin/python3 -m graderbot.dashboard

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

# Sync instructions from portal repo
./sync_instructions.sh

# Sync submissions from Google Drive
~/bin/rclone copy "gdrive:TheJinichLab/teaching/Chem169/..." assignments/RID_XXX/submissions --progress
```

---

## Known Issues

- Many students submitted wrong file formats (PDF notebooks, .docx logbooks) — see `find` output for full list
- Plotly heatmap click events not always reliable (dropdown selector as fallback)
- `scan_submissions()` and grading results can diverge for wrong-format files (mitigated by union logic)
- Dashboard `Last Updated` timestamp is hardcoded — should auto-update

---

## Long-Term Vision: Scaling Plan

See `SCALING_PLAN.md` for full details. Summary:
- Migrate to Supabase (auth, database, storage)
- Student portal with Google SSO
- Auto-grading on submission (no manual batch runs)
- Multi-course support
- Target: Beta by Summer 2026

---

## File Structure

```
chem169_llm_grader/
├── graderbot/
│   ├── cli.py              # Main CLI
│   ├── grader.py           # Grading logic
│   ├── llm_client.py       # OpenAI/Anthropic clients
│   ├── route_parser.py     # Exercise extraction from markdown
│   ├── text_view.py        # Text file submission handling
│   ├── dashboard.py        # Interactive dashboard generation
│   ├── route_analysis.py   # Route-level feedback analysis
│   ├── report.py           # Human-readable report generation
│   └── schema.py           # Pydantic models
├── assignments/
│   └── RID_XXX/
│       ├── instructions.md
│       ├── submissions/
│       └── results/
├── docs/
│   └── index.html          # Dashboard for GitHub Pages
├── mid_term_description_doc.md  # Midterm doc for students
├── SCALING_PLAN.md          # Long-term architecture plan
├── .env                     # API keys (not in git)
└── CLAUDE_CHECKPOINT.md     # This file
```
