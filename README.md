# Manel Bot 🔵⚪

A small Telegram bot that watches for Celta de Vigo's La Liga results and
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

1. `main.py` reads `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`,
   `FOOTBALL_DATA_API_KEY`, and `CELTA_TEAM_ID` from environment variables.
2. It asks [football-data.org](https://www.football-data.org/) for Celta's
   most recent *finished* La Liga matches.
3. It compares the latest finished match's id against the one saved in
   `state.json`.
   - If it's the same, nothing happened since last time -- the script exits
     quietly.
   - If it's different, that's a new result: the script compares the
     half-time score to the full-time score to work out not just
     WIN/DRAW/LOSS but the *shape* of the match, picks a random Galician
     phrase matching that from `phrases.py`, and posts a message like:

     > Ben, Celta, ben! Ían perdendo e deron a volta ao marcador! Celta 2-1 Getafe

   The categories are (see `classify_match()` in `main.py`):
   - **Win:** comeback (behind at half-time, won) · blowout (won by 3+) ·
     narrow (won by 1) · standard (anything else)
   - **Draw:** rally (behind at half-time, clawed back to a draw) ·
     squandered (led at half-time, dropped it to a draw) · flat (level at
     half-time and full-time)
   - **Loss:** collapse (led at half-time, lost) · blowout (lost by 3+) ·
     narrow (lost by 1) · standard (anything else)

   Note: football-data.org's free tier doesn't include minute-by-minute
   goal data, so things like "last-minute winner" aren't detectable --
   half-time vs full-time is as granular as the data gets.

4. `state.json` is updated with the new match id, and the GitHub Actions
   workflow commits that change back to the repo, so the next scheduled run
   knows this result was already posted.

On the very first run ever (when `state.json` has no recorded match yet),
the bot deliberately does **not** post anything -- it just records the
latest finished match as "already seen". This avoids posting about an old
match the moment you first set the bot up. From the next new result
onwards, it posts normally.

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
all 11 (comeback win, blowout loss, flat draw, etc. -- see "How it works"
above) with made-up teams and score, builds the message the exact same way
a real result would (random phrase from `phrases.py` included), and sends
it to every configured channel. It never touches football-data.org or
`state.json`. **Note:** the message is not labelled as a test -- it looks
exactly like a real result with a made-up score, so only run this when
that won't confuse anyone reading the chat.

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
| `main.py` | The core script: fetches match data, classifies the result into a category, posts to Telegram, updates state. |
| `phrases.py` | Galician phrase banks, one per category (11 total) -- edit freely. |
| `requirements.txt` | Python dependencies (just `requests`). |
| `state.json` | Tracks the last match id that was posted, so results aren't duplicated. |
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
