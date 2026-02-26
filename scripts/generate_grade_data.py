#!/usr/bin/env python3
"""Generate grade-related CSV files for final grade calculation."""

import csv
from datetime import datetime
from pathlib import Path

# Add parent to path for graderbot import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from graderbot.dashboard import scan_submissions


GRADES_DIR = Path(__file__).parent.parent / "grades"
MIDTERM_ROUTES = {'MID_001', 'MID_002', 'MID_003'}
EC_ROUTES = {'RID_EC1'}


def generate_route_completion_summary():
    """Generate comprehensive route completion summary."""
    student_routes = scan_submissions()

    data = []
    for student, routes in sorted(student_routes.items()):
        regular = routes - MIDTERM_ROUTES - EC_ROUTES
        midterms = routes & MIDTERM_ROUTES
        extra_credit = routes & EC_ROUTES

        data.append({
            'student_id': student,
            'regular_routes': len(regular),
            'midterms_completed': len(midterms),
            'extra_credit': len(extra_credit),
            'total_routes': len(routes),
            'regular_route_list': ','.join(sorted(regular)),
            'midterm_list': ','.join(sorted(midterms)),
            'ec_list': ','.join(sorted(extra_credit)),
        })

    output_file = GRADES_DIR / 'route_completion_summary.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'student_id', 'regular_routes', 'midterms_completed',
            'extra_credit', 'total_routes', 'regular_route_list',
            'midterm_list', 'ec_list'
        ])
        writer.writeheader()
        writer.writerows(data)

    print(f"Wrote {len(data)} students to {output_file}")
    return data


def generate_penalty_list(threshold=10):
    """Generate list of students below route threshold."""
    student_routes = scan_submissions()

    under_threshold = []
    for student, routes in sorted(student_routes.items()):
        regular = routes - MIDTERM_ROUTES
        ec = routes & EC_ROUTES
        # Count regular routes + extra credit toward threshold
        total_toward_threshold = len(regular) + len(ec)
        if total_toward_threshold < threshold:
            under_threshold.append({
                'student_id': student,
                'display_name': student.replace('_', ' ').title(),
                'routes_sent': total_toward_threshold,
                'routes_needed': threshold - total_toward_threshold,
            })

    # Sort by routes_sent ascending
    under_threshold.sort(key=lambda x: x['routes_sent'])

    output_file = GRADES_DIR / 'penalty_feb23_under10_routes.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'student_id', 'display_name', 'routes_sent', 'routes_needed'
        ])
        writer.writeheader()
        writer.writerows(under_threshold)

    print(f"Wrote {len(under_threshold)} students to {output_file}")
    return under_threshold


def generate_midterm_completion():
    """Generate midterm completion status."""
    student_routes = scan_submissions()

    data = []
    for student, routes in sorted(student_routes.items()):
        midterms = routes & MIDTERM_ROUTES
        data.append({
            'student_id': student,
            'MID_001': 'Y' if 'MID_001' in midterms else '',
            'MID_002': 'Y' if 'MID_002' in midterms else '',
            'MID_003': 'Y' if 'MID_003' in midterms else '',
            'midterms_completed': len(midterms),
        })

    output_file = GRADES_DIR / 'midterm_completion.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'student_id', 'MID_001', 'MID_002', 'MID_003', 'midterms_completed'
        ])
        writer.writeheader()
        writer.writerows(data)

    # Print summary
    complete_all = sum(1 for d in data if d['midterms_completed'] == 3)
    complete_2 = sum(1 for d in data if d['midterms_completed'] == 2)
    complete_1 = sum(1 for d in data if d['midterms_completed'] == 1)
    complete_0 = sum(1 for d in data if d['midterms_completed'] == 0)

    print(f"Midterm completion: {complete_all} all, {complete_2} two, {complete_1} one, {complete_0} none")
    return data


def generate_extra_credit():
    """Generate extra credit list."""
    student_routes = scan_submissions()

    ec_students = []
    for student, routes in sorted(student_routes.items()):
        ec = routes & EC_ROUTES
        if ec:
            ec_students.append({
                'student_id': student,
                'extra_credit_routes': ','.join(sorted(ec)),
                'ec_count': len(ec),
                'reason': 'In-class participation',
            })

    output_file = GRADES_DIR / 'extra_credit.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'student_id', 'extra_credit_routes', 'ec_count', 'reason'
        ])
        writer.writeheader()
        writer.writerows(ec_students)

    print(f"Wrote {len(ec_students)} students with extra credit")
    return ec_students


def main():
    """Generate all grade data files."""
    print("=" * 60)
    print("GENERATING GRADE DATA")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    GRADES_DIR.mkdir(exist_ok=True)

    print("\n1. Route completion summary...")
    generate_route_completion_summary()

    print("\n2. Penalty list (Feb 23 deadline, <10 routes)...")
    generate_penalty_list()

    print("\n3. Midterm completion...")
    generate_midterm_completion()

    print("\n4. Extra credit...")
    generate_extra_credit()

    print("\n" + "=" * 60)
    print(f"All files written to: {GRADES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
