import os
import sys
import unittest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app, BASE_DIR, QUESTION_IMAGES_DIR
from app.test_manager import TestManager
from app.auth import create_session_token, ADMIN_USERNAME, SESSION_COOKIE_NAME
from app.photo_paper_slicer import slice_paper_photos_to_questions

class TestPhotoPaperTestCreation(unittest.TestCase):
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
        TestManager.delete_active_test()

    def tearDown(self):
        TestManager.delete_active_test()

    def test_slice_paper_photos_to_questions_kendriya_sample(self):
        """Verify AI Vision slicing of real user paper test photo (8 MCQs with diagram)."""
        photo_path = os.path.join(BASE_DIR, "sample_tests", "kendriya_math_8q.jpg")
        self.assertTrue(os.path.exists(photo_path), "Sample paper photo must exist")

        test_data = slice_paper_photos_to_questions(
            image_paths=[photo_path],
            output_dir=QUESTION_IMAGES_DIR,
            override_duration=35,
            title_override="Kendriya Math Paper Test",
            subject_override="Mathematics"
        )

        self.assertEqual(test_data["title"], "Kendriya Math Paper Test")
        self.assertEqual(test_data["duration_minutes"], 35)
        self.assertEqual(test_data["subjects"], ["Mathematics"])
        self.assertEqual(test_data["test_type"], "photo_paper")
        self.assertEqual(test_data["total_questions"], 8)
        self.assertEqual(len(test_data["questions"]), 8)

        # Verify each question from Q1 to Q8
        for i, q in enumerate(test_data["questions"]):
            expected_no = i + 1
            self.assertEqual(q["q_no"], expected_no)
            self.assertEqual(q["text"], f"Question {expected_no}")
            self.assertEqual(q["subject"], "Mathematics")
            self.assertEqual(len(q["options"]), 4)
            self.assertEqual([opt["key"] for opt in q["options"]], ["A", "B", "C", "D"])
            self.assertIsNotNone(q["image_url"])

            # Verify image file exists and is valid readable JPEG
            rel_path = q["image_url"].lstrip("/")
            local_path = os.path.join(BASE_DIR, rel_path.replace("/", os.sep))
            self.assertTrue(os.path.exists(local_path), f"Cropped image not found on disk: {local_path}")

            with Image.open(local_path) as img:
                self.assertGreater(img.width, 50)
                self.assertGreater(img.height, 20)

    def test_api_create_photo_test_success(self):
        """Verify admin endpoint /api/admin/create-photo-test creates and activates test."""
        photo_path = os.path.join(BASE_DIR, "sample_tests", "kendriya_math_8q.jpg")
        self.assertTrue(os.path.exists(photo_path))

        with open(photo_path, "rb") as f:
            files = [("files", ("kendriya_math_8q.jpg", f.read(), "image/jpeg"))]

        res = self.client.post(
            "/api/admin/create-photo-test",
            data={
                "duration": 40,
                "title": "Kendriya Math Assessment",
                "subject": "Mathematics"
            },
            files=files,
            cookies=self.cookies
        )

        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["test"]["total_questions"], 8)
        self.assertEqual(data["test"]["test_type"], "photo_paper")

        # Verify active test via TestManager
        active = TestManager.get_active_test()
        self.assertIsNotNone(active)
        self.assertEqual(active["title"], "Kendriya Math Assessment")
        self.assertEqual(active["total_questions"], 8)

        # Verify student endpoint can retrieve sanitized test
        student_res = self.client.get("/api/test/current")
        self.assertEqual(student_res.status_code, 200)
        student_test = student_res.json()
        self.assertEqual(student_test["total_questions"], 8)
        self.assertNotIn("correct_answer", student_test["questions"][0])
        self.assertEqual(student_test["questions"][0]["options"][0]["key"], "A")
        self.assertIsNotNone(student_test["questions"][0]["image_url"])

    def test_api_create_photo_test_multi_page_chaining(self):
        """Verify multiple paper photos (e.g. Page 1 + Page 2) sequentially stitch questions."""
        photo_path = os.path.join(BASE_DIR, "sample_tests", "kendriya_math_8q.jpg")
        self.assertTrue(os.path.exists(photo_path))

        with open(photo_path, "rb") as f:
            p1_bytes = f.read()

        files = [
            ("files", ("page1.jpg", p1_bytes, "image/jpeg")),
            ("files", ("page2.jpg", p1_bytes, "image/jpeg"))
        ]

        res = self.client.post(
            "/api/admin/create-photo-test",
            data={
                "duration": 60,
                "title": "Two-Page Paper Exam",
                "subject": "Mathematics"
            },
            files=files,
            cookies=self.cookies
        )

        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        # 8 from Page 1 + 8 from Page 2 = 16 questions sequentially mapped
        self.assertEqual(data["test"]["total_questions"], 16)
        questions = data["test"]["questions"]
        self.assertEqual(len(questions), 16)
        for i in range(16):
            self.assertEqual(questions[i]["q_no"], i + 1)
            self.assertEqual(questions[i]["text"], f"Question {i + 1}")

    def test_api_create_photo_test_unauthorized(self):
        """Verify endpoint rejects unauthenticated requests with 401."""
        photo_path = os.path.join(BASE_DIR, "sample_tests", "kendriya_math_8q.jpg")
        with open(photo_path, "rb") as f:
            files = [("files", ("photo.jpg", f.read(), "image/jpeg"))]

        res = self.client.post(
            "/api/admin/create-photo-test",
            data={"duration": 30},
            files=files
        )
        self.assertEqual(res.status_code, 401)

    def test_api_create_photo_test_single_active_test_limit(self):
        """Verify single active test policy prevents creating a photo test while another test is active."""
        # Create initial active test
        photo_path = os.path.join(BASE_DIR, "sample_tests", "kendriya_math_8q.jpg")
        with open(photo_path, "rb") as f:
            files = [("files", ("photo.jpg", f.read(), "image/jpeg"))]

        res1 = self.client.post(
            "/api/admin/create-photo-test",
            data={"duration": 30},
            files=files,
            cookies=self.cookies
        )
        self.assertEqual(res1.status_code, 200)

        # Attempt to create another test without deleting the first one
        with open(photo_path, "rb") as f:
            files2 = [("files", ("photo2.jpg", f.read(), "image/jpeg"))]

        res2 = self.client.post(
            "/api/admin/create-photo-test",
            data={"duration": 30},
            files=files2,
            cookies=self.cookies
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("An active test is already live", res2.json()["detail"])

if __name__ == "__main__":
    unittest.main()
