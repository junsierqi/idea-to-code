---
name: idea-to-code
description: Turn product ideas, rough requirements, or feature directions into verified software changes through an idea-to-code bundle, intake confirmation, requirements, implementation planning, role-gated execution, validation, review, and structured closeout. Use when the user invokes $idea-to-code, asks to turn an idea into working code, wants Codex to keep iterating until it works, or needs a multi-step implementation managed from idea to accepted delivery.
---

# Idea To Code

## Core Operating Contract

Turn an idea into a verified software change through a project-local bundle, not through chat memory. The bundle, script gates, recorded evidence, and final closeout are the durable continuity path.

Use idea-to-code as the primary lifecycle driver: its durable goal, exploration decisions, current TASK, next action and acceptance state direct the work. Agents execute this workflow; the skill is not a separate model that thinks, supervises or acts independently. Follow `references/workflow.md` for decisions and interventions, and `references/roles-and-state.md` for executing and supervising responsibilities.

This skill is an execution workflow, not a replacement for project governance. If the repository has `AGENTS.md`, `CONTRIBUTING.md`, architecture docs, testing docs, or acceptance rules, treat them as project-local authority and layer this skill underneath them.

Use normal engineering judgment inside the confirmed scope. The gates exist to prevent drift, hidden scope, weak validation, and false completion claims.

On every invocation, including resumed sessions and delegated work, actively look for evidence that the workflow helped, missed something, or imposed unnecessary cost; do not wait for a user to request self-improvement. Use the stage prompts under `Evidence-backed workflow improvement` in `references/workflow.md`. Preserve material findings in the active bundle, distinguish execution mistakes from rule gaps, and keep the original delivery goal current. Observing and recording learning does not itself authorize changing or installing the skill; unverified proposals remain inactive. No useful new finding is a valid outcome.

## When Is This Skill The Right One

Use it when at least one is true:

- the user invokes `$idea-to-code`;
- the user asks to turn an idea, concept, rough requirement, or feature direction into working code;
- the user wants Codex to keep iterating until it works;
- the work spans at least three milestones or at least two subsystems/layers;
- the outcome needs verified behavior, runtime evidence, or a built artifact;
- the request starts as an idea rather than a concrete one-shot edit.

Skip it for a simple one-shot edit unless the user explicitly asks for idea-to-delivery behavior. Prefer `design-to-code` when the driver is a visual design, mockup, screenshot, Figma, or live URL.

## Direct Trigger Behavior

When this skill is triggered, default to autonomous delivery unless the user asks for planning-only, review-only, status-only, pause, or analysis:

1. Create or resume the active `.idea-to-code/<slug>/` bundle.
2. Resolve Intake Gate and Controlled Exploration.
3. Register `REQ-*` scope, acceptance matrix, design, and `TASK-*` implementation plan.
4. Show `Exploration Result` or `Confirmation Required` before READY.
5. Show focused `Implementation Gate: READY` for the current TASK before edits.
6. Record visible output, enter task, acquire lease, and pass `implementation pre-edit`.
7. Implement only the visible TASK/REQ/file scope.
8. Validate with named validation types and evidence.
9. Review user-intent fit, risks, non-goals, counterexamples, and branch closure.
10. Checkpoint or close each TASK, then run pre-close verify, Closer evidence, finalize, final verify, and formal closeout when applicable.

## Script Invocation - Cross-Platform

Use the installed skill script for every bundle operation:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" <command> [args]
```

Use this exact literal prefix in command examples. Permission allowlists may match it as a string prefix; aliases or shell `eval` wrappers can break that behavior. If a lifecycle command shape is uncertain, run:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" command-guide --flow implementation-edit
```

## Workflow

Normal flow:

```text
route/current -> init/resume bundle -> intake gate -> controlled exploration
-> requirements/REQs -> acceptance matrix -> design -> TASK plan
-> exploration render -> implementation ready -> enter-task -> visible-output record -> lease -> pre-edit
-> scoped edit -> validate -> review -> checkpoint/close-task
-> pre-close verify -> closer/finalize -> final verify -> render-status
```

Read `references/workflow.md` for lifecycle order, command flow, bundle contract, current pointer rules, branch closure, quickstart/fast-lane, generated test ownership, pause/resume/archive, checkpoint, verify, finalize, and installed parity workflow.

### Runtime Start Checklist

At the start of a triggered task:

1. Inspect current state:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" current inspect --root "$(pwd)"
```

2. Initialize or resume one bundle. Do not infer a current bundle by scanning historical `.idea-to-code/<slug>/` directories.
3. Read project governance files reported by `doctor`.
4. Identify build/test/runtime commands before implementation.
5. Record Intake Gate, Controlled Exploration, requirements, acceptance matrix, and TASK plan.
6. Run `implementation plan-check --json` before READY when the plan was manually edited.
7. Show Exploration and READY in the assistant-visible body, not only tool stdout.

### Edit Gate Checklist

Before tracked source, docs, tests, config, script, or artifact edits:

1. Ask the controller what is missing:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation next-action --root "$(pwd)" --slug <slug> --task <TASK-ID> --files <path-a> <path-b> --json
```

2. Show required Display Layer blocks in the main assistant-visible body.
3. Record visible output for same-agent work:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation visible-output record --root "$(pwd)" --slug <slug> --task <TASK-ID> --display-channel main-chat --assistant-body "<body>" --display-assertion "The full Display Layer was shown in main chat, not tool stdout."
```

4. Enter the current TASK:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation enter-task --root "$(pwd)" --slug <slug> --task <TASK-ID>
```

5. Acquire a write lease:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation lease acquire --root "$(pwd)" --slug <slug> --task <TASK-ID> --owner agent --files <path-a> <path-b>
```

6. Run pre-edit:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation pre-edit --root "$(pwd)" --slug <slug> --task <TASK-ID> --files <path-a> <path-b>
```

7. Edit only files covered by the current TASK and `PRE_EDIT_OK_ID`.

`implementation guarded-apply` is the preferred path for patch-expressible tracked edits. Native edit tools are not physically blocked by this repository; that remains `host-required`.

### Autonomous Next-Action SOP

Safe same-IDEA next actions are agent-owned work. Do not stop by asking the user to type `next`, `下一步`, or `continue` when planning, READY, implementation, validation, review, install parity, or closeout can proceed safely in the current environment.

Stop only for explicit pause/status-only/review-only requests, missing product decisions, missing credentials/tools/permissions, destructive or irreversible action, commit/push/deploy/publish approval, scope uncertainty, safety/legal/privacy uncertainty, or repeated tool/environment failure that blocks progress.

Detailed same-IDEA, scope-correction, new-related-scope, unrelated, Scope Override, master backlog, and current TASK rules live in `references/workflow.md` and `references/planning-patterns.md`.

### Branch Boundaries

Keep these boundaries explicit in planning, review, and closeout:

- `Tracked edit`: edit only after current Exploration, READY, visible-output record, lease, and pre-edit.
- `Delegation evidence`: use independent evidence only when a usable delegation record exists.
- `Same-session continuity`: audit prior related scope before answering "everything", "earlier issue", or numbered-list status.
- `Idea ledger`: record material ideas with stable `IDEA-*` IDs when later status may need them.
- `Scope classification`: classify material follow-ups before mutating bundle state.
- `Scope Override`: record override before working on non-`Next Action` items while incomplete work remains.
- `Master backlog`: map multi-issue lists to `MB-*` before READY.
- `Controlled repair`: finish or close the current TASK before switching.
- `Enumerated scope`: preserve user-provided numbering or show a mapping table.
- `Current TASK entry`: use `implementation enter-task` before each TASK's edits.
- `Validation type preflight`: every TASK/IMP planned verification names an approved validation type.
- `Display artifact`: tool stdout is not the same artifact as the assistant-visible body.
- `Formal tracked handoff`: tracked delivery actions require `render-status` or an explicit failure reason.
- `Ordinary answer`: ordinary explanations stay natural and do not gain fixed fields.
- `Installed parity`: do not claim installed runtime behavior until source/installed parity is checked.

Use `branch-map --json` and `lifecycle-audit --json` to audit these branches.

### Tracked Work Compliance Checklist

For tracked work, these are mandatory:

- use one active bundle and stable `IDEA-*` / `REQ-*` / `TASK-*` / `MB-*` IDs where relevant;
- resolve Intake Gate before implementation;
- use Controlled Exploration and show the user-visible exploration layer before READY;
- show focused READY for the current TASK before edits;
- record assistant-visible output, lease, and `PRE_EDIT_OK_ID` before tracked file edits;
- record role evidence in order: Planner, Implementer, Validator, Reviewer, Closer;
- name validation types: `real-product-path`, `mock-only`, `fixture-only`, `source-only`, `dom-only`, `manual-inspection`, or `unverified`;
- keep same-agent, subagent, and fresh-agent evidence boundaries honest;
- run `render-status` for formal tracked handoff when available;
- do not claim host-required guarantees as repo-enforced.

Detailed gate semantics live in `references/workflow.md`, `references/roles-and-state.md`, and `references/verification-and-evidence.md`.

## Planning

Read `references/planning-patterns.md` when turning vague input into requirements, splitting work into milestones, writing `TASK-*` plans, or shaping final reports.

Required planning concepts:

- `Intake Gate`: Understanding, Assumptions, Acceptance Criteria, `Need Confirmation`, Confirmation Reason.
- `Controlled Exploration`: `no-fork`, `option-comparison`, or `role-sweep`; selected scope must be visible before READY.
- `Planned Scope`: Required Now, Deferred, and What READY Will Cover.
- `Decision Options`: only mutually exclusive route choices, not required work items.
- `Implementation Plan`: one or more concrete `TASK-*` blocks with Files, Execution Details, Implementation Quality Contract, Done Criteria, and Planned Verification.
- `MB-*`: stable IDs for user-provided multi-issue lists.

Do not invent fake options for a clear low-risk task. Do challenge a flawed requested implementation and recommend a better default path when evidence supports it.

### Intake And Exploration Short Rules

- Use `Need Confirmation: yes` for ambiguous, risky, irreversible, security-sensitive, architecture-shaping, expensive, or multi-interpretation work.
- Use `Need Confirmation: no` when the path is clear, low-risk, reversible, and acceptance is concrete.
- `no-fork` is for a single clear path.
- `option-comparison` is for real route/API/architecture/data/security/cost/migration/verification forks.
- `role-sweep` is for broad ideas where the risk is missing problem categories.
- Raw role-sweep findings are candidate findings until Synthesis accepts, rejects, defers, or marks them unverified.
- Revised exploration gets a new `EXPLORATION_OUTPUT_ID`.
- Deferred or rejected scope must not silently appear in READY.

### Implementation Plan Short Rules

- `REQ-*` captures user outcome.
- `TASK-*` captures the READY/edit gate.
- `IMP-*` is optional lower-level implementation detail inside a TASK.
- Do not force one-to-one numbering across `REQ-*`, `TASK-*`, and `IMP-*`.
- Do not mark READY while TASK fields contain placeholders.
- Generated tests must be classified as `persistent-product-test`, `project-native-test`, or `task-evidence-only`.
- Evidence-only scripts or artifacts belong under `.idea-to-code/<slug>/artifacts/`.

## Roles And State

Read `references/roles-and-state.md` for role responsibilities, Role Execution Mode, delegation healthcheck, task states, acceptance matrix, trace coverage, evidence quality, and role-specific evidence requirements.

Role order is:

1. Planner
2. Implementer
3. Validator
4. Reviewer
5. Closer

The same agent may perform all roles, but each role needs separate evidence. Use `/subagent` only when a real delegated subagent returned usable evidence. Planned, timed-out, unusable, or unverified delegation is not independent evidence.

### Role Evidence Minimums

- Planner evidence names planned `REQ-*`, Controlled Exploration, acceptance matrix, TASK/IMP IDs, and output IDs when READY exists.
- Implementer evidence names implemented TASK/IMP IDs, changed files, and current `PRE_EDIT_OK_ID`.
- Validator evidence names covered `REQ-*`, validation type, command/path/artifact, and observed result.
- Reviewer evidence covers scope fit, acceptance examples, counterexamples, non-goals, validation strength, shortcut risk, obvious better alternative check, unverified items, and residual risks.
- Closer evidence runs after pre-close verify and names final decision, coverage, and gate alignment.

Role evidence must be concrete English-only ASCII in bundle state. Vague evidence such as `done`, `tested`, `reviewed`, or `looks good` is invalid.

## Verification And Evidence

Read `references/verification-and-evidence.md` when validating behavior, recording evidence, reviewing acceptance, checking READY/Exploration visibility, checking final responses, handling installed skill parity, or deciding whether a result is accepted.

Accepted delivery means the result fits the user's intended observable outcome, not merely that code changed or tests passed. Validation must identify the product path or source path exercised, the command or artifact, the validation type, and the covered `REQ-*` / `TASK-*` scope.

Command success is not enough when a command ran zero relevant tests or did not exercise the user-visible outcome. Treat that as `unverified` or fix the test command before claiming coverage.

### Acceptance Check Summary

Before accepted closeout, verify:

- implementation exists and matches the restated user goal;
- Controlled Exploration was either skipped for a concrete reason or resolved with a decision;
- visible Exploration and READY output IDs are current;
- acceptance examples pass and counterexamples are not accepted;
- non-goal boundaries are preserved;
- all open REQs are covered or explicitly deferred/blocked/rejected;
- role execution mode is disclosed;
- independent/subagent claims have usable delegation evidence;
- validation type and evidence are named for every claim;
- no generated tests are ownership-ambiguous;
- pre-close verify, Closer evidence, finalize, and final verify pass.

### Evidence Categories

Keep these categories separate:

- `Fact`: observed evidence only.
- `Hypothesis`: possible explanation or route that is not proven.
- `Decision`: selected action from facts or explicitly marked hypotheses.
- `Verification`: evidence that proves, disproves, or narrows a hypothesis or acceptance claim.

Do not use an unverified hypothesis as accepted evidence. Put unresolved hypotheses in `Unverified Items`, `Residual Risks`, or the next experiment plan.

### Evidence-backed workflow improvement

Use the existing bundle to record observed workflow failures, diagnose them, and link a normal improvement TASK without losing the original resume point. Read `references/workflow.md` for the learning loop and `references/verification-and-evidence.md` for structured case/evidence and activation commands. Keep project-specific rules in the project. An installed improvement is not yet proven effective in future tasks.

## Console Response Contract

Use natural concise replies for ordinary explanation, naming, clarification, or read-only discussion. Do not add READY, `render-status`, or fixed fields just because a bundle exists.

Use formal fixed fields for formal delivery status: final closeout, final handoff, blocked handoff, review handoff, keep/revise/rollback handoff, or explicit tracked delivery status after work entered `REQ-*` / `TASK-*` accounting. Run `render-status` first when available:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" render-status --root "$(pwd)" --slug <slug> --status Completed|Progress|Blocked
```

Formal tracked status fields are:

```text
[idea-to-code][Closer/agent] Status: Completed | Progress | Blocked

Changes:
- <TASK/REQ-mapped change>

Completed Items:
- <TASK/REQ-mapped accepted item or coverage>

Incomplete Items:
- none | <TASK/REQ-mapped unfinished item and why>

Validation Results:
- <TASK/REQ-mapped validation type + command/evidence + result>

Unverified Items:
- none | <item + concrete missing dependency/reason>

Residual Risks:
- none | <TASK/REQ/MB/IDEA-mapped remaining risk>

Key Technical Details:
- <paths, behavior contracts, generated tests, migration notes, or important implementation facts>

Next Action:
- <next recommended action, user decision needed, or no unresolved task remains>
```

Detailed response-mode classification, mixed status/review split, output-compliance checks, and final-body host-hook limits live in `references/verification-and-evidence.md`.

### Response Mode Short Rules

- `ordinary-answer`: natural concise answer; no fixed fields.
- `read-only-status`: summarize status without starting edits.
- `mixed-review`: concise tracked status sentence first, then natural review sections.
- `formal-tracked-handoff`: use `render-status` fixed fields.
- `blocked-handoff`: fixed fields with concrete blocker and final `Next Action`.

Actions override prompt wording. If the turn performed tracked edits, validation, install, checkpoint, finalize, commit, render-status, or tracked status delivery, the final response is formal tracked handoff unless a blocker makes it blocked handoff.

## Completion Standard

Do not claim done until:

- implementation exists or the task is explicitly source-only/read-only;
- intake is resolved with `Need Confirmation: no`, or the response is a confirmation/blocker handoff;
- open REQs are covered or explicitly deferred/blocked/rejected;
- the acceptance matrix is concrete enough for the scope;
- role evidence is current and ordered;
- validation evidence names validation types;
- risks, external validation, and host-required limits are explicit;
- pre-close verify, Closer evidence, finalize, and final verify pass for accepted closeout.

Use `partial`, `accepted-with-followup`, `fail`, or `not-accepted` when evidence does not support full acceptance.

## User-Facing Language Contract

Meaningful user-facing prose follows the user's language by default. If the latest user request is primarily Chinese, write explanations, recommendations, caveats, and conclusions in Chinese. If the user asks in another language, use that language for meaningful prose.

Protocol tokens and state remain stable English/ASCII. Do not translate identifiers or fixed protocol fields such as role/source prefixes, role names, status fields, IDs, command names, validation types, bundle paths, or evidence strings. Quoted user text may stay in the original language; bundle state should stay portable and English-only where commands require it.

## Installed Skill Parity Checklist

When tracked work changes this skill and the user expects installed runtime behavior, do not claim the latest skill code is installed and verified until parity is checked. Formal install, validation, or final status must name the relevant TASK/REQ and show:

- install target path, normally `$CODEX_HOME/skills/idea-to-code`;
- installed focused tests;
- source/installed SHA256 parity for files changed by the batch;
- `install-parity check` evidence;
- `No commit made` in `Key Technical Details`, not under `Incomplete Items`, when no commit was requested.

Report missing install evidence in `Unverified Items`. Wrapper skills and profile-prefixed upper-layer skills must either run the same base-skill parity gate or disclose that parity is unverified.

## Host And External Validation Boundaries

The repository can expose contracts, scripts, tests, and residual-risk reporting. It cannot by itself:

- physically intercept every native Codex file-editing tool;
- inspect and block the final assistant-visible response before send;
- prove fresh-session behavior without a real fresh-session run;
- prove runner parity when metadata is missing or non-comparable;
- turn a timed-out or planned subagent into independent evidence.

Use `host-hook pre-edit-contract --json` and `host-hook final-response-contract --json` when specifying host integration requirements. Treat absent host enforcement as `host-required`, not `repo-enforced`.

## Risk And Weakness Taxonomy

When reviewing architecture, process gaps, repeated weaknesses, or "what remains weak", classify every item with one status:

- `already hardened`: rules, commands, tests, installed behavior, or state records already address it; cite evidence.
- `residual risk`: it is hardened but the current skill/runtime cannot fully prevent it; state the remaining failure mode.
- `new gap`: no current rule, command, test, benchmark, or state path covers it; state the proposed TODO/REQ/TASK/defer/reject decision.
- `external validation`: the rule or artifact exists, but fresh-session, multi-agent, user acceptance, or environment validation has not run.

Do not mix old and new weaknesses in one unlabeled list. If a user asks why a repeated weakness is still listed, map it to this taxonomy and prior evidence before proposing new work.

Every weakness also needs an enforcement boundary:

- `repo-enforced`: repository code, tests, CLI commands, or committed artifacts enforce it.
- `skill-enforced`: skill rules, bundle state, role evidence, verification, or closeout checks require it, but agent cooperation remains part of the control.
- `host-required`: Codex host/tool support is required, such as native pre-edit interception or send-time final-response blocking.

Do not repeatedly convert `host-required` residual risks into repo-only TODOs. Track them as product integration requests or external validation items unless a new host integration path exists.

## Product Direction

Read `references/product-charter.md` when reviewing architecture, drift, repeated weaknesses, or whether a proposed rule fits the product target.

The product target is an intelligent, controllable, traceable delivery workflow that improves weak ideas, exposes branches, executes mapped scope, validates with evidence, and closes every idea/branch/task/validation path without relying on chat memory.

## Maintainer Validation

Use local validation proportional to the changed surface:

- source/reference/output smoke: `test-batch --profile maintainer-fast`
- output contract changes: `output-compliance self-test` plus focused output tests
- lifecycle branch changes: `branch-map --json` and `lifecycle-audit --json`
- installed runtime claims: `install-parity check`
- broad release behavior: `controlled-exploration-benchmark.md` and release-quality/fresh-session protocols
- fresh-session benchmark runs: read `references/controlled-exploration-benchmark.md` and preserve the complete `Fresh-Session Reporting Format`, including runner metadata, accurate `External run status`, result summary, small-task friction failures, severe failures, decision, raw answers, per-output scoring, and per-scenario `Instruction drift` plus next-change notes for FS-1 through FS-7

`maintainer-fast` is quick smoke evidence, not a substitute for full validation. For full validation use `test-batch --profile full --chunk-size 20 --timeout-seconds 300` or a narrower documented profile when the acceptance scope is narrower.

## Protocol Glossary / Do-Not-Translate List

Keep these protocol tokens English-only in user-visible output, bundle artifacts, reports, state, role evidence, tests, and command examples. Meaningful prose around them should follow the user's language.

This glossary is the canonical maintenance point for protocol terms that must remain English. Add, remove, or rename entries here when the protocol changes, then update the regression test that checks representative entries. Do not scatter new do-not-translate terms only in prose.

- Role/source prefixes: `[idea-to-code][Planner/agent]`, `[idea-to-code][Implementer/agent]`, `[idea-to-code][Validator/agent]`, `[idea-to-code][Reviewer/agent]`, `[idea-to-code][Closer/agent]`, `[idea-to-code][Validator/subagent]`.
- Role names: `Planner`, `Implementer`, `Validator`, `Reviewer`, `Closer`.
- Source names: `agent`, `subagent`.
- Status labels: `Completed`, `Progress`, `Blocked`.
- Formal status fields: `Status`, `Changes`, `Completed Items`, `Incomplete Items`, `Validation Results`, `Unverified Items`, `Residual Risks`, `Key Technical Details`, `Next Action`.
- Display and gate labels: `Exploration Result`, `Confirmation Required`, `Implementation Gate: READY`, `Display Layer`, `Next Layer`, `READY Focus`, `Full Plan`.
- Scope and trace IDs: `TASK-*`, `REQ-*`, `IDEA-*`, `MB-*`, `IMP-*`.
- Output and guard IDs: `EXPLORATION_OUTPUT_ID`, `READY_TASK_OUTPUT_ID`, `PRE_EDIT_OK_ID`, `LEASE_ID`, `VISIBLE_OUTPUT_ID`.
- CLI command names and arguments: `render-status`, `response classify`, `implementation ready`, `implementation enter-task`, `implementation close-task`, `implementation pre-edit`, `implementation lease acquire`, `implementation visible-output record`, `implementation noncompliance`, `implementation noncompliance-resolve`, `idea record`, `idea status`, `backlog sync`, `scope override`, `scope override-resolve`, `--root`, `--slug`, `--task`, `--file`, `--files`, `--covers`.
- Response kinds: `ordinary-answer`, `read-only-status`, `mixed-review`, `formal-tracked-handoff`, `blocked-handoff`.
- Scope override terms: `Scope Override`, `same-ledger-verification`, `same-ledger-repair`, `new-ledger-improvement`, `accepted-residual`, `create-child-task`, `create-new-ledger`, `child-task-created`, `new-ledger-created`.
- File, artifact, and state names: `00-idea.md`, `01-progress.md`, `02-report.md`, `state.json`, `bundle`, `ledger`, `current.json`.
- Validation types: `real-product-path`, `mock-only`, `fixture-only`, `source-only`, `dom-only`, `manual-inspection`, `unverified`.
- Evidence and report content written to bundle state: role evidence, acceptance records, milestone records, final reports, validation evidence, and command output excerpts.

Detailed language-boundary checks live in `references/roles-and-state.md` and `references/verification-and-evidence.md`.

## Reference

### Reference File Addition Rule

Default to extending an existing reference file instead of adding a new one. A new file under `references/` is allowed only when the change includes evidence that the separate file improves agent understanding or compliance compared with placing the material in `SKILL.md` or an existing reference.

Acceptable evidence can include a fresh-session output comparison, multi-role simulation result, benchmark score, or concrete maintainer audit showing the existing owner document would become misleading or too broad. When evidence is missing, keep the rule in the current owner document and add tests there. Do not add a new reference file only because it feels cleaner, might be useful later, or separates a small topic. If a new reference file is justified, update the Reference Ownership Map and reference-link tests in the same TASK/REQ.

### Reference Ownership Map

Use this map before opening references or adding new rules:

| Reference | Owns | Does Not Own |
|---|---|---|
| `references/product-charter.md` | product target, anti-goals, drift signals, corrective actions | runtime lifecycle gates or command syntax |
| `references/workflow.md` | lifecycle order, bundle contract, routing, branch closure, context boundary, command flow, quickstart/fast-lane, maintainer validation flow | reusable writing templates or role-specific evidence wording |
| `references/planning-patterns.md` | intake, Controlled Exploration, TASK/REQ plan shape, milestone and report patterns | lifecycle enforcement or final acceptance checks |
| `references/roles-and-state.md` | role responsibilities, role execution mode, delegation healthcheck, role evidence, task states, acceptance matrix, trace coverage | validation taxonomy or final response contract details |
| `references/verification-and-evidence.md` | validation types, evidence quality, acceptance checks, READY/Exploration visibility checks, `render-status`, installed parity, response mode | initial planning templates or role-order ownership |
| `references/controlled-exploration-benchmark.md` | prompt-level and fresh-session benchmark scenarios, scoring, protocol, real-task sweep, copyable result templates | runtime rule authority or fixed answer templates |

Read only the reference needed for the current situation:

- `references/product-charter.md` - product target, anti-goals, drift signals, and corrective actions for architecture or process review.
- `references/workflow.md` - bundle contract, lifecycle commands, routing, preflight, pause/resume/archive, checkpoint, verify, finalize.
- `references/roles-and-state.md` - role duties, task states, task classification, acceptance matrix, trace coverage, evidence quality, and multi-role output compliance.
- `references/verification-and-evidence.md` - validation types, verification summaries, UI/runtime evidence, acceptance and closeout checks.
- `references/planning-patterns.md` - vague idea clarification, milestone decomposition, implementation plan shape, final report shape.
- `references/controlled-exploration-benchmark.md` - prompt-level scenario library, fresh-session live benchmark protocol, scoring rubric, and copyable result template for evaluating real model outputs after Controlled Exploration changes.
