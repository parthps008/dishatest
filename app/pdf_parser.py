import re
import os
import pdfplumber
from pypdf import PdfReader
from typing import List, Dict, Tuple, Optional, Any

# Common STEM/School Subjects to look for
KNOWN_SUBJECTS = [
    "PHYSICS", "CHEMISTRY", "MATHEMATICS", "MATHS", "BIOLOGY",
    "BOTANY", "ZOOLOGY", "SCIENCE", "GENERAL SCIENCE", "ENGLISH",
    "REASONING", "GENERAL KNOWLEDGE", "APTITUDE", "COMPUTER SCIENCE",
    "JAVA", "PROGRAMMING", "DATA STRUCTURES", "INFORMATION TECHNOLOGY"
]

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract clean raw text from PDF using pdfplumber with fallback to pypdf.
    Prefers natural reading order (layout=False) to avoid multi-thousand space padding.
    """
    full_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=False)
                if not text or len(text.strip()) < 20:
                    text = page.extract_text()
                if not text or len(text.strip()) < 20:
                    text = page.extract_text(layout=True)
                if text:
                    cleaned_lines = [re.sub(r'[ \t]+$', '', line) for line in text.splitlines()]
                    full_text.append("\n".join(cleaned_lines))
    except Exception as e:
        print(f"pdfplumber extraction warning: {e}, falling back to pypdf")

    if not full_text:
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
        except Exception as e:
            print(f"pypdf extraction error: {e}")

    return "\n".join(full_text)

def detect_test_meta(text: str, default_filename: str = "") -> Tuple[str, List[str], Optional[int]]:
    """Detect test title, subjects, and duration from PDF text."""
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.split("\n") if line.strip()]
    title = ""
    subjects = []
    duration = None

    # Title detection from header lines
    for i in range(min(8, len(lines))):
        line = lines[i]
        if re.search(r'^(page\s+\d+|date:|time:|\d+/\d+)', line, re.IGNORECASE):
            continue
        if any(term in line.lower() for term in ["test", "academy", "disha", "exam", "paper", "quiz", "assessment", "mock", "java"]):
            title = line
            break
    
    if not title and lines:
        title = lines[0][:80]
    if not title:
        base_name = os.path.splitext(os.path.basename(default_filename))[0] if default_filename else "Disha Academy Assessment Test"
        title = base_name.replace("_", " ").replace("-", " ").title()

    # Detect subjects from text
    upper_text = text.upper()
    for subj in KNOWN_SUBJECTS:
        if re.search(rf'\b{subj}\b', upper_text):
            canonical = subj.title()
            if canonical == "Maths":
                canonical = "Mathematics"
            if canonical not in subjects:
                subjects.append(canonical)

    if not subjects:
        subjects = ["General"]

    # Detect duration e.g. "Time: 60 Minutes" or "Duration: 45 min" or "Time Allowed: 1 Hour"
    time_match = re.search(r'(?:time|duration|time\s+allowed)[\s\:\-]+(\d+)\s*(?:minutes|mins|min|m\b)', text, re.IGNORECASE)
    if time_match:
        try:
            duration = int(time_match.group(1))
        except Exception:
            pass
    else:
        hour_match = re.search(r'(?:time|duration|time\s+allowed)[\s\:\-]+(\d+(?:\.\d+)?)\s*(?:hours|hour|hr|hrs)', text, re.IGNORECASE)
        if hour_match:
            try:
                duration = int(float(hour_match.group(1)) * 60)
            except Exception:
                pass

    return title, subjects, duration

def extract_table_answers(pdf_path: str) -> Dict[int, str]:
    """
    Extract answers from visual tables (e.g. grid format like Q1-Q5, Q6-Q10).
    Supports horizontal row pairs, vertical columns, multi-column tables, and cell pairs.
    """
    answers = {}
    if not pdf_path or not os.path.exists(pdf_path):
        return answers

    q_token_re = re.compile(r'^(?:Q(?:uestion)?\.?\s*)?(\d+)[\.\)]?$', re.IGNORECASE)
    ans_token_re = re.compile(r'^\(?([A-Da-d])\)?$')
    pair_re = re.compile(r'(?:Q(?:uestion)?\.?\s*)?(\d+)[\.\)\:\s\-]+(?:\()?([A-Da-d])(?:\))?', re.IGNORECASE)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for table in tables:
                    if not table or len(table) < 1:
                        continue

                    r = 0
                    while r < len(table):
                        row1 = [c.strip() if c else '' for c in table[r]]

                        # Check horizontal grid: row1 = Q-numbers, row2 = Answers
                        if r + 1 < len(table):
                            row2 = [c.strip() if c else '' for c in table[r+1]]
                            q_matches = [q_token_re.match(c) for c in row1]
                            a_matches = [ans_token_re.match(c) for c in row2]
                            
                            valid_q = [m for m in q_matches if m]
                            valid_a = [m for m in a_matches if m]

                            if len(valid_q) >= 2 and len(valid_a) >= 2 and len(row1) == len(row2):
                                for qm, am in zip(q_matches, a_matches):
                                    if qm and am:
                                        answers[int(qm.group(1))] = am.group(1).upper()
                                r += 2
                                continue

                        # Check vertical or multi-column: [Q, Ans, Q, Ans]
                        for c_idx in range(0, len(row1) - 1, 2):
                            qm = q_token_re.match(row1[c_idx])
                            am = ans_token_re.match(row1[c_idx + 1])
                            if qm and am:
                                answers[int(qm.group(1))] = am.group(1).upper()

                        # Check combined cells: 'Q1: A'
                        for c in row1:
                            m = pair_re.match(c)
                            if m:
                                answers[int(m.group(1))] = m.group(2).upper()

                        r += 1
    except Exception as e:
        print(f"Notice: Table answer extraction skipped: {e}")

    return answers

def extract_text_grid_answers(text: str) -> Dict[int, str]:
    """
    Extract answers from multiline grids in plain text.
    Handles lines of Q numbers followed by lines of answer letters.
    """
    answers = {}
    lines = [re.sub(r'\s+', ' ', l).strip() for l in text.splitlines() if l.strip()]
    q_tok_re = re.compile(r'^(?:Q(?:uestion)?\.?\s*)?(\d+)[\.\)]?$', re.IGNORECASE)
    ans_tok_re = re.compile(r'^\(?([A-Da-d])\)?$')

    i = 0
    while i < len(lines):
        line1 = lines[i]
        tokens1 = line1.split()
        q_nums = []
        for tok in tokens1:
            m = q_tok_re.match(tok)
            if m:
                q_nums.append(int(m.group(1)))
            else:
                break

        if len(q_nums) >= 2 and len(q_nums) == len(tokens1) and i + 1 < len(lines):
            line2 = lines[i+1]
            tokens2 = line2.split()
            ans_letters = []
            for tok in tokens2:
                m = ans_tok_re.match(tok)
                if m:
                    ans_letters.append(m.group(1).upper())
                else:
                    break

            if len(ans_letters) == len(q_nums):
                for q, a in zip(q_nums, ans_letters):
                    answers[q] = a
                i += 2
                continue
        i += 1

    return answers

def extract_answer_keys(text: str, pdf_path: Optional[str] = None) -> Dict[int, str]:
    """
    Multi-strategy answer key extractor.
    Combines:
    1. Table-based extraction from PDF
    2. Text-based multiline grid extraction
    3. Pair matching ('1. A', 'Q1: A', '1-A', '1) B')
    4. Compact stream ('1A 2B 3C')
    """
    answers = {}

    # Strategy 1: Visual tables in PDF
    if pdf_path:
        table_answers = extract_table_answers(pdf_path)
        answers.update(table_answers)

    # Strategy 2: Search for Answer Key section in text
    key_section_patterns = [
        r'(?:ANSWER\s*KEY|ANSWERS|CORRECT\s*OPTIONS|SOLUTIONS|KEY\s*SHEET)(.*?)$',
        r'(\bKEY\b[\s\:\-\=]+)(.*?)$'
    ]
    key_text = ""
    for pat in key_section_patterns:
        match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if match:
            key_text = match.group(0)
            break

    search_scope = key_text if key_text else text

    # Strategy 3: Text-based multiline grid
    grid_answers = extract_text_grid_answers(search_scope)
    for q, a in grid_answers.items():
        if q not in answers:
            answers[q] = a

    # Strategy 4: Pairs like '1. A', 'Q1: A', '1-A', '1) B'
    pairs = re.findall(r'(?:Q(?:uestion)?\.?\s*)?(\d+)[\.\)\:\s\-]+(?:\()?([A-Da-d])(?:\))?', search_scope)
    for q_num_str, ans_str in pairs:
        try:
            q_num = int(q_num_str)
            if q_num not in answers and 1 <= q_num <= 500:
                answers[q_num] = ans_str.upper()
        except ValueError:
            continue

    # Strategy 5: Stream of answers like '1A 2B 3C'
    compact_pairs = re.findall(r'\b(\d+)\s*([A-Da-d])\b', search_scope)
    for q_num_str, ans_str in compact_pairs:
        try:
            q_num = int(q_num_str)
            if q_num not in answers and 1 <= q_num <= 500:
                answers[q_num] = ans_str.upper()
        except ValueError:
            continue

    return answers

def parse_mcq_questions(text: str, detected_subjects: List[str], pdf_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse questions, options, subjects, and accurately map answers from extracted text and tables.
    """
    answer_key_dict = extract_answer_keys(text, pdf_path=pdf_path)

    # Cut off text before the Answer Key section so answer key doesn't get parsed as questions
    cutoff_match = re.search(r'\n\s*(?:ANSWER\s*KEY|ANSWERS\s*[\:\-]|SOLUTIONS\s*[\:\-]|KEY\s*SHEET)', text, re.IGNORECASE)
    body_text = text[:cutoff_match.start()] if cutoff_match else text

    lines = body_text.splitlines()

    questions: List[Dict[str, Any]] = []
    current_q: Optional[Dict[str, Any]] = None
    current_subject = detected_subjects[0] if detected_subjects else "General"
    current_option_key = None

    q_start_regex = re.compile(
        r'^\s*(?:Q(?:uestion)?\.?\s*)?(\d+)[\.\)\:\-]\s*(.*)',
        re.IGNORECASE
    )
    alt_q_start_regex = re.compile(
        r'^\s*\(([0-9]+)\)\s*(.*)',
        re.IGNORECASE
    )

    # Match option tokens e.g. "(A)", "[A]", "A.", "a.", "A)", "a)", "A:"
    opt_token_regex = re.compile(
        r'(?:^|\s+)[\(\[]?([A-Da-d])[\)\]\.\:\-]\s*'
    )

    subj_header_regex = re.compile(
        r'^\s*(?:SECTION|PART)?\s*[\w\d\:\-]*\s*(' + '|'.join(KNOWN_SUBJECTS) + r')\s*(?:SECTION|PART)?\s*$',
        re.IGNORECASE
    )

    inline_ans_regex = re.compile(
        r'(?:Ans(?:wer)?|Correct\s*(?:Option)?|Key)[\s\:\-\=]+[\(\[]?([A-Da-d])[\)\]]?',
        re.IGNORECASE
    )

    def finalize_question(q_dict: Optional[Dict[str, Any]]):
        if not q_dict:
            return
        q_dict["text"] = re.sub(r'\s+', ' ', q_dict["text"]).strip()
        cleaned_options = []
        for opt in q_dict.get("options", []):
            opt_text = re.sub(r'\s+', ' ', opt["text"]).strip()
            # Remove any trailing inline answer from option text
            ans_match = inline_ans_regex.search(opt_text)
            if ans_match and not q_dict.get("correct_answer_set"):
                q_dict["correct_answer"] = ans_match.group(1).upper()
                q_dict["correct_answer_set"] = True
                opt_text = opt_text[:ans_match.start()].strip()
            cleaned_options.append({"key": opt["key"], "text": opt_text})
        
        q_dict["options"] = cleaned_options

        # Map answer from answer keys
        q_num = q_dict["q_no"]
        if q_num in answer_key_dict:
            q_dict["correct_answer"] = answer_key_dict[q_num]
            q_dict["correct_answer_set"] = True
            q_dict["answer_auto_detected"] = True
        elif q_dict.get("correct_answer_set"):
            q_dict["answer_auto_detected"] = True
        else:
            q_dict["correct_answer"] = "A"
            q_dict["answer_auto_detected"] = False

        if len(q_dict["options"]) >= 2 and len(q_dict["text"]) > 2:
            questions.append(q_dict)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        subj_match = subj_header_regex.match(stripped)
        if subj_match:
            sub_name = subj_match.group(1).title()
            if sub_name == "Maths":
                sub_name = "Mathematics"
            current_subject = sub_name
            continue

        ans_on_line = inline_ans_regex.search(stripped)
        if ans_on_line and current_q:
            current_q["correct_answer"] = ans_on_line.group(1).upper()
            current_q["correct_answer_set"] = True
            stripped = stripped[:ans_on_line.start()].strip()
            if not stripped:
                continue

        q_match = q_start_regex.match(stripped) or alt_q_start_regex.match(stripped)
        is_new_q = False
        if q_match:
            try:
                candidate_q_no = int(q_match.group(1))
                if 0 < candidate_q_no <= 500:
                    is_new_q = True
            except ValueError:
                is_new_q = False

        if is_new_q:
            finalize_question(current_q)
            q_no = int(q_match.group(1))
            q_text = q_match.group(2)
            current_q = {
                "id": len(questions) + 1,
                "q_no": q_no,
                "text": q_text,
                "options": [],
                "correct_answer": "A",
                "correct_answer_set": False,
                "answer_auto_detected": False,
                "subject": current_subject,
                "marks": 1,
                "negative_marks": 0.0,
                "explanation": None
            }
            current_option_key = None
            continue

        if current_q:
            opt_matches = list(opt_token_regex.finditer(line))
            if opt_matches:
                for i, m in enumerate(opt_matches):
                    opt_key = m.group(1).upper()
                    start_pos = m.end()
                    end_pos = opt_matches[i+1].start() if i + 1 < len(opt_matches) else len(line)
                    opt_val = line[start_pos:end_pos].strip()

                    # Check if already exists
                    existing = next((o for o in current_q["options"] if o["key"] == opt_key), None)
                    if existing:
                        existing["text"] += " " + opt_val
                    else:
                        current_q["options"].append({"key": opt_key, "text": opt_val})
                
                current_option_key = opt_matches[-1].group(1).upper()
                continue

            # If inside an option, append multiline option text
            if current_option_key:
                for o in current_q["options"]:
                    if o["key"] == current_option_key:
                        o["text"] += " " + stripped
                        break
            else:
                current_q["text"] += " " + stripped

    finalize_question(current_q)

    # Normalize question numbers and ensure options A, B, C, D exist
    processed_questions = []
    for idx, q in enumerate(questions):
        orig_q_no = q["q_no"]
        q["id"] = idx + 1
        q["q_no"] = idx + 1
        
        # If question was re-indexed and wasn't mapped earlier, check if idx+1 matches
        if not q.get("correct_answer_set"):
            if (idx + 1) in answer_key_dict:
                q["correct_answer"] = answer_key_dict[idx + 1]
                q["answer_auto_detected"] = True
            elif orig_q_no in answer_key_dict:
                q["correct_answer"] = answer_key_dict[orig_q_no]
                q["answer_auto_detected"] = True

        opts = {o["key"]: o["text"] for o in q["options"]}
        sorted_opts = []
        for key in ["A", "B", "C", "D"]:
            if key in opts and opts[key].strip():
                sorted_opts.append({"key": key, "text": opts[key].strip()})
            else:
                sorted_opts.append({"key": key, "text": f"Option {key}"})
        q["options"] = sorted_opts
        
        q.pop("correct_answer_set", None)
        processed_questions.append(q)

    return processed_questions

def parse_pdf_test(pdf_path: str, override_duration: Optional[int] = None) -> Dict[str, Any]:
    """Complete workflow: extracts text, detects metadata, parses MCQs, builds TestData."""
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text.strip():
        raise ValueError("Could not extract any text from the provided PDF file.")

    detected_title, detected_subjects, detected_duration = detect_test_meta(raw_text, pdf_path)
    
    questions = parse_mcq_questions(raw_text, detected_subjects, pdf_path=pdf_path)
    
    if not questions:
        raise ValueError(
            "No MCQ questions could be parsed from the PDF. "
            "Please ensure questions follow standard formats like '1. Question...' and options '(A) ... (B) ...'."
        )

    # Collect actual subjects present in questions
    subjects_in_q = []
    for q in questions:
        subj = q.get("subject", "General")
        if subj not in subjects_in_q:
            subjects_in_q.append(subj)

    final_subjects = subjects_in_q if subjects_in_q else detected_subjects
    final_duration = override_duration if override_duration and override_duration > 0 else (detected_duration or 30)

    return {
        "title": detected_title,
        "subjects": final_subjects,
        "duration_minutes": final_duration,
        "total_questions": len(questions),
        "questions": questions,
        "pdf_filename": os.path.basename(pdf_path)
    }
