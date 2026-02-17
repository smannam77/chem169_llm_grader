# Grading Workflow

Standard process for syncing submissions, grading, and updating the dashboard.

## Quick Command (Full Update)

```bash
# Simplest: sync + grade + dashboard in one command (default behavior)
python3 scripts/sync_and_grade.py

# Or with explicit flags:
python3 scripts/sync_and_grade.py --all
```

The script now handles everything: sync → grade → dashboard generation.

**Before pushing**, redact any exposed GitHub tokens:
```bash
python3 -c "
import re
with open('docs/index.html') as f: c = f.read()
c = re.sub(r'gh[pohsr]_[A-Za-z0-9_]{30,}', '[REDACTED]', c)
with open('docs/index.html', 'w') as f: f.write(c)
print('Secrets redacted')
"
```

## Step-by-Step Process

### 1. Sync Submissions from Google Drive

```bash
python3 scripts/sync_and_grade.py --sync-only
```

This syncs from two locations:
- **Old direct uploads**: `04_Submissions/RID_XXX_submission/`
- **Google Form submissions**: `04_Submissions/google_form_based_submissions/RXXX_submissions/`

**Note**: Google Form folders have "File responses" subfolders that get flattened automatically.

### 2. Grade New Submissions (including resubmissions)

The grading script automatically detects:
- New files (including `_v2` resubmissions)
- Changed files (same name, different content)

```bash
python3 scripts/sync_and_grade.py --grade-only
```

**For text routes** (not handled by sync_and_grade.py), run batch-text which will skip already-graded files unless you delete the old grade:

```bash
# Regrade all text submissions for a route
python3 -m graderbot.cli batch-text \
  -r assignments/RID_007/instructions.md \
  -i assignments/RID_007/submissions \
  -o assignments/RID_007/results \
  --route-id RID_007 --provider openai
```

Or grade specific routes manually:

```bash
# Notebook routes
python3 -m graderbot.cli grade \
  --route assignments/RID_XXX/instructions.md \
  --notebook "path/to/notebook.ipynb" \
  --out assignments/RID_XXX/results/student_grade.json \
  --provider openai

# Text routes (RID_006, RID_007, RID_008, RID_013)
python3 -m graderbot.cli batch-text \
  -r assignments/RID_XXX/instructions.md \
  -i assignments/RID_XXX/submissions \
  -o assignments/RID_XXX/results \
  --route-id RID_XXX \
  --provider openai
```

### 3. Regenerate Dashboard

**IMPORTANT**: Use `plot_interactive_dashboard()` directly, NOT `main(interactive=False)`:

```bash
python3 -c "
import matplotlib; matplotlib.use('Agg')
from graderbot.dashboard import plot_interactive_dashboard, scan_submissions
student_routes = scan_submissions()
plot_interactive_dashboard(student_routes, output_path='docs/index.html')
"
```

### 4. Redact Secrets Before Pushing

Student submissions may contain GitHub tokens. Redact before pushing:

```bash
python3 -c "
import re
with open('docs/index.html') as f: content = f.read()
content = re.sub(r'gh[pohsr]_[A-Za-z0-9_]{30,}', '[REDACTED]', content)
with open('docs/index.html', 'w') as f: f.write(content)
print('GitHub tokens redacted')
"
```

### 5. Commit and Push

```bash
git add docs/index.html assignments/*/results/*.json
git commit -m "Update grades"
git push
```

---

## Troubleshooting

### Submission not detected
- Check file naming: must contain `_deliverable`, `_text_submission`, `_code`, or `_submission_file`
- Logbook files are excluded (contain `logbook` in name)

### Notebook too large to grade
Strip outputs first:
```python
import json
with open('notebook.ipynb') as f: nb = json.load(f)
for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code':
        cell['outputs'] = []
with open('notebook_stripped.ipynb', 'w') as f: json.dump(nb, f)
```

### Grade shows "needs work" but no feedback
Route was submitted but not graded. Run grading for that route.

### Resubmissions (v2) not reflected

The grading script detects resubmissions two ways:
- **Same filename, new content**: Detected via hash change → auto-regrades
- **New filename** (e.g., `_v2.ipynb`): Detected as new file → auto-grades

The dashboard uses the **newest grade file by mtime**, so v2 grades automatically take precedence.

If a v2 still isn't showing:
1. Check sync pulled the file: `ls assignments/RID_XXX/submissions/*v2*`
2. Check if graded: `ls assignments/RID_XXX/results/*student*`
3. Force regrade by deleting old grade file and re-running

**Note**: `sync_and_grade.py` only handles `.ipynb` files. For text route resubmissions (RID_006, 007, 008, 013), manually run `batch-text` which will regrade all submissions

### Student name not matching
Check `NAME_ALIASES` in `dashboard.py` for known aliases.

---

## File Patterns

| Route Type | Accepted Patterns |
|------------|-------------------|
| Notebook routes | `*.ipynb` |
| Text routes (R006, R007, R008, R013) | `*_deliverable*.txt`, `*_text_submission*.txt`, `*_code*.txt`, `*.docx` |

## Key Files

- `scripts/sync_and_grade.py` - Sync and grade automation
- `graderbot/dashboard.py` - Dashboard generation
- `graderbot/text_view.py` - Text submission handling
- `docs/index.html` - Published dashboard
- `grading_manifest.json` - Tracks graded files (hash-based change detection)

---

## Adding New Routes

When a new route (e.g., R021) is added:

### 1. Find the Google Drive folder name
```bash
~/bin/rclone lsd "gdrive:TheJinichLab/teaching/Chem169/Chem169_269_v2/04_Submissions/google_form_based_submissions" | grep -i R021
```

### 2. Add mapping to `scripts/sync_and_grade.py`
Edit `FORM_ROUTE_MAPPING` to add the new route:
```python
"R021_submissions (File responses)": "RID_021",
```

### 3. Create local folder structure
```bash
mkdir -p assignments/RID_021/{submissions,results}
```

### 4. Copy instructions from climbing-gym-app
**Instructions source**: `/Users/ajinich/Documents/repos/climbing-gym-app/content/routes/`
```bash
cp /Users/ajinich/Documents/repos/climbing-gym-app/content/routes/R021_*.md \
   assignments/RID_021/instructions.md
```

### 5. Run sync and grade
```bash
python3 scripts/sync_and_grade.py
```

---

## Handling Late Submissions

### Check actual submission time (not sync time!)
```bash
# Get Google Drive timestamps for a specific route
~/bin/rclone lsl "gdrive:TheJinichLab/teaching/Chem169/Chem169_269_v2/04_Submissions/google_form_based_submissions/M3_submission (File responses)" | grep -i "student_name"
```

### Mark as unexcused late
Move the file to the `unexcused_late` subfolder:
```bash
mkdir -p assignments/RID_XXX/submissions/unexcused_late
mv "assignments/RID_XXX/submissions/Student_Name_file.ipynb" \
   "assignments/RID_XXX/submissions/unexcused_late/"
```

The dashboard will show these as "🚫 Unexcused late" without grading them.

---

## Manifest Management

The `grading_manifest.json` tracks which files have been graded (by MD5 hash).

### If manifest gets out of sync
Rebuild it from actual results on disk:
```python
python3 << 'EOF'
import json, hashlib
from pathlib import Path
from datetime import datetime

def get_hash(fp):
    h = hashlib.md5()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

assignments = Path("assignments")
graded = {}

for rid in sorted(list(assignments.glob("RID_*")) + list(assignments.glob("MID_*"))):
    results = rid / "results"
    subs = rid / "submissions"
    if not results.exists() or not subs.exists():
        continue
    for r in results.glob("*.json"):
        if r.stem == "summary":
            continue
        sub = subs / f"{r.stem.replace('_grade', '')}.ipynb"
        if sub.exists():
            key = str(sub.relative_to(assignments))
            graded[key] = {"hash": get_hash(sub), "graded_at": datetime.fromtimestamp(r.stat().st_mtime).isoformat(), "route_id": rid.name}

manifest = {"graded_files": graded, "last_sync": datetime.now().isoformat(), "manifest_rebuilt": datetime.now().isoformat()}
with open("grading_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Rebuilt manifest with {len(graded)} entries")
EOF
```

---

## Name Alias Issues

If a student's submissions aren't being matched correctly, add an alias to `NAME_ALIASES` in `graderbot/dashboard.py`:

```python
NAME_ALIASES = {
    # ... existing aliases ...
    'wong_jessica_rid': 'wong_jessica',  # Google Forms artifact
}
```

Common issues:
- Google Forms adds ` - Student Name` suffix to filenames
- Typos in student names
- First/last name swapped
- Route ID included in parsed name (`_rid` suffix)
