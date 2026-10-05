from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class Option(BaseModel):
    key: str # "A", "B", "C", "D"
    text: str
    image_url: Optional[str] = None


class Question(BaseModel):
    id: int
    q_no: int
    text: str
    options: List[Option]
    correct_answer: str = "A" # "A", "B", "C", "D"
    answer_auto_detected: Optional[bool] = True
    image_url: Optional[str] = None # Attached diagram/image URL
    subject: str = "General"
    marks: int = 1
    negative_marks: float = 0.0
    explanation: Optional[str] = None

class TestConfig(BaseModel):
    duration_minutes: int = 30
    title: Optional[str] = None
    subject: Optional[str] = None

class TestData(BaseModel):
    id: str
    title: str
    subjects: List[str] = []
    duration_minutes: int = 30
    total_questions: int
    questions: List[Question]
    created_at: str
    pdf_filename: Optional[str] = None

class StudentAnswer(BaseModel):
    q_no: int
    selected_option: Optional[str] = None # "A", "B", "C", "D" or None

class TestSubmissionRequest(BaseModel):
    test_id: str
    student_name: str
    roll_no: Optional[str] = "N/A"
    answers: Dict[int, Optional[str]] = Field(default_factory=dict)
    time_taken_seconds: int = 0
    auto_submitted: bool = False

class QuestionResult(BaseModel):
    q_no: int
    text: str
    options: List[Option]
    subject: str
    selected_option: Optional[str]
    correct_answer: str
    is_correct: bool
    is_attempted: bool
    image_url: Optional[str] = None
    explanation: Optional[str] = None

class SubjectScore(BaseModel):
    subject: str
    total: int
    attempted: int
    correct: int
    incorrect: int
    unattempted: int
    score: float
    percentage: float

class SubmissionResult(BaseModel):
    id: str
    test_id: str
    test_title: str
    student_name: str
    roll_no: str
    total_questions: int
    attempted_count: int
    correct_count: int
    wrong_count: int
    unattempted_count: int
    total_score: float
    max_score: float
    percentage: float
    time_taken_seconds: int
    duration_minutes: int
    auto_submitted: bool
    submitted_at: str
    subject_scores: List[SubjectScore]
    question_results: List[QuestionResult]
