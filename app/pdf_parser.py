import re
import os
import pdfplumber
from pypdf import PdfReader
from typing import List, Dict, Tuple, Optional, Any

# Common STEM/School Subjects to look for
KNOWN_SUBJECTS = [
    "PHYSICS", "CHEMISTRY", "MATHEMATICS", "MATHS", "BIOLOGY",
    "BOTANY", "ZOOLOGY", "SCIENCE", "GENERAL SCIENCE", "ENGLISH",
    "REASONING", "GENERAL KNOWLEDGE", "APTITUDE", "COMPUTER SCIENCE"
]

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from PDF using pdfplumber with fallback to pypdf."""
    full_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True)
                if not text:
                    text = page.extract_text()
                if text:
                    full_text.append(text)
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
        # Ignore page numbers or dates
        if re.search(r'^(page\s+\d+|date:|time:|\d+/\d+)', line, re.IGNORECASE):
            continue
        if any(term in line.lower() for term in ["test", "academy", "disha", "exam", "paper", "quiz", "assessment", "mock"]):
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

def extract_answer_keys(text: str) -> Dict[int, str]:
    """Extract answers from an 'Answer Key' or 'Solutions' section at the end."""
    answers = {}
    
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

    if key_text:
        # Look for pairs like "1. A", "1-A", "1.(B)", "1: C", "1) D", "Q1: A", "Q.1 - B"
        pairs = re.findall(r'(?:Q\.?|Question\s*)?(\d+)[\.\)\:\s\-]+(?:\()?([A-Da-d])(?:\))?', key_text)
        for q_num, ans in pairs:
            try:
                answers[int(q_num)] = ans.upper()
            except ValueError:
                continue

    return answers

def parse_mcq_questions(text: str, detected_subjects: List[str]) -> List[Dict[str, Any]]:
    """
    Parse questions, options, subjects, and inline answers from extracted text.
    Handles multiple common question & option patterns.
    """
    answer_key_dict = extract_answer_keys(text)

    # Cut off text before the Answer Key section so answer key doesn't get parsed as questions
    cutoff_match = re.search(r'\n\s*(?:ANSWER\s*KEY|ANSWERS\s*[\:\-]|SOLUTIONS\s*[\:\-])', text, re.IGNORECASE)
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

    # Match option tokens e.g. "(A)", "[A]", "A.", "A)", "A:"
    opt_token_regex = re.compile(
        r'(?:^|\s+)[\(\[]?([A-Da-d])[\)\]\.\:\-]\s*'
    )

    subj_header_regex = re.compile(
        r'^\s*(?:SECTION|PART)?\s*[\w\d\:\-]*\s*(' + '|'.join(KNOWN_SUBJECTS) + r')\s*(?:SECTION|PART)?\s*$',
        re.IGNORECASE
    )

    inline_ans_regex = re.compile(
        r'(?:Ans(?:wer)?|Correct\s*(?:Option)?|Key)[\s\:\-\=]+[\(\[]?([A-D])[\)\]]?',
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

        # If answer was found in answer key table
        q_num = q_dict["q_no"]
        if q_num in answer_key_dict:
            q_dict["correct_answer"] = answer_key_dict[q_num]
            q_dict["correct_answer_set"] = True
        elif not q_dict.get("correct_answer_set"):
            q_dict["correct_answer"] = "A"

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
                if candidate_q_no > 0 and (candidate_q_no <= 500):
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
                "subject": current_subject,
                "marks": 1,
                "negative_marks": 0.0,
                "explanation": None
            }
            current_option_key = None
            continue

        if current_q:
            # Check for option tokens in line
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
                # Append to question text
                current_q["text"] += " " + stripped

    finalize_question(current_q)

    # Normalize question numbers and ensure options A, B, C, D exist
    processed_questions = []
    for idx, q in enumerate(questions):
        q["id"] = idx + 1
        q["q_no"] = idx + 1
        
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
    
    questions = parse_mcq_questions(raw_text, detected_subjects)
    
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
