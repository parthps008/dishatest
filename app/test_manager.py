import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models import (
    TestData, Question, TestSubmissionRequest,
    SubmissionResult, QuestionResult, SubjectScore
)
from app.firebase_sync import FirebaseSync

import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ACTIVE_TEST_FILE = os.path.join(DATA_DIR, "active_test.json")
SUBMISSIONS_DIR = os.path.join(DATA_DIR, "submissions")
SUBMISSIONS_INDEX_FILE = os.path.join(DATA_DIR, "submissions_index.json")
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")
QUESTION_IMAGES_DIR = os.path.join(UPLOADS_DIR, "questions")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
os.makedirs(QUESTION_IMAGES_DIR, exist_ok=True)

class TestManager:
    _cloud_checked_on_boot = False

    @staticmethod
    def get_active_test() -> Optional[Dict[str, Any]]:
        """Get the currently active test with all details (including answers for admin)."""
        # On first request after boot/wake, ensure cloud state is synchronized
        if FirebaseSync.is_enabled() and not TestManager._cloud_checked_on_boot:
            TestManager._cloud_checked_on_boot = True
            cloud_test = FirebaseSync.fetch_active_test_from_cloud()
            if cloud_test:
                return cloud_test
            elif not os.path.exists(ACTIVE_TEST_FILE):
                return None

        if not os.path.exists(ACTIVE_TEST_FILE):
            # If server restarted (e.g. Render after 15m), restore from Firebase cloud
            cloud_test = FirebaseSync.fetch_active_test_from_cloud()
            if cloud_test:
                return cloud_test
            return None
        try:
            with open(ACTIVE_TEST_FILE, "r", encoding="utf-8") as f:
                test = json.load(f)

            # If Render container restarted and ephemeral question images were wiped, rehydrate from Firebase
            if test and isinstance(test, dict) and "questions" in test:
                needs_image_restore = False
                for q in test.get("questions", []):
                    img_url = q.get("image_url")
                    if img_url and isinstance(img_url, str) and img_url.startswith("/static/uploads/"):
                        rel_path = img_url.lstrip("/").replace("/", os.sep)
                        full_img = os.path.join(BASE_DIR, rel_path)
                        if not os.path.exists(full_img):
                            needs_image_restore = True
                            break
                if needs_image_restore:
                    cloud_test = FirebaseSync.fetch_active_test_from_cloud()
                    if cloud_test:
                        return cloud_test

            return test
        except Exception as e:
            print(f"Error loading active test: {e}")
            cloud_test = FirebaseSync.fetch_active_test_from_cloud()
            if cloud_test:
                return cloud_test
            return None

    @staticmethod
    def get_active_test_for_student(shuffle_seed: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the active test sanitized for students (no correct answers or explanations),
        with questions shuffled uniquely per candidate session.
        """
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

        # Shuffle questions uniquely per candidate session if seed provided
        if shuffle_seed and len(sanitized_questions) > 1:
            rng = random.Random(str(shuffle_seed))
            rng.shuffle(sanitized_questions)

        # Assign display question numbers sequentially 1..N
        for idx, q in enumerate(sanitized_questions):
            q["display_q_no"] = idx + 1

        return {
            "id": test["id"],
            "title": test["title"],
            "subjects": test.get("subjects", []),
            "duration_minutes": test["duration_minutes"],
            "total_questions": len(sanitized_questions),
            "questions": sanitized_questions,
            "created_at": test["created_at"],
            "pdf_filename": test.get("pdf_filename", ""),
            "test_type": test.get("test_type", "pdf")
        }

    @staticmethod
    def _save_active_test_and_sync(active_test: Dict[str, Any]):
        with open(ACTIVE_TEST_FILE, "w", encoding="utf-8") as f:
            json.dump(active_test, f, indent=2, ensure_ascii=False)
        try:
            FirebaseSync.sync_active_test_to_cloud(active_test)
        except Exception as e:
            print(f"[TestManager] Sync to Firebase error: {e}")

    @staticmethod
    def set_active_test(test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save and activate a new test. Overwrites if an active test exists."""
        if "id" not in test_data:
            test_data["id"] = "test_" + uuid.uuid4().hex[:8]
        if "created_at" not in test_data:
            test_data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        TestManager._save_active_test_and_sync(test_data)
        return test_data

    @staticmethod
    def delete_active_test() -> bool:
        """
        Delete the currently active test, its uploaded PDF, all question diagrams,
        and all associated student logs/submissions from local disk AND Firebase cloud.
        Enforces test-wise logs and 100% disk cleanup when a test is deleted.
        """
        active_test = TestManager.get_active_test()
        test_id = active_test.get("id") if active_test else None

        # Delete from Firebase cloud database synchronously to prevent race conditions
        try:
            FirebaseSync.delete_active_test_from_cloud()
        except Exception as e:
            print(f"[TestManager] Error deleting from Firebase: {e}")

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

        # 2. Delete all uploaded diagrams and images for this test (free up disk space)
        if active_test and "questions" in active_test:
            for q in active_test["questions"]:
                # Main question image
                if q.get("image_url"):
                    clean_path = q["image_url"].lstrip("/")
                    local_file = os.path.join(BASE_DIR, clean_path.replace("/", os.sep))
                    if os.path.exists(local_file):
                        try:
                            os.remove(local_file)
                        except Exception:
                            pass
                # Option images
                for opt in q.get("options", []):
                    if opt.get("image_url"):
                        clean_path = opt["image_url"].lstrip("/")
                        local_file = os.path.join(BASE_DIR, clean_path.replace("/", os.sep))
                        if os.path.exists(local_file):
                            try:
                                os.remove(local_file)
                            except Exception:
                                pass

        # Clean any remaining diagram files in QUESTION_IMAGES_DIR to reclaim 100% space
        if os.path.exists(QUESTION_IMAGES_DIR):
            for fname in os.listdir(QUESTION_IMAGES_DIR):
                if fname == ".gitkeep":
                    continue
                fpath = os.path.join(QUESTION_IMAGES_DIR, fname)
                if os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass

        # 3. Delete uploaded source PDF if present in static/uploads
        if active_test and active_test.get("pdf_filename"):
            pdf_path = os.path.join(UPLOADS_DIR, active_test["pdf_filename"])
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass

        # 4. Delete the active test file
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
            TestManager._save_active_test_and_sync(active_test)
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
            TestManager._save_active_test_and_sync(active_test)
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
            TestManager._save_active_test_and_sync(active_test)
            return True
        return False

    @staticmethod
    def update_question_full(
        q_no: int,
        text: str,
        options: List[Dict[str, Any]],
        correct_answer: str,
        subject: Optional[str] = "General",
        marks: Optional[int] = 1
    ) -> Optional[Dict[str, Any]]:
        """Update statement, options, correct answer, subject, marks for a question."""
        active_test = TestManager.get_active_test()
        if not active_test or "questions" not in active_test:
            return None

        correct_answer = correct_answer.strip().upper()
        if correct_answer not in ["A", "B", "C", "D"]:
            return None

        target_q = None
        for q in active_test["questions"]:
            if q.get("q_no") == q_no:
                target_q = q
                break

        if not target_q:
            return None

        target_q["text"] = text.strip()
        target_q["correct_answer"] = correct_answer
        target_q["answer_auto_detected"] = False
        if subject:
            target_q["subject"] = subject.strip()
        if marks is not None:
            try:
                target_q["marks"] = max(1, int(marks))
            except (ValueError, TypeError):
                target_q["marks"] = 1

        # Format and preserve/update options
        existing_opts_by_key = {opt.get("key", "").upper(): opt for opt in target_q.get("options", [])}
        updated_options = []
        for i, key in enumerate(["A", "B", "C", "D"]):
            opt_data = None
            for o in options:
                if str(o.get("key", "")).strip().upper() == key:
                    opt_data = o
                    break
            if not opt_data and i < len(options):
                opt_data = options[i]

            opt_text = opt_data.get("text", "") if opt_data else ""
            opt_img = opt_data.get("image_url") if opt_data else None
            # If not specified in opt_data, preserve existing image if any
            if opt_img is None and key in existing_opts_by_key:
                opt_img = existing_opts_by_key[key].get("image_url")

            updated_options.append({
                "key": key,
                "text": opt_text.strip(),
                "image_url": opt_img
            })

        target_q["options"] = updated_options

        # Update test subjects list
        unique_subjects = list(dict.fromkeys(
            q.get("subject", "General").strip() 
            for q in active_test["questions"] 
            if q.get("subject")
        ))
        active_test["subjects"] = unique_subjects or ["General"]

        TestManager._save_active_test_and_sync(active_test)

        return target_q

    @staticmethod
    def delete_question(q_no: int) -> bool:
        """
        Delete a question from the active test.
        Re-indexes all remaining questions sequentially (1..N) and updates total_questions.
        """
        active_test = TestManager.get_active_test()
        if not active_test or "questions" not in active_test:
            return False

        questions = active_test["questions"]
        idx_to_remove = None
        for i, q in enumerate(questions):
            if q.get("q_no") == q_no:
                idx_to_remove = i
                break

        if idx_to_remove is None:
            return False

        # Remove image files from disk if any
        q_to_remove = questions.pop(idx_to_remove)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Main question image
        if q_to_remove.get("image_url"):
            clean_path = q_to_remove["image_url"].lstrip("/")
            local_file = os.path.join(base_dir, clean_path.replace("/", os.sep))
            if os.path.exists(local_file):
                try:
                    os.remove(local_file)
                except Exception:
                    pass

        # Options images
        for opt in q_to_remove.get("options", []):
            if opt.get("image_url"):
                clean_path = opt["image_url"].lstrip("/")
                local_file = os.path.join(base_dir, clean_path.replace("/", os.sep))
                if os.path.exists(local_file):
                    try:
                        os.remove(local_file)
                    except Exception:
                        pass

        # Re-index remaining questions sequentially (1..N)
        for new_idx, q in enumerate(questions, start=1):
            q["q_no"] = new_idx
            q["id"] = new_idx

        active_test["total_questions"] = len(questions)

        # Update subjects list
        unique_subjects = list(dict.fromkeys(
            q.get("subject", "General").strip() 
            for q in questions 
            if q.get("subject")
        ))
        active_test["subjects"] = unique_subjects or ["General"]

        TestManager._save_active_test_and_sync(active_test)

        return True

    @staticmethod
    def add_question(
        text: str,
        options: List[Dict[str, Any]],
        correct_answer: str,
        subject: Optional[str] = "General",
        marks: Optional[int] = 1,
        image_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Add a new question to the active test at the end (q_no = N + 1)."""
        active_test = TestManager.get_active_test()
        if not active_test:
            return None

        if "questions" not in active_test:
            active_test["questions"] = []

        questions = active_test["questions"]
        new_q_no = len(questions) + 1

        correct_answer = correct_answer.strip().upper()
        if correct_answer not in ["A", "B", "C", "D"]:
            correct_answer = "A"

        norm_options = []
        for i, key in enumerate(["A", "B", "C", "D"]):
            opt_data = None
            for o in options:
                if str(o.get("key", "")).strip().upper() == key:
                    opt_data = o
                    break
            if not opt_data and i < len(options):
                opt_data = options[i]

            opt_text = opt_data.get("text", "") if opt_data else ""
            opt_img = opt_data.get("image_url") if opt_data else None
            norm_options.append({
                "key": key,
                "text": opt_text.strip(),
                "image_url": opt_img
            })

        new_question = {
            "id": new_q_no,
            "q_no": new_q_no,
            "text": text.strip(),
            "options": norm_options,
            "correct_answer": correct_answer,
            "answer_auto_detected": False,
            "image_url": image_url,
            "subject": subject.strip() if subject else "General",
            "marks": max(1, int(marks)) if marks else 1,
            "negative_marks": 0.0,
            "explanation": None
        }

        questions.append(new_question)
        active_test["total_questions"] = len(questions)

        unique_subjects = list(dict.fromkeys(
            q.get("subject", "General").strip() 
            for q in questions 
            if q.get("subject")
        ))
        active_test["subjects"] = unique_subjects or ["General"]

        TestManager._save_active_test_and_sync(active_test)

        return new_question

    @staticmethod
    def attach_option_image(q_no: int, opt_key: str, image_url: str) -> bool:
        """Attach an image/diagram to a specific option (A, B, C, D) of a question."""
        active_test = TestManager.get_active_test()
        if not active_test or "questions" not in active_test:
            return False

        opt_key = opt_key.strip().upper()
        found = False
        for q in active_test["questions"]:
            if q.get("q_no") == q_no:
                for opt in q.get("options", []):
                    if opt.get("key", "").upper() == opt_key:
                        opt["image_url"] = image_url
                        found = True
                        break
                break

        if found:
            TestManager._save_active_test_and_sync(active_test)
            return True
        return False

    @staticmethod
    def remove_option_image(q_no: int, opt_key: str) -> bool:
        """Remove attached image/diagram from a specific option of a question."""
        active_test = TestManager.get_active_test()
        if not active_test or "questions" not in active_test:
            return False

        opt_key = opt_key.strip().upper()
        found = False
        for q in active_test["questions"]:
            if q.get("q_no") == q_no:
                for opt in q.get("options", []):
                    if opt.get("key", "").upper() == opt_key:
                        old_url = opt.get("image_url")
                        if old_url:
                            clean_path = old_url.lstrip("/")
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            local_file = os.path.join(base_dir, clean_path.replace("/", os.sep))
                            if os.path.exists(local_file):
                                try:
                                    os.remove(local_file)
                                except Exception:
                                    pass
                        opt["image_url"] = None
                        found = True
                        break
                break

        if found:
            TestManager._save_active_test_and_sync(active_test)
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

        # Synchronize submission & index to Firebase cloud
        FirebaseSync.sync_submission_to_cloud_async(result)

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
        sub_data = None
        if not os.path.exists(file_path):
            sub_data = FirebaseSync.fetch_submission_detail_from_cloud(submission_id)
        else:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    sub_data = json.load(f)
            except Exception as e:
                print(f"Error loading submission {submission_id}: {e}")
                sub_data = FirebaseSync.fetch_submission_detail_from_cloud(submission_id)

        if not sub_data:
            return None

        # Compute rank and percentile for this submission relative to all candidates of the test
        test_id = sub_data.get("test_id")
        all_subs = [s for s in TestManager.get_all_submissions() if s.get("test_id") == test_id]
        total_candidates = len(all_subs)
        if total_candidates > 0:
            s_score = float(sub_data.get("total_score", 0))
            count_less_equal = sum(1 for s in all_subs if float(s.get("score", 0)) <= s_score)
            percentile_val = round((count_less_equal / total_candidates) * 100, 2)
            sub_data["percentile"] = percentile_val
            sub_data["percentile_str"] = f"{percentile_val:.2f}%"

            # Rank
            all_subs.sort(key=lambda x: (-float(x.get("score", 0)), float(x.get("time_taken_seconds", 999999))))
            for idx, s in enumerate(all_subs):
                if s.get("id") == submission_id:
                    sub_data["rank"] = idx + 1
                    break
            sub_data["total_candidates"] = total_candidates
        else:
            sub_data["percentile"] = 100.0
            sub_data["percentile_str"] = "100.00%"
            sub_data["rank"] = 1
            sub_data["total_candidates"] = 1

        return sub_data

    @staticmethod
    def get_all_submissions() -> List[Dict[str, Any]]:
        if not os.path.exists(SUBMISSIONS_INDEX_FILE):
            cloud_subs = FirebaseSync.fetch_submissions_from_cloud()
            if cloud_subs:
                return cloud_subs
            return []
        try:
            with open(SUBMISSIONS_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            cloud_subs = FirebaseSync.fetch_submissions_from_cloud()
            if cloud_subs:
                return cloud_subs
            return []

    @staticmethod
    def get_active_test_submissions() -> List[Dict[str, Any]]:
        """
        Get student submissions strictly for the currently active test.
        Sorted by highest score first (Rank 1 Topper at top).
        Calculates official NTA / JEE / CET Percentile score for all candidates.
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

        total_candidates = len(test_subs)
        for idx, sub in enumerate(test_subs):
            sub["rank"] = idx + 1
            sub["is_topper"] = (idx == 0)

            # NTA / JEE / CET Percentile Formula:
            # Percentile = (Candidates with raw score <= candidate's score / Total Candidates) * 100
            s_score = float(sub.get("score", 0))
            count_less_equal = sum(1 for other in test_subs if float(other.get("score", 0)) <= s_score)
            percentile_val = round((count_less_equal / total_candidates) * 100, 2) if total_candidates > 0 else 100.0
            sub["percentile"] = percentile_val
            sub["percentile_str"] = f"{percentile_val:.2f}%"

        return test_subs
