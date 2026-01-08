@echo off
echo ============================================
echo GraderBot - LLM-Powered Notebook Grader
echo ============================================
echo.

REM Activate virtual environment
call venv\Scripts\activate

REM Check if arguments provided
if "%~1"=="" (
    echo Usage:
    echo   run_grader.bat grade SOLUTION.ipynb STUDENT.ipynb
    echo   run_grader.bat report RESULT.json
    echo   run_grader.bat demo
    echo.
    echo Example:
    echo   run_grader.bat grade solutions\solution.ipynb submissions\student.ipynb
    echo   run_grader.bat report results\student.json
    echo   run_grader.bat demo  ^(runs example^)
    exit /b 1
)

if "%~1"=="demo" (
    echo Running demo with example files...
    echo.
    graderbot grade --solution "solutions\code_TB_Data_explorer_5_7_Jinich(Solution).ipynb" --notebook "submissions\Mannam_Sricode_TB_Data_explorer_5_7_Jinich.ipynb" --provider anthropic --model claude-3-haiku-20240307 --out "results\demo_result.json"
    echo.
    echo Generating readable report...
    python -m graderbot.report "results\demo_result.json"
    echo.
    echo Demo complete! Check results\demo_result.txt
    exit /b 0
)

if "%~1"=="grade" (
    if "%~2"=="" (
        echo Error: Please provide solution and student notebook paths
        exit /b 1
    )
    if "%~3"=="" (
        echo Error: Please provide student notebook path
        exit /b 1
    )

    REM Extract filename for output
    set "student=%~n3"

    echo Grading %~3 against %~2...
    graderbot grade --solution "%~2" --notebook "%~3" --provider anthropic --model claude-3-haiku-20240307 --out "results\%student%.json"

    echo.
    echo Generating report...
    python -m graderbot.report "results\%student%.json"

    echo.
    echo Done! Results saved to results\%student%.json and results\%student%.txt
    exit /b 0
)

if "%~1"=="report" (
    if "%~2"=="" (
        echo Error: Please provide JSON file path
        exit /b 1
    )
    python -m graderbot.report "%~2"
    exit /b 0
)

echo Unknown command: %~1
echo Use: demo, grade, or report
