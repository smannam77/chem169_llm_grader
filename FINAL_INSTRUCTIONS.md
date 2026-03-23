# GraderBot Session State - January 2025

## What This Project Is
LLM-powered grading tool for Chem 169 Jupyter notebook assignments. Students submit notebooks to Google Drive, we grade them with GPT-4, and show results on a student-facing dashboard.

## What We Accomplished This Session

### 1. Grader Prompt Fixes
- **File**: `graderbot/prompts.py`
- Fixed: Grader now handles `FileNotFoundError` gracefully (data file missing is NOT a code error)
- Fixed: Students can put multiple exercises in one cell - grader evaluates code logic, not cell organization
- Added: `missing_data_file` flag for environment issues

### 2. Route Parser Fixes
- **File**: `graderbot/route_parser.py`
- Fixed: Regex now handles `### **Exercise 1\.` markdown formatting
- All 8 exercises in RID_001 now parse correctly (was only finding 0-3 before)

### 3. Notebook Truncation Fix
- **File**: `graderbot/notebook_view.py`
- Increased cell truncation from 2000 → 15000 chars
- Students who put all code in one cell now get graded fully

### 4. Student-Facing Dashboard
- **File**: `graderbot/dashboard.py`
- **Output**: `docs/index.html`
- Features:
  - Student lookup with search
  - Per-route completion status
  - Per-exercise grades (EXCELLENT/OK/NEEDS_WORK)
  - Expandable cards with rationale/feedback
  - Global stats (histogram, violin plot)

### 5. GitHub Pages Setup (PARTIAL)
- Created `docs/` folder with `index.html`
- Committed all changes locally
- **BLOCKED**: Need push access to `smannam77/chem169_llm_grader`
- **TODO**: Ask Srikar to add `ajinich` as collaborator
- Once access granted: `git push origin main`, then enable Pages in repo settings

### 6. SSH Setup
- Switched repo from HTTPS to SSH (more reliable auth)
- SSH is working: `ssh -T git@github.com` confirms `ajinich` authenticated

## What's In Progress

### Google Drive Sync + Auto-Grading Pipeline
Goal: Sync submissions from Google Drive, auto-detect new/changed files, grade only what's needed.

**Design:**
```
Google Drive                    Local Repo
/Submissions/                   /assignments/
  RID_001/         ──sync──►      RID_001/submissions/
  RID_002/         ──sync──►      RID_002/submissions/
```

**Components needed:**
1. `rclone` - CLI tool to sync Google Drive → local
2. Grading manifest - tracks {student, route, last_graded_time, file_hash}
3. `sync_and_grade.sh` or `graderbot sync` command

**Handling resubmissions:**
- Don't rely on `_v1`, `_v2` naming (students won't follow it)
- Use file modification time or content hash
- If file is newer than last graded → re-grade
- Manifest tracks what's been graded to avoid duplicates

## Pending Tasks

1. **GitHub push access** - Ask Srikar to add `ajinich` as collaborator
2. ~~Install rclone~~ - DONE: installed to `~/bin/rclone`
3. ~~Configure rclone~~ - DONE: `gdrive` remote configured
4. ~~Create sync script~~ - DONE: `scripts/sync_and_grade.py`
5. ~~Add manifest system~~ - DONE: integrated into sync script
6. ~~Configure GDRIVE_SUBMISSIONS_PATH~~ - DONE: points to TheJinichLab/teaching/Chem169/...
7. ~~Test end-to-end~~ - DONE: Sync + grade working!

### rclone Configuration Steps

Run in terminal:
```bash
~/bin/rclone config
```

1. Type `n` for new remote
2. Name it: `gdrive`
3. Choose: `drive` (Google Drive)
4. Leave client_id blank (Enter)
5. Leave client_secret blank (Enter)
6. Scope: `1` for full access
7. Leave root_folder_id blank (Enter)
8. Leave service_account_file blank (Enter)
9. Edit advanced config: `n`
10. Auto config: `y`
11. Browser opens - sign in with Google
12. Team Drive: `n`
13. Confirm: `y`
14. Quit: `q`

### After rclone is configured

Edit `scripts/sync_and_grade.py` to set your Google Drive path:
```python
GDRIVE_SUBMISSIONS_PATH = "CHEM169_Submissions"  # <-- Change this to your actual path
```

## Key Commands

```bash
# Activate environment
source venv/bin/activate

# === SYNC & GRADE (NEW - RECOMMENDED) ===
# Full pipeline: sync from Google Drive, grade new files, update dashboard
python scripts/sync_and_grade.py --all

# Just sync from Google Drive (no grading)
python scripts/sync_and_grade.py --sync-only

# Just grade new/changed files (no sync)
python scripts/sync_and_grade.py --grade-only

# Preview what would be done (dry run)
python scripts/sync_and_grade.py --all --dry-run

# === MANUAL COMMANDS (still work) ===
# Grade a single notebook
graderbot grade --route assignments/RID_001/instructions.md \
  --notebook "assignments/RID_001/submissions/Student_Name.ipynb" \
  --out "assignments/RID_001/results/Student_Name_grade.json" \
  --provider openai

# Batch grade all submissions for a route
graderbot batch --route assignments/RID_001/instructions.md \
  --submissions assignments/RID_001/submissions/ \
  --out assignments/RID_001/results/ \
  --provider openai

# Generate dashboard
python -c "from graderbot.dashboard import scan_submissions, plot_interactive_dashboard; plot_interactive_dashboard(scan_submissions(), 'docs/index.html')"

# Push to GitHub (once access granted)
git push origin main
```

## File Structure

```
chem169_llm_grader/
├── graderbot/
│   ├── cli.py           # CLI commands
│   ├── grader.py        # Main grading logic
│   ├── prompts.py       # LLM prompts (UPDATED)
│   ├── route_parser.py  # Parse instructions.md (UPDATED)
│   ├── notebook_view.py # Parse notebooks (UPDATED)
│   ├── dashboard.py     # Dashboard generator (NEW)
│   └── ...
├── scripts/
│   └── sync_and_grade.py # Sync from GDrive + grade + dashboard (NEW)
├── assignments/
│   ├── RID_001/
│   │   ├── instructions.md
│   │   ├── submissions/   # Student notebooks
│   │   └── results/       # Grading JSONs
│   └── ...
├── docs/
│   └── index.html        # Dashboard for GitHub Pages
├── grading_manifest.json # Tracks what's been graded (auto-generated)
└── FINAL_INSTRUCTIONS.md # This file
```

## Environment Variables Needed

```bash
OPENAI_API_KEY=sk-...  # For grading with GPT-4
```

## Next Session Prompt

If starting a new Claude Code session, say:

> "Read FINAL_INSTRUCTIONS.md to see where we left off. We were setting up rclone for Google Drive sync and auto-grading pipeline."
