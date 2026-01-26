"""Route-level analysis: aggregate feedback and identify common issues."""

from __future__ import annotations

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import Optional

# Try to import LLM client for summarization
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


def collect_route_feedback(route_id: str, assignments_dir: str = "assignments") -> dict:
    """
    Collect all grading feedback for a specific route.

    Returns:
        dict with structure:
        {
            'route_id': str,
            'total_submissions': int,
            'exercises': {
                'Exercise 1': {
                    'excellent': [...],
                    'ok': [...],
                    'needs_work': [{'student': str, 'rationale': str}, ...]
                },
                ...
            },
            'stats': {
                'Exercise 1': {'excellent': int, 'ok': int, 'needs_work': int},
                ...
            }
        }
    """
    results_dir = Path(assignments_dir) / route_id / "results"

    if not results_dir.exists():
        return {'route_id': route_id, 'error': 'No results directory found'}

    # Collect feedback by exercise and rating
    exercises = defaultdict(lambda: {'excellent': [], 'ok': [], 'needs_work': []})
    total_submissions = 0

    for json_file in results_dir.glob("*_grade.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            total_submissions += 1
            student_name = json_file.stem.replace('_grade', '')

            for ex in data.get('exercises', []):
                ex_id = ex.get('exercise_id', 'Unknown')
                rating = ex.get('rating', 'UNKNOWN').lower()
                rationale = ex.get('rationale', '')

                if rating in ('excellent', 'ok', 'needs_work'):
                    exercises[ex_id][rating].append({
                        'student': student_name,
                        'rationale': rationale
                    })
        except (json.JSONDecodeError, IOError):
            continue

    # Calculate stats
    stats = {}
    for ex_id, ratings in exercises.items():
        stats[ex_id] = {
            'excellent': len(ratings['excellent']),
            'ok': len(ratings['ok']),
            'needs_work': len(ratings['needs_work'])
        }

    return {
        'route_id': route_id,
        'total_submissions': total_submissions,
        'exercises': dict(exercises),
        'stats': stats
    }


def get_common_issues(feedback: dict, min_occurrences: int = 3) -> dict:
    """
    Extract exercises with significant NEEDS_WORK feedback.

    Returns:
        dict: {exercise_id: {'count': int, 'sample_rationales': [str, ...]}}
    """
    issues = {}

    for ex_id, ratings in feedback.get('exercises', {}).items():
        needs_work = ratings.get('needs_work', [])
        if len(needs_work) >= min_occurrences:
            issues[ex_id] = {
                'count': len(needs_work),
                'total': feedback['total_submissions'],
                'percentage': len(needs_work) / feedback['total_submissions'] * 100,
                'sample_rationales': [r['rationale'] for r in needs_work[:10]]
            }

    return issues


def summarize_with_llm(route_id: str, issues: dict, provider: str = "anthropic") -> Optional[str]:
    """
    Use an LLM to summarize common issues and suggest improvements.

    Args:
        route_id: The route identifier
        issues: Dict of exercises with NEEDS_WORK feedback
        provider: 'anthropic' or 'openai'

    Returns:
        Summary string or None if LLM call fails
    """
    if not HAS_HTTPX:
        return None

    if not issues:
        return "No significant issues found - this route has excellent send rates!"

    # Build prompt with the issues data
    issues_text = []
    for ex_id, data in sorted(issues.items(), key=lambda x: -x[1]['count']):
        issues_text.append(f"\n## {ex_id} ({data['count']}/{data['total']} students, {data['percentage']:.0f}%)")
        issues_text.append("Sample feedback from grader:")
        for i, rationale in enumerate(data['sample_rationales'][:5], 1):
            issues_text.append(f"  {i}. {rationale[:300]}")

    prompt = f"""Analyze the grading feedback for {route_id} and provide actionable insights.

GRADING DATA:
{''.join(issues_text)}

Please provide:
1. **Common Patterns**: What are the 2-3 main reasons students are struggling?
2. **Root Cause Analysis**: Is this likely due to:
   - Unclear instructions in the route?
   - Difficult concepts students aren't grasping?
   - Students not showing their work properly?
   - Grading criteria being too strict?
3. **Recommendations**: 2-3 specific suggestions to improve send rates.

Be concise and actionable. Format as markdown."""

    try:
        if provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                return None

            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60.0
            )

            if response.status_code == 200:
                data = response.json()
                return data['content'][0]['text']

        elif provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return None

            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60.0
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']

    except Exception as e:
        print(f"LLM call failed: {e}")
        return None

    return None


def analyze_route(route_id: str, use_llm: bool = True, provider: str = "anthropic") -> dict:
    """
    Full route analysis: collect feedback, identify issues, optionally summarize with LLM.

    Returns:
        dict with all analysis results
    """
    feedback = collect_route_feedback(route_id)
    issues = get_common_issues(feedback)

    # Calculate overall send rate
    total = feedback['total_submissions']
    total_exercises = len(feedback.get('exercises', {}))

    if total > 0 and total_exercises > 0:
        # A student "sends" if 80%+ exercises are OK or better
        # For route-level, we look at per-exercise success rates
        exercise_success = {}
        for ex_id, stats in feedback.get('stats', {}).items():
            ok_plus = stats['excellent'] + stats['ok']
            exercise_success[ex_id] = ok_plus / total * 100
    else:
        exercise_success = {}

    result = {
        'route_id': route_id,
        'total_submissions': total,
        'exercise_stats': feedback.get('stats', {}),
        'exercise_success_rates': exercise_success,
        'issues': issues,
        'llm_summary': None
    }

    if use_llm and issues:
        result['llm_summary'] = summarize_with_llm(route_id, issues, provider)

    return result


def generate_route_report(route_id: str, use_llm: bool = True, provider: str = "anthropic") -> str:
    """Generate a human-readable report for a route."""
    analysis = analyze_route(route_id, use_llm, provider)

    lines = [
        f"# Route Analysis: {route_id}",
        f"\n**Total Submissions:** {analysis['total_submissions']}",
        "\n## Exercise Success Rates\n"
    ]

    for ex_id in sorted(analysis['exercise_success_rates'].keys()):
        rate = analysis['exercise_success_rates'][ex_id]
        bar = "█" * int(rate / 5) + "░" * (20 - int(rate / 5))
        lines.append(f"- {ex_id}: {bar} {rate:.0f}%")

    if analysis['issues']:
        lines.append("\n## Exercises Needing Attention\n")
        for ex_id, data in sorted(analysis['issues'].items(), key=lambda x: -x[1]['count']):
            lines.append(f"### {ex_id} ({data['count']} students, {data['percentage']:.0f}% failure rate)")
            lines.append("\nSample issues:")
            for rationale in data['sample_rationales'][:3]:
                lines.append(f"- {rationale[:200]}...")
            lines.append("")

    if analysis['llm_summary']:
        lines.append("\n## AI Analysis\n")
        lines.append(analysis['llm_summary'])

    return '\n'.join(lines)


if __name__ == "__main__":
    import sys

    route_id = sys.argv[1] if len(sys.argv) > 1 else "RID_007"
    use_llm = "--no-llm" not in sys.argv

    print(generate_route_report(route_id, use_llm=use_llm))
