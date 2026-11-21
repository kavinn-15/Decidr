import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Any

from app.core.config import settings


# Password hashing using PBKDF2-HMAC-SHA256 (NIST SP 800-132 standard)
PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """
    Hashes a password securely using PBKDF2-HMAC-SHA256 with a unique 32-byte salt.
    Format: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    """
    salt = secrets.token_bytes(32)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(hash_bytes).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a stored hash string using constant-time comparison.
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected_hash = base64.b64decode(parts[3].encode("ascii"))

        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(computed_hash, expected_hash)
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Enforces strong password policy:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit or special symbol
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[\d\W_]", password):
        return False, "Password must contain at least one number or special character."
    return True, None


def validate_email_format(email: str) -> bool:
    """
    Validates email format using standard RFC 5322 pattern.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


# Standard JWT implementation (base64url header.payload.signature)
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data_str: str) -> bytes:
    padding = "=" * (4 - (len(data_str) % 4))
    return base64.urlsafe_b64decode(data_str + padding)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a cryptographically signed HMAC-SHA256 JWT access token.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": secrets.token_hex(16),
    })

    header = {"alg": "HS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(to_encode, separators=(",", ":")).encode("utf-8")

    header_b64 = _b64url_encode(header_json)
    payload_b64 = _b64url_encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT token signature and expiration.
    Raises ValueError on invalid token, signature mismatch, or expiration.
    """
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    header_b64, payload_b64, signature_b64 = parts

    # Verify signature
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    expected_sig_b64 = _b64url_encode(expected_sig)

    if not hmac.compare_digest(signature_b64, expected_sig_b64):
        raise ValueError("Invalid JWT signature")

    # Decode payload
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Malformed JWT payload: {e}")

    # Check expiration
    exp = payload.get("exp")
    if exp is not None:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if now_ts > exp:
            raise ValueError("Token has expired")

    return payload


def generate_secure_token(nbytes: int = 32) -> str:
    """Generates a high-entropy URL-safe token for verification or password reset."""
    return secrets.token_urlsafe(nbytes)


def generate_otp(length: int = 6) -> str:
    """Generates a cryptographically secure numeric OTP."""
    digits = [str(secrets.randbelow(10)) for _ in range(length)]
    return "".join(digits)
