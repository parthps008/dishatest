// Disha Academy - MHT-CET Style Computer Based Test (CBT) Logic

let currentIndex = 0; // 0-based index of currently displayed question
let totalQuestions = 0;
let userAnswers = {}; // Map: q_no -> "A" | "B" | "C" | "D"
let questionStates = []; // Array: 'not_visited', 'not_answered', 'answered', 'review'
let currentSubjectFilter = 'ALL';

let timeRemaining = 0; // in seconds
let totalExamSeconds = 0;
let timerInterval = null;
let isSubmitted = false;
let isExamInitialized = false;

// Fail-safe initialization for all browser load states
function safeInitExam() {
    if (isExamInitialized) return;
    isExamInitialized = true;
    initExam();
    preventBackNavigation();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', safeInitExam);
} else {
    safeInitExam();
}
window.addEventListener('load', safeInitExam);

// Prevent Back Navigation & Warn on Exit
function preventBackNavigation() {
    window.history.pushState(null, "", window.location.href);
    window.addEventListener("popstate", () => {
        window.history.pushState(null, "", window.location.href);
        if (typeof showToast === 'function') {
            showToast("Use on-screen navigation buttons or the Question Palette to navigate.", "info");
        }
    });

    window.addEventListener("beforeunload", (e) => {
        if (!isSubmitted) {
            e.preventDefault();
            e.returnValue = "Are you sure you want to leave the examination? Your progress will be lost.";
            return e.returnValue;
        }
    });
}

function getTestData() {
    return window.TEST_DATA || (typeof TEST_DATA !== 'undefined' ? TEST_DATA : null);
}

function initExam() {
    const data = getTestData();
    if (!data || !data.questions || !Array.isArray(data.questions) || data.questions.length === 0) {
        console.error("No questions found in TEST_DATA:", data);
        if (typeof showToast === 'function') {
            showToast("Error: Test questions could not be loaded.", "error");
        }
        return;
    }

    totalQuestions = data.questions.length;
    totalExamSeconds = (data.duration_minutes || 30) * 60;
    timeRemaining = totalExamSeconds;

    // Initialize question states
    questionStates = new Array(totalQuestions).fill('not_visited');
    questionStates[0] = 'not_answered'; // Q1 is open and visited

    startCountdownTimer();
    renderPaletteGrid();
    loadQuestion(0);
}

// Countdown Timer
function startCountdownTimer() {
    const timerDisplay = document.getElementById('timerDisplay');
    const timerPill = document.getElementById('examTimer');
    if (!timerDisplay) return;

    function updateTimer() {
        if (timeRemaining <= 0) {
            clearInterval(timerInterval);
            timerDisplay.textContent = "00:00";
            handleTimeExpiryAutoSubmit();
            return;
        }

        const hrs = Math.floor(timeRemaining / 3600);
        const mins = Math.floor((timeRemaining % 3600) / 60);
        const secs = timeRemaining % 60;

        let formatted = "";
        if (hrs > 0) {
            formatted = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        } else {
            formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }
        timerDisplay.textContent = formatted;

        if (timerPill) {
            if (timeRemaining <= 60) {
                timerPill.classList.remove('warning');
                timerPill.classList.add('danger');
            } else if (timeRemaining <= 300) {
                timerPill.classList.add('warning');
            }
        }

        timeRemaining--;
    }

    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
}

function handleTimeExpiryAutoSubmit() {
    if (isSubmitted) return;
    openModal('timeExpiryModal');
    setTimeout(() => {
        executeSubmission(true);
    }, 1500);
}

// Normalize options array
function normalizeOptions(rawOptions) {
    if (!rawOptions) return [];
    if (Array.isArray(rawOptions)) {
        return rawOptions.map((opt, i) => {
            if (typeof opt === 'string') {
                const keys = ['A', 'B', 'C', 'D'];
                return { key: keys[i] || String(i + 1), text: opt, image_url: null };
            }
            return {
                key: opt.key || String.fromCharCode(65 + i),
                text: opt.text || '',
                image_url: opt.image_url || null
            };
        });
    }
    if (typeof rawOptions === 'object') {
        return Object.entries(rawOptions).map(([k, v]) => ({ key: k, text: String(v), image_url: null }));
    }
    return [];
}

// Load a Specific Question into the View (One question at a time)
function loadQuestion(index) {
    const data = getTestData();
    if (!data || !data.questions) return;
    if (index < 0 || index >= totalQuestions) return;

    currentIndex = index;
    const q = data.questions[index];
    const displayNum = q.display_q_no || (index + 1);
    const qKey = q.q_no || (index + 1);

    // If this question was never visited, mark it as visited / not_answered (RED)
    if (questionStates[index] === 'not_visited') {
        questionStates[index] = 'not_answered';
    }

    // Question Number & Subject
    const numEl = document.getElementById('qNumberDisplay');
    if (numEl) numEl.textContent = `Question No. ${displayNum} of ${totalQuestions}`;

    const subjEl = document.getElementById('qSubjectBadge');
    if (subjEl) subjEl.textContent = q.subject || 'General';

    // Update status badge
    updateCurrentQuestionStatusBadge(index);

    // Question Statement (Auto-hide redundant "Question N" text when image diagram is present)
    const textEl = document.getElementById('qTextDisplay');
    if (textEl) {
        const isGenericStatement = !q.text || /^Question\s*\d+$/i.test(q.text.trim());
        if (q.image_url && isGenericStatement) {
            textEl.style.display = 'none';
        } else {
            textEl.style.display = 'block';
            textEl.textContent = q.text || `Question ${displayNum}`;
        }
    }

    // Question Diagram / Image
    const diagramContainer = document.getElementById('qDiagramContainer');
    const diagramImg = document.getElementById('qDiagramImg');
    if (diagramContainer && diagramImg) {
        if (q.image_url) {
            diagramImg.src = q.image_url;
            diagramContainer.style.display = 'block';
        } else {
            diagramContainer.style.display = 'none';
            diagramImg.src = '';
        }
    }

    // Render Options
    const selectedOption = userAnswers[qNum] || null;
    const optionsContainer = document.getElementById('optionsContainer');
    
    if (optionsContainer) {
        const options = normalizeOptions(q.options);
        const isGenericOptText = options.every(opt => !opt.text || opt.text.trim().toLowerCase() === `option ${opt.key.toLowerCase()}` || opt.text.trim().toLowerCase() === opt.key.toLowerCase());
        const isCompact = options.length === 4 && (isGenericOptText || options.every(opt => !opt.image_url && (!opt.text || opt.text.trim().length <= 25)));
        
        if (isCompact) {
            optionsContainer.classList.add('compact-options-grid');
        } else {
            optionsContainer.classList.remove('compact-options-grid');
        }
        let html = "";
        options.forEach(opt => {
            const isChecked = (selectedOption === opt.key);
            const optImgHtml = opt.image_url ? `
                <div style="margin-top: 6px;">
                    <img src="${opt.image_url}" style="max-height: 120px; max-width: 100%; object-fit: contain; border-radius: 4px; border: 1px solid #cbd5e1; cursor: zoom-in; background: white;" onclick="event.stopPropagation(); openDiagramLightbox('${opt.image_url}')" alt="Option ${opt.key} image">
                </div>
            ` : '';
            const displayText = (isGenericOptText && q.image_url) ? `Option ${opt.key}` : escapeHtml(opt.text);
            html += `
                <label class="cbt-option-item ${isCompact ? 'cbt-opt-compact' : ''} ${isChecked ? 'selected' : ''}" 
                       onclick="selectOptionChoice('${opt.key}', this)"
                       title="Select Option ${opt.key}">
                    <input type="radio" name="cbt_option" value="${opt.key}" 
                           class="cbt-option-radio" ${isChecked ? 'checked' : ''}>
                    <span class="cbt-option-badge">${opt.key}</span>
                    <span class="cbt-option-text">
                        ${displayText}
                        ${optImgHtml}
                    </span>
                    <i class="fa-solid fa-circle-check cbt-opt-check-icon"></i>
                </label>
            `;
        });
        optionsContainer.innerHTML = html;
    }

    // Previous Button Disabled on Q1
    const prevBtn = document.getElementById('prevBtn');
    if (prevBtn) prevBtn.disabled = (index === 0);

    // Update Palette highlights and Legend
    updatePaletteDisplay();
    updateLegendCounters();

    // Scroll to top of card smoothly
    window.scrollTo({ top: 80, behavior: 'smooth' });
}

function updateCurrentQuestionStatusBadge(index) {
    const badge = document.getElementById('qCurrentStatusBadge');
    if (!badge) return;
    badge.className = 'q-current-status-badge';
    const state = questionStates[index];

    if (state === 'answered') {
        badge.classList.add('status-answered');
        badge.textContent = 'Answered';
    } else if (state === 'review') {
        badge.classList.add('status-review');
        badge.textContent = 'Marked for Review';
    } else if (state === 'not_answered') {
        badge.classList.add('status-not-answered');
        badge.textContent = 'Not Answered';
    } else {
        badge.classList.add('status-not-visited');
        badge.textContent = 'Not Visited';
    }
}

// Option Radio Selection Handler
function selectOptionChoice(key, labelEl) {
    const data = getTestData();
    const q = data.questions[currentIndex];
    const qNum = q.q_no || (currentIndex + 1);

    userAnswers[qNum] = key;

    const labels = document.querySelectorAll('.cbt-option-item');
    labels.forEach(l => l.classList.remove('selected'));
    if (labelEl) labelEl.classList.add('selected');

    const radio = labelEl ? labelEl.querySelector('input[type="radio"]') : null;
    if (radio) radio.checked = true;
}

// Clear Current Response
function clearCurrentResponse() {
    const data = getTestData();
    const q = data.questions[currentIndex];
    const qNum = q.q_no || (currentIndex + 1);

    delete userAnswers[qNum];

    const labels = document.querySelectorAll('.cbt-option-item');
    labels.forEach(l => {
        l.classList.remove('selected');
        const radio = l.querySelector('input[type="radio"]');
        if (radio) radio.checked = false;
    });

    // Reset state to not_answered (RED)
    questionStates[currentIndex] = 'not_answered';
    updateCurrentQuestionStatusBadge(currentIndex);
    updatePaletteDisplay();
    updateLegendCounters();
    if (typeof showToast === 'function') {
        showToast(`Response cleared for Question ${qNum}.`, 'info');
    }
}

// Finalize state of current question before moving away
function evaluateCurrentBeforeMoving() {
    const data = getTestData();
    if (!data || !data.questions) return;
    const q = data.questions[currentIndex];
    const qNum = q.q_no || (currentIndex + 1);
    const hasAnswer = Boolean(userAnswers[qNum]);

    if (questionStates[currentIndex] === 'review') {
        return;
    }

    if (hasAnswer) {
        questionStates[currentIndex] = 'answered'; // GREEN
    } else {
        questionStates[currentIndex] = 'not_answered'; // RED
    }
}

// Save & Next Button
function saveAndNextQuestion() {
    const data = getTestData();
    const q = data.questions[currentIndex];
    const qNum = q.q_no || (currentIndex + 1);
    const hasAnswer = Boolean(userAnswers[qNum]);

    if (hasAnswer) {
        questionStates[currentIndex] = 'answered'; // GREEN
    } else {
        questionStates[currentIndex] = 'not_answered'; // RED
        if (typeof showToast === 'function') {
            showToast(`Question ${qNum} marked as Not Answered (Red).`, 'info');
        }
    }

    if (currentIndex < totalQuestions - 1) {
        loadQuestion(currentIndex + 1);
    } else {
        updatePaletteDisplay();
        updateLegendCounters();
        if (typeof showToast === 'function') {
            showToast("You are on the last question.", "info");
        }
    }
}

// Next Button (Skip / Move forward)
function goToNextQuestion() {
    evaluateCurrentBeforeMoving();
    if (currentIndex < totalQuestions - 1) {
        loadQuestion(currentIndex + 1);
    } else {
        updatePaletteDisplay();
        updateLegendCounters();
        if (typeof showToast === 'function') {
            showToast("You are on the last question.", "info");
        }
    }
}

// Previous Button
function goToPreviousQuestion() {
    if (currentIndex > 0) {
        evaluateCurrentBeforeMoving();
        loadQuestion(currentIndex - 1);
    }
}

// Mark for Review & Next
function markForReviewAndNext() {
    questionStates[currentIndex] = 'review'; // PURPLE
    if (currentIndex < totalQuestions - 1) {
        loadQuestion(currentIndex + 1);
    } else {
        updatePaletteDisplay();
        updateLegendCounters();
        if (typeof showToast === 'function') {
            showToast("Question marked for review.", "info");
        }
    }
}

// Jump directly to ANY question via the Reference Palette Box
function jumpToQuestion(targetIndex) {
    if (targetIndex === currentIndex) return;
    evaluateCurrentBeforeMoving();
    loadQuestion(targetIndex);
}

// Render the Reference Boxes Palette (1, 2, 3... N)
function renderPaletteGrid() {
    const grid = document.getElementById('paletteGrid');
    if (!grid) return;
    const data = getTestData();
    if (!data || !data.questions) return;

    // If already pre-rendered by server, just attach data and ensure all boxes exist
    if (grid.children.length === data.questions.length) {
        updatePaletteDisplay();
        return;
    }

    let html = "";
    data.questions.forEach((q, idx) => {
        const displayNum = q.display_q_no || (idx + 1);
        const subj = q.subject || 'General';
        html += `
            <div class="palette-box state-not-visited" 
                 id="palette_box_${idx}" 
                 data-index="${idx}" 
                 data-subject="${subj}"
                 title="Question ${displayNum} (${subj})"
                 onclick="jumpToQuestion(${idx})">
                ${displayNum}
            </div>
        `;
    });

    grid.innerHTML = html;
}

// Update Palette classes and states
function updatePaletteDisplay() {
    const data = getTestData();
    if (!data || !data.questions) return;

    data.questions.forEach((q, idx) => {
        const box = document.getElementById(`palette_box_${idx}`);
        if (!box) return;

        const qNum = q.q_no || (idx + 1);
        box.className = 'palette-box';

        const state = questionStates[idx] || 'not_visited';
        box.classList.add(`state-${state}`);

        if (state === 'review' && userAnswers[qNum]) {
            box.classList.add('has-answer');
        }

        // Active/Current open question highlight
        if (idx === currentIndex) {
            box.classList.add('is-current');
        }

        // Subject filter visibility
        if (currentSubjectFilter === 'ALL' || (q.subject || 'General').toUpperCase() === currentSubjectFilter.toUpperCase()) {
            box.style.display = 'flex';
        } else {
            box.style.display = 'none';
        }
    });
}

// Update Legend Live Counters
function updateLegendCounters() {
    let answered = 0;
    let notAnswered = 0;
    let notVisited = 0;
    let review = 0;

    questionStates.forEach((st) => {
        if (st === 'answered') {
            answered++;
        } else if (st === 'not_answered') {
            notAnswered++;
        } else if (st === 'review') {
            review++;
        } else {
            notVisited++;
        }
    });

    const elA = document.getElementById('countAnswered');
    if (elA) elA.textContent = answered;

    const elNA = document.getElementById('countNotAnswered');
    if (elNA) elNA.textContent = notAnswered;

    const elNV = document.getElementById('countNotVisited');
    if (elNV) elNV.textContent = notVisited;

    const elR = document.getElementById('countReview');
    if (elR) elR.textContent = review;
}

// Filter Palette by Subject
function filterPaletteSubject(subj, tabBtn) {
    currentSubjectFilter = subj;
    document.querySelectorAll('.subject-tab-btn').forEach(btn => btn.classList.remove('active'));
    if (tabBtn) tabBtn.classList.add('active');

    updatePaletteDisplay();

    // If current question does not belong to selected subject, jump to first matching question
    const data = getTestData();
    if (subj !== 'ALL' && data && data.questions) {
        const firstMatchIdx = data.questions.findIndex(q => (q.subject || 'General').toUpperCase() === subj.toUpperCase());
        if (firstMatchIdx !== -1 && (data.questions[currentIndex].subject || 'General').toUpperCase() !== subj.toUpperCase()) {
            jumpToQuestion(firstMatchIdx);
        }
    }
}

// Open Final Submission Summary Modal
function openSubmitModal() {
    evaluateCurrentBeforeMoving();
    updateLegendCounters();

    let answered = 0;
    let notAnswered = 0;
    let notVisited = 0;
    let review = 0;

    questionStates.forEach(st => {
        if (st === 'answered') answered++;
        else if (st === 'not_answered') notAnswered++;
        else if (st === 'review') review++;
        else notVisited++;
    });

    const elA = document.getElementById('modalAnsweredCount');
    if (elA) elA.textContent = answered;

    const elNA = document.getElementById('modalNotAnsweredCount');
    if (elNA) elNA.textContent = notAnswered;

    const elR = document.getElementById('modalReviewCount');
    if (elR) elR.textContent = review;

    const elNV = document.getElementById('modalNotVisitedCount');
    if (elNV) elNV.textContent = notVisited;

    openModal('submitModal');
}

// Execute Final Submission
async function executeSubmission(isAuto = false) {
    if (isSubmitted) return;
    isSubmitted = true;
    clearInterval(timerInterval);

    const submitBtn = document.getElementById('confirmSubmitBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Submitting Examination...`;
    }

    const timeSpent = totalExamSeconds - Math.max(0, timeRemaining);
    const data = getTestData();
    const studentName = window.STUDENT_NAME || "Candidate";
    const studentRoll = window.STUDENT_ROLL || "N/A";

    const payload = {
        test_id: data ? data.id : "",
        student_name: studentName,
        roll_no: studentRoll,
        answers: userAnswers,
        time_taken_seconds: timeSpent,
        auto_submitted: isAuto
    };

    try {
        const response = await fetch('/api/test/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const resData = await response.json();
        if (response.ok && resData.success) {
            const isAdmin = window.location.search.includes('from=admin') || (function(){
                try { return localStorage.getItem('disha_admin_active') === '1'; } catch(e){ return false; }
            })();
            const targetUrl = isAdmin ? `${resData.redirect_url}?from=admin` : resData.redirect_url;
            window.location.href = targetUrl;
        } else {
            if (typeof showToast === 'function') {
                showToast(resData.detail || "Submission failed. Please contact the invigilator.", "error");
            }
            isSubmitted = false;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = `Retry Submission`;
            }
        }
    } catch (err) {
        console.error(err);
        if (typeof showToast === 'function') {
            showToast("Network error submitting test.", "error");
        }
        isSubmitted = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `Retry Submission`;
        }
    }
}

// Modal Helpers
function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('open');
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('open');
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Diagram Lightbox for enlarging question diagrams
function openDiagramLightbox(src) {
    if (!src) return;
    let modal = document.getElementById('diagramLightbox');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'diagramLightbox';
        modal.className = 'diagram-lightbox-modal';
        modal.innerHTML = `
            <div class="diagram-lightbox-backdrop" onclick="closeDiagramLightbox()"></div>
            <div class="diagram-lightbox-content">
                <button type="button" class="diagram-lightbox-close" onclick="closeDiagramLightbox()">&times;</button>
                <img src="" id="lightboxModalImg" class="diagram-lightbox-img" alt="Zoomed Diagram">
                <div class="diagram-lightbox-hint">Click outside or press ESC to close</div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    const imgEl = document.getElementById('lightboxModalImg');
    if (imgEl) imgEl.src = src;
    modal.classList.add('open');
}

function closeDiagramLightbox() {
    const modal = document.getElementById('diagramLightbox');
    if (modal) modal.classList.remove('open');
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDiagramLightbox();
});
