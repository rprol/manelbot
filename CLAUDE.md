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

Both checks funnel into `select_category()`, which wraps `classify_match()`
(the *shape of this one match* — comeback/blowout/narrow/late/ten-men/
standard for wins, rally/squandered/late/flat for draws,
collapse/blowout/narrow/late/ten-men/standard for losses — 16 categories,
unchanged) with a cup-advancement default and a global win/loss streak:

1. **Cup advancement default** — in `COMPETITIONS_WHERE_WIN_MEANS_ADVANCING`
   (currently just `"Copa del Rey"`), any win becomes
   `WIN_ADVANCED_ROUND` regardless of the match's own shape. Spain's cup
   is single-match knockout for every round **except the semifinal**,
   which is two-legged — so this default is right most of the time, but
   can't be trusted blindly for that one round; see `_check_two_legged_tie()`
   below for how the *second* leg gets corrected. `UEFA Europa League` is
   deliberately NOT in this set — its multi-matchday league phase means a
   single win/loss there usually doesn't decide anything by itself, so
   this default would be wrong more often than right there.
2. **Win/loss streaks** — `_update_streak()` tracks ONE **global** streak
   in `state["streak"]` (deliberately competition-agnostic — a La Liga
   win followed by a Copa del Rey win is a 2-win streak, not two separate
   1-win streaks; a DRAW, or a different outcome, resets it).
   `WIN_STREAK_2`/`WIN_STREAK_3` or `LOSS_STREAK_2`/`LOSS_STREAK_3` (3 =
   "3 or more", generic enough to stay accurate at any length) replace
   `WIN_STANDARD`/`LOSS_STANDARD` **only** — a comeback/blowout/late/
   ten-men win or loss keeps its own category even mid-streak, since that
   match's own story is more specific than the streak trend.

Separately, `check_other_competitions_result()` calls
`_check_two_legged_tie()` **after** `select_category()`, which can
override its result entirely: it recognises a same-opponent rematch in
the same competition within `TWO_LEGGED_TIE_WINDOW_DAYS` (15) as the
second leg of a two-legged tie — Copa del Rey semifinal, or any Europa
League/Conference League knockout round (all two-legged except the
final) — and computes the *true aggregate* result across both legs,
returning `WIN_ADVANCED_ROUND` or `LOSS_ELIMINATED` (a genuinely new
category, only reachable this way — see phrases.py). This is a
**structural** signal, not round-number-based: neither a round-robin
league nor a "no repeated opponent" league phase can ever produce a
same-opponent rematch that soon, so seeing one at all reliably means a
knockout tie, regardless of what round number (if any) the data source
reports. State for this lives in
`state["last_opponent_by_competition"][competition_key]` (opponent id,
date, both scores) — updated on *every* check #2 result, not just
knockout ones, so whatever comes next always has something fresh to
compare against. This only runs inside check #2 — never call it from
check_la_liga_result(), where a same-opponent repeat is just a normal,
unrelated league fixture, not a tie.

The final category picks a random Galician phrase from `phrases.py` (22
categories total now: the 16 above + `WIN_STREAK_2/3`, `LOSS_STREAK_2/3`,
`WIN_ADVANCED_ROUND`, `LOSS_ELIMINATED`), and posts `{phrase} {home}
{score} {away} ({scorer note}). {star performer note} {table note}` (teams
in real home/away order; scorer/star notes only when timeline data was
available; the table note only for an actual La Liga result — see below)
to Telegram. **The message never names the competition** — no `[Copa del
Rey]`-style prefix; that was tried and explicitly removed. `competition_key`
is used purely internally for the advancement default and the two-legged
lookup, never rendered. Each check then writes its own new id (and, for
check #2, the event's date — see "known limitation" below) back to
`state.json`, which the workflow commits back to the repo so state
survives between runs.

**La Liga table position** — `check_la_liga_result()` additionally calls
`fetch_la_liga_standings()` (confirmed live: `/v4/competitions/PD/standings`
works on the free tier) whenever `competition_key == "La Liga"` specifically
(never for Champions League — a league table doesn't mean anything there).
`_la_liga_table_zone()` classifies the position into one of five
EXHAUSTIVE zones — `EUROPEAN` (top `LA_LIGA_EUROPEAN_POSITIONS`, 6),
`NEAR_EUROPEAN`, `MID_TABLE`, `NEAR_RELEGATION`, `RELEGATION` (bottom
`LA_LIGA_RELEGATION_ZONE_SIZE`, 3) — with `LA_LIGA_APPROACHING_MARGIN`
(3) controlling how many places count as "near" either edge; every
position falls into exactly one. `_format_table_position_note()` then
picks a random phrase for that zone from `phrases.TABLE_POSITION_PHRASES`
(a completely separate phrase system from `PHRASES`/`get_random_phrase()`
— no fixed-opener rule, no position number in the text) and adds it via
`build_message()`'s `table_note` param. **Deliberately independent of
win/draw/loss** — added after every La Liga result, not gated to specific
outcomes, since it's ongoing season context rather than something this
result caused (an earlier version only fired on a WIN reaching Europe or
a LOSS in the relegation zone, with the position number in the text —
both were deliberately changed). Fails safely to no note (never blocks
posting) on any standings-fetch failure, same pattern as the TheSportsDB
enrichment. "Approaching" is a position-count proxy, not points-based —
documented as a known simplification, same as the European-positions
cutoff itself.

**Known limitations:**
- **A two-legged tie's *first* leg can't be identified in advance** —
  there's nothing to compare against until the same opponent shows up
  again, so a Copa del Rey semifinal's first leg can still get mis-tagged
  `WIN_ADVANCED_ROUND` by the default above before we know the tie isn't
  decided. Only the second leg is guaranteed correct (it silently
  overrides whatever the first leg implied, using the real aggregate).
  Don't try to "fix" this by guessing at round numbers instead — that's
  exactly the unreliable approach this design replaced (see git history:
  an earlier version tried gating on `intRound`, which turned out to mean
  different things in different competitions/seasons and couldn't be
  verified against the free-tier data available).
- **No way to detect a cup final specifically** — winning one currently
  still reads as "advances to the next round" rather than "wins the
  trophy," for the same round-detection-reliability reason.
- Extra-time/penalty-shootout results (an aggregate-level draw, not just
  a single match) aren't specially handled — `_check_two_legged_tie()`
  returns `None` (falls back to that leg's own normal category) rather
  than guessing who went through on penalties, since how TheSportsDB
  represents a shootout on the free tier hasn't been confirmed against a
  real example.
- `eventslast.php` is not reliably monotonic/up-to-date — confirmed live
  on 2026-09-16: hours after correctly showing a new Europa League result
  (Omonia Nicosia 1-0 Celta, which had to be posted manually because of
  this same lag), it reverted to showing the *older* La Liga match again.
  `check_other_competitions_result()` therefore also stores
  `last_processed_thesportsdb_event_date` and ignores any "new" event
  whose date isn't strictly after what's already recorded, rather than
  trusting the id alone — otherwise a stale response regresses state
  backwards and risks re-posting an already-sent result once
  `eventslast.php` actually catches up. Don't remove that date check.

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
  goals()` are check #2's TheSportsDB-only path. `select_category()`
  layers the cup-advancement default/streak overrides on top of
  `classify_match()`; `_update_streak()` is its global streak tracker;
  `_check_two_legged_tie()` (called separately, only from check #2) does
  the same-opponent-rematch aggregate-score override (see "How it works"
  above for all of this). `_format_celta_scorers()` builds the
  scorer-name clause (groups a brace/hat-trick under one player instead
  of repeating the name, e.g. "cun dobrete"/"cun triplete" — deliberately
  no goal minutes in the displayed text, even though `goals[i]["minute"]`
  itself still drives `_classify_late_drama()`); `_find_star_performer()`
  finds a standout player from goal+assist counts.
  `fetch_la_liga_standings()` + `_find_team_position()` +
  `_la_liga_table_zone()` + `_format_table_position_note()` are check #1's
  La-Liga-only (never Champions League) table-position note — called
  directly from `check_la_liga_result()`, not layered into
  `select_category()`/`classify_match()` like everything else, since it
  produces an extra sentence via `build_message()`'s `table_note` param
  rather than picking a different phrases.py category, and (unlike every
  other override in this file) is deliberately independent of the
  match's own WIN/DRAW/LOSS outcome. `FAKE_TEST_MATCHES` has one
  hand-built
  `{"match": ..., "goals": ..., "red_cards": ..., "category_override":
  ...}` example per category (22 total). The base 16 rely on
  `category_override` being absent/`None`, so `build_message()` derives
  the category from the match itself via `classify_match()` as normal;
  the 6 new ones (`WIN_STREAK_2/3`, `LOSS_STREAK_2/3`,
  `WIN_ADVANCED_ROUND`, `LOSS_ELIMINATED`) can't be inferred from a
  single match in isolation (they depend on streak/two-legged-tie state
  test mode doesn't have), so they set `category_override` explicitly
  instead. Supports `python main.py --test-telegram`, which sends a
  message built from a random fake match to every configured channel
  without touching football-data.org, TheSportsDB, or `state.json` —
  used to smoke-test Telegram credentials. Note: the test message is
  indistinguishable from a real one (no "TEST" label).
- `phrases.py` — Galician phrase banks, one list per category (22 total,
  ~4 phrases each) keyed in the `PHRASES` dict by category name (e.g.
  `"WIN_COMEBACK"`, `"LOSS_BLOWOUT"`, `"WIN_LATE"`, `"WIN_TEN_MEN"`,
  `"WIN_STREAK_2"`, `"WIN_ADVANCED_ROUND"`, `"LOSS_ELIMINATED"`). Every
  phrase in a `WIN_*` category starts with "Ben, Celta, ben!", every
  `DRAW_*` with "Regular, Celta, regular!", every `LOSS_*` with "Mal,
  Celta, mal!" — this fixed-opener rule is an explicit requirement,
  preserve it if editing further. Also avoid stadium-specific wording
  (e.g. "Balaídos") since away matches are half the fixtures — this was
  already caught and fixed once. **The message never names the
  competition** (no `[Copa del Rey]`-style prefix) — that was tried and
  explicitly removed; don't reintroduce it. `LOSS_ELIMINATED` specifically
  is about being knocked out of a two-legged tie on aggregate, not about
  this match's own scoreline (Celta can even win the match and still be
  `LOSS_ELIMINATED`) — write/edit its phrases with that in mind. **Only
  the original WIN phrase ("Ben, Celta, ben! Partido gañado con
  mérito!") came from the user — the rest, including all 6 new
  streak/advancement/elimination categories, were AI-drafted and
  explicitly have not been reviewed by a native Galician speaker.** Don't
  assume their wording/tone is correct; flag this if asked to touch them.
  Also contains `TABLE_POSITION_PHRASES` — a SEPARATE dict (5 keys: See
  "La Liga table position" above), NOT part of `PHRASES`/
  `get_random_phrase()`, with no fixed-opener rule (these are trailing
  sentences, not a result's own category) — use `get_random_table_phrase()`
  for these instead, don't add them to `PHRASES` or route them through
  `get_random_phrase()`.
- `state.json` — five fields: `last_processed_match_id`
  (football-data.org, check #1); `last_processed_thesportsdb_event_id` +
  `last_processed_thesportsdb_event_date` (TheSportsDB, check #2 — the
  date exists specifically to guard against `eventslast.php`'s
  non-monotonic responses, see "known limitations" above, don't drop it);
  `streak` (ONE global object, e.g. `{"outcome": "WIN", "count": 2}` —
  see `_update_streak()`, deliberately not split per competition); and
  `last_opponent_by_competition` (a dict keyed by competition name, e.g.
  `{"Copa del Rey": {"opponent_id": 123, "date": "2027-03-04",
  "celta_score": 0, "opponent_score": 1}}` — see
  `_check_two_legged_tie()`, only ever written/read by check #2).
  Committed back to the repo by the workflow after each run
  (`github-actions[bot]` identity). All of this lives in *one* shared
  `state` dict that both checks mutate and pass to `save_state(state)` —
  never construct a fresh dict to save just one field, or you'll silently
  wipe out the other check's keys (or the streak, or the opponent
  history).
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
- `select_category()` always calls `_update_streak()` (mutating
  `state["streak"]`), and `check_other_competitions_result()` always
  calls `_check_two_legged_tie()` (mutating
  `state["last_opponent_by_competition"]`) — both even when a
  total-send-failure means `state` never actually gets saved this run.
  That's intentional: it keeps the whole "this match's effect on state"
  atomic with whether it was actually posted, so a failed send gets its
  streak/opponent-history effect recomputed correctly on retry instead of
  double-counting or missing a leg.
- The user is a Python beginner — keep comments and explanations in the code
  itself, not just in commit messages/PR descriptions.
- Ask before guessing on anything ambiguous (exact channel name, team id,
  phrase wording) rather than assuming — this was an explicit instruction in
  the original project brief.
