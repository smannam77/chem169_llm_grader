"""Command-line interface for GraderBot."""

import io
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from . import __version__
from .grader import (
    get_dry_run_output,
    get_solution_dry_run_output,
    grade_notebook_from_paths,
    grade_notebook_from_solution_paths,
    grade_text_from_paths,
    prepare_grading_context,
    prepare_solution_grading_context,
)
from .llm_client import create_client
from .text_view import list_text_submissions, render_text_submission

# Load environment variables from .env file
load_dotenv()

app = typer.Typer(
    name="graderbot",
    help="LLM-powered grading assistant for Jupyter notebooks.",
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"GraderBot v{__version__}")
        raise typer.Exit()


@app.command()
def grade(
    route: Optional[Path] = typer.Option(
        None,
        "--route",
        "-r",
        help="Path to the route/assignment markdown file",
        exists=True,
        dir_okay=False,
    ),
    solution: Optional[Path] = typer.Option(
        None,
        "--solution",
        "-s",
        help="Path to the solution Jupyter notebook (.ipynb)",
        exists=True,
        dir_okay=False,
    ),
    notebook: Path = typer.Option(
        ...,
        "--notebook",
        "-n",
        help="Path to the student Jupyter notebook (.ipynb)",
        exists=True,
        dir_okay=False,
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Path to write grading JSON output (default: stdout)",
        dir_okay=False,
    ),
    provider: str = typer.Option(
        "openai",
        "--provider",
        "-p",
        help="LLM provider: openai, anthropic, or mock",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (provider-specific default if not set)",
    ),
    route_id: Optional[str] = typer.Option(
        None,
        "--route-id",
        help="Route/assignment identifier to include in output",
    ),
    student_id: Optional[str] = typer.Option(
        None,
        "--student-id",
        help="Student identifier to include in output",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Print composed prompt without calling LLM API",
    ),
    max_retries: int = typer.Option(
        2,
        "--max-retries",
        help="Maximum retries for JSON repair",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """
    Grade a student Jupyter notebook against a route specification or solution notebook.

    You must provide either --route (markdown file) or --solution (notebook file), but not both.

    Examples:
        graderbot grade --route assignment.md --notebook student.ipynb --out result.json
        graderbot grade --solution solution.ipynb --notebook student.ipynb --out result.json
    """
    # Validate that exactly one of route or solution is provided
    if route is None and solution is None:
        typer.echo("Error: You must provide either --route or --solution", err=True)
        raise typer.Exit(1)
    if route is not None and solution is not None:
        typer.echo("Error: Cannot use both --route and --solution. Choose one.", err=True)
        raise typer.Exit(1)

    use_solution_mode = solution is not None

    try:
        if dry_run:
            # Dry run mode: just show the prompt
            if use_solution_mode:
                context = prepare_solution_grading_context(
                    solution_path=solution,
                    notebook_path=notebook,
                    route_id=route_id,
                    student_id=student_id,
                )
                output = get_solution_dry_run_output(context)
            else:
                context = prepare_grading_context(
                    route_path=route,
                    notebook_path=notebook,
                    route_id=route_id,
                    student_id=student_id,
                )
                output = get_dry_run_output(context)
            typer.echo(output)
            return

        # Build client kwargs
        client_kwargs = {}
        if model:
            client_kwargs["model"] = model

        # Create client and grade
        try:
            client = create_client(provider, **client_kwargs)
        except ValueError as e:
            typer.echo(f"Error creating LLM client: {e}", err=True)
            raise typer.Exit(1)

        typer.echo(f"Grading notebook with {client.name}...", err=True)

        if use_solution_mode:
            result = grade_notebook_from_solution_paths(
                client=client,
                solution_path=solution,
                notebook_path=notebook,
                route_id=route_id,
                student_id=student_id,
                max_retries=max_retries,
            )
        else:
            result = grade_notebook_from_paths(
                client=client,
                route_path=route,
                notebook_path=notebook,
                route_id=route_id,
                student_id=student_id,
                max_retries=max_retries,
            )

        # Output result
        json_output = result.model_dump_json(indent=2)

        if out:
            out.write_text(json_output, encoding="utf-8")
            typer.echo(f"Grading complete. Output written to: {out}", err=True)
        else:
            typer.echo(json_output)

        # Summary to stderr
        typer.echo(f"\nGraded {len(result.exercises)} exercises.", err=True)
        for ex in result.exercises:
            typer.echo(f"  {ex.exercise_id}: {ex.rating.value}", err=True)

    except FileNotFoundError as e:
        typer.echo(f"File not found: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def batch(
    route: Optional[Path] = typer.Option(
        None,
        "--route",
        "-r",
        help="Path to the route/assignment markdown file",
        exists=True,
        dir_okay=False,
    ),
    solution: Optional[Path] = typer.Option(
        None,
        "--solution",
        "-s",
        help="Path to the solution Jupyter notebook (.ipynb)",
        exists=True,
        dir_okay=False,
    ),
    submissions: Path = typer.Option(
        ...,
        "--submissions",
        "-i",
        help="Path to folder containing student notebook submissions",
        exists=True,
        file_okay=False,
    ),
    out: Path = typer.Option(
        ...,
        "--out",
        "-o",
        help="Path to output folder for grading results",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider",
        "-p",
        help="LLM provider: openai, anthropic, or mock",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (provider-specific default if not set)",
    ),
    route_id: Optional[str] = typer.Option(
        None,
        "--route-id",
        help="Route/assignment identifier to include in output",
    ),
    max_retries: int = typer.Option(
        2,
        "--max-retries",
        help="Maximum retries for JSON repair",
    ),
    pattern: str = typer.Option(
        "*.ipynb",
        "--pattern",
        help="Glob pattern for notebook files (default: *.ipynb)",
    ),
) -> None:
    """
    Grade multiple student notebooks in batch mode.

    Grades all notebooks in the submissions folder against a route (instructions) or solution notebook.
    Results are saved as individual JSON files plus a summary.

    Examples:
        graderbot batch --route assignment.md --submissions ./student_work/ --out ./results/
        graderbot batch --solution solution.ipynb --submissions ./student_work/ --out ./results/
        graderbot batch -r assignment.md -i ./submissions/ -o ./grades/ --provider anthropic
    """
    # Validate that exactly one of route or solution is provided
    if route is None and solution is None:
        typer.echo("Error: You must provide either --route or --solution", err=True)
        raise typer.Exit(1)
    if route is not None and solution is not None:
        typer.echo("Error: Cannot use both --route and --solution. Choose one.", err=True)
        raise typer.Exit(1)

    use_solution_mode = solution is not None
    # Find all notebook files
    notebooks = list(submissions.glob(pattern))

    if not notebooks:
        typer.echo(f"No notebooks found matching '{pattern}' in {submissions}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Found {len(notebooks)} notebooks to grade", err=True)

    # Create output directory
    out.mkdir(parents=True, exist_ok=True)

    # Build client
    client_kwargs = {}
    if model:
        client_kwargs["model"] = model

    try:
        client = create_client(provider, **client_kwargs)
    except ValueError as e:
        typer.echo(f"Error creating LLM client: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Using {client.name}", err=True)
    typer.echo("", err=True)

    # Grade each notebook
    results_summary = []
    successful = 0
    failed = 0

    for i, notebook_path in enumerate(notebooks, 1):
        student_name = notebook_path.stem

        # Check if already graded (for resume support)
        output_file = out / f"{student_name}_grade.json"
        if output_file.exists():
            typer.echo(f"[{i}/{len(notebooks)}] Skipping {notebook_path.name} - already graded", err=True)
            # Load existing result for summary
            try:
                existing = json.loads(output_file.read_text())
                exercise_ratings = {ex["exercise_id"]: ex["rating"] for ex in existing.get("exercises", [])}
                results_summary.append({
                    "student_id": student_name,
                    "file": notebook_path.name,
                    "exercises": exercise_ratings,
                    "output_file": output_file.name,
                    "skipped": True,
                })
                successful += 1
            except Exception:
                pass
            continue

        typer.echo(f"[{i}/{len(notebooks)}] Grading {notebook_path.name}...", err=True)

        try:
            if use_solution_mode:
                result = grade_notebook_from_solution_paths(
                    client=client,
                    solution_path=solution,
                    notebook_path=notebook_path,
                    route_id=route_id,
                    student_id=student_name,
                    max_retries=max_retries,
                )
            else:
                result = grade_notebook_from_paths(
                    client=client,
                    route_path=route,
                    notebook_path=notebook_path,
                    route_id=route_id,
                    student_id=student_name,
                    max_retries=max_retries,
                )

            # Save individual result
            output_file = out / f"{student_name}_grade.json"
            output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")

            # Build summary entry
            exercise_ratings = {ex.exercise_id: ex.rating.value for ex in result.exercises}
            manual_review_needed = any(
                "manual_review" in (ex.flags or []) for ex in result.exercises
            )

            summary_entry = {
                "student_id": student_name,
                "file": notebook_path.name,
                "exercises": exercise_ratings,
                "manual_review_needed": manual_review_needed,
                "output_file": output_file.name,
            }
            results_summary.append(summary_entry)

            # Show brief result
            ratings_str = ", ".join(f"{k}: {v}" for k, v in exercise_ratings.items())
            typer.echo(f"    {ratings_str}", err=True)
            successful += 1

        except Exception as e:
            typer.echo(f"    ERROR: {e}", err=True)
            results_summary.append({
                "student_id": student_name,
                "file": notebook_path.name,
                "error": str(e),
            })
            failed += 1

    # Write summary file
    summary_file = out / "summary.json"
    summary_data = {
        "route_id": route_id,
        "grading_mode": "solution" if use_solution_mode else "route",
        "reference_file": solution.name if use_solution_mode else route.name,
        "total_graded": len(notebooks),
        "successful": successful,
        "failed": failed,
        "results": results_summary,
    }
    summary_file.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

    # Final summary
    typer.echo("", err=True)
    typer.echo("=" * 50, err=True)
    typer.echo(f"Batch grading complete!", err=True)
    typer.echo(f"  Successful: {successful}/{len(notebooks)}", err=True)
    if failed > 0:
        typer.echo(f"  Failed: {failed}", err=True)
    typer.echo(f"  Results: {out}", err=True)
    typer.echo(f"  Summary: {summary_file}", err=True)


@app.command("batch-text")
def batch_text(
    route: Path = typer.Option(
        ...,
        "--route",
        "-r",
        help="Path to the route/assignment markdown file",
        exists=True,
        dir_okay=False,
    ),
    submissions: Path = typer.Option(
        ...,
        "--submissions",
        "-i",
        help="Path to folder containing student text submissions",
        exists=True,
        file_okay=False,
    ),
    out: Path = typer.Option(
        ...,
        "--out",
        "-o",
        help="Path to output folder for grading results",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider",
        "-p",
        help="LLM provider: openai, anthropic, or mock",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (provider-specific default if not set)",
    ),
    route_id: Optional[str] = typer.Option(
        None,
        "--route-id",
        help="Route/assignment identifier to include in output",
    ),
    max_retries: int = typer.Option(
        2,
        "--max-retries",
        help="Maximum retries for JSON repair",
    ),
) -> None:
    """
    Grade multiple student text file submissions in batch mode.

    For routes like RID_006 and RID_008 that use .txt deliverables (git logs, reflections)
    instead of Jupyter notebooks.

    Examples:
        graderbot batch-text --route assignments/RID_006/instructions.md --submissions ./submissions/ --out ./results/
    """
    # Find all text submissions
    text_submissions = list_text_submissions(str(submissions))

    if not text_submissions:
        typer.echo(f"No text submissions found in {submissions}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Found {len(text_submissions)} student submissions to grade", err=True)

    # Create output directory
    out.mkdir(parents=True, exist_ok=True)

    # Build client
    client_kwargs = {}
    if model:
        client_kwargs["model"] = model

    try:
        client = create_client(provider, **client_kwargs)
    except ValueError as e:
        typer.echo(f"Error creating LLM client: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Using {client.name}", err=True)
    typer.echo("", err=True)

    # Grade each submission
    results_summary = []
    successful = 0
    failed = 0

    for i, sub in enumerate(text_submissions, 1):
        student_name = sub['student']
        deliverable = sub.get('deliverable')
        logbook = sub.get('logbook')

        if not deliverable:
            typer.echo(f"[{i}/{len(text_submissions)}] Skipping {student_name} - no deliverable found", err=True)
            results_summary.append({
                "student_id": student_name,
                "error": "No deliverable file found",
            })
            failed += 1
            continue

        # Check if already graded (for resume support)
        output_file = out / f"{student_name}_grade.json"
        if output_file.exists():
            typer.echo(f"[{i}/{len(text_submissions)}] Skipping {student_name} - already graded", err=True)
            # Load existing result for summary
            try:
                existing = json.loads(output_file.read_text())
                exercise_ratings = {ex["exercise_id"]: ex["rating"] for ex in existing.get("exercises", [])}
                results_summary.append({
                    "student_id": student_name,
                    "deliverable": Path(deliverable).name if deliverable else None,
                    "logbook": Path(logbook).name if logbook else None,
                    "exercises": exercise_ratings,
                    "output_file": output_file.name,
                    "skipped": True,
                })
                successful += 1
            except Exception:
                pass
            continue

        typer.echo(f"[{i}/{len(text_submissions)}] Grading {student_name}...", err=True)

        try:
            result = grade_text_from_paths(
                client=client,
                route_path=route,
                deliverable_path=deliverable,
                logbook_path=logbook,
                route_id=route_id,
                student_id=student_name,
                max_retries=max_retries,
            )

            # Save individual result
            output_file = out / f"{student_name}_grade.json"
            output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")

            # Build summary entry
            exercise_ratings = {ex.exercise_id: ex.rating.value for ex in result.exercises}

            summary_entry = {
                "student_id": student_name,
                "deliverable": Path(deliverable).name if deliverable else None,
                "logbook": Path(logbook).name if logbook else None,
                "exercises": exercise_ratings,
                "output_file": output_file.name,
            }
            results_summary.append(summary_entry)

            # Show brief result
            ratings_str = ", ".join(f"{k}: {v}" for k, v in exercise_ratings.items())
            typer.echo(f"    {ratings_str}", err=True)
            successful += 1

        except Exception as e:
            typer.echo(f"    ERROR: {e}", err=True)
            results_summary.append({
                "student_id": student_name,
                "error": str(e),
            })
            failed += 1

    # Write summary file
    summary_file = out / "summary.json"
    summary_data = {
        "route_id": route_id,
        "grading_mode": "text",
        "reference_file": route.name,
        "total_graded": len(text_submissions),
        "successful": successful,
        "failed": failed,
        "results": results_summary,
    }
    summary_file.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

    # Final summary
    typer.echo("", err=True)
    typer.echo("=" * 50, err=True)
    typer.echo(f"Batch text grading complete!", err=True)
    typer.echo(f"  Successful: {successful}/{len(text_submissions)}", err=True)
    if failed > 0:
        typer.echo(f"  Failed: {failed}", err=True)
    typer.echo(f"  Results: {out}", err=True)
    typer.echo(f"  Summary: {summary_file}", err=True)


@app.command()
def parse_route(
    route: Path = typer.Argument(
        ...,
        help="Path to the route markdown file",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """
    Parse a route file and display extracted exercises.

    Useful for debugging route parsing.
    """
    from .route_parser import parse_route_file

    try:
        parsed = parse_route_file(route)
        typer.echo(f"Route: {parsed.title or '(no title)'}")
        typer.echo(f"Exercises found: {len(parsed.exercises)}")
        typer.echo("")

        for ex in parsed.exercises:
            typer.echo(f"  {ex.exercise_id}")
            if ex.title:
                typer.echo(f"    Title: {ex.title}")
            preview = ex.instructions[:100].replace("\n", " ")
            if len(ex.instructions) > 100:
                preview += "..."
            typer.echo(f"    Instructions: {preview}")
            typer.echo("")

    except Exception as e:
        typer.echo(f"Error parsing route: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def parse_solution(
    solution: Path = typer.Argument(
        ...,
        help="Path to the solution notebook file",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """
    Parse a solution notebook and display extracted exercises.

    Useful for debugging solution notebook parsing.
    """
    from .notebook_view import extract_exercises_from_notebook, parse_notebook_file

    try:
        view = parse_notebook_file(solution)
        exercises = extract_exercises_from_notebook(view)

        if not exercises:
            typer.echo("No exercises found in solution notebook.")
            typer.echo("Make sure exercises are marked with headers like '## Exercise 1'")
            raise typer.Exit(1)

        typer.echo(f"Solution notebook: {solution.name}")
        typer.echo(f"Exercises found: {len(exercises)}")
        typer.echo("")

        for ex in exercises:
            type_label = "[CODE]" if ex.exercise_type == "code" else "[WRITING]"
            typer.echo(f"  {ex.exercise_id} {type_label}")
            if ex.title:
                typer.echo(f"    Title: {ex.title}")
            typer.echo(f"    Cells: {len(ex.cells)}")

            # Count cell types
            code_cells = sum(1 for c in ex.cells if c.cell_type == "code")
            md_cells = sum(1 for c in ex.cells if c.cell_type == "markdown")
            typer.echo(f"    Code cells: {code_cells}, Markdown cells: {md_cells}")
            typer.echo("")

    except Exception as e:
        typer.echo(f"Error parsing solution notebook: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def view_notebook(
    notebook: Path = typer.Argument(
        ...,
        help="Path to the Jupyter notebook",
        exists=True,
        dir_okay=False,
    ),
    include_markdown: bool = typer.Option(
        True,
        "--include-markdown/--no-markdown",
        help="Include markdown cells in output",
    ),
) -> None:
    """
    Display a notebook in grading view format.

    Useful for debugging notebook parsing.
    """
    from .notebook_view import format_notebook_for_prompt, parse_notebook_file

    try:
        view = parse_notebook_file(notebook)
        formatted = format_notebook_for_prompt(view, include_markdown=include_markdown)
        typer.echo(formatted)

    except Exception as e:
        typer.echo(f"Error parsing notebook: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def report(
    json_file: Path = typer.Argument(
        ...,
        help="Path to the grading JSON file",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Path for the output report (default: same name with .txt)",
    ),
) -> None:
    """
    Generate a readable student report from grading JSON.

    Converts the JSON grading output into a formatted text report
    that's easier for students to read.
    """
    from .report import json_to_report

    if not json_file.exists():
        typer.echo(f"Error: File not found: {json_file}", err=True)
        raise typer.Exit(1)

    try:
        output_path = str(output) if output else None
        report_text = json_to_report(str(json_file), output_path)
        typer.echo(report_text)

        out_file = output or json_file.with_suffix(".txt")
        typer.echo(f"\nReport saved to: {out_file}")

    except Exception as e:
        typer.echo(f"Error generating report: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host to bind the server to",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to run the server on",
    ),
) -> None:
    """
    Start the web UI server.

    Launches a local web server for grading notebooks through a browser interface.

    Examples:
        graderbot serve
        graderbot serve --port 3000
        graderbot serve --host 0.0.0.0 --port 8080
    """
    try:
        import uvicorn
        from .web import app as web_app

        typer.echo(f"Starting GraderBot web UI at http://{host}:{port}", err=True)
        typer.echo("Press Ctrl+C to stop the server", err=True)
        typer.echo("", err=True)

        uvicorn.run(web_app, host=host, port=port)

    except ImportError as e:
        typer.echo(f"Error: Missing dependencies for web UI: {e}", err=True)
        typer.echo("Run: pip install fastapi uvicorn python-multipart", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error starting server: {e}", err=True)
        raise typer.Exit(1)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
