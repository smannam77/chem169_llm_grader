"""Convert Jupyter notebooks to a compact grading view."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import nbformat


@dataclass
class CellView:
    """Compact representation of a notebook cell for grading."""

    index: int
    cell_type: str  # 'code', 'markdown', 'raw'
    source: str
    outputs: list[str]
    execution_count: int | None = None


@dataclass
class NotebookView:
    """Compact representation of a notebook for grading."""

    cells: list[CellView]
    metadata: dict


@dataclass
class SolutionExercise:
    """An exercise extracted from a solution notebook."""

    exercise_id: str
    title: str | None
    cells: list[CellView]  # Cells belonging to this exercise
    exercise_type: str  # 'code' or 'writing'


def truncate_text(text: str, max_length: int = 15000) -> str:
    """Truncate text to max length with indicator.

    Default is 15000 chars to handle students who put multiple
    exercises in a single cell.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 20] + "\n... [truncated]"


def extract_output_text(output: dict) -> str:
    """Extract readable text from a cell output."""
    output_type = output.get("output_type", "")

    if output_type == "stream":
        return output.get("text", "")

    if output_type == "execute_result" or output_type == "display_data":
        data = output.get("data", {})
        # Prefer text/plain, then text/html
        if "text/plain" in data:
            text = data["text/plain"]
            if isinstance(text, list):
                text = "".join(text)
            return text
        if "text/html" in data:
            return "[HTML output]"
        if "image/png" in data or "image/jpeg" in data:
            return "[Image output]"
        return "[Data output]"

    if output_type == "error":
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        return f"[Error: {ename}: {evalue}]"

    return ""


def parse_notebook(content: str | dict) -> NotebookView:
    """
    Parse notebook content into a NotebookView.

    Args:
        content: Either a JSON string or a dict representing the notebook

    Returns:
        NotebookView with parsed cells
    """
    if isinstance(content, str):
        nb = nbformat.reads(content, as_version=4)
    else:
        nb = nbformat.from_dict(content)

    cells = []
    for idx, cell in enumerate(nb.cells):
        cell_type = cell.cell_type
        source = cell.source
        if isinstance(source, list):
            source = "".join(source)

        outputs = []
        execution_count = None

        if cell_type == "code":
            execution_count = cell.get("execution_count")
            for output in cell.get("outputs", []):
                output_text = extract_output_text(output)
                if output_text:
                    outputs.append(truncate_text(output_text))

        cells.append(
            CellView(
                index=idx,
                cell_type=cell_type,
                source=truncate_text(source),
                outputs=outputs,
                execution_count=execution_count,
            )
        )

    return NotebookView(
        cells=cells,
        metadata=dict(nb.metadata) if nb.metadata else {},
    )


def parse_notebook_file(path: Path | str) -> NotebookView:
    """
    Parse a notebook file from disk.

    Args:
        path: Path to the .ipynb file

    Returns:
        NotebookView with parsed cells
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    return parse_notebook(content)


def format_notebook_for_prompt(
    view: NotebookView,
    include_markdown: bool = True,
    max_output_lines: int = 50,
) -> str:
    """
    Format a notebook view for inclusion in the grading prompt.

    Args:
        view: Parsed notebook view
        include_markdown: Whether to include markdown cells
        max_output_lines: Max lines of output to include per cell

    Returns:
        Formatted string representation of the notebook
    """
    parts = []
    parts.append("=" * 60)
    parts.append("STUDENT NOTEBOOK")
    parts.append("=" * 60)
    parts.append("")

    for cell in view.cells:
        if cell.cell_type == "markdown" and not include_markdown:
            continue

        # Cell header
        cell_header = f"[Cell {cell.index}] ({cell.cell_type})"
        if cell.execution_count is not None:
            cell_header += f" In[{cell.execution_count}]"
        parts.append(cell_header)
        parts.append("-" * 40)

        # Source
        parts.append(cell.source)

        # Outputs (code cells only)
        if cell.outputs:
            parts.append("")
            parts.append(">>> Output:")
            for output in cell.outputs:
                output_lines = output.split("\n")
                if len(output_lines) > max_output_lines:
                    output_lines = output_lines[:max_output_lines]
                    output_lines.append("... [output truncated]")
                parts.append("\n".join(output_lines))

        parts.append("")

    return "\n".join(parts)


def get_cell_excerpt(view: NotebookView, cell_index: int, max_length: int = 200) -> str:
    """
    Get a short excerpt from a specific cell.

    Args:
        view: Notebook view
        cell_index: Index of the cell
        max_length: Maximum length of excerpt

    Returns:
        Short excerpt from the cell
    """
    if cell_index < 0 or cell_index >= len(view.cells):
        return ""

    cell = view.cells[cell_index]
    text = cell.source

    # Also include first output if it's a code cell
    if cell.cell_type == "code" and cell.outputs:
        text += "\n>>> " + cell.outputs[0][:100]

    return truncate_text(text, max_length)


# Exercise header pattern - flexible to accept many formats:
# - ## Exercise 1, ### Exercise 1, # Exercise 1 (any markdown header)
# - Exercise 1. Title, Exercise 1: Title, Exercise 1 - Title
# - **Exercise 1**, Exercise 1 (plain text)
# - Ex 1, Ex. 1 (abbreviated)
EXERCISE_PATTERN = re.compile(
    r"^(?:#{1,6}\s+)?(?:\*\*)?(?:Exercise|Ex\.?)\s+(\d+[a-z]?)(?:\*\*)?(?:\s*[:\.\-\—]\s*(.*))?$",
    re.IGNORECASE | re.MULTILINE
)


def extract_exercises_from_notebook(view: NotebookView) -> list[SolutionExercise]:
    """
    Extract exercises from a solution notebook.

    Exercises are identified by markdown cells with headers like:
    - ## Exercise 1
    - ## Exercise 2a
    - ## Exercise 1: Title Here

    Args:
        view: Parsed notebook view

    Returns:
        List of SolutionExercise objects
    """
    exercises: list[SolutionExercise] = []
    current_exercise: dict | None = None

    for cell in view.cells:
        # Check if this is an exercise header (markdown cell)
        if cell.cell_type == "markdown":
            match = EXERCISE_PATTERN.search(cell.source)
            if match:
                # Save previous exercise if exists
                if current_exercise is not None:
                    exercises.append(_finalize_exercise(current_exercise))

                # Start new exercise
                exercise_num = match.group(1)
                title = match.group(2).strip() if match.group(2) else None
                current_exercise = {
                    "exercise_id": f"Exercise {exercise_num}",
                    "title": title,
                    "cells": [cell],  # Include the header cell
                }
                continue

        # Add cell to current exercise if we're in one
        if current_exercise is not None:
            current_exercise["cells"].append(cell)

    # Don't forget the last exercise
    if current_exercise is not None:
        exercises.append(_finalize_exercise(current_exercise))

    return exercises


def _finalize_exercise(exercise_data: dict) -> SolutionExercise:
    """Convert exercise data dict to SolutionExercise with type detection."""
    cells = exercise_data["cells"]

    # Determine exercise type based on cell composition
    code_cells = sum(1 for c in cells if c.cell_type == "code")
    markdown_cells = sum(1 for c in cells if c.cell_type == "markdown")

    # If mostly markdown (excluding header), it's a writing exercise
    # Header is always markdown, so subtract 1
    if code_cells == 0 or (markdown_cells - 1) > code_cells:
        exercise_type = "writing"
    else:
        exercise_type = "code"

    return SolutionExercise(
        exercise_id=exercise_data["exercise_id"],
        title=exercise_data["title"],
        cells=cells,
        exercise_type=exercise_type,
    )


def format_solution_for_prompt(
    exercises: list[SolutionExercise],
    max_output_lines: int = 50,
) -> str:
    """
    Format solution exercises for inclusion in the grading prompt.

    Args:
        exercises: List of solution exercises
        max_output_lines: Max lines of output to include per cell

    Returns:
        Formatted string representation of the solution
    """
    parts = []
    parts.append("=" * 60)
    parts.append("SOLUTION NOTEBOOK")
    parts.append("=" * 60)
    parts.append("")

    for ex in exercises:
        # Exercise header
        title_str = f": {ex.title}" if ex.title else ""
        parts.append(f"### {ex.exercise_id}{title_str} [{ex.exercise_type.upper()}]")
        parts.append("-" * 40)

        for cell in ex.cells:
            # Cell header
            cell_header = f"[Cell {cell.index}] ({cell.cell_type})"
            if cell.execution_count is not None:
                cell_header += f" In[{cell.execution_count}]"
            parts.append(cell_header)

            # Source
            parts.append(cell.source)

            # Outputs (code cells only)
            if cell.outputs:
                parts.append("")
                parts.append(">>> Expected Output:")
                for output in cell.outputs:
                    output_lines = output.split("\n")
                    if len(output_lines) > max_output_lines:
                        output_lines = output_lines[:max_output_lines]
                        output_lines.append("... [output truncated]")
                    parts.append("\n".join(output_lines))

            parts.append("")

        parts.append("")

    return "\n".join(parts)


def get_solution_exercise_ids(exercises: list[SolutionExercise]) -> list[str]:
    """Get list of exercise IDs from solution exercises."""
    return [ex.exercise_id for ex in exercises]
