# Blockers And Change

## Purpose

Use this guide when implementation hits a blocker or the user changes direction mid-iteration.

## Blocker Handling

When blocked:

1. State the blocker concretely — name the exact missing dependency, decision, or capability.
2. Separate blocked work from unblocked work.
3. Continue all safe unblocked work.
4. Record the blocker in the delivery bundle so it is not just a chat comment:

   ```bash
   python ".../manage_delivery_bundle.py" block \
     --root "$(pwd)" --slug <slug> \
     --reason "<concrete cause>" \
     --need   "<what decision or dependency unblocks this>"
   ```

   This flips `status.state` to `blocked` and rewrites `## Current Phase` in `03-milestones.md` to name the blocker.

5. When the blocker clears, close it:

   ```bash
   python ".../manage_delivery_bundle.py" unblock \
     --root "$(pwd)" --slug <slug> \
     --note "<resolution>"
   ```

6. Report the smallest decision or dependency needed to proceed.

## Scope Change Handling

When the user changes the goal:

1. Restate the new goal.
2. Identify what prior work is still useful.
3. Stop doing obsolete work.
4. Choose the next milestone under the new direction.
5. Record the pivot as a milestone with `--gate-status partial` or `fail` where relevant, so the history is honest:

   ```bash
   python ".../manage_delivery_bundle.py" checkpoint \
     --root "$(pwd)" --slug <slug> \
     --milestone "scope pivot: <new goal>" \
     --delivered "<what carried over>" \
     --verified  "n/a — scope change" \
     --next      "<first step under new goal>" \
     --focus     "<new focus>" --gate "<new next gate>" \
     --gate-status partial
   ```

6. Update `01-requirements.md` / `02-prd.md` via the `update` subcommand so future sessions see the current goal, not the old one.

## Never Do

- Do not hide blockers behind vague language.
- Do not keep coding down a dead branch after the goal changed.
- Do not present speculative completion as verified progress.
- Do not call `finalize --decision accepted` on a bundle that is actually blocked or only partially verified — use `accepted-with-followup` or `not-accepted`.
