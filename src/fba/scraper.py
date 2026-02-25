#!/usr/bin/env python3
"""
Yahoo Fantasy Basketball Standings Scraper

Uses Playwright to scrape the Yahoo Fantasy standings page (requires login).
Saves browser session state after first login so subsequent runs are headless.

Usage:
    python scraper.py                     # headless (requires prior login)
    python scraper.py --login             # open browser, log in, save session
    python scraper.py --league-id 47205   # custom league ID
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

LEAGUE_ID = "47205"
STANDINGS_URL = "https://basketball.fantasysports.yahoo.com/nba/{league_id}/standings"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
BROWSER_STATE_FILE = str(_DATA_DIR / "browser_state.json")
STANDINGS_OUTPUT_FILE = str(_DATA_DIR / "standings.json")

# How long to wait for the standings tables to appear (ms)
TABLE_TIMEOUT_MS = 30_000


def login_and_save_session(league_id: str, no_prompt: bool = False) -> dict:
    """
    Open a visible browser, let the user log in, scrape standings, save session.

    Returns the scraped data so main() doesn't need to launch a second browser.
    If no_prompt is False, the browser stays open until the user presses Enter.
    If no_prompt is True (web app mode), the browser closes automatically after scraping.
    """
    url = STANDINGS_URL.format(league_id=league_id)
    logger.info("Opening browser — navigate to Yahoo and log in.")
    logger.info("The browser will navigate to your standings page automatically after login.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Navigate directly to the standings URL.
        # Yahoo will redirect through its login flow and then land back here.
        page.goto(url)

        try:
            # Wait for the user to complete login and land on standings
            page.wait_for_url(f"**/nba/{league_id}/standings**", timeout=120_000)
            page.wait_for_selector("table", timeout=TABLE_TIMEOUT_MS)
            # Let the JS finish populating all table rows
            page.wait_for_timeout(3_000)
        except PlaywrightTimeoutError:
            logger.error("Timed out waiting for standings page. Please try again.")
            browser.close()
            sys.exit(1)

        # Save session state AFTER the page is fully loaded
        context.storage_state(path=BROWSER_STATE_FILE)
        logger.info(f"Session saved to {BROWSER_STATE_FILE}")

        # Scrape now while we have the live page — avoids a second browser launch
        html = page.content()
        data = parse_standings_html(html)

        if not no_prompt:
            logger.info("Scrape complete. Close the browser window when you're done.")
            try:
                input("Press Enter here to close the browser...")
            except (EOFError, KeyboardInterrupt):
                pass

        browser.close()

    return data


def scrape_standings(league_id: str) -> dict:
    """Scrape the Yahoo Fantasy standings page and return structured data."""
    url = STANDINGS_URL.format(league_id=league_id)
    state_file = Path(BROWSER_STATE_FILE)

    if not state_file.exists():
        logger.error(f"No saved session found ({BROWSER_STATE_FILE}).")
        logger.error("Run: python scraper.py --login")
        sys.exit(1)

    logger.info(f"Scraping standings for league {league_id}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=BROWSER_STATE_FILE)
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=TABLE_TIMEOUT_MS)

            # Wait for at least one table to render (React needs time after DOM load)
            page.wait_for_selector("table", timeout=TABLE_TIMEOUT_MS)

            # Fixed wait instead of networkidle — Yahoo has continuous background
            # requests (analytics/ads) that prevent networkidle from ever settling.
            page.wait_for_timeout(3_000)

        except PlaywrightTimeoutError:
            logger.error("Timed out loading standings page.")
            logger.error("Your session may have expired. Run: python scraper.py --login")
            browser.close()
            sys.exit(1)

        html = page.content()
        browser.close()

    return parse_standings_html(html)


def parse_standings_html(html: str) -> dict:
    """Parse the Yahoo Fantasy standings HTML into structured JSON."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    if len(tables) < 2:
        logger.error(f"Expected 2 tables (Overall Points + Overall Stats), found {len(tables)}.")
        logger.error("The page structure may have changed or the session may be expired.")
        sys.exit(1)

    # Yahoo standings page has two tables in order:
    # tables[0] = Overall Points (roto points per category)
    # tables[1] = Overall Stats (actual stat values)
    points_table = tables[0]
    stats_table = tables[1]

    categories, roto_rows = parse_points_table(points_table)
    stats_rows = parse_stats_table(stats_table)

    # Merge by team name (rank can have ties, so it's not a unique key)
    teams = []
    stats_by_name = {row["team_name"]: row for row in stats_rows}

    for roto_row in roto_rows:
        rank = roto_row["rank"]
        name = roto_row["team_name"]
        team = {
            "rank": rank,
            "team_name": name,
            "total_points": roto_row["total_points"],
            "pts_change": roto_row.get("pts_change", 0),
            "roto_points": roto_row["roto_points"],
            "stats": stats_by_name.get(name, {}).get("stats", {}),
        }
        teams.append(team)

    return {
        "scraped_at": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
        "league": {"categories": [{"display_name": cat} for cat in categories]},
        "teams": teams,
    }


def parse_points_table(table) -> tuple[list[str], list[dict]]:
    """
    Parse the Overall Points table.

    Returns (categories, rows) where categories is a list of stat column names
    and rows is a list of dicts with rank, team_name, roto_points, total_points, pts_change.
    """
    rows = table.find_all("tr")

    # Find the header row that contains category names.
    # Yahoo renders two header rows; the second one has the actual column names.
    header_cells = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        # The column header row contains "Rank" and "Team Name"
        cell_texts = [c.get_text(strip=True) for c in cells]
        if "Rank" in cell_texts and "Team Name" in cell_texts:
            header_cells = cell_texts
            break

    if not header_cells:
        logger.warning("Could not find Points table header row — using positional parsing.")
        # Fall back: assume standard column order
        header_cells = ["Rank", "Team Name", "FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "Total Points", "Pts Change"]

    # Extract category columns (everything between "Team Name" and "Total Points")
    try:
        start = header_cells.index("Team Name") + 1
        end = header_cells.index("Total Points")
        categories = header_cells[start:end]
    except ValueError:
        # Fallback category names from standings.json
        categories = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK"]
        start = 2
        end = start + len(categories)

    data_rows = []
    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]
        if not texts[0].isdigit():
            continue  # skip header/group rows

        rank = int(texts[0])
        team_name = texts[1] if len(texts) > 1 else ""

        roto_points = {}
        for i, cat in enumerate(categories):
            col_idx = start + i
            if col_idx < len(texts):
                try:
                    val = float(texts[col_idx])
                    roto_points[cat] = int(val) if val == int(val) else val
                except ValueError:
                    roto_points[cat] = 0

        total_points = 0
        if end < len(texts):
            try:
                val = float(texts[end])
                total_points = int(val) if val == int(val) else val
            except ValueError:
                pass

        # Fallback: if total_points is 0 but roto_points has values, compute the sum.
        # This handles cases where Yahoo renders total_points in an unparseable format.
        if total_points == 0 and roto_points:
            computed = sum(v for v in roto_points.values() if isinstance(v, (int, float)))
            if computed > 0:
                total_points = computed

        pts_change = 0
        if end + 1 < len(texts):
            try:
                pts_change = int(texts[end + 1])
            except ValueError:
                pass

        data_rows.append({
            "rank": rank,
            "team_name": team_name,
            "roto_points": roto_points,
            "total_points": total_points,
            "pts_change": pts_change,
        })

    return categories, data_rows


def parse_stats_table(table) -> list[dict]:
    """
    Parse the Overall Stats table.

    Returns a list of dicts with rank and stats (GP, FG%, FT%, etc.).
    """
    rows = table.find_all("tr")

    # Find the header row to get column names
    header_cells = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        cell_texts = [c.get_text(strip=True) for c in cells]
        if "Rank" in cell_texts and "Team Name" in cell_texts:
            header_cells = cell_texts
            break

    if not header_cells:
        header_cells = ["Rank", "Team Name", "GP*", "FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK"]

    # Stat columns start after "Team Name"
    try:
        stat_start = header_cells.index("Team Name") + 1
    except ValueError:
        stat_start = 2
    stat_cols = header_cells[stat_start:]

    data_rows = []
    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]
        if not texts[0].isdigit():
            continue

        rank = int(texts[0])
        stats = {}
        for i, col in enumerate(stat_cols):
            col_idx = stat_start + i
            if col_idx >= len(texts):
                break
            raw = texts[col_idx].rstrip("*")  # GP* → GP value
            # Normalize column name: "GP*" → "GP"
            col_name = col.rstrip("*")
            try:
                if "." in raw:
                    stats[col_name] = float(raw)
                else:
                    stats[col_name] = int(raw) if raw else 0
            except ValueError:
                stats[col_name] = raw

        team_name = texts[1] if len(texts) > 1 else ""
        data_rows.append({"rank": rank, "team_name": team_name, "stats": stats})

    return data_rows


def main():
    parser = argparse.ArgumentParser(description="Scrape Yahoo Fantasy Basketball standings")
    parser.add_argument("--league-id", default=LEAGUE_ID, help=f"League ID (default: {LEAGUE_ID})")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open browser to log in to Yahoo and save session",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Close browser automatically after scraping (no interactive prompt)",
    )
    parser.add_argument(
        "--outfile",
        default=STANDINGS_OUTPUT_FILE,
        help=f"Output JSON file (default: {STANDINGS_OUTPUT_FILE})",
    )
    args = parser.parse_args()

    if args.login:
        # login_and_save_session scrapes during the login browser session,
        # so we don't need to launch a second headless browser afterward.
        data = login_and_save_session(args.league_id, no_prompt=args.no_prompt)
    else:
        data = scrape_standings(args.league_id)

    out_path = Path(args.outfile)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    teams_count = len(data.get("teams", []))
    logger.info(f"Saved standings for {teams_count} teams to {out_path}")


if __name__ == "__main__":
    main()
