# Manel Bot

A Telegram bot that posts a message whenever RC Celta de Vigo finish a
match — any competition. Runs entirely on GitHub Actions on a schedule — no
server, no database.

## How it works

Every ~20 minutes (`.github/workflows/check_result.yml`), GitHub Actions runs
`main.py`, which runs two independent checks (see `main()`), because no
single free API covers every competition Celta might play:

1. **`check_la_liga_result()`** — La Liga + Champions League, via
   football-data.org. Reads `state.json`'s `last_processed_match_id`,
   queries `/v4/teams/{team_id}/matches` (`competitions=PD,CL` —
   `COMPETITION_CODES`) for Celta's finished matches. These are the only
   two competitions confirmed available on football-data.org's *free*
   tier for Celta — querying `/v4/competitions/CDR` (Copa del Rey) or
   `/v4/competitions/EL` (Europa League) with our key returns `403
   "restricted... check your subscription"`. If the latest finished match
   is new, `fetch_thesportsdb_match_events()` tries to enrich it with
   scorer/assist names, goal minutes, and red cards from TheSportsDB —
   optional, fails safely to `None`.
2. **`check_other_competitions_result()`** — everything else (Copa del
   Rey, Europa League, Conference League, ...), via TheSportsDB directly.
   `fetch_thesportsdb_latest_event()` asks `eventslast.php` for Celta's
   single most recent event, in ANY competition, with no competition
   filter — this is the only TheSportsDB free-key endpoint confirmed to
   return live, unrestricted data for a specific team (its bulk
   season-listing endpoints, e.g. a whole Copa del Rey season, returned
   only 5 sample events total when tested — heavily restricted on the free
   key — so this bot can only ever ask "what was Celta's last finished
   match", never browse historical results). If that event's `idLeague` is
   La Liga (`4335`) or Champions League (`4480`) —
   `THESPORTSDB_LEAGUES_COVERED_BY_FOOTBALL_DATA` — it's skipped here
   (already handled by check #1, with richer half-time data); otherwise
   `build_thesportsdb_match()` turns the raw event into a
   football-data.org-shaped match dict (half-time score reconstructed from
   the goal timeline via `_derive_half_time_from_goals()`, using the same
   goal-count cross-check as `_classify_late_drama()`) so
   `classify_match()`/`build_message()` can be reused unchanged. Reads/
   writes its own `state.json` key, `last_processed_thesportsdb_event_id`
   — a *different* key than check #1, so the two never clobber each
   other's progress in the same file.

Both checks funnel into the same `classify_match()`/`build_message()`:
`classify_match()` compares half-time to full-time score (from Celta's
perspective, handling both home and away), plus enrichment goals/red-cards
data if available, to pick one of 16 categories — not just WIN/DRAW/LOSS,
but the *shape* of the result: comeback/blowout/narrow/late/ten-men/standard
for wins, rally/squandered/late/flat for draws,
collapse/blowout/narrow/late/ten-men/standard for losses. It picks a random
Galician phrase for that category from `phrases.py`, and posts
`[{competition}] {phrase} {home} {score} {away} ({scorer note}). {star
performer note}` (teams in real home/away order; the `[competition]` prefix
only appears for check #2's non-La-Liga/CL results — see `build_message()`'s
`competition_name` param; the scorer note and star-performer sentence only
appear when enrichment/timeline data was available) to Telegram. Each check
then writes its own new id back to `state.json`, which the workflow commits
back to the repo so state survives between runs.

**Known limitation:** extra-time/penalty-shootout results (Copa del Rey
ties can go to penalties) aren't specially handled — classification uses
TheSportsDB's regulation-time score (`intHomeScore`/`intAwayScore`) same as
any other match, since how a shootout is represented there on the free
tier hasn't been confirmed against a real example.

**Two data sources, one dual-purpose:**
- football-data.org's free tier has no minute-by-minute goal data (no
  `goals` array on `/v4/matches/{id}` either — confirmed empirically, not
  just undocumented). Half-time vs full-time score is the most granular
  signal it gives us on its own, and it only covers La Liga + Champions
  League for Celta on the free tier (see above).
- TheSportsDB does two jobs: (a) enrichment on top of a football-data.org
  result (`fetch_thesportsdb_match_events()`, matched to the
  football-data.org match by calendar date since the two providers use
  different ids for the same real-world match — a team can't play twice
  the same day), and (b) the *sole* source for every competition
  football-data.org's free tier doesn't cover
  (`fetch_thesportsdb_latest_event()`, competition-agnostic by design).
  Goal-by-goal timeline data confirmed working against real Celta matches
  (including a real red card found by scanning live La Liga rounds:
  `strTimelineDetail` is literally `"Red Card"`). **Its data can be
  incomplete** — we found a real match where one team's goal was simply
  missing from its timeline — so `_classify_late_drama()` and
  `_derive_half_time_from_goals()` both cross-check the goals list's own
  counts against the real final score before trusting it, and fall back
  safely (to the normal categories, or to an unknown half-time score) if
  they don't match. `_classify_ten_men()` similarly only fires when
  exactly one side has a recorded red card (Celta's), to avoid an
  ambiguous call. For check #1, none of this ever blocks or crashes the
  core posting flow — it's enrichment, not a dependency; for check #2 it
  *is* the core data source, so a TheSportsDB outage means that check
  simply finds nothing this run (logged, not fatal) rather than crashing.
- `_find_star_performer()` looks for a Celta player with 2+ goal
  contributions (their own goals + assists given) and names them as the
  standout — the most honest signal the free-tier data supports for "who
  had a great match," since there's no official man-of-the-match or
  player-rating endpoint (checked). Don't extend this to claim a stronger
  "best player" signal than goal involvement without new data backing it.

First-ever run of *each check* is a no-op that just records the current
latest match/event as the baseline, so the bot doesn't blast out a
historical result the moment it's installed (or the moment this
multi-competition support is deployed to an already-running bot).

## Key files

- `main.py` — all the logic, heavily commented (written for a Python
  beginner to read). `check_la_liga_result()` / `check_other_competitions_
  result()` are the two top-level checks `main()` runs every invocation
  (each returns `True` only on a genuinely-new-result-failed-to-send, so
  `main()` can `sys.exit(1)` after both have run, not before). `classify_
  match()` does the category classification (`_classify_late_drama()`
  handles `*_LATE`, `_classify_ten_men()` handles `*_TEN_MEN`);
  `fetch_thesportsdb_match_events()` does the by-date-matched TheSportsDB
  lookup for check #1 (returns `{"goals": [...], "red_cards": [...]}` or
  `None`); `fetch_thesportsdb_latest_event()` + `_fetch_thesportsdb_
  timeline()` (shared helper, also used by `fetch_thesportsdb_match_
  events()`) + `build_thesportsdb_match()` + `_derive_half_time_from_
  goals()` are check #2's TheSportsDB-only path; `_format_celta_scorers()`
  builds the scorer-name clause (groups a brace/hat-trick under one player
  instead of repeating the name); `_find_star_performer()` finds a
  standout player from goal+assist counts. `FAKE_TEST_MATCHES` has one
  hand-built `{"match": ..., "goals": ..., "red_cards": ...,
  "competition_name": ...}` example per category (18 total: 16 categories
  + 2 demonstrating the `[competition]` prefix) for local/CI testing.
  Supports `python main.py --test-telegram`, which sends a message built
  from a random fake match to every configured channel without touching
  football-data.org, TheSportsDB, or `state.json` — used to smoke-test
  Telegram credentials. Note: the test message is indistinguishable from a
  real one (no "TEST" label).
- `phrases.py` — Galician phrase banks, one list per category (16 total,
  ~4 phrases each) keyed in the `PHRASES` dict by category name (e.g.
  `"WIN_COMEBACK"`, `"LOSS_BLOWOUT"`, `"WIN_LATE"`, `"WIN_TEN_MEN"`).
  Every phrase in a `WIN_*` category starts with "Ben, Celta, ben!",
  every `DRAW_*` with "Regular, Celta, regular!", every `LOSS_*` with
  "Mal, Celta, mal!" — this fixed-opener rule is an explicit requirement,
  preserve it if editing further. Also avoid stadium-specific wording
  (e.g. "Balaídos") since away matches are half the fixtures — this was
  already caught and fixed once. **Only the original WIN phrase ("Ben,
  Celta, ben! Partido gañado con mérito!") came from the user — the rest
  were AI-drafted and explicitly have not been reviewed by a native
  Galician speaker.** Don't assume their wording/tone is correct; flag
  this if asked to touch them.
- `state.json` — two fields, one per check: `last_processed_match_id`
  (football-data.org, check #1) and `last_processed_thesportsdb_event_id`
  (TheSportsDB, check #2). Committed back to the repo by the workflow
  after each run (`github-actions[bot]` identity). Both checks mutate the
  *same* shared `state` dict and call `save_state(state)` — never
  construct a fresh dict to save just one field, or you'll silently wipe
  out the other check's key.
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
- `FOOTBALL_DATA_API_KEY` — football-data.org free tier. Only used by
  `check_la_liga_result()`; `CELTA_TEAM_ID` is confirmed to be `558` (RC
  Celta de Vigo) via the live API, no longer just an unverified guess.
- `CELTA_TEAM_ID` — not a secret; falls back to `DEFAULT_CELTA_TEAM_ID = "558"`
  in `main.py` if unset.
- `THESPORTSDB_TEAM_ID` / `THESPORTSDB_API_KEY` — both optional, not
  secrets, with working free defaults (`DEFAULT_THESPORTSDB_TEAM_ID =
  "133937"`, confirmed against the live API; `DEFAULT_THESPORTSDB_API_KEY =
  "3"`, TheSportsDB's public free test key). No signup needed. **No longer
  purely optional in effect** — `check_other_competitions_result()` (Copa
  del Rey, Europa League, ...) depends entirely on TheSportsDB; only the
  *enrichment* role on top of check #1's La Liga/Champions League results
  is optional/fails-safe.

## Things to know before making changes

- No hardcoded secrets anywhere — always env vars / GitHub secrets.
- API calls (`fetch_recent_matches`, `send_telegram_message`,
  `fetch_thesportsdb_match_events`, `fetch_thesportsdb_latest_event`,
  `_fetch_thesportsdb_timeline`) never raise; they log and return
  `None`/`False` so a bad run doesn't crash the whole workflow or corrupt
  state. TheSportsDB's *enrichment* role (check #1) is a nice-to-have on
  top of an already-working core flow — never make it required or block
  posting on it succeeding. Its role as check #2's primary data source is
  different: a TheSportsDB failure there just means check #2 finds
  nothing this run, same as football-data.org failing means check #1
  finds nothing — neither should ever crash the process.
- `check_la_liga_result()` and `check_other_competitions_result()` are
  independent: one failing/finding-nothing must never prevent the other
  from running. `main()` calls both unconditionally and only decides on
  `sys.exit(1)` after both have returned — don't reintroduce an early
  `return`/`sys.exit()` inside either check that would still be reachable
  from `main()` before the other check runs (early returns *inside* a
  check, once it's determined there's nothing new for *that* check, are
  fine and expected).
- On partial Telegram failures, `state.json` is still updated (so working
  channels don't get double-posted) — the failing channel just misses that
  one result until fixed.
- The user is a Python beginner — keep comments and explanations in the code
  itself, not just in commit messages/PR descriptions.
- Ask before guessing on anything ambiguous (exact channel name, team id,
  phrase wording) rather than assuming — this was an explicit instruction in
  the original project brief.
