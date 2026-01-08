"""Tests for route parsing."""

import pytest

from graderbot.route_parser import (
    format_route_for_prompt,
    get_exercise_ids,
    parse_route,
)


class TestParseRoute:
    """Tests for parse_route function."""

    def test_parse_simple_route(self):
        """Test parsing a simple route with exercises."""
        content = """# Chemistry Lab 1

This is the preamble with instructions.

## Exercise 1: Calculate Molarity

Calculate the molarity of a NaCl solution.

## Exercise 2: Plot Results

Create a plot of concentration vs. absorbance.
"""
        route = parse_route(content)

        assert route.title == "Chemistry Lab 1"
        assert "preamble" in route.preamble.lower()
        assert len(route.exercises) == 2
        assert route.exercises[0].exercise_id == "Exercise 1"
        assert route.exercises[0].title == "Calculate Molarity"
        assert "molarity" in route.exercises[0].instructions.lower()
        assert route.exercises[1].exercise_id == "Exercise 2"

    def test_parse_numbered_exercises(self):
        """Test parsing exercises with various numbering."""
        content = """## Exercise 1

First exercise.

## Exercise 2a

Sub-exercise a.

## Exercise 2b

Sub-exercise b.

## Exercise 3

Third exercise.
"""
        route = parse_route(content)

        assert len(route.exercises) == 4
        assert route.exercises[0].exercise_id == "Exercise 1"
        assert route.exercises[1].exercise_id == "Exercise 2a"
        assert route.exercises[2].exercise_id == "Exercise 2b"
        assert route.exercises[3].exercise_id == "Exercise 3"

    def test_parse_no_title(self):
        """Test parsing route without a title."""
        content = """## Exercise 1

Do this task.
"""
        route = parse_route(content)

        assert route.title is None
        assert len(route.exercises) == 1

    def test_parse_exercise_without_colon(self):
        """Test parsing exercise headings without colons."""
        content = """## Exercise 1 - First Task

Instructions here.

## Exercise 2

More instructions.
"""
        route = parse_route(content)

        assert len(route.exercises) == 2
        assert route.exercises[0].exercise_id == "Exercise 1"
        assert route.exercises[0].title == "First Task"

    def test_empty_content(self):
        """Test parsing empty content."""
        route = parse_route("")
        assert route.title is None
        assert route.exercises == []


class TestGetExerciseIds:
    """Tests for get_exercise_ids function."""

    def test_get_ids(self):
        """Test extracting exercise IDs."""
        content = """## Exercise 1
A
## Exercise 2
B
## Exercise 3
C
"""
        route = parse_route(content)
        ids = get_exercise_ids(route)

        assert ids == ["Exercise 1", "Exercise 2", "Exercise 3"]


class TestFormatRouteForPrompt:
    """Tests for format_route_for_prompt function."""

    def test_format_includes_all_parts(self):
        """Test that formatted route includes title and exercises."""
        content = """# Test Route

Preamble text.

## Exercise 1: Task One

Do this.

## Exercise 2

Do that.
"""
        route = parse_route(content)
        formatted = format_route_for_prompt(route)

        assert "Test Route" in formatted
        assert "Preamble text" in formatted
        assert "Exercise 1" in formatted
        assert "Task One" in formatted
        assert "Do this" in formatted
        assert "Exercise 2" in formatted
