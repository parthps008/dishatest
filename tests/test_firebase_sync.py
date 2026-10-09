import unittest
from unittest.mock import patch, MagicMock
import os
import json
import base64
from fastapi.testclient import TestClient

from app.main import app
from app.firebase_sync import FirebaseSync
from app.auth import create_session_token, ADMIN_USERNAME, SESSION_COOKIE_NAME

class TestFirebaseSync(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        token = create_session_token(ADMIN_USERNAME)
        self.cookies = {SESSION_COOKIE_NAME: token, "disha_admin": "1"}

    def test_firebase_status_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            status = FirebaseSync.get_status()
            self.assertIn("enabled", status)
            self.assertIn("cloud_provider", status)

    def test_embed_and_restore_images(self):
        # Create a dummy image
        test_data = {
            "id": "test_embed",
            "title": "Embedded Test",
            "questions": [
                {
                    "id": 1,
                    "q_no": 1,
                    "text": "Sample Q1",
                    "options": [{"key": "A", "text": "Opt A", "image_url": None}],
                    "image_url": None
                }
            ]
        }
        embedded = FirebaseSync._embed_images_as_base64(test_data)
        self.assertEqual(embedded["id"], "test_embed")
        restored = FirebaseSync._restore_images_from_base64(embedded)
        self.assertEqual(restored["id"], "test_embed")

    def test_firebase_status_endpoint(self):
        resp = self.client.get("/api/admin/firebase-status", cookies=self.cookies)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("enabled", data)

    def test_firebase_config_endpoint(self):
        with patch.object(FirebaseSync, "test_connection", return_value=(True, "Connected!")):
            resp = self.client.post(
                "/api/admin/firebase-config",
                json={"database_url": "https://dummy-test-default-rtdb.firebaseio.com"},
                cookies=self.cookies
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data.get("success"))

            # Clean up config file
            FirebaseSync.set_config("")

if __name__ == "__main__":
    unittest.main()
