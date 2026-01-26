"""Main grader orchestration module."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .llm_client import LLMClient, LLMResponse
from .notebook_view import (
    NotebookView,
    SolutionExercise,
    extract_exercises_from_notebook,
    format_notebook_for_prompt,
    format_solution_for_prompt,
    get_solution_exercise_ids,
    parse_notebook_file,
)
from .prompts import (
    SOLUTION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_grading_prompt,
    build_repair_prompt,
    build_solution_grading_prompt,
)
from .route_parser import Route, format_route_for_prompt, get_exercise_ids, parse_route_file
from .schema import GradingResult


@dataclass
class GradingContext:
    """Context for a grading operation (route-based)."""

    route: Route
    notebook: NotebookView
    route_text: str
    notebook_text: str
    exercise_ids: list[str]
    route_id: str | None = None
    student_id: str | None = None


@dataclass
class SolutionGradingContext:
    """Context for a solution-based grading operation."""

    solution_exercises: list[SolutionExercise]
    notebook: NotebookView
    solution_text: str
    notebook_text: str
    exercise_ids: list[str]
    exercise_types: dict[str, str]  # Maps exercise_id to 'code' or 'writing'
    route_id: str | None = None
    student_id: str | None = None


class GradingError(Exception):
    """Error during grading process."""

    pass


def extract_json_from_response(content: str) -> str:
    """
    Extract JSON from LLM response, handling markdown code blocks.

    Args:
        content: Raw LLM response

    Returns:
        Extracted JSON string
    """
    # Try to find JSON in code blocks first
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    matches = re.findall(code_block_pattern, content, re.DOTALL)
    if matches:
        return matches[0].strip()

    # Otherwise, try to find raw JSON (object starting with {)
    content = content.strip()
    if content.startswith("{"):
        return content

    # Look for JSON object anywhere in the response
    json_pattern = r"\{.*\}"
    match = re.search(json_pattern, content, re.DOTALL)
    if match:
        return match.group(0)

    return content


def parse_and_validate_response(content: str) -> GradingResult:
    """
    Parse and validate LLM response as GradingResult.

    Args:
        content: Raw LLM response content

    Returns:
        Validated GradingResult

    Raises:
        ValidationError: If JSON is invalid or doesn't match schema
        json.JSONDecodeError: If content is not valid JSON
    """
    json_str = extract_json_from_response(content)
    data = json.loads(json_str)
    return GradingResult.model_validate(data)


def prepare_grading_context(
    route_path: Path | str,
    notebook_path: Path | str,
    route_id: str | None = None,
    student_id: str | None = None,
) -> GradingContext:
    """
    Prepare the context for grading.

    Args:
        route_path: Path to route markdown file
        notebook_path: Path to student notebook
        route_id: Optional route identifier
        student_id: Optional student identifier

    Returns:
        GradingContext ready for grading
    """
    route = parse_route_file(route_path)
    notebook = parse_notebook_file(notebook_path)

    route_text = format_route_for_prompt(route)
    notebook_text = format_notebook_for_prompt(notebook)
    exercise_ids = get_exercise_ids(route)

    return GradingContext(
        route=route,
        notebook=notebook,
        route_text=route_text,
        notebook_text=notebook_text,
        exercise_ids=exercise_ids,
        route_id=route_id,
        student_id=student_id,
    )


def prepare_solution_grading_context(
    solution_path: Path | str,
    notebook_path: Path | str,
    route_id: str | None = None,
    student_id: str | None = None,
) -> SolutionGradingContext:
    """
    Prepare the context for solution-based grading.

    Args:
        solution_path: Path to solution notebook
        notebook_path: Path to student notebook
        route_id: Optional route identifier
        student_id: Optional student identifier

    Returns:
        SolutionGradingContext ready for grading
    """
    solution_notebook = parse_notebook_file(solution_path)
    student_notebook = parse_notebook_file(notebook_path)

    # Extract exercises from solution
    solution_exercises = extract_exercises_from_notebook(solution_notebook)

    if not solution_exercises:
        raise GradingError(
            "No exercises found in solution notebook. "
            "Exercises must be marked with markdown headers like '## Exercise 1'"
        )

    solution_text = format_solution_for_prompt(solution_exercises)
    notebook_text = format_notebook_for_prompt(student_notebook)
    exercise_ids = get_solution_exercise_ids(solution_exercises)
    exercise_types = {ex.exercise_id: ex.exercise_type for ex in solution_exercises}

    return SolutionGradingContext(
        solution_exercises=solution_exercises,
        notebook=student_notebook,
        solution_text=solution_text,
        notebook_text=notebook_text,
        exercise_ids=exercise_ids,
        exercise_types=exercise_types,
        route_id=route_id,
        student_id=student_id,
    )


def grade_notebook(
    client: LLMClient,
    context: GradingContext,
    max_retries: int = 2,
    temperature: float = 0.0,
) -> GradingResult:
    """
    Grade a notebook using the LLM.

    Args:
        client: LLM client to use
        context: Prepared grading context
        max_retries: Maximum retries for JSON repair
        temperature: Sampling temperature

    Returns:
        Validated GradingResult

    Raises:
        GradingError: If grading fails after all retries
    """
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
        temperature=temperature,
    )

    # Try to parse and validate
    last_error = None
    content = response.content

    for attempt in range(max_retries + 1):
        try:
            result = parse_and_validate_response(content)

            # Fill in route_id and student_id if not set
            if context.route_id and not result.route_id:
                result.route_id = context.route_id
            if context.student_id and not result.student_id:
                result.student_id = context.student_id

            return result

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            error_msg = str(e)

            if attempt < max_retries:
                # Try to repair
                repair_prompt = build_repair_prompt(content, error_msg)
                repair_response = client.chat(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=repair_prompt,
                    temperature=0.0,
                )
                content = repair_response.content

    raise GradingError(
        f"Failed to get valid grading response after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def grade_notebook_from_paths(
    client: LLMClient,
    route_path: Path | str,
    notebook_path: Path | str,
    route_id: str | None = None,
    student_id: str | None = None,
    max_retries: int = 2,
) -> GradingResult:
    """
    Convenience function to grade a notebook from file paths.

    Args:
        client: LLM client to use
        route_path: Path to route markdown file
        notebook_path: Path to student notebook
        route_id: Optional route identifier
        student_id: Optional student identifier
        max_retries: Maximum retries for JSON repair

    Returns:
        Validated GradingResult
    """
    context = prepare_grading_context(
        route_path=route_path,
        notebook_path=notebook_path,
        route_id=route_id,
        student_id=student_id,
    )

    return grade_notebook(client, context, max_retries=max_retries)


def grade_notebook_with_solution(
    client: LLMClient,
    context: SolutionGradingContext,
    max_retries: int = 2,
    temperature: float = 0.0,
) -> GradingResult:
    """
    Grade a notebook using solution-based comparison.

    Args:
        client: LLM client to use
        context: Prepared solution grading context
        max_retries: Maximum retries for JSON repair
        temperature: Sampling temperature

    Returns:
        Validated GradingResult

    Raises:
        GradingError: If grading fails after all retries
    """
    user_prompt = build_solution_grading_prompt(
        solution_text=context.solution_text,
        notebook_text=context.notebook_text,
        exercise_ids=context.exercise_ids,
        exercise_types=context.exercise_types,
        route_id=context.route_id,
        student_id=context.student_id,
    )

    response = client.chat(
        system_prompt=SOLUTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=temperature,
    )

    # Try to parse and validate
    last_error = None
    content = response.content

    for attempt in range(max_retries + 1):
        try:
            result = parse_and_validate_response(content)

            # Fill in route_id and student_id if not set
            if context.route_id and not result.route_id:
                result.route_id = context.route_id
            if context.student_id and not result.student_id:
                result.student_id = context.student_id

            return result

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            error_msg = str(e)

            if attempt < max_retries:
                # Try to repair
                repair_prompt = build_repair_prompt(content, error_msg)
                repair_response = client.chat(
                    system_prompt=SOLUTION_SYSTEM_PROMPT,
                    user_prompt=repair_prompt,
                    temperature=0.0,
                )
                content = repair_response.content

    raise GradingError(
        f"Failed to get valid grading response after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def grade_notebook_from_solution_paths(
    client: LLMClient,
    solution_path: Path | str,
    notebook_path: Path | str,
    route_id: str | None = None,
    student_id: str | None = None,
    max_retries: int = 2,
) -> GradingResult:
    """
    Convenience function to grade a notebook from solution notebook path.

    Args:
        client: LLM client to use
        solution_path: Path to solution notebook
        notebook_path: Path to student notebook
        route_id: Optional route identifier
        student_id: Optional student identifier
        max_retries: Maximum retries for JSON repair

    Returns:
        Validated GradingResult
    """
    context = prepare_solution_grading_context(
        solution_path=solution_path,
        notebook_path=notebook_path,
        route_id=route_id,
        student_id=student_id,
    )

    return grade_notebook_with_solution(client, context, max_retries=max_retries)


def get_dry_run_output(context: GradingContext) -> str:
    """
    Get the prompt that would be sent to the LLM (for dry run mode).

    Args:
        context: Prepared grading context

    Returns:
        Formatted string showing what would be sent
    """
    user_prompt = build_grading_prompt(
        route_text=context.route_text,
        notebook_text=context.notebook_text,
        exercise_ids=context.exercise_ids,
        route_id=context.route_id,
        student_id=context.student_id,
    )

    output = []
    output.append("=" * 70)
    output.append("DRY RUN - Prompts that would be sent to LLM")
    output.append("=" * 70)
    output.append("")
    output.append("### SYSTEM PROMPT ###")
    output.append("-" * 40)
    output.append(SYSTEM_PROMPT)
    output.append("")
    output.append("### USER PROMPT ###")
    output.append("-" * 40)
    output.append(user_prompt)
    output.append("")
    output.append("=" * 70)
    output.append(f"Total exercises to grade: {len(context.exercise_ids)}")
    output.append(f"Exercise IDs: {', '.join(context.exercise_ids)}")
    output.append(f"Notebook cells: {len(context.notebook.cells)}")
    output.append("=" * 70)

    return "\n".join(output)


def get_solution_dry_run_output(context: SolutionGradingContext) -> str:
    """
    Get the prompt that would be sent to the LLM for solution-based grading (dry run mode).

    Args:
        context: Prepared solution grading context

    Returns:
        Formatted string showing what would be sent
    """
    user_prompt = build_solution_grading_prompt(
        solution_text=context.solution_text,
        notebook_text=context.notebook_text,
        exercise_ids=context.exercise_ids,
        exercise_types=context.exercise_types,
        route_id=context.route_id,
        student_id=context.student_id,
    )

    output = []
    output.append("=" * 70)
    output.append("DRY RUN - Prompts that would be sent to LLM (Solution Mode)")
    output.append("=" * 70)
    output.append("")
    output.append("### SYSTEM PROMPT ###")
    output.append("-" * 40)
    output.append(SOLUTION_SYSTEM_PROMPT)
    output.append("")
    output.append("### USER PROMPT ###")
    output.append("-" * 40)
    output.append(user_prompt)
    output.append("")
    output.append("=" * 70)
    output.append(f"Total exercises to grade: {len(context.exercise_ids)}")
    output.append(f"Exercise IDs: {', '.join(context.exercise_ids)}")

    # Show exercise types
    type_info = [f"{eid} ({context.exercise_types.get(eid, 'code')})"
                 for eid in context.exercise_ids]
    output.append(f"Exercise types: {', '.join(type_info)}")
    output.append(f"Student notebook cells: {len(context.notebook.cells)}")
    output.append("=" * 70)

    return "\n".join(output)


@dataclass
class TextGradingContext:
    """Context for grading text file submissions (e.g., git logs)."""

    route: Route
    submission_text: str
    route_text: str
    exercise_ids: list[str]
    route_id: str | None = None
    student_id: str | None = None


def prepare_text_grading_context(
    route_path: Path | str,
    deliverable_path: Path | str,
    logbook_path: Path | str | None = None,
    route_id: str | None = None,
    student_id: str | None = None,
) -> TextGradingContext:
    """
    Prepare context for grading text file submissions.

    Args:
        route_path: Path to route markdown file
        deliverable_path: Path to deliverable.txt file
        logbook_path: Optional path to logbook.txt file
        route_id: Optional route identifier
        student_id: Optional student identifier

    Returns:
        TextGradingContext ready for grading
    """
    from .text_view import render_text_submission

    route = parse_route_file(route_path)
    route_text = format_route_for_prompt(route)
    exercise_ids = get_exercise_ids(route)

    submission_text = render_text_submission(str(deliverable_path), str(logbook_path) if logbook_path else None)

    return TextGradingContext(
        route=route,
        submission_text=submission_text,
        route_text=route_text,
        exercise_ids=exercise_ids,
        route_id=route_id,
        student_id=student_id,
    )


TEXT_GRADING_SYSTEM_PROMPT = """You are an expert grader for a scientific computing course. Your task is to grade student text file submissions (git logs, reflection answers, etc.) against assignment instructions.

## Grading Criteria
- **EXCELLENT**: Fully meets requirements with clear evidence of understanding
- **OK**: Meets basic requirements but may have minor issues or incomplete explanations
- **NEEDS_WORK**: Missing key requirements or shows misunderstanding

## For Git Log Submissions
When grading git deliverables, look for:
1. Valid repository URL (github.com link)
2. Commit history showing required steps were performed
3. Proper commit messages describing the work
4. Evidence of branching/merging if required
5. Author name/email configured

## For Logbook/Reflection Submissions
When grading written reflections, evaluate:
1. Completeness - Did they answer all questions?
2. Understanding - Do they demonstrate grasp of concepts?
3. Specificity - Did they provide concrete examples from their experience?
4. Thoughtfulness - Is there evidence of genuine reflection?

## Important
- Be fair but rigorous
- Give credit for partial understanding
- If something is ambiguous, lean toward giving the student benefit of the doubt
- Focus on whether they demonstrated learning, not perfection"""


def build_text_grading_prompt(
    route_text: str,
    submission_text: str,
    exercise_ids: list[str],
    route_id: str | None = None,
    student_id: str | None = None,
) -> str:
    """Build the grading prompt for text submissions."""
    json_schema = """{
  "schema_version": "1.0",
  "route_id": "<route identifier or null>",
  "student_id": "<student identifier or null>",
  "exercises": [
    {
      "exercise_id": "<Exercise N or Part X>",
      "rating": "EXCELLENT | OK | NEEDS_WORK",
      "feedback": "<specific feedback>",
      "flags": ["<optional flags like manual_review>"]
    }
  ],
  "overall_summary": "<brief overall assessment>"
}"""

    return f"""# Grading Task

Grade the following text submission against the assignment instructions.

## Assignment Instructions
{route_text}

## Student Submission
{submission_text}

## Exercises to Grade
{', '.join(exercise_ids)}

## Output Format
Return a JSON object matching this schema:
{json_schema}

Route ID: {route_id or 'null'}
Student ID: {student_id or 'null'}

Grade each exercise and provide specific feedback based on what you see in their submission."""


def grade_text_submission(
    client: LLMClient,
    context: TextGradingContext,
    max_retries: int = 2,
    temperature: float = 0.0,
) -> GradingResult:
    """
    Grade a text file submission using the LLM.

    Args:
        client: LLM client to use
        context: Prepared text grading context
        max_retries: Maximum retries for JSON repair
        temperature: Sampling temperature

    Returns:
        Validated GradingResult

    Raises:
        GradingError: If grading fails after all retries
    """
    user_prompt = build_text_grading_prompt(
        route_text=context.route_text,
        submission_text=context.submission_text,
        exercise_ids=context.exercise_ids,
        route_id=context.route_id,
        student_id=context.student_id,
    )

    response = client.chat(
        system_prompt=TEXT_GRADING_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=temperature,
    )

    # Try to parse and validate
    last_error = None
    content = response.content

    for attempt in range(max_retries + 1):
        try:
            result = parse_and_validate_response(content)

            # Fill in route_id and student_id if not set
            if context.route_id and not result.route_id:
                result.route_id = context.route_id
            if context.student_id and not result.student_id:
                result.student_id = context.student_id

            return result

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            error_msg = str(e)

            if attempt < max_retries:
                # Try to repair
                repair_prompt = build_repair_prompt(content, error_msg)
                repair_response = client.chat(
                    system_prompt=TEXT_GRADING_SYSTEM_PROMPT,
                    user_prompt=repair_prompt,
                    temperature=0.0,
                )
                content = repair_response.content

    raise GradingError(
        f"Failed to get valid grading response after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def grade_text_from_paths(
    client: LLMClient,
    route_path: Path | str,
    deliverable_path: Path | str,
    logbook_path: Path | str | None = None,
    route_id: str | None = None,
    student_id: str | None = None,
    max_retries: int = 2,
) -> GradingResult:
    """
    Convenience function to grade text submission from file paths.

    Args:
        client: LLM client to use
        route_path: Path to route markdown file
        deliverable_path: Path to deliverable.txt
        logbook_path: Optional path to logbook.txt
        route_id: Optional route identifier
        student_id: Optional student identifier
        max_retries: Maximum retries for JSON repair

    Returns:
        Validated GradingResult
    """
    context = prepare_text_grading_context(
        route_path=route_path,
        deliverable_path=deliverable_path,
        logbook_path=logbook_path,
        route_id=route_id,
        student_id=student_id,
    )

    return grade_text_submission(client, context, max_retries=max_retries)
