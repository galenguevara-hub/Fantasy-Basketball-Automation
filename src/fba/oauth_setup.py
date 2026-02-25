"""
Yahoo OAuth Setup

Handles first-time OAuth authorization and credential management.
Replaces the Playwright browser login flow.

Usage:
    python -m fba.oauth_setup              # Interactive setup
    python -m fba.oauth_setup --check      # Check auth status
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
OAUTH_FILE = _DATA_DIR / "oauth2.json"


def create_credentials(consumer_key: str, consumer_secret: str):
    """Create the initial oauth2.json with consumer credentials.

    After calling this, instantiating OAuth2 will trigger the browser auth flow.
    """
    OAUTH_FILE.parent.mkdir(parents=True, exist_ok=True)

    creds = {
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
    }
    with open(OAUTH_FILE, "w") as f:
        json.dump(creds, f, indent=4)

    logger.info(f"Credentials saved to {OAUTH_FILE}")


def authorize():
    """Run the full OAuth authorization flow.

    Opens a browser for Yahoo login, then saves tokens to oauth2.json.
    This is interactive — requires user to paste a verifier code.
    """
    from yahoo_oauth import OAuth2

    if not OAUTH_FILE.exists():
        print("No credentials file found.")
        print("Enter your Yahoo app credentials:")
        consumer_key = input("  Consumer Key: ").strip()
        consumer_secret = input("  Consumer Secret: ").strip()
        create_credentials(consumer_key, consumer_secret)

    print("\nStarting Yahoo OAuth authorization...")
    print("A browser window will open. Log in and authorize the app.")
    print("Then paste the verification code below.\n")

    # This will trigger the auth flow (opens browser, prompts for verifier)
    oauth = OAuth2(None, None, from_file=str(OAUTH_FILE))

    if oauth.token_is_valid():
        print("\nAuthorization successful! Token saved.")
        return True
    else:
        print("\nAuthorization failed. Please try again.")
        return False


def check_auth() -> bool:
    """Check if valid OAuth credentials exist and report status."""
    if not OAUTH_FILE.exists():
        print(f"No credentials file found at {OAUTH_FILE}")
        return False

    try:
        from yahoo_oauth import OAuth2
        oauth = OAuth2(None, None, from_file=str(OAUTH_FILE))

        if oauth.token_is_valid():
            print("OAuth token is valid.")
            return True
        else:
            print("OAuth token is expired. Attempting refresh...")
            try:
                oauth.refresh_access_token()
                print("Token refreshed successfully.")
                return True
            except Exception as e:
                print(f"Token refresh failed: {e}")
                print("Run this script without --check to re-authorize.")
                return False
    except Exception as e:
        print(f"Error checking auth: {e}")
        return False


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Yahoo Fantasy OAuth Setup")
    parser.add_argument("--check", action="store_true", help="Check auth status")
    args = parser.parse_args()

    if args.check:
        sys.exit(0 if check_auth() else 1)
    else:
        sys.exit(0 if authorize() else 1)


if __name__ == "__main__":
    main()
