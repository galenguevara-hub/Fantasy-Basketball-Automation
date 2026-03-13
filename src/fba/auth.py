"""Yahoo OAuth2 web flow, token encryption, and Flask-Login integration."""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import requests as http_requests
from cryptography.fernet import Fernet, InvalidToken
from flask import session
from flask_login import LoginManager, UserMixin, login_user, logout_user

from fba.config import Config

logger = logging.getLogger(__name__)

# Yahoo OAuth2 endpoints
YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_USERINFO_URL = "https://api.login.yahoo.com/openid/v1/userinfo"

login_manager = LoginManager()


# ---------------------------------------------------------------------------
# User model (session-backed, no database)
# ---------------------------------------------------------------------------

@dataclass
class User(UserMixin):
    id: str  # Yahoo GUID
    display_name: str = ""

    def get_id(self) -> str:
        return self.id


@login_manager.user_loader
def _load_user(user_id: str) -> User | None:
    """Reconstruct user from session. Called by Flask-Login on each request."""
    encrypted = session.get("yahoo_tokens")
    if not encrypted:
        return None
    return User(id=user_id, display_name=session.get("yahoo_display_name", ""))


# ---------------------------------------------------------------------------
# Token encryption (Fernet)
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    return Fernet(Config.get_encryption_key())


def encrypt_tokens(tokens: dict) -> str:
    """Encrypt a token dict for safe storage in the session cookie."""
    return _get_fernet().encrypt(json.dumps(tokens).encode()).decode()


def decrypt_tokens(encrypted: str) -> dict | None:
    """Decrypt tokens from the session cookie. Returns None on failure."""
    try:
        return json.loads(_get_fernet().decrypt(encrypted.encode()))
    except (InvalidToken, json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to decrypt session tokens: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def store_user_session(yahoo_user_id: str, display_name: str, tokens: dict) -> None:
    """Store encrypted tokens and user info in the session, then log in."""
    session["yahoo_tokens"] = encrypt_tokens(tokens)
    session["yahoo_display_name"] = display_name
    user = User(id=yahoo_user_id, display_name=display_name)
    login_user(user, remember=True)


def clear_user_session() -> None:
    """Log out and wipe auth data from the session."""
    logout_user()
    session.pop("yahoo_tokens", None)
    session.pop("yahoo_display_name", None)
    session.pop("oauth_state", None)


def validate_oauth_state(received_state: str) -> bool:
    """Validate the OAuth state parameter to prevent CSRF on the callback.

    Returns True if the state matches and clears it from the session.
    Returns False if missing or mismatched.

    When the local-dev bounce path is used, the state arriving at the local
    callback is the bare token (the ``local_dev:<port>:`` prefix was stripped
    by the production handler before forwarding).
    """
    expected = session.pop("oauth_state", None)
    session.modified = True
    if not expected or not received_state:
        return False
    return secrets.compare_digest(expected, received_state)


def get_user_tokens() -> dict | None:
    """Return decrypted OAuth tokens for the current session, or None."""
    encrypted = session.get("yahoo_tokens")
    if not encrypted:
        return None
    return decrypt_tokens(encrypted)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def refresh_access_token(tokens: dict) -> dict | None:
    """Use the refresh_token to obtain a new access_token from Yahoo.

    Returns the updated token dict on success, None on failure.
    """
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        logger.warning("No refresh_token available — cannot refresh.")
        return None

    resp = http_requests.post(
        YAHOO_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": Config.YAHOO_CLIENT_ID,
            "client_secret": Config.YAHOO_CLIENT_SECRET,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        logger.error("Token refresh failed: HTTP %s — %s", resp.status_code, resp.text)
        return None

    new_tokens = resp.json()
    # Preserve refresh_token if Yahoo didn't return a new one
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    # Record when these tokens were obtained
    new_tokens["obtained_at"] = int(time.time())

    logger.info("Successfully refreshed Yahoo access token.")
    return new_tokens


def get_valid_tokens() -> dict | None:
    """Return valid OAuth tokens, refreshing if expired.

    Updates the session cookie with refreshed tokens when needed.
    Returns None if tokens are missing or refresh fails.
    """
    tokens = get_user_tokens()
    if not tokens:
        return None

    # Check expiration: Yahoo tokens last ~3600s
    obtained_at = tokens.get("obtained_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    if time.time() > obtained_at + expires_in - 60:  # 60s buffer
        logger.info("Access token expired, attempting refresh...")
        new_tokens = refresh_access_token(tokens)
        if not new_tokens:
            return None
        # Update session with refreshed tokens
        session["yahoo_tokens"] = encrypt_tokens(new_tokens)
        session.modified = True
        return new_tokens

    return tokens


# ---------------------------------------------------------------------------
# OAuth2 Authorization Code flow helpers
# ---------------------------------------------------------------------------

PROD_REDIRECT_URI = "https://roto-fantasy-solver.fly.dev/auth/yahoo/callback"


def build_auth_url() -> str:
    """Build the Yahoo OAuth2 authorization redirect URL.

    Generates a cryptographically random state token, stores it in the session,
    and includes it in the URL for CSRF protection on the callback.

    Local dev mode: if REDIS_URL is not set (i.e. running locally), Yahoo is
    always told to redirect to the production callback URL. The production
    handler will detect the ``local_dev:<port>:`` prefix in the state and bounce
    the request back to localhost to complete the flow — so Yahoo only ever
    needs one registered callback URL.
    """
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    session.modified = True

    # In local dev, route the OAuth callback through production so Yahoo only
    # ever sees the stable production redirect URI.
    # Use YAHOO_REDIRECT_URI itself as the signal: if it points to prod, we're
    # in local dev mode (local .env always sets the prod URL; production Fly.io
    # also sets the prod URL but has FLY_APP_NAME set to distinguish).
    import os
    is_local = not os.environ.get("FLY_APP_NAME")
    if is_local:
        redirect_uri = PROD_REDIRECT_URI
        # Embed a local_dev marker + the local port so production can bounce back.
        import re
        local_port = "8080"
        if Config.YAHOO_REDIRECT_URI:
            m = re.search(r":(\d+)/", Config.YAHOO_REDIRECT_URI)
            if m:
                local_port = m.group(1)
        yahoo_state = f"local_dev:{local_port}:{state}"
    else:
        redirect_uri = Config.YAHOO_REDIRECT_URI
        yahoo_state = state

    params = {
        "client_id": Config.YAHOO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "language": "en-us",
        "state": yahoo_state,
    }
    url = f"{YAHOO_AUTH_URL}?{urlencode(params)}"
    logger.info("OAuth authorization URL built (redirect_uri=%s)", redirect_uri)
    return url


def exchange_code_for_tokens(code: str) -> dict | None:
    """Exchange an authorization code for access + refresh tokens.

    Returns the full token response dict, or None on failure.
    """
    resp = http_requests.post(
        YAHOO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": Config.YAHOO_REDIRECT_URI,
            "client_id": Config.YAHOO_CLIENT_ID,
            "client_secret": Config.YAHOO_CLIENT_SECRET,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        logger.error(
            "Token exchange failed: HTTP %s — %s", resp.status_code, resp.text
        )
        return None

    tokens = resp.json()
    tokens["obtained_at"] = int(time.time())
    return tokens


def fetch_yahoo_user_info(access_token: str) -> tuple[str, str]:
    """Fetch user identity from Yahoo. Returns (yahoo_guid, display_name)."""
    try:
        resp = http_requests.get(
            YAHOO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            info = resp.json()
            guid = info.get("sub", "unknown")
            name = info.get("name") or info.get("nickname") or "Yahoo User"
            return guid, name
    except Exception as exc:
        logger.warning("Failed to fetch Yahoo user info: %s", exc)

    return "unknown", "Yahoo User"
