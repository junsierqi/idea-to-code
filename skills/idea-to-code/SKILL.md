---
name: idea-to-code
description: Turn product ideas, rough requirements, or feature directions into verified software changes through an idea-to-code bundle, intake confirmation, requirements, implementation planning, role-gated execution, validation, review, and structured closeout. Use when the user invokes $idea-to-code, asks to turn an idea into working code, wants Codex to keep iterating until it works, or needs a multi-step implementation managed from idea to accepted delivery.
---

# Idea To Code

## Overview

Drive an idea from vague intent to verified implementation. Keep moving between clarification, architecture, coding, testing, and acceptance until the request is concretely delivered or blocked by a real external dependency.

This skill is an execution workflow for idea-to-code delivery, not a replacement for project governance. If the repository has `AGENTS.md`, `CONTRIBUTING.md`, architecture docs, testing docs, or acceptance rules, treat them as project-local authority and layer this skill underneath them. A task ledger or roadmap records state and evidence; it must not define behavior policy unless the project explicitly gives it that authority.

## Core Operating Contract

When this skill loads, understand its core as: turn an idea into a verified software change through a project-local bundle, not through chat memory. The bundle, script gates, and recorded evidence are the source of continuity.

This skill can:

- capture rough ideas and convert them into requirements, acceptance, design, implementation tasks, validation, review, and closeout;
- decide whether intake needs user confirmation before implementation;
- keep one active task through `.idea-to-code/current.json`;
- split large work into REQ-covered milestones without losing the original goal;
- handle mid-stream clarification, expansion, switch, new-task, pause, block, resume, archive, and finalize flows;
- enforce role evidence for Planner, Implementer, Validator, Reviewer, and Closer;
- produce a structured closeout response.

Standard flow:

```text
route/current -> intake gate -> bundle -> requirements/REQs -> design -> implementation gate
-> implement -> validate -> review -> checkpoint -> pre-close verify -> closer/finalize -> final verify -> structured closeout response
```

Tool-owned gates are not optional and should not be inferred from chat: Intake Gate, implementation ready, REQ coverage, Acceptance Matrix, role evidence, validation type, pre-close verify, finalize, and final verify are enforced by `idea_to_code_bundle.py` and guarded by the regression suite.

This section orients the agent; it does not narrow ordinary coding capability. Use normal engineering judgment inside the confirmed plan, while respecting the gates that keep the idea from drifting.

## When Is This Skill The Right One

Use it when **at least one** is true:

- the user frames the task as "keep iterating until it works" or equivalent
- the work spans **>= 3 milestones or >= 2 subsystems / layers**
- the outcome needs verified behavior (tests, runtime, built artifact), not just a code edit
- the request starts as an idea or concept rather than a concrete change list

If the request is a one-shot edit (rename, typo, single-function change) and the user did not invoke `$idea-to-code` or ask for idea-to-delivery behavior, skip this skill and just do the edit. Once this skill is triggered, always follow the bundle, role evidence, and implementation-gate rules even for a small task.

Prefer `design-to-code` when the driver is a visual design / mockup.

---

## Script Invocation - Cross-Platform

All delivery-bundle operations use a single Python script installed alongside this skill. The path is the same on Windows, macOS, and Linux when you use Codex's shell:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" <command> [args]
```

Requires Python 3.8+. No project-local copy is needed. Never write `python scripts/idea_to_code_bundle.py` - there is no such file in the project.

**Always use this exact literal prefix.** Permission allowlists match it as a string prefix; aliases like `BUNDLE=...` + `eval "$BUNDLE ..."` break the match and trigger a confirmation prompt on every call. Verbose but permission-clean beats clever and prompt-spammy.

To silence the confirmation prompt once, add to `~/.codex/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python \"$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py\" *)"
    ]
  }
}
```

**Note on path shorthand**: examples below use `".../idea_to_code_bundle.py"` as a placeholder for readability. Always invoke with the full `python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py"` prefix so the allow rule matches.

---

## Workflow

## Direct Trigger Behavior

Do not require slash commands. When this skill is triggered, default to autonomous delivery:

1. Create or resume the bundle.
2. Fill intake gate, requirements, task classification, acceptance matrix, design, and implementation checklist.
3. Mark the implementation gate READY only after intake is resolved.
4. Record Planner evidence.
5. Execute the checklist, validate, review, checkpoint, run pre-close verification, close, finalize, and run final verification.

Stop after planning only when the user explicitly says "plan only", "implementation checklist only", "do not edit code", "proposal only", or equivalent. In that case, fill `00-idea.md`, print the implementation checklist, and stop before business-code edits.

Treat "status", "progress", "where are we", or equivalent as read-only status requests: inspect `current.json`, `state.json`, `00-idea.md`, and `01-progress.md`; summarize progress; do not edit product files unless the user also asks to continue.

Treat "stop", "pause", "wait", or equivalent as an immediate pause request: stop after the current safe operation, record a pause note, and do not continue coding until the user resumes.

### Intake Gate

On the first idea/requirement message, record a compact intake in `00-idea.md` before implementation:

- `Understanding`: restate the intended outcome in implementation terms.
- `Assumptions`: list assumptions you would otherwise silently make.
- `Acceptance Criteria`: name the observable result that would satisfy the user.
- `Need Confirmation`: `yes` or `no`.
- `Confirmation Reason`: why confirmation is or is not required.

Opening a bundle is allowed as task capture. Product-code edits are not allowed until `Need Confirmation: no` and the implementation gate is READY.

Use `Need Confirmation: yes` when the idea is ambiguous, risky, architecture-shaping, security-sensitive, destructive, expensive, changes user-visible behavior in multiple plausible ways, or contradicts project governance. Ask the user to confirm or correct the intake before marking implementation ready.

Use `Need Confirmation: no` when the task is clear, low-risk, reversible, and the acceptance criteria can be stated concretely. In that case, restate the intake and proceed autonomously without asking a routine confirmation question.

If the user says the original idea was wrong:

- same idea with corrected details: record `clarification --changes-plan yes`, update intake/requirements/design/implementation, then rerun `implementation ready`;
- added acceptance or boundary case: record `expand --changes-plan yes`;
- replacement direction: record `switch --changes-plan yes` in the same bundle;
- unrelated task: record `new-task --changes-plan no`, archive the current bundle, then initialize the new task;
- canceled idea: archive or close with a concrete reason, do not delete evidence.

During autonomous delivery, do not ask routine "continue?" questions. Work through the implementation checklist until completion. Interrupt only for:

- implementation gate failure or missing implementation-plan details in `00-idea.md`
- architecture/scope ambiguity that changes user-visible behavior
- destructive or irreversible action
- missing credential, permission, external service, or environment capability
- implementation plan contradicts the actual codebase in a way that needs a scope decision
- verification fails and cannot be fixed within the confirmed checklist

If the user provides a new consideration while work is active, classify it as continue, expand, switch, new-task, status, pause, blocked, clarification, or no-op before acting. Do not initialize a new bundle while an unfinished current bundle exists.

Mission-control rule: every non-trivial incoming request must first be routed against `.idea-to-code/current.json`. The active bundle owns the work until it is finalized, archived, paused, or explicitly switched. Treat chat history as secondary; the bundle state decides whether the request continues the current idea, expands it, replaces it, parks it for a separate task, or only asks for status.

Use the read-only router when the classification is not obvious or when resuming after interruption:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" route \
  --root "$(pwd)" \
  --input "<English summary of the incoming user request>"
```

`route` prints the active bundle, recommended classification, whether the plan must change, and the next action. It does not mutate files. After reading the route, record the decision with `user-input record` when a current bundle exists and the request affects execution.

Do not read only `recommended_classification`. Respect these route flags:

- `route_gate` is the current control gate. Treat anything except `execution-ready`, `skip-delivery`, or `read-only` as blocking product-code edits until resolved.
- `can_edit_product_files: false` means no product-code edits yet.
- `requires_resume: true` means run `current resume --reason "<reason>"` before any mutation.
- `requires_unblock: true` means resolve the blocker and run `unblock` before mutation.
- `must_update_plan_before_code: true` means update requirements/design/implementation and rerun `implementation ready` before product-code edits.
- `required_next_commands` is the command checklist to satisfy the gate. Run or deliberately account for each command before proceeding.

Before acting on any mid-stream user input, record how it affects the active task:

```bash
python ".../idea_to_code_bundle.py" user-input record --root "$(pwd)" --slug <slug> \
  --summary "<English summary of the user input>" \
  --classification continue|expand|switch|new-task|status|pause|blocked|clarification|no-op \
  --rationale "<why this classification is correct>" \
  --action "<what happens next>" \
  --changes-plan yes|no
```

Use `--changes-plan yes` for `expand`, `switch`, or `clarification`. That marks the bundle as pending a plan update; `verify` and `finalize` refuse to pass until requirements, design, or implementation is updated. Use `--changes-plan no` for `continue`, `new-task`, `status`, `pause`, or `no-op`; these inputs must not silently rewrite active scope.

Active task routing:

- Same task, different wording: record `continue --changes-plan no`, keep the current bundle, and do not create a duplicate bundle.
- Same task with new acceptance details: record `clarification` or `expand --changes-plan yes`, update requirements/design/implementation, rerun `implementation ready`, and continue.
- Different unrelated task while current work is unfinished: record `new-task --changes-plan no` on the current bundle, run `current archive --reason "<parked reason>"` to park it, then run `init` for the new task. Resume the parked task later with `current set`.
- True replacement of the current goal: record `switch --changes-plan yes`, update the current bundle's plan, and continue in the same bundle.
- Unclear relationship to the current idea: run `route`, inspect `00-idea.md`, `01-progress.md`, and `state.json`, then choose the smallest classification that preserves the user's latest goal.

Publish-quality dogfood coverage: changes to this skill must keep the permanent scenario matrix passing: trivial one-shot edit, medium full lifecycle, large 3+ milestone lifecycle, mid-stream expand, mid-stream switch, resume after interruption, invalid closeout rejection, and multi-task archive/resume. Do not claim the skill is improved if this matrix fails.

```
Preflight -> current.json -> Bundle init/resume -> Requirements -> Design -> Implementation Gate
   |                                                                          |
   +----------> Milestone loop (execute TASK/IMP items -> verify -> gate -> checkpoint --covers REQ-X)
                                                                              |
                                                                blocked? -> block / unblock
                                                                              |
                                                      pre-close verify -> Closer -> Finalize -> final verify -> history/index.jsonl
```

Trace matrix is the spine: every requirement has a REQ-ID; every milestone lists which REQ-IDs it covers; `verify` exits non-zero if any open REQ is uncovered; the final report auto-rolls up the matrix.

Governance and roles are the closeout spine: every tracked task records task classification, acceptance matrix rows, validation type, and Planner / Implementer / Validator / Reviewer / Closer evidence. Read `references/roles-and-state.md` before substantial planning, execution, validation, review, closeout, or after contradicted feedback.

### State Model And Resume Contract

Use `state.json` as the source of truth. Chat history is supporting context only.

- Bundle state: `in_progress`, `blocked`, `paused`, `completed`, or `closed`.
- Execution-log events: `init`, `update`, `user-input`, `requirement-add`, `implementation-ready`, `role-*`, `checkpoint`, `verify`, `block`, `unblock`, `pause`, `resume`, `archive`, and `finalize-*`. These are audit events in `01-progress.md`, not task states.
- Intake gate: `Need Confirmation: yes` blocks implementation ready; update intake to `Need Confirmation: no` only after the user confirms or the plan is safely clarified.
- Implementation gate: `implementation_ready` must be true before product-code edits continue.
- Plan revision: requirements, design, or implementation updates increment `plan_revision` and stale prior role evidence.
- User input decisions: `user_input_decisions` records whether new user input continues, expands, switches, pauses, blocks, clarifies, or has no effect on the task.
- Pending plan update: `pending_plan_update` means user input changed the plan but requirements/design/implementation have not been updated yet; do not edit code or close while this is true.
- Verification state: `last_verify_ok` and `last_verified_plan_revision` show whether current-plan pre-close verification passed.
- Closeout state: `gate_status`, `decision`, and `closeout_status` summarize acceptance after finalize.

On a new session or after interruption:

1. Run `doctor`, `current status`, or `route` with the latest user request.
2. Resolve the active bundle from `.idea-to-code/current.json`.
3. Inspect `state.json`, `00-idea.md`, role evidence, milestones, blocks, and user input decisions.
4. If `state` is `blocked` or `paused`, report the resume condition before editing.
5. If `state` is `paused`, run `current resume --reason "<why work is resuming>"` only after the user resumes.
6. If `pending_plan_update` is true, update requirements/design/implementation before coding.
7. If `implementation_ready` is false, refine the implementation plan and run `implementation ready` before coding.
8. If role evidence is missing or stale for the current `plan_revision`, return to the missing role.
9. If closeout seems ready, rerun `verify`, then Closer/finalize/final verify.

### Bundle Layout

Every new bundle must use this file set:

```text
.idea-to-code/<YYYYMMDD-HHMM-normalized-title>/
  00-idea.md
  01-progress.md
  02-report.md
  state.json
```

File responsibilities:

| File | Responsibility |
|---|---|
| `00-idea.md` | Original idea, requirements, task classification, acceptance matrix, design, and implementation plan. |
| `01-progress.md` | Current phase, local records, role gates, milestone history, verification history, risks, acceptance notes, and timeline. |
| `02-report.md` | Final user-facing delivery report generated by `finalize`. |
| `state.json` | Machine-readable state, plan revision, requirements, role evidence, local records, milestones, blockers, verification, and closeout. |

The script owns this artifact contract. Inspect it with:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" contract
```

Do not add ad hoc top-level Markdown files to a bundle. If a new artifact seems necessary, first update the artifact contract, tests, and documentation in the same tracked task; otherwise use the existing file whose responsibility matches the content.

Roles and files are intentionally many-to-many, not one-to-one. Planner, Implementer, Validator, Reviewer, and Closer are lifecycle gates; the compact bundle files are durable artifacts. A role may read and update several artifacts, and one artifact may contain evidence from several roles. The authoritative mapping is exposed by `contract.role_artifact_map`.

For MaskPilot-style audit visibility:

- Run `status --full` for the machine-readable lifecycle account: requirements, user inputs, role evidence, milestones, blockers, verification state, and closeout.
- Run `ledger --root "$(pwd)" --slug <slug>` or open `01-progress.md` for the human-readable lifecycle event trail.
- Use `record add/list` for observed MaskPilot-style local sub-records: `A` acceptance, `D` discovery, `I` iteration, `R` risk, `V` validation, and `F` follow-up.
- Use `01-progress.md` for delivered slices and REQ coverage.
- Use `01-progress.md` for validation history.

`01-progress.md` is not a file-write audit log. Ordinary `update` commands update the relevant section and `state.json`, but they do not append human ledger noise. The ledger records lifecycle-significant events: init, requirement changes, implementation-ready, role evidence, local records, checkpoints, verification, blockers, pause/resume/archive, and finalize.

Project-level state:

- `.idea-to-code/current.json` points to exactly one active bundle.
- `.idea-to-code/history/index.jsonl` records closed bundles. Do not move old bundle directories; history is an index, not storage.
- New bundle slugs must use `YYYYMMDD-HHMM-<normalized-task-title>` in local project time. Use `init --unique` to create this shape; collisions append `-02`, `-03`, etc.
- Mutating commands must operate on the current bundle. `update`, `implementation ready`, `requirement add/remove`, `role record`, `checkpoint`, `link`, `block`, `unblock`, `rebuild-progress`, and `finalize` refuse non-current bundles.
- `verify` may inspect any bundle, including a finalized bundle, but writes `last_verify_*` only for the current bundle when it is not paused, completed, or closed.
- `current set` refuses completed or closed bundles; closed work cannot be resumed into `in_progress`.
- `init` refuses to replace an unfinished current bundle. Park or close the current bundle explicitly before starting a different task.
- `current set` refuses to switch away from an unfinished current bundle. Run `current archive --reason "<reason>"` first.
- `current clear` refuses to delete an unfinished current pointer. Use `current archive` so the parked task is recorded in history.

1. **Preflight** - detect project language/stack; confirm build/test command; confirm git / cwd state. Abort early on a broken baseline rather than masking it later. See `references/workflow.md`.
   ```bash
   python ".../idea_to_code_bundle.py" doctor --root "$(pwd)"
   ```
   Read any project governance files reported by `doctor` before planning or editing.
2. **Restate the outcome in implementation terms and classify the task.** Write the latest user goal, intake gate, constraints, acceptance criteria, file changes yes/no, semantic impact yes/no/unclear, tracking required yes/no, and reason in `00-idea.md`. If semantic impact is unclear, default to tracked.
3. **If the request is still fuzzy**, convert the idea into a concrete requirement set (`references/planning-patterns.md`) before coding.
4. **Resolve or initialize the active delivery bundle** before any code edit:
   ```bash
   python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" current status \
     --root "$(pwd)"
   ```
   If there is no current bundle, or the current bundle is closed and indexed in history, initialize a new one:
   ```bash
   python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" init \
     --root "$(pwd)" --slug <task-slug> --title "<task title>" --unique [--idea "<seed>"]
   ```
   `init` creates the compact bundle files and writes `.idea-to-code/current.json`. Do not pass `--no-current` during normal idea-to-code work; reserve it for isolated script tests where no active task pointer should be changed.
5. **Fill `00-idea.md` sections** with the `update` subcommand - don't leave them as empty templates. `00-idea.md` must include Intake Gate, Task Classification, and an Acceptance Matrix row for each open `REQ-*`:
   ```bash
   python ".../idea_to_code_bundle.py" update --root "$(pwd)" --slug <slug> \
     --file requirements --content-file path/to/requirements.md
   ```
5b. **Register REQ-IDs** for the trace matrix - one row per requirement:
   ```bash
   python ".../idea_to_code_bundle.py" requirement add --root "$(pwd)" --slug <slug> \
     --id REQ-1 --description "User can X" --type functional
   ```
   `--type` is `functional | nonfunctional | constraint`. Do not skip this step for tracked work; `verify` and `finalize` require at least one open `REQ-*` with acceptance-matrix coverage.
6. **Inspect the current codebase, docs, project governance, and runnable paths** before proposing structure. If project-local rules define authority order, module boundaries, real product paths, validation types, or closeout gates, obey them before generic skill defaults.
7. **Decide the next smallest milestone** that creates real progress and keeps the system runnable.
8. **Before editing, fill and print `00-idea.md`.** This is the implementation gate. Use `TASK-ID` or `IMP-ID` items that are concrete enough to verify but not so fine-grained that they describe every line edit:
   ```text
   [idea-to-code] Implementation Gate: READY
   Bundle: .idea-to-code/<slug>
   Plan: 00-idea.md

   TASK-1: <change point>
   Files: <expected files/modules>
   Execution Details: <behavior/data/UI/test change to make>
   Done Criteria: <how this item is complete>
   Planned Verification: <command/runtime check/evidence target>

   TASK-2: ...
   ```
   Create items for user-visible behavior, protocol/API/data model changes, persistence/state changes, UI workflows, risky refactors, and test/acceptance paths. Do not create items for trivial mechanical edits unless they carry separate acceptance risk.
   Mark the gate ready only after every TASK has non-empty `Files`, `Execution Details`, `Done Criteria`, and `Planned Verification`:
   ```bash
   python ".../idea_to_code_bundle.py" implementation ready --root "$(pwd)" --slug <slug>
   ```
   If this command fails, refine the plan only. Do not edit code. `checkpoint`, `verify`, and `finalize` are script-guarded against a non-ready implementation gate.
9. **Record Planner evidence before implementation**:
   ```bash
   python ".../idea_to_code_bundle.py" role record --root "$(pwd)" --slug <slug> \
     --role planner --evidence "REQ-1..REQ-N planned in 00-idea.md; TASK-1..TASK-N ready in 00-idea.md" \
     --covers "REQ-1,REQ-2"
   ```
10. **Implement that milestone end-to-end** instead of stopping at analysis. Track progress by IMP-ID in updates, e.g. `IMP-2 PASS`, `IMP-3 PARTIAL`, or `IMP-4 FAIL`. After implementation, record Implementer evidence with files/modules and TASK/IMP IDs.
11. **Verify each IMP** with the strongest available local validation (see `references/verification-and-evidence.md`). Every validation claim must name one validation type: `real-product-path`, `mock-only`, `fixture-only`, `source-only`, `dom-only`, `manual-inspection`, or `unverified`. Overall tests do not replace per-IMP evidence; use the overall test run as shared evidence where it genuinely covers multiple IMPs. Record Validator evidence with validation type and covered REQ IDs.
12. **Review the result before checkpoint/finalize.** Make a separate Reviewer pass over scope, diffs, architecture boundaries, acceptance matrix coverage, validation strength, unverified items, and residual risks. Record Reviewer evidence. Do not claim an independent reviewer ran unless one actually did.
13. **Emit the Verification Summary Block** (see below) before recording the milestone. The result is the aggregate of the IMP results, not a separate competing checklist.
14. **Record the milestone**, listing which REQ-IDs it covers:
    ```bash
    python ".../idea_to_code_bundle.py" checkpoint --root "$(pwd)" --slug <slug> \
      --milestone "<name>" --delivered "<changed>" --verified "<how>" --next "<next>" \
      --focus "<current focus>" --gate "<next gate>" --gate-status pass \
      --covers "REQ-1,REQ-3"
    ```
    `--gate-status` is **required** (one of `pass | partial | fail`). Be honest - `finalize` cross-checks every REQ aggregate against your claim and refuses inconsistent ones. `--covers` accepts comma-separated REQ-IDs; unknown IDs cause the command to fail early.
15. **Continue into the next milestone** unless a real blocker or a true architectural fork requires the user.
15b. **Retroactive link (migration path)**: when resuming an older bundle whose historical milestones predate `--covers`, attach requirements after the fact:
    ```bash
    python ".../idea_to_code_bundle.py" link --root "$(pwd)" --slug <slug> \
      --milestone "<exact past name>" --covers "REQ-1,REQ-3"
    ```
    Default merges with any existing covers; pass `--replace` to overwrite. Unknown REQ-IDs are rejected up-front.
16. **On a real blocker**, record it; do not hide it:
    ```bash
    python ".../idea_to_code_bundle.py" block --root "$(pwd)" --slug <slug> \
      --reason "<concrete cause>" --need "<decision or dependency>"
    ```
    Call `unblock --note "<resolution>"` when cleared.
17. **Run pre-close verification after Reviewer evidence and before Closer evidence**:
    ```bash
    python ".../idea_to_code_bundle.py" verify --root "$(pwd)" --slug <slug>
    ```
    This pre-close verify does not require Closer evidence yet, but it must pass for the current plan revision. If it fails, return to the missing role, requirement, acceptance matrix, validation, or trace coverage gap before closing.
18. **When the task is genuinely complete**, record Closer evidence and finalize:
    ```bash
    python ".../idea_to_code_bundle.py" role record --root "$(pwd)" --slug <slug> \
      --role closer --evidence "Pre-close verify passed; Planner/Implementer/Validator/Reviewer evidence current; REQ-1..REQ-N covered; final result pass" \
      --covers "REQ-1,REQ-2"
    ```
    ```bash
    python ".../idea_to_code_bundle.py" finalize --root "$(pwd)" --slug <slug> \
      --summary "<impl summary>" --verification "<verif summary>" \
      --risks "<risks>" --acceptance "<scope delivered>" \
      --gate-status pass --decision accepted \
      [--acceptance-notes "..."] [--deferred "..."]
    ```
    The finalize command rolls up all recorded milestones into `02-report.md`, writes `01-progress.md`, appends the current bundle to `history/index.jsonl`, and clears `current.json`.
19. **Run final verification after finalize**:
    ```bash
    python ".../idea_to_code_bundle.py" verify --root "$(pwd)" --slug <slug>
    ```
    Non-zero exit = open requirement uncovered, fail gate reached, missing classification, missing acceptance matrix, missing validation type, missing role evidence, non-English bundle text, 00-idea empty, or required files missing. Fix before claiming done.
20. **Keep reports in English.** Final reports, acceptance records, role evidence, and bundle documentation must use English-only ASCII text.

---

## Operating Rules

- Prefer execution once direction is clear; ask only for architecture, user-visible contract, security, irreversibility, missing credentials, or true scope forks.
- Before code edits, resolve `.idea-to-code/current.json`, print the `00-idea.md` task list, and confirm the implementation gate is READY.
- Never mutate a non-current, paused, completed, or closed bundle to make progress.
- Keep TASK/IMP IDs tied to files, done criteria, and planned verification.
- Record Planner, Implementer, Validator, Reviewer, and Closer evidence in order for the current `plan_revision`.
- Every validation claim must name a validation type; do not inflate mock/source/DOM evidence into real product-path proof.
- When this skill creates test files, record `Test Ownership`: `persistent-product-test`, `project-native-test`, or `task-evidence-only`. Persistent/project-native tests must be visibly namespaced with `idea_to_code` or the task slug; evidence-only scripts and outputs belong under `.idea-to-code/<slug>/artifacts/`.
- Run pre-close `verify` after Reviewer evidence and before Closer/finalize.
- Run final `verify` after finalize.
- Treat bundle upkeep as part of the work product.

For detailed role/state rules, read `references/roles-and-state.md`.
For verification, evidence, and closeout rules, read `references/verification-and-evidence.md`.
For milestone and implementation-plan patterns, read `references/planning-patterns.md`.

---

## Execution Visibility

When this skill is active, every user-visible assistant message MUST start with `[idea-to-code]`. This includes commentary updates, plans, status answers, blocker reports, verification summaries, final responses, and follow-up explanations. Do not drop the marker just because the work is editing the skill itself.

The first line SHOULD name mode, bundle, and gate/state when useful:

```text
[idea-to-code] Mode: delivery | Bundle: <slug> | Gate: ready
[idea-to-code] Mode: status | Bundle: <slug> | State: <state>
```

If the message is a short answer rather than a lifecycle update, still start with `[idea-to-code]`.

### Console Handoff Contract

After tracked closeout, the final user-visible console/chat response MUST use this compact field contract. This is separate from `02-report.md`; it governs the assistant's final response to the user.

```text
[idea-to-code] Status: Completed | Progress | Blocked

Changes:
- <what changed>

Completed Items:
- <accepted item or REQ coverage>

Incomplete Items:
- none | <unfinished item and why>

Validation Results:
- <validation type + command/evidence + result>

Unverified Items:
- none | <item + concrete missing dependency/reason>

Residual Risks:
- none | <remaining risk>

Key Technical Details:
- <paths, behavior contracts, generated tests, migration notes, or important implementation facts>
```

Use `Completed` only after pre-close verify, Closer evidence, finalize, and final verify have passed. If any accepted item is incomplete, failed, unverified, or blocked, label the response `Progress` or `Blocked` and do not claim the task is complete. For small tasks, keep bullets short, but do not omit field names.

Default to autonomous delivery unless the user explicitly asks for planning-only, status, pause, review, or analysis.

---

## Completion Standard

Do not claim done until:

- implementation exists
- intake gate is resolved with `Need Confirmation: no`
- open REQs are covered
- acceptance matrix is concrete
- role evidence is current and ordered
- validation evidence names validation types
- known gaps and risks are explicit
- pre-close verify, finalize, and final verify have passed

Use `partial`, `accepted-with-followup`, `fail`, or `not-accepted` when evidence does not support full acceptance.

---

## Reference

Read only the reference needed for the current situation:

- `references/workflow.md` - bundle contract, lifecycle commands, routing, preflight, pause/resume/archive, checkpoint, verify, finalize.
- `references/roles-and-state.md` - role duties, task states, task classification, acceptance matrix, trace coverage, evidence quality.
- `references/verification-and-evidence.md` - validation types, verification summaries, UI/runtime evidence, acceptance and closeout checks.
- `references/planning-patterns.md` - vague idea clarification, milestone decomposition, implementation plan shape, final report shape.


