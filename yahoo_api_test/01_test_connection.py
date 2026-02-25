"""
Step 1: Test Yahoo OAuth Connection
====================================
This script verifies that your credentials work and you can connect to Yahoo's API.
On first run, it will open a browser for you to authorize the app.
After that, the token is cached in oauth2.json.
"""

import json
from yahoo_oauth import OAuth2
from yahoo_fantasy_api import Game

CREDENTIALS_FILE = "oauth2.json"


def test_connection():
    print("=" * 60)
    print("Yahoo Fantasy API - Connection Test")
    print("=" * 60)

    # Step 1: Create OAuth session
    print("\n[1] Creating OAuth session...")
    print("    (A browser window may open for authorization)")
    oauth = OAuth2(None, None, from_file=CREDENTIALS_FILE)

    if not oauth.token_is_valid():
        oauth.refresh_access_token()

    print("    OAuth session created successfully!")

    # Step 2: Test with a basic API call
    print("\n[2] Testing API access with NBA game...")
    game = Game(oauth, "nba")
    game_id = game.game_id()
    print(f"    NBA Game ID: {game_id}")

    # Step 3: List your leagues
    print("\n[3] Fetching your NBA league IDs...")
    league_ids = game.league_ids()
    print(f"    Found {len(league_ids)} league(s):")
    for lid in league_ids:
        print(f"      - {lid}")

    print("\n" + "=" * 60)
    print("CONNECTION SUCCESSFUL!")
    print("=" * 60)
    print(f"\nYour league IDs: {league_ids}")
    print("Use these in the next scripts to explore your league data.")

    return oauth, game, league_ids


if __name__ == "__main__":
    test_connection()
