# Roles And State

## Purpose

Use this reference for role responsibilities, task states, state transitions, task classification, acceptance matrix, and REQ coverage.

## Skill Objective

The role system exists to make idea-to-code an intelligent, controllable delivery skill. Roles are not ceremonial labels: each role must preserve the user's real goal, improve weak ideas with evidence-backed recommendations, keep branches traceable, and close its own responsibility with concrete state. Future agent behavior should be derivable from these rules plus bundle records, not from informal chat memory.

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
- Record delegated or fresh-agent attempts with `delegation record`. Only `status usable` can support an independent/subagent/fresh-agent role claim. `timeout`, `unusable`, `planned`, and `unverified` records are visible risk/evidence gaps, not proof. Close a non-usable finding with `delegation resolve` only when the fallback, supersession, accepted risk, or invalid-record reason is explicit; this closes the branch but does not create independent evidence.
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

For multi-agent implementation inside one session ledger, Planner evidence must name IDEA/TASK/REQ ownership and file/module boundaries before parallel edits begin. Implementer evidence from each agent or worker subagent must cite its owned IDEA/TASK/REQ slice and changed files. Validator/Reviewer subagents normally record evidence in the parent slug rather than creating new slugs. Different live sessions require separate slugs, not separate role entries in one bundle.

## Role Responsibilities

- Planner: produces `00-idea.md` content: goal, Controlled Exploration, requirements, task classification, acceptance matrix, design, and implementation plan.
- Implementer: makes scoped changes and records TASK/IMP evidence tied to files or modules.
- Validator: records validation type, command/runtime/manual evidence, and covered REQ IDs.
- Reviewer: reconciles requested scope, actual diff, acceptance matrix, verification strength, risks, and boundary cases.
- Closer: runs after pre-close verify; records final decision, triggers finalize, and verifies the finalized bundle.

## Multi-Role Output Compliance

This section owns the role-by-role output matrix. `workflow.md` owns the lifecycle trigger for when to run the scenario and the `.idea-to-code/current.json` context boundary.

After changing Exploration Visibility Gate output, READY visibility, role/source prefixes, validation status wording, noncompliance reporting, or final handoff formatting, run or update the multi-role output compliance scenario. The scenario covers Planner, Implementer, Validator, Reviewer, and Closer expectations, plus current-TASK entry, overview output, and ordinary-answer boundary checks, and records expected versus observed behavior so instruction drift is visible instead of guessed.

The hard checks are:

- Planner output shows `[idea-to-code][Planner/agent] Exploration Result | Bundle: <slug>` for autonomous work or `[idea-to-code][Planner/agent] Confirmation Required | Bundle: <slug>` for confirmation work before READY, with `Display Layer`, `Next Layer`, and `Planned Scope` separated from `Decision Options`.
- Planner output preserves same-session continuity: for related follow-ups it audits prior related scope and classifies the message as `same scope`, `scope correction`, `new related scope`, or `unrelated ordinary answer` before changing the plan or claiming status.
- Planner output creates and syncs a master backlog for multi-issue related work before READY; it must not collapse several MB items into one TASK unless the Deferred or Out-of-Scope mapping is visible.
- Planner output shows `[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: <slug>` and a visible focused TASK/REQ excerpt only after the Exploration Visibility Gate output is current; full READY output is reserved for `--full-plan` audit use. Every current TASK transition needs visible task info for that TASK before edits begin, preferably through `implementation enter-task --task <TASK-ID>` so state records the current TASK.
- Planner output records material same-session related follow-ups with `session audit` before planning, answering status, or claiming completion from long-session context.
- Planner output records material related-vs-unrelated decisions with `scope classify`; a related correction cannot be handled as an ordinary unrelated answer without a classification record.
- Planner output records material same-session ideas with `idea record` when they are introduced, corrected, deferred, rejected, completed, blocked, superseded, or reopened, and consults `idea status` before answering status about prior ideas.
- Planner output preserves user-provided or agent-created numbered issue lists as stable scope IDs. If it reorganizes a prior list, it must show a mapping table with `Previous ID`, `Current ID`, and `Change Reason`; a fresh unrelated 1-7 list without mapping is noncompliant.
- Implementer output does not start tracked repository or artifact edits until the visible Exploration Visibility Gate output and READY excerpt have appeared, `implementation enter-task --task <TASK-ID>` has recorded the current TASK, `implementation lease acquire --task <TASK-ID> --owner <owner> --file <path>` has acquired non-overlapping write ownership, and `implementation pre-edit --task <TASK-ID> --file <path>` has printed `PRE_EDIT_OK_ID`.
- Implementer evidence names the current TASK/REQ, lines up with the latest `current_task_id` when `enter-task` was available, and cites the current `PRE_EDIT_OK_ID` when the pre-edit guard ran. The guard records must cover every file claimed for that TASK; partial guard coverage is noncompliant even if one file has a valid ID.
- Validator output names validation type, command/evidence, and covered TASK/REQ IDs.
- Reviewer output flags missing Exploration Visibility Gate output, missing READY visibility, late READY remediation, or missing fixed final status fields as noncompliance.
- Reviewer output flags same-session drift, failure to audit related prior scope, or treating a related correction as an unrelated ordinary answer as continuity noncompliance.
- Reviewer output flags missing, stale, or unmapped `IDEA-*` records when a formal status claims progress across multiple same-session ideas or a user asks about prior idea completion.
- Reviewer output flags missing, stale, or incomplete master backlog coverage when a multi-issue request is reported as complete.
- Reviewer output flags missing, stale, wrong-task, or incomplete pre-edit guard coverage, and flags open `implementation noncompliance` events instead of letting a late guard appear compliant.
- Reviewer output flags missing or overlapping write leases for implementation edits. Read-only Validator/Reviewer subagents do not need write leases unless they edit files.
- Reviewer output refuses independent/subagent/fresh-agent claims unless a current usable delegation record exists; timed-out, planned-only, unusable, or unverified delegation records must be carried as evidence gaps until resolved. Negated disclosures such as `independent review not run` or `subagent unavailable` are same-agent honesty statements, not independent-evidence claims.
- Reviewer output flags unstable numbering, unmapped renumbering, or a second unrelated same-number list as traceability noncompliance.
- Reviewer weakness reports must classify every listed weakness as one of `already hardened`, `residual risk`, `new gap`, or `external validation`. Repeating an older issue without saying which class it belongs to is ambiguous review output and must be corrected before planning another batch.
- Reviewer output captures every review-discovered `new gap` as a TODO candidate, deferred item, or rejected item. It must not mention a `new gap` once and then drop it from follow-up planning, and it must not mark the gap completed without TASK/REQ and validation evidence.
- Closer output runs `render-status` first for tracked final handoff; if unavailable or failed, it states the reason and uses the fixed Console Response Contract fields manually.
- Formal tracked status MUST use render-status generated fields when `render-status` is available. The final response may replace placeholders with actual evidence, but it must not omit, rename, reorder, or hand-invent the fixed field set.
- Closer formal tracked status fails compliance if it omits any fixed field (`Changes`, `Completed Items`, `Incomplete Items`, `Validation Results`, `Unverified Items`, `Residual Risks`, or `Key Technical Details`), drops TASK/REQ mapping from `Changes`, `Completed Items`, `Incomplete Items`, or `Validation Results`, drops IDEA/TASK/REQ mapping when multiple ideas exist in the session ledger, puts `No commit made` under `Incomplete Items`, or hand-writes a formal tracked handoff without first using `render-status` when it is available.
- All roles preserve the language boundary: user-facing explanations, recommendations, and conclusions follow the user's language by default, while entries from `SKILL.md#Protocol Glossary / Do-Not-Translate List` remain English-only ASCII. Role/source prefixes, role names, fixed protocol fields, IDs, commands, bundle state, role evidence, and validation types must not be translated.
- Reviewer output flags translated protocol glossary entries, such as localized role names, localized `Status` fields, localized `TASK-*` or `REQ-*` IDs, or localized command names, as language-boundary noncompliance.

Ordinary untracked explanations remain concise and are scored separately so the compliance rules do not reintroduce over-templating. Over-templates ordinary untracked replies is a failure signal for this scenario.

The ordinary-answer role check is explicit: a role simulation must fail if it adds READY output, `render-status`, or fixed status fields to explanation-only, naming, clarification, or lightweight commentary messages that do not start file edits.

Run protocol:

1. Use the installed skill from `$HOME/.codex/skills/idea-to-code`.
2. Require every role simulation or subagent to read installed `SKILL.md` as the behavior authority, then read only the relevant referenced files before inspecting output compliance.
3. Ask separate role simulations or subagents to inspect the installed guidance without editing files.
4. Capture PASS/FAIL for Planner, Implementer, Validator, Reviewer, Closer, current-TASK entry, overview output, same-session continuity, stable enumeration traceability, and ordinary-answer boundary.
5. Record exact drift, not guessed causes.
6. If any role fails, revise guidance or tests before claiming output compliance.

## Role Evidence Checklist

Use this checklist before recording role evidence. If `role record` rejects evidence, inspect this checklist or run the read-only helper:

```bash
python ".../idea_to_code_bundle.py" role explain --role <planner|implementer|validator|reviewer|closer>
```

`role explain` is not a state transition, not a role gate, and not a replacement for `role record`. It only prints the evidence expectations in a machine-readable shape.

### Planner Evidence

Must include:

- planned REQ IDs
- 00-idea.md, Controlled Exploration, Exploration Visibility Gate output, requirements, acceptance matrix, or implementation plan
- TASK/IMP IDs or implementation-plan reference
- EXPLORATION_OUTPUT_ID and READY_TASK_OUTPUT_ID when the plan reached READY
- planning work, not validation, review, or closeout work

Must not include:

- claims that implementation or validation already happened unless those role gates have actually run
- vague phrases such as planned, ready, or looks good without REQ/TASK context

### Implementer Evidence

Must include:

- implemented TASK/IMP IDs
- changed files or modules
- latest `PRE_EDIT_OK_ID` when a pre-edit guard exists for the current plan revision
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
