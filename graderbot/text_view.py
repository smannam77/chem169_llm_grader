"""Text file viewer for grading plain text submissions."""

from __future__ import annotations

from pathlib import Path


def extract_text_from_docx(file_path: str) -> str:
    """Extract text content from a .docx file."""
    try:
        import docx
        doc = docx.Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs]
        return "\n".join(paragraphs)
    except Exception as e:
        return f"ERROR: Could not extract text from docx: {e}"


def read_text_file(file_path: str) -> str:
    """Read text from a file, handling both .txt and .docx formats."""
    path = Path(file_path)
    if path.suffix.lower() == '.docx':
        return extract_text_from_docx(file_path)
    else:
        return path.read_text(encoding='utf-8', errors='replace')


def render_text_submission(deliverable_path: str, logbook_path: str | None = None) -> str:
    """
    Render text submission files for LLM grading.

    Args:
        deliverable_path: Path to the deliverable.txt file
        logbook_path: Optional path to the logbook.txt file

    Returns:
        Formatted string containing the submission content
    """
    output_parts = []

    # Read deliverable
    deliverable = Path(deliverable_path)
    if deliverable.exists():
        output_parts.append("=" * 60)
        output_parts.append("DELIVERABLE FILE")
        output_parts.append("=" * 60)
        output_parts.append(read_text_file(deliverable_path))
    else:
        output_parts.append(f"ERROR: Deliverable file not found: {deliverable_path}")

    # Read logbook if provided
    if logbook_path:
        logbook = Path(logbook_path)
        if logbook.exists():
            output_parts.append("")
            output_parts.append("=" * 60)
            output_parts.append("LOGBOOK FILE")
            output_parts.append("=" * 60)
            output_parts.append(read_text_file(logbook_path))
        else:
            output_parts.append(f"\nNOTE: Logbook file not found: {logbook_path}")

    return "\n".join(output_parts)


def find_submission_pair(submissions_dir: str, student_pattern: str) -> tuple[str | None, str | None]:
    """
    Find deliverable and logbook files for a student.

    Args:
        submissions_dir: Directory containing submissions
        student_pattern: Pattern to match student name (e.g., "Smith_John")

    Returns:
        Tuple of (deliverable_path, logbook_path), either may be None
    """
    submissions = Path(submissions_dir)
    deliverable = None
    logbook = None

    for f in submissions.iterdir():
        if not f.is_file():
            continue
        name_lower = f.name.lower()
        pattern_lower = student_pattern.lower()

        # Check if this file belongs to the student
        if pattern_lower in name_lower or name_lower.startswith(pattern_lower.split('_')[0]):
            if 'deliverable' in name_lower or 'text_submission' in name_lower or 'submission_file' in name_lower or '_code' in name_lower:
                deliverable = str(f)
            elif 'logbook' in name_lower:
                logbook = str(f)

    return deliverable, logbook


def list_text_submissions(submissions_dir: str) -> list[dict]:
    """
    List all text submissions in a directory, grouping deliverable and logbook.

    Args:
        submissions_dir: Directory containing submissions

    Returns:
        List of dicts with 'student', 'deliverable', 'logbook' keys
    """
    submissions = Path(submissions_dir)

    # Group files by student
    students = {}

    for f in submissions.iterdir():
        if not f.is_file() or f.suffix.lower() not in ('.txt', '.docx'):
            continue

        name = f.stem
        name_lower = name.lower()

        # Extract student identifier (everything before RID or deliverable/logbook)
        import re
        # Try to extract student name from filename
        # Patterns: LastName_FirstName_RID_XXX_deliverable.txt
        #           LastName_FirstName_deliverable_RID_XXX.txt
        match = re.match(r'^([A-Za-z]+_[A-Za-z]+)', name, re.IGNORECASE)
        if match:
            student_key = match.group(1).lower()
        else:
            # Fallback: use first part before underscore
            student_key = name.split('_')[0].lower()

        if student_key not in students:
            students[student_key] = {'student': student_key, 'deliverable': None, 'logbook': None}

        if 'deliverable' in name_lower or 'text_submission' in name_lower or 'submission_file' in name_lower or '_code' in name_lower:
            students[student_key]['deliverable'] = str(f)
        elif 'logbook' in name_lower:
            students[student_key]['logbook'] = str(f)

    return list(students.values())
