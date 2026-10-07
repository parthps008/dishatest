import os
import re
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageOps

from app.pdf_parser import detect_test_meta, extract_answer_keys

# Singleton OCR engine to avoid re-initializing on each request
_ocr_engine = None
_ocr_init_attempted = False


def get_ocr_engine():
    """Lazily loads RapidOCR engine if available, or returns None to use visual fallback."""
    global _ocr_engine, _ocr_init_attempted
    if _ocr_init_attempted:
        return _ocr_engine
    
    _ocr_init_attempted = True
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        print("[Photo Paper Slicer] RapidOCR AI engine successfully initialized.")
    except Exception as e:
        print(f"[Photo Paper Slicer] RapidOCR not available ({e}). Using pure vision fallback slicer.")
        _ocr_engine = None
    return _ocr_engine


# Flexible Question and Option Matchers
Q_MARKER_RE = re.compile(
    r'^(?:(?:Q(?:uestion|ue)?|Q\.?No\.?)[\.\s\-_]*(?:\(?|\[?)(\d{1,3})(?:\)?|\]?)|(?:\(?|\[?)(\d{1,3})(?:\)|\]|\.|\:|\s+[-–]))\s*(.*)$',
    re.IGNORECASE
)
OPT_MARKER_RE = re.compile(
    r'^(?:(?:\(?|\[?)([a-d1-4])(?:\)?|\]?|\.|\:))\s*(.*)$',
    re.IGNORECASE
)
CIR_ANS_RE = re.compile(r'[\(\[]?([A-Da-d])[\)\]]?\s*[\u2713\u2714\u25cf\u25cb]?', re.IGNORECASE)


def trim_white_borders(img: Image.Image, padding: int = 8, thresh: int = 242) -> Image.Image:
    """Trims unnecessary white borders around the question screenshot while keeping comfortable padding."""
    try:
        gray = img.convert('L')
        bw = gray.point(lambda p: 255 if p < thresh else 0, mode='1')
        bbox = bw.getbbox()
        if bbox:
            left = max(0, bbox[0] - padding)
            top = max(0, bbox[1] - padding)
            right = min(img.width, bbox[2] + padding)
            bottom = min(img.height, bbox[3] + padding)
            return img.crop((left, top, right, bottom))
    except Exception:
        pass
    return img


def optimize_and_save_crop(img: Image.Image, target_path: str, max_width: int = 1200) -> None:
    """Optimizes and saves the question screenshot as a responsive, sharp JPEG."""
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(float(img.height) * float(ratio))
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    img.save(target_path, "JPEG", quality=84)


def analyze_paper_layout_and_slices(img_path: str) -> Dict[str, Any]:
    """
    Universal multi-publisher exam paper segmentation engine:
    1. Detects header and footer boundaries (strips publisher watermarks and copyright lines).
    2. Identifies 1-column vs 2-column page layout.
    3. Employs Dual-Anchor detection:
       - Top Anchor: Question numbering sequence (1., 2., Q1., Question 1)
       - Bottom Anchor: Option (A)–(D) clusters (Option D marks the end of an MCQ)
    4. Computes horizontal projection profiles to snap cut lines to inter-question whitespace gutters.
    5. Filters and merges micro-fragments so questions are never cut in half.
    Returns: {width, height, slices, detected_title, detected_subjects, detected_duration, full_text}
    """
    pil_img = ImageOps.exif_transpose(Image.open(img_path))
    W, H = pil_img.size

    engine = get_ocr_engine()
    ocr_result = None
    if engine:
        try:
            ocr_result, _ = engine(np.array(pil_img))
        except Exception as e:
            print(f"[Photo Paper Slicer] OCR failed ({e}). Proceeding to visual projection profile.")
            ocr_result = None

    # Base Header and Footer boundaries
    top_cutoff = int(H * 0.07)
    bot_cutoff = int(H * 0.96)
    full_text_lines = []

    if ocr_result:
        boxes = []
        for box, txt, score in ocr_result:
            txt_s = txt.strip()
            if not txt_s:
                continue
            full_text_lines.append(txt_s)
            ymin = min(pt[1] for pt in box)
            ymax = max(pt[1] for pt in box)
            xmin = min(pt[0] for pt in box)
            xmax = max(pt[0] for pt in box)

            t_up = txt_s.upper()
            if ymin < H * 0.22:
                if any(k in t_up for k in ['PRACTICE PAPER', 'CHAPTER', 'DEFINITE INTEGRALS', 'INTEGRAL CALCULUS',
                                           'INTEGRATION', 'MULTIPLE CHOICE', 'SINGLE TYPE', 'QUESTION BANK',
                                           'SECTION - A', 'SECTION-A', 'GENERAL INSTRUCTIONS']):
                    top_cutoff = max(top_cutoff, int(ymax) + 8)

            if ymax > H * 0.88:
                if any(k in t_up for k in ['PREPARED BY', 'PAGE', 'WWW.', 'HTTP', 'DOWNLOADED', 'COPYRIGHT']):
                    bot_cutoff = min(bot_cutoff, int(ymin) - 8)

            boxes.append({
                'text': txt_s,
                'box': box,
                'ymin': ymin,
                'ymax': ymax,
                'xmin': xmin,
                'xmax': xmax,
                'ymid': (ymin + ymax) / 2
            })
    else:
        boxes = []

    full_text = "\n".join(full_text_lines)
    answer_keys = extract_answer_keys(full_text)
    detected_title, detected_subjects, detected_duration = detect_test_meta(full_text, default_filename=img_path)

    # Detect 2-column layout via vertical projection profile
    mid_start, mid_end = int(W * 0.42), int(W * 0.58)
    gray = np.array(pil_img.convert('L'))
    col_dark = (gray[top_cutoff:bot_cutoff, :] < 205).sum(axis=0)
    mid_min_x = mid_start + int(np.argmin(col_dark[mid_start:mid_end])) if col_dark.size > 0 else int(W * 0.5)
    avg_dark = float(col_dark.mean()) if col_dark.size > 0 else 1.0
    is_two_col = (col_dark[mid_min_x] < (avg_dark * 0.55)) and (W > 700)

    columns = []
    content_boxes = [b for b in boxes if b['ymin'] >= top_cutoff - 15 and b['ymax'] <= bot_cutoff + 15]

    if is_two_col:
        columns.append(('left', 0, mid_min_x, [b for b in content_boxes if b['xmin'] < mid_min_x]))
        columns.append(('right', mid_min_x, W, [b for b in content_boxes if b['xmin'] >= mid_min_x]))
    else:
        columns.append(('single', 0, W, content_boxes))

    all_slices = []
    global_q_counter = 1

    for col_name, c_left, c_right, c_boxes in columns:
        col_w = c_right - c_left
        if col_w < 60:
            continue

        c_boxes.sort(key=lambda b: b['ymin'])

        # Compute Whitespace valleys in column (gutters)
        pad_x1 = max(0, c_left + int(col_w * 0.02))
        pad_x2 = min(W, c_right - int(col_w * 0.02))
        col_gray = gray[top_cutoff:bot_cutoff, pad_x1:pad_x2]
        row_dark = (col_gray < 205).sum(axis=1) if col_gray.size > 0 else np.array([])
        row_thresh = max(4, int(col_w * 0.035))
        is_space = (row_dark < row_thresh) if row_dark.size > 0 else np.array([])

        gutters = []
        in_gap = False
        gap_start = 0
        for i, blank in enumerate(is_space):
            if blank and not in_gap:
                in_gap = True
                gap_start = i
            elif not blank and in_gap:
                in_gap = False
                if (i - gap_start) >= 6:
                    gutters.append(top_cutoff + (gap_start + i) // 2)

        # Extract Question Markers and Option (A)-(D) boundaries
        q_markers = []
        d_options = []

        for b in c_boxes:
            if b['xmin'] < c_left + col_w * 0.40:
                m_q = Q_MARKER_RE.match(b['text'])
                if m_q:
                    val = m_q.group(1) or m_q.group(2)
                    if val and 1 <= int(val) <= 150:
                        q_markers.append((int(val), b['ymin'], b))

            m_opt = OPT_MARKER_RE.match(b['text'])
            if m_opt:
                k = m_opt.group(1).upper()
                if k in ('D', '4'):
                    d_options.append((b['ymax'], b))

        # Filter strictly increasing question markers
        valid_qs = []
        last_num = 0
        for num, y, b in q_markers:
            if num > last_num:
                valid_qs.append((num, y))
                last_num = num

        # Filter & merge Option D markers that are too close (belongs to same question)
        merged_d_options = []
        for d_y, d_box in sorted(d_options, key=lambda x: x[0]):
            if not merged_d_options or (d_y - merged_d_options[-1][0]) >= 40:
                merged_d_options.append((d_y, d_box))

        col_slices = []

        # Decision Logic:
        # A) If question markers are cleanly detected (at least 3 in sequence)
        if len(valid_qs) >= 3:
            for idx in range(len(valid_qs)):
                q_num, y_top = valid_qs[idx]
                prev_gutters = [g for g in gutters if g <= y_top and g >= y_top - 32]
                slice_top = prev_gutters[-1] if prev_gutters else max(top_cutoff, int(y_top) - 6)

                if idx + 1 < len(valid_qs):
                    next_y = valid_qs[idx + 1][1]
                    next_gutters = [g for g in gutters if g > y_top + 18 and g <= next_y]
                    slice_bot = next_gutters[-1] if next_gutters else int(next_y) - 4
                else:
                    after_ds = [d[0] for d in merged_d_options if d[0] > y_top]
                    slice_bot = min(bot_cutoff, int(max(after_ds)) + 12) if after_ds else bot_cutoff

                col_slices.append({
                    'q_no': q_num,
                    'ymin': max(0, slice_top),
                    'xmin': c_left,
                    'ymax': min(H, slice_bot),
                    'xmax': c_right,
                    'correct_answer': answer_keys.get(q_num, 'A')
                })

        # B) If Option D clusters are prominent (e.g. Vedantu, Amit Bajaj where integrals absorb Q numbers)
        elif len(merged_d_options) >= 2:
            prev_y = top_cutoff
            for q_idx, (d_y, _) in enumerate(merged_d_options):
                q_num = global_q_counter + q_idx
                slice_top = max(top_cutoff, int(prev_y) - 2)
                after_gutters = [g for g in gutters if g >= d_y and g <= d_y + 35]
                slice_bot = after_gutters[0] if after_gutters else min(bot_cutoff, int(d_y) + 12)
                prev_y = slice_bot

                col_slices.append({
                    'q_no': q_num,
                    'ymin': max(0, slice_top),
                    'xmin': c_left,
                    'ymax': min(H, slice_bot),
                    'xmax': c_right,
                    'correct_answer': answer_keys.get(q_num, 'A')
                })

        # C) Visual Projection Profile Fallback
        else:
            divs = [top_cutoff]
            for g in gutters:
                if (g - divs[-1]) >= 48:
                    divs.append(g)
            divs.append(bot_cutoff)

            if len(divs) < 3:
                default_qs = 4
                step = (bot_cutoff - top_cutoff) // default_qs
                divs = [top_cutoff + s * step for s in range(default_qs + 1)]
                divs[-1] = bot_cutoff

            for d_idx in range(len(divs) - 1):
                q_num = global_q_counter + d_idx
                col_slices.append({
                    'q_no': q_num,
                    'ymin': max(0, divs[d_idx]),
                    'xmin': c_left,
                    'ymax': min(H, divs[d_idx + 1]),
                    'xmax': c_right,
                    'correct_answer': answer_keys.get(q_num, 'A')
                })

        # Filter out micro-fragments (< 32px height) and merge into previous slice
        clean_col_slices = []
        for sl in col_slices:
            h_slice = sl['ymax'] - sl['ymin']
            if h_slice < 32 and clean_col_slices:
                clean_col_slices[-1]['ymax'] = max(clean_col_slices[-1]['ymax'], sl['ymax'])
            else:
                clean_col_slices.append(sl)

        all_slices.extend(clean_col_slices)
        global_q_counter += len(clean_col_slices)

    # Renumber sequentially
    for idx, sl in enumerate(all_slices, 1):
        sl['q_no'] = idx

    return {
        'width': W,
        'height': H,
        'slices': all_slices,
        'detected_title': detected_title or "Disha Academy Paper Photo Assessment",
        'detected_subjects': detected_subjects or ["General"],
        'detected_duration': detected_duration or 30,
        'full_text': full_text
    }


def slice_single_paper_image(img_path: str) -> Tuple[List[Tuple[int, Image.Image]], str]:
    """
    Analyzes a test paper photo using the universal layout engine,
    and crops each question into its own sharp screenshot.
    Returns: (list of (q_num, cropped_img), extracted_text)
    """
    pil_img = ImageOps.exif_transpose(Image.open(img_path))
    W, H = pil_img.size

    analysis = analyze_paper_layout_and_slices(img_path)
    slices = analysis.get('slices', [])
    full_text = analysis.get('full_text', '')

    crops = []
    for sl in slices:
        q_no = sl['q_no']
        # Pad slightly horizontally and vertically for comfort
        y1 = max(0, sl['ymin'])
        y2 = min(H, sl['ymax'])
        x1 = max(0, sl['xmin'])
        x2 = min(W, sl['xmax'])

        if (y2 - y1) >= 28 and (x2 - x1) >= 40:
            q_crop = pil_img.crop((x1, y1, x2, y2))
            q_trimmed = trim_white_borders(q_crop)
            crops.append((q_no, q_trimmed))

    if not crops:
        crops = [(1, pil_img)]

    return (crops, full_text)


def slice_paper_photos_to_questions(
    image_paths: List[str],
    output_dir: str,
    override_duration: Optional[int] = None,
    title_override: Optional[str] = None,
    subject_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    End-to-end multi-photo paper question parser:
    1. Scans each uploaded photo across pages.
    2. Uses universal layout engine (Question Markers + Option ABCD clusters + Gutters).
    3. Crops high-resolution screenshots for each question.
    4. Auto-detects test metadata (title, subject, duration) and answer keys if present.
    5. Saves optimized question images into output_dir and maps them sequentially.
    6. Returns structured TestData ready for activation and CBT student testing.
    """
    os.makedirs(output_dir, exist_ok=True)

    all_detected_crops = [] # List of (detected_q_num, cropped_img)
    combined_texts = []

    for photo_path in image_paths:
        crops, text = slice_single_paper_image(photo_path)
        all_detected_crops.extend(crops)
        if text:
            combined_texts.append(text)

    if not all_detected_crops:
        raise ValueError("Could not extract any questions from the uploaded paper photos. Please make sure the photos are clear and questions are numbered.")

    # Metadata extraction from combined OCR text
    full_text = "\n".join(combined_texts)
    detected_title, detected_subjects, detected_duration = detect_test_meta(full_text, default_filename=image_paths[0])
    answer_keys = extract_answer_keys(full_text)

    test_title = (title_override or "").strip() or detected_title or "Disha Academy Paper Photo Assessment"
    subjects = [subject_override.strip()] if (subject_override and subject_override.strip()) else (detected_subjects or ["General"])
    duration = override_duration if (override_duration and override_duration > 0) else (detected_duration or 30)

    primary_subject = subjects[0] if subjects else "General"

    def process_and_save_photo_crop(item):
        idx, (raw_num, crop_img) = item
        q_no = idx + 1
        safe_filename = f"qimg_photo_q{q_no}_{uuid.uuid4().hex[:8]}.jpg"
        target_path = os.path.join(output_dir, safe_filename)
        optimize_and_save_crop(crop_img, target_path)

        img_url = f"/static/uploads/questions/{safe_filename}"

        correct_ans = answer_keys.get(q_no) or answer_keys.get(raw_num) or "A"
        correct_ans = str(correct_ans).strip().upper()
        if correct_ans in ["A", "B", "C", "D"]:
            auto_detected = (q_no in answer_keys or raw_num in answer_keys)
        else:
            correct_ans = "A"
            auto_detected = False

        q_data = {
            "id": q_no,
            "q_no": q_no,
            "text": f"Question {q_no}",
            "options": [
                {"key": "A", "text": "Option A", "image_url": None},
                {"key": "B", "text": "Option B", "image_url": None},
                {"key": "C", "text": "Option C", "image_url": None},
                {"key": "D", "text": "Option D", "image_url": None}
            ],
            "correct_answer": correct_ans,
            "answer_auto_detected": auto_detected,
            "image_url": img_url,
            "subject": primary_subject,
            "marks": 1,
            "negative_marks": 0.0,
            "explanation": None
        }
        return (q_no, q_data)

    max_workers = min(8, max(2, (os.cpu_count() or 2) * 2))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        processed_pairs = list(executor.map(process_and_save_photo_crop, enumerate(all_detected_crops)))

    processed_pairs.sort(key=lambda x: x[0])
    questions = [p[1] for p in processed_pairs]

    test_data = {
        "id": "test_" + uuid.uuid4().hex[:8],
        "title": test_title,
        "subjects": subjects,
        "duration_minutes": duration,
        "total_questions": len(questions),
        "questions": questions,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pdf_filename": None,
        "test_type": "photo_paper"
    }

    return test_data


def crop_and_save_custom_slices(
    img_path: str,
    slices: List[Dict[str, Any]],
    output_dir: str,
    start_q_no: int = 1,
    primary_subject: str = "General"
) -> List[Dict[str, Any]]:
    """
    Crops and optimizes questions using custom/calibrated slices from the admin layout inspector.
    """
    os.makedirs(output_dir, exist_ok=True)
    pil_img = ImageOps.exif_transpose(Image.open(img_path))
    W, H = pil_img.size

    questions = []
    for idx, sl in enumerate(slices):
        q_no = start_q_no + idx
        y1 = max(0, int(sl.get('ymin', 0)))
        y2 = min(H, int(sl.get('ymax', H)))
        x1 = max(0, int(sl.get('xmin', 0)))
        x2 = min(W, int(sl.get('xmax', W)))

        if (y2 - y1) < 20 or (x2 - x1) < 30:
            continue

        crop = pil_img.crop((x1, y1, x2, y2))
        trimmed = trim_white_borders(crop)

        safe_filename = f"qimg_photo_q{q_no}_{uuid.uuid4().hex[:8]}.jpg"
        target_path = os.path.join(output_dir, safe_filename)
        optimize_and_save_crop(trimmed, target_path)

        correct_ans = str(sl.get('correct_answer', sl.get('ans', 'A'))).strip().upper()
        if correct_ans not in ('A', 'B', 'C', 'D'):
            correct_ans = 'A'

        q_data = {
            "id": q_no,
            "q_no": q_no,
            "text": f"Question {q_no}",
            "options": [
                {"key": "A", "text": "Option A", "image_url": None},
                {"key": "B", "text": "Option B", "image_url": None},
                {"key": "C", "text": "Option C", "image_url": None},
                {"key": "D", "text": "Option D", "image_url": None}
            ],
            "correct_answer": correct_ans,
            "answer_auto_detected": True,
            "image_url": f"/static/uploads/questions/{safe_filename}",
            "subject": sl.get('subject', primary_subject),
            "marks": 1,
            "negative_marks": 0.0,
            "explanation": None
        }
        questions.append(q_data)

    return questions

