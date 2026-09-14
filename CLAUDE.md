# Manel Bot

A Telegram bot that posts a message whenever RC Celta de Vigo finish a La Liga
match. Runs entirely on GitHub Actions on a schedule — no server, no database.

## How it works

Every ~20 minutes (`.github/workflows/check_result.yml`), GitHub Actions runs
`main.py`, which:

1. Reads `state.json` for the last match ID we've already posted about.
2. Queries football-data.org (`/v4/teams/{team_id}/matches`, competition code
   `PD` = La Liga) for Celta's finished matches.
3. If the latest finished match is new, `fetch_thesportsdb_goals()` tries
   to enrich it with scorer names and goal minutes from TheSportsDB (see
   below) — this is optional and fails safely to `None`.
   `classify_match()` then compares half-time to full-time score (from
   Celta's perspective, handling both home and away), plus the enrichment
   data if available, to pick one of 14 categories — not just
   WIN/DRAW/LOSS, but the *shape* of the result:
   comeback/blowout/narrow/late/standard for wins,
   rally/squandered/late/flat for draws,
   collapse/blowout/narrow/late/standard for losses. It picks a random
   Galician phrase for that category from `phrases.py`, and posts
   `{phrase} {home} {score} {away} ({scorer note})` (teams in real
   home/away order; the scorer note only appears when enrichment data was
   available) to Telegram.
4. Writes the new match ID back to `state.json`, which the workflow commits
   back to the repo so state survives between runs.

**Two data sources, one optional:**
- football-data.org's free tier has no minute-by-minute goal data (no
  `goals` array on `/v4/matches/{id}` either — confirmed empirically, not
  just undocumented). Half-time vs full-time score is the most granular
  signal it gives us on its own.
- TheSportsDB (`fetch_thesportsdb_goals()`) fills that gap for free — goal
  scorer names and exact minutes, confirmed working against real Celta
  matches. It's matched to the football-data.org match by calendar date
  (teams can't play twice the same day). **Its data can be incomplete** —
  we found a real match where one team's goal was simply missing from its
  timeline — so `_classify_late_drama()` cross-checks the goals list's own
  counts against the real final score before trusting it for a
  `*_LATE` category, and bails out to the normal categories if they don't
  match. Never let this data source's absence or unreliability block or
  crash the core posting flow — it's enrichment, not a dependency.

First-ever run is a no-op that just records the current latest match as the
baseline, so the bot doesn't blast out a historical result the moment it's
installed.

## Key files

- `main.py` — all the logic, heavily commented (written for a Python
  beginner to read). `classify_match()` does the category classification
  (`_classify_late_drama()` handles the `*_LATE` cases specifically);
  `fetch_thesportsdb_goals()` does the TheSportsDB lookup;
  `_format_celta_scorers()` builds the scorer-name clause. `FAKE_TEST_MATCHES`
  has one hand-built `{"match": ..., "goals": ...}` example per category
  (14 total, three with fake goals data) for local/CI testing. Supports
  `python main.py --test-telegram`, which sends a message built from a
  random fake match to every configured channel without touching
  football-data.org, TheSportsDB, or `state.json` — used to smoke-test
  Telegram credentials. Note: the test message is indistinguishable from a
  real one (no "TEST" label).
- `phrases.py` — Galician phrase banks, one list per category (14 total,
  ~4 phrases each) keyed in the `PHRASES` dict by category name (e.g.
  `"WIN_COMEBACK"`, `"LOSS_BLOWOUT"`, `"WIN_LATE"`). Every phrase in a
  `WIN_*` category starts with "Ben, Celta, ben!", every `DRAW_*` with
  "Regular, Celta, regular!", every `LOSS_*` with "Mal, Celta, mal!" —
  this fixed-opener rule is an explicit requirement, preserve it if
  editing further. Also avoid stadium-specific wording (e.g. "Balaídos")
  since away matches are half the fixtures — this was already caught and
  fixed once. **Only the original WIN phrase ("Ben, Celta, ben! Partido
  gañado con mérito!") came from the user — the rest were AI-drafted and
  explicitly have not been reviewed by a native Galician speaker.** Don't
  assume their wording/tone is correct; flag this if asked to touch them.
- `state.json` — single field, `last_processed_match_id`. Committed back to
  the repo by the workflow after each run (`github-actions[bot]` identity).
- `.github/workflows/check_result.yml` — cron `*/20 * * * *`, plus a manual
  `workflow_dispatch` with a `test_mode` boolean input that runs
  `--test-telegram` instead of a real check.
- `.env.example` — template for local runs; real `.env` is gitignored and
  never committed. In production these are GitHub Actions repo secrets.

## Config (env vars / GitHub secrets)

- `TELEGRAM_BOT_TOKEN` — from BotFather
- `TELEGRAM_CHANNEL_ID` — one channel/group (`@name` or numeric id) or
  several comma-separated (posts to all; partial failures don't block the
  working ones, and only mark the match processed if at least one send
  succeeds). Channels need the bot added as **admin**; groups only need the
  bot as a plain **member**. Groups upgraded to supergroups get a new
  `-100...` id — a working group ID that suddenly fails is usually this.
- `FOOTBALL_DATA_API_KEY` — football-data.org free tier
- `CELTA_TEAM_ID` — not a secret; falls back to `DEFAULT_CELTA_TEAM_ID = "558"`
  in `main.py` if unset. **This id is an unverified best guess** — both
  `main.py` and `.env.example` flag it explicitly. If match data ever looks
  wrong, verify this against the live API before debugging anything else.
- `THESPORTSDB_TEAM_ID` / `THESPORTSDB_API_KEY` — both optional, not
  secrets, with working free defaults (`DEFAULT_THESPORTSDB_TEAM_ID =
  "133937"`, confirmed against the live API; `DEFAULT_THESPORTSDB_API_KEY =
  "3"`, TheSportsDB's public free test key). No signup needed to get
  enrichment working.

## Things to know before making changes

- No hardcoded secrets anywhere — always env vars / GitHub secrets.
- API calls (`fetch_recent_matches`, `send_telegram_message`,
  `fetch_thesportsdb_goals`) never raise; they log and return
  `None`/`False` so a bad run doesn't crash the whole workflow or corrupt
  state. TheSportsDB enrichment specifically is a nice-to-have on top of
  an already-working core flow — never make it required or block posting
  on it succeeding.
- On partial Telegram failures, `state.json` is still updated (so working
  channels don't get double-posted) — the failing channel just misses that
  one result until fixed.
- The user is a Python beginner — keep comments and explanations in the code
  itself, not just in commit messages/PR descriptions.
- Ask before guessing on anything ambiguous (exact channel name, team id,
  phrase wording) rather than assuming — this was an explicit instruction in
  the original project brief.
