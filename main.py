#!/usr/bin/env python3
"""
main.py -- Manel Bot

This script checks whether Celta de Vigo have just finished a match, and if
so, posts a result message to a Telegram channel.

It is designed to be run on a schedule (see .github/workflows/check_result.yml)
rather than kept running all the time. Each run does two independent checks:

  1. check_la_liga_result() -- La Liga and the Champions League, via
     football-data.org (the only two competitions its free tier covers for
     Celta -- confirmed against the live API).
  2. check_other_competitions_result() -- everything else (Copa del Rey,
     Europa League, Conference League, ...), via TheSportsDB, which
     football-data.org's free tier simply doesn't include. It looks up
     Celta's actual latest finished match regardless of competition, and
     skips it if that turns out to be a La Liga/Champions League match --
     those are already handled (with richer data) by check #1.

Both checks work the same way: read state.json for the last match we
already posted about, compare it to the latest finished match, and if
there's a new one, work out not just WIN/DRAW/LOSS but the *shape* of the
match (comeback, blowout, narrow result, etc. -- see classify_match()),
pick a random Galician phrase matching that, and send a message to the
Telegram channel. Each writes its own key to state.json so the two checks
don't interfere with each other.

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

# football-data.org competition codes this check covers: "PD" (La Liga,
# Primera División) and "CL" (Champions League). These are the only two
# competitions Celta could play in that football-data.org's *free* tier
# actually includes -- confirmed by querying /v4/competitions with our key
# and separately getting a 403 "check your subscription" on both Copa del
# Rey and the Europa League. See check_other_competitions_result() below
# for how those (and anything else) get covered instead, via TheSportsDB.
COMPETITION_CODES = "PD,CL"

# Human-readable competition names, keyed by football-data.org's code --
# used as the `competition_key` passed to select_category() (see below),
# so La Liga and Champions League results track their win/loss streaks
# separately.
COMPETITION_NAMES_BY_CODE = {
    "PD": "La Liga",
    "CL": "UEFA Champions League",
}

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

# TheSportsDB (https://www.thesportsdb.com) is an optional second data
# source, used only to enrich a result with things football-data.org's free
# tier doesn't give us: goal scorer/assist names, goal minutes, and red
# cards. If this lookup fails, or can't confidently be matched to the
# right match, we just post without that extra detail -- see
# fetch_thesportsdb_match_events(). It never blocks the core posting flow.

# TheSportsDB's numeric id for Celta Vigo -- confirmed by querying the live
# API and cross-checking that it returned the same real match
# football-data.org reported (same date, same score).
DEFAULT_THESPORTSDB_TEAM_ID = "133937"

# "3" is TheSportsDB's public free test key, usable with no registration --
# per their own docs, this is the normal way to use the v1 API for free/
# hobby projects. It's shared across everyone using it, so if reliability
# ever becomes an issue, register for a personal key at
# https://www.thesportsdb.com/free_sports_api and set THESPORTSDB_API_KEY.
DEFAULT_THESPORTSDB_API_KEY = "3"

# TheSportsDB's own numeric league ids for La Liga and the Champions League
# (confirmed live: GET /search_all_leagues.php?c=Spain and
# /lookupleague.php?id=4480). check_other_competitions_result() uses these
# to recognise when Celta's latest TheSportsDB event is actually one of the
# two competitions check_la_liga_result() already handles (with richer
# half-time data straight from football-data.org), so it doesn't post the
# same match a second time.
THESPORTSDB_LEAGUES_COVERED_BY_FOOTBALL_DATA = {
    "4335",  # Spanish La Liga
    "4480",  # UEFA Champions League
}

# A goal scored at or after this minute counts as "late drama" for the
# WIN_LATE / DRAW_LATE / LOSS_LATE categories.
LATE_GOAL_MINUTE = 85


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
    Ask football-data.org for Celta's most recent FINISHED matches in the
    competitions its free tier covers (see COMPETITION_CODES).

    Returns a list of match dicts (newest first), or None if the request
    failed for any reason. We deliberately return None instead of raising,
    so main() can just skip this run and try again next time.
    """
    url = f"https://api.football-data.org/v4/teams/{team_id}/matches"
    headers = {"X-Auth-Token": api_key}
    params = {
        "status": "FINISHED",
        "competitions": COMPETITION_CODES,
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

    # Extra safety net: only keep matches that are actually in one of our
    # covered competitions and actually finished, in case the API ever
    # returns something unexpected.
    covered_codes = set(COMPETITION_CODES.split(","))
    matches = [
        m
        for m in matches
        if m.get("status") == "FINISHED"
        and m.get("competition", {}).get("code") in covered_codes
    ]

    # Sort newest first by kickoff date, so matches[0] is the latest match.
    matches.sort(key=lambda m: m.get("utcDate", ""), reverse=True)
    return matches


# ---------------------------------------------------------------------------
# TheSportsDB -- covers two different jobs:
#   1. Enrichment for La Liga/Champions League matches (scorers, assists,
#      red cards) on top of football-data.org's core result -- optional,
#      never blocks posting. See fetch_thesportsdb_match_events().
#   2. The *only* source for competitions football-data.org's free tier
#      doesn't cover at all (Copa del Rey, Europa League, ...) -- see
#      fetch_thesportsdb_latest_event() and check_other_competitions_result().
# ---------------------------------------------------------------------------

def _fetch_thesportsdb_timeline(event_id, thesportsdb_team_id, api_key):
    """
    Fetch and parse the goal-by-goal and card timeline for one TheSportsDB
    event id. Shared by fetch_thesportsdb_match_events() (enrichment, event
    found by matching calendar date) and check_other_competitions_result()
    (the event id is already known there), so both parse timeline entries
    identically.

    Returns {"goals": [...], "red_cards": [...]}, where:
      - goals is a list sorted by minute, each a dict like
        {"minute": 41, "scorer": "Ferran Jutglà", "celta_scored": True,
         "assist": "Hugo González" or None}
      - red_cards is a list of dicts like
        {"minute": 72, "player": "...", "celta": True}

    Returns None (not a dict) if the lookup itself fails. Either inner list
    can still be empty (a real match can have zero red cards) -- only the
    outer None means "no data at all".
    """
    base_url = f"https://www.thesportsdb.com/api/v1/json/{api_key}"

    try:
        response = requests.get(
            f"{base_url}/lookuptimeline.php",
            params={"id": event_id},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        timeline = response.json().get("timeline") or []
    except (requests.exceptions.RequestException, ValueError) as error:
        print(f"WARNING: TheSportsDB timeline lookup failed, posting without extra detail: {error}")
        return None

    goals = []
    red_cards = []
    for event in timeline:
        try:
            minute = int(event["intTime"])
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed entries rather than crash on bad data

        event_type = event.get("strTimeline")
        is_celta = event.get("idTeam") == thesportsdb_team_id

        if event_type == "Goal":
            goals.append(
                {
                    "minute": minute,
                    "scorer": event.get("strPlayer") or "descoñecido",
                    "celta_scored": is_celta,
                    "assist": event.get("strAssist") or None,
                }
            )
        elif event_type == "Card" and "red" in (event.get("strTimelineDetail") or "").lower():
            red_cards.append(
                {
                    "minute": minute,
                    "player": event.get("strPlayer") or "descoñecido",
                    "celta": is_celta,
                }
            )

    goals.sort(key=lambda g: g["minute"])
    red_cards.sort(key=lambda c: c["minute"])
    return {"goals": goals, "red_cards": red_cards}


def fetch_thesportsdb_match_events(match, thesportsdb_team_id, api_key):
    """
    Look up the same football-data.org match on TheSportsDB and return its
    timeline, so we can name scorers (and who assisted them), detect late
    drama, and detect a Celta player being sent off -- none of which
    football-data.org's free tier can tell us on its own. Used only for the
    two competitions football-data.org covers (see check_la_liga_result());
    check_other_competitions_result() already has its event id directly and
    calls _fetch_thesportsdb_timeline() itself.

    Returns None (not a dict) if anything about this lookup fails, or we
    can't confidently match it to the right event -- callers must treat
    None as "no enrichment available this time" and carry on without it,
    never as an error worth stopping for.
    """
    match_date = match.get("utcDate", "")[:10]  # "2026-09-13T12:00:00Z" -> "2026-09-13"
    if not match_date:
        return None

    base_url = f"https://www.thesportsdb.com/api/v1/json/{api_key}"

    try:
        response = requests.get(
            f"{base_url}/eventslast.php",
            params={"id": thesportsdb_team_id},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        events = response.json().get("results") or []
    except (requests.exceptions.RequestException, ValueError) as error:
        print(f"WARNING: TheSportsDB lookup failed, posting without extra detail: {error}")
        return None

    # Find the event that's actually the same match: same calendar date.
    # (football-data.org and TheSportsDB use different ids for the same
    # real-world match, so date is our simplest reliable correlation key --
    # a team can't play two matches on the same day.)
    matching_event = next((e for e in events if e.get("dateEvent") == match_date), None)
    if matching_event is None:
        print(f"WARNING: no TheSportsDB event found for {match_date}, posting without extra detail.")
        return None

    return _fetch_thesportsdb_timeline(matching_event.get("idEvent"), thesportsdb_team_id, api_key)


def fetch_thesportsdb_latest_event(thesportsdb_team_id, api_key):
    """
    Ask TheSportsDB for Celta's single most recent event, in ANY
    competition, via eventslast.php -- the one free-test-key endpoint
    confirmed to return live, unrestricted data for a specific team (its
    bulk season-listing endpoints are heavily sample-limited on the free
    key, so they can't be used to browse a whole competition's history --
    but this bot only ever needs "what was Celta's last finished match",
    which this endpoint answers directly).

    Returns the raw event dict, or None if the request failed or returned
    nothing.
    """
    base_url = f"https://www.thesportsdb.com/api/v1/json/{api_key}"
    try:
        response = requests.get(
            f"{base_url}/eventslast.php",
            params={"id": thesportsdb_team_id},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
    except (requests.exceptions.RequestException, ValueError) as error:
        print(f"WARNING: TheSportsDB latest-event lookup failed: {error}")
        return None
    return results[0] if results else None


def _derive_half_time_from_goals(goals, celta_ft, opponent_ft, celta_is_home):
    """
    Reconstruct the half-time score by counting timeline goals scored by
    minute 45, for matches that only have TheSportsDB data (no
    football-data.org half-time score to use directly -- see
    build_thesportsdb_match()).

    Only trusted if the timeline's own goal count adds up to the real
    final score -- the same safety check _classify_late_drama() uses,
    since TheSportsDB's timeline is volunteer-maintained and can be
    missing a goal. If they don't match, we can't tell which goals
    happened before half-time, so this returns None and classify_match()
    falls back to its non-half-time categories, exactly as if
    football-data.org just hadn't given us a half-time score either.
    """
    if not goals:
        return None

    celta_goal_count = sum(1 for g in goals if g["celta_scored"])
    opponent_goal_count = len(goals) - celta_goal_count
    if celta_goal_count != celta_ft or opponent_goal_count != opponent_ft:
        return None

    home_ht = sum(1 for g in goals if g["minute"] <= 45 and g["celta_scored"] == celta_is_home)
    away_ht = sum(1 for g in goals if g["minute"] <= 45 and g["celta_scored"] != celta_is_home)
    return {"home": home_ht, "away": away_ht}


def build_thesportsdb_match(event, thesportsdb_team_id, goals):
    """
    Turn a raw TheSportsDB event (from fetch_thesportsdb_latest_event())
    into a match dict shaped just like a football-data.org one -- id,
    homeTeam/awayTeam with ids and names, score.fullTime, score.halfTime,
    competition.name -- so classify_match() and build_message() can be
    reused completely unchanged for competitions football-data.org's free
    tier doesn't cover (Copa del Rey, Europa League, ...).

    Half-time score is derived from `goals` (see
    _derive_half_time_from_goals()) when available and trustworthy;
    otherwise it's left as None, same as a football-data.org match that's
    simply missing that field.

    Known limitation: extra-time/penalty-shootout knockout results aren't
    specially handled -- this uses TheSportsDB's regulation-time score
    (intHomeScore/intAwayScore) for classification like any other match,
    since we haven't confirmed how TheSportsDB represents a penalty
    shootout on the free tier. Worth revisiting if this bot needs to cover
    a Copa del Rey tie that goes to penalties.
    """
    team_id = int(thesportsdb_team_id)
    home_id = int(event.get("idHomeTeam") or 0)
    away_id = int(event.get("idAwayTeam") or 0)
    home_score = int(event.get("intHomeScore") or 0)
    away_score = int(event.get("intAwayScore") or 0)
    celta_is_home = home_id == team_id

    celta_ft = home_score if celta_is_home else away_score
    opponent_ft = away_score if celta_is_home else home_score
    half_time = _derive_half_time_from_goals(goals, celta_ft, opponent_ft, celta_is_home)

    return {
        "id": f"tsdb-{event.get('idEvent')}",
        "utcDate": event.get("strTimestamp") or f"{event.get('dateEvent', '')}T00:00:00Z",
        "homeTeam": {"id": home_id, "name": event.get("strHomeTeam", "o rival")},
        "awayTeam": {"id": away_id, "name": event.get("strAwayTeam", "o rival")},
        "score": {
            "fullTime": {"home": home_score, "away": away_score},
            "halfTime": half_time,
        },
        "competition": {"name": event.get("strLeague", "")},
    }


def _classify_late_drama(goals, celta_ft, opponent_ft):
    """
    Look at the very last goal of the match: if it was scored at or after
    LATE_GOAL_MINUTE and it's what actually decided the final result (i.e.
    the score was level or worse for Celta immediately before it), return
    the matching WIN_LATE/DRAW_LATE/LOSS_LATE category. Otherwise return
    None, so classify_match() falls back to its normal half-time/full-time
    categories -- e.g. a late goal that just padded an already-safe lead
    doesn't count as "late drama".

    TheSportsDB's timeline data is volunteer-maintained and can be
    incomplete -- we've seen a real match where one team's goal was simply
    missing from it. If the goals list's own counts don't add up to the
    real final score, we can't trust which goal was really "last", so we
    bail out here rather than risk a wrong late-drama call; classify_match()
    then falls back to the half-time/full-time categories instead.
    """
    celta_goal_count = sum(1 for g in goals if g["celta_scored"])
    opponent_goal_count = len(goals) - celta_goal_count
    if celta_goal_count != celta_ft or opponent_goal_count != opponent_ft:
        return None

    last_goal = goals[-1]
    if last_goal["minute"] < LATE_GOAL_MINUTE:
        return None

    # Score margin (from Celta's perspective) just before that last goal.
    margin = celta_ft - opponent_ft
    margin_before_last_goal = margin - (1 if last_goal["celta_scored"] else -1)

    if margin > 0 and last_goal["celta_scored"] and margin_before_last_goal <= 0:
        return "WIN_LATE"
    if margin == 0 and last_goal["celta_scored"] and margin_before_last_goal < 0:
        return "DRAW_LATE"
    if margin < 0 and not last_goal["celta_scored"] and margin_before_last_goal >= 0:
        return "LOSS_LATE"
    return None


def _classify_ten_men(red_cards, margin):
    """
    If Celta had a player sent off and the opponent did not (so this is
    specifically about playing a man down, not a chaotic match with cards
    both ways), return WIN_TEN_MEN or LOSS_TEN_MEN. A draw with a red card
    doesn't get its own category -- it falls back to the normal draw
    categories -- to keep this to the two clearly notable cases.
    """
    celta_sent_off = any(c["celta"] for c in red_cards)
    opponent_sent_off = any(not c["celta"] for c in red_cards)
    if not celta_sent_off or opponent_sent_off:
        return None
    if margin > 0:
        return "WIN_TEN_MEN"
    if margin < 0:
        return "LOSS_TEN_MEN"
    return None


def _celta_full_time_score(match, team_id):
    """
    Return (celta_ft, opponent_ft) -- Celta's and the opponent's full-time
    goals -- from Celta's perspective, handling both home and away
    matches. Shared by classify_match() and select_category() (via
    _match_outcome()) so both agree on the same win/draw/loss reading of
    a match without duplicating the home/away lookup.
    """
    team_id = int(team_id)
    home_team = match["homeTeam"]
    full_time = match["score"]["fullTime"]
    celta_is_home = home_team.get("id") == team_id
    if celta_is_home:
        return full_time.get("home"), full_time.get("away")
    return full_time.get("away"), full_time.get("home")


def _match_outcome(margin):
    """Return "WIN", "DRAW", or "LOSS" for a Celta full-time goal margin."""
    if margin > 0:
        return "WIN"
    if margin < 0:
        return "LOSS"
    return "DRAW"


def classify_match(match, team_id, goals=None, red_cards=None):
    """
    Work out not just WIN/DRAW/LOSS but the *shape* of the match from
    Celta's point of view, by comparing the half-time score to the
    full-time score. Handles both home and away matches. Returns one of
    the category keys in phrases.PHRASES, e.g. "WIN_COMEBACK",
    "LOSS_BLOWOUT", "DRAW_FLAT".

    This only looks at THIS match -- see select_category() for how its
    result gets combined with competition-level context (win/loss
    streaks, cup advancement) into the category actually used.

    football-data.org's free tier doesn't give us minute-by-minute goal
    data, so on its own we can't detect things like a last-minute winner --
    half-time vs full-time is enough to tell a comeback from a collapse
    from a routine result, though. If `goals` and/or `red_cards` are
    provided (from fetch_thesportsdb_match_events()), we additionally
    check for WIN_LATE/DRAW_LATE/LOSS_LATE (see _classify_late_drama()) and
    WIN_TEN_MEN/LOSS_TEN_MEN (see _classify_ten_men()), checked in that
    order since a late goal is usually the more immediate story even in a
    match also played with ten men. Leave both as None (the default) to
    classify using only half-time/full-time, exactly as before.
    """
    team_id = int(team_id)
    home_team = match["homeTeam"]
    half_time = match["score"].get("halfTime") or {}

    celta_ft, opponent_ft = _celta_full_time_score(match, team_id)
    celta_is_home = home_team.get("id") == team_id
    if celta_is_home:
        celta_ht, opponent_ht = half_time.get("home"), half_time.get("away")
    else:
        celta_ht, opponent_ht = half_time.get("away"), half_time.get("home")

    margin = celta_ft - opponent_ft

    if goals:
        late_category = _classify_late_drama(goals, celta_ft, opponent_ft)
        if late_category:
            return late_category

    if red_cards:
        ten_men_category = _classify_ten_men(red_cards, margin)
        if ten_men_category:
            return ten_men_category

    # Half-time scores are normally present, but guard against them being
    # missing (e.g. incomplete data) -- if so, we just can't tell a
    # comeback/collapse/rally/squandered-lead story and fall back to the
    # plain result-based categories below.
    half_time_known = celta_ht is not None and opponent_ht is not None

    if margin > 0:  # WIN
        if half_time_known and celta_ht < opponent_ht:
            return "WIN_COMEBACK"
        if margin >= 3:
            return "WIN_BLOWOUT"
        if margin == 1:
            return "WIN_NARROW"
        return "WIN_STANDARD"

    if margin < 0:  # LOSS
        if half_time_known and celta_ht > opponent_ht:
            return "LOSS_COLLAPSE"
        if margin <= -3:
            return "LOSS_BLOWOUT"
        if margin == -1:
            return "LOSS_NARROW"
        return "LOSS_STANDARD"

    # DRAW
    if half_time_known and celta_ht < opponent_ht:
        return "DRAW_RALLY"
    if half_time_known and celta_ht > opponent_ht:
        return "DRAW_SQUANDERED"
    return "DRAW_FLAT"


# Competitions where a single win always means advancing to the next round,
# so select_category() can confidently override to WIN_ADVANCED_ROUND.
# Spain's Copa del Rey has been straight single-match knockout (no
# two-legged ties, no replays) since the 2019-20 format change, so a win
# there unambiguously means advancing. The Europa League is NOT included --
# it mixes a multi-matchday league phase (a single win/loss there doesn't
# decide anything by itself) with mostly two-legged knockout rounds (a
# single-leg win doesn't guarantee the aggregate tie), and TheSportsDB's
# free-tier event data doesn't reliably tell us which phase/leg a given
# match was -- confirmed live: the Sept 2026 Omonia Nicosia match came back
# with "intRound": "1", which is a league-phase matchday number here, not a
# knockout round. Guessing "advanced" anyway risks posting something
# false, so this stays unhandled until there's a reliable way to tell.
COMPETITIONS_WHERE_WIN_MEANS_ADVANCING = {"Copa del Rey"}


def _update_streak(state, competition_key, outcome):
    """
    Update state["streaks"][competition_key] with this new result and
    return the resulting streak length for `outcome`.

    Only WIN and LOSS chains are tracked -- a DRAW (or a different
    outcome than whatever streak was running) resets the streak back to
    1 for the new outcome, or clears it out on a draw. Mutates `state` in
    place; callers are responsible for calling save_state() afterwards
    (same shared-state convention as check_la_liga_result()/
    check_other_competitions_result() use for their own match/event id
    keys -- see CLAUDE.md).

    Returns the new streak length (always 1 right after a DRAW, or after
    a WIN following a LOSS and vice versa) -- callers only act on this
    when `outcome` is WIN or LOSS and the returned count is >= 2.
    """
    streaks = state.setdefault("streaks", {})
    current = streaks.get(competition_key)

    if current and current.get("outcome") == outcome:
        new_count = current["count"] + 1
    else:
        new_count = 1

    streaks[competition_key] = {"outcome": outcome, "count": new_count}
    return new_count


def select_category(match, team_id, goals, red_cards, competition_key, state):
    """
    Decide which phrases.py category this result should actually use.
    Wraps classify_match() (the *shape of this one match* -- comeback,
    blowout, late, ten-men, etc.) with two competition-level overrides,
    checked in this order:

      1. Cup advancement: in a competition from
         COMPETITIONS_WHERE_WIN_MEANS_ADVANCING (currently just Copa del
         Rey), a win always becomes WIN_ADVANCED_ROUND -- advancing (or
         not) is bigger news than whether this particular win was a
         comeback or a blowout, and it's true every single time, so it
         takes over regardless of the match's own shape.
      2. Win/loss streaks: WIN_STREAK_2/3 or LOSS_STREAK_2/3 replace
         WIN_STANDARD/LOSS_STANDARD specifically -- i.e. only when
         classify_match() found no more specific story of its own (not a
         comeback, blowout, ten-men, or late-drama result). A comeback
         win that also happens to be the 3rd in a row still reads as
         WIN_COMEBACK; a bog-standard 1-0 win that's the 3rd in a row
         reads as WIN_STREAK_3 instead of the blander WIN_STANDARD.
         (This never actually fires for Copa del Rey wins in practice,
         since rule 1 above already claims every one of those -- and a
         Copa del Rey LOSS ends the run in that competition, so there's
         never a same-competition loss streak to track there either.)

    `competition_key` identifies the competition for streak-tracking
    purposes (e.g. "La Liga", "UEFA Champions League", "Copa del Rey",
    whatever TheSportsDB calls it) -- see COMPETITION_NAMES_BY_CODE for
    check_la_liga_result()'s case and `strLeague` for check_other_
    competitions_result()'s.

    Always calls _update_streak() (mutating `state` in place) even when
    its result isn't used for this category, so the streak count itself
    stays accurate for next time. Callers must save `state` afterwards
    exactly as they already do for their own match/event id key.
    """
    base_category = classify_match(match, team_id, goals, red_cards)

    celta_ft, opponent_ft = _celta_full_time_score(match, team_id)
    outcome = _match_outcome(celta_ft - opponent_ft)
    streak_count = _update_streak(state, competition_key, outcome)

    if outcome == "WIN" and competition_key in COMPETITIONS_WHERE_WIN_MEANS_ADVANCING:
        return "WIN_ADVANCED_ROUND"

    if base_category == "WIN_STANDARD" and streak_count >= 2:
        return "WIN_STREAK_3" if streak_count >= 3 else "WIN_STREAK_2"
    if base_category == "LOSS_STANDARD" and streak_count >= 2:
        return "LOSS_STREAK_3" if streak_count >= 3 else "LOSS_STREAK_2"

    return base_category


def _format_celta_scorers(goals):
    """
    Build a short Galician clause naming Celta's scorer(s) and the
    minute(s) each of their goals went in. Goals are grouped by player so
    a brace/hat-trick reads as one clause -- e.g. "marcou Iago Aspas
    (min. 23, min. 80)" -- instead of repeating the name. For more than
    one scorer: "marcaron Iago Aspas (min. 23) e Ferran Jutglà (min. 78)".
    Returns "" (nothing to add) if there's no goal data or Celta didn't
    score.
    """
    if not goals:
        return ""

    celta_goals = [g for g in goals if g["celta_scored"]]
    if not celta_goals:
        return ""

    minutes_by_scorer = {}
    scorer_order = []
    for g in celta_goals:
        if g["scorer"] not in minutes_by_scorer:
            minutes_by_scorer[g["scorer"]] = []
            scorer_order.append(g["scorer"])
        minutes_by_scorer[g["scorer"]].append(g["minute"])

    def describe(scorer):
        minutes = ", ".join(f"min. {m}" for m in minutes_by_scorer[scorer])
        return f"{scorer} ({minutes})"

    if len(scorer_order) == 1:
        return f"marcou {describe(scorer_order[0])}"

    parts = [describe(s) for s in scorer_order]
    return "marcaron " + ", ".join(parts[:-1]) + " e " + parts[-1]


def _find_star_performer(goals):
    """
    Look for a Celta player involved in 2+ goal contributions this match
    (their own goals plus assists they gave for other Celta goals), and
    return (name, contribution_count) for whoever has the most, or None if
    nobody reaches that bar.

    This is the most honest signal our data can support for "who had a
    great match" -- there's no official man-of-the-match or player-rating
    data on the free tier (checked), so this only recognizes goal
    involvement, not e.g. a strong performance with no goal or assist.
    """
    if not goals:
        return None

    contributions = {}
    for g in goals:
        if not g["celta_scored"]:
            continue
        contributions[g["scorer"]] = contributions.get(g["scorer"], 0) + 1
        assist = g.get("assist")
        if assist:
            contributions[assist] = contributions.get(assist, 0) + 1

    if not contributions:
        return None

    name, count = max(contributions.items(), key=lambda item: item[1])
    return (name, count) if count >= 2 else None


def build_message(match, team_id, goals=None, red_cards=None, category_override=None):
    """
    Build the full text we're going to post to Telegram, e.g.:
    "Ben, Celta, ben! Partido gañado con mérito! Celta 2-1 Getafe"

    The message never mentions which competition the match was -- it's
    the same phrase-and-score format no matter what (La Liga, Copa del
    Rey, whatever); only the *content* of the phrase itself changes
    (see category_override below).

    Teams are always shown in actual home-away order (Celta first when
    playing at home, second when playing away) so the score reads the
    same way it would on a scoreboard -- e.g. "Getafe 1-1 Celta" for an
    away draw, not "Celta 1-1 Getafe".

    If `goals`/`red_cards` are provided (from
    fetch_thesportsdb_match_events()), they're used both to pick a more
    specific category (see classify_match()) and to add extra detail to
    the message: Celta's scorer(s) in parentheses, plus a follow-up
    sentence naming a standout player if anyone had 2+ goal contributions
    (goals + assists) -- see _find_star_performer(). E.g.:
    "... Celta 2-1 Getafe (marcou Iago Aspas (min. 23, min. 80)). Iago Aspas leva 2 accións de gol hoxe!"
    Leave both as None (the default) to build the message exactly as
    before, with no extra detail.

    By default the category comes from classify_match() (the *shape of
    this match* -- comeback, blowout, etc.), same as always. Pass
    `category_override` (from select_category(), which additionally
    knows about win/loss streaks and cup advancement -- see its
    docstring) to use that category instead. check_la_liga_result() and
    check_other_competitions_result() always pass one in; only
    run_test_message()'s base-16-category fake matches rely on the
    default.
    """
    team_id = int(team_id)
    home_team = match["homeTeam"]
    away_team = match["awayTeam"]
    full_time = match["score"]["fullTime"]

    celta_is_home = home_team.get("id") == team_id
    home_name = "Celta" if celta_is_home else home_team.get("name", "o rival")
    away_name = away_team.get("name", "o rival") if celta_is_home else "Celta"

    category = category_override or classify_match(match, team_id, goals, red_cards)
    phrase = get_random_phrase(category)

    result_line = f"{phrase} {home_name} {full_time.get('home')}-{full_time.get('away')} {away_name}"

    scorers_note = _format_celta_scorers(goals)
    if scorers_note:
        result_line = f"{result_line} ({scorers_note})"

    star = _find_star_performer(goals)
    if star:
        name, count = star
        result_line = f"{result_line}. {name} leva {count} accións de gol hoxe!"

    return result_line


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


# A few made-up matches used only for --test-telegram, one per category (see
# classify_match() above), so a test run can show what each kind of message
# actually looks like with a real (randomly picked) phrase from phrases.py.
# These are never sent to football-data.org or TheSportsDB, or compared
# against real results -- purely fake data, but each one's scores (and, for
# some, "goals"/"red_cards" timeline) are deliberately chosen to land in a
# specific category. Each entry is {"match": <football-data.org-shaped
# dict>, "goals": <goals list, or None>, "red_cards": <red cards list, or
# None>} -- both shaped like fetch_thesportsdb_match_events()'s return
# value -- so run_test_message() can exercise both the plain and
# TheSportsDB-enriched code paths.
FAKE_TEST_MATCHES = [
    {  # WIN_COMEBACK: Celta home, down 0-1 at half, won 2-1 -- also shows
       # a brace (both goals by Aspas) with an assist on the second, which
       # triggers the star-performer callout (2+ goal contributions).
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 601, "name": "Getafe CF"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 2, "away": 1},
                "halfTime": {"home": 0, "away": 1},
            },
        },
        "goals": [
            {"minute": 50, "scorer": "Iago Aspas", "celta_scored": True, "assist": None},
            {"minute": 80, "scorer": "Iago Aspas", "celta_scored": True, "assist": "Fran Beltrán"},
        ],
        "red_cards": None,
    },
    {  # WIN_BLOWOUT: Celta away, already ahead 0-2 at half, won 1-4
        "match": {
            "homeTeam": {"id": 602, "name": "Athletic Club"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 1, "away": 4},
                "halfTime": {"home": 0, "away": 2},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # WIN_NARROW: Celta home, 0-0 at half, won 1-0 -- also shows a
       # scorer note attached to a non-late category (min. 63 is well
       # before LATE_GOAL_MINUTE, so this does NOT become WIN_LATE).
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 603, "name": "Real Madrid CF"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 1, "away": 0},
                "halfTime": {"home": 0, "away": 0},
            },
        },
        "goals": [{"minute": 63, "scorer": "Borja Iglesias", "celta_scored": True, "assist": None}],
        "red_cards": None,
    },
    {  # WIN_STANDARD: Celta away, already ahead 0-1 at half, won 1-3
        "match": {
            "homeTeam": {"id": 604, "name": "Real Valladolid CF"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 1, "away": 3},
                "halfTime": {"home": 0, "away": 1},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # WIN_LATE: Celta home, level 0-0 all match until a single goal in
       # minute 90 wins it -- overrides what would otherwise be WIN_NARROW.
        "match": {
            "homeTeam": {"id": 612, "name": "Girona FC"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 0, "away": 1},
                "halfTime": {"home": 0, "away": 0},
            },
        },
        "goals": [{"minute": 90, "scorer": "Iago Aspas", "celta_scored": True, "assist": None}],
        "red_cards": None,
    },
    {  # WIN_TEN_MEN: Celta home, a Celta player sent off at minute 35, but
       # still won 2-0 -- overrides what would otherwise be WIN_STANDARD.
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 615, "name": "CD Mirandés"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 2, "away": 0},
                "halfTime": {"home": 1, "away": 0},
            },
        },
        "goals": None,
        "red_cards": [{"minute": 35, "player": "Marcos Alonso", "celta": True}],
    },
    {  # DRAW_RALLY: Celta away, down 2-0 at half, rallied to 2-2
        "match": {
            "homeTeam": {"id": 605, "name": "Deportivo Alavés"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "DRAW",
                "fullTime": {"home": 2, "away": 2},
                "halfTime": {"home": 2, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # DRAW_SQUANDERED: Celta home, ahead 1-0 at half, only drew 1-1
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 606, "name": "Rayo Vallecano"},
            "score": {
                "winner": "DRAW",
                "fullTime": {"home": 1, "away": 1},
                "halfTime": {"home": 1, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # DRAW_FLAT: Celta home, 0-0 at half, 1-1 at full-time
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 607, "name": "Sevilla FC"},
            "score": {
                "winner": "DRAW",
                "fullTime": {"home": 1, "away": 1},
                "halfTime": {"home": 0, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # DRAW_LATE: Celta away, down 0-1 since minute 30, equalizes at
       # minute 90 -- overrides what would otherwise be DRAW_RALLY.
        "match": {
            "homeTeam": {"id": 613, "name": "CD Leganés"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "DRAW",
                "fullTime": {"home": 1, "away": 1},
                "halfTime": {"home": 1, "away": 0},
            },
        },
        "goals": [
            {"minute": 30, "scorer": "Rival Player", "celta_scored": False, "assist": None},
            {"minute": 90, "scorer": "Fran Beltrán", "celta_scored": True, "assist": None},
        ],
        "red_cards": None,
    },
    {  # LOSS_COLLAPSE: Celta home, ahead 2-0 at half, lost 2-3
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 608, "name": "Real Sociedad"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 2, "away": 3},
                "halfTime": {"home": 2, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # LOSS_BLOWOUT: Celta away, down 1-0 at half, lost 4-0
        "match": {
            "homeTeam": {"id": 609, "name": "RCD Espanyol"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 4, "away": 0},
                "halfTime": {"home": 1, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # LOSS_NARROW: Celta home, 0-0 at half, lost 1-2
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 610, "name": "Villarreal CF"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 1, "away": 2},
                "halfTime": {"home": 0, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # LOSS_STANDARD: Celta away, down 1-0 at half, lost 3-1
        "match": {
            "homeTeam": {"id": 611, "name": "CA Osasuna"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 3, "away": 1},
                "halfTime": {"home": 1, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
    },
    {  # LOSS_LATE: Celta home, led 1-0 then conceded twice, the second
       # (deciding) goal at minute 90 -- overrides what would otherwise be
       # LOSS_NARROW.
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 614, "name": "UD Las Palmas"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 1, "away": 2},
                "halfTime": {"home": 1, "away": 0},
            },
        },
        "goals": [
            {"minute": 30, "scorer": "Williot Swedberg", "celta_scored": True, "assist": None},
            {"minute": 60, "scorer": "Rival Player", "celta_scored": False, "assist": None},
            {"minute": 90, "scorer": "Rival Player 2", "celta_scored": False, "assist": None},
        ],
        "red_cards": None,
    },
    {  # LOSS_TEN_MEN: Celta away, a Celta player sent off at minute 50,
       # lost 0-1 -- overrides what would otherwise be LOSS_NARROW.
        "match": {
            "homeTeam": {"id": 616, "name": "UD Almería"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 1, "away": 0},
                "halfTime": {"home": 0, "away": 0},
            },
        },
        "goals": None,
        "red_cards": [{"minute": 50, "player": "Carl Starfelt", "celta": True}],
    },
    {  # WIN_STREAK_2: select_category() decides this from a win/loss
       # history main.py doesn't have in test mode, so it's forced here via
       # "category_override" instead of being inferred from the match itself
       # (same underlying match shape as WIN_NARROW).
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 617, "name": "SD Ponferradina"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 1, "away": 0},
                "halfTime": {"home": 0, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
        "category_override": "WIN_STREAK_2",
    },
    {  # WIN_STREAK_3
        "match": {
            "homeTeam": {"id": 619, "name": "CD Eldense"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 0, "away": 2},
                "halfTime": {"home": 0, "away": 1},
            },
        },
        "goals": None,
        "red_cards": None,
        "category_override": "WIN_STREAK_3",
    },
    {  # WIN_ADVANCED_ROUND: a Copa del Rey win, which always means
       # advancing in the current single-match format -- see
       # COMPETITIONS_WHERE_WIN_MEANS_ADVANCING.
        "match": {
            "homeTeam": {"id": 620, "name": "Real Avilés"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 0, "away": 1},
                "halfTime": {"home": 0, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
        "category_override": "WIN_ADVANCED_ROUND",
    },
    {  # LOSS_STREAK_2
        "match": {
            "homeTeam": {"id": 618, "name": "Bayern Munich"},
            "awayTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "score": {
                "winner": "HOME_TEAM",
                "fullTime": {"home": 3, "away": 1},
                "halfTime": {"home": 1, "away": 0},
            },
        },
        "goals": None,
        "red_cards": None,
        "category_override": "LOSS_STREAK_2",
    },
    {  # LOSS_STREAK_3
        "match": {
            "homeTeam": {"id": 558, "name": "RC Celta de Vigo"},
            "awayTeam": {"id": 621, "name": "Paris Saint-Germain"},
            "score": {
                "winner": "AWAY_TEAM",
                "fullTime": {"home": 0, "away": 2},
                "halfTime": {"home": 0, "away": 1},
            },
        },
        "goals": None,
        "red_cards": None,
        "category_override": "LOSS_STREAK_3",
    },
]


def run_test_message():
    """
    Send a sample result message -- a random category (comeback, blowout,
    narrow win, etc. -- see classify_match()) with a real, randomly-picked
    phrase from phrases.py -- to every configured Telegram channel, without
    touching football-data.org or state.json at all.

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

    fake_entry = random.choice(FAKE_TEST_MATCHES)
    message = build_message(
        fake_entry["match"],
        DEFAULT_CELTA_TEAM_ID,
        fake_entry["goals"],
        fake_entry["red_cards"],
        fake_entry.get("category_override"),
    )

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
# The two independent checks
# ---------------------------------------------------------------------------

def check_la_liga_result(
    state, football_api_key, celta_team_id, thesportsdb_team_id, thesportsdb_api_key,
    telegram_token, telegram_channel_ids,
):
    """
    Check football-data.org for a new finished La Liga/Champions League
    match and post it if there is one. This is the original core flow --
    see check_other_competitions_result() below for the newer path that
    covers everything football-data.org's free tier can't (Copa del Rey,
    Europa League, ...) via TheSportsDB instead.

    Mutates `state` in place and saves it (via save_state(state), never a
    fresh dict) whenever `last_processed_match_id` changes, so we never
    wipe out check_other_competitions_result()'s own key in the same file.

    Returns True only if a genuinely new result failed to reach every
    Telegram channel (so main() can still exit non-zero to flag the
    failure), False otherwise -- including "nothing new to post".
    """
    matches = fetch_recent_matches(football_api_key, celta_team_id)
    if not matches:
        # Either an API error (already logged above) or genuinely no
        # finished matches yet. Either way, there's nothing more to do.
        print("No finished La Liga/Champions League matches to process this run.")
        return False

    latest_match = matches[0]
    latest_match_id = latest_match["id"]
    last_processed_id = state.get("last_processed_match_id")

    # First-run bootstrap: if we have no prior state at all, don't post
    # about a match that may have finished long before the bot existed.
    # Just remember it as "already seen" and start posting from the next
    # new result onwards.
    if last_processed_id is None:
        print(
            f"First run detected. Recording match {latest_match_id} as the "
            "starting point without posting (to avoid posting an old result)."
        )
        state["last_processed_match_id"] = latest_match_id
        save_state(state)
        return False

    # If the latest finished match is one we've already posted, there's
    # nothing new to do.
    if latest_match_id == last_processed_id:
        print("Latest finished La Liga/Champions League match has already been posted. Nothing to do.")
        return False

    # We have a new result! Try to enrich it with scorer/assist/red-card
    # data from TheSportsDB -- if this fails or doesn't find a match,
    # events is None and build_message() just posts without that extra
    # detail. This never blocks posting the core result.
    events = fetch_thesportsdb_match_events(latest_match, thesportsdb_team_id, thesportsdb_api_key)
    goals = events["goals"] if events else None
    red_cards = events["red_cards"] if events else None

    # Work out the final category -- classify_match()'s match-shape
    # categories (comeback, blowout, ...), possibly overridden by a
    # win/loss streak (see select_category()). Champions League never
    # gets the cup-advancement override (COMPETITIONS_WHERE_WIN_MEANS_ADVANCING
    # doesn't include it), only Copa del Rey does.
    competition_key = COMPETITION_NAMES_BY_CODE.get(
        latest_match.get("competition", {}).get("code"), "La Liga"
    )
    category = select_category(latest_match, celta_team_id, goals, red_cards, competition_key, state)

    # Build the message and post it to every configured channel. We try
    # all of them even if one fails, so a single broken channel doesn't
    # stop the others from getting posted.
    message = build_message(latest_match, celta_team_id, goals, red_cards, category)
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
        return True

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

    # Success (at least partially)! Remember this match so we don't post
    # it again to the channels that already received it.
    state["last_processed_match_id"] = latest_match_id
    save_state(state)
    print("Done with La Liga/Champions League check.")
    return False


def check_other_competitions_result(
    state, thesportsdb_team_id, thesportsdb_api_key, telegram_token, telegram_channel_ids,
):
    """
    Check TheSportsDB directly for Celta's actual latest finished match in
    ANY competition, and post it if it's new and NOT already covered by
    check_la_liga_result() -- this is how the bot covers Copa del Rey, the
    Europa League, the Conference League, etc., which football-data.org's
    free tier doesn't include at all (only La Liga and the Champions League
    do -- see COMPETITION_CODES above).

    Mutates `state` in place, using different keys
    (`last_processed_thesportsdb_event_id` + `last_processed_thesportsdb_
    event_date`) than check_la_liga_result()'s `last_processed_match_id`,
    so the two checks track their own progress independently in the same
    state.json without clobbering each other. The date is stored
    alongside the id so a stale/out-of-order response from
    eventslast.php can't regress state backwards -- see the date check
    below.

    Returns True only if a genuinely new, postable result failed to reach
    every Telegram channel (so main() can still exit non-zero), False
    otherwise -- including "nothing new" or "it was actually a La
    Liga/Champions League match, already handled above".
    """
    latest_event = fetch_thesportsdb_latest_event(thesportsdb_team_id, thesportsdb_api_key)
    if not latest_event:
        print("No TheSportsDB event data available this run.")
        return False

    if latest_event.get("strStatus") != "FT":
        print("Celta's most recent TheSportsDB event isn't finished yet.")
        return False

    event_id = latest_event.get("idEvent")
    event_date = latest_event.get("dateEvent") or ""
    last_seen_event_id = state.get("last_processed_thesportsdb_event_id")
    last_seen_event_date = state.get("last_processed_thesportsdb_event_date") or ""

    # First-run bootstrap, same reasoning as check_la_liga_result(): don't
    # post about a match that may have finished long before this check
    # existed, just record it as the starting point.
    if last_seen_event_id is None:
        print(
            f"First run detected for TheSportsDB tracking. Recording event {event_id} "
            "as the starting point without posting."
        )
        state["last_processed_thesportsdb_event_id"] = event_id
        state["last_processed_thesportsdb_event_date"] = event_date
        save_state(state)
        return False

    if event_id == last_seen_event_id:
        print("Latest TheSportsDB event has already been processed. Nothing to do.")
        return False

    # eventslast.php isn't reliably monotonic -- confirmed live on
    # 2026-09-16: hours after it had shown a newer Europa League match
    # (which we'd already processed), it reverted to showing the older La
    # Liga match again. A different id here doesn't necessarily mean a
    # genuinely new result -- only trust it if its date is actually after
    # what we've already processed, so a stale/lagging response can't
    # regress our state backwards (which would make us think a real,
    # already-posted result is "new" again on some future run, and
    # re-post it).
    if event_date and last_seen_event_date and event_date <= last_seen_event_date:
        print(
            f"TheSportsDB's latest event ({event_id}, {event_date}) isn't newer than what "
            f"we've already processed ({last_seen_event_id}, {last_seen_event_date}) -- "
            "ignoring as likely stale/lagging data. Will check again next run."
        )
        return False

    if latest_event.get("idLeague") in THESPORTSDB_LEAGUES_COVERED_BY_FOOTBALL_DATA:
        # This is a La Liga/Champions League match -- check_la_liga_result()
        # already handles (or will handle) it, with richer half-time data
        # straight from football-data.org. Just mark it as seen here so we
        # don't keep re-detecting it as "new" on every future run.
        print(
            f"Latest TheSportsDB event ({event_id}) is a La Liga/Champions League "
            "match -- already handled by the football-data.org check. Marking as seen."
        )
        state["last_processed_thesportsdb_event_id"] = event_id
        state["last_processed_thesportsdb_event_date"] = event_date
        save_state(state)
        return False

    competition_key = latest_event.get("strLeague") or "outra competición"
    print(f"New result detected via TheSportsDB: {competition_key}.")

    timeline = _fetch_thesportsdb_timeline(event_id, thesportsdb_team_id, thesportsdb_api_key)
    goals = timeline["goals"] if timeline else None
    red_cards = timeline["red_cards"] if timeline else None

    synthetic_match = build_thesportsdb_match(latest_event, thesportsdb_team_id, goals)
    category = select_category(synthetic_match, thesportsdb_team_id, goals, red_cards, competition_key, state)
    message = build_message(synthetic_match, thesportsdb_team_id, goals, red_cards, category)
    print(f"Posting new result: {message}")

    successes = 0
    for channel_id in telegram_channel_ids:
        if send_telegram_message(telegram_token, channel_id, message):
            successes += 1
        else:
            print(f"Failed to send to channel '{channel_id}'.")

    if successes == 0:
        print("Failed to send to any channel. Will retry next run.")
        return True

    if successes < len(telegram_channel_ids):
        print(
            f"WARNING: only {successes}/{len(telegram_channel_ids)} channels "
            "received this message. Check the errors above."
        )

    state["last_processed_thesportsdb_event_id"] = event_id
    state["last_processed_thesportsdb_event_date"] = event_date
    save_state(state)
    print("Done with other-competitions check.")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Special test mode: "python main.py --test-telegram" only exercises
    # the Telegram-sending part, skipping football-data.org, TheSportsDB,
    # and state.json entirely. See run_test_message() above for details.
    if "--test-telegram" in sys.argv:
        run_test_message()
        return

    # Load required configuration from environment variables / secrets.
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
    # Same "or" pattern for the optional TheSportsDB config -- neither of
    # these is a secret, both have working free defaults (see their
    # DEFAULT_* constants above).
    thesportsdb_team_id = os.environ.get("THESPORTSDB_TEAM_ID") or DEFAULT_THESPORTSDB_TEAM_ID
    thesportsdb_api_key = os.environ.get("THESPORTSDB_API_KEY") or DEFAULT_THESPORTSDB_API_KEY

    # Load what we last posted about (shared by both checks below, each
    # using its own key -- see their docstrings).
    state = load_state()

    la_liga_failed = check_la_liga_result(
        state, football_api_key, celta_team_id, thesportsdb_team_id, thesportsdb_api_key,
        telegram_token, telegram_channel_ids,
    )
    other_failed = check_other_competitions_result(
        state, thesportsdb_team_id, thesportsdb_api_key, telegram_token, telegram_channel_ids,
    )

    if la_liga_failed or other_failed:
        # At least one check found a genuinely new result that failed to
        # reach every channel -- exit non-zero so the scheduled workflow
        # shows as failed and it's easy to notice.
        sys.exit(1)


if __name__ == "__main__":
    main()
