"""
Step 3: Explore Detailed League Data
======================================
Pulls matchups, draft results, transactions, and rosters.
Edit LEAGUE_ID below after running 01_test_connection.py.
"""

import json
from yahoo_oauth import OAuth2
from yahoo_fantasy_api import Game

CREDENTIALS_FILE = "oauth2.json"

# UPDATE THIS after running 01_test_connection.py
LEAGUE_ID = "466.l.47205"


def pretty(data):
    print(json.dumps(data, indent=2, default=str))


def explore_league_data():
    if LEAGUE_ID is None:
        print("ERROR: Set LEAGUE_ID at the top of this file first!")
        print("Run 01_test_connection.py to find your league IDs.")
        return

    print("=" * 60)
    print(f"Yahoo Fantasy API - League Data Explorer")
    print(f"League: {LEAGUE_ID}")
    print("=" * 60)

    oauth = OAuth2(None, None, from_file=CREDENTIALS_FILE)
    game = Game(oauth, "nba")
    league = game.to_league(LEAGUE_ID)

    # Matchups for current week
    print("\n--- CURRENT MATCHUPS ---")
    try:
        matchups = league.matchups()
        pretty(matchups)
    except Exception as e:
        print(f"  Error: {e}")

    # Week date range
    print("\n--- WEEK DATE RANGE ---")
    try:
        week = league.current_week()
        date_range = league.week_date_range(week)
        print(f"  Week {week}: {date_range[0]} to {date_range[1]}")
    except Exception as e:
        print(f"  Error: {e}")

    # Draft results
    print("\n--- DRAFT RESULTS (first 10) ---")
    try:
        draft = league.draft_results()
        for pick in draft[:10]:
            pretty(pick)
        print(f"  ... ({len(draft)} total picks)")
    except Exception as e:
        print(f"  Error: {e}")

    # Recent transactions
    print("\n--- RECENT TRANSACTIONS ---")
    try:
        transactions = league.transactions("add,drop,trade", "25")
        for txn in transactions[:5]:
            pretty(txn)
        print(f"  ... ({len(transactions)} total)")
    except Exception as e:
        print(f"  Error: {e}")

    # Waivers
    print("\n--- WAIVERS ---")
    try:
        waivers = league.waivers()
        if waivers:
            pretty(waivers[:5])
        else:
            print("  No pending waivers")
    except Exception as e:
        print(f"  Error: {e}")

    # Free agents (top 10)
    print("\n--- TOP FREE AGENTS ---")
    try:
        free_agents = league.free_agents("PG")
        for fa in free_agents[:10]:
            name = fa.get("name", "Unknown")
            print(f"  - {name}")
        pretty(free_agents[:3])  # Full details for first 3
    except Exception as e:
        print(f"  Error: {e}")

    # Your team's roster
    print("\n--- YOUR TEAM KEY ---")
    try:
        team_key = league.team_key()
        print(f"  Team key: {team_key}")

        team = league.to_team(team_key)
        print("\n--- YOUR ROSTER ---")
        roster = team.roster()
        for player in roster:
            name = player.get("name", "Unknown")
            pos = player.get("selected_position", "?")
            print(f"  {pos:4s} - {name}")
        print("\n  Full roster data (first player):")
        if roster:
            pretty(roster[0])
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    explore_league_data()
