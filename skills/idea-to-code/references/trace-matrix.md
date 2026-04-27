# Trace Matrix

## Purpose

Connect every requirement the user asked for to a milestone that delivered it and to the evidence that verified it. Without this, "the feature is done" is a guess. With it, `verify` can mechanically prove coverage.

## Concepts

- **Requirement**: one thing the user asked for. Has an `id` (short, stable, e.g. `REQ-1`, `AUTH-login`, `C1`), a `description`, a `type` (`functional` | `nonfunctional` | `constraint`), and a `state` (`open` | `closed`).
- **Milestone**: a unit of implemented + verified work. Lists which requirement IDs it covers via `--covers REQ-1,REQ-3`.
- **Aggregate gate**: the worst gate-status across all milestones covering a given requirement. Any `fail` → `fail`; any `partial` or missing → `partial`; all `pass` → `pass`; no coverage → `uncovered`.

## Rules

1. **Assign an ID before implementing.** If it doesn't have a REQ-ID, it doesn't go in the milestone. Record via `requirement add`.
2. **Every milestone must name its REQ-IDs** via `--covers`. Milestones that touch infra / tooling only can list `[]` but should still be honest about that.
3. **`verify` enforces coverage.** It exits non-zero when an open requirement has no covering milestone, or when the aggregate gate is `fail`.
4. **A failing gate doesn't disappear.** A later milestone that passes can raise the aggregate to `partial` but cannot rewrite an earlier `fail` to `pass`. Work through failures with additional milestones, not by hiding them.
5. **Closed requirements** (`requirement close --id REQ-X --note "…"`) are excluded from coverage enforcement. Use this for requirements the user explicitly dropped, not for ones you didn't get to.

## Commands

```bash
BUNDLE='python "<path-to-idea-to-code>/scripts/manage_delivery_bundle.py"'

# Register
$BUNDLE requirement add --root "$(pwd)" --slug <slug> \
    --id REQ-1 --description "User can create a note" --type functional

# Inspect coverage
$BUNDLE requirement list --root "$(pwd)" --slug <slug>

# Close a dropped requirement
$BUNDLE requirement close --root "$(pwd)" --slug <slug> \
    --id REQ-4 --note "User dropped image upload from this slice."

# Link a milestone to requirements
$BUNDLE checkpoint --root "$(pwd)" --slug <slug> \
    --milestone "notes CRUD" --delivered "..." --verified "..." \
    --next "..." --focus "..." --gate "..." --gate-status pass \
    --covers "REQ-1,REQ-2"
```

## Matrix In The Final Report

`finalize` automatically renders a `## Trace Matrix` section with columns:

| ID | Type | State | Description | Covered By | Aggregate Gate |

Read it at acceptance time. Rows with `_(uncovered)_` or `fail` in Aggregate Gate are the reasons the bundle is not `accepted`.

## Bilingual Report

When you need a secondary-language version of the final report:

1. Run `finalize` so the primary `05-final-report.md` (including the matrix) is up to date.
2. Run:
   ```bash
   $BUNDLE translate-report --root "$(pwd)" --slug <slug> \
       --source 05-final-report.md --lang en
   ```
   Output: `05-final-report.en.md` (or `.zh.md`, `.ja.md` depending on `--lang`). Section headings are translated; body prose is left verbatim.
3. Use Edit to translate the body lines. Keep the same structure so the matrix stays aligned.
4. Never translate from memory without running `translate-report` first — the structure drifts and rows get reordered.

## Anti-Patterns

- Inventing requirements mid-finalize to paper over uncovered gaps. If the requirement didn't exist before the milestone started, close it or ask.
- Listing every REQ on every milestone "just in case". `--covers` is a claim that the milestone actually delivered against that requirement.
- Flipping a `fail` gate to `pass` in a later milestone without a retest. Run the retest, then add a new milestone with its real gate status.
