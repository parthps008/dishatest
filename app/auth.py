import hmac
import hashlib
import time
from fastapi import Request

# ----------------- Disha Academy Admin Credentials -----------------
ADMIN_USERNAME = "dishateacher"
ADMIN_PASSWORD = "disha@1235"

SECRET_KEY = "disha-academy-secure-admin-portal-key-2026-auth"
SESSION_COOKIE_NAME = "disha_admin_session"
LEGACY_COOKIE_NAME = "disha_admin"
SESSION_MAX_AGE = 86400  # 24 hours (in seconds)


def authenticate_admin(username: str, password: str) -> bool:
    """Verifies admin ID and password."""
    if not username or not password:
        return False
    return username.strip() == ADMIN_USERNAME and password.strip() == ADMIN_PASSWORD


def create_session_token(username: str = ADMIN_USERNAME) -> str:
    """Generates an HMAC-signed session token containing username and timestamp."""
    timestamp = int(time.time())
    payload = f"{username}:{timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> bool:
    """Validates HMAC signature and timestamp expiry of the session token."""
    if not token or not isinstance(token, str):
        return False
    parts = token.split(":")
    if len(parts) != 3:
        return False
    
    username, ts_str, signature = parts
    if username != ADMIN_USERNAME:
        return False
    
    try:
        timestamp = int(ts_str)
    except ValueError:
        return False
    
    # Check if session expired (24 hours)
    if (time.time() - timestamp) > SESSION_MAX_AGE:
        return False
    
    expected_payload = f"{username}:{timestamp}"
    expected_sig = hmac.new(SECRET_KEY.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_sig)


def is_admin_authenticated(request: Request) -> bool:
    """Checks whether the incoming HTTP request has a valid admin session cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return verify_session_token(token)
