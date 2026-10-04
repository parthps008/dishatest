// Admin Dashboard JavaScript

document.addEventListener('DOMContentLoaded', () => {
    initDropzone();
});

// Dropzone Initialization
function initDropzone() {
    const dropzone = document.getElementById('pdfDropzone');
    if (!dropzone) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            const fileInput = document.getElementById('pdfFileInput');
            fileInput.files = files;
            handleFileSelect(fileInput);
        }
    });
}

function handleFileSelect(input) {
    const file = input.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Please select a valid PDF file.', 'error');
        input.value = '';
        document.getElementById('fileSelectionBadge').style.display = 'none';
        return;
    }

    const badge = document.getElementById('fileSelectionBadge');
    const nameEl = document.getElementById('selectedFileName');
    const sizeEl = document.getElementById('selectedFileSize');

    nameEl.textContent = file.name;
    sizeEl.textContent = `(${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    badge.style.display = 'inline-flex';
}

function toggleCustomDuration(val) {
    const customInput = document.getElementById('customDurationInput');
    if (val === 'custom') {
        customInput.style.display = 'inline-block';
        customInput.focus();
    } else {
        customInput.style.display = 'none';
    }
}

function getSelectedDuration() {
    const select = document.getElementById('durationSelect');
    if (select.value === 'custom') {
        const customVal = parseInt(document.getElementById('customDurationInput').value, 10);
        return isNaN(customVal) || customVal <= 0 ? 30 : customVal;
    }
    return parseInt(select.value, 10) || 30;
}

// Upload & Generate Test Handler
async function handlePdfUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('pdfFileInput');
    const file = fileInput.files[0];

    if (!file) {
        showToast('Please select a PDF file first.', 'error');
        return;
    }

    const duration = getSelectedDuration();
    const titleOverride = document.getElementById('titleOverrideInput').value.trim();

    const generateBtn = document.getElementById('generateBtn');
    const originalBtnHtml = generateBtn.innerHTML;
    generateBtn.disabled = true;
    generateBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>Parsing PDF & Generating Test...</span>`;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('duration', duration);
    if (titleOverride) {
        formData.append('title_override', titleOverride);
    }

    try {
        const response = await fetch('/api/admin/upload-pdf', {
            method: 'POST',
            body: formData
        });

        if (response.status === 401) {
            showToast('Session expired. Redirecting to admin login...', 'error');
            setTimeout(() => { window.location.href = '/admin/login?msg=session_expired'; }, 1000);
            return;
        }

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(data.message || 'Test generated successfully!', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1200);
        } else {
            showToast(data.detail || 'Failed to generate test from PDF.', 'error');
            generateBtn.disabled = false;
            generateBtn.innerHTML = originalBtnHtml;
        }
    } catch (err) {
        console.error(err);
        showToast('Network error while uploading PDF.', 'error');
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalBtnHtml;
    }
}

// Delete Active Test & Associated Student Logs
async function confirmDeleteTest() {
    if (!confirm('Are you sure you want to delete the active test? All student submission records and the leaderboard for this test will also be permanently deleted so you can start fresh with a new test.')) {
        return;
    }

    try {
        const response = await fetch('/api/admin/delete-test', {
            method: 'DELETE'
        });

        if (response.status === 401) {
            showToast('Session expired. Redirecting to admin login...', 'error');
            setTimeout(() => { window.location.href = '/admin/login?msg=session_expired'; }, 1000);
            return;
        }

        const data = await response.json();
        if (response.ok && data.success) {
            showToast('Active test and all its student logs have been deleted successfully.', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showToast(data.detail || 'Could not delete test.', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('Network error deleting test.', 'error');
    }
}

// Load Sample Test
async function loadSampleTestPrompt() {
    if (!confirm('Load the sample Disha Academy JEE/NEET Mock Test (25 questions, Physics/Chem/Maths)? This will set it as the active test.')) {
        return;
    }

    try {
        const response = await fetch('/api/admin/load-sample');

        if (response.status === 401) {
            showToast('Session expired. Redirecting to admin login...', 'error');
            setTimeout(() => { window.location.href = '/admin/login?msg=session_expired'; }, 1000);
            return;
        }

        const data = await response.json();
        if (response.ok && data.success) {
            showToast('Sample test loaded successfully!', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showToast(data.detail || 'Failed to load sample test.', 'error');
        }
    } catch (err) {
        showToast('Error loading sample test.', 'error');
    }
}

// Inspect Questions Modal
async function openQuestionsModal() {
    const modal = document.getElementById('questionsModal');
    const container = document.getElementById('modalQuestionsList');
    modal.classList.add('open');
    container.innerHTML = '<p><i class="fa-solid fa-spinner fa-spin"></i> Fetching questions...</p>';

    try {
        const response = await fetch('/api/admin/active-test');
        const data = await response.json();
        const test = data.active_test;

        if (!test || !test.questions || test.questions.length === 0) {
            container.innerHTML = '<p>No questions found in active test.</p>';
            return;
        }

        let html = '';
        test.questions.forEach(q => {
            const correctKey = (q.correct_answer || 'A').toUpperCase();
            html += `
                <div class="q-preview-item">
                    <div class="q-preview-header">
                        <span class="badge badge-navy">Q${q.q_no}</span>
                        <span class="badge badge-gold">${q.subject || 'General'}</span>
                        <span class="badge badge-green">Correct: Option ${correctKey}</span>
                    </div>
                    <div class="q-preview-text">${q.text}</div>
                    <div class="q-preview-opts">
                        ${q.options.map(opt => `
                            <div class="q-opt-pill ${opt.key === correctKey ? 'is-correct' : ''}">
                                <strong>(${opt.key})</strong> ${opt.text}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = '<p class="text-maroon">Error loading questions details.</p>';
    }
}

function closeQuestionsModal() {
    document.getElementById('questionsModal').classList.remove('open');
}
