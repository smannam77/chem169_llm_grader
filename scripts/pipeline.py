#!/usr/bin/env python3
"""
Master grading pipeline script.

Usage:
    python scripts/pipeline.py status              # Show what needs attention
    python scripts/pipeline.py sync                # Sync from Google Drive
    python scripts/pipeline.py grade               # Grade all new/changed
    python scripts/pipeline.py grade R002          # Grade specific route only
    python scripts/pipeline.py grade R002 --force  # Regrade all R002 (ignore manifest)
    python scripts/pipeline.py dashboard           # Regenerate dashboard
    python scripts/pipeline.py push                # Push dashboard to GitHub
    python scripts/pipeline.py full                # sync + grade + dashboard + push
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

RCLONE_BIN = os.path.expanduser("~/bin/rclone")
RCLONE_REMOTE = "gdrive"
GDRIVE_FORM_SUBMISSIONS_PATH = "TheJinichLab/teaching/Chem169/Chem169_269_v2/04_Submissions/google_form_based_submissions"
LOCAL_ASSIGNMENTS_DIR = Path(__file__).parent.parent / "assignments"
MANIFEST_FILE = Path(__file__).parent.parent / "grading_manifest.json"
DOCS_DIR = Path(__file__).parent.parent / "docs"

# Google Form folder → local folder mapping
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
    "F036_submissions (File responses)": "F036",
    "F037_submissions (File responses)": "F037",
}

# ============================================================================
# Manifest helpers
# ============================================================================

def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    return {"graded_files": {}, "last_sync": None}


def save_manifest(manifest: dict):
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


def get_file_hash(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ============================================================================
# Status command
# ============================================================================

def cmd_status():
    """Show current grading status - what needs attention."""
    print("=" * 60)
    print("GRADING PIPELINE STATUS")
    print("=" * 60)

    manifest = load_manifest()
    graded = manifest.get("graded_files", {})

    # Count submissions and grades per route
    ungraded_by_route = defaultdict(list)
    graded_by_route = defaultdict(int)

    for pattern in ["RID_*", "MID_*"]:
        for rid_folder in sorted(LOCAL_ASSIGNMENTS_DIR.glob(pattern)):
            route_id = rid_folder.name
            submissions_dir = rid_folder / "submissions"

            if not submissions_dir.exists():
                continue

            for nb in submissions_dir.glob("*.ipynb"):
                key = str(nb.relative_to(LOCAL_ASSIGNMENTS_DIR))
                if key not in graded:
                    ungraded_by_route[route_id].append(nb.name)
                else:
                    graded_by_route[route_id] += 1

    # Print summary
    print("\n📊 Graded submissions by route:")
    for route in sorted(graded_by_route.keys()):
        print(f"  {route}: {graded_by_route[route]}")

    total_ungraded = sum(len(v) for v in ungraded_by_route.values())
    if total_ungraded > 0:
        print(f"\n⚠️  Ungraded submissions: {total_ungraded}")
        for route in sorted(ungraded_by_route.keys()):
            files = ungraded_by_route[route]
            if files:
                print(f"  {route}: {len(files)} files")
                for f in files[:3]:  # Show first 3
                    print(f"    - {f[:50]}...")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")
    else:
        print("\n✅ All submissions graded!")

    # Last sync info
    last_sync = manifest.get("last_sync")
    if last_sync:
        print(f"\n🕐 Last sync: {last_sync}")

    last_graded = manifest.get("last_graded")
    if last_graded:
        print(f"🕐 Last grade: {last_graded}")


# ============================================================================
# Sync command
# ============================================================================

def flatten_subfolders():
    """Flatten Google Forms 'File responses' subfolders."""
    for rid_folder in LOCAL_ASSIGNMENTS_DIR.glob("*"):
        submissions_dir = rid_folder / "submissions"
        if not submissions_dir.exists():
            continue

        for subdir in list(submissions_dir.iterdir()):
            if subdir.is_dir() and "File responses" in subdir.name:
                for f in subdir.iterdir():
                    if f.is_file():
                        dest = submissions_dir / f.name
                        if not dest.exists():
                            shutil.move(str(f), str(dest))
                        else:
                            f.unlink()
                try:
                    subdir.rmdir()
                except OSError:
                    pass


def cmd_sync(routes=None):
    """Sync submissions from Google Drive."""
    print("=" * 60)
    print("SYNCING FROM GOOGLE DRIVE")
    print("=" * 60)

    if not Path(RCLONE_BIN).exists():
        print(f"Error: rclone not found at {RCLONE_BIN}")
        return False

    # Filter routes if specified
    mapping = FORM_ROUTE_MAPPING
    if routes:
        routes_upper = [r.upper() for r in routes]
        # Handle both "R002" and "RID_002" formats
        mapping = {k: v for k, v in mapping.items()
                   if v in routes_upper or v.replace("RID_", "R").replace("MID_", "M") in routes_upper
                   or v.replace("RID_", "").replace("MID_", "M") in routes_upper}

    for gdrive_folder, local_rid in mapping.items():
        gdrive_path = f"{RCLONE_REMOTE}:{GDRIVE_FORM_SUBMISSIONS_PATH}/{gdrive_folder}"
        local_path = LOCAL_ASSIGNMENTS_DIR / local_rid / "submissions"
        local_path.mkdir(parents=True, exist_ok=True)

        print(f"\n📥 {gdrive_folder} → {local_rid}")

        cmd = [
            RCLONE_BIN, "copy",
            gdrive_path, str(local_path),
            "--include", "*.ipynb",
            "--include", "*.txt",
            "-v",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ⚠️  Warning: {result.stderr[:100]}")

    print("\n📁 Flattening subfolders...")
    flatten_subfolders()

    # Update manifest
    manifest = load_manifest()
    manifest["last_sync"] = datetime.now().isoformat()
    save_manifest(manifest)

    print("✅ Sync complete")
    return True


# ============================================================================
# Grade command
# ============================================================================

def grade_notebook(notebook_path: Path, route_id: str, provider: str = "openai") -> bool:
    """Grade a single notebook."""
    route_file = LOCAL_ASSIGNMENTS_DIR / route_id / "instructions.md"
    results_dir = LOCAL_ASSIGNMENTS_DIR / route_id / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    output_file = results_dir / f"{notebook_path.stem}_grade.json"

    if not route_file.exists():
        return False

    cmd = [
        sys.executable, "-m", "graderbot.cli", "grade",
        "--route", str(route_file),
        "--notebook", str(notebook_path),
        "--out", str(output_file),
        "--provider", provider,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def cmd_grade(routes=None, force=False, provider="openai"):
    """Grade submissions. Optionally filter by route or force regrade."""
    print("=" * 60)
    print("GRADING SUBMISSIONS")
    print("=" * 60)

    manifest = load_manifest()
    graded = manifest.get("graded_files", {})

    # If force and routes specified, clear those from manifest
    if force and routes:
        routes_upper = [r.upper().replace("R", "RID_").replace("M", "MID_") if not r.startswith(("RID", "MID")) else r.upper() for r in routes]
        keys_to_remove = [k for k in graded if any(r in k for r in routes_upper)]
        for k in keys_to_remove:
            del graded[k]
        print(f"🔄 Force regrade: cleared {len(keys_to_remove)} entries from manifest")

    # Find files to grade
    to_grade = []

    for pattern in ["RID_*", "MID_*", "F*"]:
        for rid_folder in sorted(LOCAL_ASSIGNMENTS_DIR.glob(pattern)):
            route_id = rid_folder.name

            # Filter by route if specified
            if routes:
                routes_upper = [r.upper() for r in routes]
                route_short = route_id.replace("RID_", "R").replace("MID_", "M")
                if route_id.upper() not in routes_upper and route_short not in routes_upper:
                    continue

            submissions_dir = rid_folder / "submissions"
            if not submissions_dir.exists():
                continue

            for nb in submissions_dir.glob("*.ipynb"):
                key = str(nb.relative_to(LOCAL_ASSIGNMENTS_DIR))
                if key not in graded:
                    to_grade.append((nb, route_id))

    if not to_grade:
        print("\n✅ Nothing to grade!")
        return

    print(f"\n📝 Found {len(to_grade)} files to grade\n")

    success_count = 0
    for i, (notebook_path, route_id) in enumerate(to_grade, 1):
        print(f"[{i}/{len(to_grade)}] {notebook_path.name[:50]}...", end=" ", flush=True)

        success = grade_notebook(notebook_path, route_id, provider)

        if success:
            key = str(notebook_path.relative_to(LOCAL_ASSIGNMENTS_DIR))
            graded[key] = {
                "hash": get_file_hash(notebook_path),
                "graded_at": datetime.now().isoformat(),
                "route_id": route_id,
            }
            print("✓")
            success_count += 1
        else:
            print("✗")

    manifest["graded_files"] = graded
    manifest["last_graded"] = datetime.now().isoformat()
    save_manifest(manifest)

    print(f"\n✅ Graded {success_count}/{len(to_grade)} files")


# ============================================================================
# Dashboard command
# ============================================================================

def cmd_dashboard():
    """Regenerate the dashboard."""
    print("=" * 60)
    print("REGENERATING DASHBOARD")
    print("=" * 60)

    try:
        import matplotlib
        matplotlib.use('Agg')
        from graderbot.dashboard import main
        main(interactive=True)

        # Copy to docs
        shutil.copy(
            LOCAL_ASSIGNMENTS_DIR.parent / "dashboard.html",
            DOCS_DIR / "index.html"
        )
        print("✅ Dashboard updated: docs/index.html")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


# ============================================================================
# Push command
# ============================================================================

def cmd_push(message=None):
    """Push dashboard to GitHub."""
    print("=" * 60)
    print("PUSHING TO GITHUB")
    print("=" * 60)

    if message is None:
        message = f"Update dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    cmds = [
        ["git", "add", "docs/index.html"],
        ["git", "commit", "-m", message],
        ["git", "push"],
    ]

    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            if "nothing to commit" in result.stdout + result.stderr:
                print("ℹ️  Nothing to commit")
                return True
            print(f"❌ Error: {result.stderr}")
            return False

    print("✅ Pushed to GitHub")
    return True


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Grading pipeline master script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/pipeline.py status              # What needs attention?
    python scripts/pipeline.py sync                # Sync all from GDrive
    python scripts/pipeline.py sync R002 M1        # Sync specific routes
    python scripts/pipeline.py grade               # Grade all new
    python scripts/pipeline.py grade R002          # Grade only R002
    python scripts/pipeline.py grade R002 --force  # Regrade ALL R002
    python scripts/pipeline.py dashboard           # Regenerate dashboard
    python scripts/pipeline.py push                # Push to GitHub
    python scripts/pipeline.py full                # Do everything
        """
    )

    parser.add_argument("command", choices=["status", "sync", "grade", "dashboard", "push", "full"],
                        help="Command to run")
    parser.add_argument("routes", nargs="*", help="Routes to operate on (e.g., R002 M1)")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Force regrade (clear manifest for specified routes)")
    parser.add_argument("--provider", "-p", default="openai",
                        help="LLM provider (default: openai)")
    parser.add_argument("--message", "-m", help="Commit message for push")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()

    elif args.command == "sync":
        cmd_sync(args.routes if args.routes else None)

    elif args.command == "grade":
        cmd_grade(args.routes if args.routes else None, args.force, args.provider)

    elif args.command == "dashboard":
        cmd_dashboard()

    elif args.command == "push":
        cmd_push(args.message)

    elif args.command == "full":
        print("🚀 Running full pipeline...\n")
        cmd_sync(args.routes if args.routes else None)
        print()
        cmd_grade(args.routes if args.routes else None, args.force, args.provider)
        print()
        cmd_dashboard()
        print()
        cmd_push(args.message)


if __name__ == "__main__":
    main()
