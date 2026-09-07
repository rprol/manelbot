#!/usr/bin/env python3
"""
main.py -- Manel Bot

This script checks whether Celta de Vigo have just finished a La Liga match,
and if so, posts a result message to a Telegram channel.

It is designed to be run on a schedule (see .github/workflows/check_result.yml)
rather than kept running all the time. Each run does the following:

  1. Read state.json to see which finished match we last posted about.
  2. Ask football-data.org for Celta's most recent matches.
  3. If there's a finished match we haven't posted yet, work out whether it
     was a WIN, DRAW, or LOSS for Celta, pick a random Galician phrase, and
     send a message to the Telegram channel.
  4. Save the new match id to state.json so we don't post the same result
     twice next time this script runs.

Nothing here needs a server or a database -- state.json (a single small
JSON file) is all we use to remember what's already been posted, and the
GitHub Actions workflow commits it back to the repo after each run.
"""

import json
import os
import random
import sys

import requests

from phrases import get_random_phrase

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Where we keep track of the last match we posted about, so we never post
# the same result twice. This file lives in the repo and gets committed
# back by the GitHub Actions workflow after every run.
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# football-data.org competition code for the Spanish La Liga ("PD" = Primera
# División). See https://www.football-data.org/documentation/quickstart
COMPETITION_CODE = "PD"

# football-data.org's numeric id for RC Celta de Vigo.
#
# NOTE: this is a best-guess default and has NOT been independently
# verified against the live API. Before relying on this bot, please confirm
# the id yourself -- the README explains exactly how (a one-line curl
# command) -- and set the CELTA_TEAM_ID environment variable/secret if it
# turns out to be different.
DEFAULT_CELTA_TEAM_ID = "558"

# How many of Celta's most recent finished matches to fetch. We only ever
# care about the single latest one, but asking for a few gives us a safety
# margin in case the API's "most recent" ordering ever surprises us.
MATCH_FETCH_LIMIT = 5

# Emojis used in the posted message (Celta's colours: sky blue and white).
CELTA_EMOJIS = "🔵⚪"

# How long to wait for network calls before giving up, in seconds.
REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def get_required_env(name):
    """
    Fetch an environment variable that MUST be set (a secret/token/etc).
    If it's missing, print a clear error and stop the script.
    """
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: required environment variable '{name}' is not set.")
        sys.exit(1)
    return value


def load_state():
    """
    Load state.json and return it as a dict. If the file doesn't exist yet
    (e.g. this is the very first run), return a default state instead of
    crashing.
    """
    if not os.path.exists(STATE_FILE):
        return {"last_processed_match_id": None}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as error:
        # If the state file is somehow corrupted, don't crash -- just start
        # fresh. Worst case we might re-post one old result, which is far
        # better than the whole workflow breaking permanently.
        print(f"WARNING: could not read {STATE_FILE} ({error}). Starting fresh.")
        return {"last_processed_match_id": None}


def save_state(state):
    """Write the state dict back to state.json, pretty-printed."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# football-data.org
# ---------------------------------------------------------------------------

def fetch_recent_matches(api_key, team_id):
    """
    Ask football-data.org for Celta's most recent FINISHED matches.

    Returns a list of match dicts (newest first), or None if the request
    failed for any reason. We deliberately return None instead of raising,
    so main() can just skip this run and try again next time.
    """
    url = f"https://api.football-data.org/v4/teams/{team_id}/matches"
    headers = {"X-Auth-Token": api_key}
    params = {
        "status": "FINISHED",
        "competitions": COMPETITION_CODE,
        "limit": MATCH_FETCH_LIMIT,
    }

    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException as error:
        print(f"ERROR: request to football-data.org failed: {error}")
        return None

    if response.status_code == 429:
        print("ERROR: football-data.org rate limit hit. Will try again next run.")
        return None

    if response.status_code != 200:
        print(
            f"ERROR: football-data.org returned status {response.status_code}: "
            f"{response.text[:300]}"
        )
        return None

    try:
        data = response.json()
    except ValueError as error:
        print(f"ERROR: could not parse football-data.org response as JSON: {error}")
        return None

    matches = data.get("matches", [])

    # Extra safety net: only keep matches that are actually in La Liga and
    # actually finished, in case the API ever returns something unexpected.
    matches = [
        m
        for m in matches
        if m.get("status") == "FINISHED"
        and m.get("competition", {}).get("code") == COMPETITION_CODE
    ]

    # Sort newest first by kickoff date, so matches[0] is the latest match.
    matches.sort(key=lambda m: m.get("utcDate", ""), reverse=True)
    return matches


def determine_outcome(match, team_id):
    """
    Work out the result from Celta's point of view: "WIN", "DRAW", or "LOSS".
    Handles both home and away matches.
    """
    team_id = int(team_id)
    winner = match.get("score", {}).get("winner")  # "HOME_TEAM" / "AWAY_TEAM" / "DRAW"
    home_id = match.get("homeTeam", {}).get("id")

    if winner == "DRAW":
        return "DRAW"

    celta_is_home = home_id == team_id
    celta_won = (winner == "HOME_TEAM" and celta_is_home) or (
        winner == "AWAY_TEAM" and not celta_is_home
    )
    return "WIN" if celta_won else "LOSS"


def build_message(match, team_id):
    """
    Build the full text we're going to post to Telegram, e.g.:
    "Ben, Celta, ben! Partido gañado con mérito! 🔵⚪ Celta 2-1 Getafe"
    """
    team_id = int(team_id)
    home_team = match["homeTeam"]
    away_team = match["awayTeam"]
    full_time = match["score"]["fullTime"]

    celta_is_home = home_team.get("id") == team_id
    if celta_is_home:
        opponent_name = away_team.get("name", "o rival")
        celta_score = full_time.get("home")
        opponent_score = full_time.get("away")
    else:
        opponent_name = home_team.get("name", "o rival")
        celta_score = full_time.get("away")
        opponent_score = full_time.get("home")

    outcome = determine_outcome(match, team_id)
    phrase = get_random_phrase(outcome)

    return f"{phrase} {CELTA_EMOJIS} Celta {celta_score}-{opponent_score} {opponent_name}"


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram_message(bot_token, channel_id, text):
    """
    Post a message to the configured Telegram channel using the Bot API.
    Returns True on success, False on failure (never raises).
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": channel_id, "text": text}

    try:
        response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as error:
        print(f"ERROR: request to Telegram failed: {error}")
        return False

    if response.status_code != 200:
        print(
            f"ERROR: Telegram API returned status {response.status_code}: "
            f"{response.text[:300]}"
        )
        return False

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1. Load required configuration from environment variables / secrets.
    telegram_token = get_required_env("TELEGRAM_BOT_TOKEN")
    telegram_channel_id = get_required_env("TELEGRAM_CHANNEL_ID")
    football_api_key = get_required_env("FOOTBALL_DATA_API_KEY")
    # CELTA_TEAM_ID is not a secret, just a config value, so it's fine to
    # fall back to a default instead of requiring it to be set. We use
    # "or" (not just .get(..., default)) because the GitHub Actions
    # workflow always sets this env var, even to an empty string if the
    # secret hasn't been configured -- .get()'s default would never kick
    # in for an empty-but-present value.
    celta_team_id = os.environ.get("CELTA_TEAM_ID") or DEFAULT_CELTA_TEAM_ID

    # 2. Load what we last posted about.
    state = load_state()
    last_processed_id = state.get("last_processed_match_id")

    # 3. Fetch Celta's recent finished matches.
    matches = fetch_recent_matches(football_api_key, celta_team_id)
    if not matches:
        # Either an API error (already logged above) or genuinely no
        # finished matches yet. Either way, there's nothing more to do --
        # exit cleanly so the scheduled workflow doesn't show as failed.
        print("No finished matches to process this run.")
        return

    latest_match = matches[0]
    latest_match_id = latest_match["id"]

    # 4. First-run bootstrap: if we have no prior state at all, don't post
    #    about a match that may have finished long before the bot existed.
    #    Just remember it as "already seen" and start posting from the next
    #    new result onwards.
    if last_processed_id is None:
        print(
            f"First run detected. Recording match {latest_match_id} as the "
            "starting point without posting (to avoid posting an old result)."
        )
        save_state({"last_processed_match_id": latest_match_id})
        return

    # 5. If the latest finished match is one we've already posted, there's
    #    nothing new to do.
    if latest_match_id == last_processed_id:
        print("Latest finished match has already been posted. Nothing to do.")
        return

    # 6. We have a new result! Build the message and post it.
    message = build_message(latest_match, celta_team_id)
    print(f"Posting new result: {message}")

    sent_ok = send_telegram_message(telegram_token, telegram_channel_id, message)
    if not sent_ok:
        # Don't update state if the message failed to send -- we want to
        # retry posting this same result on the next scheduled run.
        print("Failed to send Telegram message. Will retry next run.")
        sys.exit(1)

    # 7. Success! Remember this match so we don't post it again.
    save_state({"last_processed_match_id": latest_match_id})
    print("Done.")


if __name__ == "__main__":
    main()
