"""FastAPI web interface for GraderBot."""

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Annotated
from zipfile import ZipFile

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .grader import (
    GradingError,
    SolutionGradingContext,
    grade_notebook_with_solution,
)
from .llm_client import create_client
from .notebook_view import (
    extract_exercises_from_notebook,
    format_notebook_for_prompt,
    format_solution_for_prompt,
    get_solution_exercise_ids,
    parse_notebook,
)
from .schema import GradingResult

# Load environment variables
load_dotenv()

app = FastAPI(
    title="GraderBot",
    description="LLM-powered grading assistant for Jupyter notebooks",
    version="0.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def prepare_solution_grading_context_from_content(
    solution_content: str,
    notebook_content: str,
    route_id: str | None = None,
    student_id: str | None = None,
) -> SolutionGradingContext:
    """
    Prepare grading context from notebook content strings.

    Args:
        solution_content: Solution notebook JSON string
        notebook_content: Student notebook JSON string
        route_id: Optional route identifier
        student_id: Optional student identifier

    Returns:
        SolutionGradingContext ready for grading
    """
    solution_notebook = parse_notebook(solution_content)
    student_notebook = parse_notebook(notebook_content)

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


def generate_text_report(result: GradingResult) -> str:
    """Generate a readable text report from grading result."""
    lines = []
    lines.append("=" * 60)
    lines.append("GRADING REPORT")
    lines.append("=" * 60)
    lines.append("")

    if result.student_id:
        lines.append(f"Student: {result.student_id}")
    if result.route_id:
        lines.append(f"Assignment: {result.route_id}")
    if result.student_id or result.route_id:
        lines.append("")

    lines.append("-" * 60)
    lines.append("OVERALL SUMMARY")
    lines.append("-" * 60)
    lines.append(result.overall_summary or "No summary available.")
    lines.append("")

    lines.append("-" * 60)
    lines.append("EXERCISE GRADES")
    lines.append("-" * 60)
    lines.append("")

    for ex in result.exercises:
        rating_display = {
            "EXCELLENT": "[EXCELLENT]",
            "OK": "[OK]",
            "NEEDS_WORK": "[NEEDS WORK]"
        }.get(ex.rating.value, f"[{ex.rating.value}]")

        lines.append(f"{ex.exercise_id}: {rating_display}")
        lines.append("-" * 40)

        if ex.rationale:
            lines.append(f"Feedback: {ex.rationale}")

        if ex.missing_or_wrong:
            lines.append("")
            lines.append("Issues to address:")
            for item in ex.missing_or_wrong:
                lines.append(f"  - {item}")

        if ex.flags:
            lines.append("")
            lines.append(f"Flags: {', '.join(ex.flags)}")

        lines.append("")
        lines.append("")

    lines.append("-" * 60)
    lines.append("SUMMARY")
    lines.append("-" * 60)

    excellent = sum(1 for ex in result.exercises if ex.rating.value == "EXCELLENT")
    ok = sum(1 for ex in result.exercises if ex.rating.value == "OK")
    needs_work = sum(1 for ex in result.exercises if ex.rating.value == "NEEDS_WORK")
    total = len(result.exercises)

    lines.append(f"  EXCELLENT:   {excellent}/{total}")
    lines.append(f"  OK:          {ok}/{total}")
    lines.append(f"  NEEDS WORK:  {needs_work}/{total}")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main UI."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(content="<h1>GraderBot</h1><p>Static files not found.</p>")


@app.get("/api/status")
async def status():
    """Check API status and available providers."""
    providers = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")

    return {
        "status": "ok",
        "version": "0.1.0",
        "providers": providers,
    }


@app.post("/api/grade")
async def grade_notebook(
    solution: Annotated[UploadFile, File(description="Solution notebook (.ipynb)")],
    submission: Annotated[UploadFile, File(description="Student submission (.ipynb)")],
    provider: Annotated[str, Form()] = "anthropic",
    student_id: Annotated[str | None, Form()] = None,
):
    """
    Grade a single student notebook against a solution.

    Returns the grading result as JSON.
    """
    try:
        # Read file contents
        solution_content = (await solution.read()).decode("utf-8")
        submission_content = (await submission.read()).decode("utf-8")

        # Extract student ID from filename if not provided
        if not student_id and submission.filename:
            # Remove .ipynb extension and use as student ID
            student_id = Path(submission.filename).stem

        # Create LLM client
        try:
            client = create_client(provider)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Prepare context and grade
        context = prepare_solution_grading_context_from_content(
            solution_content=solution_content,
            notebook_content=submission_content,
            student_id=student_id,
        )

        result = grade_notebook_with_solution(client, context)

        return JSONResponse(content=json.loads(result.model_dump_json()))

    except GradingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid notebook JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch")
async def batch_grade(
    solution: Annotated[UploadFile, File(description="Solution notebook (.ipynb)")],
    submissions: Annotated[list[UploadFile], File(description="Student submissions (.ipynb files)")],
    provider: Annotated[str, Form()] = "anthropic",
):
    """
    Grade multiple student notebooks against a solution.

    Returns an array of grading results.
    """
    try:
        # Read solution once
        solution_content = (await solution.read()).decode("utf-8")

        # Create LLM client
        try:
            client = create_client(provider)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        results = []
        errors = []

        for sub in submissions:
            try:
                submission_content = (await sub.read()).decode("utf-8")
                student_id = Path(sub.filename).stem if sub.filename else None

                context = prepare_solution_grading_context_from_content(
                    solution_content=solution_content,
                    notebook_content=submission_content,
                    student_id=student_id,
                )

                result = grade_notebook_with_solution(client, context)
                results.append({
                    "filename": sub.filename,
                    "student_id": student_id,
                    "success": True,
                    "result": json.loads(result.model_dump_json()),
                })

            except Exception as e:
                results.append({
                    "filename": sub.filename,
                    "student_id": Path(sub.filename).stem if sub.filename else None,
                    "success": False,
                    "error": str(e),
                })

        return JSONResponse(content={
            "total": len(submissions),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results,
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/report")
async def generate_report(result: dict):
    """
    Generate a text report from a grading result JSON.

    Accepts the grading result and returns a plain text report.
    """
    try:
        grading_result = GradingResult.model_validate(result)
        report = generate_text_report(grading_result)
        return Response(content=report, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download-batch")
async def download_batch_results(results: dict):
    """
    Create a ZIP file containing all batch grading results.

    Returns a ZIP file with JSON and TXT files for each graded submission.
    """
    try:
        buffer = BytesIO()

        with ZipFile(buffer, "w") as zf:
            for item in results.get("results", []):
                if item.get("success") and item.get("result"):
                    student_id = item.get("student_id", "unknown")

                    # Add JSON result
                    json_content = json.dumps(item["result"], indent=2)
                    zf.writestr(f"{student_id}.json", json_content)

                    # Add text report
                    try:
                        grading_result = GradingResult.model_validate(item["result"])
                        report = generate_text_report(grading_result)
                        zf.writestr(f"{student_id}.txt", report)
                    except Exception:
                        pass  # Skip text report if validation fails

        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=grading_results.zip"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
