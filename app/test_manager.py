import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models import (
    TestData, Question, TestSubmissionRequest,
    SubmissionResult, QuestionResult, SubjectScore
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ACTIVE_TEST_FILE = os.path.join(DATA_DIR, "active_test.json")
SUBMISSIONS_DIR = os.path.join(DATA_DIR, "submissions")
SUBMISSIONS_INDEX_FILE = os.path.join(DATA_DIR, "submissions_index.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)

class TestManager:
    @staticmethod
    def get_active_test() -> Optional[Dict[str, Any]]:
        """Get the currently active test with all details (including answers for admin)."""
        if not os.path.exists(ACTIVE_TEST_FILE):
            return None
        try:
            with open(ACTIVE_TEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading active test: {e}")
            return None

    @staticmethod
    def get_active_test_for_student() -> Optional[Dict[str, Any]]:
        """Get the active test sanitized for students (no correct answers or explanations)."""
        test = TestManager.get_active_test()
        if not test:
            return None

        # Deep copy sanitized questions
        sanitized_questions = []
        for q in test.get("questions", []):
            sanitized_questions.append({
                "id": q["id"],
                "q_no": q["q_no"],
                "text": q["text"],
                "options": q["options"],
                "image_url": q.get("image_url"),
                "subject": q.get("subject", "General"),
                "marks": q.get("marks", 1)
            })

        return {
            "id": test["id"],
            "title": test["title"],
            "subjects": test.get("subjects", []),
            "duration_minutes": test["duration_minutes"],
            "total_questions": len(sanitized_questions),
            "questions": sanitized_questions,
            "created_at": test["created_at"],
            "pdf_filename": test.get("pdf_filename", "")
        }

    @staticmethod
    def set_active_test(test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save and activate a new test. Overwrites if an active test exists."""
        if "id" not in test_data:
            test_data["id"] = "test_" + uuid.uuid4().hex[:8]
        if "created_at" not in test_data:
            test_data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(ACTIVE_TEST_FILE, "w", encoding="utf-8") as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)

        return test_data

    @staticmethod
    def delete_active_test() -> bool:
        """
        Delete the currently active test and all associated student logs/submissions.
        Enforces test-wise logs: when a test is deleted, all its student records are deleted too.
        """
        active_test = TestManager.get_active_test()
        test_id = active_test.get("id") if active_test else None

        # 1. Delete all submission files for this test
        if test_id and os.path.exists(SUBMISSIONS_INDEX_FILE):
            try:
                with open(SUBMISSIONS_INDEX_FILE, "r", encoding="utf-8") as f:
                    index = json.load(f)
                
                remaining_index = []
                for sub in index:
                    if sub.get("test_id") == test_id:
                        sub_file = os.path.join(SUBMISSIONS_DIR, f"{sub['id']}.json")
                        if os.path.exists(sub_file):
                            try:
                                os.remove(sub_file)
                            except Exception as e:
                                print(f"Error removing sub file {sub_file}: {e}")
                    else:
                        remaining_index.append(sub)

                with open(SUBMISSIONS_INDEX_FILE, "w", encoding="utf-8") as f:
                    json.dump(remaining_index, f, indent=2)
            except Exception as e:
                print(f"Error cleaning submissions for test {test_id}: {e}")

        # 2. Delete the active test file
        if os.path.exists(ACTIVE_TEST_FILE):
            try:
                os.remove(ACTIVE_TEST_FILE)
                return True
            except Exception as e:
                print(f"Error removing active test: {e}")
                return False
        return True

    @staticmethod
    def update_question_answer(q_no: int, new_answer: str) -> bool:
        """Update correct answer for a specific question in active test."""
        active_test = TestManager.get_active_test()
        if not active_test or "questions" not in active_test:
            return False

        new_answer = new_answer.strip().upper()
        if new_answer not in ["A", "B", "C", "D"]:
            return False

        found = False
        for q in active_test["questions"]:
            if q.get("q_no") == q_no:
                q["correct_answer"] = new_answer
                q["answer_auto_detected"] = False
                found = True
                break

        if found:
            with open(ACTIVE_TEST_FILE, "w", encoding="utf-8") as f:
                json.dump(active_test, f, indent=2, ensure_ascii=False)
            return True
        return False

    @staticmethod
    def attach_question_image(q_no: int, image_url: str) -> bool:
        """Attach an image/diagram URL to a specific question."""
        active_test = TestManager.get_active_test()
        if not active_test or "questions" not in active_test:
            return False

        found = False
        for q in active_test["questions"]:
            if q.get("q_no") == q_no:
                q["image_url"] = image_url
                found = True
                break

        if found:
            with open(ACTIVE_TEST_FILE, "w", encoding="utf-8") as f:
                json.dump(active_test, f, indent=2, ensure_ascii=False)
            return True
        return False

    @staticmethod
    def remove_question_image(q_no: int) -> bool:
        """Remove attached image/diagram from a specific question."""
        active_test = TestManager.get_active_test()
        if not active_test or "questions" not in active_test:
            return False

        found = False
        for q in active_test["questions"]:
            if q.get("q_no") == q_no:
                old_url = q.get("image_url")
                if old_url:
                    clean_path = old_url.lstrip("/")
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    local_file = os.path.join(base_dir, clean_path.replace("/", os.sep))
                    if os.path.exists(local_file):
                        try:
                            os.remove(local_file)
                        except Exception:
                            pass
                q["image_url"] = None
                found = True
                break

        if found:
            with open(ACTIVE_TEST_FILE, "w", encoding="utf-8") as f:
                json.dump(active_test, f, indent=2, ensure_ascii=False)
            return True
        return False

    @staticmethod
    def submit_test(submission: TestSubmissionRequest) -> SubmissionResult:
        """Grade student answers against active test and save submission."""
        active_test = TestManager.get_active_test()
        if not active_test or active_test["id"] != submission.test_id:
            # If active test ID matches or fallback to active test if ID isn't set
            if not active_test:
                raise ValueError("No active test currently running.")

        questions = active_test.get("questions", [])
        q_map = {q["q_no"]: q for q in questions}

        total_questions = len(questions)
        attempted_count = 0
        correct_count = 0
        wrong_count = 0
        unattempted_count = 0
        total_score = 0.0
        max_score = sum(q.get("marks", 1) for q in questions)

        subject_stats: Dict[str, Dict[str, Any]] = {}
        question_results: List[QuestionResult] = []

        for q in questions:
            q_no = q["q_no"]
            subj = q.get("subject", "General")
            if subj not in subject_stats:
                subject_stats[subj] = {
                    "subject": subj,
                    "total": 0,
                    "attempted": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "unattempted": 0,
                    "score": 0.0
                }
            subject_stats[subj]["total"] += 1

            # Get student answer (keys can be string or int)
            selected = submission.answers.get(q_no) or submission.answers.get(str(q_no))
            if selected:
                selected = str(selected).upper().strip()

            correct = q.get("correct_answer", "A").upper().strip()
            is_attempted = bool(selected)
            is_correct = (selected == correct) if is_attempted else False
            marks = q.get("marks", 1)

            if is_attempted:
                attempted_count += 1
                subject_stats[subj]["attempted"] += 1
                if is_correct:
                    correct_count += 1
                    total_score += marks
                    subject_stats[subj]["correct"] += 1
                    subject_stats[subj]["score"] += marks
                else:
                    wrong_count += 1
                    subject_stats[subj]["incorrect"] += 1
            else:
                unattempted_count += 1
                subject_stats[subj]["unattempted"] += 1

            question_results.append(QuestionResult(
                q_no=q_no,
                text=q["text"],
                options=q["options"],
                subject=subj,
                selected_option=selected,
                correct_answer=correct,
                is_correct=is_correct,
                is_attempted=is_attempted,
                image_url=q.get("image_url"),
                explanation=q.get("explanation")
            ))

        percentage = round((total_score / max_score * 100), 2) if max_score > 0 else 0.0

        subject_scores_list = []
        for s_name, s_data in subject_stats.items():
            s_pct = round((s_data["score"] / s_data["total"] * 100), 2) if s_data["total"] > 0 else 0.0
            subject_scores_list.append(SubjectScore(
                subject=s_data["subject"],
                total=s_data["total"],
                attempted=s_data["attempted"],
                correct=s_data["correct"],
                incorrect=s_data["incorrect"],
                unattempted=s_data["unattempted"],
                score=s_data["score"],
                percentage=s_pct
            ))

        sub_id = "sub_" + uuid.uuid4().hex[:10]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = SubmissionResult(
            id=sub_id,
            test_id=active_test["id"],
            test_title=active_test["title"],
            student_name=submission.student_name.strip() or "Anonymous Student",
            roll_no=submission.roll_no.strip() if submission.roll_no else "N/A",
            total_questions=total_questions,
            attempted_count=attempted_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            unattempted_count=unattempted_count,
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            time_taken_seconds=submission.time_taken_seconds,
            duration_minutes=active_test["duration_minutes"],
            auto_submitted=submission.auto_submitted,
            submitted_at=now_str,
            subject_scores=subject_scores_list,
            question_results=question_results
        )

        # Save individual submission JSON
        sub_file = os.path.join(SUBMISSIONS_DIR, f"{sub_id}.json")
        with open(sub_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        # Update submissions index
        TestManager._add_to_submissions_index(result)

        return result

    @staticmethod
    def _add_to_submissions_index(result: SubmissionResult):
        index = []
        if os.path.exists(SUBMISSIONS_INDEX_FILE):
            try:
                with open(SUBMISSIONS_INDEX_FILE, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                index = []

        summary = {
            "id": result.id,
            "test_id": result.test_id,
            "test_title": result.test_title,
            "student_name": result.student_name,
            "roll_no": result.roll_no,
            "score": result.total_score,
            "max_score": result.max_score,
            "percentage": result.percentage,
            "correct_count": result.correct_count,
            "wrong_count": result.wrong_count,
            "unattempted_count": result.unattempted_count,
            "time_taken_seconds": result.time_taken_seconds,
            "submitted_at": result.submitted_at,
            "auto_submitted": result.auto_submitted
        }
        index.insert(0, summary)

        with open(SUBMISSIONS_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    @staticmethod
    def get_submission(submission_id: str) -> Optional[Dict[str, Any]]:
        file_path = os.path.join(SUBMISSIONS_DIR, f"{submission_id}.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading submission {submission_id}: {e}")
            return None

    @staticmethod
    def get_all_submissions() -> List[Dict[str, Any]]:
        if not os.path.exists(SUBMISSIONS_INDEX_FILE):
            return []
        try:
            with open(SUBMISSIONS_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def get_active_test_submissions() -> List[Dict[str, Any]]:
        """
        Get student submissions strictly for the currently active test.
        Sorted by highest score first (Rank 1 Topper at top).
        """
        active_test = TestManager.get_active_test()
        if not active_test or "id" not in active_test:
            return []

        active_id = active_test["id"]
        all_subs = TestManager.get_all_submissions()
        
        # Filter strictly for active test
        test_subs = [s for s in all_subs if s.get("test_id") == active_id]

        # Sort: Highest score first, then least time taken
        test_subs.sort(
            key=lambda x: (
                -float(x.get("score", 0)),
                float(x.get("time_taken_seconds", 999999))
            )
        )

        # Assign ranks
        for idx, sub in enumerate(test_subs):
            sub["rank"] = idx + 1
            sub["is_topper"] = (idx == 0)

        return test_subs
