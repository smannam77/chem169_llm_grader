# Grading Workflow

Standard process for syncing submissions, grading, and updating the dashboard.

## Quick Command (Full Update)

```bash
# One-liner for routine updates
python3 scripts/sync_and_grade.py --sync --grade && python3 -c "
import matplotlib; matplotlib.use('Agg')
from graderbot.dashboard import plot_interactive_dashboard, scan_submissions
plot_interactive_dashboard(scan_submissions(), 'docs/index.html')
" && python3 -c "
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

### 2. Grade New Submissions

```bash
python3 scripts/sync_and_grade.py --grade-only
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
1. Ensure sync pulled the latest files
2. Dashboard uses newest grade file by mtime - regrade to update

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
