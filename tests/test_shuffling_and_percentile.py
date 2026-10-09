import os
import io
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.test_manager import TestManager
from app.firebase_sync import FirebaseSync
from app.auth import create_session_token, ADMIN_USERNAME, SESSION_COOKIE_NAME
from app.percentile_pdf import generate_percentile_merit_list_pdf


class TestShufflingAndPercentile(unittest.TestCase):
    def setUp(self):
        self.fb_patch1 = patch.object(FirebaseSync, "sync_active_test_to_cloud", return_value=True)
        self.fb_patch2 = patch.object(FirebaseSync, "delete_active_test_from_cloud", return_value=True)
        self.fb_patch3 = patch.object(FirebaseSync, "sync_submission_to_cloud", return_value=True)
        self.fb_patch4 = patch.object(FirebaseSync, "fetch_active_test_from_cloud", return_value=None)
        self.fb_patch5 = patch.object(FirebaseSync, "fetch_submissions_from_cloud", return_value={})
        self.fb_patch1.start()
        self.fb_patch2.start()
        self.fb_patch3.start()
        self.fb_patch4.start()
        self.fb_patch5.start()
        TestManager._cloud_checked_on_boot = True

        self.client = TestClient(app)
        self.token = create_session_token(ADMIN_USERNAME)
        self.cookies = {SESSION_COOKIE_NAME: self.token, "disha_admin": "1"}

        # Create a test with 5 distinct questions
        self.test_data = {
            "id": "test_shuff_perc_demo",
            "title": "Disha Shuffling & Percentile Test",
            "duration_minutes": 20,
            "total_questions": 5,
            "questions": [
                {
                    "id": 1,
                    "q_no": 1,
                    "text": "Question 1 Physics",
                    "options": [{"key": "A", "text": "Opt A"}, {"key": "B", "text": "Opt B"}],
                    "correct_answer": "A",
                    "subject": "Physics",
                    "marks": 1
                },
                {
                    "id": 2,
                    "q_no": 2,
                    "text": "Question 2 Chemistry",
                    "options": [{"key": "A", "text": "Opt A"}, {"key": "B", "text": "Opt B"}],
                    "correct_answer": "B",
                    "subject": "Chemistry",
                    "marks": 1
                },
                {
                    "id": 3,
                    "q_no": 3,
                    "text": "Question 3 Maths",
                    "options": [{"key": "A", "text": "Opt A"}, {"key": "B", "text": "Opt B"}],
                    "correct_answer": "A",
                    "subject": "Maths",
                    "marks": 1
                },
                {
                    "id": 4,
                    "q_no": 4,
                    "text": "Question 4 Biology",
                    "options": [{"key": "A", "text": "Opt A"}, {"key": "B", "text": "Opt B"}],
                    "correct_answer": "B",
                    "subject": "Biology",
                    "marks": 1
                },
                {
                    "id": 5,
                    "q_no": 5,
                    "text": "Question 5 Logic",
                    "options": [{"key": "A", "text": "Opt A"}, {"key": "B", "text": "Opt B"}],
                    "correct_answer": "A",
                    "subject": "Logic",
                    "marks": 1
                }
            ]
        }
        TestManager.set_active_test(self.test_data)

    def tearDown(self):
        TestManager.delete_active_test()
        self.fb_patch1.stop()
        self.fb_patch2.stop()
        self.fb_patch3.stop()
        self.fb_patch4.stop()
        self.fb_patch5.stop()
        TestManager._cloud_checked_on_boot = False
        FirebaseSync.fetch_active_test_from_cloud()

    def test_question_shuffling_per_student(self):
        """Questions are shuffled uniquely for different students, but stable for same student session."""
        # Student 1: Parth (Roll 101)
        student1_test = TestManager.get_active_test_for_student(shuffle_seed="seed_parth_101")
        s1_q_order = [q["q_no"] for q in student1_test["questions"]]

        # Student 2: Vikrant (Roll 102)
        student2_test = TestManager.get_active_test_for_student(shuffle_seed="seed_vikrant_102")
        s2_q_order = [q["q_no"] for q in student2_test["questions"]]

        # They should have all 5 questions
        self.assertEqual(len(s1_q_order), 5)
        self.assertEqual(len(s2_q_order), 5)
        self.assertEqual(set(s1_q_order), {1, 2, 3, 4, 5})
        self.assertEqual(set(s2_q_order), {1, 2, 3, 4, 5})

        # Different seeds produce different sequences
        self.assertNotEqual(s1_q_order, s2_q_order)

        # Same seed produces identical sequence (refresh-safe)
        repeat_test = TestManager.get_active_test_for_student(shuffle_seed="seed_parth_101")
        repeat_order = [q["q_no"] for q in repeat_test["questions"]]
        self.assertEqual(s1_q_order, repeat_order)

        # Sequential display numbers are 1..5
        display_nos = [q["display_q_no"] for q in student1_test["questions"]]
        self.assertEqual(display_nos, [1, 2, 3, 4, 5])

    def test_accurate_grading_with_shuffled_answers(self):
        """Answers mapped to original q_no grade accurately regardless of display sequence."""
        # Parth answers Q1=A (correct), Q2=B (correct), Q3=A (correct), Q4=B (correct), Q5=A (correct) -> 5/5
        sub_data = {
            "test_id": "test_shuff_perc_demo",
            "student_name": "Parth",
            "roll_no": "DA-101",
            "answers": {"1": "A", "2": "B", "3": "A", "4": "B", "5": "A"},
            "time_taken_seconds": 300,
            "auto_submitted": False
        }
        res = self.client.post("/api/test/submit", json=sub_data)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["score"], 5.0)
        self.assertEqual(data["percentage"], 100.0)

    def test_percentile_calculation_and_pdf_export(self):
        """Submits 5 candidates with varying scores and verifies NTA/CET percentile calculation and PDF download."""
        # 1. Parth: 5/5
        self.client.post("/api/test/submit", json={
            "test_id": "test_shuff_perc_demo", "student_name": "Parth", "roll_no": "DA-101",
            "answers": {"1": "A", "2": "B", "3": "A", "4": "B", "5": "A"}, "time_taken_seconds": 250
        })
        # 2. Vikrant: 3/5 (Q1, Q2, Q3 correct)
        self.client.post("/api/test/submit", json={
            "test_id": "test_shuff_perc_demo", "student_name": "Vikrant", "roll_no": "DA-102",
            "answers": {"1": "A", "2": "B", "3": "A", "4": "A", "5": "B"}, "time_taken_seconds": 310
        })
        # 3. Sneha: 2/5 (Q1, Q2 correct)
        self.client.post("/api/test/submit", json={
            "test_id": "test_shuff_perc_demo", "student_name": "Sneha", "roll_no": "DA-103",
            "answers": {"1": "A", "2": "B", "3": "B", "4": "A", "5": "B"}, "time_taken_seconds": 360
        })
        # 4. Rahul: 1/5 (Q1 correct)
        self.client.post("/api/test/submit", json={
            "test_id": "test_shuff_perc_demo", "student_name": "Rahul", "roll_no": "DA-104",
            "answers": {"1": "A", "2": "A", "3": "B", "4": "A", "5": "B"}, "time_taken_seconds": 400
        })
        # 5. Amit: 0/5 (all wrong)
        self.client.post("/api/test/submit", json={
            "test_id": "test_shuff_perc_demo", "student_name": "Amit", "roll_no": "DA-105",
            "answers": {"1": "B", "2": "A", "3": "B", "4": "A", "5": "B"}, "time_taken_seconds": 420
        })

        subs = TestManager.get_active_test_submissions()
        self.assertEqual(len(subs), 5)

        # Ranked by score descending
        self.assertEqual(subs[0]["student_name"], "Parth")
        self.assertEqual(subs[0]["rank"], 1)
        self.assertEqual(subs[0]["percentile"], 100.0) # Topper = 100 percentile

        self.assertEqual(subs[1]["student_name"], "Vikrant")
        self.assertEqual(subs[1]["rank"], 2)
        self.assertEqual(subs[1]["percentile"], 80.0) # 4/5 candidates <= 3 score = 80 percentile

        self.assertEqual(subs[2]["student_name"], "Sneha")
        self.assertEqual(subs[2]["percentile"], 60.0) # 3/5 candidates <= 2 score = 60 percentile

        self.assertEqual(subs[3]["student_name"], "Rahul")
        self.assertEqual(subs[3]["percentile"], 40.0)

        self.assertEqual(subs[4]["student_name"], "Amit")
        self.assertEqual(subs[4]["percentile"], 20.0)

        # Download PDF as Percentile
        pdf_res = self.client.get("/api/admin/export-percentile-pdf", cookies=self.cookies)
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers["content-type"], "application/pdf")
        self.assertIn("Disha_Academy_Percentile_Report", pdf_res.headers.get("content-disposition", ""))
        self.assertGreater(len(pdf_res.content), 2000)

        # Verify ReportLab generator directly
        pdf_bytes = generate_percentile_merit_list_pdf(self.test_data, subs)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 2000)


if __name__ == "__main__":
    unittest.main()
