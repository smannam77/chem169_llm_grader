"""Tests for schema validation."""

import json

import pytest
from pydantic import ValidationError

from graderbot.schema import (
    Evidence,
    ExerciseGrade,
    GradingResult,
    Rating,
)


class TestRating:
    """Tests for Rating enum."""

    def test_valid_ratings(self):
        """Test that all valid ratings work."""
        assert Rating.EXCELLENT.value == "EXCELLENT"
        assert Rating.OK.value == "OK"
        assert Rating.NEEDS_WORK.value == "NEEDS_WORK"

    def test_rating_from_string(self):
        """Test creating rating from string."""
        assert Rating("EXCELLENT") == Rating.EXCELLENT
        assert Rating("OK") == Rating.OK
        assert Rating("NEEDS_WORK") == Rating.NEEDS_WORK


class TestEvidence:
    """Tests for Evidence model."""

    def test_valid_evidence(self):
        """Test creating valid evidence."""
        evidence = Evidence(
            cell_index=5,
            excerpt="x = 42",
        )
        assert evidence.cell_index == 5
        assert evidence.excerpt == "x = 42"

    def test_negative_cell_index_fails(self):
        """Test that negative cell index fails validation."""
        with pytest.raises(ValidationError):
            Evidence(cell_index=-1, excerpt="test")


class TestExerciseGrade:
    """Tests for ExerciseGrade model."""

    def test_valid_exercise_grade(self):
        """Test creating a valid exercise grade."""
        grade = ExerciseGrade(
            exercise_id="Exercise 1",
            rating=Rating.EXCELLENT,
            rationale="Student correctly solved the problem.",
            evidence=[
                Evidence(cell_index=2, excerpt="result = 42")
            ],
            missing_or_wrong=[],
            flags=[],
        )

        assert grade.exercise_id == "Exercise 1"
        assert grade.rating == Rating.EXCELLENT
        assert len(grade.evidence) == 1

    def test_minimal_exercise_grade(self):
        """Test exercise grade with only required fields."""
        grade = ExerciseGrade(
            exercise_id="Exercise 1",
            rating=Rating.OK,
            rationale="Mostly correct.",
        )

        assert grade.exercise_id == "Exercise 1"
        assert grade.evidence == []
        assert grade.missing_or_wrong == []
        assert grade.flags == []

    def test_with_flags(self):
        """Test exercise grade with flags."""
        grade = ExerciseGrade(
            exercise_id="Exercise 1",
            rating=Rating.NEEDS_WORK,
            rationale="Code was not executed.",
            flags=["not_executed", "incomplete"],
        )

        assert "not_executed" in grade.flags
        assert "incomplete" in grade.flags


class TestGradingResult:
    """Tests for GradingResult model."""

    def test_valid_grading_result(self):
        """Test creating a valid grading result."""
        result = GradingResult(
            schema_version="1.0",
            route_id="chem169-lab1",
            student_id="student123",
            exercises=[
                ExerciseGrade(
                    exercise_id="Exercise 1",
                    rating=Rating.EXCELLENT,
                    rationale="Perfect solution.",
                    evidence=[Evidence(cell_index=1, excerpt="correct code")],
                ),
                ExerciseGrade(
                    exercise_id="Exercise 2",
                    rating=Rating.OK,
                    rationale="Minor issues.",
                ),
            ],
            overall_summary="Good work overall.",
        )

        assert result.schema_version == "1.0"
        assert result.route_id == "chem169-lab1"
        assert len(result.exercises) == 2

    def test_json_serialization(self):
        """Test that grading result serializes to valid JSON."""
        result = GradingResult(
            exercises=[
                ExerciseGrade(
                    exercise_id="Exercise 1",
                    rating=Rating.EXCELLENT,
                    rationale="Good.",
                ),
            ],
            overall_summary="Well done.",
        )

        json_str = result.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "1.0"
        assert parsed["exercises"][0]["rating"] == "EXCELLENT"

    def test_json_deserialization(self):
        """Test that JSON deserializes to valid grading result."""
        json_data = {
            "schema_version": "1.0",
            "exercises": [
                {
                    "exercise_id": "Exercise 1",
                    "rating": "OK",
                    "rationale": "Acceptable.",
                    "evidence": [{"cell_index": 0, "excerpt": "code"}],
                    "missing_or_wrong": ["no plot title"],
                    "flags": [],
                }
            ],
            "overall_summary": "Needs improvement.",
        }

        result = GradingResult.model_validate(json_data)

        assert result.exercises[0].rating == Rating.OK
        assert result.exercises[0].missing_or_wrong == ["no plot title"]

    def test_optional_fields(self):
        """Test that optional fields can be None."""
        result = GradingResult(
            exercises=[],
            overall_summary="Empty submission.",
        )

        assert result.route_id is None
        assert result.student_id is None
