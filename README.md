# Manel Bot 🔵⚪

A small Telegram bot that watches for Celta de Vigo's results -- La Liga,
the Champions League, Copa del Rey, the Europa League, anything -- and
posts a reaction message to a Telegram channel -- in Galician -- whenever a
match finishes.

It has no server: a GitHub Actions workflow runs the script every 20
minutes, checks whether Celta played a match that just finished, and posts
about it if so. A tiny `state.json` file (committed back to the repo by the
workflow) keeps track of what's already been posted, so the same result is
never posted twice.

## ⚠️ Before going live: review the phrases

The Galician phrases in [phrases.py](phrases.py) were drafted by an AI
(except the original WIN phrase you provided: "Ben, Celta, ben! Partido
gañado con mérito!"). Every phrase always starts with a fixed opener for its
outcome -- "Ben, Celta, ben!" for wins, "Regular, Celta, regular!" for
draws, "Mal, Celta, mal!" for losses -- followed by an AI-drafted
continuation that varies per phrase and per category (see "How it works"
below for what the categories are). **Please have a native Galician speaker
read through the continuations in `phrases.py` and correct anything that
sounds wrong before you start posting to a real channel.** The file is
plain Python lists of strings, so editing, replacing, or adding phrases is
just editing text.

## How it works

`main.py` runs two independent checks every time it's invoked, because no
single free API covers everything Celta might play:

- **`check_la_liga_result()`** -- La Liga and the Champions League, via
  [football-data.org](https://www.football-data.org/). These are the only
  two competitions Celta could play in that football-data.org's *free* tier
  actually includes (confirmed against the live API -- Copa del Rey and the
  Europa League both return a 403 "check your subscription").
- **`check_other_competitions_result()`** -- everything else (Copa del Rey,
  the Europa League, the Conference League, ...), via
  [TheSportsDB](https://www.thesportsdb.com/), which covers any competition.
  It looks up Celta's actual latest finished match with no competition
  filter at all, and skips it if that turns out to be a La Liga/Champions
  League match -- those are already handled (with richer data) by the check
  above, so it's never posted twice.

Both checks work the same way:

1. Fetch Celta's latest finished match from their respective data source.
2. Compare its id against the one saved in `state.json` (each check uses
   its own key, so they don't interfere with each other).
   - If it's the same, nothing happened since last time for that check --
     it exits quietly.
   - If it's different, that's a new result: work out not just WIN/DRAW/LOSS
     but the *shape* of the match, pick a random Galician phrase matching
     that from `phrases.py`, and post a message like:

     > Ben, Celta, ben! Ían perdendo e deron a volta ao marcador! Celta 2-1 Getafe

     **The message never names the competition** -- it's the exact same
     phrase-and-score format no matter what competition it was.

   The base categories (shared by both checks -- see `classify_match()` in
   `main.py`):
   - **Win:** comeback (behind at half-time, won) · blowout (won by 3+) ·
     narrow (won by 1) · late (winning goal in the closing minutes) · ten
     men (won despite a Celta player being sent off) · standard (anything
     else)
   - **Draw:** rally (behind at half-time, clawed back to a draw) ·
     squandered (led at half-time, dropped it to a draw) · late
     (equalizer in the closing minutes) · flat (level at half-time and
     full-time)
   - **Loss:** collapse (led at half-time, lost) · blowout (lost by 3+) ·
     narrow (lost by 1) · late (decisive goal conceded in the closing
     minutes) · ten men (lost while playing with a man down) · standard
     (anything else)

   The "late" and "ten men" categories, plus scorer names and a
   standout-player callout in the posted message, come from TheSportsDB's
   goal-by-goal timeline -- see "Scorer names, standout players, and match
   drama" below. Without it, half-time vs full-time alone gives enough for
   every other category.

   On top of that, `select_category()` (see "Streaks and cup advancement"
   below) can swap a bland "standard" win/loss for a streak-aware phrase,
   or a Copa del Rey win for an advancement phrase -- these take priority
   over the base categories above in specific cases; see that section for
   exactly when.

3. `state.json` is updated with the new match/event id, and the GitHub
   Actions workflow commits that change back to the repo, so the next
   scheduled run knows this result was already posted.

On the very first run ever for each check (when its key isn't in
`state.json` yet), the bot deliberately does **not** post anything -- it
just records the latest finished match as "already seen". This avoids
posting about an old match the moment you first set the bot up (or the
moment this multi-competition support is deployed to an existing bot).
From the next new result onwards, it posts normally.

**Known limitations:**
- Extra-time/penalty-shootout knockout results (which Copa del Rey ties
  can go to) aren't specially handled -- classification uses TheSportsDB's
  regulation-time score, since how it represents a penalty shootout on the
  free tier hasn't been confirmed. Worth revisiting if this bot needs to
  cover a tie that goes to penalties.
- TheSportsDB's `eventslast.php` (the primary source for
  `check_other_competitions_result()`) isn't always up to date -- it can
  briefly show an older match again even after a newer one has finished
  and already been posted. `state.json` stores the date of the last
  processed event specifically to detect and ignore this, so it doesn't
  cause a duplicate post once the endpoint catches up.

## Streaks and cup advancement

On top of each match's own shape, `select_category()` in `main.py` adds
two more layers of context, each tracked **separately per competition**
(a La Liga streak and a Champions League streak, for example, never mix):

- **Win/loss streaks:** two or more wins (or losses) in a row in the same
  competition get a streak-aware phrase instead of a bland "standard"
  one, e.g.:

  > Ben, Celta, ben! Terceira vitoria consecutiva, o Celta está en racha! Celta 1-0 Getafe

  This only replaces the *standard* win/loss category -- a comeback,
  blowout, late winner, or ten-men result keeps its own more specific
  phrase even if it's also the 3rd win in a row, since that match's own
  story is more specific than the streak. A draw (or the opposite result)
  resets the streak back to zero.
- **Cup advancement:** a **Copa del Rey** win always gets an
  advancement-themed phrase instead, e.g.:

  > Ben, Celta, ben! O Celta avanza á seguinte rolda da copa! Celta 1-0 Ponferradina

  This is reliable specifically because Spain's cup has been strict
  single-match knockout (no two-legged ties, no replays) since the
  2019-20 format change -- a win there always means advancing, full stop,
  so it takes priority over every other category for that competition.

  **The Europa League deliberately does NOT get this treatment.** Its
  format mixes a multi-matchday league phase (a single result doesn't
  decide anything by itself) with mostly two-legged knockout rounds (a
  single-leg win doesn't guarantee winning the tie), and TheSportsDB's
  free-tier data doesn't reliably tell us which phase/leg a given match
  was -- confirmed live: a real September 2026 Europa League match came
  back tagged `"intRound": "1"`, which turned out to be a league-phase
  matchday number, not a knockout round. Guessing "advanced" from a
  single win risks posting something false, so this stays unhandled
  until there's a reliable way to tell the phase/leg apart.

## Scorer names, standout players, and match drama

football-data.org's free tier only gives half-time and full-time scores --
no goal-by-goal detail, so there's no way to know who scored, when, or
whether anyone was sent off. To add that, `main.py` also queries
[TheSportsDB](https://www.thesportsdb.com/) right after detecting a new La
Liga/Champions League result (for anything else, TheSportsDB is already the
primary source -- see "How it works" above -- so its timeline is used
directly, not as a lookup on top of another source). If it finds the
matching event:

- **Celta's scorer(s) and goal minute(s)** get appended to the message,
  e.g.:

  > Ben, Celta, ben! Partido gañado con mérito! Celta 2-1 Getafe (marcou Iago Aspas (min. 23))

- If the decisive goal was scored in the closing minutes (from minute 85
  onwards), the match is classified as `WIN_LATE`, `DRAW_LATE`, or
  `LOSS_LATE` instead of its usual category, using a phrase that reflects
  the late drama.
- If a Celta player was sent off (red card) and the match was still won or
  lost, it's classified as `WIN_TEN_MEN` or `LOSS_TEN_MEN` instead.
- If any Celta player was involved in **2 or more goals** this match
  (their own goals plus assists they set up for teammates), they get
  called out by name as the standout performer, e.g.:

  > ... Celta 2-1 Getafe (marcou Iago Aspas (min. 23, min. 80)). Iago Aspas leva 2 accións de gol hoxe!

  This is the most honest signal the data can support for "who had a
  great match" -- there's no official man-of-the-match or player-rating
  data on the free tier (checked), so it only recognizes goal
  involvement, not e.g. a strong defensive performance with no goal or
  assist.

**This is entirely optional and fails safely.** If TheSportsDB is
unreachable, doesn't have that match, or its data doesn't add up to the
real score (its goal data is volunteer-maintained and can be incomplete --
we've seen this happen on a real match, where one team's goal was simply
missing from its timeline; `classify_match()` checks for this and falls
back safely rather than risk a wrong call), the bot just posts the normal
message with no extra detail. Nothing about the core flow depends on this
working.

No signup is required: `THESPORTSDB_TEAM_ID` (Celta's id, `133937`, already
verified against the live API) and `THESPORTSDB_API_KEY` (`3`, TheSportsDB's
public free test key -- per their own docs, this is the normal way to use
their v1 API for free/hobby projects) both have working defaults baked into
`main.py`. You don't need to set either one to get this working. If you
ever want a dedicated (non-shared) key, register for free at
[thesportsdb.com/free_sports_api](https://www.thesportsdb.com/free_sports_api)
and set `THESPORTSDB_API_KEY` to override the default.

## Setup guide

This assumes no prior experience with Telegram bots or GitHub Actions.

### 1. Create a Telegram bot with BotFather

1. In Telegram, search for **@BotFather** and start a chat with it.
2. Send `/newbot` and follow the prompts (pick a name and a username ending
   in `bot`).
3. BotFather will give you a **token** that looks like
   `123456789:AAExampleTokenHere`. Save it -- this is your
   `TELEGRAM_BOT_TOKEN`.

### 2. Add the bot to the channel(s) or group(s) where it should post

This bot can post to Telegram **channels** and **groups** (including
supergroups) -- `TELEGRAM_CHANNEL_ID` can hold any mix of them. The setup is
slightly different for each:

**Channels:** the bot must be added as an **admin** with permission to post
messages -- Telegram enforces this for channels no matter what.

1. Open the channel's settings → **Administrators** → **Add Admin**, and
   add your bot.
2. Figure out its id:
   - Public channel: its `@username` (e.g. `@celta_results`).
   - Private channel: a numeric id, usually a large negative number like
     `-1001234567890`. Get it by posting any message in the channel, then
     visiting `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a
     browser and looking for `"chat":{"id": ...}` in the response.

**Groups:** just add the bot as a normal **member** -- admin rights are
*not* required (unlike channels), unless the group's permissions
specifically restrict regular members from sending messages, in which case
the bot needs the same send-messages exemption an admin would have.

1. Add the bot to the group like you would any other member.
2. Get its chat id the same way as a private channel: send any message in
   the group, then check `getUpdates` as above. It'll be a negative number.
   - ⚠️ If a "basic" group later gets converted to a **supergroup**
     (Telegram does this automatically once a group grows or certain
     features get enabled), its id changes to a new `-100...` one. If
     posting suddenly starts failing with "chat not found" for a group that
     used to work, this is the first thing to check -- re-fetch the id via
     `getUpdates` and update the secret.

**Posting to more than one channel/group:** once each one has the bot added
(as admin for channels, as a member for groups), set `TELEGRAM_CHANNEL_ID` to
a comma-separated list mixing either kind freely, e.g.:

```
TELEGRAM_CHANNEL_ID=@celta_results,-1001234567890,-4009876543
```

The bot posts the same message to every entry in the list. If one fails
(e.g. the bot was removed as admin/member there) the others still get the
message -- check the workflow logs for a warning naming which one(s) failed.

### 3. Get a football-data.org API key

1. Go to [football-data.org](https://www.football-data.org/client/register)
   and register for a free account.
2. Once logged in, find your API key/token on your account page. This is
   your `FOOTBALL_DATA_API_KEY`.
3. The free tier is rate-limited (10 requests/minute), which is more than
   enough for checking once every 20 minutes.

### 4. Verify Celta de Vigo's team id

The bot defaults `CELTA_TEAM_ID` to `558`, which is RC Celta de Vigo's id on
football-data.org at the time this bot was written -- **but please verify
it yourself**, since these ids aren't something we can guarantee will stay
correct. Run this in a terminal (replace `YOUR_API_KEY`):

```bash
curl -H "X-Auth-Token: YOUR_API_KEY" "https://api.football-data.org/v4/competitions/PD/teams"
```

This returns JSON listing every La Liga team. Search the output for
`"Celta"` -- you'll see an entry like:

```json
{
  "id": 558,
  "name": "RC Celta de Vigo",
  ...
}
```

If the `id` you find is different from `558`, use that number instead
wherever `CELTA_TEAM_ID` is mentioned below.

### 5. Test locally (optional but recommended)

1. Install [Python 3.11+](https://www.python.org/downloads/) if you don't
   have it.
2. In the project folder, install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your real values:

   ```bash
   cp .env.example .env
   ```

4. Load the `.env` file into your shell and run the script. On macOS/Linux:

   ```bash
   export $(grep -v '^#' .env | xargs)
   python main.py
   ```

   You should see log output in the terminal explaining what it did (e.g.
   "No finished matches to process this run." or "Posting new result: ...").

### 6. Add secrets to GitHub Actions

The workflow needs your real credentials, but as **repository secrets** --
never commit real tokens into the code.

1. In your GitHub repository, go to **Settings → Secrets and variables →
   Actions → New repository secret**.
2. Add each of these one at a time:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID`
   - `FOOTBALL_DATA_API_KEY`
   - `CELTA_TEAM_ID` (optional -- only needed if it's different from the
     default `558`; if you skip it, the script falls back to `558`)
   - `THESPORTSDB_TEAM_ID` and `THESPORTSDB_API_KEY` (both optional -- see
     "Scorer names and late-goal drama" above; skip both and it just uses
     the free defaults)

### 7. Enable and test the workflow

1. Push this repository to GitHub if you haven't already.
2. Go to the **Actions** tab -- you should see the "Check Celta de Vigo
   result" workflow.
3. It runs automatically every 20 minutes, but you can trigger it manually
   right away: click the workflow, then **Run workflow**.
4. Check the run's logs to confirm it worked. If a new result was posted,
   check your Telegram channel too.

That's it -- from here, the workflow keeps checking every 20 minutes on its
own, and Manel Bot will post whenever Celta finish a match.

## Testing the bot

There's no real match finishing on demand, so testing the "does Telegram
actually receive a message" part is separated from the "does it correctly
read football-data.org" part.

**Test that Telegram posting works (no real match needed):**

Run the script with `--test-telegram` -- it picks a random category out of
all 16 (comeback win, blowout loss, flat draw, a last-minute winner, a
win with a man sent off, etc. -- see "How it works" above) with made-up
teams, score, and (for some categories) fake scorer/assist/red-card data,
builds the message the exact same way a real result would (random phrase
from `phrases.py` included), and sends it to every configured channel. It
never touches football-data.org, TheSportsDB, or `state.json`. **Note:**
the message is not labelled as a test -- it looks exactly like a real
result with a
made-up score, so only run this when that won't confuse anyone reading the
chat.

- From the **Actions** tab: click **Run workflow**, tick the **test_mode**
  checkbox, then run. This uses your real repository secrets, so it's the
  easiest way to test since you already set those up there.
- Locally (if you've done step 5 above and have a `.env` file):

  ```bash
  export $(grep -v '^#' .env | xargs)
  python main.py --test-telegram
  ```

Either way, check the configured channel(s) for the sample result message.

**About testing a real result end-to-end:** the very first time the real
(non-test) workflow runs, it won't post anything even if Celta have a
recent finished match -- by design, it just records that match as "already
seen" so you don't get an old result posted the moment you set things up
(see "First-run bootstrap" in `main.py`). From the next new result onwards,
it posts normally. If you want to see a real result posted sooner, you can
manually edit `state.json`, set `"last_processed_match_id"` to some old
value that isn't Celta's actual latest finished match id, commit it, and
run the workflow -- it'll treat the latest match as new and post it for
real using live data.

## Project files

| File | Purpose |
|---|---|
| `main.py` | The core script: two independent checks (La Liga/Champions League via football-data.org, everything else via TheSportsDB), each fetching match data, classifying the result into a category, posting to Telegram, and updating its own state. |
| `phrases.py` | Galician phrase banks, one per category (21 total) -- edit freely. |
| `requirements.txt` | Python dependencies (just `requests`). |
| `state.json` | Tracks the last match/event id each check posted (plus per-competition win/loss streaks), so results aren't duplicated. |
| `.env.example` | Template showing which environment variables are needed for local testing. |
| `.github/workflows/check_result.yml` | The scheduled GitHub Actions workflow. |

## Troubleshooting

- **Nothing gets posted, ever:** check the Actions logs for the exact error
  message -- `main.py` prints a clear `ERROR:` line for API failures,
  missing environment variables, etc.
- **"required environment variable ... is not set":** a secret is missing
  or misspelled in your repository settings.
- **Telegram API errors (e.g. "chat not found" or "not enough rights"):**
  double-check `TELEGRAM_CHANNEL_ID`, and that the bot is an admin (for a
  channel) or at least a member (for a group) with permission to post
  messages. For groups, also check whether the id changed because the group
  was upgraded to a supergroup (see step 2 above).
- **football-data.org returns an error:** double-check
  `FOOTBALL_DATA_API_KEY` and `CELTA_TEAM_ID`.
- **A `WARNING: TheSportsDB ...` line in the logs:** this is expected and
  harmless -- it just means the result was posted without scorer names/
  late-goal detail that run (TheSportsDB was unreachable, didn't have that
  match yet, or its data didn't fully add up). It never stops the actual
  result from being posted. Only worth investigating if it happens on
  every single run.
