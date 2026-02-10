"""Dashboard prototype: visualize student submission statistics."""

import os
import re
from pathlib import Path
from collections import defaultdict

# Try plotly first for interactive, fall back to matplotlib
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

import matplotlib.pyplot as plt


# Known name aliases for students who submit with inconsistent naming
NAME_ALIASES = {
    # Kao variations
    'kao_yingchieh': 'kao_ying',
    'kao_ying chieh': 'kao_ying',
    'kao_ying_chieh': 'kao_ying',
    # Tsai variations (canonical: tsai_i-shan -> displays as "Tsai I-Shan")
    'tsai_i': 'tsai_i-shan',
    'tsai_i_shan': 'tsai_i-shan',
    # Jaramillo typo
    'jaramilo_jonathan': 'jaramillo_jonathan',
    # Gupta typo
    'gupa_siddhartha': 'gupta_siddhartha',
    # Hossain variations
    'md_saddam_hossain': 'hossain_mdsaddam',
    'md_saddam': 'hossain_mdsaddam',
    'saddam_hossain': 'hossain_mdsaddam',
    # Xinyi Shang variations (Google account says "minji shang", submits as Xinyi_Shang)
    'xinyi_shang_': 'xinyi_shang',
    'shang_xinyi': 'xinyi_shang',
    'shang_xinyi_rid_xyz_code_minji_shang': 'xinyi_shang',
    # RID_RXXX filename pattern leaves trailing _rid
    'srikumaran_sarayu_rid': 'srikumaran_sarayu',
    'spock_lilian_rid': 'spock_lilian',
    # Deliverable filename mistaken for student name
    'deliverable_rid': 'lee_minji',
    # Route-prefix extraction artifact
    'pham_richie_pham': 'pham_richie',
    # Weeranarawat typo (missing 'a')
    'weeranarwat_anya': 'weeranarawat_anya',
    # First/Last name swapped
    'jinyi_zhang': 'zhang_jinyi',
    'jingru_zhao': 'zhao_jingru',
    'anya_weeranarawat': 'weeranarawat_anya',
    'heyang_haoye': 'haoye_heyang',
    'tito_tapia': 'tapia_tito',
    # Single-word names from Route_XXX patterns
    'tiwary': 'tiwary_ayush',
    'huang': 'huang_terry',
    'pineda': 'pineda_leo',
    # Filename artifact: Ma-Richard_name_RID_007_deliverable
    'ma_richard_name': 'ma_richard',
    # Midterm naming issues (filenames with RID_MO2, MT1, etc.)
    'alvarado_isacc_rid_mo2_code_isacc_a': 'alvarado_isacc',
    'alvarado_isacc_rid_mo3_code_isacc_a': 'alvarado_isacc',
    'alvarado_isacc_rid_mo3_code_isacc_alvarado': 'alvarado_isacc',
    'anonich_ryan_mt1': 'anonich_ryan',
    'anonich_ryan_mt1_001_code': 'anonich_ryan',
    'anonich_ryan_mt1_003_code': 'anonich_ryan',
    # Swapped first/last name
    'abdulghani_binnafisah': 'binnafisah_abdulghani',
    # Jaramillo typo variant (double l missing)
    'jaramllo_jonathan': 'jaramillo_jonathan',
    # Saldivar middle name included in filename
    'saldivar_garcia': 'saldivar_alexis',
    # Trailing _rid artifacts from midterm filenames
    'pham_richie_rid': 'pham_richie',
}

# Students not enrolled (exclude from dashboard)
EXCLUDED_STUDENTS = {
    'wagner_eli',
    'schaap_tamar',
    'cruz_jade',
    'test_student',   # Adrian's own test submissions
    'deliverable',    # Bare filename artifact from deliverable_RID_XXX files
    'm3_brenda_o.',   # Unknown midterm submission - cannot identify student
    'm3',             # Bare "M3 -" filename artifact
}

# Routes that get a "free pass" - always count as sent regardless of grade
# (Use for routes with confusing instructions where students shouldn't be penalized)
FREE_PASS_ROUTES = {
    'RID_007',  # Instructions were unclear, students submitted wrong format
}

# Track files with non-standard naming (populated during scan)
NON_STANDARD_FILES = []


def extract_student_name(filename: str, track_non_standard: bool = True) -> str:
    """Extract student name from submission filename.

    Args:
        filename: The submission filename
        track_non_standard: If True, add non-standard files to NON_STANDARD_FILES list

    Returns:
        Normalized student name or None if cannot be determined
    """
    # Remove extension
    name = Path(filename).stem
    original_name = name

    # Handle "Route_XXX_..._StudentName" format - extract last word as student name
    if re.match(r'^Route', name, flags=re.IGNORECASE):
        # Split by underscore and get the last part (should be student name)
        parts = name.split('_')
        if len(parts) >= 2:
            # Last part is likely the student name
            last_part = parts[-1]
            # Make sure it's not a number or common word
            if last_part and not re.match(r'^\d+$', last_part) and last_part.lower() not in ('code', 'notebook', 'ipynb'):
                name = last_part
                if track_non_standard:
                    NON_STANDARD_FILES.append({
                        'original': filename,
                        'extracted_name': last_part,
                        'issue': 'Route-prefixed filename'
                    })
            else:
                return None
        else:
            return None

    # Remove common suffixes like _RID_001_code, _R007_code, _RID002_code, _RD_003, _Route_001, _001_code, etc.
    # Also handles midterms: _MID_001, _M001, _M1, _M01, _RID_M001, _MT1, _MO2, _RID_MO2, etc.
    # Handles: _RID_001, _RID001, _R001, _R_001, _RD_001, _Route_001, _001, _MID_001, _M1, _M01, _RID_M001,
    #          _MT1, _MT_001 (midterm T variant), _MO1, _RID_MO2 (letter O instead of zero), etc.
    name = re.sub(r'_(?:R(?:ID|D|oute)?_?(?:M(?:ID|T|O)?)?_?\d+|Route_?\d+|M(?:ID|T|O)?_?\d+).*$', '', name, flags=re.IGNORECASE)
    # Also handle bare _001_ patterns (no R prefix)
    name = re.sub(r'_0\d{2}_.*$', '', name, flags=re.IGNORECASE)
    # Remove student ID numbers like _A10589679
    name = re.sub(r'_A\d{7,9}', '', name, flags=re.IGNORECASE)
    name = re.sub(r'_code$', '', name, flags=re.IGNORECASE)

    # Skip if name still looks like a route/assignment identifier
    if re.match(r'^(route|rid|r)\d+', name, flags=re.IGNORECASE):
        return None

    # Skip empty names
    if not name or len(name) < 2:
        return None

    # Normalize to lowercase
    name = name.lower().strip()

    # Normalize separators: replace spaces and hyphens with underscores
    name = name.replace(' ', '_').replace('-', '_')

    # Remove trailing underscores
    name = name.rstrip('_')

    # Remove any leftover numeric suffixes like _005 at the end (after RID was stripped)
    name = re.sub(r'_\d+$', '', name)

    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)

    # Apply known aliases
    name = NAME_ALIASES.get(name, name)

    # Skip excluded students (not enrolled)
    if name in EXCLUDED_STUDENTS:
        return None

    return name if name else None


def scan_submissions(assignments_dir: str = "assignments") -> dict:
    """
    Scan all assignment folders and count submissions per student.

    Returns:
        dict: {student_name: set of RIDs submitted}
    """
    student_routes = defaultdict(set)

    assignments_path = Path(assignments_dir)

    # Routes that use .txt deliverables instead of .ipynb notebooks
    TXT_DELIVERABLE_ROUTES = {"RID_006", "RID_007", "RID_008", "RID_013"}

    # Include both RID_* and MID_* folders
    all_route_folders = sorted(list(assignments_path.glob("RID_*")) + list(assignments_path.glob("MID_*")))
    for rid_folder in all_route_folders:
        rid = rid_folder.name  # e.g., "RID_001" or "MID_001"
        submissions_dir = rid_folder / "submissions"

        if not submissions_dir.exists():
            continue

        if rid in TXT_DELIVERABLE_ROUTES:
            # For text routes, look for deliverable/text_submission .txt or .docx files
            for ext in ['*.txt', '*.docx']:
                for txt_file in submissions_dir.glob(ext):
                    name_lower = txt_file.name.lower()
                    if 'deliverable' in name_lower or 'text_submission' in name_lower or 'submission_file' in name_lower or 'text' in name_lower:
                        clean_name = txt_file.name
                        for tag in ['_deliverable', '_text_submission', '_submission_file', '_text']:
                            clean_name = re.sub(re.escape(tag), '', clean_name, flags=re.IGNORECASE)
                        student = extract_student_name(clean_name)
                        if student:
                            student_routes[student].add(rid)
            # For FREE_PASS text routes, be lenient - accept ANY submission file
            # (students may not follow naming conventions or submit wrong format)
            if rid in FREE_PASS_ROUTES:
                for ext in ['*.ipynb', '*.txt', '*.docx']:
                    for f in submissions_dir.glob(ext):
                        # Skip logbook files
                        if 'logbook' in f.name.lower():
                            continue
                        student = extract_student_name(f.name)
                        if student:
                            student_routes[student].add(rid)
        else:
            # For code routes, look for .ipynb notebooks
            for notebook in submissions_dir.glob("*.ipynb"):
                student = extract_student_name(notebook.name)
                if student:
                    student_routes[student].add(rid)

    return dict(student_routes)


def is_soft_send(exercises: list, threshold: float = 0.8, route_id: str = None) -> bool:
    """
    Check if a route submission qualifies as a "soft send".

    A soft send means >= threshold (default 80%) of exercises are rated EXCELLENT or OK.
    Routes in FREE_PASS_ROUTES always return True (free pass for confusing instructions).

    Args:
        exercises: List of exercise dicts with 'rating' keys
        threshold: Minimum fraction of OK+ ratings (default 0.8)
        route_id: Optional route ID to check for free pass

    Returns:
        True if the route is a soft send, False otherwise
    """
    # Free pass routes always count as sent
    if route_id and route_id in FREE_PASS_ROUTES:
        return True

    if not exercises:
        return False

    good_ratings = sum(1 for ex in exercises if ex.get('rating') in ('EXCELLENT', 'OK'))
    return (good_ratings / len(exercises)) >= threshold


def count_soft_sends(student_grades: dict, student_routes: dict = None) -> dict:
    """
    Count the number of "soft sends" per student.

    Args:
        student_grades: Dict of {student_name: {rid: grade_info}}
        student_routes: Optional dict of {student_name: set of RIDs submitted}
                        Used to count FREE_PASS routes that have submissions but no grade JSONs.

    Returns:
        Dict of {student_name: number_of_soft_sends}
    """
    soft_sends = {}

    # Get all students from both sources
    all_students = set(student_grades.keys())
    if student_routes:
        all_students.update(student_routes.keys())

    for student in all_students:
        count = 0
        counted_rids = set()

        # Count from grading results
        if student in student_grades:
            for rid, grade_info in student_grades[student].items():
                counted_rids.add(rid)
                exercises = grade_info.get('exercises', [])
                if is_soft_send(exercises, route_id=rid):
                    count += 1

        # Count FREE_PASS routes from submissions that aren't in grading results
        if student_routes and student in student_routes:
            for rid in student_routes[student]:
                if rid not in counted_rids and rid in FREE_PASS_ROUTES:
                    count += 1

        soft_sends[student] = count
    return soft_sends


def scan_grading_results(assignments_dir: str = "assignments") -> dict:
    """
    Scan all grading result JSON files.

    Returns:
        dict: {student_name: {rid: grading_data}}
        where grading_data contains exercises with ratings, rationales, etc.
    """
    import json

    student_grades = defaultdict(dict)
    assignments_path = Path(assignments_dir)

    # Include both RID_* and MID_* folders
    all_route_folders = sorted(list(assignments_path.glob("RID_*")) + list(assignments_path.glob("MID_*")))
    for rid_folder in all_route_folders:
        rid = rid_folder.name  # e.g., "RID_001" or "MID_001"
        results_dir = rid_folder / "results"

        if not results_dir.exists():
            continue

        for json_file in results_dir.glob("*_grade.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Extract student name from filename
                student = extract_student_name(json_file.stem.replace('_grade', ''))
                if not student:
                    continue

                # Build grade summary
                exercises = data.get('exercises', [])
                grade_info = {
                    'route_id': rid,
                    'exercises': [],
                    'overall_summary': data.get('overall_summary', ''),
                }

                for ex in exercises:
                    grade_info['exercises'].append({
                        'exercise_id': ex.get('exercise_id', ''),
                        'rating': ex.get('rating', 'UNKNOWN'),
                        'rationale': ex.get('rationale', ''),
                        'flags': ex.get('flags', []),
                    })

                student_grades[student][rid] = grade_info

            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read {json_file}: {e}")
                continue

    return dict(student_grades)


def get_latest_submission_time(assignments_dir: str = "assignments") -> str:
    """Get the timestamp of the most recently modified submission file."""
    from datetime import datetime

    assignments_path = Path(assignments_dir)
    latest_time = None

    # Include both RID_* and MID_* folders
    for pattern in ["RID_*/submissions/*.ipynb", "MID_*/submissions/*.ipynb"]:
        for notebook in assignments_path.glob(pattern):
            mtime = notebook.stat().st_mtime
            if latest_time is None or mtime > latest_time:
                latest_time = mtime

    if latest_time:
        dt = datetime.fromtimestamp(latest_time)
        return dt.strftime("%Y-%m-%d %H:%M")
    return "Unknown"


def get_completion_stats(student_routes: dict, assignments_dir: str = "assignments") -> dict:
    """Calculate completion statistics."""
    # Dynamically count routes that have submissions or instructions
    assignments_path = Path(assignments_dir)
    # Include both RID_* and MID_* folders
    route_folders = sorted(list(assignments_path.glob("RID_*")) + list(assignments_path.glob("MID_*")))
    total_routes = len(route_folders)

    # Get list of all route IDs
    all_route_ids = [f.name for f in route_folders]

    completions = [len(routes) for routes in student_routes.values()]

    return {
        "total_students": len(student_routes),
        "total_routes": total_routes,
        "all_routes": all_route_ids,
        "completions": completions,
        "avg_completed": sum(completions) / len(completions) if completions else 0,
        "max_completed": max(completions) if completions else 0,
        "min_completed": min(completions) if completions else 0,
        "last_updated": get_latest_submission_time(assignments_dir),
    }


def plot_dashboard(student_routes: dict, output_path: str = None):
    """Create dashboard visualizations."""
    stats = get_completion_stats(student_routes)
    completions = stats["completions"]
    total_routes = stats["total_routes"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # --- Histogram: Distribution of routes completed ---
    ax1 = axes[0]
    bins = range(0, total_routes + 2)
    ax1.hist(completions, bins=bins, edgecolor='black', alpha=0.7, align='left')
    ax1.set_xlabel("Routes Completed")
    ax1.set_ylabel("Number of Students")
    ax1.set_title(f"Distribution of Routes Completed\n(Gym Size: {total_routes} routes)")
    ax1.set_xticks(range(0, total_routes + 1))

    # Add stats text
    stats_text = f"n={stats['total_students']}\nμ={stats['avg_completed']:.1f}\nmax={stats['max_completed']}"
    ax1.text(0.95, 0.95, stats_text, transform=ax1.transAxes,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # --- Scatter: Each student as a point ---
    ax2 = axes[1]
    # X = gym size (constant for now), Y = routes completed per student
    # Add jitter to X for visibility
    import numpy as np
    np.random.seed(42)
    x_jitter = np.random.normal(total_routes, 0.15, len(completions))

    ax2.scatter(x_jitter, completions, alpha=0.5, s=50)
    ax2.set_xlabel("Gym Size (Routes Available)")
    ax2.set_ylabel("Routes Completed")
    ax2.set_title(f"Student Progress\n({stats['total_students']} students)")
    ax2.set_xlim(0, total_routes + 1)
    ax2.set_ylim(-0.5, total_routes + 0.5)
    ax2.axhline(y=stats['avg_completed'], color='red', linestyle='--', label=f"Mean: {stats['avg_completed']:.1f}")
    ax2.legend()

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150)
        print(f"Dashboard saved to: {output_path}")

    plt.show()
    return fig


def print_summary(student_routes: dict):
    """Print text summary of submissions."""
    stats = get_completion_stats(student_routes)

    print("=" * 60)
    print("SUBMISSION STATISTICS")
    print("=" * 60)
    print(f"Gym Size: {stats['total_routes']} routes")
    print(f"Total Students: {stats['total_students']}")
    print(f"Average Completed: {stats['avg_completed']:.1f}")
    print(f"Range: {stats['min_completed']} - {stats['max_completed']}")
    print(f"Last Updated: {stats['last_updated']}")
    print()

    # Distribution table
    from collections import Counter
    dist = Counter(stats['completions'])
    print("Distribution:")
    for n in range(stats['total_routes'] + 1):
        count = dist.get(n, 0)
        bar = "█" * count
        print(f"  {n} routes: {count:3d} students {bar}")


def get_route_stats(student_routes: dict, student_grades: dict, all_routes: list) -> dict:
    """
    Calculate per-route submission and send statistics.

    Returns:
        dict: {route_id: {'submitted': int, 'sent': int, 'not_sent': int, 'send_rate': float}}
    """
    route_stats = {rid: {'submitted': 0, 'sent': 0, 'not_sent': 0} for rid in all_routes}

    # Track which (student, route) pairs we've counted from grades
    counted = set()

    # Count from grading results (ensures submitted = sent + not_sent)
    for student, grades in student_grades.items():
        for rid, grade_info in grades.items():
            if rid not in route_stats:
                continue
            counted.add((student, rid))
            route_stats[rid]['submitted'] += 1
            exercises = grade_info.get('exercises', [])
            if is_soft_send(exercises, route_id=rid):
                route_stats[rid]['sent'] += 1
            else:
                route_stats[rid]['not_sent'] += 1

    # For FREE_PASS routes, also count students who submitted but weren't graded
    for student, routes in student_routes.items():
        for rid in routes:
            if rid in FREE_PASS_ROUTES and (student, rid) not in counted and rid in route_stats:
                route_stats[rid]['submitted'] += 1
                route_stats[rid]['sent'] += 1  # FREE_PASS = auto-sent

    # Calculate send rate
    for rid, stats in route_stats.items():
        if stats['submitted'] > 0:
            stats['send_rate'] = stats['sent'] / stats['submitted'] * 100
        else:
            stats['send_rate'] = 0.0

    return route_stats


def plot_interactive_dashboard(student_routes: dict, output_path: str = "dashboard.html", assignments_dir: str = "assignments"):
    """Create interactive HTML dashboard with plotly."""
    if not HAS_PLOTLY:
        raise ImportError("plotly is required for interactive dashboard. Install with: pip install plotly")

    import numpy as np
    import json
    from collections import Counter

    stats = get_completion_stats(student_routes, assignments_dir)
    total_routes = stats["total_routes"]
    all_routes = stats.get("all_routes", [f"RID_{str(i).zfill(3)}" for i in range(1, total_routes + 1)])

    # Get grading results
    student_grades = scan_grading_results(assignments_dir)

    # Merge student_grades routes into student_routes so "submitted" reflects both sources
    # (A student who was graded for a route clearly submitted it, even if scan_submissions missed it)
    for student, grades in student_grades.items():
        if student not in student_routes:
            student_routes[student] = set()
        for rid in grades:
            student_routes[student].add(rid)

    # Calculate soft sends per student (pass student_routes for FREE_PASS fallback)
    soft_sends = count_soft_sends(student_grades, student_routes)

    # Calculate per-route statistics
    route_stats = get_route_stats(student_routes, student_grades, all_routes)

    # Prepare data with student names
    students = list(student_routes.keys())
    completions = [len(routes) for routes in student_routes.values()]
    sends = [soft_sends.get(s, 0) for s in students]

    # Calculate stats (median and percentiles)
    median_submitted = float(np.median(completions)) if completions else 0
    median_sent = float(np.median(sends)) if sends else 0
    p25_submitted = float(np.percentile(completions, 25)) if completions else 0
    p75_submitted = float(np.percentile(completions, 75)) if completions else 0
    p25_sent = float(np.percentile(sends, 25)) if sends else 0
    p75_sent = float(np.percentile(sends, 75)) if sends else 0

    # Create 2x2 figure with subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f"Submitted Distribution (median={median_submitted:.0f})",
            f"Sent Distribution (median={median_sent:.0f})",
            f"Submitted by Student Rank",
            f"Sent by Student Rank"
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.08
    )

    # --- Histograms ---
    dist_submitted = Counter(completions)
    dist_sent = Counter(sends)
    x_hist = list(range(total_routes + 1))
    y_submitted = [dist_submitted.get(n, 0) for n in x_hist]
    y_sent = [dist_sent.get(n, 0) for n in x_hist]

    # Top-left: Submitted histogram (blue)
    fig.add_trace(
        go.Bar(
            x=x_hist,
            y=y_submitted,
            marker_color='steelblue',
            opacity=0.8,
            name='Submitted',
            showlegend=False,
            hovertemplate='%{y} students submitted %{x} routes<extra></extra>'
        ),
        row=1, col=1
    )

    # Top-right: Sent histogram (green)
    fig.add_trace(
        go.Bar(
            x=x_hist,
            y=y_sent,
            marker_color='seagreen',
            opacity=0.8,
            name='Sent',
            showlegend=False,
            hovertemplate='%{y} students sent %{x} routes<extra></extra>'
        ),
        row=1, col=2
    )

    # --- Scatter plots ---
    np.random.seed(42)

    # Sort students by completion count (descending), then by name for ties
    sorted_by_submitted = sorted(
        zip(students, completions, sends),
        key=lambda x: (-x[1], x[0])
    )
    sorted_by_sent = sorted(
        zip(students, completions, sends),
        key=lambda x: (-x[2], x[0])
    )

    # Ranks
    ranks = list(range(1, len(students) + 1))

    # Format student names nicely for hover
    display_names_sub = [name.replace('_', ' ').title() for name, _, _ in sorted_by_submitted]
    completions_sorted = [c for _, c, _ in sorted_by_submitted]

    display_names_sent = [name.replace('_', ' ').title() for name, _, _ in sorted_by_sent]
    sends_sorted = [s for _, _, s in sorted_by_sent]

    # Add jitter
    y_jitter_sub = np.array(completions_sorted) + np.random.uniform(-0.25, 0.25, len(completions_sorted))
    y_jitter_sent = np.array(sends_sorted) + np.random.uniform(-0.25, 0.25, len(sends_sorted))

    # Bottom-left: Submitted scatter (blue)
    fig.add_trace(
        go.Scatter(
            x=ranks,
            y=y_jitter_sub,
            mode='markers',
            marker=dict(size=7, color='steelblue', opacity=0.7),
            name='Submitted',
            showlegend=False,
            customdata=[[s, c, r] for s, c, r in zip(display_names_sub, completions_sorted, ranks)],
            hovertemplate='Rank: %{customdata[2]}<br>Submitted: %{customdata[1]}<extra></extra>'
        ),
        row=2, col=1
    )

    # Bottom-right: Sent scatter (green)
    fig.add_trace(
        go.Scatter(
            x=ranks,
            y=y_jitter_sent,
            mode='markers',
            marker=dict(size=7, color='seagreen', opacity=0.7),
            name='Sent',
            showlegend=False,
            customdata=[[s, c, r] for s, c, r in zip(display_names_sent, sends_sorted, ranks)],
            hovertemplate='Rank: %{customdata[2]}<br>Sent: %{customdata[1]}<extra></extra>'
        ),
        row=2, col=2
    )

    # Add percentile lines to scatter plots
    # 25th percentile (dotted, lighter)
    fig.add_hline(y=p25_submitted, line_dash="dot", line_color="orange",
                  annotation_text=f"25th={p25_submitted:.0f}",
                  annotation_position="bottom right", row=2, col=1)
    fig.add_hline(y=p25_sent, line_dash="dot", line_color="orange",
                  annotation_text=f"25th={p25_sent:.0f}",
                  annotation_position="bottom right", row=2, col=2)

    # Median (dashed, red)
    fig.add_hline(y=median_submitted, line_dash="dash", line_color="red",
                  annotation_text=f"50th={median_submitted:.0f}",
                  annotation_position="top right", row=2, col=1)
    fig.add_hline(y=median_sent, line_dash="dash", line_color="red",
                  annotation_text=f"50th={median_sent:.0f}",
                  annotation_position="top right", row=2, col=2)

    # 75th percentile (dotted, lighter)
    fig.add_hline(y=p75_submitted, line_dash="dot", line_color="orange",
                  annotation_text=f"75th={p75_submitted:.0f}",
                  annotation_position="top right", row=2, col=1)
    fig.add_hline(y=p75_sent, line_dash="dot", line_color="orange",
                  annotation_text=f"75th={p75_sent:.0f}",
                  annotation_position="top right", row=2, col=2)

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"<b>Route Completion Dashboard</b><br>n={stats['total_students']} students | \"Sent\" = 80%+ exercises OK or better | Updated: {stats['last_updated']}",
            x=0.5,
            y=0.98,
            font=dict(size=20)
        ),
        showlegend=False,
        height=750,
        width=1000,
        margin=dict(t=100),
        template='plotly_white'
    )

    # Update subplot title positions to avoid overlap
    for annotation in fig['layout']['annotations']:
        if 'Distribution' in annotation['text'] or 'Student Rank' in annotation['text']:
            annotation['y'] = annotation['y'] - 0.02

    # Update axes for 2x2 grid
    # Row 1: Histograms
    fig.update_xaxes(title_text="Routes", row=1, col=1)
    fig.update_xaxes(title_text="Routes", row=1, col=2)
    fig.update_yaxes(title_text="# Students", row=1, col=1)
    fig.update_yaxes(title_text="# Students", row=1, col=2)

    # Row 2: Scatter plots
    fig.update_xaxes(title_text="Student Rank", row=2, col=1)
    fig.update_xaxes(title_text="Student Rank", row=2, col=2)
    fig.update_yaxes(title_text="Routes", range=[-0.5, total_routes + 0.5], row=2, col=1)
    fig.update_yaxes(title_text="Routes", range=[-0.5, total_routes + 0.5], row=2, col=2)

    # Generate the plotly chart HTML
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    # --- Route Analysis Chart (Heatmap Tiles) ---
    # Create a heatmap grid showing send rate per route
    import math

    # Sort so RID routes come first (by number), then MID routes at the end
    rid_routes = sorted([r for r in route_stats.keys() if r.startswith('RID_')])
    mid_routes = sorted([r for r in route_stats.keys() if r.startswith('MID_')])
    route_ids = rid_routes + mid_routes
    n_routes = len(route_ids)

    # Dynamic grid sizing - aim for roughly square, max 10 columns
    n_cols = min(10, max(5, int(math.ceil(math.sqrt(n_routes)))))
    n_rows = math.ceil(n_routes / n_cols)

    # Build grid data (bottom to top so RID_001 is top-left)
    z = []  # send rates
    text = []  # display text
    hover_text = []  # hover info

    for row in range(n_rows - 1, -1, -1):  # reverse so row 0 is at top visually
        row_z = []
        row_text = []
        row_hover = []
        for col in range(n_cols):
            idx = row * n_cols + col
            if idx < n_routes:
                rid = route_ids[idx]
                rate = route_stats[rid]['send_rate']
                sent = route_stats[rid]['sent']
                submitted = route_stats[rid]['submitted']
                not_sent = route_stats[rid]['not_sent']
                row_z.append(rate)
                # Format label: RID_001 -> R001, MID_001 -> M1
                if rid.startswith('MID_'):
                    label = 'M' + str(int(rid.replace('MID_', '')))
                else:
                    label = 'R' + rid.replace('RID_', '')
                row_text.append(f'{label}<br>{rate:.0f}%<br>n={submitted}')
                row_hover.append(f'<b>{rid}</b><br>Send Rate: {rate:.0f}%<br>Sent: {sent}/{submitted}<br>Not Sent: {not_sent}')
            else:
                row_z.append(None)
                row_text.append('')
                row_hover.append('')
        z.append(row_z)
        text.append(row_text)
        hover_text.append(row_hover)

    route_fig = go.Figure(data=go.Heatmap(
        z=z,
        text=text,
        texttemplate='%{text}',
        textfont=dict(size=14, color='white'),
        hovertext=hover_text,
        hovertemplate='%{hovertext}<extra></extra>',
        colorscale=[
            [0, '#dc3545'],      # red at 0%
            [0.5, '#ffc107'],    # yellow at 50%
            [0.8, '#28a745'],    # green at 80%
            [1, '#155724']       # dark green at 100%
        ],
        zmin=0,
        zmax=100,
        showscale=True,
        colorbar=dict(
            title='Send Rate %',
            ticksuffix='%',
            x=1.02
        ),
        xgap=3,
        ygap=3
    ))

    route_fig.update_layout(
        title=dict(
            text='<b>Route Health: Send Rates</b><br>Red/yellow = hard content, unclear instructions, or grading issues. Click a route to see details.',
            x=0.5,
            font=dict(size=18)
        ),
        height=max(300, n_rows * 80 + 100),
        width=1000,
        template='plotly_white',
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False)
    )

    route_chart_html = route_fig.to_html(full_html=False, include_plotlyjs=False, div_id='routeHeatmap')

    # --- Generate Route Analysis Data ---
    # Import route analysis module for detailed feedback
    from graderbot.route_analysis import collect_route_feedback, get_common_issues

    route_analysis_data = {}
    for rid in route_ids:
        feedback = collect_route_feedback(rid, assignments_dir)

        # Skip routes with no results or errors
        if 'error' in feedback or feedback.get('total_submissions', 0) == 0:
            route_analysis_data[rid] = {
                'total_submissions': 0,
                'send_rate': 0,
                'sent': 0,
                'not_sent': 0,
                'exercise_success': {},
                'issues': {},
                'free_pass': rid in FREE_PASS_ROUTES
            }
            continue

        issues = get_common_issues(feedback, min_occurrences=2)

        # Calculate exercise success rates
        exercise_success = {}
        for ex_id, stats_data in feedback.get('stats', {}).items():
            total_ex = stats_data['excellent'] + stats_data['ok'] + stats_data['needs_work']
            if total_ex > 0:
                ok_plus = stats_data['excellent'] + stats_data['ok']
                exercise_success[ex_id] = {
                    'rate': round(ok_plus / total_ex * 100),
                    'excellent': stats_data['excellent'],
                    'ok': stats_data['ok'],
                    'needs_work': stats_data['needs_work']
                }

        # Format issues for display
        formatted_issues = {}
        for ex_id, issue_data in issues.items():
            formatted_issues[ex_id] = {
                'count': issue_data['count'],
                'percentage': round(issue_data['percentage']),
                'samples': issue_data['sample_rationales'][:3]  # Top 3 examples
            }

        # Use route_stats for all counts (ensures consistency)
        route_analysis_data[rid] = {
            'total_submissions': route_stats[rid]['submitted'],
            'send_rate': route_stats[rid]['send_rate'],
            'sent': route_stats[rid]['sent'],
            'not_sent': route_stats[rid]['not_sent'],
            'exercise_success': exercise_success,
            'issues': formatted_issues,
            'free_pass': rid in FREE_PASS_ROUTES
        }

    route_analysis_json = json.dumps(route_analysis_data)

    # Prepare student data for JavaScript
    student_data = {}
    for student, routes in student_routes.items():
        display_name = student.replace('_', ' ').title()

        # Start with routes from submissions
        completed_set = set(routes)

        # Include grading data and calculate send status for each route
        grades = {}
        sent_routes = []  # Routes that qualify as "sent" (80%+ OK)
        not_sent_routes = []  # Submitted but not sent

        if student in student_grades:
            for rid, grade_info in student_grades[student].items():
                # If we have grades, they completed it (even if wrong file format)
                completed_set.add(rid)

                exercises = grade_info.get("exercises", [])
                grades[rid] = {
                    "exercises": exercises,
                    "overall_summary": grade_info.get("overall_summary", ""),
                }
                # Check if this route is a "send"
                if is_soft_send(exercises, route_id=rid):
                    sent_routes.append(rid)
                else:
                    not_sent_routes.append(rid)

        completed = sorted(list(completed_set))
        missing = [r for r in all_routes if r not in completed_set]

        # Routes completed but not graded yet
        for rid in completed:
            if rid not in sent_routes and rid not in not_sent_routes:
                # FREE_PASS routes count as sent even without grades
                if rid in FREE_PASS_ROUTES:
                    sent_routes.append(rid)
                else:
                    not_sent_routes.append(rid)

        student_data[student] = {
            "display_name": display_name,
            "completed": completed,
            "missing": missing,
            "sent": sorted(sent_routes),
            "not_sent": sorted(not_sent_routes),
            "count": len(completed_set),
            "sent_count": len(sent_routes),
            "total": total_routes,
            "grades": grades,
        }

    student_json = json.dumps(student_data)
    sorted_students_json = json.dumps(sorted(students))

    # Generate route selector options
    route_options = '\n'.join([
        f'<option value="{rid}">{rid} ({route_stats[rid]["send_rate"]:.0f}% sent)</option>'
        for rid in route_ids
    ])

    # Create full HTML with search functionality
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>Route Completion Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .search-panel {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .search-panel h3 {{
            margin-top: 0;
            color: #333;
        }}
        .search-row {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        #studentSearch {{
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 300px;
        }}
        #studentSelect {{
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 300px;
        }}
        .search-results {{
            margin-top: 10px;
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            display: none;
        }}
        .search-results.active {{
            display: block;
        }}
        .search-result-item {{
            padding: 10px 15px;
            cursor: pointer;
            border-bottom: 1px solid #eee;
            transition: background 0.15s;
        }}
        .search-result-item:last-child {{
            border-bottom: none;
        }}
        .search-result-item:hover {{
            background: #e8f4fc;
        }}
        .search-result-item .name {{
            font-weight: 500;
        }}
        .search-result-item .meta {{
            font-size: 0.85em;
            color: #666;
        }}
        .no-results {{
            padding: 15px;
            color: #888;
            text-align: center;
            font-style: italic;
        }}
        .clear-btn {{
            padding: 10px 15px;
            font-size: 14px;
            background: #e74c3c;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .clear-btn:hover {{
            background: #c0392b;
        }}
        .student-info {{
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
            display: none;
        }}
        .student-info.active {{
            display: block;
        }}
        .student-name {{
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .stats-row {{
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
        }}
        .stat-box {{
            background: white;
            padding: 15px 25px;
            border-radius: 4px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .routes-section {{
            display: flex;
            gap: 20px;
        }}
        .routes-list {{
            flex: 1;
        }}
        .routes-list h4 {{
            margin: 0 0 10px 0;
            color: #555;
        }}
        .route-tag {{
            display: inline-block;
            padding: 5px 10px;
            margin: 3px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .route-sent {{
            background: #d4edda;
            color: #155724;
        }}
        .route-not-sent {{
            background: #fff3cd;
            color: #856404;
        }}
        .route-missing {{
            background: #f8d7da;
            color: #721c24;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        /* Route Analysis Panel */
        .route-analysis-panel {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            margin-top: 20px;
            border: 2px solid #3498db;
        }}
        .route-analysis-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }}
        .route-analysis-header h3 {{
            margin: 0;
            color: #2c3e50;
        }}
        .close-btn {{
            background: #e74c3c;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 5px 12px;
            cursor: pointer;
            font-size: 14px;
        }}
        .close-btn:hover {{
            background: #c0392b;
        }}
        .route-stats-row {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }}
        .route-stat-box {{
            background: #f8f9fa;
            padding: 12px 20px;
            border-radius: 6px;
            text-align: center;
            flex: 1;
        }}
        .route-stat-number {{
            font-size: 1.8em;
            font-weight: bold;
            color: #3498db;
        }}
        .route-stat-label {{
            color: #666;
            font-size: 0.85em;
        }}
        .exercise-bar {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}
        .exercise-bar-label {{
            width: 100px;
            font-weight: 500;
            flex-shrink: 0;
        }}
        .exercise-bar-track {{
            flex: 1;
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin: 0 10px;
        }}
        .exercise-bar-fill {{
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s ease;
        }}
        .exercise-bar-value {{
            width: 50px;
            text-align: right;
            font-weight: 500;
        }}
        .issue-card {{
            background: #fff8e1;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin-bottom: 12px;
            border-radius: 0 6px 6px 0;
        }}
        .issue-card.severe {{
            background: #ffebee;
            border-left-color: #dc3545;
        }}
        .issue-header {{
            font-weight: bold;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }}
        .issue-samples {{
            font-size: 0.9em;
            color: #555;
        }}
        .issue-samples li {{
            margin-bottom: 6px;
        }}
        /* Grading feedback styles */
        .grades-section {{
            margin-top: 20px;
            border-top: 1px solid #ddd;
            padding-top: 15px;
        }}
        .grades-section h4 {{
            margin: 0 0 15px 0;
            color: #333;
        }}
        .route-grade-card {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 15px;
            overflow: hidden;
        }}
        .route-grade-header {{
            background: #f8f9fa;
            padding: 10px 15px;
            font-weight: bold;
            border-bottom: 1px solid #e0e0e0;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .route-grade-header:hover {{
            background: #e9ecef;
        }}
        .route-grade-body {{
            padding: 15px;
            display: none;
        }}
        .route-grade-body.expanded {{
            display: block;
        }}
        .exercise-row {{
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .exercise-row:last-child {{
            border-bottom: none;
        }}
        .exercise-id {{
            font-weight: 500;
            width: 100px;
            flex-shrink: 0;
        }}
        .exercise-rating {{
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
            margin-right: 15px;
            flex-shrink: 0;
        }}
        .rating-excellent {{
            background: #d4edda;
            color: #155724;
        }}
        .rating-ok {{
            background: #fff3cd;
            color: #856404;
        }}
        .rating-needs_work {{
            background: #f8d7da;
            color: #721c24;
        }}
        .exercise-rationale {{
            color: #666;
            font-size: 0.9em;
            flex-grow: 1;
        }}
        .overall-summary {{
            margin-top: 15px;
            padding: 12px;
            background: #e8f4f8;
            border-radius: 6px;
            font-style: italic;
            color: #333;
        }}
        .grade-summary-badge {{
            font-size: 0.85em;
            padding: 2px 8px;
            border-radius: 10px;
            background: #e0e0e0;
        }}
        .no-grades {{
            color: #888;
            font-style: italic;
            padding: 10px 0;
        }}
        .expand-icon {{
            transition: transform 0.2s;
        }}
        .expand-icon.rotated {{
            transform: rotate(180deg);
        }}
    </style>
</head>
<body>
    <!-- Password Gate -->
    <div id="loginOverlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #f5f5f5; z-index: 9999; display: flex; align-items: center; justify-content: center;">
        <div style="background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); text-align: center; max-width: 400px;">
            <h2 style="margin-top: 0; color: #333;">🧗 Chem169 Dashboard</h2>
            <p style="color: #666;">Enter the course password to view the dashboard.</p>
            <input type="password" id="passwordInput" placeholder="Password"
                   style="width: 100%; padding: 12px; font-size: 16px; border: 2px solid #ddd; border-radius: 6px; margin: 10px 0; box-sizing: border-box;"
                   onkeypress="if(event.key==='Enter') checkPassword()">
            <button onclick="checkPassword()"
                    style="width: 100%; padding: 12px; font-size: 16px; background: #007bff; color: white; border: none; border-radius: 6px; cursor: pointer; margin-top: 10px;">
                Enter
            </button>
            <p id="loginError" style="color: #dc3545; margin-top: 10px; display: none;">Incorrect password. Try again.</p>
        </div>
    </div>
    <script>
        const DASHBOARD_PASSWORD = 'Chem169269!!!';
        function checkPassword() {{
            const input = document.getElementById('passwordInput').value;
            if (input === DASHBOARD_PASSWORD) {{
                sessionStorage.setItem('chem169_authenticated', 'true');
                document.getElementById('loginOverlay').style.display = 'none';
            }} else {{
                document.getElementById('loginError').style.display = 'block';
                document.getElementById('passwordInput').value = '';
            }}
        }}
        // Check if already authenticated
        if (sessionStorage.getItem('chem169_authenticated') === 'true') {{
            document.getElementById('loginOverlay').style.display = 'none';
        }}
    </script>

    <div class="container">
        <div class="search-panel">
            <h3>🔍 Student Lookup</h3>
            <div class="search-row">
                <input type="text" id="studentSearch" placeholder="Type to search student..." oninput="filterStudents()">
                <button id="clearBtn" class="clear-btn" onclick="clearSearch()" style="display: none;">✕ Clear</button>
                <select id="studentSelect" onchange="showStudentInfo()" style="display: none;">
                    <option value="">-- Select a student --</option>
                </select>
            </div>
            <div id="searchResults" class="search-results"></div>
            <div id="studentInfo" class="student-info">
                <div class="student-name" id="displayName"></div>
                <div class="stats-row">
                    <div class="stat-box">
                        <div class="stat-number" id="completedCount">0</div>
                        <div class="stat-label">Submitted</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" id="sentCount" style="color: #28a745;">0</div>
                        <div class="stat-label">Sent</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" id="missingCount">0</div>
                        <div class="stat-label">Missing</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" id="percentComplete">0%</div>
                        <div class="stat-label">Progress</div>
                    </div>
                </div>
                <div class="routes-section">
                    <div class="routes-list">
                        <h4>✅ Sent (80%+ OK)</h4>
                        <div id="sentRoutes"></div>
                    </div>
                    <div class="routes-list">
                        <h4>⚠️ Submitted (needs work)</h4>
                        <div id="notSentRoutes"></div>
                    </div>
                    <div class="routes-list">
                        <h4>❌ Missing</h4>
                        <div id="missingRoutes"></div>
                    </div>
                </div>
                <div class="grades-section">
                    <h4>📝 Grading Feedback</h4>
                    <div id="gradesContainer"></div>
                </div>
            </div>
        </div>
        <div class="chart-container">
            {chart_html}
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {route_chart_html}
            <div style="margin-top: 15px; text-align: center;">
                <span style="color: #666; margin-right: 10px;">Or select a route:</span>
                <select id="routeSelector" onchange="if(this.value) showRouteAnalysis(this.value);" style="padding: 8px; font-size: 14px; border-radius: 4px; border: 1px solid #ddd;">
                    <option value="">-- Select Route --</option>
                    {route_options}
                </select>
            </div>
        </div>
        <div id="routeAnalysisPanel" class="route-analysis-panel" style="display: none;">
            <div class="route-analysis-header">
                <h3 id="routeAnalysisTitle">Route Analysis</h3>
                <button onclick="closeRouteAnalysis()" class="close-btn">✕</button>
            </div>
            <div class="route-analysis-body">
                <div class="route-stats-row">
                    <div class="route-stat-box">
                        <div class="route-stat-number" id="raSubmissions">0</div>
                        <div class="route-stat-label">Submissions</div>
                    </div>
                    <div class="route-stat-box">
                        <div class="route-stat-number" id="raSent" style="color: #28a745;">0</div>
                        <div class="route-stat-label">Sent</div>
                    </div>
                    <div class="route-stat-box">
                        <div class="route-stat-number" id="raNotSent" style="color: #dc3545;">0</div>
                        <div class="route-stat-label">Not Sent</div>
                    </div>
                    <div class="route-stat-box">
                        <div class="route-stat-number" id="raSendRate">0%</div>
                        <div class="route-stat-label">Send Rate</div>
                    </div>
                </div>
                <div id="freePassBanner" style="display: none; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 12px 16px; margin: 16px 0; color: #856404;">
                    <strong>⚠️ Free Pass Route:</strong> This route had confusing instructions, so all submissions count as "sent" regardless of actual grades. The exercise success rates below reflect actual performance, but students are not penalized.
                </div>
                <h4>Exercise Success Rates</h4>
                <div id="exerciseSuccessRates"></div>
                <h4>Common Issues</h4>
                <div id="commonIssues"></div>
            </div>
        </div>
    </div>

    <script>
        const studentData = {student_json};
        const allStudents = {sorted_students_json};
        const routeAnalysisData = {route_analysis_json};

        // Populate dropdown on load
        function populateDropdown(students) {{
            const select = document.getElementById('studentSelect');
            select.innerHTML = '<option value="">-- Select a student --</option>';
            students.forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = studentData[s].display_name;
                select.appendChild(opt);
            }});
        }}

        // Filter students based on search input
        function filterStudents() {{
            const query = document.getElementById('studentSearch').value.toLowerCase().trim();
            const resultsDiv = document.getElementById('searchResults');

            if (!query) {{
                resultsDiv.classList.remove('active');
                resultsDiv.innerHTML = '';
                return;
            }}

            const filtered = allStudents.filter(s =>
                s.toLowerCase().includes(query) ||
                studentData[s].display_name.toLowerCase().includes(query)
            );

            if (filtered.length === 0) {{
                resultsDiv.innerHTML = '<div class="no-results">No students found</div>';
                resultsDiv.classList.add('active');
                return;
            }}

            // Show up to 10 results
            const toShow = filtered.slice(0, 10);
            let html = '';
            for (const s of toShow) {{
                const data = studentData[s];
                html += `
                    <div class="search-result-item" onclick="selectStudent('${{s}}')">
                        <div class="name">${{data.display_name}}</div>
                        <div class="meta">${{data.count}}/${{data.total}} routes completed</div>
                    </div>
                `;
            }}
            if (filtered.length > 10) {{
                html += `<div class="no-results">${{filtered.length - 10}} more results...</div>`;
            }}
            resultsDiv.innerHTML = html;
            resultsDiv.classList.add('active');

            // Auto-select if exactly one match
            if (filtered.length === 1) {{
                selectStudent(filtered[0]);
            }}
        }}

        // Select a student from search results
        function selectStudent(studentKey) {{
            document.getElementById('studentSelect').value = studentKey;
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('studentSearch').value = studentData[studentKey].display_name;
            document.getElementById('clearBtn').style.display = 'inline-block';
            showStudentInfo();
        }}

        // Clear search and return to landing view
        function clearSearch() {{
            document.getElementById('studentSearch').value = '';
            document.getElementById('studentSelect').value = '';
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('searchResults').innerHTML = '';
            document.getElementById('studentInfo').classList.remove('active');
            document.getElementById('clearBtn').style.display = 'none';
        }}

        // Show selected student info
        function showStudentInfo() {{
            const selected = document.getElementById('studentSelect').value;
            const infoPanel = document.getElementById('studentInfo');

            if (!selected) {{
                infoPanel.classList.remove('active');
                return;
            }}

            const data = studentData[selected];
            document.getElementById('displayName').textContent = data.display_name;
            document.getElementById('completedCount').textContent = data.count;
            document.getElementById('sentCount').textContent = data.sent_count;
            document.getElementById('missingCount').textContent = data.missing.length;
            document.getElementById('percentComplete').textContent =
                Math.round((data.count / data.total) * 100) + '%';

            // Render sent routes (green - 80%+ OK)
            document.getElementById('sentRoutes').innerHTML = data.sent
                .map(r => `<span class="route-tag route-sent">${{r}}</span>`)
                .join('') || '<em>None yet</em>';

            // Render not-sent routes (yellow - submitted but needs work)
            document.getElementById('notSentRoutes').innerHTML = data.not_sent
                .map(r => `<span class="route-tag route-not-sent">${{r}}</span>`)
                .join('') || '<em>None</em>';

            // Render missing routes
            document.getElementById('missingRoutes').innerHTML = data.missing
                .map(r => `<span class="route-tag route-missing">${{r}}</span>`)
                .join('') || '<em>All complete!</em>';

            // Render grading feedback
            renderGrades(data);

            infoPanel.classList.add('active');
        }}

        // Render grading feedback for a student
        function renderGrades(data) {{
            const container = document.getElementById('gradesContainer');
            const grades = data.grades || {{}};
            const gradedRoutes = Object.keys(grades).sort();

            if (gradedRoutes.length === 0) {{
                container.innerHTML = '<p class="no-grades">No grading feedback available yet.</p>';
                return;
            }}

            let html = '';
            for (const rid of gradedRoutes) {{
                const gradeInfo = grades[rid];
                const exercises = gradeInfo.exercises || [];

                // Calculate summary stats
                const excellent = exercises.filter(e => e.rating === 'EXCELLENT').length;
                const ok = exercises.filter(e => e.rating === 'OK').length;
                const needsWork = exercises.filter(e => e.rating === 'NEEDS_WORK').length;
                const total = exercises.length;

                // Auto-expand routes that need work so students see feedback immediately
                const autoExpand = needsWork > 0;
                const expandedClass = autoExpand ? 'expanded' : '';
                const rotatedClass = autoExpand ? 'rotated' : '';

                html += `
                    <div class="route-grade-card">
                        <div class="route-grade-header" onclick="toggleGradeCard(this)">
                            <span>${{rid}}</span>
                            <span>
                                <span class="grade-summary-badge">${{excellent}}/${{total}} Excellent</span>
                                <span class="expand-icon ${{rotatedClass}}">▼</span>
                            </span>
                        </div>
                        <div class="route-grade-body ${{expandedClass}}">
                `;

                for (const ex of exercises) {{
                    const ratingClass = 'rating-' + ex.rating.toLowerCase();
                    html += `
                        <div class="exercise-row">
                            <span class="exercise-id">${{ex.exercise_id}}</span>
                            <span class="exercise-rating ${{ratingClass}}">${{ex.rating}}</span>
                            <span class="exercise-rationale">${{ex.rationale || ''}}</span>
                        </div>
                    `;
                }}

                if (gradeInfo.overall_summary) {{
                    html += `<div class="overall-summary"><strong>Summary:</strong> ${{gradeInfo.overall_summary}}</div>`;
                }}

                html += `
                        </div>
                    </div>
                `;
            }}

            container.innerHTML = html;
        }}

        // Toggle grade card expansion
        function toggleGradeCard(header) {{
            const body = header.nextElementSibling;
            const icon = header.querySelector('.expand-icon');
            body.classList.toggle('expanded');
            icon.classList.toggle('rotated');
        }}

        // --- Route Analysis Functions ---
        function showRouteAnalysis(routeId) {{
            const data = routeAnalysisData[routeId];
            if (!data) return;

            const panel = document.getElementById('routeAnalysisPanel');
            document.getElementById('routeAnalysisTitle').textContent = `Route Analysis: ${{routeId}}`;
            document.getElementById('raSubmissions').textContent = data.total_submissions;
            document.getElementById('raSent').textContent = data.sent;
            document.getElementById('raNotSent').textContent = data.not_sent;
            document.getElementById('raSendRate').textContent = Math.round(data.send_rate) + '%';

            // Show/hide free pass banner
            document.getElementById('freePassBanner').style.display = data.free_pass ? 'block' : 'none';

            // Render exercise success rates
            let exerciseHtml = '';
            const exercises = Object.entries(data.exercise_success).sort((a, b) => a[0].localeCompare(b[0]));
            for (const [exId, exData] of exercises) {{
                const rate = exData.rate;
                const color = rate >= 80 ? '#28a745' : (rate >= 50 ? '#ffc107' : '#dc3545');
                exerciseHtml += `
                    <div class="exercise-bar">
                        <span class="exercise-bar-label">${{exId.replace('Exercise ', 'Ex ')}}</span>
                        <div class="exercise-bar-track">
                            <div class="exercise-bar-fill" style="width: ${{rate}}%; background: ${{color}};"></div>
                        </div>
                        <span class="exercise-bar-value">${{rate}}%</span>
                    </div>
                `;
            }}
            document.getElementById('exerciseSuccessRates').innerHTML = exerciseHtml || '<em>No exercise data</em>';

            // Render common issues
            let issuesHtml = '';
            const issues = Object.entries(data.issues).sort((a, b) => b[1].count - a[1].count);
            if (issues.length === 0) {{
                issuesHtml = '<p style="color: #28a745;"><strong>No significant issues found - this route has excellent send rates!</strong></p>';
            }} else {{
                for (const [exId, issueData] of issues) {{
                    const severe = issueData.percentage >= 30;
                    issuesHtml += `
                        <div class="issue-card ${{severe ? 'severe' : ''}}">
                            <div class="issue-header">
                                <span>${{exId}}</span>
                                <span>${{issueData.count}} students (${{issueData.percentage}}%)</span>
                            </div>
                            <ul class="issue-samples">
                                ${{issueData.samples.map(s => `<li>${{s.substring(0, 150)}}${{s.length > 150 ? '...' : ''}}</li>`).join('')}}
                            </ul>
                        </div>
                    `;
                }}
            }}
            document.getElementById('commonIssues').innerHTML = issuesHtml;

            panel.style.display = 'block';
            panel.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}

        function closeRouteAnalysis() {{
            document.getElementById('routeAnalysisPanel').style.display = 'none';
        }}

        // Hook into plotly heatmap clicks
        function setupRouteClickHandler() {{
            const routeChart = document.getElementById('routeHeatmap');
            if (routeChart) {{
                routeChart.on('plotly_click', function(data) {{
                    if (data.points && data.points[0]) {{
                        const text = data.points[0].text || '';
                        const match = text.match(/R(\\d+)/);
                        if (match) {{
                            const routeId = 'RID_' + match[1];
                            showRouteAnalysis(routeId);
                        }}
                    }}
                }});
                console.log('Route click handler attached');
            }} else {{
                console.log('Route chart not found, retrying...');
                setTimeout(setupRouteClickHandler, 500);
            }}
        }}

        // Initialize
        populateDropdown(allStudents);
        // Setup route click handler after plotly loads
        setTimeout(setupRouteClickHandler, 500);
    </script>
</body>
</html>'''

    # Write to file
    with open(output_path, 'w') as f:
        f.write(html_content)

    print(f"Interactive dashboard saved to: {output_path}")
    print(f"Open in browser: file://{os.path.abspath(output_path)}")

    return fig


def main(interactive: bool = True):
    """Run dashboard."""
    student_routes = scan_submissions()
    print_summary(student_routes)

    if interactive and HAS_PLOTLY:
        plot_interactive_dashboard(student_routes, output_path="dashboard.html")
    else:
        plot_dashboard(student_routes, output_path="dashboard.png")


if __name__ == "__main__":
    main()
