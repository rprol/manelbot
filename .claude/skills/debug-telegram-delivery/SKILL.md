---
name: debug-telegram-delivery
description: Diagnose why Manel Bot failed to deliver a Telegram message — "chat not found", "bot can't initiate conversation with a user", 401/403 errors, or a channel/group that used to work and suddenly doesn't. Use whenever a workflow run's "Run result checker" step shows a Telegram API error, or when setting up a new channel/group.
---

# Debug Telegram delivery failures

`send_telegram_message()` in `main.py` never raises — it logs the Telegram
API's JSON error response and returns `False`. That logged message tells
you exactly what's wrong; match it against the table below rather than
guessing.

## Error → cause → fix

| Error from Telegram API | What it actually means | Fix |
|---|---|---|
| `401 Unauthorized` | `TELEGRAM_BOT_TOKEN` is wrong or revoked | Get a fresh token from @BotFather, update the repo secret |
| `400 Bad Request: chat not found` | The `chat_id` value is malformed or the bot was never added to that chat | See "Getting the right chat id" below |
| `403 Forbidden: bot can't initiate conversation with a user` | The configured id is a **person's** private chat id (positive number), not a group/channel id (negative). Classic mistake: grabbing the wrong `id` field out of a JsonDumpBot response | Re-derive the id — see below |
| `403 Forbidden: bot is not a member of the...chat` / `not enough rights` | Bot isn't in the chat, or (for channels specifically) isn't an admin | Add the bot; for **channels** it must be an **Administrator** with post permission — Telegram enforces this. For **groups**, plain membership is enough unless the group restricts regular members from posting |
| Previously-working group id suddenly fails with "chat not found" | Telegram silently upgraded the group to a **supergroup**, which gets a new `-100...` id | Re-fetch the id (below) and update the secret |

## Getting the right chat id

Don't hand-convert ids from a Telegram Web URL — that's the client's
internal id, not the Bot API's `chat_id`, and the conversion is easy to
get wrong. Use one of these instead:

**Method A — from the bot's own updates (most reliable for groups):**

1. In the target chat, send a command explicitly at the bot:
   `/start@YourBotUsername` (slash commands reach the bot even with
   privacy mode on; plain text messages might not).
2. `curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool`
3. Find `message.chat.id` in the response. Negative number, `"type"` is
   `"group"`, `"supergroup"`, or `"channel"`. That's the value.

**Method B — forward-to-dump-bot (works without needing bot admin first,
useful for private channels):**

1. Forward any message from the target chat to **@JsonDumpBot** (or
   **@RawDataBot**) in a private chat.
2. Look for `forward_origin.chat.id` (Bot API 7.0+) or the older
   `forward_from_chat.id` — **not** the top-level `message.chat.id`, which
   is the id of your DM with the dump bot itself (a positive number = your
   own user id — using this by mistake is exactly what produces the 403
   "can't initiate conversation with a user" error above).

**Verify before spending an Actions run on it:**

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getChat?chat_id=<CANDIDATE_ID>"
```

`"ok":true` with chat details back = correct. `"ok":false` = try again.

## Multi-channel note

`TELEGRAM_CHANNEL_ID` can hold a comma-separated list. One bad id in the
list doesn't block the others — `main.py` tries every entry and only skips
updating `state.json` if *all* of them fail. Check the log for which
specific id failed rather than assuming the whole list is broken.
