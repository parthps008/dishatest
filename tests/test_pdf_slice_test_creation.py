import os
import unittest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app, BASE_DIR, QUESTION_IMAGES_DIR
from app.test_manager import TestManager
from app.auth import create_session_token, ADMIN_USERNAME, SESSION_COOKIE_NAME
from app.pdf_image_slicer import slice_pdf_to_question_images

class TestPdfSliceTestCreation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.active_test_path = os.path.join(BASE_DIR, "data", "active_test.json")
        cls.saved_active_test = None
        if os.path.exists(cls.active_test_path):
            with open(cls.active_test_path, "r", encoding="utf-8") as f:
                cls.saved_active_test = f.read()

    @classmethod
    def tearDownClass(cls):
        if cls.saved_active_test is not None:
            with open(cls.active_test_path, "w", encoding="utf-8") as f:
                f.write(cls.saved_active_test)

    def setUp(self):
        self.client = TestClient(app)
        self.token = create_session_token(ADMIN_USERNAME)
        self.cookies = {SESSION_COOKIE_NAME: self.token}
        # Clear active test before each test
        TestManager.delete_active_test()

    def tearDown(self):
        # Clean up active test after each test
        TestManager.delete_active_test()

    def test_slice_pdf_to_question_images_physics(self):
        """Verify slicing 50-question 2-column physics PDF."""
        pdf_path = os.path.join(BASE_DIR, "sample_tests", "disha_physics_50q.pdf")
        self.assertTrue(os.path.exists(pdf_path))

        test_data = slice_pdf_to_question_images(
            pdf_path=pdf_path,
            output_dir=QUESTION_IMAGES_DIR,
            override_duration=45,
            title_override="Physics 50Q Auto-Sliced Test"
        )

        self.assertEqual(test_data["title"], "Physics 50Q Auto-Sliced Test")
        self.assertEqual(test_data["duration_minutes"], 45)
        self.assertEqual(test_data["total_questions"], 50)
        self.assertEqual(len(test_data["questions"]), 50)
        self.assertEqual(test_data["test_type"], "pdf_slice")

        # Verify sequential mapping Q1..Q50
        for i, q in enumerate(test_data["questions"]):
            expected_no = i + 1
            self.assertEqual(q["q_no"], expected_no)
            self.assertEqual(q["text"], f"Question {expected_no}")
            self.assertEqual(len(q["options"]), 4)
            self.assertEqual([opt["key"] for opt in q["options"]], ["A", "B", "C", "D"])
            self.assertIsNotNone(q["image_url"])
            
            # Verify file exists on disk
            rel_path = q["image_url"].lstrip("/")
            local_path = os.path.join(BASE_DIR, rel_path.replace("/", os.sep))
            self.assertTrue(os.path.exists(local_path), f"Image file not found: {local_path}")
            
            # Verify image is a valid readable JPEG
            with Image.open(local_path) as img:
                self.assertGreater(img.width, 50)
                self.assertGreater(img.height, 20)

    def test_slice_pdf_to_question_images_mock_test_with_answer_key(self):
        """Verify slicing 25-question mock test with auto-detected answer key."""
        pdf_path = os.path.join(BASE_DIR, "sample_tests", "disha_academy_mock_test.pdf")
        self.assertTrue(os.path.exists(pdf_path))

        test_data = slice_pdf_to_question_images(
            pdf_path=pdf_path,
            output_dir=QUESTION_IMAGES_DIR
        )

        self.assertEqual(test_data["total_questions"], 25)
        self.assertEqual(len(test_data["questions"]), 25)

        # Q1 answer in mock test key is B
        q1 = test_data["questions"][0]
        self.assertEqual(q1["q_no"], 1)
        self.assertEqual(q1["correct_answer"], "B")
        self.assertTrue(q1["answer_auto_detected"])

        # Q20 answer in mock test key is A
        q20 = test_data["questions"][19]
        self.assertEqual(q20["q_no"], 20)
        self.assertEqual(q20["correct_answer"], "A")
        self.assertTrue(q20["answer_auto_detected"])

    def test_api_create_pdf_sliced_test_unauthorized(self):
        """Verify endpoint rejects unauthenticated requests."""
        pdf_path = os.path.join(BASE_DIR, "sample_tests", "java_assessment_part2.pdf")
        with open(pdf_path, "rb") as f:
            resp = self.client.post(
                "/api/admin/create-pdf-sliced-test",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"duration": 30}
            )
        self.assertEqual(resp.status_code, 401)

    def test_api_create_pdf_sliced_test_success_and_lifecycle(self):
        """Verify end-to-end API upload, test activation, student submission, and cleanup."""
        pdf_path = os.path.join(BASE_DIR, "sample_tests", "java_assessment_part2.pdf")
        self.assertTrue(os.path.exists(pdf_path))

        with open(pdf_path, "rb") as f:
            resp = self.client.post(
                "/api/admin/create-pdf-sliced-test",
                cookies=self.cookies,
                files={"file": ("java_assessment_part2.pdf", f, "application/pdf")},
                data={
                    "duration": 25,
                    "title": "Java Sliced Test API",
                    "subject": "Java"
                }
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["test"]["total_questions"], 10)
        self.assertEqual(data["test"]["duration_minutes"], 25)

        # Verify active test via student API
        student_test = TestManager.get_active_test_for_student()
        self.assertIsNotNone(student_test)
        self.assertEqual(student_test["total_questions"], 10)
        self.assertEqual(student_test["questions"][0]["image_url"], data["test"]["questions"][0]["image_url"])
        # Student should not see correct_answer
        self.assertNotIn("correct_answer", student_test["questions"][0])

        # Test single active test policy: trying to create another test while active must fail with 400
        with open(pdf_path, "rb") as f:
            resp2 = self.client.post(
                "/api/admin/create-pdf-sliced-test",
                cookies=self.cookies,
                files={"file": ("java_assessment_part2.pdf", f, "application/pdf")},
                data={"duration": 30}
            )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("already live", resp2.json()["detail"])

        # Test student submission against sliced test
        submission_payload = {
            "test_id": student_test["id"],
            "student_name": "Rohan Patil",
            "roll_no": "DISHA-2026-09",
            "answers": {1: "A", 2: "B"},
            "time_taken_seconds": 120,
            "auto_submitted": False
        }
        sub_resp = self.client.post("/api/test/submit", json=submission_payload)
        self.assertEqual(sub_resp.status_code, 200)
        sub_data = sub_resp.json()
        self.assertTrue(sub_data["success"])
        self.assertIn("submission_id", sub_data)
        self.assertIn("score", sub_data)

        # Test admin delete test cleans up images
        del_resp = self.client.delete("/api/admin/delete-test", cookies=self.cookies)
        self.assertEqual(del_resp.status_code, 200)
        self.assertIsNone(TestManager.get_active_test())

if __name__ == "__main__":
    unittest.main()
