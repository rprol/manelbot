---
name: verify-football-api
description: Diagnose football-data.org API key and CELTA_TEAM_ID issues for Manel Bot by running known-good checks against the live API. Use when match data looks wrong, the bot isn't detecting a result it should, before deploying to confirm credentials work, or whenever someone is about to change CELTA_TEAM_ID.
---

# Verify football-data.org API access

Manel Bot depends on two football-data.org values: `FOOTBALL_DATA_API_KEY`
and `CELTA_TEAM_ID` (defaults to `558` — see `DEFAULT_CELTA_TEAM_ID` in
`main.py`). This skill confirms both are correct using the exact endpoint
the bot itself calls, so nothing is verified against the wrong shape of
data.

Don't guess at the key's validity or the team id — always check live.

## Steps

1. **Get the key.** Prefer asking the person to run the commands below
   themselves (keeps the key out of the conversation). If they'd rather
   paste it, that's fine too — just don't persist it anywhere beyond the
   current check.

2. **Confirm the key works and the team id is right**, by searching the
   full PD (La Liga) teams list for "Celta":

   ```bash
   curl -s -H "X-Auth-Token: YOUR_KEY" "https://api.football-data.org/v4/competitions/PD/teams" \
     | python3 -m json.tool | grep -i -B 3 "celta"
   ```

   Expect to see `"id": 558` next to `"name": "RC Celta de Vigo"`. If the
   id differs from what's currently configured, that's the bug — update
   `CELTA_TEAM_ID` (repo secret) and flag it, don't silently "fix" the
   default in code without saying so.

3. **Confirm the actual endpoint the bot polls returns what `main.py`
   expects** (this matters more than step 2 — it's the real code path):

   ```bash
   curl -s -H "X-Auth-Token: YOUR_KEY" \
     "https://api.football-data.org/v4/teams/558/matches?status=FINISHED&competitions=PD&limit=1" \
     | python3 -m json.tool
   ```

   Check for:
   - HTTP 200, not 403/429 (429 = rate limited; free tier is 10 req/min)
   - `matches[0].score.fullTime` present
   - `matches[0].score.halfTime` present — `classify_match()` in `main.py`
     needs this to detect comebacks/collapses/rallies; without it, every
     result falls back to the `_STANDARD`/`_FLAT` category

4. **Report plainly**: which checks passed/failed, and if something's
   wrong, name the exact secret or file to fix (e.g. "update the
   `CELTA_TEAM_ID` repo secret to 558" or "the free-tier plan appears to
   be rate-limiting — check call frequency").

## Known limitation (don't try to "fix" this)

The free tier has no minute-by-minute goal data — confirmed empirically by
fetching `/v4/matches/{id}` for a real match and finding no `goals` array.
Half-time vs full-time score is as granular as it gets. Don't spend time
looking for a `goals` field or a way to get exact goal minutes on the free
plan; it isn't there.
