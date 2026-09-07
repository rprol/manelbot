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
    "Ben, Celta, ben! Partido gañado con mérito! Celta 2-1 Getafe"
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

    return f"{phrase} Celta {celta_score}-{opponent_score} {opponent_name}"


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def parse_channel_ids(raw_channel_ids):
    """
    TELEGRAM_CHANNEL_ID can hold a single channel (e.g. "@my_channel") or
    several, separated by commas (e.g. "@channel_one,-1001234567890"), so
    the same result can be posted to more than one channel/group. This
    splits that string into a clean list, ignoring extra whitespace and
    empty entries.
    """
    return [c.strip() for c in raw_channel_ids.split(",") if c.strip()]


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


# A few made-up matches used only for --test-telegram, one per outcome, so
# a test run can show what a WIN/DRAW/LOSS message actually looks like with
# a real (randomly picked) phrase from phrases.py. These are never sent to
# football-data.org or compared against real results -- purely fake data.
FAKE_TEST_MATCHES = [
    {  # Celta at home, WIN
        "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
        "awayTeam": {"id": 559, "name": "Getafe CF"},
        "score": {"winner": "HOME_TEAM", "fullTime": {"home": 2, "away": 1}},
    },
    {  # Celta away, DRAW
        "homeTeam": {"id": 77, "name": "Athletic Club"},
        "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
        "score": {"winner": "DRAW", "fullTime": {"home": 1, "away": 1}},
    },
    {  # Celta away, LOSS
        "homeTeam": {"id": 86, "name": "Real Madrid CF"},
        "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
        "score": {"winner": "HOME_TEAM", "fullTime": {"home": 3, "away": 0}},
    },
]


def run_test_message():
    """
    Send a sample result message -- a random outcome (WIN/DRAW/LOSS) with a
    real, randomly-picked phrase from phrases.py -- to every configured
    Telegram channel, without touching football-data.org or state.json at
    all.

    This lets you check both that Telegram is set up correctly (right
    token, right channel id, bot allowed to post) AND preview what a real
    result message will look like, without waiting for a real Celta match
    to finish. Note: the message sent is indistinguishable from a real
    result (no "TEST" label), since the made-up score is realistic-looking
    on purpose -- only run this when that's not going to confuse anyone
    reading the chat.

    Triggered by running: python main.py --test-telegram
    """
    telegram_token = get_required_env("TELEGRAM_BOT_TOKEN")
    telegram_channel_ids = parse_channel_ids(get_required_env("TELEGRAM_CHANNEL_ID"))

    fake_match = random.choice(FAKE_TEST_MATCHES)
    message = build_message(fake_match, DEFAULT_CELTA_TEAM_ID)

    successes = 0
    for channel_id in telegram_channel_ids:
        print(f"Sending test message to '{channel_id}'...")
        if send_telegram_message(telegram_token, channel_id, message):
            print(f"  -> sent OK to '{channel_id}'.")
            successes += 1
        else:
            print(f"  -> FAILED to send to '{channel_id}'. See error above.")

    print(f"\n{successes}/{len(telegram_channel_ids)} channel(s) received the test message.")
    sys.exit(0 if successes == len(telegram_channel_ids) else 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Special test mode: "python main.py --test-telegram" only exercises
    # the Telegram-sending part, skipping football-data.org and state.json
    # entirely. See run_test_message() above for details.
    if "--test-telegram" in sys.argv:
        run_test_message()
        return

    # 1. Load required configuration from environment variables / secrets.
    telegram_token = get_required_env("TELEGRAM_BOT_TOKEN")
    telegram_channel_ids = parse_channel_ids(get_required_env("TELEGRAM_CHANNEL_ID"))
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

    # 6. We have a new result! Build the message and post it to every
    #    configured channel. We try all of them even if one fails, so a
    #    single broken channel doesn't stop the others from getting posted.
    message = build_message(latest_match, celta_team_id)
    print(f"Posting new result: {message}")

    successes = 0
    for channel_id in telegram_channel_ids:
        if send_telegram_message(telegram_token, channel_id, message):
            successes += 1
        else:
            print(f"Failed to send to channel '{channel_id}'.")

    if successes == 0:
        # Every channel failed -- don't update state, so we retry posting
        # this same result (to all channels) on the next scheduled run.
        print("Failed to send to any channel. Will retry next run.")
        sys.exit(1)

    if successes < len(telegram_channel_ids):
        # Partial failure: at least one channel got the message. We still
        # mark this match as processed so working channels don't get the
        # same result posted again next run -- but the failing channel(s)
        # will miss this result until you fix the underlying issue (e.g.
        # bot removed as admin, wrong channel id).
        print(
            f"WARNING: only {successes}/{len(telegram_channel_ids)} channels "
            "received this message. Check the errors above."
        )

    # 7. Success (at least partially)! Remember this match so we don't post
    #    it again to the channels that already received it.
    save_state({"last_processed_match_id": latest_match_id})
    print("Done.")


if __name__ == "__main__":
    main()
