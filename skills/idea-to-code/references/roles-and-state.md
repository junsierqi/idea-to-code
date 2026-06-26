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

## User-Visible Role Display

Every user-visible idea-to-code message must identify the active role and execution source in its prefix:

```text
[idea-to-code][Planner/agent]
[idea-to-code][Implementer/agent]
[idea-to-code][Validator/agent]
[idea-to-code][Reviewer/subagent]
[idea-to-code][Closer/agent]
```

Use `/agent` when the current assistant is performing that role. Use `/subagent` only when a real delegated subagent actually ran the role and returned usable evidence. If a subagent was planned, unavailable, timed out, or produced unusable evidence, keep the visible source as `/agent` and record the fallback or timeout in role evidence.

## Role Execution Mode

Before implementation, choose a mode and record it in Planner evidence:

- `same-agent`: one agent performs all role gates sequentially.
- `hybrid-team`: the main agent performs some roles and at least one real subagent performs Validator or Reviewer work.
- `independent-team`: multiple real agents perform separate role gates or disjoint implementation slices.

Selection rules:

- Check real tool availability first. Use visible subagent/team tools when they are available and materially improve independence.
- Confirm delegation health with a bounded ping or recent successful subagent result before treating subagent availability as usable for evidence.
- Keep delegated tasks narrow: one role, one question, one file set, clear output shape, and no broad repository exploration unless explicitly required.
- Prefer `hybrid-team` for complex, high-risk, user-intent-sensitive, cross-module, or closeout-sensitive work.
- Prefer independent Validator or Reviewer over independent Planner when the main risk is biased acceptance of the implementer's own work.
- Use `same-agent` for small low-risk work, unavailable subagent tools, unclear delegation boundaries, or when delegation would create write conflicts.
- Do not fabricate independent work. If a subagent did not actually run, evidence must say `same-agent` or explain the fallback.
- If a subagent times out or returns no usable evidence, close it, record the timeout, split the task smaller or fall back to `same-agent`, and do not count that attempt as independent evidence.
- Do not infer the cause of a timeout from convenience. If cause matters, run comparison tests such as ping, scoped review, and broader review. Record only observed results; leave the root cause `unverified` when the evidence does not isolate it.

## Delegation Healthcheck Protocol

Use this protocol before claiming `/subagent` in a user-visible role/source prefix or recording independent Validator/Reviewer evidence. Skip it only when the current session already has a recent successful subagent result for the same tool path and similar scope.

Healthcheck steps:

1. `Ping`: delegate a tiny bounded request such as "reply with READY" to confirm the subagent can start and return.
2. `Scoped review`: delegate one narrow file set, one role, and one question with a concrete output shape.
3. `Broader review`: for complex work only, delegate a wider but still bounded review after the scoped review succeeds.
4. `Timeout/fallback record`: if any step times out or returns unusable output, record the observed failure and fall back to `same-agent` or split the delegated task smaller.

Usable subagent evidence must include:

- role delegated: `Validator` or `Reviewer`
- scope delegated: files, TASK/REQ IDs, or question
- result returned before timeout
- concrete findings or validation evidence
- whether the result is used as independent evidence or rejected as unusable

Do not display `/subagent` for planned, timed-out, unavailable, or unusable delegation. Use `/agent` and record the fallback reason instead.

When using `same-agent`, Reviewer evidence must explicitly say `same-agent review` and cover user-intent fit, REQ coverage, acceptance examples, counterexamples, non-goal boundaries, diff scope, validation strength, unverified items, and residual risks.

When using `hybrid-team` or `independent-team`, evidence must name which role ran independently and include the subagent result or identifier when available.

## Role Responsibilities

- Planner: produces `00-idea.md` content: goal, Controlled Exploration, requirements, task classification, acceptance matrix, design, and implementation plan.
- Implementer: makes scoped changes and records TASK/IMP evidence tied to files or modules.
- Validator: records validation type, command/runtime/manual evidence, and covered REQ IDs.
- Reviewer: reconciles requested scope, actual diff, acceptance matrix, verification strength, risks, and boundary cases.
- Closer: runs after pre-close verify; records final decision, triggers finalize, and verifies the finalized bundle.

## Role Evidence Checklist

Use this checklist before recording role evidence. If `role record` rejects evidence, inspect this checklist or run the read-only helper:

```bash
python ".../idea_to_code_bundle.py" role explain --role <planner|implementer|validator|reviewer|closer>
```

`role explain` is not a state transition, not a role gate, and not a replacement for `role record`. It only prints the evidence expectations in a machine-readable shape.

### Planner Evidence

Must include:

- planned REQ IDs
- 00-idea.md, Controlled Exploration, requirements, acceptance matrix, or implementation plan
- TASK/IMP IDs or implementation-plan reference
- planning work, not validation, review, or closeout work

Must not include:

- claims that implementation or validation already happened unless those role gates have actually run
- vague phrases such as planned, ready, or looks good without REQ/TASK context

### Implementer Evidence

Must include:

- implemented TASK/IMP IDs
- changed files or modules
- implementation verbs such as added, updated, changed, created, or refactored
- implementation work, not planning, validation, review, or closeout work

Must not include:

- test-only evidence without naming the implemented change
- broad claims such as done without file/module and TASK/IMP context

### Validator Evidence

Must include:

- covered REQ IDs
- one validation type from the approved validation taxonomy
- validation action, command, or inspection path
- validation work, not another role

Must not include:

- a passing command without explaining the validation type or covered requirement
- unverified evidence without naming the missing dependency or reason

### Reviewer Evidence

Must include:

- scope, coverage, boundary, architecture, acceptance matrix, or residual risk review
- reviewed requirements, implementation, verification, or REQ/TASK/IMP IDs
- review work, not another role
- same-agent review when the reviewer is not a real independent subagent

Must not include:

- independent-review claims unless a real subagent/person actually ran and returned evidence
- acceptance claims that ignore counterexamples, non-goals, unverified items, or residual risks

### Closer Evidence

Must include:

- pre-close verify passed
- final decision, gate alignment, or REQ coverage
- closeout work, not another role
- accepted closeout-status wording such as `prior role evidence is current` when referring to earlier role gates

Must not include:

- closeout before Reviewer evidence and pre-close verify
- accepted/completed claims when coverage, validation, role evidence, or final verify is still missing
- claims that the closer performed planning, implementation, validation, or review work

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

- `User Goal Fit`: how this requirement serves the restated user outcome
- `Acceptance Examples`: concrete examples that should pass
- `Counterexamples`: wrong-but-working outputs that must not be accepted
- `Non-Goal Boundaries`: related outcomes that are intentionally out of scope
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

Command success is not enough for acceptance. A row is weak if it only says the build, tests, or implementation ran but does not explain how the observed result matches the user's intended outcome. For small tasks, one compact example and one counterexample may be enough. For larger tasks, each major REQ needs its own examples and counterexamples.

## Trace Coverage

- Register every requirement with `requirement add`.
- Every meaningful checkpoint must use `--covers`.
- `verify` fails if any open requirement has no covering milestone.
- `finalize --gate-status pass` fails when any open requirement is uncovered, failing, or partial.
- Close requirements only when the user explicitly drops, defers, or supersedes them.

## Evidence Quality

Evidence must be English-only ASCII and concrete. Good evidence names REQ/TASK/IMP IDs, files, commands, validation type, observed behavior, or artifacts.

Vague evidence such as `done`, `tested`, `reviewed`, or `looks good` is invalid.
