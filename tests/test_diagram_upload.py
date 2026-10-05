import os
import sys
import io
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.test_manager import TestManager
from app.pdf_parser import parse_pdf_test
from app.auth import create_session_token, ADMIN_USERNAME, SESSION_COOKIE_NAME

class TestDiagramUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load test
        pdf_path = os.path.join("sample_tests", "java_assessment_part2.pdf")
        if os.path.exists(pdf_path):
            test_data = parse_pdf_test(pdf_path)
            TestManager.set_active_test(test_data)
        cls.client = TestClient(app)
        cls.token = create_session_token(ADMIN_USERNAME)

    def test_direct_manager_image_attachment(self):
        # Attach image
        success = TestManager.attach_question_image(1, "/static/uploads/questions/test_diagram.png")
        self.assertTrue(success)

        # Check admin view
        active = TestManager.get_active_test()
        q1 = next(q for q in active["questions"] if q["q_no"] == 1)
        self.assertEqual(q1["image_url"], "/static/uploads/questions/test_diagram.png")

        # Check student view
        student_test = TestManager.get_active_test_for_student()
        sq1 = next(q for q in student_test["questions"] if q["q_no"] == 1)
        self.assertEqual(sq1["image_url"], "/static/uploads/questions/test_diagram.png")

        # Remove image
        rem_success = TestManager.remove_question_image(1)
        self.assertTrue(rem_success)

        active = TestManager.get_active_test()
        q1 = next(q for q in active["questions"] if q["q_no"] == 1)
        self.assertIsNone(q1["image_url"])

    def test_api_upload_and_remove_image(self):
        self.client.cookies.set(SESSION_COOKIE_NAME, self.token)

        # Create dummy image in memory
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"file": ("diagram_circuit.png", io.BytesIO(dummy_png), "image/png")}
        data = {"q_no": 2}

        # Upload
        res = self.client.post("/api/admin/upload-question-image", data=data, files=files)
        self.assertEqual(res.status_code, 200, res.text)
        res_data = res.json()
        self.assertTrue(res_data["success"])
        self.assertIn("/static/uploads/questions/", res_data["image_url"])

        # Verify Q2 has image in active test
        active = TestManager.get_active_test()
        q2 = next(q for q in active["questions"] if q["q_no"] == 2)
        self.assertEqual(q2["image_url"], res_data["image_url"])

        # Remove
        rem_res = self.client.post("/api/admin/remove-question-image", json={"q_no": 2})
        self.assertEqual(rem_res.status_code, 200)
        self.assertTrue(rem_res.json()["success"])

        active = TestManager.get_active_test()
        q2 = next(q for q in active["questions"] if q["q_no"] == 2)
        self.assertIsNone(q2["image_url"])

if __name__ == "__main__":
    unittest.main()
