"""Parse route markdown files into structured exercise specifications."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union

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
    #   # **Exercise 1: Title**
    exercise_pattern = re.compile(
        r"^(#{1,4})\s+\*{0,2}(?:Exercise\s+)?(\d+[a-z]?(?:\.\d+)?)\*{0,2}[\.\\\s:\-]*\*{0,2}\s*(.*)$",
        re.IGNORECASE,
    )

    # Pattern for Part-based exercises (e.g., "## **Part A — Title**")
    part_pattern = re.compile(
        r"^(#{1,4})\s+\*{0,2}Part\s+([A-Za-z])\s*[\—\-–:\.]*\s*\*{0,2}\s*(.*)$",
        re.IGNORECASE,
    )

    # Keywords that indicate an optional exercise
    optional_keywords = re.compile(
        r"\b(optional|bonus|dyno|extra\s+practice|anchor\s+challenge)\b",
        re.IGNORECASE,
    )

    # Pattern for standalone optional sections (e.g., "### **Optional Hold (extra practice)**")
    optional_section_pattern = re.compile(
        r"^(#{1,4})\s+\*{0,2}(Optional\s+Hold|The\s+Dyno|Bonus\s+Hold|Anchor\s+Challenge)[^\*]*\*{0,2}\s*(.*)$",
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

        # Check for exercise heading (e.g., "## Exercise 1")
        exercise_match = exercise_pattern.match(line)
        # Check for part heading (e.g., "## **Part A — Title**")
        part_match = part_pattern.match(line)
        # Check for standalone optional section (e.g., "### **Optional Hold**")
        optional_section_match = optional_section_pattern.match(line)

        if exercise_match or part_match or optional_section_match:
            in_preamble = False

            # Finalize previous exercise
            if current_exercise:
                finalize_exercise()
            elif preamble_lines:
                # Only keep preamble if we haven't started exercises
                pass

            if exercise_match:
                heading_level = len(exercise_match.group(1))
                exercise_num = exercise_match.group(2)
                exercise_title = exercise_match.group(3).strip() or None
                exercise_id = f"Exercise {exercise_num}"
                # Check if optional based on title/header keywords
                full_header = line + " " + (exercise_title or "")
                is_optional = bool(optional_keywords.search(full_header))
            elif part_match:
                heading_level = len(part_match.group(1))
                part_letter = part_match.group(2).upper()
                exercise_title = part_match.group(3).strip() or None
                exercise_id = f"Part {part_letter}"
                # Check if optional based on title/header keywords
                full_header = line + " " + (exercise_title or "")
                is_optional = bool(optional_keywords.search(full_header))
            else:  # optional_section_match
                heading_level = len(optional_section_match.group(1))
                section_name = optional_section_match.group(2).strip()
                exercise_title = optional_section_match.group(3).strip() or section_name
                exercise_id = section_name.replace(" ", "_")
                is_optional = True  # Always optional

            # Clean up title (remove trailing ** from bold markdown)
            if exercise_title:
                exercise_title = exercise_title.rstrip("*").strip()

            current_exercise = Exercise(
                exercise_id=exercise_id,
                title=exercise_title or None,
                instructions="",
                optional=is_optional,
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
        optional_marker = " [OPTIONAL]" if exercise.optional else ""
        parts.append(f"## {exercise.exercise_id}{optional_marker}")
        if exercise.title:
            parts.append(f": {exercise.title}")
        parts.append("\n")
        parts.append(exercise.instructions)
        parts.append("\n")

    return "\n".join(parts)
