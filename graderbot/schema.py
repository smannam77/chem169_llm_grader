"""Pydantic schemas for grading output."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Rating(str, Enum):
    """Three-level grading rating."""

    EXCELLENT = "EXCELLENT"
    OK = "OK"
    NEEDS_WORK = "NEEDS_WORK"


class Evidence(BaseModel):
    """Evidence from a specific cell supporting the grading decision."""

    cell_index: int = Field(
        ...,
        description="Zero-based index of the notebook cell",
        ge=0,
    )
    excerpt: str = Field(
        ...,
        description="Short excerpt from the cell (code or output)",
        max_length=1500,
    )


class ExerciseGrade(BaseModel):
    """Grading result for a single exercise."""

    exercise_id: str = Field(
        ...,
        description="Exercise identifier (e.g., 'Exercise 1', 'Exercise 2a')",
    )
    rating: Rating = Field(
        ...,
        description="Three-level rating: EXCELLENT, OK, or NEEDS_WORK",
    )
    rationale: str = Field(
        ...,
        description="Brief explanation of the rating (max 3 sentences)",
        max_length=500,
    )
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="List of cell excerpts supporting the decision",
    )
    missing_or_wrong: list[str] = Field(
        default_factory=list,
        description="List of missing or incorrect elements",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Special flags: 'not_executed', 'possible_plagiarism', 'incomplete', 'copy_paste', 'manual_review' (for writing exercises)",
    )


class GradingResult(BaseModel):
    """Complete grading result for a student notebook."""

    schema_version: str = Field(
        default="1.0",
        description="Version of the grading schema",
    )
    route_id: Optional[str] = Field(
        default=None,
        description="Identifier for the route/assignment",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Student identifier (if available)",
    )
    exercises: list[ExerciseGrade] = Field(
        ...,
        description="Grading results for each exercise",
    )
    overall_summary: str = Field(
        ...,
        description="Overall assessment summary (max 5 sentences)",
        max_length=1000,
    )


# Schema for exercises parsed from route markdown
class Exercise(BaseModel):
    """An exercise parsed from the route specification."""

    exercise_id: str = Field(
        ...,
        description="Exercise identifier",
    )
    title: Optional[str] = Field(
        default=None,
        description="Exercise title if present",
    )
    instructions: str = Field(
        ...,
        description="Full instructions/prompt for the exercise",
    )
    subsections: list["Exercise"] = Field(
        default_factory=list,
        description="Sub-exercises (e.g., 1a, 1b)",
    )


class Route(BaseModel):
    """Parsed route/assignment specification."""

    title: Optional[str] = Field(
        default=None,
        description="Route title",
    )
    preamble: Optional[str] = Field(
        default=None,
        description="Introductory text before exercises",
    )
    exercises: list[Exercise] = Field(
        ...,
        description="List of exercises in the route",
    )
