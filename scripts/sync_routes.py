#!/usr/bin/env python3
"""
Sync route instructions from the gym portal repository.

This script copies route .md files from the climbing-gym-app repo
to the grader's assignments folders as instructions.md.

Usage:
    python scripts/sync_routes.py              # Sync all routes
    python scripts/sync_routes.py --dry-run    # Preview what would be synced
    python scripts/sync_routes.py R006 R007    # Sync specific routes only
"""

import argparse
import re
import shutil
from pathlib import Path

# Configuration - update these if repos move
GYM_PORTAL_ROUTES = Path.home() / "Documents/repos/climbing-gym-app/content/routes"
GRADER_ASSIGNMENTS = Path(__file__).parent.parent / "assignments"


def find_route_file(routes_dir: Path, route_num: str) -> Path | None:
    """Find the route .md file for a given route number (e.g., '001', '006')."""
    pattern = f"R{route_num}_*.md"
    matches = list(routes_dir.glob(pattern))
    if matches:
        return matches[0]
    return None


def get_available_routes(routes_dir: Path) -> list[str]:
    """Get list of available route numbers from the gym portal."""
    routes = []
    for f in routes_dir.glob("R*.md"):
        match = re.match(r"R(\d+)_", f.name)
        if match:
            routes.append(match.group(1))
    return sorted(routes)


def sync_route(route_num: str, dry_run: bool = False) -> bool:
    """
    Sync a single route from gym portal to grader.

    Returns True if synced successfully.
    """
    source_file = find_route_file(GYM_PORTAL_ROUTES, route_num)

    if not source_file:
        print(f"  [SKIP] R{route_num}: No source file found in gym portal")
        return False

    dest_dir = GRADER_ASSIGNMENTS / f"RID_{route_num}"
    dest_file = dest_dir / "instructions.md"

    # Check if destination already exists and is same
    if dest_file.exists():
        source_content = source_file.read_text()
        dest_content = dest_file.read_text()
        if source_content == dest_content:
            print(f"  [OK] R{route_num}: Already up to date")
            return True
        else:
            action = "UPDATE"
    else:
        action = "NEW"

    if dry_run:
        print(f"  [DRY-RUN] {action} R{route_num}: {source_file.name} → {dest_file}")
        return True

    # Create destination directory if needed
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy the file
    shutil.copy2(source_file, dest_file)
    print(f"  [{action}] R{route_num}: {source_file.name} → instructions.md")
    return True


def main():
    parser = argparse.ArgumentParser(description="Sync route instructions from gym portal")
    parser.add_argument("routes", nargs="*", help="Specific routes to sync (e.g., 006 007)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without copying")
    parser.add_argument("--portal-path", type=Path, help="Override gym portal routes path")
    args = parser.parse_args()

    global GYM_PORTAL_ROUTES
    if args.portal_path:
        GYM_PORTAL_ROUTES = args.portal_path

    if not GYM_PORTAL_ROUTES.exists():
        print(f"Error: Gym portal routes not found at {GYM_PORTAL_ROUTES}")
        print("Update GYM_PORTAL_ROUTES in this script or use --portal-path")
        return 1

    print("=" * 60)
    print("SYNCING ROUTE INSTRUCTIONS FROM GYM PORTAL")
    print("=" * 60)
    print(f"Source: {GYM_PORTAL_ROUTES}")
    print(f"Dest:   {GRADER_ASSIGNMENTS}")
    print()

    # Determine which routes to sync
    if args.routes:
        # Normalize route numbers (handle both "6" and "006" and "R006")
        routes = []
        for r in args.routes:
            r = r.upper().replace("RID_", "").replace("R", "")
            routes.append(r.zfill(3))
    else:
        routes = get_available_routes(GYM_PORTAL_ROUTES)

    print(f"Routes to sync: {', '.join(f'R{r}' for r in routes)}")
    print()

    synced = 0
    for route_num in routes:
        if sync_route(route_num, dry_run=args.dry_run):
            synced += 1

    print()
    print("=" * 60)
    print(f"Synced {synced}/{len(routes)} routes" + (" (dry run)" if args.dry_run else ""))
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
