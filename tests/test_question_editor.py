import os
import sys
import io
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.test_manager import TestManager
from app.auth import create_session_token, ADMIN_USERNAME, SESSION_COOKIE_NAME

class TestQuestionEditor(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.token = create_session_token(ADMIN_USERNAME)

        # Initialize a known test state for testing
        test_fixture = {
            "id": "test_editor_fixture",
            "title": "Question Editor Test Exam",
            "subjects": ["Physics", "Chemistry"],
            "duration_minutes": 30,
            "total_questions": 3,
            "questions": [
                {
                    "id": 1,
                    "q_no": 1,
                    "text": "Original Question 1 statement?",
                    "options": [
                        {"key": "A", "text": "Option A1"},
                        {"key": "B", "text": "Option B1"},
                        {"key": "C", "text": "Option C1"},
                        {"key": "D", "text": "Option D1"}
                    ],
                    "correct_answer": "A",
                    "answer_auto_detected": True,
                    "image_url": None,
                    "subject": "Physics",
                    "marks": 1
                },
                {
                    "id": 2,
                    "q_no": 2,
                    "text": "Original Question 2 statement?",
                    "options": [
                        {"key": "A", "text": "Option A2"},
                        {"key": "B", "text": "Option B2"},
                        {"key": "C", "text": "Option C2"},
                        {"key": "D", "text": "Option D2"}
                    ],
                    "correct_answer": "B",
                    "answer_auto_detected": True,
                    "image_url": None,
                    "subject": "Physics",
                    "marks": 1
                },
                {
                    "id": 3,
                    "q_no": 3,
                    "text": "Original Question 3 statement?",
                    "options": [
                        {"key": "A", "text": "Option A3"},
                        {"key": "B", "text": "Option B3"},
                        {"key": "C", "text": "Option C3"},
                        {"key": "D", "text": "Option D3"}
                    ],
                    "correct_answer": "C",
                    "answer_auto_detected": True,
                    "image_url": None,
                    "subject": "Chemistry",
                    "marks": 1
                }
            ]
        }
        TestManager.set_active_test(test_fixture)

    def test_update_question_full_api(self):
        self.client.cookies.set(SESSION_COOKIE_NAME, self.token)

        payload = {
            "q_no": 1,
            "text": "Updated statement for Question 1: What is Newton's second law?",
            "subject": "Physics",
            "correct_answer": "C",
            "marks": 2,
            "options": [
                {"key": "A", "text": "F = m/a"},
                {"key": "B", "text": "F = v/t"},
                {"key": "C", "text": "F = m*a"},
                {"key": "D", "text": "F = m*v^2"}
            ]
        }

        res = self.client.post("/api/admin/update-question-full", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["question"]["correct_answer"], "C")
        self.assertEqual(data["question"]["marks"], 2)
        self.assertFalse(data["question"]["answer_auto_detected"])

        # Check that changes are reflected live in student test
        student_test = TestManager.get_active_test_for_student()
        q1 = next(q for q in student_test["questions"] if q["q_no"] == 1)
        self.assertEqual(q1["text"], "Updated statement for Question 1: What is Newton's second law?")
        self.assertEqual(q1["options"][2]["text"], "F = m*a")
        # Ensure student test does not expose correct_answer
        self.assertNotIn("correct_answer", q1)

    def test_add_new_question_api(self):
        self.client.cookies.set(SESSION_COOKIE_NAME, self.token)

        initial_count = TestManager.get_active_test()["total_questions"]
        payload = {
            "text": "New Question: What is Avogadro's constant?",
            "subject": "Chemistry",
            "correct_answer": "B",
            "marks": 1,
            "options": [
                {"key": "A", "text": "3.14 x 10^23"},
                {"key": "B", "text": "6.022 x 10^23"},
                {"key": "C", "text": "9.8 x 10^23"},
                {"key": "D", "text": "1.6 x 10^-19"}
            ]
        }

        res = self.client.post("/api/admin/add-question", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total_questions"], initial_count + 1)
        self.assertEqual(data["question"]["q_no"], initial_count + 1)

        # Check live student view has the new question
        student_test = TestManager.get_active_test_for_student()
        self.assertEqual(len(student_test["questions"]), initial_count + 1)

    def test_option_image_upload_and_removal(self):
        self.client.cookies.set(SESSION_COOKIE_NAME, self.token)

        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"file": ("benzene_ring.png", io.BytesIO(dummy_png), "image/png")}
        data = {"q_no": 2, "opt_key": "B"}

        # Upload option image
        res = self.client.post("/api/admin/upload-option-image", data=data, files=files)
        self.assertEqual(res.status_code, 200, res.text)
        res_data = res.json()
        self.assertTrue(res_data["success"])
        self.assertIn("/static/uploads/questions/", res_data["image_url"])

        # Check active test option has image
        active = TestManager.get_active_test()
        q2 = next(q for q in active["questions"] if q["q_no"] == 2)
        opt_b = next(o for o in q2["options"] if o["key"] == "B")
        self.assertEqual(opt_b["image_url"], res_data["image_url"])

        # Remove option image
        rem_res = self.client.post("/api/admin/remove-option-image", json={"q_no": 2, "opt_key": "B"})
        self.assertEqual(rem_res.status_code, 200, rem_res.text)
        
        # Verify removed
        active2 = TestManager.get_active_test()
        q2_updated = next(q for q in active2["questions"] if q["q_no"] == 2)
        opt_b_updated = next(o for o in q2_updated["options"] if o["key"] == "B")
        self.assertIsNone(opt_b_updated["image_url"])

    def test_delete_question_and_reindexing(self):
        self.client.cookies.set(SESSION_COOKIE_NAME, self.token)

        active = TestManager.get_active_test()
        count_before = active["total_questions"]

        # Delete question 2
        res = self.client.post("/api/admin/delete-question", json={"q_no": 2})
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total_questions"], count_before - 1)

        # Verify that remaining questions are sequentially re-indexed 1..N
        active_after = TestManager.get_active_test()
        questions = active_after["questions"]
        self.assertEqual(len(questions), count_before - 1)
        for expected_q_no, q in enumerate(questions, start=1):
            self.assertEqual(q["q_no"], expected_q_no)
            self.assertEqual(q["id"], expected_q_no)

    def test_delete_active_test_disk_cleanup(self):
        from app.test_manager import QUESTION_IMAGES_DIR
        self.client.cookies.set(SESSION_COOKIE_NAME, self.token)

        # Upload a dummy diagram first
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"file": ("test_diagram_cleanup.png", io.BytesIO(dummy_png), "image/png")}
        res = self.client.post("/api/admin/upload-question-image", data={"q_no": 1}, files=files)
        self.assertEqual(res.status_code, 200)

        # Confirm file exists in QUESTION_IMAGES_DIR
        files_before = os.listdir(QUESTION_IMAGES_DIR)
        self.assertTrue(len(files_before) > 0)

        # Delete active test
        del_res = self.client.delete("/api/admin/delete-test")
        self.assertEqual(del_res.status_code, 200)

        # Confirm all files in QUESTION_IMAGES_DIR were cleaned up
        files_after = [f for f in os.listdir(QUESTION_IMAGES_DIR) if f != ".gitkeep"]
        self.assertEqual(len(files_after), 0, f"Expected empty directory, but found: {files_after}")

if __name__ == "__main__":
    unittest.main()

