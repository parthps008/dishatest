import os
import shutil
import uuid
from typing import Optional
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

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

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
