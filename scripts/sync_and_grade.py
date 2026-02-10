#!/usr/bin/env python3
"""
Sync submissions from Google Drive and grade new/updated files.

Usage:
    python scripts/sync_and_grade.py --sync --grade
    python scripts/sync_and_grade.py --sync-only
    python scripts/sync_and_grade.py --grade-only
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configuration
RCLONE_BIN = os.path.expanduser("~/bin/rclone")
RCLONE_REMOTE = "gdrive"  # Name of the rclone remote (from rclone config)
GDRIVE_SUBMISSIONS_PATH = "TheJinichLab/teaching/Chem169/Chem169_269_v2/04_Submissions"
LOCAL_ASSIGNMENTS_DIR = Path(__file__).parent.parent / "assignments"
MANIFEST_FILE = Path(__file__).parent.parent / "grading_manifest.json"

# Route mapping: Google Drive folder name → local RID folder
# Format: "GDrive_folder_name": "local_folder_name"
# Note: Old direct upload folders (RID_XXX_submission) are mostly empty
# Google Form submissions go to google_form_based_submissions/RXXX_submissions (File responses)
ROUTE_MAPPING = {
    # Old direct upload folders (kept for backwards compatibility)
    "RID_001_submission": "RID_001",
    "RID_002_submission": "RID_002",
    "RID_003_submission": "RID_003",
    "RID_004_submission": "RID_004",
    "RID_005_submission": "RID_005",
    "RID_006_submission": "RID_006",
    "RID_007_submission": "RID_007",
    "RID_008_submission": "RID_008",
    "RID_009_submission": "RID_009",
    "RID_012_submission": "RID_012",
}

# Google Form based submissions - these have the actual student files
GDRIVE_FORM_SUBMISSIONS_PATH = "TheJinichLab/teaching/Chem169/Chem169_269_v2/04_Submissions/google_form_based_submissions"
FORM_ROUTE_MAPPING = {
    "R001_Submission_File_responses": "RID_001",
    "R002_Submission_File_responses": "RID_002",
    "R003_Submission (File responses)": "RID_003",
    "R004_Submission _File_responses": "RID_004",
    "R005_submissions (File responses)": "RID_005",
    "R006_submissions (File responses)": "RID_006",
    "R007_submissions (File responses)": "RID_007",
    "R008_submissions (File responses)": "RID_008",
    "R009_submissions (File responses)": "RID_009",
    "R010_submissions (File responses)": "RID_010",
    "R012_submissions (File responses)": "RID_012",
    "R013_Submission_File_responses": "RID_013",
    "R014_submissions (File responses)": "RID_014",
    "R015_submissions (File responses)": "RID_015",
    "R016_submissions (File responses)": "RID_016",
    "R017_submission (File responses)": "RID_017",
    "M1_submission (File responses)": "MID_001",
    "M2_submission (File responses)": "MID_002",
    "M3_submission (File responses)": "MID_003",
}


def load_manifest() -> dict:
    """Load the grading manifest (tracks what's been graded)."""
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    return {"graded_files": {}, "last_sync": None}


def save_manifest(manifest: dict):
    """Save the grading manifest."""
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


def get_file_hash(filepath: Path) -> str:
    """Get MD5 hash of a file (for detecting changes)."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sync_from_gdrive(dry_run: bool = False) -> bool:
    """
    Sync submissions from Google Drive to local assignments folder.

    Returns True if sync succeeded.
    """
    print("=" * 60)
    print("SYNCING FROM GOOGLE DRIVE")
    print("=" * 60)

    if not Path(RCLONE_BIN).exists():
        print(f"Error: rclone not found at {RCLONE_BIN}")
        print("Install with: brew install rclone")
        return False

    # Check if remote is configured
    result = subprocess.run(
        [RCLONE_BIN, "listremotes"],
        capture_output=True,
        text=True
    )

    if f"{RCLONE_REMOTE}:" not in result.stdout:
        print(f"Error: rclone remote '{RCLONE_REMOTE}' not configured")
        print("Run: ~/bin/rclone config")
        return False

    # Sync from old direct upload folders (mostly empty now)
    for gdrive_folder, local_rid in ROUTE_MAPPING.items():
        gdrive_path = f"{RCLONE_REMOTE}:{GDRIVE_SUBMISSIONS_PATH}/{gdrive_folder}"
        local_path = LOCAL_ASSIGNMENTS_DIR / local_rid / "submissions"

        # Create local directory if needed
        local_path.mkdir(parents=True, exist_ok=True)

        print(f"\nSyncing {gdrive_folder} → {local_path}")

        cmd = [
            RCLONE_BIN, "copy",  # Use copy instead of sync to not delete local files
            gdrive_path,
            str(local_path),
            "--include", "*.ipynb",
            "--include", "*.txt",
            "--include", "*.docx",
            "-v",
        ]

        if dry_run:
            cmd.append("--dry-run")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  Warning: sync had issues: {result.stderr}")
        else:
            print(f"  Done")

    # Sync from Google Form based submissions (where most files actually are)
    print("\n" + "=" * 60)
    print("SYNCING GOOGLE FORM SUBMISSIONS")
    print("=" * 60)

    for gdrive_folder, local_rid in FORM_ROUTE_MAPPING.items():
        gdrive_path = f"{RCLONE_REMOTE}:{GDRIVE_FORM_SUBMISSIONS_PATH}/{gdrive_folder}"
        local_path = LOCAL_ASSIGNMENTS_DIR / local_rid / "submissions"

        # Create local directory if needed
        local_path.mkdir(parents=True, exist_ok=True)

        print(f"\nSyncing {gdrive_folder} → {local_rid}")

        # Google Forms creates subfolders for each file type, so we need to copy recursively
        cmd = [
            RCLONE_BIN, "copy",  # Use copy to merge with existing files
            gdrive_path,
            str(local_path),
            "--include", "*.ipynb",
            "--include", "*.txt",
            "--include", "*.docx",
            "-v",
        ]

        if dry_run:
            cmd.append("--dry-run")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  Warning: sync had issues: {result.stderr}")
        else:
            print(f"  Done")

    # Flatten Google Forms subfolders (they create "File responses" subfolders)
    print("\n" + "=" * 60)
    print("FLATTENING SUBFOLDERS")
    print("=" * 60)
    flatten_subfolders()

    return True


def flatten_subfolders():
    """
    Flatten Google Forms 'File responses' subfolders into main submissions folder.

    Google Forms creates subfolders like 'Deliverable file (.txt) (File responses)/'
    when there are multiple file upload fields. This moves files up to the main
    submissions folder so the grader can find them.
    """
    import shutil

    for rid_folder in LOCAL_ASSIGNMENTS_DIR.glob("*ID_*"):  # Matches RID_* and MID_*
        submissions_dir = rid_folder / "submissions"
        if not submissions_dir.exists():
            continue

        # Find all "File responses" subfolders
        for subdir in submissions_dir.iterdir():
            if subdir.is_dir() and "File responses" in subdir.name:
                # Move all files from subfolder to parent
                for f in subdir.iterdir():
                    if f.is_file():
                        dest = submissions_dir / f.name
                        if not dest.exists():
                            shutil.move(str(f), str(dest))
                        else:
                            # File already exists, skip
                            f.unlink()
                # Remove empty subfolder
                try:
                    subdir.rmdir()
                except OSError:
                    pass  # Not empty, skip

    print("Done flattening subfolders")


def find_new_or_changed_files(manifest: dict) -> list[tuple[Path, str]]:
    """
    Find notebooks that are new or changed since last grading.

    Returns list of (notebook_path, route_id) tuples.
    """
    to_grade = []
    graded_files = manifest.get("graded_files", {})

    for rid_folder in LOCAL_ASSIGNMENTS_DIR.glob("RID_*"):
        route_id = rid_folder.name
        submissions_dir = rid_folder / "submissions"

        if not submissions_dir.exists():
            continue

        for notebook in submissions_dir.glob("*.ipynb"):
            file_key = str(notebook.relative_to(LOCAL_ASSIGNMENTS_DIR))
            current_hash = get_file_hash(notebook)

            # Check if file is new or changed
            if file_key not in graded_files:
                print(f"  New: {notebook.name}")
                to_grade.append((notebook, route_id))
            elif graded_files[file_key]["hash"] != current_hash:
                print(f"  Changed: {notebook.name}")
                to_grade.append((notebook, route_id))
            # else: unchanged, skip

    return to_grade


def grade_notebook(notebook_path: Path, route_id: str, provider: str = "openai") -> bool:
    """
    Grade a single notebook.

    Returns True if grading succeeded.
    """
    route_file = LOCAL_ASSIGNMENTS_DIR / route_id / "instructions.md"
    results_dir = LOCAL_ASSIGNMENTS_DIR / route_id / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    output_file = results_dir / f"{notebook_path.stem}_grade.json"

    if not route_file.exists():
        print(f"    Warning: No instructions.md for {route_id}, skipping")
        return False

    cmd = [
        sys.executable, "-m", "graderbot.cli", "grade",
        "--route", str(route_file),
        "--notebook", str(notebook_path),
        "--out", str(output_file),
        "--provider", provider,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"    Error: {result.stderr}")
        return False

    return True


def grade_new_submissions(manifest: dict, provider: str = "openai") -> dict:
    """
    Grade all new/changed submissions.

    Returns updated manifest.
    """
    print("\n" + "=" * 60)
    print("GRADING NEW/CHANGED SUBMISSIONS")
    print("=" * 60)

    to_grade = find_new_or_changed_files(manifest)

    if not to_grade:
        print("\nNo new or changed files to grade.")
        return manifest

    print(f"\nFound {len(to_grade)} files to grade.\n")

    graded_files = manifest.get("graded_files", {})

    for i, (notebook_path, route_id) in enumerate(to_grade, 1):
        print(f"[{i}/{len(to_grade)}] Grading {notebook_path.name}...")

        success = grade_notebook(notebook_path, route_id, provider)

        if success:
            file_key = str(notebook_path.relative_to(LOCAL_ASSIGNMENTS_DIR))
            graded_files[file_key] = {
                "hash": get_file_hash(notebook_path),
                "graded_at": datetime.now().isoformat(),
                "route_id": route_id,
            }
            print(f"    Done")
        else:
            print(f"    Failed")

    manifest["graded_files"] = graded_files
    manifest["last_graded"] = datetime.now().isoformat()

    return manifest


def regenerate_dashboard():
    """Regenerate the dashboard HTML."""
    print("\n" + "=" * 60)
    print("REGENERATING DASHBOARD")
    print("=" * 60)

    try:
        from graderbot.dashboard import scan_submissions, plot_interactive_dashboard

        student_routes = scan_submissions()
        plot_interactive_dashboard(student_routes, "docs/index.html")
        print("Dashboard updated: docs/index.html")
    except Exception as e:
        print(f"Error regenerating dashboard: {e}")


def main():
    parser = argparse.ArgumentParser(description="Sync and grade submissions")
    parser.add_argument("--sync", action="store_true", help="Sync from Google Drive")
    parser.add_argument("--grade", action="store_true", help="Grade new/changed files")
    parser.add_argument("--dashboard", action="store_true", help="Regenerate dashboard")
    parser.add_argument("--sync-only", action="store_true", help="Only sync, don't grade")
    parser.add_argument("--grade-only", action="store_true", help="Only grade, don't sync")
    parser.add_argument("--provider", default="openai", help="LLM provider (default: openai)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--all", action="store_true", help="Sync + grade + dashboard")

    args = parser.parse_args()

    # Default to --all if no specific action
    if not any([args.sync, args.grade, args.dashboard, args.sync_only, args.grade_only, args.all]):
        args.all = True

    manifest = load_manifest()

    # Sync
    if args.sync or args.sync_only or args.all:
        success = sync_from_gdrive(dry_run=args.dry_run)
        if not success and not args.dry_run:
            print("Sync failed. Check rclone configuration.")

    # Grade
    if args.grade or args.grade_only or args.all:
        if not args.dry_run:
            manifest = grade_new_submissions(manifest, provider=args.provider)
            save_manifest(manifest)

    # Dashboard
    if args.dashboard or args.all:
        if not args.dry_run:
            regenerate_dashboard()

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
