# Manel Bot

A Telegram bot that posts a message whenever RC Celta de Vigo finish a La Liga
match. Runs entirely on GitHub Actions on a schedule — no server, no database.

## How it works

Every ~20 minutes (`.github/workflows/check_result.yml`), GitHub Actions runs
`main.py`, which:

1. Reads `state.json` for the last match ID we've already posted about.
2. Queries football-data.org (`/v4/teams/{team_id}/matches`, competition code
   `PD` = La Liga) for Celta's finished matches.
3. If the latest finished match is new, works out WIN/DRAW/LOSS from Celta's
   perspective (handles home and away), picks a random Galician phrase from
   `phrases.py`, and posts `{phrase} Celta {score} {opponent}` to Telegram.
4. Writes the new match ID back to `state.json`, which the workflow commits
   back to the repo so state survives between runs.

First-ever run is a no-op that just records the current latest match as the
baseline, so the bot doesn't blast out a historical result the moment it's
installed.

## Key files

- `main.py` — all the logic, heavily commented (written for a Python
  beginner to read). Supports `python main.py --test-telegram`, which sends a
  message built from a fake match (random WIN/DRAW/LOSS) to every configured
  channel without touching football-data.org or `state.json` — used to
  smoke-test Telegram credentials. Note: the test message is
  indistinguishable from a real one (no "TEST" label).
- `phrases.py` — Galician phrase banks (`WIN_PHRASES`, `DRAW_PHRASES`,
  `LOSS_PHRASES`), 6 each. **Only the original WIN phrase ("Ben, Celta, ben!
  Partido gañado con mérito!") came from the user — the rest were AI-drafted
  and explicitly have not been reviewed by a native Galician speaker.** Don't
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

## Things to know before making changes

- No hardcoded secrets anywhere — always env vars / GitHub secrets.
- API calls (`fetch_recent_matches`, `send_telegram_message`) never raise;
  they log and return `None`/`False` so a bad run doesn't crash the whole
  workflow or corrupt state.
- On partial Telegram failures, `state.json` is still updated (so working
  channels don't get double-posted) — the failing channel just misses that
  one result until fixed.
- The user is a Python beginner — keep comments and explanations in the code
  itself, not just in commit messages/PR descriptions.
- Ask before guessing on anything ambiguous (exact channel name, team id,
  phrase wording) rather than assuming — this was an explicit instruction in
  the original project brief.
