# Roles And State

## Purpose

Use this reference for role responsibilities, task states, state transitions, task classification, acceptance matrix, and REQ coverage.

## Role Order

Record roles in this order for the current `plan_revision`:

1. Planner
2. Implementer
3. Validator
4. Reviewer
5. Closer

The same agent may perform all roles, but each role requires separate evidence. Do not claim another person or subagent performed a role unless that actually happened and evidence was recorded.

## Role Responsibilities

- Planner: produces `00-idea.md` content: goal, requirements, task classification, acceptance matrix, design, and implementation plan.
- Implementer: makes scoped changes and records TASK/IMP evidence tied to files or modules.
- Validator: records validation type, command/runtime/manual evidence, and covered REQ IDs.
- Reviewer: reconciles requested scope, actual diff, acceptance matrix, verification strength, risks, and boundary cases.
- Closer: runs after pre-close verify; records final decision, triggers finalize, and verifies the finalized bundle.

## Task States

Main states live in `state.json.state`:

- `in_progress`: active work.
- `blocked`: external dependency prevents progress.
- `paused`: user or workflow paused the task.
- `completed`: finalized with `decision=accepted`.
- `closed`: finalized without full accepted completion.

State changes are script-owned:

- `init` creates `in_progress`.
- `block` and `unblock` change blocked state.
- `current pause` and `current resume` change paused state.
- `finalize` changes to `completed` or `closed`.
- `verify` updates verification fields only.
- `role record` records evidence only.

## Task Classification

Before behavior-changing work, record in `00-idea.md`:

- File changes: `yes` or `no`.
- Semantic impact: `yes`, `no`, or `unclear`.
- Tracking required: `yes` or `no`.
- Reason: concrete sentence naming why the work is tracked or untracked.

If semantic impact is unclear, treat the task as tracked.

## Acceptance Matrix

Every open `REQ-*` needs a row covering:

- expected path
- negative or invalid inputs
- boundary cases
- state, persistence, or migration effects
- rollback or cancellation where applicable
- error reporting
- observability
- real product-path effects
- validation type

Weak cells such as `none`, `todo`, or `n/a` cause `verify` to fail unless the task truly makes that dimension irrelevant and explains it concretely.

## Trace Coverage

- Register every requirement with `requirement add`.
- Every meaningful checkpoint must use `--covers`.
- `verify` fails if any open requirement has no covering milestone.
- `finalize --gate-status pass` fails when any open requirement is uncovered, failing, or partial.
- Close requirements only when the user explicitly drops, defers, or supersedes them.

## Evidence Quality

Evidence must be English-only ASCII and concrete. Good evidence names REQ/TASK/IMP IDs, files, commands, validation type, observed behavior, or artifacts.

Vague evidence such as `done`, `tested`, `reviewed`, or `looks good` is invalid.
