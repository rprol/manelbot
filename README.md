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

The Galician phrases in [phrases.py](phrases.py) were drafted by an AI. Each
outcome always starts with a fixed opener you specified -- "Ben, Celta,
ben!" for wins, "Regular, Celta, regular!" for draws, "Mal, Celta, mal!" for
losses -- followed by an AI-drafted continuation that varies per phrase.
**Please have a native Galician speaker read through the continuations in
`WIN_PHRASES`, `DRAW_PHRASES`, and `LOSS_PHRASES` in that file and correct
anything that sounds wrong before you start posting to a real channel.**
The file is plain Python lists of strings, so editing, replacing, or adding
phrases is just editing text.

## How it works

1. `main.py` reads `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`,
   `FOOTBALL_DATA_API_KEY`, and `CELTA_TEAM_ID` from environment variables.
2. It asks [football-data.org](https://www.football-data.org/) for Celta's
   most recent *finished* La Liga matches.
3. It compares the latest finished match's id against the one saved in
   `state.json`.
   - If it's the same, nothing happened since last time -- the script exits
     quietly.
   - If it's different, that's a new result: the script works out whether
     Celta won, drew, or lost (checking both home and away cases), picks a
     random Galician phrase for that outcome from `phrases.py`, and posts a
     message like:

     > Ben, Celta, ben! Partido gañado con mérito! 🔵⚪ Celta 2-1 Getafe

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

### 2. Create (or choose) a Telegram channel and add the bot as admin

1. Create a Telegram channel (or use an existing one) where results should
   be posted. You can repeat this for more than one channel -- see below.
2. Open the channel's settings → **Administrators** → **Add Admin**, and
   add your bot. It needs permission to post messages.
3. Figure out your `TELEGRAM_CHANNEL_ID`:
   - If the channel is public, it's just its `@username` (e.g.
     `@celta_results`).
   - If the channel is private, it's a numeric id, usually a large negative
     number like `-1001234567890`. One way to get it: post any message in
     the channel, then visit
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
     look for `"chat":{"id": ...}` in the response.

**Posting to more than one channel:** add the bot as admin to each channel,
then set `TELEGRAM_CHANNEL_ID` to a comma-separated list, e.g.:

```
TELEGRAM_CHANNEL_ID=@celta_results,-1001234567890
```

The bot posts the same message to every channel in the list. If one channel
fails (e.g. the bot was removed as admin there) the others still get the
message -- check the workflow logs for a warning naming which channel(s)
failed.

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

## Project files

| File | Purpose |
|---|---|
| `main.py` | The core script: fetches match data, decides the outcome, posts to Telegram, updates state. |
| `phrases.py` | Galician phrase banks (WIN/DRAW/LOSS) -- edit freely. |
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
  double-check `TELEGRAM_CHANNEL_ID` and that the bot is an admin of the
  channel with permission to post messages.
- **football-data.org returns an error:** double-check
  `FOOTBALL_DATA_API_KEY` and `CELTA_TEAM_ID`.
