---
name: validate-phrases
description: Structurally validate phrases.py after editing it — confirms every phrase starts with the correct fixed opener for its category, every category classify_match()/select_category() can return in main.py has a non-empty phrase list, and there are no typo'd category keys. Use after any edit to phrases.py, or before merging a phrase-wording change.
---

# Validate phrases.py structure

This checks *structure only* — never wording or Galician accuracy. Nobody
including Claude is a substitute for the native-speaker review that
`phrases.py` and the README explicitly call for; don't claim a phrase
"sounds right." What this skill catches is code-breaking mistakes: a
missing category, a typo'd key, a phrase that forgot its required opener.

## What must hold

- `phrases.PHRASES` has exactly these 22 keys:
  - The 16 `classify_match()` can return directly: `WIN_COMEBACK`,
    `WIN_BLOWOUT`, `WIN_NARROW`, `WIN_STANDARD`, `WIN_LATE`, `WIN_TEN_MEN`,
    `DRAW_RALLY`, `DRAW_SQUANDERED`, `DRAW_FLAT`, `DRAW_LATE`,
    `LOSS_COLLAPSE`, `LOSS_BLOWOUT`, `LOSS_NARROW`, `LOSS_STANDARD`,
    `LOSS_LATE`, `LOSS_TEN_MEN`. The `*_LATE` and `*_TEN_MEN` categories
    are only reachable when TheSportsDB goal/card data is available (see
    `fetch_thesportsdb_match_events()`) — a match with no such data, or
    with a `goals` list whose counts don't add up to the real score
    (TheSportsDB's data can be incomplete), never produces one.
  - 4 more `select_category()` can additionally return, layered on top of
    (and sometimes overriding) `classify_match()`'s result: `WIN_STREAK_2`,
    `WIN_STREAK_3`, `LOSS_STREAK_2`, `LOSS_STREAK_3` (2+/3+ wins or losses
    in a row, tracked GLOBALLY across every competition in
    `state["streak"]` — only reachable when the base category would
    otherwise have been `WIN_STANDARD`/`LOSS_STANDARD`), and
    `WIN_ADVANCED_ROUND` (defaults to any Copa del Rey win — see
    `COMPETITIONS_WHERE_WIN_MEANS_ADVANCING`).
  - 2 more only `check_other_competitions_result()` can return, via
    `_check_two_legged_tie()`, which can override *any* of the above
    entirely: `WIN_ADVANCED_ROUND` again (confirmed by real two-leg
    aggregate this time, not just the default) and `LOSS_ELIMINATED`
    (aggregate loss of a two-legged tie — this one has NO other path to
    it, so if it's ever unreachable in a review of `main.py`, that's a
    real bug, not just an unused category).
  - Any category not in this set of 22 is either a typo or dead code —
    either way, worth flagging.
- Every phrase in a `WIN_*` list starts with `"Ben, Celta, ben!"`.
- Every phrase in a `DRAW_*` list starts with `"Regular, Celta, regular!"`.
- Every phrase in a `LOSS_*` list starts with `"Mal, Celta, mal!"`.
- No category's list is empty (an empty list makes `random.choice` crash
  the moment that category is hit).
- No phrase mentions a specific competition (e.g. "Copa del Rey",
  "Champions League") — messages are deliberately competition-agnostic in
  their wording (an earlier `[competition]` prefix was tried and removed);
  a phrase naming one would be actively misleading when reused for a
  different competition.

## Steps

1. Run this from the repo root:

   ```bash
   python3 -c "
   from phrases import PHRASES

   expected_categories = {
       'WIN_COMEBACK', 'WIN_BLOWOUT', 'WIN_NARROW', 'WIN_STANDARD', 'WIN_LATE', 'WIN_TEN_MEN',
       'WIN_STREAK_2', 'WIN_STREAK_3', 'WIN_ADVANCED_ROUND',
       'DRAW_RALLY', 'DRAW_SQUANDERED', 'DRAW_FLAT', 'DRAW_LATE',
       'LOSS_COLLAPSE', 'LOSS_BLOWOUT', 'LOSS_NARROW', 'LOSS_STANDARD', 'LOSS_LATE', 'LOSS_TEN_MEN',
       'LOSS_STREAK_2', 'LOSS_STREAK_3', 'LOSS_ELIMINATED',
   }
   prefixes = {
       'WIN': 'Ben, Celta, ben!',
       'DRAW': 'Regular, Celta, regular!',
       'LOSS': 'Mal, Celta, mal!',
   }

   problems = []

   missing = expected_categories - PHRASES.keys()
   extra = PHRASES.keys() - expected_categories
   if missing:
       problems.append(f'Missing categories: {missing}')
   if extra:
       problems.append(f'Unexpected categories (typo? not used by classify_match/select_category): {extra}')

   for category, phrase_list in PHRASES.items():
       if not phrase_list:
           problems.append(f'{category} has zero phrases')
           continue
       base = category.split('_')[0]
       expected_prefix = prefixes.get(base)
       if not expected_prefix:
           continue
       for p in phrase_list:
           if not p.startswith(expected_prefix):
               problems.append(f'{category} phrase missing \"{expected_prefix}\" prefix: {p!r}')

   if problems:
       print('FAILED:')
       for p in problems:
           print(f'  - {p}')
   else:
       total = sum(len(v) for v in PHRASES.values())
       print(f'OK: {len(PHRASES)} categories, {total} phrases, all prefixes correct.')
   "
   ```

2. If it also matters whether `main.py`'s `classify_match()`/
   `select_category()` can still return exactly this category set (e.g.
   after editing either function), cross-check their `return` statements
   against `expected_categories` above by reading them directly — there's
   no automated way to extract that without running real match data
   through them.

3. Report the result plainly. Don't silently "fix" a wording issue this
   check doesn't cover — a passing structural check says nothing about
   whether the Galician is correct.
