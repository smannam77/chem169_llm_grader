# Grades Data

This folder contains grade-related data for final grade calculation.

## Files

### `route_completion_summary.csv`
Complete summary of all students' route completion status.
- `student_id`: Student identifier
- `regular_routes`: Count of regular routes (RID_001-029) sent
- `midterms_completed`: Count of midterms (MID_001-003) completed
- `extra_credit`: Count of extra credit routes
- `total_routes`: Total routes completed
- `regular_route_list`: Comma-separated list of regular routes
- `midterm_list`: Comma-separated list of midterms
- `ec_list`: Comma-separated list of extra credit routes

### `penalty_feb23_under10_routes.csv`
Students with <10 regular routes as of Feb 23 deadline (5% penalty).
- `student_id`: Student identifier
- `display_name`: Display name
- `routes_sent`: Number of routes sent
- `routes_needed`: Routes needed to reach 10

### `midterm_completion.csv`
Midterm completion status per student.
- `student_id`: Student identifier
- `MID_001`, `MID_002`, `MID_003`: Y if completed, blank if not
- `midterms_completed`: Total midterms completed (0-3)

### `extra_credit.csv`
Students who received extra credit.
- `student_id`: Student identifier
- `extra_credit_routes`: Routes awarded as extra credit
- `ec_count`: Number of extra credit routes
- `reason`: Reason for extra credit

## Regenerating Data

Run from repo root:
```bash
python3 -B scripts/generate_grade_data.py
```

## Last Updated
2026-02-24
