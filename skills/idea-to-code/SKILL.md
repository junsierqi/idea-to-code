---
name: idea-to-code
description: Turn product ideas, rough feature concepts, or design directions into delivered software through iterative clarification, architecture, implementation, testing, verification, acceptance, and sustained autonomous delivery. Use when the user wants you to keep iterating on an idea until it is concretely implemented, validated, and ready for review rather than stopping at brainstorming, asking routine next-step questions, or doing a one-off code edit.
---

# Idea To Code

## Overview

Drive an idea from vague intent to verified implementation. Keep moving between clarification, architecture, coding, testing, and acceptance until the request is concretely delivered or blocked by a real external dependency.

## When Is This Skill The Right One

Use it when **at least one** is true:

- the user frames the task as "keep iterating until it works" / "一路做到能跑起来"
- the work spans **≥ 3 milestones or ≥ 2 subsystems / layers**
- the outcome needs verified behavior (tests, runtime, built artifact), not just a code edit
- the request starts as an idea or concept rather than a concrete change list

If the request is a one-shot edit (rename, typo, single-function change), skip this skill and just do the edit.

Prefer `design-to-code` when the driver is a visual design / mockup.

---

## Script Invocation - Cross-Platform

All delivery-bundle operations use a single Python script installed alongside this skill:

```bash
python <path-to-idea-to-code>/scripts/manage_delivery_bundle.py <command> [args]
```

Requires Python 3.8+. Resolve `<path-to-idea-to-code>` to the skill directory before running commands. When this repository root is the current working directory, `python skills/idea-to-code/scripts/manage_delivery_bundle.py ...` is correct. When the skill directory itself is the current working directory, `python scripts/manage_delivery_bundle.py ...` is correct. When the skill is installed under Codex, the path is commonly:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/manage_delivery_bundle.py" <command> [args]
```

**Note on path shorthand**: examples below use `python ".../manage_delivery_bundle.py"` as a placeholder for readability. In actual tool calls, use the resolved absolute path to this skill's bundled script, `python skills/idea-to-code/scripts/manage_delivery_bundle.py` from this repository root, or `python scripts/manage_delivery_bundle.py` from the skill directory.

---

## Workflow

```
Preflight → Clarify → Bundle init → Requirements (REQ-IDs)
   ↓                                      ↓
   └──────────► Milestone loop (implement → verify → checkpoint --covers REQ-X)
                                                                  ↓
                                                    blocked? → block / unblock
                                                                  ↓
                                                  verify → Finalize (+ optional translate-report)
```

Trace matrix is the spine: every requirement has a REQ-ID; every milestone lists which REQ-IDs it covers; `verify` exits non-zero if any open REQ is uncovered; the final report auto-rolls up the matrix.

1. **Preflight** — detect project language/stack; confirm build/test command; confirm git / cwd state. Abort early on a broken baseline rather than masking it later. See `references/preflight.md`.
2. **Restate the outcome in implementation terms.** Write it down, don't keep it only in your head.
3. **If the request is still fuzzy**, convert the idea into a concrete requirement set (`references/requirements-clarification.md`) before coding.
4. **For substantial work** (see threshold above), initialize a delivery bundle:
   ```bash
   python ".../manage_delivery_bundle.py" init \
     --root "$(pwd)" --slug <task-slug> --title "<task title>" [--unique] [--idea "<seed>"]
   ```
   Use `--unique` to prefix the slug with `YYYYMMDD-HHMM` so re-runs of the same feature don't collide.
5. **Fill `01-requirements.md` / `02-prd.md`** with the `update` subcommand — don't leave them as empty templates:
   ```bash
   python ".../manage_delivery_bundle.py" update --root "$(pwd)" --slug <slug> \
     --file requirements --content-file path/to/requirements.md
   ```
5b. **Register REQ-IDs** for the trace matrix — one row per requirement:
   ```bash
   python ".../manage_delivery_bundle.py" requirement add --root "$(pwd)" --slug <slug> \
     --id REQ-1 --description "User can X" --type functional
   ```
   `--type` is `functional | nonfunctional | constraint`. Skip this step only for one-milestone tasks; otherwise the trace matrix is how `verify` detects forgotten requirements.
6. **Inspect the current codebase, docs, and runnable paths** before proposing structure.
7. **Decide the next smallest milestone** that creates real progress and keeps the system runnable.
8. **Implement that milestone end-to-end** instead of stopping at analysis.
9. **Verify the change** with the strongest available local validation (see `references/verification-matrix.md`).
10. **Emit the Gate Verification Block** (see below) before recording the milestone.
11. **Record the milestone**, listing which REQ-IDs it covers:
    ```bash
    python ".../manage_delivery_bundle.py" checkpoint --root "$(pwd)" --slug <slug> \
      --milestone "<name>" --delivered "<changed>" --verified "<how>" --next "<next>" \
      --focus "<current focus>" --gate "<next gate>" --gate-status pass \
      --covers "REQ-1,REQ-3"
    ```
    `--gate-status` is **required** (one of `pass | partial | fail`). Be honest — `finalize` cross-checks every REQ aggregate against your claim and refuses inconsistent ones. `--covers` accepts comma-separated REQ-IDs; unknown IDs cause the command to fail early.
12. **Continue into the next milestone** unless a real blocker or a true architectural fork requires the user.
12b. **Retroactive link (migration path)**: when resuming an older bundle whose historical milestones predate `--covers`, attach requirements after the fact:
    ```bash
    python ".../manage_delivery_bundle.py" link --root "$(pwd)" --slug <slug> \
      --milestone "<exact past name>" --covers "REQ-1,REQ-3"
    ```
    Default merges with any existing covers; pass `--replace` to overwrite. Unknown REQ-IDs are rejected up-front.
13. **On a real blocker**, record it; do not hide it:
    ```bash
    python ".../manage_delivery_bundle.py" block --root "$(pwd)" --slug <slug> \
      --reason "<concrete cause>" --need "<decision or dependency>"
    ```
    Call `unblock --note "<resolution>"` when cleared.
14. **When the task is genuinely complete**, finalize:
    ```bash
    python ".../manage_delivery_bundle.py" finalize --root "$(pwd)" --slug <slug> \
      --summary "<impl summary>" --verification "<verif summary>" \
      --risks "<risks>" --acceptance "<scope delivered>" \
      --gate-status pass --decision accepted \
      [--acceptance-notes "..."] [--deferred "..."]
    ```
    The finalize command rolls up all recorded milestones into `05-final-report.md` and backs up any manually edited report/acceptance files as `.bak` unless `--force` is passed.
15. **Sanity-check the bundle**:
    ```bash
    python ".../manage_delivery_bundle.py" verify --root "$(pwd)" --slug <slug>
    ```
    Non-zero exit = open requirement uncovered, fail gate reached, 00-idea empty, or required files missing. Fix before claiming done.
16. **Optional: bilingual report.** If the user needs a secondary language, clone the primary report's structure:
    ```bash
    python ".../manage_delivery_bundle.py" translate-report --root "$(pwd)" --slug <slug> \
      --source 05-final-report.md --lang en    # or zh, ja
    ```
    The script translates section headings only. Use the Edit tool to translate body prose inline (same structure, same line count). See the bilingual convention below.

---

## Autonomy vs. Clarification — Tiebreaker

Both "don't ask routine questions" and "convert vague ideas to requirements first" apply; resolve conflicts with this rule:

| Situation | Do |
|---|---|
| Ambiguity is about **architecture, user-visible contract, irreversibility, security, or scope** | **Ask** before coding. One clarifying question is cheaper than a wasted milestone. |
| Ambiguity is about **implementation detail** (naming, file layout, internal helper shape) | **Decide and proceed.** Record the decision in the milestone's `--delivered` or in `02-prd.md` `Decisions`. |
| Requirement conflicts with existing architecture or a prior user direction | **Ask.** |
| Missing permission, secret, dependency, service, or environment capability | **Block** the bundle and report. |
| Destructive or irreversible action needed | **Ask.** Exception: resetting auto-generated build artifacts (`build/`, `node_modules/`, `__pycache__`, etc.) is **not** destructive — reset without asking. See `references/preflight.md > Stale Generated Artifacts`. |
| Multiple useful improvements exist, all on the critical path | **Pick the one that best preserves the critical path. Don't ask.** |

Do not stop just to ask whether to continue, whether to do the obvious next hardening step, or whether to follow the established roadmap.

### Do NOT Ask The User

Treat these as auto-decided; act and report in the milestone, do not interrupt the user:

- "Should I proceed?" → always proceed
- "Which naming / layout / helper should I use?" → choose; record in `02-prd.md > Technical Shape` via `update`
- "Should I fix this unrelated small issue I just spotted?" → fix silently if on the critical path, defer otherwise
- "Is this OK so far?" → keep going, report at the next milestone
- "Want me to run tests?" → always run tests when a test command exists
- "Which gate status should I claim?" → the one the evidence supports; never inflate

The ONLY time to interrupt mid-stream:

- baseline build fails on untouched code (preflight)
- missing credential / permission / external service
- destructive or irreversible action about to be taken
- user-visible contract change that the user hasn't sanctioned
- two plausible architectures with materially different long-term costs

### Red Flags — You Are About To Skip A Gate

If any of these thoughts show up, stop and course-correct:

| Thought | Reality |
|---|---|
| "The work is done, just need to deliver" | Finalize IS part of the work. Run it. |
| "I'll skip the gate verification block, it's obvious" | If it's obvious, printing it takes 10 seconds. Print it. |
| "I already checked mentally" | Mental checks leave no evidence. Put it in the block. |
| "The matrix is overkill for this task" | Then there are ≤ 2 requirements and adding them is free. |
| "Translation can come later" | Later = never. Run `translate-report` now if bilingual was requested. |
| "`pass` is basically true, just missing one small flow" | That's `partial`. Name the uncovered flow. |
| "I'll finalize before running `verify`" | `verify` is the acceptance gate. Run it first. |
| "Bundle paperwork slows me down" | The bundle survives your context window. Chat doesn't. |

---

## Operating Rules

- Prefer execution over discussion once the direction is clear.
- Break large ideas into milestones that preserve momentum and verify each milestone before moving on.
- Keep architecture, docs, and code aligned in the same change set when boundaries change.
- For substantial tasks, keep the delivery bundle updated — it is **part of the work product**, not optional bookkeeping.
- Treat tests, builds, and runtime checks as part of completion, not optional follow-up.
- If a request is underspecified **on implementation detail**, make the smallest safe assumption that still moves the build forward. For architectural or scope ambiguity, ask.
- If a blocker is external, record it with `block`, surface it in chat, and continue all unblocked work.

---

## Execution Visibility

Make the skill visible to the user whenever it is active. Start substantial work with a compact status line:

```text
[idea-to-code] Phase: <phase name> | Mode: autonomous|single-milestone | Current: <milestone>
```

Use this marker for progress updates, gate summaries, phase summaries, and final reports. The marker is not decoration; it tells the user the delivery workflow is running rather than ordinary ad-hoc coding.

When the user says "continue", "按建议继续", "一路推行", "执行 C1-C5", or repeatedly asks for the next task, default to **autonomous phase mode**:

- Define the current phase in one sentence.
- List the next 2-5 micro-milestones if they are already clear.
- Continue through those micro-milestones without waiting for the user after each one.
- Stop only for a real blocker, destructive action, user-visible contract fork, or completed phase summary.

If the user asks only for analysis, comparison, review, or status, do not code. Still use the marker when the answer is part of the idea-to-code delivery process:

```text
[idea-to-code] Assessment: <topic>
```

---

## Phase And Micro-Milestone Rules

A **micro-milestone** is a small verified slice that normally takes one focused iteration, such as adding attachment metadata display, transfer-status markers, or a single desktop button plus smoke coverage.

A **phase** is a coherent product capability made of related micro-milestones, such as "C3 attachment desktop experience" or "desktop account onboarding".

Start a new phase when at least one is true:

- The work changes product area, e.g. attachments -> registration -> contacts.
- The user asks to execute a named set such as C1-C5 or C3.
- There are 2+ obvious adjacent micro-milestones on the same user-visible capability.
- A previous phase has reached a natural acceptance boundary.

Automatically emit a phase summary when at least one is true:

- The planned micro-milestones for the phase are complete.
- Three micro-milestones have completed under the same phase.
- The next best task is in a different product area.
- The user asks "progress", "what's next", "compare", "completion", or similar.
- A blocker prevents further progress in the phase.

Do not require the user to say "continue" between obvious micro-milestones inside an active phase.

---

## Gate Mindset

Each phase has an exit gate. Do not quietly move past a failed gate — fix it or say why it remains open.

| Gate | Phase | Pass criteria |
|---|---|---|
| **Understanding** | after requirements | Target outcome, primary user, main flow, success criteria are written. |
| **Implementation** | after coding a milestone | Code is in the repo; the change doesn't leave the project unbuildable. |
| **Verification** | after validation | Build/test/runtime check was actually run; results printed. |
| **Acceptance** | before finalize | Evidence, risks, deferred work are each stated in one place. |

### Gate Verification Block (mandatory before `checkpoint` and `finalize`)

For phase completion, checkpointing a major milestone, or finalizing, print this full block into chat so the gate isn't silently skipped:

```
=== GATE VERIFICATION: <milestone> ===
[ ] Code change lands in: <file(s)>
[ ] Build/compile: <command + result>
[ ] Tests/runtime check: <command + result>
[ ] Behavior observed: <log / output / screenshot reference>
Result: PASS | PARTIAL | FAIL
===
```

If `FAIL` → fix or `block`. If `PARTIAL` → record `--gate-status partial` and name the uncovered flow. Don't claim `PASS` without evidence in the block.

For micro-milestones inside an active phase, use a compact gate instead of the full block:

```text
[idea-to-code] Micro Gate: <milestone> — PASS|PARTIAL|FAIL
Build: <command/result>; Checks: <key tests/results>; Observed: <one behavior>; Next: <next micro-milestone>
```

Record the micro-milestone in the delivery bundle with `checkpoint` when it has a distinct REQ or meaningful acceptance evidence. Otherwise include it in the next phase summary checkpoint.

---

## Human-Readable Execution Report

Maintain a human-readable report in the delivery bundle for substantial autonomous phases. Prefer `.idea-to-code/<slug>/07-execution-log.md` unless the project already has an equivalent report.

Append or update the report at phase start, after meaningful micro-milestones, and at phase summary. Include:

- Requirement understanding: what user outcome is being delivered.
- Development tasks: planned and completed micro-milestones.
- Implementation notes: important files/modules changed, without excessive diffs.
- Test flow: build, unit/store tests, smoke tests, full sweeps as applicable.
- Test report: pass/fail counts and notable observed behavior.
- Acceptance: whether the user-visible phase is pass/partial/fail.
- Deferred work and risks: explicit follow-ups and why they are deferred.

This report complements `status.json`; it should be readable by a human resuming the project without scanning chat history.

Phase summaries must be completion-first. Do not replace the completion report with only next-step suggestions. Always report in this order:

1. Phase goal: the product outcome the phase was meant to deliver.
2. Requirement understanding: what user need was implemented.
3. Completed tasks: micro-milestones finished in this phase.
4. Implementation summary: important modules/files changed and behavior added.
5. Test flow: build, targeted tests, smoke tests, full sweeps as applicable.
6. Test results: exact pass/fail evidence and scenario counts when available.
7. Acceptance conclusion: PASS, PARTIAL, or FAIL with a concrete reason.
8. Deferred work and risks: what remains and why it is not part of this phase.
9. Next-phase recommendation: the next best product area after the phase is accepted.

Use this shape in chat and mirror it into `07-execution-log.md` for substantial phases.

---

## Completion Standard

Do not treat a task as complete just because code was written. Consider the task complete only when all applicable items below are addressed:

- implementation exists in the repository
- impacted docs are updated
- the strongest available local tests or runtime checks were run across the implemented flow, not just a narrow happy path
- known gaps and follow-up work are explicit
- the user can see the result in code, output, or behavior

For a stronger close-out pass, read `references/acceptance-checklist.md` before declaring a substantial task finished.
For a more formal acceptance pass, read `references/task-acceptance-template.md`.

---

## Milestone Pattern

For large ideas, use this order unless the repository strongly suggests otherwise:

1. scope and boundaries
2. protocol and data model
3. control-plane behavior
4. local state model
5. user-facing flow
6. persistence and reliability
7. hardening, tests, and acceptance cleanup

See `references/milestone-template.md` for more detail.

---

## Response Style

- Keep updates concise and execution-focused.
- Report progress in terms of delivered capability, not effort spent.
- End each iteration with the next concrete move when more work remains.
- Distinguish clearly between completed work, verified work, and still-assumed work.
- Prefer milestone reports over frequent conversational check-ins once execution is underway.
- At the end of each completed milestone, post the Gate Verification Block + a short milestone report (what delivered / how verified / what's next). Mirror it into the bundle via `checkpoint`.

---

## Bilingual Report Convention

When the user or stakeholders need reports in two languages:

- Primary report is the one `finalize` produces: `05-final-report.md`.
- Secondary report lives alongside it as `05-final-report.<lang>.md` (e.g. `.en.md`, `.zh.md`, `.ja.md`). Same structure, same line count.
- Generate the skeleton with `translate-report --lang <lang>` — that command translates section headings and adds a banner comment. **It does not translate prose**; you translate the body lines yourself with Edit.
- Don't produce translations from memory without the skeleton — the structure drifts and the matrix rows get reordered. Always start from the skeleton.
- When the user speaks only one language, one report is enough — do not invent a second.

---

## Final Delivery Report

For substantial tasks, `finalize` generates `05-final-report.md` covering:

- target outcome
- milestone-by-milestone rollup (auto-populated from recorded milestones)
- implementation summary
- verification and gate status
- visual evidence placeholder
- risks and deferred work

For screenshot and evidence collection rules, read `references/evidence-capture.md` when the task has visible UI, rendered output, or other inspectable runtime behavior.

For the report structure, read `references/final-report-template.md`.

---

## Reference

Read only the references needed for the current task:

- `references/preflight.md` — environment checks before the delivery loop starts
- `references/trace-matrix.md` — REQ-ID rules, coverage semantics, bilingual report convention
- `references/delivery-loop.md` — basic iteration contract
- `references/requirements-clarification.md` — converting vague ideas into buildable requirements
- `references/prd-template.md` — concise product and implementation brief
- `references/milestone-template.md` — decomposing larger requests
- `references/artifact-workflow.md` — full reference for every `manage_delivery_bundle.py` subcommand
- `references/autonomy-default.md` — default execution and question gating
- `references/acceptance-checklist.md` — before closing substantial work
- `references/task-acceptance-template.md` — formal task acceptance review
- `references/blockers-and-change.md` — scope changes or blockers
- `references/verification-matrix.md` — broader end-to-end test coverage
- `references/final-report-template.md` — final idea-to-delivery report structure
- `references/evidence-capture.md` — screenshot and runtime evidence collection
