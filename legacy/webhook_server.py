#!/usr/bin/env python3
"""
Archived Flask webhook server for an older Yahoo-to-Google-Sheets flow.

This server provides endpoints that can be called from Google Apps Script
to fetch fresh data and update the Google Sheet.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for Google Apps Script calls


@app.route("/", methods=["GET"])
def home():
    """Health check endpoint."""
    return jsonify({
        "status": "running",
        "message": "Yahoo Fantasy Webhook Server",
        "endpoints": {
            "/update": "POST - Fetch fresh data and update Google Sheet",
            "/status": "GET - Get last update status",
        }
    })


@app.route("/status", methods=["GET"])
def status():
    """Get current data status."""
    standings_file = Path("standings.json")

    if not standings_file.exists():
        return jsonify({
            "status": "no_data",
            "message": "No standings data available. Run update first."
        }), 404

    # Get file modification time
    mod_time = datetime.fromtimestamp(standings_file.stat().st_mtime)
    age_minutes = (datetime.now() - mod_time).total_seconds() / 60

    # Read data
    with open(standings_file) as f:
        data = json.load(f)

    return jsonify({
        "status": "ok",
        "last_updated": mod_time.strftime("%Y-%m-%d %I:%M:%S %p"),
        "age_minutes": round(age_minutes, 1),
        "teams_count": len(data.get("teams", [])),
        "categories": [cat["display_name"] for cat in data["league"]["categories"]],
    })


@app.route("/update", methods=["POST"])
def update():
    """
    Fetch fresh Yahoo Fantasy data and push to Google Sheets.

    This endpoint:
    1. Runs yahoo_roto_standings.py to fetch fresh data
    2. Runs push_to_sheets.py to update Google Sheet
    3. Returns status
    """
    logger.info("=" * 80)
    logger.info("UPDATE REQUEST RECEIVED")
    logger.info("=" * 80)

    try:
        # Step 1: Fetch fresh Yahoo data
        logger.info("Step 1: Fetching fresh Yahoo Fantasy data...")
        result = subprocess.run(
            ["python", "yahoo_roto_standings.py"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.error(f"Yahoo fetch failed: {result.stderr}")
            return jsonify({
                "status": "error",
                "step": "fetch_yahoo_data",
                "error": result.stderr,
            }), 500

        logger.info("✓ Yahoo data fetched successfully")

        # Step 2: Push to Google Sheets
        logger.info("Step 2: Pushing data to Google Sheets...")
        result = subprocess.run(
            ["python", "push_to_sheets.py"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.error(f"Google Sheets push failed: {result.stderr}")
            return jsonify({
                "status": "error",
                "step": "push_to_sheets",
                "error": result.stderr,
            }), 500

        logger.info("✓ Google Sheet updated successfully")

        # Get updated data info
        with open("standings.json") as f:
            data = json.load(f)

        return jsonify({
            "status": "success",
            "message": "Data updated successfully!",
            "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            "teams_updated": len(data["teams"]),
        })

    except subprocess.TimeoutExpired:
        logger.error("Update timed out")
        return jsonify({
            "status": "error",
            "error": "Operation timed out",
        }), 504

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
        }), 500


@app.route("/data", methods=["GET"])
def get_data():
    """Return current standings data as JSON."""
    standings_file = Path("standings.json")

    if not standings_file.exists():
        return jsonify({
            "status": "error",
            "message": "No data available"
        }), 404

    with open(standings_file) as f:
        data = json.load(f)

    return jsonify(data)


if __name__ == "__main__":
    port = 8080
    logger.info("=" * 80)
    logger.info("YAHOO FANTASY WEBHOOK SERVER")
    logger.info("=" * 80)
    logger.info(f"Starting server on http://localhost:{port}")
    logger.info("Endpoints:")
    logger.info(f"  - GET  http://localhost:{port}/")
    logger.info(f"  - GET  http://localhost:{port}/status")
    logger.info(f"  - POST http://localhost:{port}/update")
    logger.info(f"  - GET  http://localhost:{port}/data")
    logger.info("=" * 80)

    app.run(host="0.0.0.0", port=port, debug=False)
