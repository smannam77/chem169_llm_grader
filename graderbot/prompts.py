"""Prompt templates for LLM-based grading."""

import json

from .schema import Exercise, GradingResult, Route

SYSTEM_PROMPT = """You are an expert teaching assistant grading student Jupyter notebooks for a university chemistry course (Chem 169/269 "routes").

Your task is to evaluate student work against a provided assignment specification and produce structured grading feedback.

## Grading Rubric

Use exactly these three rating levels:

**EXCELLENT**: The solution is correct, clearly presented, and reproducible. The student fully addresses the prompt with proper explanations and clean code/analysis.

**OK**: The solution is mostly correct but has minor issues: incomplete explanations, minor bugs, sloppy presentation, or doesn't fully address all parts of the prompt.

**NEEDS_WORK**: The solution is incorrect, missing, or does not address the prompt. This includes: fundamental errors, evidence of not actually running the code, copy/paste answers without understanding, or missing required components.

## Critical Requirements

1. **Evidence-Based Grading**: Every rating MUST be supported by specific evidence from the notebook.
   - Cite exact cell indices (e.g., "Cell 3")
   - Include short, relevant excerpts from the student's code or output
   - Never make claims without pointing to specific cells

2. **Be Specific**: In your rationale, explain exactly what is correct or incorrect.
   - Good: "Cell 5 correctly implements the Beer-Lambert equation (A = εlc) and calculates absorbance as 0.45"
   - Bad: "The calculation looks correct"

3. **Check Execution**: Note if cells appear unexecuted (no output, execution_count is None).

4. **Flag Issues**: Use flags for special concerns:
   - "not_executed": Code cells have no output/execution count
   - "possible_plagiarism": Suspiciously sophisticated code without explanations
   - "incomplete": Work appears unfinished
   - "copy_paste": Appears to be copied answers without understanding

## Output Format

You must respond with ONLY valid JSON matching this exact schema:

```json
{
  "schema_version": "1.0",
  "route_id": "string or null",
  "student_id": "string or null",
  "exercises": [
    {
      "exercise_id": "Exercise 1",
      "rating": "EXCELLENT | OK | NEEDS_WORK",
      "rationale": "Brief explanation (max 3 sentences)",
      "evidence": [
        {"cell_index": 0, "excerpt": "relevant code or output snippet"}
      ],
      "missing_or_wrong": ["list of specific issues"],
      "flags": ["optional flags"]
    }
  ],
  "overall_summary": "Overall assessment (max 5 sentences)"
}
```

Do not include any text before or after the JSON. The response must be parseable JSON."""


SOLUTION_SYSTEM_PROMPT = """You are an expert teaching assistant grading student Jupyter notebooks by comparing them against a solution notebook.

Your task is to evaluate student work against a provided solution and produce structured grading feedback.

## Grading Rubric

Use exactly these three rating levels:

**EXCELLENT**: The student's output matches the expected solution output. The code runs correctly and produces equivalent results (values may differ slightly due to floating point, but the approach and result type must match).

**OK**: The student's output is partially correct. The approach is reasonable but results differ, there are minor bugs, or the code runs with small issues. Award partial credit when the student demonstrates understanding even if the final output isn't perfect.

**NEEDS_WORK**: The student's output is incorrect, missing, or fundamentally wrong. This includes: code that doesn't run, completely wrong approach, missing required components, or unexecuted cells.

## Critical Requirements

1. **Compare Outputs**: For CODE exercises, compare the student's output to the expected output in the solution.
   - Equivalent numerical results (within reasonable tolerance) = EXCELLENT
   - Correct approach but wrong numbers = OK
   - Wrong approach or no output = NEEDS_WORK

2. **Writing Exercises**: For WRITING exercises (mostly markdown, explanatory text), you should:
   - Give a rating of OK by default
   - Add the "manual_review" flag
   - Note in the rationale that this requires human review
   - Do NOT attempt to deeply grade the content - the instructor will review

3. **Evidence-Based Grading**: Every rating MUST be supported by specific evidence from the notebook.
   - Cite exact cell indices (e.g., "Cell 3")
   - Include short, relevant excerpts from the student's code or output
   - Never make claims without pointing to specific cells

4. **Partial Credit**: Award OK (partial credit) when:
   - Code runs but produces slightly different output
   - Approach is correct but implementation has minor bugs
   - Student shows understanding even if result is imperfect

5. **Check Execution**: Note if cells appear unexecuted (no output, execution_count is None).

6. **Flag Issues**: Use flags for special concerns:
   - "not_executed": Code cells have no output/execution count
   - "manual_review": Writing exercises that need human review
   - "possible_plagiarism": Suspiciously sophisticated code without explanations
   - "incomplete": Work appears unfinished

## Output Format

You must respond with ONLY valid JSON matching this exact schema:

```json
{
  "schema_version": "1.0",
  "route_id": "string or null",
  "student_id": "string or null",
  "exercises": [
    {
      "exercise_id": "Exercise 1",
      "rating": "EXCELLENT | OK | NEEDS_WORK",
      "rationale": "Brief explanation comparing to solution (max 3 sentences)",
      "evidence": [
        {"cell_index": 0, "excerpt": "relevant code or output snippet"}
      ],
      "missing_or_wrong": ["list of specific differences from solution"],
      "flags": ["optional flags like 'manual_review'"]
    }
  ],
  "overall_summary": "Overall assessment (max 5 sentences)"
}
```

Do not include any text before or after the JSON. The response must be parseable JSON."""


def build_grading_prompt(
    route_text: str,
    notebook_text: str,
    exercise_ids: list[str],
    route_id: str | None = None,
    student_id: str | None = None,
) -> str:
    """
    Build the user prompt for grading.

    Args:
        route_text: Formatted route/assignment specification
        notebook_text: Formatted notebook grading view
        exercise_ids: List of exercise IDs to grade
        route_id: Optional route identifier
        student_id: Optional student identifier

    Returns:
        Complete user prompt for the LLM
    """
    exercises_list = "\n".join(f"- {eid}" for eid in exercise_ids)

    prompt = f"""## Assignment Specification

{route_text}

## Student Submission

{notebook_text}

## Grading Task

Grade the student's notebook against the assignment specification above.

Exercises to grade:
{exercises_list}

{f'Route ID: {route_id}' if route_id else ''}
{f'Student ID: {student_id}' if student_id else ''}

For each exercise:
1. Find the relevant cells in the student's notebook
2. Evaluate correctness, completeness, and presentation
3. Assign a rating (EXCELLENT, OK, or NEEDS_WORK)
4. Provide specific evidence with cell indices and excerpts
5. List any missing or incorrect elements

Remember:
- You MUST cite specific cell indices for every claim
- Include short excerpts as evidence
- Be constructive but accurate in your assessment

Respond with ONLY valid JSON matching the schema described in your instructions."""

    return prompt


def build_repair_prompt(invalid_json: str, error_message: str) -> str:
    """
    Build a prompt to repair invalid JSON output.

    Args:
        invalid_json: The invalid JSON string from the LLM
        error_message: The validation error message

    Returns:
        Prompt asking the LLM to fix the JSON
    """
    return f"""The previous JSON response was invalid.

Error: {error_message}

Invalid response:
```
{invalid_json[:2000]}
```

Please provide a corrected JSON response that:
1. Is valid JSON (properly escaped strings, no trailing commas)
2. Matches the required schema exactly
3. Contains all required fields

Respond with ONLY the corrected JSON, no other text."""


def get_schema_json() -> str:
    """Get the JSON schema for GradingResult."""
    return json.dumps(GradingResult.model_json_schema(), indent=2)


def build_solution_grading_prompt(
    solution_text: str,
    notebook_text: str,
    exercise_ids: list[str],
    exercise_types: dict[str, str],  # Maps exercise_id to 'code' or 'writing'
    route_id: str | None = None,
    student_id: str | None = None,
) -> str:
    """
    Build the user prompt for solution-based grading.

    Args:
        solution_text: Formatted solution notebook
        notebook_text: Formatted student notebook grading view
        exercise_ids: List of exercise IDs to grade
        exercise_types: Dict mapping exercise_id to type ('code' or 'writing')
        route_id: Optional route identifier
        student_id: Optional student identifier

    Returns:
        Complete user prompt for the LLM
    """
    exercises_list = []
    for eid in exercise_ids:
        etype = exercise_types.get(eid, "code")
        exercises_list.append(f"- {eid} [{etype.upper()}]")
    exercises_str = "\n".join(exercises_list)

    prompt = f"""## Solution Notebook (Expected Outputs)

{solution_text}

## Student Submission

{notebook_text}

## Grading Task

Compare the student's notebook against the solution notebook above.

Exercises to grade:
{exercises_str}

{f'Route ID: {route_id}' if route_id else ''}
{f'Student ID: {student_id}' if student_id else ''}

For each exercise:
1. Find the corresponding cells in the student's notebook
2. Compare outputs to the expected outputs in the solution
3. For CODE exercises: Check if outputs match or are equivalent
4. For WRITING exercises: Flag as "manual_review" and give rating OK
5. Assign a rating (EXCELLENT, OK, or NEEDS_WORK)
6. Provide specific evidence with cell indices and excerpts

Remember:
- You MUST cite specific cell indices for every claim
- Include short excerpts as evidence
- Award partial credit (OK) for correct approach with minor issues
- WRITING exercises should always get "manual_review" flag

Respond with ONLY valid JSON matching the schema described in your instructions."""

    return prompt
