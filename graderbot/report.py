"""Generate readable student reports from grading JSON."""

import json
from pathlib import Path


def json_to_report(json_path: str, output_path: str | None = None) -> str:
    """
    Convert grading JSON to a readable student report.

    Args:
        json_path: Path to the grading JSON file
        output_path: Optional path to save the report (defaults to same name with .txt)

    Returns:
        The formatted report as a string
    """
    with open(json_path, "r") as f:
        data = json.load(f)

    lines = []
    lines.append("=" * 60)
    lines.append("GRADING REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Student/Route info if available
    if data.get("student_id"):
        lines.append(f"Student: {data['student_id']}")
    if data.get("route_id"):
        lines.append(f"Assignment: {data['route_id']}")
    if data.get("student_id") or data.get("route_id"):
        lines.append("")

    # Overall summary
    lines.append("-" * 60)
    lines.append("OVERALL SUMMARY")
    lines.append("-" * 60)
    lines.append(data.get("overall_summary", "No summary available."))
    lines.append("")

    # Exercise grades
    lines.append("-" * 60)
    lines.append("EXERCISE GRADES")
    lines.append("-" * 60)
    lines.append("")

    for ex in data.get("exercises", []):
        # Header with rating
        rating = ex.get("rating", "N/A")
        rating_emoji = {"EXCELLENT": "[EXCELLENT]", "OK": "[OK]", "NEEDS_WORK": "[NEEDS WORK]"}.get(rating, f"[{rating}]")

        exercise_id = ex.get("exercise_id", "Unknown")
        lines.append(f"{exercise_id}: {rating_emoji}")
        lines.append("-" * 40)

        # Rationale
        if ex.get("rationale"):
            lines.append(f"Feedback: {ex['rationale']}")

        # Missing or wrong items
        if ex.get("missing_or_wrong"):
            lines.append("")
            lines.append("Issues to address:")
            for item in ex["missing_or_wrong"]:
                lines.append(f"  - {item}")

        # Flags
        if ex.get("flags"):
            lines.append("")
            lines.append(f"Flags: {', '.join(ex['flags'])}")

        lines.append("")
        lines.append("")

    # Grade summary table
    lines.append("-" * 60)
    lines.append("SUMMARY")
    lines.append("-" * 60)

    excellent = sum(1 for ex in data.get("exercises", []) if ex.get("rating") == "EXCELLENT")
    ok = sum(1 for ex in data.get("exercises", []) if ex.get("rating") == "OK")
    needs_work = sum(1 for ex in data.get("exercises", []) if ex.get("rating") == "NEEDS_WORK")
    total = len(data.get("exercises", []))

    lines.append(f"  EXCELLENT:   {excellent}/{total}")
    lines.append(f"  OK:          {ok}/{total}")
    lines.append(f"  NEEDS WORK:  {needs_work}/{total}")
    lines.append("")
    lines.append("=" * 60)

    report = "\n".join(lines)

    # Save to file if output path provided or default
    if output_path is None:
        output_path = str(Path(json_path).with_suffix(".txt"))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m graderbot.report <grading.json> [output.txt]")
        sys.exit(1)

    json_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    report = json_to_report(json_path, output_path)
    print(report)

    output_file = output_path or str(Path(json_path).with_suffix(".txt"))
    print(f"\nReport saved to: {output_file}")


if __name__ == "__main__":
    main()
