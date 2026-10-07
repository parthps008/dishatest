import os
import re
import uuid
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image
import pdfplumber

from app.pdf_parser import extract_text_from_pdf, detect_test_meta, extract_answer_keys

STRICT_Q_RE = re.compile(r'^(?:Q(?:uestion)?[\.\s_]*)?(\d{1,3})[\.\)\:\-](?!\d)', re.IGNORECASE)

def trim_white_borders(img: Image.Image, padding: int = 10, thresh: int = 245) -> Image.Image:
    """
    Trims excessive blank white margins around a cropped question image
    while preserving comfortable padding so text and diagrams don't touch the border.
    """
    try:
        gray = img.convert('L')
        # Mask non-white pixels
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
    """
    Ensures question crop is high-resolution, responsive, and compressed (~50-100KB JPEG).
    """
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(float(img.height) * float(ratio))
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    img.save(target_path, "JPEG", quality=82)

def slice_pdf_to_question_images(
    pdf_path: str,
    output_dir: str,
    override_duration: Optional[int] = None,
    title_override: Optional[str] = None,
    subject_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Automatically converts a question paper PDF into high-resolution sequential question snapshots:
    1. Analyzes document layout (1-column vs 2-column papers).
    2. Identifies question markers (e.g. 1., 2), Q1., etc.) using margin clustering to filter out false positives.
    3. Crops each question bounding box cleanly without overlapping next questions or footers.
    4. Auto-detects answer key table if present at the end of the PDF.
    5. Saves optimized question images into output_dir and maps them sequentially (Q1 -> Crop 1, Q2 -> Crop 2...).
    6. Returns structured TestData ready for activation and CBT student testing.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Extract text and metadata for title, subjects, duration, and answer keys
    raw_text = extract_text_from_pdf(pdf_path)
    detected_title, detected_subjects, detected_duration = detect_test_meta(raw_text, default_filename=pdf_path)
    answer_keys = extract_answer_keys(raw_text, pdf_path=pdf_path)

    # Title resolution
    test_title = (title_override or "").strip()
    if not test_title:
        test_title = detected_title or "Disha Academy Assessment Test"

    # Subject resolution
    if subject_override and subject_override.strip():
        subjects = [subject_override.strip()]
    elif detected_subjects:
        subjects = detected_subjects
    else:
        subjects = ["General"]

    # Duration resolution
    if override_duration and override_duration > 0:
        duration = override_duration
    elif detected_duration and detected_duration > 0:
        duration = detected_duration
    else:
        duration = 30

    # 2. Open PDF and slice questions
    detected_crops = [] # List of tuples: (raw_q_num, crop_image)

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            w = page.width
            h = page.height
            words = page.extract_words()
            if not words or len(words) < 3:
                continue

            # Header detection (banner at top e.g. Disha Academy, Name, Marks)
            hw = [
                wd for wd in words 
                if wd['top'] < 70 and any(t in wd['text'].upper() for t in ['DISHA', 'ACADEMY', 'NAME:', 'SUB:', 'MARKS:'])
            ]
            header_bottom = max(wd['bottom'] for wd in hw) if hw else 0

            # Answer key heading cutoff (e.g. ANSWER KEY, SOLUTIONS, ANSWERS)
            ak_top = None
            for i, wd in enumerate(words):
                txt = wd['text'].upper()
                if 'ANSWER' in txt or 'SOLUTIONS' in txt:
                    if i + 1 < len(words) and 'KEY' in words[i+1]['text'].upper():
                        ak_top = wd['top'] - 6
                        break
                    elif 'KEY' in txt or txt == 'ANSWERS':
                        ak_top = wd['top'] - 6
                        break

            # Grid table cutoff (e.g. empty student answer sheet '1 11 21 31 41...')
            grid_top = None
            grid_words = [
                wd for wd in words 
                if wd['top'] > 450 and wd['text'] in ['11', '21', '31', '41'] and wd['x0'] > 250
            ]
            if len(grid_words) >= 3:
                grid_top = min(wd['top'] for wd in grid_words) - 6

            # Two-column layout detection
            mid_x = w * 0.48
            body_words = [wd for wd in words if wd['top'] >= header_bottom]
            left_words = [wd for wd in body_words if wd['x1'] <= mid_x]
            right_words = [wd for wd in body_words if wd['x0'] >= mid_x]
            crossing = [wd for wd in body_words if wd['x0'] < mid_x - 5 and wd['x1'] > mid_x + 5]

            is_two_col = (
                len(body_words) > 30 and
                (len(crossing) / len(body_words) < 0.05) and
                (len(left_words) / len(body_words) > 0.20) and
                (len(right_words) / len(body_words) > 0.20)
            )

            # Render page at 150 DPI for crisp readability of math formulas, exponents, and diagrams
            page_render = page.to_image(resolution=150).original
            sx = page_render.width / w
            sy = page_render.height / h

            columns = []
            if is_two_col:
                columns.append(('left', 0, mid_x, left_words, ak_top))
                r_cutoff = ak_top
                if grid_top:
                    r_cutoff = min(r_cutoff, grid_top) if r_cutoff else grid_top
                columns.append(('right', mid_x, w, right_words, r_cutoff))
            else:
                columns.append(('single', 0, w, body_words, ak_top))

            for col_name, col_left, col_right, col_words, col_cutoff in columns:
                # Find candidate question markers in this column
                candidates = []
                for wd in col_words:
                    if col_cutoff and wd['top'] >= col_cutoff:
                        continue
                    m = STRICT_Q_RE.match(wd['text'].strip())
                    if m:
                        candidates.append((int(m.group(1)), wd))

                if not candidates:
                    continue

                # Filter by dominant left margin in this column (within 18pt)
                min_col_x = min(wd['x0'] for _, wd in candidates)
                valid_qs = [
                    (num, wd) for num, wd in candidates 
                    if abs(wd['x0'] - min_col_x) <= 18
                ]
                valid_qs.sort(key=lambda x: x[1]['top'])

                for i, (q_num, wd) in enumerate(valid_qs):
                    top_y = max(0, wd['top'] - 5)
                    if i + 1 < len(valid_qs):
                        bottom_y = valid_qs[i+1][1]['top'] - 3
                    else:
                        # Last question in this column
                        q_words = [
                            w for w in col_words 
                            if w['top'] >= wd['top'] and (not col_cutoff or w['bottom'] <= col_cutoff + 5)
                        ]
                        if q_words:
                            bottom_y = max(w['bottom'] for w in q_words) + 6
                        else:
                            bottom_y = col_cutoff if col_cutoff else h - 10
                        if col_cutoff:
                            bottom_y = min(bottom_y, col_cutoff)

                    # Bounding box coordinates scaled to image resolution
                    pad_left = max(0, col_left + 15) if col_name == 'right' else max(0, min_col_x - 12)
                    pad_right = min(w, col_right - 8) if col_name == 'left' else min(w, col_right)

                    crop_box = (
                        int(pad_left * sx),
                        int(top_y * sy),
                        int(pad_right * sx),
                        int(bottom_y * sy)
                    )

                    # Ensure valid box dimensions
                    if crop_box[2] > crop_box[0] + 20 and crop_box[3] > crop_box[1] + 20:
                        raw_crop = page_render.crop(crop_box)
                        trimmed_crop = trim_white_borders(raw_crop)
                        detected_crops.append((q_num, trimmed_crop))

    # Fallback: if no question markers matched (e.g. 1 question per page/slide format)
    if not detected_crops:
        with pdfplumber.open(pdf_path) as pdf:
            for p_idx, page in enumerate(pdf.pages):
                words = page.extract_words()
                if not words:
                    continue
                p_img = page.to_image(resolution=150).original
                trimmed = trim_white_borders(p_img)
                detected_crops.append((p_idx + 1, trimmed))

    if not detected_crops:
        raise ValueError("Could not detect any questions in the uploaded PDF. Please verify that the PDF contains readable text and numbered questions.")

    # 3. Save question crops and construct sequential question mapping
    questions = []
    primary_subject = subjects[0] if subjects else "General"

    for idx, (raw_num, crop_img) in enumerate(detected_crops):
        q_no = idx + 1
        safe_filename = f"qimg_slice_q{q_no}_{uuid.uuid4().hex[:8]}.jpg"
        target_path = os.path.join(output_dir, safe_filename)
        optimize_and_save_crop(crop_img, target_path)

        img_url = f"/static/uploads/questions/{safe_filename}"

        # Match answer key by sequential question number or raw extracted number
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
        questions.append(q_data)

    test_data = {
        "id": "test_" + uuid.uuid4().hex[:8],
        "title": test_title,
        "subjects": subjects,
        "duration_minutes": duration,
        "total_questions": len(questions),
        "questions": questions,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pdf_filename": os.path.basename(pdf_path),
        "test_type": "pdf_slice"
    }

    return test_data
