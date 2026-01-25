"""Dashboard prototype: visualize student submission statistics."""

import os
import re
from pathlib import Path
from collections import defaultdict

# Try plotly first for interactive, fall back to matplotlib
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

import matplotlib.pyplot as plt


def extract_student_name(filename: str) -> str:
    """Extract student name from submission filename."""
    # Remove extension
    name = Path(filename).stem
    # Remove common suffixes like _RID_001_code, _RID_002_code, etc.
    name = re.sub(r'_RID_?\d+.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'_code$', '', name, flags=re.IGNORECASE)
    # Normalize to lowercase for matching
    return name.lower().strip()


def scan_submissions(assignments_dir: str = "assignments") -> dict:
    """
    Scan all assignment folders and count submissions per student.

    Returns:
        dict: {student_name: set of RIDs submitted}
    """
    student_routes = defaultdict(set)

    assignments_path = Path(assignments_dir)

    for rid_folder in sorted(assignments_path.glob("RID_*")):
        rid = rid_folder.name  # e.g., "RID_001"
        submissions_dir = rid_folder / "submissions"

        if not submissions_dir.exists():
            continue

        for notebook in submissions_dir.glob("*.ipynb"):
            student = extract_student_name(notebook.name)
            if student:
                student_routes[student].add(rid)

    return dict(student_routes)


def scan_grading_results(assignments_dir: str = "assignments") -> dict:
    """
    Scan all grading result JSON files.

    Returns:
        dict: {student_name: {rid: grading_data}}
        where grading_data contains exercises with ratings, rationales, etc.
    """
    import json

    student_grades = defaultdict(dict)
    assignments_path = Path(assignments_dir)

    for rid_folder in sorted(assignments_path.glob("RID_*")):
        rid = rid_folder.name  # e.g., "RID_001"
        results_dir = rid_folder / "results"

        if not results_dir.exists():
            continue

        for json_file in results_dir.glob("*_grade.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Extract student name from filename
                student = extract_student_name(json_file.stem.replace('_grade', ''))
                if not student:
                    continue

                # Build grade summary
                exercises = data.get('exercises', [])
                grade_info = {
                    'route_id': rid,
                    'exercises': [],
                    'overall_summary': data.get('overall_summary', ''),
                }

                for ex in exercises:
                    grade_info['exercises'].append({
                        'exercise_id': ex.get('exercise_id', ''),
                        'rating': ex.get('rating', 'UNKNOWN'),
                        'rationale': ex.get('rationale', ''),
                        'flags': ex.get('flags', []),
                    })

                student_grades[student][rid] = grade_info

            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read {json_file}: {e}")
                continue

    return dict(student_grades)


def get_latest_submission_time(assignments_dir: str = "assignments") -> str:
    """Get the timestamp of the most recently modified submission file."""
    from datetime import datetime

    assignments_path = Path(assignments_dir)
    latest_time = None

    for notebook in assignments_path.glob("RID_*/submissions/*.ipynb"):
        mtime = notebook.stat().st_mtime
        if latest_time is None or mtime > latest_time:
            latest_time = mtime

    if latest_time:
        dt = datetime.fromtimestamp(latest_time)
        return dt.strftime("%Y-%m-%d %H:%M")
    return "Unknown"


def get_completion_stats(student_routes: dict, assignments_dir: str = "assignments") -> dict:
    """Calculate completion statistics."""
    total_routes = 6  # Current gym size

    completions = [len(routes) for routes in student_routes.values()]

    return {
        "total_students": len(student_routes),
        "total_routes": total_routes,
        "completions": completions,
        "avg_completed": sum(completions) / len(completions) if completions else 0,
        "max_completed": max(completions) if completions else 0,
        "min_completed": min(completions) if completions else 0,
        "last_updated": get_latest_submission_time(assignments_dir),
    }


def plot_dashboard(student_routes: dict, output_path: str = None):
    """Create dashboard visualizations."""
    stats = get_completion_stats(student_routes)
    completions = stats["completions"]
    total_routes = stats["total_routes"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # --- Histogram: Distribution of routes completed ---
    ax1 = axes[0]
    bins = range(0, total_routes + 2)
    ax1.hist(completions, bins=bins, edgecolor='black', alpha=0.7, align='left')
    ax1.set_xlabel("Routes Completed")
    ax1.set_ylabel("Number of Students")
    ax1.set_title(f"Distribution of Routes Completed\n(Gym Size: {total_routes} routes)")
    ax1.set_xticks(range(0, total_routes + 1))

    # Add stats text
    stats_text = f"n={stats['total_students']}\nμ={stats['avg_completed']:.1f}\nmax={stats['max_completed']}"
    ax1.text(0.95, 0.95, stats_text, transform=ax1.transAxes,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # --- Scatter: Each student as a point ---
    ax2 = axes[1]
    # X = gym size (constant for now), Y = routes completed per student
    # Add jitter to X for visibility
    import numpy as np
    np.random.seed(42)
    x_jitter = np.random.normal(total_routes, 0.15, len(completions))

    ax2.scatter(x_jitter, completions, alpha=0.5, s=50)
    ax2.set_xlabel("Gym Size (Routes Available)")
    ax2.set_ylabel("Routes Completed")
    ax2.set_title(f"Student Progress\n({stats['total_students']} students)")
    ax2.set_xlim(0, total_routes + 1)
    ax2.set_ylim(-0.5, total_routes + 0.5)
    ax2.axhline(y=stats['avg_completed'], color='red', linestyle='--', label=f"Mean: {stats['avg_completed']:.1f}")
    ax2.legend()

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150)
        print(f"Dashboard saved to: {output_path}")

    plt.show()
    return fig


def print_summary(student_routes: dict):
    """Print text summary of submissions."""
    stats = get_completion_stats(student_routes)

    print("=" * 60)
    print("SUBMISSION STATISTICS")
    print("=" * 60)
    print(f"Gym Size: {stats['total_routes']} routes")
    print(f"Total Students: {stats['total_students']}")
    print(f"Average Completed: {stats['avg_completed']:.1f}")
    print(f"Range: {stats['min_completed']} - {stats['max_completed']}")
    print(f"Last Updated: {stats['last_updated']}")
    print()

    # Distribution table
    from collections import Counter
    dist = Counter(stats['completions'])
    print("Distribution:")
    for n in range(stats['total_routes'] + 1):
        count = dist.get(n, 0)
        bar = "█" * count
        print(f"  {n} routes: {count:3d} students {bar}")


def plot_interactive_dashboard(student_routes: dict, output_path: str = "dashboard.html", assignments_dir: str = "assignments"):
    """Create interactive HTML dashboard with plotly."""
    if not HAS_PLOTLY:
        raise ImportError("plotly is required for interactive dashboard. Install with: pip install plotly")

    import numpy as np
    import json
    from collections import Counter

    stats = get_completion_stats(student_routes)
    total_routes = stats["total_routes"]
    all_routes = [f"RID_{str(i).zfill(3)}" for i in range(1, total_routes + 1)]

    # Get grading results
    student_grades = scan_grading_results(assignments_dir)

    # Prepare data with student names
    students = list(student_routes.keys())
    completions = [len(routes) for routes in student_routes.values()]

    # Create figure with subplots
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            f"Distribution of Routes Completed (Gym: {total_routes} routes)",
            f"Student Progress ({len(students)} students)"
        ),
        column_widths=[0.5, 0.5]
    )

    # --- Left: Histogram ---
    dist = Counter(completions)
    x_hist = list(range(total_routes + 1))
    y_hist = [dist.get(n, 0) for n in x_hist]

    fig.add_trace(
        go.Bar(
            x=x_hist,
            y=y_hist,
            marker_color='steelblue',
            opacity=0.7,
            name='Students',
            hovertemplate='%{y} students completed %{x} routes<extra></extra>'
        ),
        row=1, col=1
    )

    # --- Right: Violin + Strip plot with student names ---
    np.random.seed(42)

    # Add violin plot
    fig.add_trace(
        go.Violin(
            y=completions,
            box_visible=True,
            meanline_visible=True,
            fillcolor='lightblue',
            opacity=0.6,
            line_color='steelblue',
            name='Distribution',
            side='positive',
            x0='Students',
            hoverinfo='skip'
        ),
        row=1, col=2
    )

    # Add strip plot (individual points) with jitter
    jitter = np.random.normal(0, 0.04, len(students))

    # Format student names nicely for hover
    display_names = [name.replace('_', ' ').title() for name in students]

    fig.add_trace(
        go.Scatter(
            x=jitter,
            y=completions,
            mode='markers',
            marker=dict(
                size=8,
                color='darkblue',
                opacity=0.6
            ),
            name='Students',
            text=display_names,
            customdata=[[s, c] for s, c in zip(display_names, completions)],
            hovertemplate='<b>%{customdata[0]}</b><br>Routes: %{customdata[1]}<extra></extra>'
        ),
        row=1, col=2
    )

    # Add mean line
    fig.add_hline(
        y=stats['avg_completed'],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {stats['avg_completed']:.1f}",
        annotation_position="top right",
        row=1, col=2
    )

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"<b>Route Completion Dashboard</b><br><sub>n={stats['total_students']} students | μ={stats['avg_completed']:.1f} routes | range={stats['min_completed']}-{stats['max_completed']} | Last updated: {stats['last_updated']}</sub>",
            x=0.5
        ),
        showlegend=False,
        height=500,
        width=1000,
        template='plotly_white'
    )

    # Update axes
    fig.update_xaxes(title_text="Routes Completed", row=1, col=1)
    fig.update_yaxes(title_text="Number of Students", row=1, col=1)
    fig.update_xaxes(title_text="", showticklabels=False, row=1, col=2)
    fig.update_yaxes(title_text="Routes Completed", range=[-0.5, total_routes + 0.5], row=1, col=2)

    # Generate the plotly chart HTML
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    # Prepare student data for JavaScript
    student_data = {}
    for student, routes in student_routes.items():
        display_name = student.replace('_', ' ').title()
        completed = sorted(list(routes))
        missing = [r for r in all_routes if r not in routes]

        # Include grading data if available
        grades = {}
        if student in student_grades:
            for rid, grade_info in student_grades[student].items():
                grades[rid] = {
                    "exercises": grade_info.get("exercises", []),
                    "overall_summary": grade_info.get("overall_summary", ""),
                }

        student_data[student] = {
            "display_name": display_name,
            "completed": completed,
            "missing": missing,
            "count": len(routes),
            "total": total_routes,
            "grades": grades,
        }

    student_json = json.dumps(student_data)
    sorted_students_json = json.dumps(sorted(students))

    # Create full HTML with search functionality
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>Route Completion Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .search-panel {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .search-panel h3 {{
            margin-top: 0;
            color: #333;
        }}
        .search-row {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        #studentSearch {{
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 300px;
        }}
        #studentSelect {{
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 300px;
        }}
        .student-info {{
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
            display: none;
        }}
        .student-info.active {{
            display: block;
        }}
        .student-name {{
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .stats-row {{
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
        }}
        .stat-box {{
            background: white;
            padding: 15px 25px;
            border-radius: 4px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .routes-section {{
            display: flex;
            gap: 20px;
        }}
        .routes-list {{
            flex: 1;
        }}
        .routes-list h4 {{
            margin: 0 0 10px 0;
            color: #555;
        }}
        .route-tag {{
            display: inline-block;
            padding: 5px 10px;
            margin: 3px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .route-completed {{
            background: #d4edda;
            color: #155724;
        }}
        .route-missing {{
            background: #f8d7da;
            color: #721c24;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        /* Grading feedback styles */
        .grades-section {{
            margin-top: 20px;
            border-top: 1px solid #ddd;
            padding-top: 15px;
        }}
        .grades-section h4 {{
            margin: 0 0 15px 0;
            color: #333;
        }}
        .route-grade-card {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 15px;
            overflow: hidden;
        }}
        .route-grade-header {{
            background: #f8f9fa;
            padding: 10px 15px;
            font-weight: bold;
            border-bottom: 1px solid #e0e0e0;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .route-grade-header:hover {{
            background: #e9ecef;
        }}
        .route-grade-body {{
            padding: 15px;
            display: none;
        }}
        .route-grade-body.expanded {{
            display: block;
        }}
        .exercise-row {{
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .exercise-row:last-child {{
            border-bottom: none;
        }}
        .exercise-id {{
            font-weight: 500;
            width: 100px;
            flex-shrink: 0;
        }}
        .exercise-rating {{
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
            margin-right: 15px;
            flex-shrink: 0;
        }}
        .rating-excellent {{
            background: #d4edda;
            color: #155724;
        }}
        .rating-ok {{
            background: #fff3cd;
            color: #856404;
        }}
        .rating-needs_work {{
            background: #f8d7da;
            color: #721c24;
        }}
        .exercise-rationale {{
            color: #666;
            font-size: 0.9em;
            flex-grow: 1;
        }}
        .overall-summary {{
            margin-top: 15px;
            padding: 12px;
            background: #e8f4f8;
            border-radius: 6px;
            font-style: italic;
            color: #333;
        }}
        .grade-summary-badge {{
            font-size: 0.85em;
            padding: 2px 8px;
            border-radius: 10px;
            background: #e0e0e0;
        }}
        .no-grades {{
            color: #888;
            font-style: italic;
            padding: 10px 0;
        }}
        .expand-icon {{
            transition: transform 0.2s;
        }}
        .expand-icon.rotated {{
            transform: rotate(180deg);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="search-panel">
            <h3>🔍 Student Lookup</h3>
            <div class="search-row">
                <input type="text" id="studentSearch" placeholder="Type to search student..." oninput="filterStudents()">
                <select id="studentSelect" onchange="showStudentInfo()">
                    <option value="">-- Select a student --</option>
                </select>
            </div>
            <div id="studentInfo" class="student-info">
                <div class="student-name" id="displayName"></div>
                <div class="stats-row">
                    <div class="stat-box">
                        <div class="stat-number" id="completedCount">0</div>
                        <div class="stat-label">Completed</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" id="missingCount">0</div>
                        <div class="stat-label">Missing</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" id="percentComplete">0%</div>
                        <div class="stat-label">Progress</div>
                    </div>
                </div>
                <div class="routes-section">
                    <div class="routes-list">
                        <h4>✅ Completed Routes</h4>
                        <div id="completedRoutes"></div>
                    </div>
                    <div class="routes-list">
                        <h4>❌ Missing Routes</h4>
                        <div id="missingRoutes"></div>
                    </div>
                </div>
                <div class="grades-section">
                    <h4>📝 Grading Feedback</h4>
                    <div id="gradesContainer"></div>
                </div>
            </div>
        </div>
        <div class="chart-container">
            {chart_html}
        </div>
    </div>

    <script>
        const studentData = {student_json};
        const allStudents = {sorted_students_json};

        // Populate dropdown on load
        function populateDropdown(students) {{
            const select = document.getElementById('studentSelect');
            select.innerHTML = '<option value="">-- Select a student --</option>';
            students.forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = studentData[s].display_name;
                select.appendChild(opt);
            }});
        }}

        // Filter students based on search input
        function filterStudents() {{
            const query = document.getElementById('studentSearch').value.toLowerCase();
            const filtered = allStudents.filter(s =>
                s.toLowerCase().includes(query) ||
                studentData[s].display_name.toLowerCase().includes(query)
            );
            populateDropdown(filtered);
            if (filtered.length === 1) {{
                document.getElementById('studentSelect').value = filtered[0];
                showStudentInfo();
            }}
        }}

        // Show selected student info
        function showStudentInfo() {{
            const selected = document.getElementById('studentSelect').value;
            const infoPanel = document.getElementById('studentInfo');

            if (!selected) {{
                infoPanel.classList.remove('active');
                return;
            }}

            const data = studentData[selected];
            document.getElementById('displayName').textContent = data.display_name;
            document.getElementById('completedCount').textContent = data.count;
            document.getElementById('missingCount').textContent = data.missing.length;
            document.getElementById('percentComplete').textContent =
                Math.round((data.count / data.total) * 100) + '%';

            // Render completed routes
            document.getElementById('completedRoutes').innerHTML = data.completed
                .map(r => `<span class="route-tag route-completed">${{r}}</span>`)
                .join('') || '<em>None</em>';

            // Render missing routes
            document.getElementById('missingRoutes').innerHTML = data.missing
                .map(r => `<span class="route-tag route-missing">${{r}}</span>`)
                .join('') || '<em>All complete! 🎉</em>';

            // Render grading feedback
            renderGrades(data);

            infoPanel.classList.add('active');
        }}

        // Render grading feedback for a student
        function renderGrades(data) {{
            const container = document.getElementById('gradesContainer');
            const grades = data.grades || {{}};
            const gradedRoutes = Object.keys(grades).sort();

            if (gradedRoutes.length === 0) {{
                container.innerHTML = '<p class="no-grades">No grading feedback available yet.</p>';
                return;
            }}

            let html = '';
            for (const rid of gradedRoutes) {{
                const gradeInfo = grades[rid];
                const exercises = gradeInfo.exercises || [];

                // Calculate summary stats
                const excellent = exercises.filter(e => e.rating === 'EXCELLENT').length;
                const ok = exercises.filter(e => e.rating === 'OK').length;
                const needsWork = exercises.filter(e => e.rating === 'NEEDS_WORK').length;
                const total = exercises.length;

                html += `
                    <div class="route-grade-card">
                        <div class="route-grade-header" onclick="toggleGradeCard(this)">
                            <span>${{rid}}</span>
                            <span>
                                <span class="grade-summary-badge">${{excellent}}/${{total}} Excellent</span>
                                <span class="expand-icon">▼</span>
                            </span>
                        </div>
                        <div class="route-grade-body">
                `;

                for (const ex of exercises) {{
                    const ratingClass = 'rating-' + ex.rating.toLowerCase();
                    html += `
                        <div class="exercise-row">
                            <span class="exercise-id">${{ex.exercise_id}}</span>
                            <span class="exercise-rating ${{ratingClass}}">${{ex.rating}}</span>
                            <span class="exercise-rationale">${{ex.rationale || ''}}</span>
                        </div>
                    `;
                }}

                if (gradeInfo.overall_summary) {{
                    html += `<div class="overall-summary"><strong>Summary:</strong> ${{gradeInfo.overall_summary}}</div>`;
                }}

                html += `
                        </div>
                    </div>
                `;
            }}

            container.innerHTML = html;
        }}

        // Toggle grade card expansion
        function toggleGradeCard(header) {{
            const body = header.nextElementSibling;
            const icon = header.querySelector('.expand-icon');
            body.classList.toggle('expanded');
            icon.classList.toggle('rotated');
        }}

        // Initialize
        populateDropdown(allStudents);
    </script>
</body>
</html>'''

    # Write to file
    with open(output_path, 'w') as f:
        f.write(html_content)

    print(f"Interactive dashboard saved to: {output_path}")
    print(f"Open in browser: file://{os.path.abspath(output_path)}")

    return fig


def main(interactive: bool = True):
    """Run dashboard."""
    student_routes = scan_submissions()
    print_summary(student_routes)

    if interactive and HAS_PLOTLY:
        plot_interactive_dashboard(student_routes, output_path="dashboard.html")
    else:
        plot_dashboard(student_routes, output_path="dashboard.png")


if __name__ == "__main__":
    main()
