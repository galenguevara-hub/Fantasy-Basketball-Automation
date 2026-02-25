"""
Step 4: Explore Player Data
=============================
Deep dive into player stats, ownership, and details.
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


def explore_player_data():
    if LEAGUE_ID is None:
        print("ERROR: Set LEAGUE_ID at the top of this file first!")
        print("Run 01_test_connection.py to find your league IDs.")
        return

    print("=" * 60)
    print(f"Yahoo Fantasy API - Player Data Explorer")
    print(f"League: {LEAGUE_ID}")
    print("=" * 60)

    oauth = OAuth2(None, None, from_file=CREDENTIALS_FILE)
    game = Game(oauth, "nba")
    league = game.to_league(LEAGUE_ID)

    # Search for a specific player by name
    print("\n--- PLAYER DETAILS (by name) ---")
    test_players = ["LeBron James", "Nikola Jokic", "Luka Doncic"]
    for player_name in test_players:
        try:
            details = league.player_details(player_name)
            print(f"\n  {player_name}:")
            pretty(details)
        except Exception as e:
            print(f"  {player_name}: Error - {e}")

    # Free agents by position
    print("\n--- FREE AGENTS BY POSITION ---")
    positions = ["PG", "SG", "SF", "PF", "C"]
    for pos in positions:
        try:
            fas = league.free_agents(pos)
            print(f"\n  {pos}: {len(fas)} available")
            if fas:
                # Show top 3 names
                for fa in fas[:3]:
                    print(f"    - {fa.get('name', 'Unknown')}")
        except Exception as e:
            print(f"  {pos}: Error - {e}")

    # Taken players
    print("\n--- TAKEN PLAYERS (sample) ---")
    try:
        taken = league.taken_players()
        print(f"  Total taken: {len(taken)}")
        for p in taken[:5]:
            pretty(p)
    except Exception as e:
        print(f"  Error: {e}")

    # Player stats (season)
    print("\n--- PLAYER STATS (season) ---")
    print("  Note: Need player IDs. Getting from roster first...")
    try:
        team_key = league.team_key()
        team = league.to_team(team_key)
        roster = team.roster()

        if roster:
            # Get first 3 player IDs from roster
            player_ids = []
            for p in roster[:3]:
                pid = p.get("player_id")
                if pid:
                    player_ids.append(pid)

            if player_ids:
                print(f"  Fetching stats for player IDs: {player_ids}")
                stats = league.player_stats(player_ids, "season")
                pretty(stats)
            else:
                print("  Could not extract player IDs from roster")
                print("  Roster sample:")
                pretty(roster[0])
    except Exception as e:
        print(f"  Error: {e}")

    # Ownership / percent owned
    print("\n--- PERCENT OWNED ---")
    try:
        if player_ids:
            pct = league.percent_owned(player_ids)
            pretty(pct)
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    explore_player_data()
