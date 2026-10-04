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
            const autoDetectedBadge = q.answer_auto_detected 
                ? '<span class="badge badge-gold" title="Auto mapped from PDF answer key"><i class="fa-solid fa-wand-magic-sparkles"></i> Auto-Mapped</span>'
                : '<span class="badge" style="background:#e2e8f0; color:#475569;" title="Manually edited"><i class="fa-solid fa-pen"></i> Edited</span>';

            html += `
                <div class="q-preview-item" id="q-preview-${q.q_no}">
                    <div class="q-preview-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                            <span class="badge badge-navy">Q${q.q_no}</span>
                            <span class="badge badge-gold">${q.subject || 'General'}</span>
                            ${autoDetectedBadge}
                        </div>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <label style="font-size:12px; font-weight:600; color:#333; margin:0;">Correct Answer:</label>
                            <select class="form-select form-select-sm" style="display:inline-block; width:auto; padding:2px 8px; font-weight:bold; color:var(--green); border:1.5px solid var(--green); border-radius:4px; cursor:pointer;" onchange="updateQuestionAnswer(${q.q_no}, this.value)">
                                <option value="A" ${correctKey === 'A' ? 'selected' : ''}>Option A</option>
                                <option value="B" ${correctKey === 'B' ? 'selected' : ''}>Option B</option>
                                <option value="C" ${correctKey === 'C' ? 'selected' : ''}>Option C</option>
                                <option value="D" ${correctKey === 'D' ? 'selected' : ''}>Option D</option>
                            </select>
                        </div>
                    </div>
                    <div class="q-preview-text" style="margin-top:8px;">${q.text}</div>
                    <div class="q-preview-opts">
                        ${q.options.map(opt => `
                            <div class="q-opt-pill ${opt.key === correctKey ? 'is-correct' : ''}" data-key="${opt.key}">
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

async function updateQuestionAnswer(qNo, newAnswer) {
    try {
        const response = await fetch('/api/admin/update-question-answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q_no: qNo, correct_answer: newAnswer })
        });
        const data = await response.json();
        if (response.ok && data.success) {
            showToast(`Q${qNo} correct answer updated to Option ${newAnswer}!`, 'success');
            const item = document.getElementById(`q-preview-${qNo}`);
            if (item) {
                item.querySelectorAll('.q-opt-pill').forEach(pill => {
                    if (pill.getAttribute('data-key') === newAnswer) {
                        pill.classList.add('is-correct');
                    } else {
                        pill.classList.remove('is-correct');
                    }
                });
            }
        } else {
            showToast(data.detail || 'Failed to update answer.', 'error');
        }
    } catch (err) {
        showToast('Error updating question answer.', 'error');
    }
}

function closeQuestionsModal() {
    document.getElementById('questionsModal').classList.remove('open');
}

