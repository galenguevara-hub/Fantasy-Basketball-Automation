"""Application configuration loaded from environment variables."""

import base64
import hashlib
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    YAHOO_CLIENT_ID = os.environ.get("YAHOO_CLIENT_ID", "")
    YAHOO_CLIENT_SECRET = os.environ.get("YAHOO_CLIENT_SECRET", "")
    YAHOO_REDIRECT_URI = os.environ.get(
        "YAHOO_REDIRECT_URI", "http://localhost:8080/auth/yahoo/callback"
    )

    @classmethod
    def get_encryption_key(cls) -> bytes:
        """Return a Fernet-compatible encryption key.

        Uses TOKEN_ENCRYPTION_KEY env var if set, otherwise derives one
        from SECRET_KEY (convenient for local dev).
        """
        explicit = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
        if explicit:
            return explicit.encode()
        # Derive a 32-byte key from SECRET_KEY, then base64-encode for Fernet
        digest = hashlib.sha256(cls.SECRET_KEY.encode()).digest()
        return base64.urlsafe_b64encode(digest)
