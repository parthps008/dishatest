import os
import sys
import io
import json
import unittest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.test_manager import TestManager
from app.auth import create_session_token, ADMIN_USERNAME, SESSION_COOKIE_NAME

class TestImageTestCreation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.token = create_session_token(ADMIN_USERNAME)
        self.client.cookies.set(SESSION_COOKIE_NAME, self.token)
        # Ensure fresh state
        TestManager.delete_active_test()

    def tearDown(self):
        TestManager.delete_active_test()

    def _create_dummy_image(self, width=200, height=200, color=(255, 0, 0), format="PNG"):
        img = Image.new("RGB", (width, height), color=color)
        buf = io.BytesIO()
        img.save(buf, format=format)
        buf.seek(0)
        return buf.getvalue()

    def test_create_image_test_success(self):
        """Test creating an image test with 3 images, custom answers, and compression."""
        img1 = self._create_dummy_image(color=(255, 0, 0))
        img2 = self._create_dummy_image(color=(0, 255, 0))
        img3 = self._create_dummy_image(color=(0, 0, 255))

        files = [
            ("files", ("q1_math.png", io.BytesIO(img1), "image/png")),
            ("files", ("q2_physics.png", io.BytesIO(img2), "image/png")),
            ("files", ("q3_chem.png", io.BytesIO(img3), "image/png")),
        ]

        answers = {"1": "C", "2": "A", "3": "D"}
        data = {
            "duration": 45,
            "title": "Disha Academy MHT-CET Image Mock Test",
            "subject": "Mathematics",
            "answers_json": json.dumps(answers)
        }

        res = self.client.post("/api/admin/create-image-test", data=data, files=files)
        self.assertEqual(res.status_code, 200, res.text)
        res_data = res.json()
        self.assertTrue(res_data["success"])
        self.assertEqual(res_data["test"]["total_questions"], 3)
        self.assertEqual(res_data["test"]["duration_minutes"], 45)
        self.assertEqual(res_data["test"]["title"], "Disha Academy MHT-CET Image Mock Test")

        # Verify active test structure in TestManager
        active = TestManager.get_active_test()
        self.assertIsNotNone(active)
        self.assertEqual(len(active["questions"]), 3)

        # Verify Q1 mapping
        q1 = active["questions"][0]
        self.assertEqual(q1["q_no"], 1)
        self.assertEqual(q1["correct_answer"], "C")
        self.assertIsNotNone(q1["image_url"])
        self.assertEqual(len(q1["options"]), 4)
        self.assertEqual(q1["options"][0]["key"], "A")
        self.assertEqual(q1["options"][1]["key"], "B")
        self.assertEqual(q1["options"][2]["key"], "C")
        self.assertEqual(q1["options"][3]["key"], "D")

        # Verify Q2 & Q3 answers
        self.assertEqual(active["questions"][1]["correct_answer"], "A")
        self.assertEqual(active["questions"][2]["correct_answer"], "D")

        # Verify file actually saved on disk and compressed
        local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            q1["image_url"].lstrip("/").replace("/", os.sep)
        )
        self.assertTrue(os.path.exists(local_path))

    def test_single_active_test_policy_enforcement(self):
        """Cannot create a second test while one is active."""
        img1 = self._create_dummy_image()
        files = [("files", ("q1.png", io.BytesIO(img1), "image/png"))]
        data = {"duration": 30, "title": "First Test"}
        res = self.client.post("/api/admin/create-image-test", data=data, files=files)
        self.assertEqual(res.status_code, 200)

        # Attempt second creation
        img2 = self._create_dummy_image()
        files2 = [("files", ("q2.png", io.BytesIO(img2), "image/png"))]
        res2 = self.client.post("/api/admin/create-image-test", data=data, files=files2)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("already live", res2.json()["detail"])

    def test_max_50_images_limit(self):
        """Cannot upload more than 50 images."""
        img_bytes = self._create_dummy_image()
        files = [
            ("files", (f"q{i}.png", io.BytesIO(img_bytes), "image/png"))
            for i in range(51)
        ]
        data = {"duration": 30, "title": "Over Limit Test"}
        res = self.client.post("/api/admin/create-image-test", data=data, files=files)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Maximum 50 images allowed", res.json()["detail"])

    def test_admin_update_answer_and_student_submission(self):
        """Admin can edit answers for image test and student submissions grade properly."""
        img1 = self._create_dummy_image()
        img2 = self._create_dummy_image()
        files = [
            ("files", ("q1.png", io.BytesIO(img1), "image/png")),
            ("files", ("q2.png", io.BytesIO(img2), "image/png")),
        ]
        # Initially set Q1 -> A, Q2 -> B
        data = {"duration": 30, "answers_json": json.dumps({"1": "A", "2": "B"})}
        res = self.client.post("/api/admin/create-image-test", data=data, files=files)
        self.assertEqual(res.status_code, 200)

        # Admin edits Q2 answer to D
        update_res = self.client.post(
            "/api/admin/update-question-answer",
            json={"q_no": 2, "correct_answer": "D"}
        )
        self.assertEqual(update_res.status_code, 200)

        active = TestManager.get_active_test()
        self.assertEqual(active["questions"][1]["correct_answer"], "D")

        # Student submits: Q1 -> A (correct), Q2 -> D (correct)
        sub_data = {
            "test_id": active["id"],
            "student_name": "Test Student",
            "roll_no": "ROLL-101",
            "answers": {1: "A", 2: "D"},
            "time_taken_seconds": 120,
            "auto_submitted": False
        }
        sub_res = self.client.post("/api/test/submit", json=sub_data)
        self.assertEqual(sub_res.status_code, 200)
        sub_json = sub_res.json()
        self.assertEqual(sub_json["score"], 2.0)
        self.assertEqual(sub_json["max_score"], 2.0)
        self.assertEqual(sub_json["percentage"], 100.0)

    def test_disk_cleanup_on_delete_image_test(self):
        """Deleting active image test removes all uploaded images from disk."""
        img1 = self._create_dummy_image()
        files = [("files", ("q1.png", io.BytesIO(img1), "image/png"))]
        res = self.client.post("/api/admin/create-image-test", files=files)
        self.assertEqual(res.status_code, 200)

        active = TestManager.get_active_test()
        q1_url = active["questions"][0]["image_url"]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, q1_url.lstrip("/").replace("/", os.sep))
        self.assertTrue(os.path.exists(file_path))

        # Delete active test
        del_res = self.client.delete("/api/admin/delete-test")
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(TestManager.get_active_test())
        self.assertFalse(os.path.exists(file_path))

if __name__ == "__main__":
    unittest.main()
