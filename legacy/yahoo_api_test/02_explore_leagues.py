"""
Step 2: Explore League Data
============================
Discovers your leagues and prints settings, standings, and basic info.
"""

import json
from yahoo_oauth import OAuth2
from yahoo_fantasy_api import Game

CREDENTIALS_FILE = "oauth2.json"


def pretty(data):
    """Pretty print any data structure."""
    print(json.dumps(data, indent=2, default=str))


def explore_leagues():
    print("=" * 60)
    print("Yahoo Fantasy API - League Explorer")
    print("=" * 60)

    oauth = OAuth2(None, None, from_file=CREDENTIALS_FILE)
    game = Game(oauth, "nba")
    league_ids = game.league_ids()

    for league_id in league_ids:
        print(f"\n{'='*60}")
        print(f"LEAGUE: {league_id}")
        print(f"{'='*60}")

        league = game.to_league(league_id)

        # Settings
        print("\n--- SETTINGS ---")
        try:
            settings = league.settings()
            pretty(settings)
        except Exception as e:
            print(f"  Error: {e}")

        # Current week
        print("\n--- CURRENT WEEK ---")
        try:
            week = league.current_week()
            print(f"  Week: {week}")
        except Exception as e:
            print(f"  Error: {e}")

        # Standings
        print("\n--- STANDINGS ---")
        try:
            standings = league.standings()
            for i, team in enumerate(standings, 1):
                name = team.get("name", "Unknown")
                print(f"  {i}. {name}")
        except Exception as e:
            print(f"  Error: {e}")

        # Teams
        print("\n--- TEAMS ---")
        try:
            teams = league.teams()
            pretty(teams)
        except Exception as e:
            print(f"  Error: {e}")

        # Stat categories
        print("\n--- STAT CATEGORIES ---")
        try:
            categories = league.stat_categories()
            pretty(categories)
        except Exception as e:
            print(f"  Error: {e}")

        # Positions
        print("\n--- POSITIONS ---")
        try:
            positions = league.positions()
            pretty(positions)
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    explore_leagues()
