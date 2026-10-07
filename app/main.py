import os
import shutil
import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import TestSubmissionRequest
from app.pdf_parser import parse_pdf_test
from app.test_manager import TestManager
from app.auth import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    authenticate_admin,
    create_session_token,
    verify_session_token,
    is_admin_authenticated,
    SESSION_COOKIE_NAME,
    LEGACY_COOKIE_NAME,
    SESSION_MAX_AGE
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOADS_DIR = os.path.join(BASE_DIR, "data", "uploads")
QUESTION_IMAGES_DIR = os.path.join(STATIC_DIR, "uploads", "questions")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(QUESTION_IMAGES_DIR, exist_ok=True)

app = FastAPI(title="Disha Academy Test Portal")

@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    # Prevent aggressive browser caching of static scripts and templates
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ----------------- Helper for Admin Security -----------------

def check_is_admin(request: Request) -> bool:
    """Returns True only if the user is authenticated as Disha Academy admin."""
    return is_admin_authenticated(request)

def require_admin_auth(request: Request):
    """Enforces admin authentication for API endpoints."""
    if not is_admin_authenticated(request):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized. Admin authentication required. Please log in at /admin/login."
        )

# ----------------- Student Facing Pages -----------------

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Landing / Entry page for students."""
    active_test = TestManager.get_active_test_for_student()
    is_admin = check_is_admin(request)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"active_test": active_test, "is_admin": is_admin}
    )

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request, name: Optional[str] = None, roll: Optional[str] = None):
    """Test interface for students."""
    active_test = TestManager.get_active_test_for_student()
    if not active_test:
        return RedirectResponse(url="/?error=no_active_test")
    
    is_admin = check_is_admin(request)
    return templates.TemplateResponse(
        request=request,
        name="test.html",
        context={
            "test": active_test,
            "student_name": name or "",
            "roll_no": roll or "",
            "is_test_page": True,
            "is_admin": is_admin
        }
    )

@app.get("/result/{submission_id}", response_class=HTMLResponse)
async def result_page(request: Request, submission_id: str):
    """Student result and scorecard review page."""
    submission = TestManager.get_submission(submission_id)
    if not submission:
        return RedirectResponse(url="/?error=submission_not_found")
    
    is_admin = check_is_admin(request)
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={"sub": submission, "is_admin": is_admin}
    )

# ----------------- Admin Auth & Management Pages -----------------

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, msg: Optional[str] = None):
    """Displays secure faculty/admin login page."""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={"is_admin": False, "error_msg": None}
    )

@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Validates faculty credentials and establishes session."""
    if authenticate_admin(username, password):
        token = create_session_token(ADMIN_USERNAME)
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=SESSION_MAX_AGE,
            httponly=True,
            path="/"
        )
        response.set_cookie(
            key=LEGACY_COOKIE_NAME,
            value="1",
            max_age=SESSION_MAX_AGE,
            path="/"
        )
        return response
    else:
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={
                "is_admin": False,
                "error_msg": "Invalid Admin User ID or Password. Please check your credentials.",
                "submitted_username": username
            },
            status_code=401
        )

@app.get("/admin/logout", response_class=HTMLResponse)
async def admin_logout(request: Request):
    """Clears admin authentication session cookies and redirects to login page."""
    response = RedirectResponse(url="/admin/login?msg=logged_out", status_code=302)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=LEGACY_COOKIE_NAME, path="/")
    return response

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin dashboard to manage, upload, generate, view and delete tests. Protected route."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    active_test = TestManager.get_active_test()
    submissions = TestManager.get_active_test_submissions()
    topper = submissions[0] if submissions else None
    response = templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "active_test": active_test,
            "submissions": submissions,
            "topper": topper,
            "is_admin": True,
            "current_admin": ADMIN_USERNAME
        }
    )
    return response

# ----------------- API Endpoints -----------------

@app.get("/api/test/current")
async def get_current_test():
    """Returns the currently active test for students without answers."""
    active_test = TestManager.get_active_test_for_student()
    if not active_test:
        raise HTTPException(status_code=404, detail="No active test currently available.")
    return active_test

@app.post("/api/test/submit")
async def submit_test(submission: TestSubmissionRequest):
    """Submits student answers, calculates scores, and returns scorecard."""
    try:
        result = TestManager.submit_test(submission)
        return {
            "success": True,
            "submission_id": result.id,
            "redirect_url": f"/result/{result.id}",
            "score": result.total_score,
            "max_score": result.max_score,
            "percentage": result.percentage
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/result/{submission_id}")
async def get_submission_api(submission_id: str):
    """Returns detailed submission result."""
    sub = TestManager.get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return sub

@app.get("/api/admin/active-test")
async def get_admin_active_test(request: Request):
    """Returns the full active test details (including answer keys) for admin."""
    require_admin_auth(request)
    active_test = TestManager.get_active_test()
    return {"active_test": active_test}

def optimize_and_save_uploaded_image(upload_file: UploadFile, target_path: str, max_width: int = 1200):
    """
    Compresses and auto-optimizes uploaded mobile screenshots and diagram images.
    Converts huge 3-5MB phone screenshots into crisp ~60-120KB images so tests load instantly on mobile data.
    """
    ext = os.path.splitext(target_path)[1].lower()
    try:
        from PIL import Image, ImageOps
        upload_file.file.seek(0, os.SEEK_END)
        fsize = upload_file.file.tell()
        upload_file.file.seek(0)

        # Fast path: If already a compact JPEG (< 300KB)
        if ext in [".jpg", ".jpeg"] and fsize < 300 * 1024:
            try:
                img = Image.open(upload_file.file)
                if img.width <= max_width:
                    upload_file.file.seek(0)
                    with open(target_path, "wb") as buffer:
                        shutil.copyfileobj(upload_file.file, buffer)
                    return
            except Exception:
                upload_file.file.seek(0)

        upload_file.file.seek(0)
        img = Image.open(upload_file.file)
        img = ImageOps.exif_transpose(img)
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * float(ratio))
            img = img.resize((max_width, new_height), Image.Resampling.BILINEAR if max(img.width, img.height) > 2500 else Image.Resampling.LANCZOS)
        
        if ext in [".jpg", ".jpeg"]:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(target_path, "JPEG", quality=82)
        elif ext == ".png":
            if img.mode == "RGBA":
                alpha = img.split()[-1]
                if alpha.getextrema() == (255, 255):
                    img = img.convert("RGB")
            # Fast PNG compression without slow brute-force filter search
            img.save(target_path, "PNG", compress_level=4)
        elif ext == ".webp":
            img.save(target_path, "WEBP", quality=82)
        else:
            upload_file.file.seek(0)
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
    except Exception:
        upload_file.file.seek(0)
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

@app.post("/api/admin/upload-pdf")
async def upload_pdf_and_parse(
    request: Request,
    file: UploadFile = File(...),
    duration: int = Form(30),
    title_override: Optional[str] = Form(None)
):
    """Uploads a PDF, parses MCQs and returns extracted test structure. Enforces single active test policy."""
    require_admin_auth(request)
    existing_test = TestManager.get_active_test()
    if existing_test:
        raise HTTPException(
            status_code=400,
            detail="An active test is already live. Please delete the current test using the Delete Test button before uploading a new one."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    saved_file_path = os.path.join(UPLOADS_DIR, file.filename)
    with open(saved_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        parsed_data = parse_pdf_test(saved_file_path, override_duration=duration)
        if title_override and title_override.strip():
            parsed_data["title"] = title_override.strip()

        # Set as active test immediately (single test policy)
        active_test = TestManager.set_active_test(parsed_data)

        return {
            "success": True,
            "message": f"Successfully parsed and activated test with {active_test['total_questions']} questions!",
            "test": active_test
        }
    except Exception as e:
        # Clean up file if failed
        if os.path.exists(saved_file_path):
            try:
                os.remove(saved_file_path)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")

@app.post("/api/admin/create-image-test")
async def create_image_test_api(
    request: Request,
    files: List[UploadFile] = File(...),
    duration: int = Form(30),
    title: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    answers_json: Optional[str] = Form(None)
):
    """
    Creates an image-based MCQ test where each uploaded screenshot corresponds to one question (1st image = Q1, 2nd = Q2, etc.).
    Supports up to 50 images with multi-image upload and compression.
    Options are fixed A, B, C, D. Answers are configured and editable by the admin.
    """
    require_admin_auth(request)
    existing_test = TestManager.get_active_test()
    if existing_test:
        raise HTTPException(
            status_code=400,
            detail="An active test is already live. Please delete the current test using the Delete Test button before creating a new one."
        )

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Please upload at least 1 image to create a test.")

    if len(files) > 50:
        raise HTTPException(status_code=400, detail=f"Maximum 50 images allowed per test. You uploaded {len(files)} images.")

    # Parse admin-specified answers if provided
    answers_map: Dict[str, str] = {}
    if answers_json:
        try:
            parsed = json.loads(answers_json)
            if isinstance(parsed, dict):
                answers_map = {str(k): str(v).strip().upper() for k, v in parsed.items()}
            elif isinstance(parsed, list):
                for idx, ans in enumerate(parsed):
                    answers_map[str(idx + 1)] = str(ans).strip().upper()
        except Exception:
            pass

    allowed_exts = {".png", ".jpg", ".jpeg", ".webp"}
    questions = []
    saved_paths = []

    try:
        subject_clean = (subject or "General").strip() or "General"
        test_title = (title or "Disha Academy Image Assessment").strip() or "Disha Academy Image Assessment"

        # Validate file extensions first
        for idx, file in enumerate(files):
            q_no = idx + 1
            filename = file.filename or f"question_{q_no}.jpg"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_exts:
                raise HTTPException(
                    status_code=400,
                    detail=f"File #{q_no} ('{filename}') has an unsupported format. Allowed formats: PNG, JPG, JPEG, WEBP."
                )

        from concurrent.futures import ThreadPoolExecutor

        def process_one_image_file(item):
            idx, file = item
            q_no = idx + 1
            filename = file.filename or f"question_{q_no}.jpg"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_exts:
                ext = ".jpg"

            safe_filename = f"qimg_q{q_no}_{uuid.uuid4().hex[:8]}{ext}"
            target_path = os.path.join(QUESTION_IMAGES_DIR, safe_filename)

            optimize_and_save_uploaded_image(file, target_path)

            img_url = f"/static/uploads/questions/{safe_filename}"
            correct_ans = answers_map.get(str(q_no), "A")
            if correct_ans not in ["A", "B", "C", "D"]:
                correct_ans = "A"

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
                "answer_auto_detected": False,
                "image_url": img_url,
                "subject": subject_clean,
                "marks": 1,
                "negative_marks": 0.0,
                "explanation": None
            }
            return (q_no, target_path, q_data)

        # Process all uploaded screenshots in parallel across CPU cores
        worker_count = min(8, max(2, (os.cpu_count() or 2) * 2))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            processed_results = list(executor.map(process_one_image_file, enumerate(files)))

        # Sort sequentially by question number
        processed_results.sort(key=lambda r: r[0])
        saved_paths = [r[1] for r in processed_results]
        questions = [r[2] for r in processed_results]

        test_data = {
            "id": "test_" + uuid.uuid4().hex[:8],
            "title": test_title,
            "subjects": [subject_clean],
            "duration_minutes": duration if duration > 0 else 30,
            "total_questions": len(questions),
            "questions": questions,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pdf_filename": None,
            "test_type": "image"
        }

        active_test = TestManager.set_active_test(test_data)
        return {
            "success": True,
            "message": f"Successfully created Image Test with {len(questions)} questions!",
            "test": active_test
        }

    except HTTPException:
        for p in saved_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        raise
    except Exception as e:
        for p in saved_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        raise HTTPException(status_code=400, detail=f"Failed to create test from images: {str(e)}")

@app.delete("/api/admin/delete-test")
async def delete_active_test(request: Request):
    """Deletes the active test so a new test can be uploaded."""
    require_admin_auth(request)
    success = TestManager.delete_active_test()
    if success:
        return {"success": True, "message": "Active test has been successfully deleted."}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete active test.")

class UpdateQuestionAnswerRequest(BaseModel):
    q_no: int
    correct_answer: str

@app.post("/api/admin/update-question-answer")
async def update_question_answer(request: Request, payload: UpdateQuestionAnswerRequest):
    """Allows admin to update or override the correct answer for a specific question."""
    require_admin_auth(request)
    success = TestManager.update_question_answer(payload.q_no, payload.correct_answer)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to update answer for Q{payload.q_no}.")
    return {"success": True, "message": f"Updated Q{payload.q_no} correct answer to Option {payload.correct_answer.upper()}."}

class RemoveQuestionImageRequest(BaseModel):
    q_no: int

@app.post("/api/admin/upload-question-image")
async def upload_question_image(
    request: Request,
    q_no: int = Form(...),
    file: UploadFile = File(...)
):
    """Uploads and attaches a diagram/image to a specific question in active test."""
    require_admin_auth(request)

    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail="Invalid image format. Allowed formats: PNG, JPG, JPEG, WEBP, SVG, GIF."
        )

    safe_filename = f"diagram_q{q_no}_{uuid.uuid4().hex[:8]}{ext}"
    target_path = os.path.join(QUESTION_IMAGES_DIR, safe_filename)

    optimize_and_save_uploaded_image(file, target_path)

    image_url = f"/static/uploads/questions/{safe_filename}"
    success = TestManager.attach_question_image(q_no, image_url)
    if not success:
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"Question Q{q_no} not found in active test.")

    return {
        "success": True,
        "q_no": q_no,
        "image_url": image_url,
        "message": f"Diagram successfully attached to Question {q_no}!"
    }

@app.post("/api/admin/remove-question-image")
async def remove_question_image(request: Request, payload: RemoveQuestionImageRequest):
    """Removes attached diagram/image from a specific question."""
    require_admin_auth(request)
    success = TestManager.remove_question_image(payload.q_no)
    if not success:
        raise HTTPException(status_code=400, detail=f"Question Q{payload.q_no} not found in active test.")
    return {
        "success": True,
        "q_no": payload.q_no,
        "message": f"Diagram removed from Question {payload.q_no}."
    }

class OptionPayload(BaseModel):
    key: str
    text: str
    image_url: Optional[str] = None

class UpdateQuestionFullRequest(BaseModel):
    q_no: int
    text: str
    options: List[OptionPayload]
    correct_answer: str
    subject: Optional[str] = "General"
    marks: Optional[int] = 1

@app.post("/api/admin/update-question-full")
async def update_question_full_api(request: Request, payload: UpdateQuestionFullRequest):
    """Update question statement, option texts, correct answer, and subject."""
    require_admin_auth(request)
    opts = [o.model_dump() if hasattr(o, "model_dump") else o.dict() for o in payload.options]
    updated = TestManager.update_question_full(
        q_no=payload.q_no,
        text=payload.text,
        options=opts,
        correct_answer=payload.correct_answer,
        subject=payload.subject,
        marks=payload.marks
    )
    if not updated:
        raise HTTPException(status_code=400, detail=f"Failed to update Question {payload.q_no}.")
    return {
        "success": True,
        "message": f"Question {payload.q_no} successfully updated!",
        "question": updated
    }

class DeleteQuestionRequest(BaseModel):
    q_no: int

@app.post("/api/admin/delete-question")
async def delete_question_api(request: Request, payload: DeleteQuestionRequest):
    """Deletes a question from active test and re-indexes remaining questions."""
    require_admin_auth(request)
    success = TestManager.delete_question(payload.q_no)
    if not success:
        raise HTTPException(status_code=400, detail=f"Question Q{payload.q_no} could not be deleted.")
    active_test = TestManager.get_active_test()
    total_q = active_test.get("total_questions", 0) if active_test else 0
    return {
        "success": True,
        "message": f"Question {payload.q_no} deleted. Remaining {total_q} questions re-indexed sequentially.",
        "total_questions": total_q
    }

class AddQuestionRequest(BaseModel):
    text: str
    options: List[OptionPayload]
    correct_answer: str
    subject: Optional[str] = "General"
    marks: Optional[int] = 1
    image_url: Optional[str] = None

@app.post("/api/admin/add-question")
async def add_question_api(request: Request, payload: AddQuestionRequest):
    """Manually append a new question to the active test."""
    require_admin_auth(request)
    opts = [o.model_dump() if hasattr(o, "model_dump") else o.dict() for o in payload.options]
    new_q = TestManager.add_question(
        text=payload.text,
        options=opts,
        correct_answer=payload.correct_answer,
        subject=payload.subject,
        marks=payload.marks,
        image_url=payload.image_url
    )
    if not new_q:
        raise HTTPException(status_code=400, detail="Failed to add new question. Ensure a test is active.")
    active_test = TestManager.get_active_test()
    return {
        "success": True,
        "message": f"Question {new_q['q_no']} added successfully!",
        "question": new_q,
        "total_questions": active_test.get("total_questions", 0)
    }

@app.post("/api/admin/upload-option-image")
async def upload_option_image(
    request: Request,
    q_no: int = Form(...),
    opt_key: str = Form(...),
    file: UploadFile = File(...)
):
    """Uploads and attaches a diagram/image to a specific option (A, B, C, D) of a question."""
    require_admin_auth(request)

    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail="Invalid image format. Allowed formats: PNG, JPG, JPEG, WEBP, SVG, GIF."
        )

    safe_filename = f"opt_{opt_key.lower()}_q{q_no}_{uuid.uuid4().hex[:8]}{ext}"
    target_path = os.path.join(QUESTION_IMAGES_DIR, safe_filename)

    optimize_and_save_uploaded_image(file, target_path)

    image_url = f"/static/uploads/questions/{safe_filename}"
    success = TestManager.attach_option_image(q_no, opt_key, image_url)
    if not success:
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"Question Q{q_no} Option {opt_key} not found.")

    return {
        "success": True,
        "q_no": q_no,
        "opt_key": opt_key.upper(),
        "image_url": image_url,
        "message": f"Option {opt_key.upper()} image attached to Question {q_no}!"
    }

class RemoveOptionImageRequest(BaseModel):
    q_no: int
    opt_key: str

@app.post("/api/admin/remove-option-image")
async def remove_option_image_api(request: Request, payload: RemoveOptionImageRequest):
    """Removes attached diagram/image from a specific option."""
    require_admin_auth(request)
    success = TestManager.remove_option_image(payload.q_no, payload.opt_key)
    if not success:
        raise HTTPException(status_code=400, detail=f"Option {payload.opt_key} in Q{payload.q_no} not found.")
    return {
        "success": True,
        "q_no": payload.q_no,
        "opt_key": payload.opt_key.upper(),
        "message": f"Image removed from Q{payload.q_no} Option {payload.opt_key.upper()}."
    }


@app.get("/api/admin/submissions")
async def get_admin_submissions(request: Request):
    """Returns list of student test submissions strictly for the active test."""
    require_admin_auth(request)
    subs = TestManager.get_active_test_submissions()
    return {
        "submissions": subs,
        "topper": subs[0] if subs else None
    }

@app.get("/api/admin/load-sample")
async def load_sample_test(request: Request):
    """Helper to load the sample Disha Academy mock test directly for demo/testing."""
    require_admin_auth(request)
    sample_path = os.path.join(BASE_DIR, "sample_tests", "disha_academy_mock_test.pdf")
    if not os.path.exists(sample_path):
        from generate_sample_pdf import generate_sample_pdf
        generate_sample_pdf(sample_path)
    
    parsed = parse_pdf_test(sample_path, override_duration=30)
    saved = TestManager.set_active_test(parsed)
    return {"success": True, "message": "Sample Disha Academy Test loaded!", "test": saved}
