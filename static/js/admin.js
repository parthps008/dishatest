// Admin Dashboard JavaScript

document.addEventListener('DOMContentLoaded', () => {
    initDropzone();
    initImagesDropzone();
    initPdfSliceDropzone();
    initPhotoPaperDropzone();
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

// ===================================================
// Creation Mode Menu (PDF vs Images vs Auto-Slice PDF)
// ===================================================
function switchCreationMenu(mode) {
    const btnPdf = document.getElementById('menuBtnPdf');
    const btnImages = document.getElementById('menuBtnImages');
    const btnPdfSlice = document.getElementById('menuBtnPdfSlice');
    const btnPhotoPaper = document.getElementById('menuBtnPhotoPaper');
    const panePdf = document.getElementById('pdfUploadPane');
    const paneImages = document.getElementById('imageUploadPane');
    const panePdfSlice = document.getElementById('pdfSliceUploadPane');
    const panePhotoPaper = document.getElementById('photoPaperUploadPane');

    if (!btnPdf || !btnImages || !panePdf || !paneImages) return;

    // Clear active classes and hide all panes
    [btnPdf, btnImages, btnPdfSlice, btnPhotoPaper].forEach(b => b && b.classList.remove('active'));
    [panePdf, paneImages, panePdfSlice, panePhotoPaper].forEach(p => p && (p.style.display = 'none'));

    if (mode === 'images') {
        if (btnImages) btnImages.classList.add('active');
        if (paneImages) paneImages.style.display = 'block';
    } else if (mode === 'pdf_slice') {
        if (btnPdfSlice) btnPdfSlice.classList.add('active');
        if (panePdfSlice) panePdfSlice.style.display = 'block';
    } else if (mode === 'photo_paper') {
        if (btnPhotoPaper) btnPhotoPaper.classList.add('active');
        if (panePhotoPaper) panePhotoPaper.style.display = 'block';
    } else {
        if (btnPdf) btnPdf.classList.add('active');
        if (panePdf) panePdf.style.display = 'block';
    }
}

// ===================================================
// Multi-Image Question Test Creation Logic (Up to 50 Qs)
// ===================================================
let selectedImageFilesArray = []; // Array of { file, answer, objectUrl }

function initImagesDropzone() {
    const dropzone = document.getElementById('imagesDropzone');
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
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            processIncomingImageFiles(Array.from(files));
        }
    });
}

function handleImageFilesSelect(input) {
    if (!input.files || input.files.length === 0) return;
    processIncomingImageFiles(Array.from(input.files));
    // Reset file input value so user can re-select same file if needed
    input.value = '';
}

function processIncomingImageFiles(fileList) {
    const allowed = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    const validFiles = fileList.filter(f => {
        const ext = '.' + f.name.split('.').pop().toLowerCase();
        return allowed.includes(f.type) || ['.png', '.jpg', '.jpeg', '.webp'].includes(ext);
    });

    if (validFiles.length === 0) {
        showToast('Please select valid image files (.png, .jpg, .jpeg, .webp).', 'error');
        return;
    }

    if (selectedImageFilesArray.length + validFiles.length > 50) {
        const allowedCount = 50 - selectedImageFilesArray.length;
        if (allowedCount <= 0) {
            showToast('Maximum 50 images limit reached. Cannot add more images.', 'error');
            return;
        }
        showToast(`Only first ${allowedCount} images added. Maximum limit is 50 images per test.`, 'warning');
        validFiles.splice(allowedCount);
    }

    validFiles.forEach(file => {
        selectedImageFilesArray.push({
            file: file,
            answer: 'A',
            objectUrl: URL.createObjectURL(file)
        });
    });

    renderImagesPreviewTable();
    showToast(`Added ${validFiles.length} image(s). Total: ${selectedImageFilesArray.length}/50 questions.`, 'success');
}

function renderImagesPreviewTable() {
    const container = document.getElementById('selectedImagesContainer');
    const tbody = document.getElementById('imagesTableBody');
    const countBadge = document.getElementById('imagesCountBadge');
    const submitBtn = document.getElementById('generateImagesBtn');
    const submitBtnText = document.getElementById('generateImagesBtnText');

    if (!container || !tbody) return;

    const count = selectedImageFilesArray.length;

    if (count === 0) {
        container.style.display = 'none';
        tbody.innerHTML = '';
        if (submitBtn) {
            submitBtn.disabled = true;
            if (submitBtnText) submitBtnText.textContent = 'Select Images to Create Test';
        }
        return;
    }

    container.style.display = 'block';
    if (countBadge) countBadge.textContent = `${count} Images Selected (${count} Questions)`;

    if (submitBtn) {
        submitBtn.disabled = false;
        if (submitBtnText) submitBtnText.textContent = `Generate Image Test (${count} Questions)`;
    }

    let rowsHtml = '';
    selectedImageFilesArray.forEach((item, index) => {
        const qNum = index + 1;
        const fileSizeStr = (item.file.size / 1024).toFixed(1) + ' KB';

        rowsHtml += `
            <tr>
                <td><span class="badge badge-navy" style="font-size: 0.85rem; font-weight: 800;">Q${qNum}</span></td>
                <td>
                    <img src="${item.objectUrl}" class="img-table-thumb" alt="Q${qNum}" onclick="window.open('${item.objectUrl}', '_blank')" title="Click to view full image">
                </td>
                <td>
                    <div style="font-weight: 700; color: var(--primary-navy); word-break: break-all; font-size: 0.88rem;">${escapeHtml(item.file.name)}</div>
                    <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 2px;">
                        <i class="fa-solid fa-file-image"></i> ${fileSizeStr} &bull; Mapped to Question ${qNum}
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <label style="font-size: 11px; font-weight: 700; color: #475569; margin: 0;">Key:</label>
                        <select class="form-select form-select-sm image-q-ans-select" onchange="setImageQuestionAnswer(${index}, this.value)">
                            <option value="A" ${item.answer === 'A' ? 'selected' : ''}>Option A</option>
                            <option value="B" ${item.answer === 'B' ? 'selected' : ''}>Option B</option>
                            <option value="C" ${item.answer === 'C' ? 'selected' : ''}>Option C</option>
                            <option value="D" ${item.answer === 'D' ? 'selected' : ''}>Option D</option>
                        </select>
                    </div>
                </td>
                <td style="text-align: center;">
                    <button type="button" class="btn btn-outline" style="padding: 3px 8px; font-size: 0.8rem; color: var(--accent-maroon); border-color: #fca5a5;" onclick="removeSelectedImage(${index})" title="Remove this screenshot">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

function setImageQuestionAnswer(index, val) {
    if (index >= 0 && index < selectedImageFilesArray.length) {
        selectedImageFilesArray[index].answer = (val || 'A').toUpperCase();
    }
}

function removeSelectedImage(index) {
    if (index >= 0 && index < selectedImageFilesArray.length) {
        const removed = selectedImageFilesArray.splice(index, 1)[0];
        if (removed && removed.objectUrl) {
            try { URL.revokeObjectURL(removed.objectUrl); } catch (e) {}
        }
        renderImagesPreviewTable();
    }
}

function bulkSetAllImageAnswers(val) {
    val = (val || 'A').toUpperCase();
    selectedImageFilesArray.forEach(item => {
        item.answer = val;
    });
    renderImagesPreviewTable();
    showToast(`All ${selectedImageFilesArray.length} question answers set to Option ${val}.`, 'info');
}

function clearAllSelectedImages() {
    selectedImageFilesArray.forEach(item => {
        if (item.objectUrl) {
            try { URL.revokeObjectURL(item.objectUrl); } catch (e) {}
        }
    });
    selectedImageFilesArray = [];
    renderImagesPreviewTable();
}

function toggleCustomImgDuration(val) {
    const customInput = document.getElementById('customImgDurationInput');
    if (!customInput) return;
    if (val === 'custom') {
        customInput.style.display = 'inline-block';
        customInput.focus();
    } else {
        customInput.style.display = 'none';
    }
}

function getSelectedImgDuration() {
    const select = document.getElementById('imgDurationSelect');
    if (!select) return 30;
    if (select.value === 'custom') {
        const customVal = parseInt(document.getElementById('customImgDurationInput').value, 10);
        return isNaN(customVal) || customVal <= 0 ? 30 : customVal;
    }
    return parseInt(select.value, 10) || 30;
}

// Hardware-accelerated browser-side image optimizer (converts 4-8MB mobile screenshots to crisp ~70KB JPEGs in ~15ms)
function fastCompressImage(file, maxWidth = 1200, quality = 0.82) {
    return new Promise((resolve) => {
        if (!file || !file.type || !file.type.startsWith('image/')) {
            resolve(file);
            return;
        }

        // If file is already smaller than 150KB and already a JPEG, keep it as is
        if (file.size <= 150 * 1024 && (file.type === 'image/jpeg' || file.name.toLowerCase().endsWith('.jpg'))) {
            resolve(file);
            return;
        }

        const img = new Image();
        const url = URL.createObjectURL(file);

        img.onload = () => {
            URL.revokeObjectURL(url);
            try {
                let width = img.naturalWidth || img.width;
                let height = img.naturalHeight || img.height;

                if (!width || !height) {
                    resolve(file);
                    return;
                }

                if (width > maxWidth) {
                    height = Math.round((height * maxWidth) / width);
                    width = maxWidth;
                }

                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                canvas.toBlob(
                    (blob) => {
                        if (blob && blob.size < file.size) {
                            const cleanName = (file.name || 'question.jpg').replace(/\.[^.]+$/, '.jpg');
                            const compressedFile = new File([blob], cleanName, {
                                type: 'image/jpeg',
                                lastModified: Date.now()
                            });
                            resolve(compressedFile);
                        } else {
                            resolve(file);
                        }
                    },
                    'image/jpeg',
                    quality
                );
            } catch (e) {
                console.warn('Canvas compression fallback to raw file', e);
                resolve(file);
            }
        };

        img.onerror = () => {
            URL.revokeObjectURL(url);
            resolve(file);
        };

        img.src = url;
    });
}

async function handleImageTestUpload(e) {
    if (e && e.preventDefault) e.preventDefault();

    if (selectedImageFilesArray.length === 0) {
        showToast('Please select at least 1 question screenshot image.', 'error');
        return;
    }

    if (selectedImageFilesArray.length > 50) {
        showToast('Maximum 50 images allowed per test.', 'error');
        return;
    }

    const duration = getSelectedImgDuration();
    const title = document.getElementById('imgTitleInput').value.trim() || 'Disha Academy Image Assessment';
    const subject = document.getElementById('imgSubjectInput').value.trim() || 'General';

    const submitBtn = document.getElementById('generateImagesBtn');
    const submitBtnText = document.getElementById('generateImagesBtnText');
    const originalText = submitBtnText ? submitBtnText.innerHTML : 'Generate Test';

    submitBtn.disabled = true;

    // Step 1: Pre-compress screenshots in browser using hardware acceleration (reduces 150MB -> ~3MB in under 1 second!)
    const totalCount = selectedImageFilesArray.length;
    const filesToUpload = [];

    for (let i = 0; i < totalCount; i++) {
        if (submitBtnText) {
            submitBtnText.innerHTML = `<i class="fa-solid fa-bolt fa-spin"></i> Optimizing ${i + 1}/${totalCount} Screenshots...`;
        }
        const item = selectedImageFilesArray[i];
        const compressedFile = await fastCompressImage(item.file);
        filesToUpload.push(compressedFile);
    }

    if (submitBtnText) {
        submitBtnText.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Uploading ${totalCount} Questions...`;
    }

    const formData = new FormData();
    filesToUpload.forEach(file => {
        formData.append('files', file);
    });

    const answersMap = {};
    selectedImageFilesArray.forEach((item, index) => {
        answersMap[String(index + 1)] = item.answer || 'A';
    });
    formData.append('answers_json', JSON.stringify(answersMap));
    formData.append('duration', duration);
    formData.append('title', title);
    formData.append('subject', subject);

    try {
        const response = await fetch('/api/admin/create-image-test', {
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
            showToast(data.message || 'Image test created successfully!', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1200);
        } else {
            showToast(data.detail || 'Failed to create image test.', 'error');
            submitBtn.disabled = false;
            if (submitBtnText) submitBtnText.innerHTML = originalText;
        }
    } catch (err) {
        console.error(err);
        showToast('Network error while uploading images.', 'error');
        submitBtn.disabled = false;
        if (submitBtnText) submitBtnText.innerHTML = originalText;
    }
}

// ===================================================
// Option 3: PDF to Images Auto-Slice Test Creation Logic
// ===================================================
function toggleCustomSliceDuration(val) {
    const customInput = document.getElementById('customSliceDurationInput');
    if (!customInput) return;
    if (val === 'custom') {
        customInput.style.display = 'inline-block';
        customInput.focus();
    } else {
        customInput.style.display = 'none';
    }
}

function getSelectedSliceDuration() {
    const select = document.getElementById('sliceDurationSelect');
    if (!select) return 30;
    if (select.value === 'custom') {
        const customVal = parseInt(document.getElementById('customSliceDurationInput').value, 10);
        return isNaN(customVal) || customVal <= 0 ? 30 : customVal;
    }
    return parseInt(select.value, 10) || 30;
}

function initPdfSliceDropzone() {
    const dropzone = document.getElementById('pdfSliceDropzone');
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
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            const file = files[0];
            if (file.name.toLowerCase().endsWith('.pdf')) {
                const input = document.getElementById('pdfSliceFileInput');
                input.files = files;
                updatePdfSliceFileBadge(file);
            } else {
                showToast('Only PDF files are supported.', 'error');
            }
        }
    });
}

function handlePdfSliceFileSelect(input) {
    if (input.files && input.files.length > 0) {
        updatePdfSliceFileBadge(input.files[0]);
    }
}

function updatePdfSliceFileBadge(file) {
    const badge = document.getElementById('sliceFileSelectionBadge');
    const nameEl = document.getElementById('selectedSliceFileName');
    const sizeEl = document.getElementById('selectedSliceFileSize');
    if (badge && nameEl && sizeEl) {
        nameEl.textContent = file.name;
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        sizeEl.textContent = `(${sizeMb} MB)`;
        badge.style.display = 'inline-flex';
    }
}

// Circular Progress Helper for PDF Slicing
function setSliceProgress(pct, statusTitle, statusDesc, stageIdx) {
    const ring = document.getElementById('sliceProgressRing');
    const percentEl = document.getElementById('sliceProgressPercent');
    const titleEl = document.getElementById('sliceStatusTitle');
    const descEl = document.getElementById('sliceStatusDesc');

    const C = 314.16;
    const clamped = Math.max(0, Math.min(100, pct));
    if (ring) {
        ring.style.strokeDashoffset = C - (clamped / 100) * C;
    }
    if (percentEl) {
        percentEl.textContent = `${Math.round(clamped)}%`;
    }
    if (titleEl && statusTitle) {
        titleEl.innerHTML = statusTitle;
    }
    if (descEl && statusDesc) {
        descEl.textContent = statusDesc;
    }

    if (stageIdx !== undefined) {
        for (let i = 1; i <= 5; i++) {
            const step = document.getElementById(`stageStep${i}`);
            if (step) {
                if (i < stageIdx) {
                    step.className = 'stage-step done';
                } else if (i === stageIdx) {
                    step.className = 'stage-step active';
                } else {
                    step.className = 'stage-step';
                }
            }
        }
    }
}

async function handlePdfSliceUpload(e) {
    if (e && e.preventDefault) e.preventDefault();

    const fileInput = document.getElementById('pdfSliceFileInput');
    const file = fileInput ? fileInput.files[0] : null;

    if (!file) {
        showToast('Please select a PDF file first.', 'error');
        return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Please select a valid .pdf file.', 'error');
        return;
    }

    const duration = getSelectedSliceDuration();
    const title = document.getElementById('sliceTitleInput') ? document.getElementById('sliceTitleInput').value.trim() : '';
    const subject = document.getElementById('sliceSubjectInput') ? document.getElementById('sliceSubjectInput').value.trim() : '';

    const submitBtn = document.getElementById('generateSliceBtn');
    const submitBtnText = document.getElementById('generateSliceBtnText');
    const originalText = submitBtnText ? submitBtnText.innerHTML : 'Slice PDF & Generate Test';
    const progressModal = document.getElementById('pdfSliceProgressModal');

    submitBtn.disabled = true;
    if (submitBtnText) {
        submitBtnText.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Slicing PDF & Generating Questions...`;
    }

    // Configure modal for PDF Auto-Slice
    const modalTitleEl = document.getElementById('progressModalTitle');
    const modalSubEl = document.getElementById('progressModalSub');
    if (modalTitleEl) modalTitleEl.textContent = 'Generating Questions from PDF';
    if (modalSubEl) modalSubEl.textContent = 'Auto-slicing PDF into crisp question snapshots...';

    const ring = document.getElementById('sliceProgressRing');
    const subEl = document.getElementById('sliceProgressSub');
    if (ring) ring.style.stroke = '#2563eb';
    if (subEl) {
        subEl.textContent = 'Processing';
        subEl.style.color = 'var(--text-muted)';
    }

    // Open round circular loading modal
    if (progressModal) {
        progressModal.style.display = 'flex';
    }
    setSliceProgress(8, '<i class="fa-solid fa-spinner fa-spin text-navy"></i> Reading & Analyzing PDF...', 'Sending document to server for layout detection...', 1);

    // Dynamic simulated stage progression while multi-threaded slicing processes
    let currentPct = 8;
    const progressTimer = setInterval(() => {
        if (currentPct < 25) {
            currentPct += 4;
            setSliceProgress(currentPct, '<i class="fa-solid fa-spinner fa-spin text-navy"></i> Detecting Layout & Columns...', 'Analyzing 1-column vs 2-column format...', 2);
        } else if (currentPct < 55) {
            currentPct += 5;
            setSliceProgress(currentPct, '<i class="fa-solid fa-spinner fa-spin text-navy"></i> Slicing Question Snapshots...', 'Cropping high-res snapshots of questions and diagrams...', 3);
        } else if (currentPct < 85) {
            currentPct += 4;
            setSliceProgress(currentPct, '<i class="fa-solid fa-spinner fa-spin text-navy"></i> Optimizing Math Formulas...', 'Compressing snapshots and trimming borders...', 3);
        } else if (currentPct < 94) {
            currentPct += 1;
            setSliceProgress(currentPct, '<i class="fa-solid fa-spinner fa-spin text-navy"></i> Mapping Questions & Answer Keys...', 'Mapping options A, B, C, D sequentially...', 4);
        }
    }, 180);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('duration', duration);
    if (title) formData.append('title', title);
    if (subject) formData.append('subject', subject);

    try {
        const response = await fetch('/api/admin/create-pdf-sliced-test', {
            method: 'POST',
            body: formData
        });

        clearInterval(progressTimer);

        if (response.status === 401) {
            if (progressModal) progressModal.style.display = 'none';
            showToast('Session expired. Redirecting to admin login...', 'error');
            setTimeout(() => { window.location.href = '/admin/login?msg=session_expired'; }, 1000);
            return;
        }

        const data = await response.json();

        if (response.ok && data.success) {
            const totalQ = (data.test && data.test.total_questions) ? data.test.total_questions : 'all';
            
            // Set circle to 100% completed state
            setSliceProgress(
                100,
                `<i class="fa-solid fa-circle-check text-green"></i> Completed! All ${totalQ} Test Questions Mapped!`,
                `Successfully converted PDF into ${totalQ} question snapshots and activated test.`,
                5
            );

            const ring = document.getElementById('sliceProgressRing');
            const percentEl = document.getElementById('sliceProgressPercent');
            const subEl = document.getElementById('sliceProgressSub');
            if (ring) ring.style.stroke = '#10b981';
            if (percentEl) percentEl.innerHTML = `<span style="color: #10b981;">100%</span>`;
            if (subEl) {
                subEl.textContent = 'COMPLETED';
                subEl.style.color = '#10b981';
            }

            for (let i = 1; i <= 5; i++) {
                const step = document.getElementById(`stageStep${i}`);
                if (step) step.className = 'stage-step done';
            }

            showToast(`Completed! All ${totalQ} test questions mapped!`, 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1400);
        } else {
            clearInterval(progressTimer);
            if (progressModal) progressModal.style.display = 'none';
            showToast(data.detail || 'Failed to auto-slice PDF.', 'error');
            submitBtn.disabled = false;
            if (submitBtnText) submitBtnText.innerHTML = originalText;
        }
    } catch (err) {
        clearInterval(progressTimer);
        if (progressModal) progressModal.style.display = 'none';
        console.error(err);
        showToast('Network error while slicing PDF.', 'error');
        submitBtn.disabled = false;
        if (submitBtnText) submitBtnText.innerHTML = originalText;
    }
}

// ===================================================
// Option 4: Image to Test (Paper Scan / Photo Auto-Crop) Logic
// ===================================================
let selectedPhotoPaperFilesArray = [];

function initPhotoPaperDropzone() {
    const dropzone = document.getElementById('photoPaperDropzone');
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
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            processIncomingPhotoPaperFiles(Array.from(files));
        }
    });
}

function handlePhotoPaperFileSelect(input) {
    if (!input.files || input.files.length === 0) return;
    processIncomingPhotoPaperFiles(Array.from(input.files));
    input.value = '';
}

function processIncomingPhotoPaperFiles(fileList) {
    const allowed = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    const validFiles = fileList.filter(f => {
        const ext = '.' + f.name.split('.').pop().toLowerCase();
        return allowed.includes(f.type) || ['.png', '.jpg', '.jpeg', '.webp'].includes(ext);
    });

    if (validFiles.length === 0) {
        showToast('Please select valid paper photo images (.png, .jpg, .jpeg, .webp).', 'error');
        return;
    }

    validFiles.forEach(file => {
        selectedPhotoPaperFilesArray.push(file);
    });

    updatePhotoPaperFileListDisplay();
}

function updatePhotoPaperFileListDisplay() {
    const badge = document.getElementById('photoPaperSelectionBadge');
    const countEl = document.getElementById('selectedPhotoPaperCount');
    const sizeEl = document.getElementById('selectedPhotoPaperSize');
    const wrap = document.getElementById('photoPaperListWrap');
    const listEl = document.getElementById('photoPaperFileList');

    if (!badge || !countEl || !wrap || !listEl) return;

    if (selectedPhotoPaperFilesArray.length === 0) {
        badge.style.display = 'none';
        wrap.style.display = 'none';
        listEl.innerHTML = '';
        return;
    }

    const count = selectedPhotoPaperFilesArray.length;
    let totalBytes = 0;
    selectedPhotoPaperFilesArray.forEach(f => { totalBytes += f.size; });
    const sizeMb = (totalBytes / (1024 * 1024)).toFixed(2);

    countEl.textContent = `${count} Paper Photo${count > 1 ? 's' : ''} Selected`;
    if (sizeEl) sizeEl.textContent = `(${sizeMb} MB total)`;
    badge.style.display = 'inline-flex';
    wrap.style.display = 'block';

    listEl.innerHTML = '';
    selectedPhotoPaperFilesArray.forEach((file, idx) => {
        const chip = document.createElement('div');
        chip.style.cssText = 'display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 20px; font-size: 0.78rem; color: #1e293b;';
        chip.innerHTML = `
            <i class="fa-solid fa-file-image" style="color: #16a34a;"></i>
            <span style="font-weight: 700;">Page ${idx + 1}:</span>
            <span style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.name}">${file.name}</span>
            <button type="button" style="border: none; background: transparent; cursor: pointer; color: #ef4444; font-size: 0.82rem; padding: 0 2px;" onclick="removePhotoPaperFile(${idx})">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;
        listEl.appendChild(chip);
    });
}

function removePhotoPaperFile(index) {
    if (index >= 0 && index < selectedPhotoPaperFilesArray.length) {
        selectedPhotoPaperFilesArray.splice(index, 1);
        updatePhotoPaperFileListDisplay();
    }
}

function clearPhotoPaperFiles() {
    selectedPhotoPaperFilesArray = [];
    updatePhotoPaperFileListDisplay();
}

function toggleCustomPhotoPaperDuration(val) {
    const customInput = document.getElementById('customPhotoPaperDurationInput');
    if (!customInput) return;
    if (val === 'custom') {
        customInput.style.display = 'inline-block';
        customInput.focus();
    } else {
        customInput.style.display = 'none';
    }
}

function getSelectedPhotoPaperDuration() {
    const select = document.getElementById('photoPaperDurationSelect');
    if (!select) return 30;
    if (select.value === 'custom') {
        const customVal = parseInt(document.getElementById('customPhotoPaperDurationInput').value, 10);
        return isNaN(customVal) || customVal <= 0 ? 30 : customVal;
    }
    return parseInt(select.value, 10) || 30;
}

async function handlePhotoPaperUpload(e) {
    if (e && e.preventDefault) e.preventDefault();

    if (selectedPhotoPaperFilesArray.length === 0) {
        showToast('Please select at least 1 test paper photo to scan.', 'error');
        return;
    }

    const duration = getSelectedPhotoPaperDuration();
    const title = document.getElementById('photoPaperTitleInput') ? document.getElementById('photoPaperTitleInput').value.trim() : '';
    const subject = document.getElementById('photoPaperSubjectInput') ? document.getElementById('photoPaperSubjectInput').value.trim() : '';

    const submitBtn = document.getElementById('generatePhotoPaperBtn');
    const submitBtnText = document.getElementById('generatePhotoPaperBtnText');
    const originalText = submitBtnText ? submitBtnText.innerHTML : 'Scan Photos & Generate Test';
    const progressModal = document.getElementById('pdfSliceProgressModal');

    submitBtn.disabled = true;
    if (submitBtnText) {
        submitBtnText.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Scanning Photos & Slicing Questions...`;
    }

    // Configure modal for Paper Photo AI Vision
    const modalTitleEl = document.getElementById('progressModalTitle');
    const modalSubEl = document.getElementById('progressModalSub');
    if (modalTitleEl) modalTitleEl.textContent = 'AI Vision Question Auto-Crop';
    if (modalSubEl) modalSubEl.textContent = `Analyzing ${selectedPhotoPaperFilesArray.length} paper photo(s) & extracting question snapshots...`;

    // Reset ring styles
    const ring = document.getElementById('sliceProgressRing');
    const subEl = document.getElementById('sliceProgressSub');
    if (ring) ring.style.stroke = '#2563eb';
    if (subEl) {
        subEl.textContent = 'Processing';
        subEl.style.color = 'var(--text-muted)';
    }

    if (progressModal) {
        progressModal.style.display = 'flex';
    }

    setSliceProgress(10, '<i class="fa-solid fa-camera fa-spin text-navy"></i> Reading & Preprocessing Photos...', `Uploading ${selectedPhotoPaperFilesArray.length} test paper scan(s)...`, 1);

    let currentPct = 10;
    const progressTimer = setInterval(() => {
        if (currentPct < 30) {
            currentPct += 5;
            setSliceProgress(currentPct, '<i class="fa-solid fa-microscope fa-spin text-navy"></i> Running AI Vision OCR...', 'Detecting question numbers and columns across paper pages...', 2);
        } else if (currentPct < 60) {
            currentPct += 5;
            setSliceProgress(currentPct, '<i class="fa-solid fa-crop-simple fa-spin text-navy"></i> Detecting Question Boundaries...', 'Extracting MCQs, diagrams, and formulas...', 3);
        } else if (currentPct < 85) {
            currentPct += 4;
            setSliceProgress(currentPct, '<i class="fa-solid fa-scissors fa-spin text-navy"></i> Slicing & Optimizing Question Snapshots...', 'Trimming white borders and compressing images for mobile...', 3);
        } else if (currentPct < 94) {
            currentPct += 1;
            setSliceProgress(currentPct, '<i class="fa-solid fa-map-location-dot fa-spin text-navy"></i> Mapping Questions & ABCD Options...', 'Sequentially chaining questions (Q1..Qn)...', 4);
        }
    }, 220);

    const formData = new FormData();
    selectedPhotoPaperFilesArray.forEach(file => {
        formData.append('files', file);
    });
    formData.append('duration', duration);
    if (title) formData.append('title', title);
    if (subject) formData.append('subject', subject);

    try {
        const response = await fetch('/api/admin/create-photo-test', {
            method: 'POST',
            body: formData
        });

        clearInterval(progressTimer);

        if (response.status === 401) {
            if (progressModal) progressModal.style.display = 'none';
            showToast('Session expired. Redirecting to admin login...', 'error');
            setTimeout(() => { window.location.href = '/admin/login?msg=session_expired'; }, 1000);
            return;
        }

        const data = await response.json();

        if (response.ok && data.success) {
            const totalQ = (data.test && data.test.total_questions) ? data.test.total_questions : 'all';

            setSliceProgress(
                100,
                `<i class="fa-solid fa-circle-check text-green"></i> Completed! All ${totalQ} Test Questions Mapped!`,
                `Successfully cropped ${totalQ} question screenshots from paper photos and activated test.`,
                5
            );

            if (ring) ring.style.stroke = '#10b981';
            const percentEl = document.getElementById('sliceProgressPercent');
            if (percentEl) percentEl.innerHTML = `<span style="color: #10b981;">100%</span>`;
            if (subEl) {
                subEl.textContent = 'COMPLETED';
                subEl.style.color = '#10b981';
            }

            for (let i = 1; i <= 5; i++) {
                const step = document.getElementById(`stageStep${i}`);
                if (step) step.className = 'stage-step done';
            }

            showToast(`Completed! All ${totalQ} test questions mapped!`, 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1400);
        } else {
            clearInterval(progressTimer);
            if (progressModal) progressModal.style.display = 'none';
            showToast(data.detail || 'Failed to extract questions from test photos.', 'error');
            submitBtn.disabled = false;
            if (submitBtnText) submitBtnText.innerHTML = originalText;
        }
    } catch (err) {
        clearInterval(progressTimer);
        if (progressModal) progressModal.style.display = 'none';
        console.error(err);
        showToast('Network error while processing test photos.', 'error');
        submitBtn.disabled = false;
        if (submitBtnText) submitBtnText.innerHTML = originalText;
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

// ================= Global State for Inspect Questions =================
let activeModalQuestions = [];
let activeModalFilterText = '';
let activeModalFilterSubject = 'all';
let editingQuestionsState = {};

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Inspect Questions Modal
async function openQuestionsModal() {
    const modal = document.getElementById('questionsModal');
    const container = document.getElementById('modalQuestionsList');
    modal.classList.add('open');
    container.innerHTML = '<p><i class="fa-solid fa-spinner fa-spin"></i> Fetching questions...</p>';

    try {
        const response = await fetch('/api/admin/active-test');
        if (response.status === 401) {
            showToast('Session expired. Redirecting to admin login...', 'error');
            setTimeout(() => { window.location.href = '/admin/login?msg=session_expired'; }, 1000);
            return;
        }

        const data = await response.json();
        const test = data.active_test;

        if (!test || !test.questions || test.questions.length === 0) {
            activeModalQuestions = [];
            container.innerHTML = '<p>No questions found in active test.</p>';
            updateModalHeaderBadges(0);
            return;
        }

        activeModalQuestions = test.questions;
        updateModalHeaderBadges(activeModalQuestions.length);
        populateSubjectFilterDropdown(activeModalQuestions);
        renderQuestionsList();
    } catch (err) {
        console.error(err);
        container.innerHTML = '<p class="text-maroon">Error loading questions details.</p>';
    }
}

function updateModalHeaderBadges(count) {
    const totalBadge = document.getElementById('modalQTotalBadge');
    if (totalBadge) totalBadge.textContent = `${count} Questions`;

    const summary = document.getElementById('modalQSummary');
    if (summary) summary.textContent = `Total Questions: ${count}`;
}

function populateSubjectFilterDropdown(questions) {
    const subjSelect = document.getElementById('modalQSubjFilter');
    if (!subjSelect) return;

    const subjects = Array.from(new Set(questions.map(q => q.subject || 'General').filter(Boolean)));
    const currentVal = subjSelect.value || 'all';

    let html = '<option value="all">All Subjects</option>';
    subjects.forEach(s => {
        html += `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`;
    });
    subjSelect.innerHTML = html;
    if (subjects.includes(currentVal)) {
        subjSelect.value = currentVal;
    } else {
        subjSelect.value = 'all';
    }
}

function onQuestionSearchChange(val) {
    activeModalFilterText = (val || '').toLowerCase().trim();
    renderQuestionsList();
}

function onQuestionSubjectFilterChange(val) {
    activeModalFilterSubject = val;
    renderQuestionsList();
}

function toggleAddQuestionCard(forceState) {
    const box = document.getElementById('addQuestionBox');
    if (!box) return;
    if (forceState !== undefined) {
        box.style.display = forceState ? 'block' : 'none';
    } else {
        box.style.display = (box.style.display === 'none' || !box.style.display) ? 'block' : 'none';
    }
}

function toggleEditQuestion(qNo) {
    editingQuestionsState[qNo] = true;
    renderQuestionsList();
}

function cancelEditQuestion(qNo) {
    delete editingQuestionsState[qNo];
    renderQuestionsList();
}

function renderQuestionsList() {
    const container = document.getElementById('modalQuestionsList');
    if (!container) return;

    if (!activeModalQuestions || activeModalQuestions.length === 0) {
        container.innerHTML = '<p>No questions found in active test.</p>';
        return;
    }

    const filtered = activeModalQuestions.filter(q => {
        // Subject filter
        if (activeModalFilterSubject !== 'all' && (q.subject || 'General') !== activeModalFilterSubject) {
            return false;
        }

        // Text / Number search
        if (activeModalFilterText) {
            const qNoStr = String(q.q_no);
            if (qNoStr === activeModalFilterText) return true;
            if (q.text && q.text.toLowerCase().includes(activeModalFilterText)) return true;
            if (q.options && q.options.some(o => o.text && o.text.toLowerCase().includes(activeModalFilterText))) return true;
            return false;
        }
        return true;
    });

    const summary = document.getElementById('modalQSummary');
    if (summary) {
        summary.textContent = `Showing ${filtered.length} of ${activeModalQuestions.length} Questions`;
    }

    if (filtered.length === 0) {
        container.innerHTML = '<p style="padding: 1.5rem; text-align: center; color: var(--text-secondary);">No questions matched your search/filter criteria.</p>';
        return;
    }

    let html = '';
    filtered.forEach(q => {
        const isEditing = !!editingQuestionsState[q.q_no];
        const correctKey = (q.correct_answer || 'A').toUpperCase();

        if (isEditing) {
            // Render Inline Editing Form
            html += renderInlineEditCard(q, correctKey);
        } else {
            // Render Standard View Card
            html += renderQuestionViewCard(q, correctKey);
        }
    });

    container.innerHTML = html;
}

function renderQuestionViewCard(q, correctKey) {
    const autoDetectedBadge = q.answer_auto_detected 
        ? '<span class="badge badge-gold" title="Auto mapped from PDF answer key"><i class="fa-solid fa-wand-magic-sparkles"></i> Auto-Mapped</span>'
        : '<span class="badge" style="background:#e2e8f0; color:#475569;" title="Manually verified/edited"><i class="fa-solid fa-pen"></i> Edited</span>';

    const hasDiagram = !!q.image_url;
    const diagramHtml = hasDiagram ? `
        <div class="q-diagram-section" id="q-diagram-wrap-${q.q_no}" style="margin: 10px 0; padding: 10px; background: #f8fafc; border-radius: 8px; border: 1.5px solid #e2e8f0;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px; flex-wrap:wrap; gap:6px;">
                <span style="font-size: 12px; font-weight: 700; color: var(--primary-navy);">
                    <i class="fa-solid fa-image text-gold"></i> Question Diagram / Image:
                </span>
                <button type="button" class="btn btn-outline" style="padding: 2px 8px; font-size: 11px; color: var(--accent-maroon); border-color: #fca5a5;" onclick="removeQuestionImage(${q.q_no})">
                    <i class="fa-solid fa-trash-can"></i> Remove Image
                </button>
            </div>
            <div style="text-align: center;">
                <img src="${q.image_url}" id="q-img-${q.q_no}" style="max-height: 180px; max-width: 100%; object-fit: contain; border-radius: 6px; border: 1px solid #cbd5e1; background: white; cursor: zoom-in;" onclick="window.open(this.src, '_blank')" alt="Diagram for Q${q.q_no}" title="Click to view full image">
            </div>
            <div style="margin-top: 8px; display: flex; justify-content: flex-end;">
                <label class="btn btn-outline" style="padding: 2px 10px; font-size: 11px; cursor: pointer; margin: 0;">
                    <i class="fa-solid fa-arrows-rotate"></i> Replace Image
                    <input type="file" accept="image/*" style="display:none;" onchange="uploadQuestionImage(${q.q_no}, this.files[0])">
                </label>
            </div>
        </div>
    ` : `
        <div class="q-diagram-section" id="q-diagram-wrap-${q.q_no}" style="margin: 10px 0; padding: 8px 12px; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
            <div style="font-size: 12px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px;">
                <i class="fa-solid fa-image" style="color: #94a3b8;"></i>
                <span>No question diagram (click to attach if question has a figure)</span>
            </div>
            <label class="btn btn-outline" style="padding: 3px 10px; font-size: 11px; cursor: pointer; margin: 0; background: white; border-color: #cbd5e1; font-weight: 600;">
                <i class="fa-solid fa-cloud-arrow-up text-gold"></i> Attach Diagram / Image
                <input type="file" accept="image/*" style="display:none;" onchange="uploadQuestionImage(${q.q_no}, this.files[0])">
            </label>
        </div>
    `;

    return `
        <div class="q-preview-item" id="q-preview-${q.q_no}">
            <div class="q-preview-header">
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                    <span class="badge badge-navy">Q${q.q_no}</span>
                    <span class="badge badge-gold">${escapeHtml(q.subject || 'General')}</span>
                    <span class="badge" style="background:#e0f2fe; color:#0369a1;"><i class="fa-solid fa-star"></i> ${q.marks || 1} Mark</span>
                    ${autoDetectedBadge}
                </div>
                
                <div class="btn-action-group">
                    <div style="display:flex; align-items:center; gap:6px;">
                        <label style="font-size:11px; font-weight:700; color:#333; margin:0;">Answer:</label>
                        <select class="form-select form-select-sm" style="display:inline-block; width:auto; padding:2px 6px; font-weight:bold; color:var(--green); border:1.5px solid var(--green); border-radius:4px; cursor:pointer;" onchange="updateQuestionAnswer(${q.q_no}, this.value)">
                            <option value="A" ${correctKey === 'A' ? 'selected' : ''}>Opt A</option>
                            <option value="B" ${correctKey === 'B' ? 'selected' : ''}>Opt B</option>
                            <option value="C" ${correctKey === 'C' ? 'selected' : ''}>Opt C</option>
                            <option value="D" ${correctKey === 'D' ? 'selected' : ''}>Opt D</option>
                        </select>
                    </div>

                    <button type="button" class="btn btn-outline" style="padding: 3px 10px; font-size: 11px; font-weight: 600;" onclick="toggleEditQuestion(${q.q_no})">
                        <i class="fa-solid fa-pen-to-square text-navy"></i> Edit
                    </button>
                    <button type="button" class="btn btn-outline" style="padding: 3px 8px; font-size: 11px; color: var(--accent-maroon); border-color: #fca5a5;" onclick="deleteQuestionPrompt(${q.q_no})">
                        <i class="fa-solid fa-trash-can"></i> Delete
                    </button>
                </div>
            </div>

            <div class="q-preview-text">${escapeHtml(q.text)}</div>
            ${diagramHtml}

            <div class="q-preview-opts">
                ${(q.options || []).map(opt => {
                    const isTarget = (opt.key === correctKey);
                    const optImg = opt.image_url ? `
                        <div style="margin-top:4px;">
                            <img src="${opt.image_url}" class="q-opt-img-thumb" onclick="window.open(this.src, '_blank')" alt="Option ${opt.key} figure" title="Click to view full image">
                        </div>
                    ` : '';
                    return `
                        <div class="q-opt-pill ${isTarget ? 'is-correct' : ''}" data-key="${opt.key}" style="cursor: pointer;" onclick="updateQuestionAnswer(${q.q_no}, '${opt.key}')" title="Click to set Option ${opt.key} as correct answer">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span><strong>(${opt.key})</strong> ${escapeHtml(opt.text)}</span>
                                ${isTarget ? '<i class="fa-solid fa-check-circle" style="color:var(--green);" title="Correct Answer"></i>' : ''}
                            </div>
                            ${optImg}
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

function renderInlineEditCard(q, correctKey) {
    const optsMap = {};
    (q.options || []).forEach(o => {
        optsMap[o.key] = o;
    });

    const optA = optsMap['A'] || { key: 'A', text: '', image_url: null };
    const optB = optsMap['B'] || { key: 'B', text: '', image_url: null };
    const optC = optsMap['C'] || { key: 'C', text: '', image_url: null };
    const optD = optsMap['D'] || { key: 'D', text: '', image_url: null };

    return `
        <div class="q-preview-item is-editing" id="q-preview-${q.q_no}">
            <div class="q-preview-header" style="border-bottom: 1px dashed #cbd5e1; padding-bottom: 0.5rem;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="badge badge-navy">Editing Q${q.q_no}</span>
                    <span style="font-size: 12px; font-weight: 700; color: #2563eb;">
                        <i class="fa-solid fa-pen-nib"></i> Modify Question Statement, Options & Answer
                    </span>
                </div>
                <div style="display:flex; gap:6px;">
                    <button type="button" class="btn btn-outline" style="padding: 2px 8px; font-size: 11px;" onclick="cancelEditQuestion(${q.q_no})">
                        Cancel
                    </button>
                    <button type="button" class="btn btn-primary" style="padding: 3px 12px; font-size: 12px;" onclick="saveQuestionEdit(${q.q_no})">
                        <i class="fa-solid fa-floppy-disk"></i> Save Changes
                    </button>
                </div>
            </div>

            <div class="q-edit-box">
                <!-- Meta inputs: Subject, Marks, Correct Answer -->
                <div class="q-edit-meta-row">
                    <div style="flex: 1; min-width: 150px;">
                        <label style="font-size: 11px; font-weight: 700; color: #475569;">Subject:</label>
                        <input type="text" id="edit-subj-${q.q_no}" class="form-control" value="${escapeHtml(q.subject || 'General')}">
                    </div>
                    <div style="width: 150px;">
                        <label style="font-size: 11px; font-weight: 700; color: #475569;">Correct Answer:</label>
                        <select id="edit-correct-${q.q_no}" class="form-select font-bold" style="color: var(--green);">
                            <option value="A" ${correctKey === 'A' ? 'selected' : ''}>Option A</option>
                            <option value="B" ${correctKey === 'B' ? 'selected' : ''}>Option B</option>
                            <option value="C" ${correctKey === 'C' ? 'selected' : ''}>Option C</option>
                            <option value="D" ${correctKey === 'D' ? 'selected' : ''}>Option D</option>
                        </select>
                    </div>
                    <div style="width: 100px;">
                        <label style="font-size: 11px; font-weight: 700; color: #475569;">Marks:</label>
                        <input type="number" id="edit-marks-${q.q_no}" class="form-control" value="${q.marks || 1}" min="1" max="10">
                    </div>
                </div>

                <!-- Question Statement Textarea -->
                <div>
                    <label style="font-size: 11px; font-weight: 700; color: #475569;">Question Statement:</label>
                    <textarea id="edit-text-${q.q_no}" class="form-control" rows="3">${escapeHtml(q.text)}</textarea>
                </div>

                <!-- Attached Question Diagram preview & upload -->
                <div style="padding: 8px 10px; background: #ffffff; border-radius: 6px; border: 1px solid #e2e8f0;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                        <span style="font-size: 11px; font-weight: 700; color: var(--primary-navy);">
                            <i class="fa-solid fa-image text-gold"></i> Question Main Diagram / Figure:
                        </span>
                        <div style="display:flex; gap:6px;">
                            ${q.image_url ? `
                                <button type="button" class="btn btn-outline" style="padding: 2px 8px; font-size: 11px; color: var(--accent-maroon); border-color:#fca5a5;" onclick="removeQuestionImage(${q.q_no})">
                                    <i class="fa-solid fa-trash-can"></i> Remove
                                </button>
                            ` : ''}
                            <label class="btn btn-outline" style="padding: 2px 8px; font-size: 11px; cursor: pointer; margin: 0;">
                                <i class="fa-solid fa-upload"></i> ${q.image_url ? 'Replace' : 'Attach'} Diagram
                                <input type="file" accept="image/*" style="display:none;" onchange="uploadQuestionImage(${q.q_no}, this.files[0])">
                            </label>
                        </div>
                    </div>
                    ${q.image_url ? `
                        <div style="text-align:center; margin-top:6px;">
                            <img src="${q.image_url}" style="max-height:120px; max-width:100%; object-fit:contain; border-radius:4px; border:1px solid #cbd5e1;" alt="Diagram for Q${q.q_no}">
                        </div>
                    ` : ''}
                </div>

                <!-- Options A, B, C, D Editor Grid -->
                <div>
                    <label style="font-size: 11px; font-weight: 700; color: #475569; margin-bottom: 4px; display: block;">
                        MCQ Options (Text & Figures):
                    </label>
                    <div class="q-edit-opts-grid">
                        ${renderOptionEditCard(q.q_no, optA, correctKey)}
                        ${renderOptionEditCard(q.q_no, optB, correctKey)}
                        ${renderOptionEditCard(q.q_no, optC, correctKey)}
                        ${renderOptionEditCard(q.q_no, optD, correctKey)}
                    </div>
                </div>

                <!-- Save / Cancel / Delete Bar -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.5rem; flex-wrap:wrap; gap:8px;">
                    <button type="button" class="btn btn-outline" style="color:var(--accent-maroon); border-color:#fca5a5; font-size:12px;" onclick="deleteQuestionPrompt(${q.q_no})">
                        <i class="fa-solid fa-trash-can"></i> Delete Question ${q.q_no}
                    </button>
                    <div style="display:flex; gap:8px;">
                        <button type="button" class="btn btn-outline" onclick="cancelEditQuestion(${q.q_no})">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="saveQuestionEdit(${q.q_no})">
                            <i class="fa-solid fa-check"></i> Save Changes to Q${q.q_no}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderOptionEditCard(qNo, opt, correctKey) {
    const isTarget = (opt.key === correctKey);
    return `
        <div class="q-edit-opt-card ${isTarget ? 'is-correct-target' : ''}">
            <div class="q-edit-opt-top">
                <span class="q-edit-opt-badge ${isTarget ? 'text-green' : 'text-gold'}">
                    Option (${opt.key}) ${isTarget ? '<i class="fa-solid fa-circle-check"></i> Correct' : ''}
                </span>
                <div style="display:flex; gap:4px;">
                    ${opt.image_url ? `
                        <button type="button" class="btn btn-outline" style="padding: 1px 6px; font-size: 10px; color: var(--accent-maroon); border-color:#fca5a5;" onclick="removeOptionImage(${qNo}, '${opt.key}')" title="Remove Option Diagram">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    ` : ''}
                    <label class="btn btn-outline" style="padding: 1px 6px; font-size: 10px; cursor: pointer; margin: 0;" title="${opt.image_url ? 'Replace' : 'Attach'} Option Diagram">
                        <i class="fa-solid fa-image text-navy"></i>
                        <input type="file" accept="image/*" style="display:none;" onchange="uploadOptionImage(${qNo}, '${opt.key}', this.files[0])">
                    </label>
                </div>
            </div>
            <input type="text" id="edit-opt-${qNo}-${opt.key}" class="form-control" value="${escapeHtml(opt.text)}" placeholder="Option ${opt.key} text">
            ${opt.image_url ? `
                <div style="text-align:center; margin-top:2px;">
                    <img src="${opt.image_url}" class="q-opt-img-thumb" onclick="window.open(this.src, '_blank')" alt="Option ${opt.key} figure" title="Click to expand">
                </div>
            ` : ''}
        </div>
    `;
}

// Save Full Question Changes
async function saveQuestionEdit(qNo) {
    const textEl = document.getElementById(`edit-text-${qNo}`);
    const correctEl = document.getElementById(`edit-correct-${qNo}`);
    const subjEl = document.getElementById(`edit-subj-${qNo}`);
    const marksEl = document.getElementById(`edit-marks-${qNo}`);

    const optA = document.getElementById(`edit-opt-${qNo}-A`);
    const optB = document.getElementById(`edit-opt-${qNo}-B`);
    const optC = document.getElementById(`edit-opt-${qNo}-C`);
    const optD = document.getElementById(`edit-opt-${qNo}-D`);

    if (!textEl || !textEl.value.trim()) {
        showToast('Question statement cannot be empty.', 'error');
        return;
    }

    const payload = {
        q_no: qNo,
        text: textEl.value.trim(),
        subject: subjEl ? subjEl.value.trim() : 'General',
        correct_answer: correctEl ? correctEl.value.trim().toUpperCase() : 'A',
        marks: marksEl ? parseInt(marksEl.value) || 1 : 1,
        options: [
            { key: 'A', text: optA ? optA.value.trim() : '' },
            { key: 'B', text: optB ? optB.value.trim() : '' },
            { key: 'C', text: optC ? optC.value.trim() : '' },
            { key: 'D', text: optD ? optD.value.trim() : '' }
        ]
    };

    try {
        const response = await fetch('/api/admin/update-question-full', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(`Question ${qNo} saved and updated live!`, 'success');
            
            // Update local state
            const targetIdx = activeModalQuestions.findIndex(q => q.q_no === qNo);
            if (targetIdx !== -1 && data.question) {
                activeModalQuestions[targetIdx] = data.question;
            }
            delete editingQuestionsState[qNo];
            renderQuestionsList();
        } else {
            showToast(data.detail || 'Failed to update question.', 'error');
        }
    } catch (err) {
        showToast('Network error saving question.', 'error');
    }
}

// Delete Question Prompt
async function deleteQuestionPrompt(qNo) {
    if (!confirm(`Are you sure you want to delete Question ${qNo}?\n\nThis will remove the question and re-index all remaining questions (1 to N) immediately in the live test.`)) {
        return;
    }

    try {
        const response = await fetch('/api/admin/delete-question', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q_no: qNo })
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || `Question ${qNo} deleted.`, 'success');
            delete editingQuestionsState[qNo];
            // Reload all questions to get re-indexed state
            await openQuestionsModal();
        } else {
            showToast(data.detail || 'Could not delete question.', 'error');
        }
    } catch (err) {
        showToast('Network error deleting question.', 'error');
    }
}

// Save New Question
async function saveNewQuestion() {
    const textEl = document.getElementById('newQText');
    const subjEl = document.getElementById('newQSubject');
    const correctEl = document.getElementById('newQCorrect');
    const marksEl = document.getElementById('newQMarks');
    const optA = document.getElementById('newOptA');
    const optB = document.getElementById('newOptB');
    const optC = document.getElementById('newOptC');
    const optD = document.getElementById('newOptD');

    if (!textEl || !textEl.value.trim()) {
        showToast('Please enter the question statement.', 'error');
        return;
    }

    const payload = {
        text: textEl.value.trim(),
        subject: subjEl ? subjEl.value.trim() : 'Physics',
        correct_answer: correctEl ? correctEl.value.trim().toUpperCase() : 'A',
        marks: marksEl ? parseInt(marksEl.value) || 1 : 1,
        options: [
            { key: 'A', text: optA ? optA.value.trim() : '' },
            { key: 'B', text: optB ? optB.value.trim() : '' },
            { key: 'C', text: optC ? optC.value.trim() : '' },
            { key: 'D', text: optD ? optD.value.trim() : '' }
        ]
    };

    const btn = document.getElementById('saveNewQBtn');
    if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

    try {
        const response = await fetch('/api/admin/add-question', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || 'Question added successfully!', 'success');
            // Clear inputs
            if (textEl) textEl.value = '';
            if (optA) optA.value = '';
            if (optB) optB.value = '';
            if (optC) optC.value = '';
            if (optD) optD.value = '';
            toggleAddQuestionCard(false);
            // Refresh modal
            await openQuestionsModal();
        } else {
            showToast(data.detail || 'Failed to add question.', 'error');
        }
    } catch (err) {
        showToast('Network error adding question.', 'error');
    } finally {
        if (btn) btn.innerHTML = '<i class="fa-solid fa-save"></i> Save & Append Question';
    }
}

// Upload & Remove Question Diagram
async function uploadQuestionImage(qNo, file) {
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
        showToast('Image size exceeds 10MB limit.', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('q_no', qNo);
    formData.append('file', file);

    try {
        const response = await fetch('/api/admin/upload-question-image', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || `Diagram attached to Q${qNo}!`, 'success');
            const targetQ = activeModalQuestions.find(q => q.q_no === qNo);
            if (targetQ) targetQ.image_url = data.image_url;
            renderQuestionsList();
        } else {
            showToast(data.detail || 'Failed to upload image.', 'error');
        }
    } catch (err) {
        showToast('Network error uploading diagram.', 'error');
    }
}

async function removeQuestionImage(qNo) {
    if (!confirm(`Are you sure you want to remove the diagram from Question ${qNo}?`)) {
        return;
    }

    try {
        const response = await fetch('/api/admin/remove-question-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q_no: qNo })
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || `Diagram removed from Q${qNo}.`, 'success');
            const targetQ = activeModalQuestions.find(q => q.q_no === qNo);
            if (targetQ) targetQ.image_url = null;
            renderQuestionsList();
        } else {
            showToast(data.detail || 'Failed to remove diagram.', 'error');
        }
    } catch (err) {
        showToast('Error removing diagram.', 'error');
    }
}

// Upload & Remove Option Diagram
async function uploadOptionImage(qNo, optKey, file) {
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
        showToast('Image size exceeds 10MB limit.', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('q_no', qNo);
    formData.append('opt_key', optKey);
    formData.append('file', file);

    try {
        const response = await fetch('/api/admin/upload-option-image', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || `Option ${optKey} image attached!`, 'success');
            const targetQ = activeModalQuestions.find(q => q.q_no === qNo);
            if (targetQ && targetQ.options) {
                const targetOpt = targetQ.options.find(o => o.key.toUpperCase() === optKey.toUpperCase());
                if (targetOpt) targetOpt.image_url = data.image_url;
            }
            renderQuestionsList();
        } else {
            showToast(data.detail || 'Failed to upload option image.', 'error');
        }
    } catch (err) {
        showToast('Network error uploading option image.', 'error');
    }
}

async function removeOptionImage(qNo, optKey) {
    if (!confirm(`Remove image from Question ${qNo} Option ${optKey}?`)) {
        return;
    }

    try {
        const response = await fetch('/api/admin/remove-option-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q_no: qNo, opt_key: optKey })
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || `Image removed from Option ${optKey}.`, 'success');
            const targetQ = activeModalQuestions.find(q => q.q_no === qNo);
            if (targetQ && targetQ.options) {
                const targetOpt = targetQ.options.find(o => o.key.toUpperCase() === optKey.toUpperCase());
                if (targetOpt) targetOpt.image_url = null;
            }
            renderQuestionsList();
        } else {
            showToast(data.detail || 'Failed to remove option image.', 'error');
        }
    } catch (err) {
        showToast('Error removing option image.', 'error');
    }
}

// Instant Quick Answer Update
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
            const targetQ = activeModalQuestions.find(q => q.q_no === qNo);
            if (targetQ) {
                targetQ.correct_answer = newAnswer;
                targetQ.answer_auto_detected = false;
            }
            renderQuestionsList();
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


