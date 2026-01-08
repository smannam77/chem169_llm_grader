// GraderBot Frontend Application

// State
let currentSingleResult = null;
let currentBatchResults = null;

// DOM Elements
const tabLinks = document.querySelectorAll('.tab-link');
const tabContents = document.querySelectorAll('.tab-content');

// Tab Navigation
tabLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetTab = link.dataset.tab;

        // Update active states
        tabLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        tabContents.forEach(content => {
            content.classList.add('hidden');
            if (content.id === `${targetTab}-tab`) {
                content.classList.remove('hidden');
            }
        });
    });
});

// Single Grading Form
const singleForm = document.getElementById('single-form');
const singleProgress = document.getElementById('single-progress');
const singleResults = document.getElementById('single-results');
const singleError = document.getElementById('single-error');

singleForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Hide previous results/errors
    singleResults.classList.add('hidden');
    singleError.classList.add('hidden');
    singleProgress.classList.remove('hidden');

    const formData = new FormData(singleForm);

    try {
        const response = await fetch('/api/grade', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Grading failed');
        }

        const result = await response.json();
        currentSingleResult = result;
        displaySingleResults(result);

    } catch (error) {
        displaySingleError(error.message);
    } finally {
        singleProgress.classList.add('hidden');
    }
});

function displaySingleResults(result) {
    // Summary
    document.getElementById('summary-text').textContent = result.overall_summary || 'No summary available.';

    // Exercises
    const container = document.getElementById('exercises-container');
    container.innerHTML = '';

    result.exercises.forEach(ex => {
        const card = document.createElement('article');
        card.className = `exercise-card ${ex.rating.toLowerCase()}`;

        const ratingBadge = {
            'EXCELLENT': 'Excellent',
            'OK': 'OK',
            'NEEDS_WORK': 'Needs Work'
        }[ex.rating] || ex.rating;

        card.innerHTML = `
            <header>
                <strong>${ex.exercise_id}</strong>
                <span class="rating-badge ${ex.rating.toLowerCase()}">${ratingBadge}</span>
            </header>
            <p>${ex.rationale || 'No feedback provided.'}</p>
            ${ex.missing_or_wrong && ex.missing_or_wrong.length > 0 ? `
                <details>
                    <summary>Issues to Address</summary>
                    <ul>
                        ${ex.missing_or_wrong.map(item => `<li>${item}</li>`).join('')}
                    </ul>
                </details>
            ` : ''}
            ${ex.flags && ex.flags.length > 0 ? `
                <p class="flags">Flags: ${ex.flags.join(', ')}</p>
            ` : ''}
        `;

        container.appendChild(card);
    });

    singleResults.classList.remove('hidden');
}

function displaySingleError(message) {
    document.getElementById('error-text').textContent = message;
    singleError.classList.remove('hidden');
}

// Download handlers for single grading
document.getElementById('download-json').addEventListener('click', () => {
    if (currentSingleResult) {
        downloadJSON(currentSingleResult, 'grading_result.json');
    }
});

document.getElementById('download-txt').addEventListener('click', async () => {
    if (currentSingleResult) {
        try {
            const response = await fetch('/api/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentSingleResult),
            });
            const text = await response.text();
            downloadText(text, 'grading_report.txt');
        } catch (error) {
            alert('Failed to generate report: ' + error.message);
        }
    }
});

// Batch Grading Form
const batchForm = document.getElementById('batch-form');
const batchProgress = document.getElementById('batch-progress');
const batchResults = document.getElementById('batch-results');
const batchError = document.getElementById('batch-error');
const batchSubmissionsInput = document.getElementById('batch-submissions-files');

// File selection display
batchSubmissionsInput.addEventListener('change', () => {
    const count = batchSubmissionsInput.files.length;
    document.getElementById('files-selected').textContent =
        count === 0 ? 'No files selected' :
        count === 1 ? '1 file selected' :
        `${count} files selected`;
});

batchForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Hide previous results/errors
    batchResults.classList.add('hidden');
    batchError.classList.add('hidden');
    batchProgress.classList.remove('hidden');

    const formData = new FormData();
    formData.append('solution', document.getElementById('batch-solution-file').files[0]);
    formData.append('provider', document.getElementById('batch-provider').value);

    // Add all submission files
    const submissions = batchSubmissionsInput.files;
    for (let i = 0; i < submissions.length; i++) {
        formData.append('submissions', submissions[i]);
    }

    const progressBar = document.getElementById('batch-progress-bar');
    const progressText = document.getElementById('batch-progress-text');
    progressText.textContent = `Grading ${submissions.length} notebooks...`;
    progressBar.removeAttribute('value'); // Indeterminate progress

    try {
        const response = await fetch('/api/batch', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Batch grading failed');
        }

        const result = await response.json();
        currentBatchResults = result;
        displayBatchResults(result);

    } catch (error) {
        displayBatchError(error.message);
    } finally {
        batchProgress.classList.add('hidden');
    }
});

function displayBatchResults(results) {
    // Stats
    document.getElementById('batch-total').textContent = results.total;
    document.getElementById('batch-success').textContent = results.successful;
    document.getElementById('batch-failed').textContent = results.failed;

    // Table
    const tbody = document.getElementById('batch-results-body');
    tbody.innerHTML = '';

    results.results.forEach((item, index) => {
        const row = document.createElement('tr');

        if (item.success) {
            const result = item.result;
            const excellent = result.exercises.filter(e => e.rating === 'EXCELLENT').length;
            const ok = result.exercises.filter(e => e.rating === 'OK').length;
            const needsWork = result.exercises.filter(e => e.rating === 'NEEDS_WORK').length;

            row.innerHTML = `
                <td>${item.student_id || item.filename}</td>
                <td><span class="status-badge success">Graded</span></td>
                <td>${excellent}</td>
                <td>${ok}</td>
                <td>${needsWork}</td>
                <td>
                    <button class="small secondary view-btn" data-index="${index}">View</button>
                    <button class="small secondary download-btn" data-index="${index}">Download</button>
                </td>
            `;
        } else {
            row.innerHTML = `
                <td>${item.student_id || item.filename}</td>
                <td><span class="status-badge error">Failed</span></td>
                <td colspan="3">${item.error}</td>
                <td>-</td>
            `;
        }

        tbody.appendChild(row);
    });

    // Add event listeners for view/download buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.dataset.index);
            const item = currentBatchResults.results[index];
            if (item.success) {
                showResultModal(item);
            }
        });
    });

    document.querySelectorAll('.download-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.dataset.index);
            const item = currentBatchResults.results[index];
            if (item.success) {
                downloadJSON(item.result, `${item.student_id || 'result'}.json`);
            }
        });
    });

    batchResults.classList.remove('hidden');
}

function displayBatchError(message) {
    document.getElementById('batch-error-text').textContent = message;
    batchError.classList.remove('hidden');
}

// Download all as ZIP
document.getElementById('download-all-zip').addEventListener('click', async () => {
    if (currentBatchResults) {
        try {
            const response = await fetch('/api/download-batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentBatchResults),
            });

            if (!response.ok) {
                throw new Error('Failed to generate ZIP');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'grading_results.zip';
            a.click();
            URL.revokeObjectURL(url);

        } catch (error) {
            alert('Failed to download ZIP: ' + error.message);
        }
    }
});

// Modal for viewing individual batch results
function showResultModal(item) {
    // Create modal
    const modal = document.createElement('dialog');
    modal.className = 'result-modal';

    const result = item.result;
    const exercisesHtml = result.exercises.map(ex => {
        const ratingBadge = {
            'EXCELLENT': 'Excellent',
            'OK': 'OK',
            'NEEDS_WORK': 'Needs Work'
        }[ex.rating] || ex.rating;

        return `
            <div class="exercise-card ${ex.rating.toLowerCase()}">
                <strong>${ex.exercise_id}</strong>
                <span class="rating-badge ${ex.rating.toLowerCase()}">${ratingBadge}</span>
                <p>${ex.rationale || 'No feedback.'}</p>
            </div>
        `;
    }).join('');

    modal.innerHTML = `
        <article>
            <header>
                <strong>${item.student_id || item.filename}</strong>
                <button class="close-modal" aria-label="Close">&times;</button>
            </header>
            <h4>Summary</h4>
            <p>${result.overall_summary}</p>
            <h4>Exercises</h4>
            ${exercisesHtml}
            <footer>
                <button class="close-modal-btn">Close</button>
            </footer>
        </article>
    `;

    document.body.appendChild(modal);
    modal.showModal();

    // Close handlers
    modal.querySelector('.close-modal').addEventListener('click', () => {
        modal.close();
        modal.remove();
    });
    modal.querySelector('.close-modal-btn').addEventListener('click', () => {
        modal.close();
        modal.remove();
    });
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.close();
            modal.remove();
        }
    });
}

// Utility functions
function downloadJSON(data, filename) {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

function downloadText(text, filename) {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// Check API status on load
async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        console.log('GraderBot API status:', status);

        // Update provider dropdowns based on available providers
        if (status.providers && status.providers.length > 0) {
            const defaultProvider = status.providers[0];
            document.getElementById('provider').value = defaultProvider;
            document.getElementById('batch-provider').value = defaultProvider;
        }
    } catch (error) {
        console.error('Failed to check API status:', error);
    }
}

checkStatus();
