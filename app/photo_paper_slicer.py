import os
import re
import uuid
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageOps
from rapidocr_onnxruntime import RapidOCR

from app.pdf_parser import detect_test_meta, extract_answer_keys

# Singleton OCR engine to avoid re-initializing on each request
_ocr_engine = None

def get_ocr_engine() -> RapidOCR:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine

PREFIXED_Q_RE = re.compile(
    r'^(?:Q(?:uestion|ue)?|Q\.?No\.?)[\.\s\-_]*(?:\(?|\[?)(\d{1,3})(?:\)?|\]?)(?:[\.\)\:\-]|\s|$)',
    re.IGNORECASE
)
DELIMITED_NUM_RE = re.compile(
    r'^(?:(?:\(?|\[?)(\d{1,3})(?:\)|\])|(\d{1,3})[\.\)\:\-]|(\d{1,3})\s+[-–])(?!\d)',
    re.IGNORECASE
)
PREFIX_WORD_RE = re.compile(r'^(?:Q(?:uestion|ue)?|Q\.?No\.?)$', re.IGNORECASE)
NUM_TOKEN_RE = re.compile(r'^(?:\(?|\[?)(\d{1,3})(?:\)?|\]?)[\.\)\:\-]?$', re.IGNORECASE)

def is_q_token(text: str) -> Optional[int]:
    """Checks if a string token is a question marker (e.g. 1., 2), Q1., etc.)."""
    m = PREFIXED_Q_RE.match(text)
    if m:
        return int(m.group(1))
    m2 = DELIMITED_NUM_RE.match(text)
    if m2:
        val = m2.group(1) or m2.group(2) or m2.group(3)
        return int(val) if val else None
    return None

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

def slice_single_paper_image(img_path: str) -> Tuple[List[Tuple[int, Image.Image]], str]:
    """
    Analyzes a single test paper photo, runs AI vision OCR to detect question numbers,
    and crops each question into its own screenshot.
    Returns: (list of (q_num, cropped_img), extracted_text)
    """
    engine = get_ocr_engine()
    pil_img = Image.open(img_path)
    pil_img = ImageOps.exif_transpose(pil_img)
    W, H = pil_img.size

    img_np = np.array(pil_img)
    ocr_result, _ = engine(img_np)
    if not ocr_result:
        # Fallback: whole image if no text recognized
        return ([(1, pil_img)], "")

    # Extract all text for metadata / answer keys
    full_text = "\n".join([item[1] for item in ocr_result])

    # Find raw question candidates
    raw_cands = []
    num_boxes = len(ocr_result)
    for i in range(num_boxes):
        box, text, score = ocr_result[i]
        txt = text.strip()

        # Check two-word 'Question 1'
        if PREFIX_WORD_RE.match(txt) and (i + 1 < num_boxes):
            next_box, next_text, _ = ocr_result[i + 1]
            m_num = NUM_TOKEN_RE.match(next_text.strip())
            if m_num and (next_box[0][0] - box[1][0] < 30):
                num = int(m_num.group(1))
                if 1 <= num <= 500:
                    y_top = min(pt[1] for pt in box)
                    y_bottom = max(pt[1] for pt in box)
                    x_left = min(pt[0] for pt in box)
                    raw_cands.append((num, x_left, y_top, y_bottom, text))
                    continue

        num = is_q_token(txt)
        if num and 1 <= num <= 500:
            y_top = min(pt[1] for pt in box)
            y_bottom = max(pt[1] for pt in box)
            x_left = min(pt[0] for pt in box)
            raw_cands.append((num, x_left, y_top, y_bottom, text))

    if not raw_cands:
        return ([(1, pil_img)], full_text)

    # Detect 1-column vs 2-column layout
    mid_x = W * 0.48
    left_cands = [c for c in raw_cands if c[1] < mid_x]
    right_cands = [c for c in raw_cands if c[1] >= mid_x]
    is_two_col = (len(left_cands) >= 2 and len(right_cands) >= 2)

    columns = []
    if is_two_col:
        columns.append(('left', 0, int(mid_x), left_cands))
        columns.append(('right', int(mid_x), W, right_cands))
    else:
        columns.append(('single', 0, W, raw_cands))

    crops = []

    for col_name, col_left, col_right, col_cands in columns:
        if not col_cands:
            continue

        # Cluster by dominant left margin in this column
        min_x = min(c[1] for c in col_cands)
        valid_qs = [c for c in col_cands if abs(c[1] - min_x) <= 28]
        valid_qs.sort(key=lambda x: x[2])

        if not valid_qs:
            continue

        # Detect footer or next section cutoff after last question in column
        last_q_y = valid_qs[-1][2]
        col_cutoff = H - 8
        for box, text, _ in ocr_result:
            y_top = min(pt[1] for pt in box)
            x_box = min(pt[0] for pt in box)
            if y_top > last_q_y + 35:
                if col_name == 'left' and x_box >= mid_x:
                    continue
                if col_name == 'right' and x_box < mid_x:
                    continue
                t_up = text.upper()
                if any(term in t_up for term in ['SECTION', 'PAGE', 'PREPARED BY', 'IN THE FOLLOWING', 'ANSWER', 'KEY', 'MARKS']):
                    col_cutoff = min(col_cutoff, int(y_top) - 6)

        # Slice each question in this column
        for i, q in enumerate(valid_qs):
            q_num = q[0]
            # Use exact top of the question marker
            top_y = max(0, int(q[2]) - 1)

            if i + 1 < len(valid_qs):
                bottom_y = max(top_y + 20, int(valid_qs[i + 1][2]) - 2)
            else:
                bottom_y = max(top_y + 25, col_cutoff)

            pad_left = max(0, col_left + 10) if col_name == 'right' else max(0, int(min_x) - 14)
            pad_right = min(W, col_right - 6) if col_name == 'left' else min(W, col_right - 8)

            crop_box = (pad_left, top_y, pad_right, bottom_y)
            if crop_box[2] > crop_box[0] + 30 and crop_box[3] > crop_box[1] + 20:
                q_crop = pil_img.crop(crop_box)
                q_trimmed = trim_white_borders(q_crop)
                crops.append((q_num, q_trimmed))

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
    1. Scans each uploaded photo (e.g. photo 1 = Q1..Q8, photo 2 = Q9..Q16...).
    2. Uses RapidOCR to detect question boundaries, formulas, and diagrams.
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

    # Process and save all crops in parallel across multi-core CPU
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
