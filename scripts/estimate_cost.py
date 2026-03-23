#!/usr/bin/env python3
"""
Estimate grading costs by running a small sample and measuring token usage.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graderbot.llm_client import create_client
from graderbot.grader import prepare_grading_context
from graderbot.prompts import SYSTEM_PROMPT, build_grading_prompt

# GPT-4o pricing (as of Jan 2025)
INPUT_COST_PER_1M = 2.50   # $2.50 per 1M input tokens
OUTPUT_COST_PER_1M = 10.00  # $10.00 per 1M output tokens


def estimate_cost(route_id: str = "RID_002", sample_size: int = 3):
    """Grade a few notebooks and report token usage."""

    assignments_dir = Path(__file__).parent.parent / "assignments"
    route_dir = assignments_dir / route_id
    route_file = route_dir / "instructions.md"
    submissions_dir = route_dir / "submissions"

    if not route_file.exists():
        print(f"Error: {route_file} not found")
        return

    notebooks = list(submissions_dir.glob("*.ipynb"))[:sample_size]

    if not notebooks:
        print(f"No notebooks found in {submissions_dir}")
        return

    print(f"Testing {len(notebooks)} notebooks from {route_id}...")
    print("=" * 60)

    client = create_client("openai")
    total_input = 0
    total_output = 0

    for i, nb in enumerate(notebooks, 1):
        print(f"\n[{i}/{len(notebooks)}] Grading: {nb.name}")

        response = grade_notebook_with_usage(
            route_file=route_file,
            notebook_file=nb,
            client=client
        )

        if response and response.usage:
            input_tokens = response.usage.get("prompt_tokens", 0)
            output_tokens = response.usage.get("completion_tokens", 0)
            total_input += input_tokens
            total_output += output_tokens

            input_cost = input_tokens / 1_000_000 * INPUT_COST_PER_1M
            output_cost = output_tokens / 1_000_000 * OUTPUT_COST_PER_1M

            print(f"   Input tokens:  {input_tokens:,} (${input_cost:.4f})")
            print(f"   Output tokens: {output_tokens:,} (${output_cost:.4f})")
            print(f"   Total cost:    ${input_cost + output_cost:.4f}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    avg_input = total_input / len(notebooks)
    avg_output = total_output / len(notebooks)
    avg_cost = (avg_input / 1_000_000 * INPUT_COST_PER_1M +
                avg_output / 1_000_000 * OUTPUT_COST_PER_1M)

    print(f"Average per notebook:")
    print(f"   Input tokens:  {avg_input:,.0f}")
    print(f"   Output tokens: {avg_output:,.0f}")
    print(f"   Cost:          ${avg_cost:.4f}")

    print(f"\nEstimated cost for 661 notebooks: ${661 * avg_cost:.2f}")


def grade_notebook_with_usage(route_file, notebook_file, client):
    """Grade a notebook and return the LLM response with usage info."""
    context = prepare_grading_context(
        route_path=route_file,
        notebook_path=notebook_file
    )

    user_prompt = build_grading_prompt(
        route_text=context.route_text,
        notebook_text=context.notebook_text,
        exercise_ids=context.exercise_ids,
        route_id=context.route_id,
        student_id=context.student_id,
    )

    response = client.chat(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0
    )

    return response


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", default="RID_002", help="Route ID to test")
    parser.add_argument("--count", type=int, default=3, help="Number of notebooks")
    args = parser.parse_args()

    estimate_cost(args.route, args.count)
