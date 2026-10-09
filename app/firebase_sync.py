import os
import json
import base64
import threading
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
CONFIG_FILE = os.path.join(DATA_DIR, "firebase_config.json")
ACTIVE_TEST_FILE = os.path.join(DATA_DIR, "active_test.json")
SUBMISSIONS_DIR = os.path.join(DATA_DIR, "submissions")
SUBMISSIONS_INDEX_FILE = os.path.join(DATA_DIR, "submissions_index.json")
QUESTION_IMAGES_DIR = os.path.join(STATIC_DIR, "uploads", "questions")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
os.makedirs(QUESTION_IMAGES_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)


DEFAULT_DATABASE_URL = "https://disha-academy-test-default-rtdb.firebaseio.com"

class FirebaseSync:
    """
    Handles automatic 24/7 cloud persistence using Google Firebase Realtime Database.
    Prevents tests, question screenshots, and student submissions from being wiped
    when Render Free Tier spins down or restarts after 15 minutes of inactivity.
    100% Free Forever (Firebase Spark Plan).
    """

    @staticmethod
    def get_database_url() -> Optional[str]:
        # 1. Environment variable (set in Render Dashboard -> Environment)
        env_url = os.environ.get("FIREBASE_DATABASE_URL", "").strip()
        if env_url:
            return env_url.rstrip("/")

        # 2. Local config file (set via Admin UI)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    db_url = cfg.get("database_url", "").strip()
                    if db_url:
                        return db_url.rstrip("/")
            except Exception:
                pass

        # 3. Default configured Firebase Realtime Database
        return DEFAULT_DATABASE_URL

    @staticmethod
    def get_database_secret() -> Optional[str]:
        env_secret = os.environ.get("FIREBASE_SECRET", "").strip()
        if env_secret:
            return env_secret

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    secret = cfg.get("secret", "").strip()
                    if secret:
                        return secret
            except Exception:
                pass
        return None

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(cls.get_database_url())

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        url = cls.get_database_url()
        secret = cls.get_database_secret()
        return {
            "enabled": bool(url),
            "database_url": url,
            "has_secret": bool(secret),
            "cloud_provider": "Google Firebase Realtime Database (Free Spark Plan)"
        }

    @classmethod
    def set_config(cls, database_url: str, secret: Optional[str] = None) -> bool:
        clean_url = database_url.strip().rstrip("/")
        if not clean_url:
            if os.path.exists(CONFIG_FILE):
                try:
                    os.remove(CONFIG_FILE)
                except Exception:
                    pass
            return True

        cfg = {"database_url": clean_url, "secret": (secret or "").strip()}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            return True
        except Exception as e:
            print(f"[FirebaseSync] Error saving config: {e}")
            return False

    @classmethod
    def _build_url(cls, path: str) -> Optional[str]:
        base = cls.get_database_url()
        if not base:
            return None
        clean_path = path.lstrip("/")
        full_url = f"{base}/{clean_path}.json"
        secret = cls.get_database_secret()
        if secret:
            full_url += f"?auth={secret}"
        return full_url

    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        if not cls.is_enabled():
            return False, "FIREBASE_DATABASE_URL is not configured."
        url = cls._build_url(".info/connected")
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    return True, "Successfully connected to Firebase Realtime Database!"
                return False, f"Firebase returned HTTP status {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code == 401 or e.code == 403:
                return False, "Permission denied. Check Firebase Database Rules (set to read: true, write: true) or provide FIREBASE_SECRET."
            return False, f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    # ----------------------------------------------------
    # Active Test Persistence (with Embedded Images)
    # ----------------------------------------------------

    @classmethod
    def sync_active_test_to_cloud(cls, test_data: Dict[str, Any]) -> bool:
        """Pushes active test and all question images to Firebase."""
        if not cls.is_enabled():
            return False
        url = cls._build_url("active_test")
        if not url:
            return False

        try:
            # Embed image bytes as base64 so images survive Render container restart
            payload = cls._embed_images_as_base64(test_data)
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="PUT"
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                success = (resp.status == 200)
                if success:
                    print(f"[FirebaseSync] Synced active test '{test_data.get('title')}' to Firebase cloud.")
                return success
        except Exception as e:
            print(f"[FirebaseSync] Error syncing active test to Firebase: {e}")
            return False

    @classmethod
    def sync_active_test_to_cloud_async(cls, test_data: Dict[str, Any]):
        """Runs cloud sync in background thread to avoid blocking client requests."""
        if cls.is_enabled():
            threading.Thread(target=cls.sync_active_test_to_cloud, args=(test_data,), daemon=True).start()

    @classmethod
    def fetch_active_test_from_cloud(cls) -> Optional[Dict[str, Any]]:
        """
        Fetches active test from Firebase, re-extracts question image files to local disk,
        and saves local active_test.json cache.
        """
        if not cls.is_enabled():
            return None
        url = cls._build_url("active_test")
        if not url:
            return None

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    if not raw or raw == "null":
                        return None
                    data = json.loads(raw)
                    if not isinstance(data, dict) or not data.get("id"):
                        return None

                    # Restore question images from base64 back onto Render disk
                    restored = cls._restore_images_from_base64(data)

                    # Cache locally
                    with open(ACTIVE_TEST_FILE, "w", encoding="utf-8") as f:
                        json.dump(restored, f, indent=2, ensure_ascii=False)

                    print(f"[FirebaseSync] Successfully rehydrated active test '{restored.get('title')}' from Firebase!")
                    return restored
        except Exception as e:
            print(f"[FirebaseSync] Error fetching active test from Firebase: {e}")
            return None

    @classmethod
    def delete_active_test_from_cloud(cls) -> bool:
        """Deletes active test, submissions, and submissions index from Firebase."""
        if not cls.is_enabled():
            return False

        success = True
        for path in ["active_test", "submissions", "submissions_index"]:
            url = cls._build_url(path)
            if not url:
                continue
            try:
                req = urllib.request.Request(url, method="DELETE")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass
            except Exception as e:
                print(f"[FirebaseSync] Error deleting '{path}' from Firebase: {e}")
                success = False

        if success:
            print("[FirebaseSync] Successfully deleted active test & submissions from Firebase.")
        return success

    @classmethod
    def delete_active_test_from_cloud_async(cls):
        if cls.is_enabled():
            threading.Thread(target=cls.delete_active_test_from_cloud, daemon=True).start()

    # ----------------------------------------------------
    # Submissions & Leaderboard Persistence
    # ----------------------------------------------------

    @classmethod
    def sync_submission_to_cloud(cls, result: Any) -> bool:
        if not cls.is_enabled():
            return False

        try:
            sub_id = getattr(result, "id", None) or result.get("id")
            if not sub_id:
                return False

            # Convert result to dict
            sub_dict = result.model_dump() if hasattr(result, "model_dump") else result

            # 1. Save detailed submission
            sub_url = cls._build_url(f"submissions/{sub_id}")
            sub_bytes = json.dumps(sub_dict, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                sub_url,
                data=sub_bytes,
                headers={"Content-Type": "application/json"},
                method="PUT"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass

            # 2. Update submissions index
            index_url = cls._build_url("submissions_index")
            current_index = cls.fetch_submissions_from_cloud() or []
            summary = {
                "id": sub_dict["id"],
                "test_id": sub_dict["test_id"],
                "test_title": sub_dict["test_title"],
                "student_name": sub_dict["student_name"],
                "roll_no": sub_dict["roll_no"],
                "score": sub_dict["total_score"],
                "max_score": sub_dict["max_score"],
                "percentage": sub_dict["percentage"],
                "correct_count": sub_dict["correct_count"],
                "wrong_count": sub_dict["wrong_count"],
                "unattempted_count": sub_dict["unattempted_count"],
                "time_taken_seconds": sub_dict["time_taken_seconds"],
                "submitted_at": sub_dict["submitted_at"],
                "auto_submitted": sub_dict.get("auto_submitted", False)
            }
            # Prepend newest
            current_index.insert(0, summary)

            idx_bytes = json.dumps(current_index, ensure_ascii=False).encode("utf-8")
            req_idx = urllib.request.Request(
                index_url,
                data=idx_bytes,
                headers={"Content-Type": "application/json"},
                method="PUT"
            )
            with urllib.request.urlopen(req_idx, timeout=10) as resp:
                pass

            print(f"[FirebaseSync] Synced submission '{sub_id}' to Firebase.")
            return True
        except Exception as e:
            print(f"[FirebaseSync] Error syncing submission to Firebase: {e}")
            return False

    @classmethod
    def sync_submission_to_cloud_async(cls, result: Any):
        if cls.is_enabled():
            threading.Thread(target=cls.sync_submission_to_cloud, args=(result,), daemon=True).start()

    @classmethod
    def fetch_submissions_from_cloud(cls) -> List[Dict[str, Any]]:
        """Fetches submissions index from Firebase and restores local index file."""
        if not cls.is_enabled():
            return []
        url = cls._build_url("submissions_index")
        if not url:
            return []

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    if not raw or raw == "null":
                        return []
                    data = json.loads(raw)
                    if isinstance(data, list):
                        # Cache locally
                        with open(SUBMISSIONS_INDEX_FILE, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        return data
        except Exception as e:
            print(f"[FirebaseSync] Error fetching submissions index from Firebase: {e}")
        return []

    @classmethod
    def fetch_submission_detail_from_cloud(cls, submission_id: str) -> Optional[Dict[str, Any]]:
        if not cls.is_enabled():
            return None
        url = cls._build_url(f"submissions/{submission_id}")
        if not url:
            return None

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    if not raw or raw == "null":
                        return None
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        # Save locally
                        sub_file = os.path.join(SUBMISSIONS_DIR, f"{submission_id}.json")
                        with open(sub_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        return data
        except Exception as e:
            print(f"[FirebaseSync] Error fetching submission detail {submission_id}: {e}")
        return None

    # ----------------------------------------------------
    # Startup Auto-Rehydration
    # ----------------------------------------------------

    @classmethod
    def init_and_restore(cls):
        """
        Runs on server boot. If Render just woke up and local files were wiped,
        this immediately pulls the active test and submissions from Firebase.
        """
        if not cls.is_enabled():
            print("[FirebaseSync] No FIREBASE_DATABASE_URL configured. Local file storage active.")
            return

        print("[FirebaseSync] Initializing cloud sync with Firebase...")
        # 1. Restore active test if missing locally
        if not os.path.exists(ACTIVE_TEST_FILE):
            cls.fetch_active_test_from_cloud()
        else:
            # If local active test exists, ensure it is also pushed to cloud
            try:
                with open(ACTIVE_TEST_FILE, "r", encoding="utf-8") as f:
                    local_test = json.load(f)
                if local_test and isinstance(local_test, dict):
                    # Check if cloud has it
                    cloud_test = cls.fetch_active_test_from_cloud()
                    if not cloud_test:
                        cls.sync_active_test_to_cloud(local_test)
            except Exception:
                pass

        # 2. Restore submissions index if missing locally
        if not os.path.exists(SUBMISSIONS_INDEX_FILE):
            cls.fetch_submissions_from_cloud()

    # ----------------------------------------------------
    # Image Base64 Helpers
    # ----------------------------------------------------

    @classmethod
    def _embed_images_as_base64(cls, test_data: Dict[str, Any]) -> Dict[str, Any]:
        data_copy = json.loads(json.dumps(test_data))

        # Check PDF file
        pdf_name = data_copy.get("pdf_filename")
        if pdf_name:
            pdf_path = os.path.join(UPLOADS_DIR, pdf_name)
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) < 15 * 1024 * 1024:
                try:
                    with open(pdf_path, "rb") as f:
                        data_copy["_pdf_b64"] = base64.b64encode(f.read()).decode("ascii")
                except Exception:
                    pass

        # Check questions and options
        for q in data_copy.get("questions", []):
            img_url = q.get("image_url")
            if img_url and isinstance(img_url, str) and img_url.startswith("/static/uploads/"):
                clean_path = img_url.lstrip("/")
                local_path = os.path.join(BASE_DIR, clean_path.replace("/", os.sep))
                if os.path.exists(local_path) and os.path.isfile(local_path):
                    try:
                        with open(local_path, "rb") as f:
                            raw_bytes = f.read()
                        ext = os.path.splitext(local_path)[1].lower()
                        mime = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
                        q["_image_b64"] = f"data:{mime};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
                        q["_image_filename"] = os.path.basename(local_path)
                    except Exception as e:
                        print(f"[FirebaseSync] Error embedding image {local_path}: {e}")

            for opt in q.get("options", []):
                opt_img = opt.get("image_url")
                if opt_img and isinstance(opt_img, str) and opt_img.startswith("/static/uploads/"):
                    clean_path = opt_img.lstrip("/")
                    local_path = os.path.join(BASE_DIR, clean_path.replace("/", os.sep))
                    if os.path.exists(local_path) and os.path.isfile(local_path):
                        try:
                            with open(local_path, "rb") as f:
                                raw_bytes = f.read()
                            ext = os.path.splitext(local_path)[1].lower()
                            mime = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
                            opt["_image_b64"] = f"data:{mime};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
                            opt["_image_filename"] = os.path.basename(local_path)
                        except Exception as e:
                            print(f"[FirebaseSync] Error embedding option image {local_path}: {e}")

        return data_copy

    @classmethod
    def _restore_images_from_base64(cls, test_data: Dict[str, Any]) -> Dict[str, Any]:
        # Restore PDF file
        pdf_b64 = test_data.pop("_pdf_b64", None)
        pdf_name = test_data.get("pdf_filename")
        if pdf_b64 and pdf_name:
            target_pdf = os.path.join(UPLOADS_DIR, pdf_name)
            if not os.path.exists(target_pdf):
                try:
                    with open(target_pdf, "wb") as f:
                        f.write(base64.b64decode(pdf_b64))
                except Exception as e:
                    print(f"[FirebaseSync] Error restoring PDF {pdf_name}: {e}")

        # Restore question images
        for q in test_data.get("questions", []):
            b64 = q.pop("_image_b64", None)
            fname = q.pop("_image_filename", None)
            if b64 and fname:
                target_path = os.path.join(QUESTION_IMAGES_DIR, fname)
                if not os.path.exists(target_path):
                    try:
                        raw_b64 = b64.split(",", 1)[1] if "," in b64 else b64
                        img_bytes = base64.b64decode(raw_b64)
                        with open(target_path, "wb") as f:
                            f.write(img_bytes)
                    except Exception as e:
                        print(f"[FirebaseSync] Error restoring image {fname}: {e}")
                q["image_url"] = f"/static/uploads/questions/{fname}"

            for opt in q.get("options", []):
                opt_b64 = opt.pop("_image_b64", None)
                opt_fname = opt.pop("_image_filename", None)
                if opt_b64 and opt_fname:
                    target_path = os.path.join(QUESTION_IMAGES_DIR, opt_fname)
                    if not os.path.exists(target_path):
                        try:
                            raw_b64 = opt_b64.split(",", 1)[1] if "," in opt_b64 else opt_b64
                            img_bytes = base64.b64decode(raw_b64)
                            with open(target_path, "wb") as f:
                                f.write(img_bytes)
                        except Exception as e:
                            print(f"[FirebaseSync] Error restoring opt image {opt_fname}: {e}")
                    opt["image_url"] = f"/static/uploads/questions/{opt_fname}"

        return test_data
