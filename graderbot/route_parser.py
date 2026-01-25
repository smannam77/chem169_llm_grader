"""Parse route markdown files into structured exercise specifications."""

import re
from pathlib import Path

from .schema import Exercise, Route


def parse_route(content: str) -> Route:
    """
    Parse a route markdown file into a Route object.

    Expects markdown with:
    - Optional title as # heading
    - Optional preamble text before exercises
    - Exercises marked with ## Exercise N or ### Exercise Na patterns

    Args:
        content: Raw markdown content

    Returns:
        Route object with parsed exercises
    """
    lines = content.split("\n")

    title = None
    preamble_lines: list[str] = []
    exercises: list[Exercise] = []

    # Patterns for exercise headings
    # Handles various formats:
    #   ## Exercise 1. Title
    #   ### **Exercise 1\. Title**
    #   ### Exercise 1: Title
    exercise_pattern = re.compile(
        r"^(#{2,4})\s+\*{0,2}(?:Exercise\s+)?(\d+[a-z]?(?:\.\d+)?)\*{0,2}[\.\\\s:\-]*\*{0,2}\s*(.*)$",
        re.IGNORECASE,
    )
    title_pattern = re.compile(r"^#\s+(.+)$")

    current_exercise: Exercise | None = None
    current_content: list[str] = []
    in_preamble = True

    def finalize_exercise():
        nonlocal current_exercise, current_content
        if current_exercise:
            current_exercise.instructions = "\n".join(current_content).strip()
            exercises.append(current_exercise)
        current_content = []
        current_exercise = None

    for line in lines:
        # Check for main title
        title_match = title_pattern.match(line)
        if title_match and title is None and not exercises:
            title = title_match.group(1).strip()
            in_preamble = True
            continue

        # Check for exercise heading
        exercise_match = exercise_pattern.match(line)
        if exercise_match:
            in_preamble = False

            # Finalize previous exercise
            if current_exercise:
                finalize_exercise()
            elif preamble_lines:
                # Only keep preamble if we haven't started exercises
                pass

            heading_level = len(exercise_match.group(1))
            exercise_num = exercise_match.group(2)
            exercise_title = exercise_match.group(3).strip() or None

            # Clean up title (remove trailing ** from bold markdown)
            if exercise_title:
                exercise_title = exercise_title.rstrip("*").strip()

            current_exercise = Exercise(
                exercise_id=f"Exercise {exercise_num}",
                title=exercise_title or None,
                instructions="",
            )
            current_content = []
            continue

        # Accumulate content
        if in_preamble and not current_exercise:
            preamble_lines.append(line)
        elif current_exercise:
            current_content.append(line)

    # Finalize last exercise
    if current_exercise:
        finalize_exercise()

    # Clean up preamble
    preamble = "\n".join(preamble_lines).strip() or None

    return Route(
        title=title,
        preamble=preamble,
        exercises=exercises,
    )


def parse_route_file(path: Path | str) -> Route:
    """
    Parse a route markdown file from disk.

    Args:
        path: Path to the route markdown file

    Returns:
        Route object with parsed exercises
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    return parse_route(content)


def get_exercise_ids(route: Route) -> list[str]:
    """
    Get all exercise IDs from a route.

    Args:
        route: Parsed route object

    Returns:
        List of exercise IDs in order
    """
    return [ex.exercise_id for ex in route.exercises]


def format_route_for_prompt(route: Route) -> str:
    """
    Format a route for inclusion in the grading prompt.

    Args:
        route: Parsed route object

    Returns:
        Formatted string representation of the route
    """
    parts = []

    if route.title:
        parts.append(f"# {route.title}\n")

    if route.preamble:
        parts.append(f"{route.preamble}\n")

    for exercise in route.exercises:
        parts.append(f"## {exercise.exercise_id}")
        if exercise.title:
            parts.append(f": {exercise.title}")
        parts.append("\n")
        parts.append(exercise.instructions)
        parts.append("\n")

    return "\n".join(parts)
