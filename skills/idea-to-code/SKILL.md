---
name: idea-to-code
description: Turn product ideas, rough requirements, or feature directions into verified software changes through an idea-to-code bundle, intake confirmation, requirements, implementation planning, role-gated execution, validation, review, and structured closeout. Use when the user invokes $idea-to-code, asks to turn an idea into working code, wants Codex to keep iterating until it works, or needs a multi-step implementation managed from idea to accepted delivery.
---

# Idea To Code

## Overview

Drive an idea from vague intent to verified implementation. Keep moving between clarification, architecture, coding, testing, and acceptance until the request is concretely delivered or blocked by a real external dependency.

This skill is an execution workflow for idea-to-code delivery, not a replacement for project governance. If the repository has `AGENTS.md`, `CONTRIBUTING.md`, architecture docs, testing docs, or acceptance rules, treat them as project-local authority and layer this skill underneath them. A task ledger or roadmap records state and evidence; it must not define behavior policy unless the project explicitly gives it that authority.

`SKILL.md` is the skill runtime entry point. `AGENTS.md` is an optional project-specific entry point for agents working inside a repository, and `CONTRIBUTING.md` is optional project-specific contributor guidance. Project governance can constrain repo work when present, but it is not the definition of this skill.

## Core Operating Contract

When this skill loads, understand its core as: turn an idea into a verified software change through a project-local bundle, not through chat memory. The bundle, script gates, and recorded evidence are the source of continuity.

## Product Direction And Architecture

The long-term objective is an intelligent, controllable idea-to-code delivery agent. The current product is a skill that hardens that agent behavior through explicit lifecycle rules, bundle state, script gates, evidence records, and regression tests. Do not treat this skill as a loose checklist or a chat style guide.

Every tracked idea must move through a clear closed loop:

- understand the user's real goal and restate it in implementation terms;
- improve the idea when the requested path is weak, risky, incomplete, or unverifiable;
- expose exploration and selected scope before READY;
- execute only the visible TASK/REQ scope;
- validate with named evidence;
- review user-intent fit, counterexamples, non-goals, and branch closure;
- close or defer every branch explicitly instead of leaving ambiguous conversation residue.

Future agents must be able to recover the objective, architecture, current scope, and evidence path from installed skill instructions plus the project-local bundle. If a later answer would rely only on chat memory, old numbering, or a vague "as discussed" reference, first create or read the state-backed mapping. The implementation path is iterative: use idea-to-code to improve idea-to-code, make each control gap a TASK/REQ-backed change, install the latest skill code, and validate source plus installed behavior before claiming progress.

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
route/current -> intake gate -> controlled exploration -> Exploration Visibility Gate -> bundle -> requirements/REQs -> design -> implementation gate
-> implement -> validate -> review -> checkpoint -> pre-close verify -> closer/finalize -> final verify -> structured closeout response
```

Tool-owned gates are not optional and should not be inferred from chat: Intake Gate, Controlled Exploration shape, Exploration Visibility Gate, implementation ready, REQ coverage, Acceptance Matrix, role evidence, validation type, pre-close verify, finalize, and final verify are enforced by `idea_to_code_bundle.py` and guarded by the regression suite.

Use the Branch Coverage Map when reviewing whether the lifecycle is controlled end to end:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" branch-map --json
```

The map is an observability and self-check aid. Each branch has `id`, `entry`, `exit`, `validation`, and `failure_handling`. It does not prove live agent compliance by itself; it shows what branch closure evidence should exist.
The map mirrors the branch closure checks in `references/workflow.md`; each entry also exposes `workflow_branch` so reviewers can compare the CLI output to the workflow source text.

This section orients the agent; it does not narrow ordinary coding capability. Use normal engineering judgment inside the confirmed plan, while respecting the gates that keep the idea from drifting.

Accepted delivery means the result fits the user's intended outcome, not merely that code changed or tests passed. For every tracked task, keep a user-intent acceptance thread: restated user goal, observable user outcome, in-scope boundaries, non-goals, acceptance examples, counterexamples of wrong-but-working results, and final decision rationale. If the implemented result is technically valid but does not satisfy that intent thread, close as `Progress`, `Blocked`, `partial`, `accepted-with-followup`, `fail`, or `not-accepted` instead of `Completed` / `accepted`.

Role gates are mandatory; separate agents are preferred when real orchestration is available and useful. At planning time, choose and record one Role Execution Mode:

- `same-agent`: one agent performs Planner, Implementer, Validator, Reviewer, and Closer sequentially.
- `hybrid-team`: the main agent implements, while at least Validator or Reviewer runs as a real independent subagent.
- `independent-team`: multiple real agents own separate role gates or disjoint implementation slices.

Check visible tool availability before choosing team mode. If subagent/team tools are available, prefer an independent Validator or Reviewer for complex, high-risk, user-intent-sensitive, or cross-module work. If subagents are unavailable, the task is small/low-risk, or delegation would create more coordination risk than value, use `same-agent` and record the fallback reason. Never claim that a separate agent planned, validated, reviewed, or closed unless that agent actually ran and its evidence is available.

Before relying on subagent evidence in a session, run a bounded delegation health check or use a recent successful subagent result from the same session. Delegate narrow tasks: one role, one question, one file set, clear output shape, and no broad repo exploration unless that exploration is the assigned job. If a subagent times out, close it, record the timeout, do not claim independent evidence, and either split the task smaller or fall back to `same-agent` with the stricter review checklist.

Use the Delegation Healthcheck Protocol in `references/roles-and-state.md` before showing `/subagent` or recording independent Validator/Reviewer evidence. The protocol checks ping, scoped review, broader review when needed, and timeout/fallback recording.

Do not guess delegation failure causes. If a subagent attempt fails, times out, or returns unusable evidence, classify the cause only from observed data. Run bounded comparison tests when practical, such as ping, scoped file review, and a deliberately broader review, then record what passed, what failed, and what remains unknown. If the failing condition cannot be reproduced or isolated, keep the cause `unverified` and do not present the fallback as proof that the original failure was due to prompt size, tool health, or model behavior.

Keep Fact / Hypothesis / Decision / Verification separate:

- `Fact`: observed evidence only, such as command output, tool result, file diff, runtime behavior, or user-confirmed statement.
- `Hypothesis`: possible explanation or option for brainstorming. Hypotheses are allowed, but must be labeled as unverified until tested.
- `Decision`: the next action chosen from facts or explicit hypotheses, such as the experiment, implementation change, or fallback path to try.
- `Verification`: evidence that proves, disproves, or narrows a hypothesis or acceptance claim.

Accepted evidence can use Facts and Verification. It cannot use an unverified Hypothesis as if it were a Fact. Unresolved hypotheses belong in `Unverified Items`, `Residual Risks`, or the next experiment plan.

## Risk And Weakness Taxonomy

When the agent reviews idea-to-code architecture, control gaps, or "what remains weak", it must classify every listed weakness with one of these statuses:

- `already hardened`: the skill already has rules, commands, tests, or installed behavior that address the issue. Cite the evidence and do not present it as new work.
- `residual risk`: the issue was hardened but the current skill/runtime cannot fully prevent it. State the remaining failure mode.
- `new gap`: the issue lacks a current rule, command, test, benchmark, or state path. State the proposed next TASK/REQ direction.
- `external validation`: the rule or artifact exists, but fresh-session, multi-agent, user acceptance, or environment validation has not been run.

Do not mix old and new weaknesses in one unlabeled list. If the user asks why a repeated weakness is still listed, answer by mapping it to this taxonomy and the prior evidence.

Every weakness classification must also name an enforcement boundary:

- `repo-enforced`: enforced by repository code, tests, CLI commands, or committed artifacts.
- `skill-enforced`: required by skill rules, bundle state, role evidence, verification, or closeout checks, but still agent-mediated.
- `host-required`: cannot be guaranteed by this repository or skill alone; it requires Codex host/tool support such as a native pre-edit hook or external fresh-session runner.

Do not repeatedly convert `host-required` residual risks into repo-only TODOs. A host-required item may be tracked as a product integration request or external validation item, but do not claim it can be perfectly solved by adding more skill prose, tests, or bundle rules.

Review-discovered TODO capture rule: when a review, weakness list, architecture assessment, or mixed-response review identifies a `new gap`, the answer must state whether that gap should enter TODO/REQ/backlog, be deferred, or be rejected. Do not silently drop a `new gap` after mentioning it, and do not describe it as completed unless a TASK/REQ with validation evidence already covers it. When the user asks to continue implementation, convert accepted TODO candidates into tracked REQ/TASK scope before editing.

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
2. Fill intake gate, Controlled Exploration, requirements, task classification, acceptance matrix, design, and implementation checklist.
3. Mark the implementation gate READY only after intake is resolved.
4. Record Planner evidence.
5. Execute the checklist, validate, review, checkpoint, run pre-close verification, close, finalize, and run final verification.

### Tracked Work Compliance Checklist

For tracked idea-to-code work, these checks are mandatory, not style preferences:

- **Rule loading**: every agent, subagent, or role simulation using idea-to-code must read `SKILL.md` as the behavior authority and then read only the relevant referenced files before acting. Do not rely on partial snippets, old chat memory, or historical bundle ledgers as the source of behavior rules.
- **Delegation evidence rule**: claims about independent agents, subagents, fresh agents, hybrid-team, or independent-team evidence require a current usable `delegation record`. Planned, timed-out, unusable, or unverified attempts must be recorded as such and surfaced by `delegation status`, `verify`, and `render-status`; they are not evidence of compliance.
- **Non-bypassable pre-edit self-check**: immediately before calling any file-editing tool for tracked work, stop and confirm in the agent's own working context that the current user-visible conversation already contains the focused READY TASK excerpt for the exact TASK/REQ and files about to be edited. If that visible excerpt is missing, do not edit. Run or reuse `implementation show-ready --task <TASK-ID>`, send the focused READY excerpt as a normal assistant message, then continue only after that message is visible.
- **Before any tracked repository or artifact edit**: resolve the current bundle, run or reuse `implementation ready` / `implementation show-ready --task <TASK-ID>`, and paste the relevant READY TASK excerpt in a normal assistant message. This applies to code, docs, tests, config, scripts, and tracked bundle artifacts. Reusing a prior READY result still requires showing the relevant excerpt again before the current edit unless the user explicitly waived repeated visibility after an initial visible READY excerpt. Tool stdout, folded transcripts, and internal notes do not satisfy this requirement.
- **Before implementation READY**: generate or reuse the current `exploration render` output and surface it in a normal assistant message before the READY TASK excerpt. `implementation ready` prints Exploration Visibility Gate output before READY when it must refresh it, but the agent must still make that output visible to the user. Tool stdout, folded transcripts, and internal notes are not enough by themselves.
- **Before final tracked handoff**: for install, validation, commit, delivery, blocked, review, keep/revise/rollback, or final status responses, run `render-status` first. If `render-status` is unavailable or fails, state that reason and then use the fixed Console Response Contract fields manually.
- **Mapping rule**: every formal tracked `Changes`, `Completed Items`, `Incomplete Items`, and `Validation Results` bullet must map to the visible Exploration Visibility Gate output and READY TASK/REQ excerpt that were shown before execution.
- **Same-session continuity rule**: within one conversation session, related ideas, corrections, numbered lists, scope decisions, and completion claims must remain traceable and consistent across turns. Before answering or acting on a related follow-up, audit the prior related scope from the active bundle, visible READY/Exploration outputs, explicit conversation context, and `idea status`. Record material follow-ups with `session audit` and, when the follow-up changes or clarifies the idea itself, `idea record`. If the relationship is unclear, classify or ask; do not silently reinterpret it. Unrelated questions may stay ordinary concise answers and must not be forced into the active bundle.
- **Idea record rule**: every material same-session idea, correction, deferral, rejection, or completion that later status may need to reference must have a stable `IDEA-*` record in `state.json`. Use `idea record --id IDEA-* --status active|completed|deferred|rejected|superseded|blocked|reference --summary "<English summary>" --related-reqs "<REQs>" --notes "<English trace notes>"`. Status, READY, and final handoff must preserve IDEA/TASK/REQ mapping when more than one idea record exists or when the user refers back to a prior idea.
- **Scope classification rule**: material follow-ups must be classified as `same-scope`, `scope-correction`, `new-related-scope`, or `unrelated` before planning, editing, or claiming status. Use `scope classify` when the classification affects the active idea flow. Related corrections must not be treated as ordinary answers; unrelated answers must not be forced into tracked work.
- **Master backlog rule**: when one user request contains multiple related issues, risks, ideas, or numbered work items, record them as stable master backlog IDs such as `MB-1..MB-N` before implementation. Run `backlog sync` so the IDs live in `state.json`. READY, status, checkpoint, and closeout must keep incomplete MB IDs visible; do not claim "all done" while any MB item is pending, active, blocked, or uncovered.
- **Stable enumeration traceability rule**: when the user gives, asks about, or the agent creates a numbered issue list, treat those numbers as stable scope IDs for that discussion. Later references such as "the 1-7", "item 3", or "all seven" must use the same meanings or include an explicit mapping table with `Previous ID`, `Current ID`, and `Change Reason`. Do not create a fresh unrelated 1-7 list and imply it corresponds to the earlier list. If the mapping is unclear, answer with an audit/mapping clarification before planning or claiming progress.
- **Noncompliance rule**: if the visible READY excerpt or fixed final status fields were missed, say so plainly, correct the process, and do not present the run as fully compliant.
- **Late READY rule**: printing READY after edits have already started is remediation only. It does not make earlier edits compliant. Record the lapse in Reviewer or final status, tighten guidance or tests when the lapse exposed an instruction gap, and continue only after the corrected READY excerpt is visible.
- **Current TASK entry rule**: before editing files for each TASK/IMP, run or reuse `implementation enter-task --task <TASK-ID>` so the current TASK is machine-recorded and its READY Focus is visible. `implementation show-ready --task <TASK-ID>` is acceptable only as a display fallback when state mutation is impossible; record the reason.
- **Implementation lease rule**: before any tracked implementation edit, acquire a write lease with `implementation lease acquire --task <TASK-ID> --owner <agent-or-session> --file <path>`, then run `implementation pre-edit`. The lease is required for same-agent and multi-agent implementation edits so the guard behavior is consistent. Overlapping active leases for different owners are refused. Validator/Reviewer/read-only subagents do not need write leases unless they edit files.
- **Pre-edit guard rule**: immediately after `enter-task` and before tracked file edits, run `implementation pre-edit --task <TASK-ID> --file <path>` for every file about to be edited. It must print `PRE_EDIT_OK_ID`; Implementer evidence must cite that ID. The guard is recorded in `pre_edit_records`; missing, stale, wrong-task, or incomplete file coverage must be refused or surfaced by `implementation status`, `verify`, and `render-status`. If an edit already happened without the guard, record it with `implementation noncompliance` and do not present the run as fully compliant until the lapse is resolved or explicitly carried as risk.
- **Tool-layer edit wrapper rule**: `implementation guarded-apply --task <TASK-ID> --patch-file <path>` is the default tracked edit path when an edit can be represented as a git patch. The wrapper resolves the active bundle, checks patch paths, requires visible Exploration and READY Focus for the current TASK, requires a non-overlapping lease, runs `implementation pre-edit`, captures `PRE_EDIT_OK_ID`, verifies the patch with `git apply --check`, then applies it with `git apply`. If a tracked edit cannot use `guarded-apply`, record a fallback reason in Implementer evidence and still cite the current `READY_TASK_OUTPUT_ID` and `PRE_EDIT_OK_ID`; do not describe the fallback edit as wrapper-compliant. Current Codex-native edit tools are still not host-level blocked by this skill; until host pre-edit hooks exist, native-tool bypass remains a `residual risk` and must not be described as impossible.
- **Multi-role regression rule**: after changing lifecycle, exploration, READY, validation, review, or output-compliance guidance, run or update the multi-role output compliance scenario in `references/roles-and-state.md#multi-role-output-compliance`, covering Planner, Implementer, Validator, Reviewer, Closer, and ordinary-answer boundary expectations, then record expected versus observed behavior and any instruction drift.

This checklist does not apply to ordinary untracked explanations, naming discussions, or lightweight commentary updates; those remain concise while still using the required role/source prefix when this skill is active.

Action boundary for this checklist:

- `tracked-edit`: repository files, skill files, tests, config, scripts, or tracked bundle artifacts are about to be changed for a READY TASK/REQ. Run the pre-edit self-check and require visible READY first.
- `plan-correction`: bundle planning files are being corrected so READY can accurately describe the work. Make the smallest planning correction, refresh READY, then run the tracked-edit branch before implementation edits.
- `read-only-status`: the user asks status/progress/where are we. Read allowed current bundle state and answer or use `render-status` for formal tracked status; do not run pre-edit READY because no edit is starting.
- `ordinary-answer`: explanation, naming discussion, clarification, or lightweight working update without file edits. Keep the answer natural and concise; do not use the fixed status fields and do not run READY only for the answer.
- `formal-tracked-handoff`: install, validation, commit, delivery, blocked, review, keep/revise/rollback, or final status for tracked work. Run `render-status` first, or state why unavailable and use the fixed field contract manually.
- `related-session-follow-up`: the user refers to previous work, says "we", "this flow", "all tasks", "the earlier issue", "continue", "is it done", "you said", or otherwise ties the message to prior session context. First audit the related scope and state whether it is `same scope`, `scope correction`, `new related scope`, or `unrelated ordinary answer`. Do not answer from only the most recent local bundle if older related context in the same conversation is material.
- `multi-issue-master-backlog`: the user gives several related problems or asks to fix a list such as "1-6". Create stable `MB-*` IDs, register matching REQ/TASK coverage, run `backlog sync`, and show which MB IDs are Required Now, pending, deferred, or out of scope before implementation.
- `enumerated-scope-reference`: the user refers to a prior numbered list, such as "the 1-7", "number 4", "all seven", "A/B/C", or "the above points". First preserve or reconstruct the exact prior IDs. If a new grouping is useful, show a mapping table before using the new grouping. Do not continue with an unannounced renumbering.

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

After Intake Gate and before Task Classification, record Controlled Exploration in `00-idea.md`. This is the controlled brainstorming step: it explores uncertainty only when needed, records options as hypotheses, and forces one decision before implementation planning.

Use this shape:

```text
## Controlled Exploration

- Exploration Needed: yes|no
- Trigger: <why exploration is needed or safely skipped>
- Constraints:
  - <hard constraint from user, repository, governance, or runtime>
- Planned Scope:
  - Required Now: <scope included in the next READY output>
  - Deferred: <scope explicitly excluded or postponed>
  - What READY Will Cover: <TASK/REQ scope allowed after this exploration output>
- Options Considered:
  - Option A: <approach>
    - Hypothesis:
    - Fit to user goal:
    - Cost:
    - Risk:
    - Verification path:
    - Rejection condition:
- Decision:
  - Chosen option:
  - Decision reason:
  - Rejected options:
  - Unverified items:
```

Decision table:

| Condition | Exploration Needed | Action |
|---|---:|---|
| Clear, low-risk task with one direct path | no | Record the skip Trigger and continue. |
| Real user-visible, architecture, API, cross-module, security, data, cost, migration, destructive-action, ambiguity, failure-cause, verification, or meaningful risk fork | yes | Compare 2-4 options and choose one decision before `implementation ready`. |
| User's requested implementation is clearly flawed | yes | Treat it as a candidate, explain the issue, and recommend a better default path. |

Controlled Exploration is not a hidden planning note. It must be surfaced through the Exploration Visibility Gate before READY.

The Exploration Visibility Gate must separate `Planned Scope` from `Decision Options`. `Planned Scope` is the execution scope: required-now items, deferred items, and what READY may cover. `Decision Options` is only for mutually exclusive route choices or candidate approaches. Do not ask the user to choose among required scope items, and do not hide deferred or rejected scope inside option prose. New or revised bundles must record `Planned Scope` structurally in `00-idea.md`; legacy bundles may render fallback text, but current work should not rely on fallback text when scope was discussed.

Use three display layers:

- `Exploration Result` / `Exploration Decision Request`: shows user goal, `Planned Scope`, route decision/options, and what can move to READY.
- `READY Focus`: shows the current TASK/REQ info that is about to be edited or executed.
- `Full Plan`: shows all TASK/IMP blocks only for audit, review, or explicit `--full-plan` use.

When `Need Confirmation: no`, the Planner chooses and records the decision autonomously, then shows the `Planned Scope`, selected approach, and why it will proceed. Do not dump alternative routes or ask for routine approval.

When `Need Confirmation: yes`, include `Planned Scope`, the `Decision Options` list, recommended decision, and explicit reply choices in one confirmation request so the user can approve, choose another option, correct scope, ask to explore more, pause, or cancel.

Exploration Revision Rule:

- If the user changes the exploration output, rejects options, defers part of the planned scope, proposes a new route, or asks to explore more in a direction, treat it as a plan-changing clarification/switch before READY.
- Generate a new `EXPLORATION_OUTPUT_ID`; do not reuse the prior exploration output as proof of the revised scope.
- The revised Exploration Visibility Gate must explicitly show:
  - `Required Now`
  - `Deferred`
  - `Rejected Options`
  - `New / Selected Option`
  - `What READY Will Cover`
- If the user only gives a direction, not a concrete route, do not pretend a route is selected. Produce a revised `Confirmation Required` output with new candidate options generated from that direction, a recommendation, and `explore more: <direction>` still available.
- If the user explicitly selects a clear route and no true confirmation risk remains, produce `Exploration Result` and proceed to READY for `Required Now` only.

The user-visible shapes are:

```text
[idea-to-code][Planner/agent] Exploration Result | Bundle: <slug>
EXPLORATION_OUTPUT_ID: <id>
Display Layer: Exploration Result
Next Layer: READY Focus after this output is visible; Full Plan only on --full-plan.
Planned Scope:
- Required Now: <scope included now>
- Deferred: <scope excluded from this execution>
- What READY Will Cover: <TASK/REQ scope allowed in READY>
Selected Approach:
- <chosen option>
Why This Approach:
- <decision reason>
Implementation Will Proceed To:
- Implementation Gate READY after this exploration output is visible.
```

```text
[idea-to-code][Planner/agent] Confirmation Required | Bundle: <slug>
EXPLORATION_OUTPUT_ID: <id>
Display Layer: Exploration Decision Request
Next Layer: READY Focus after this output is visible; Full Plan only on --full-plan.
Planned Scope:
- Required Now: <scope included now>
- Deferred: <scope excluded from this execution>
- What READY Will Cover: <TASK/REQ scope allowed after confirmation>
Decision Options:
- <2-4 options when exploration is needed>
Recommended Option:
- <chosen option>
Please reply with one of:
- approve
- choose: <option>
- change: <correction>
- explore more: <direction>
- pause
- cancel
```

For revised exploration, use this additional shape before either `Exploration Result` or `Confirmation Required` details:

```text
Exploration Revision:
- Required Now: <scope that remains in this execution>
- Deferred: <scope explicitly postponed>
- Rejected Options: <routes or assumptions the user rejected>
- New / Selected Option: <new route, or "direction only - more options needed">
- What READY Will Cover: <REQ/TASK scope that can appear in READY after approval>
```

Default to `Exploration Needed: no`. Use `yes` only for a real fork or risk. The goal is better decisions with less user burden, not more process.

Small-task friction remains a hard guardrail: clear README, typo, single-file config, or direct documentation updates should normally record `Exploration Needed: no` and proceed without option dumping or routine confirmation.

For `Exploration Needed: yes`, the chosen option is not accepted just because it was selected. Later validation and review must check whether the selected option's `Decision reason` and `Verification path` held up. If an exploration hypothesis remains unverified, keep it in `Unverified Items`, `Residual Risks`, or a follow-up verification path instead of presenting it as fact.

Judge recommendation quality by whether the selected path improves user-goal fit, reduces risk or cost, preserves user constraints and non-goal boundaries, and is verifiable.

Opening a bundle is allowed as task capture. Product-code edits are not allowed until `Need Confirmation: no`, the Exploration Visibility Gate output is current for the plan revision, any Exploration Revision fields are reflected in the plan, and the implementation gate is READY.

Use `Need Confirmation: yes` when the idea is ambiguous, risky, architecture-shaping, security-sensitive, destructive, expensive, changes user-visible behavior in multiple plausible ways, or contradicts project governance. Ask the user to confirm or correct the intake before marking implementation ready.

Use `Need Confirmation: no` when the task is clear, low-risk, reversible, and the acceptance criteria can be stated concretely. In that case, restate the intake and proceed autonomously without asking a routine confirmation question.

`Need Confirmation: no` skips the approval wait; it does not skip exploration and task-list visibility. `implementation ready` prints the generated Exploration Visibility Gate output when needed and then the `[idea-to-code][Planner/agent] Implementation Gate: READY` output, or `[idea-to-code/<profile>][Planner/agent] Implementation Gate: READY` when an upper-layer skill passes a profile, including `EXPLORATION_OUTPUT_ID` and `READY_TASK_OUTPUT_ID`; send both outputs to the user before any product-file edit, and only then continue implementation. By default, READY prints the focused first TASK/IMP excerpt and records `ready_task_output_scope: focused-default`; use `implementation ready --full-plan` or `implementation show-ready --full-plan` only when a full audit list is needed. The full READY plan remains in `00-idea.md`. Command stdout, tool output, or a folded transcript is not enough by itself; the Exploration Result plus READY TASK list or focused excerpt for the TASKs about to be executed must appear in normal assistant messages. Every time execution enters a different current TASK, show that TASK's focused READY info with `implementation show-ready --task TASK-N` before editing files for that TASK, unless the user explicitly waived repeated visibility after the first display. Profile prefixes are display-only: they do not alter lifecycle gates, bundle state, requirements, role evidence, checkpoints, ledger semantics, finalize behavior, or permissions. This message is transparency, not an approval request, so continue implementation immediately after sending it unless the user interrupts.

For clear, low-risk, single-slice tasks such as a small README or documentation edit, prefer the lightweight quickstart path instead of manually drafting every bundle section:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" quickstart \
  --root "$(pwd)" \
  --slug <short-task-slug> \
  --title "<short title>" \
  --idea "<restated user goal>" \
  --file <primary-file> \
  --task "<concrete TASK-1 description>" \
  --unique
```

Quickstart creates the current bundle, fills intake, Controlled Exploration with `Exploration Needed: no`, REQ-1, acceptance matrix, design, and TASK-1, records an Exploration Visibility Gate output, marks implementation ready, records Planner evidence, and prints the generated READY TASK output with `EXPLORATION_OUTPUT_ID`. It does not replace confirmation for ambiguous, risky, destructive, security-sensitive, or multi-interpretation work; use the full intake and confirmation flow for those tasks. Paste the quickstart READY output to the user, then continue unless interrupted.

Use `quickstart --json` only for automation that needs pure machine-readable output; the default output intentionally includes the READY TASK text for agent/user visibility.

When `Need Confirmation: yes`, the user-visible response must be an explicit decision request, not a status paragraph that hides the ask. The confirmation output must restate the user goal as a hard rule before asking for approval: the user must be able to see what the agent believes it will do, what observable acceptance outcome will prove it, and which planned TASK items will be executed. Use this confirmation shape:

```text
[idea-to-code][Planner/agent] Confirmation Required

I have paused before implementation because: <risk or ambiguity>.

Restated user goal:
- <what I understand the user wants, in implementation terms>

Observable acceptance outcome:
- <what the user should be able to observe when this is done>

Controlled Exploration:
- Exploration Needed: yes
- Real user goal:
  - <underlying outcome the user is trying to achieve>
- Issue with requested approach, if any:
  - <why the user's proposed implementation is risky, misaligned, or more costly than needed>
- Options Considered:
  - Option A: <approach, fit, cost, risk, verification, rejection condition>
  - Option B: <approach, fit, cost, risk, verification, rejection condition>
- Recommended decision:
  - <chosen option and why>

Proposed scope after approval:
- <specific work I will do>
- <specific verification I will run>

Planned TASK list before approval:

TASK-1: <change point>
Files:
- <known files or ... while the plan is still DRAFT>
Execution Details:
- <specific execution details or ... while the plan is still DRAFT>
Done Criteria:
- <how this item will be complete>
Planned Verification:
- <command, runtime check, or evidence target>

TASK-2: <next change point, if needed>

Please reply with one of:
- "yes" or "approved" to proceed with the recommended decision and scope.
- "change: <correction>" to choose another option or adjust the scope before implementation.
- "pause" to leave the bundle open without coding.
- "cancel" to archive or close this idea without implementation.

If approved, next step: I will update Intake Gate to `Need Confirmation: no`, update Controlled Exploration with the confirmed decision, replace any DRAFT placeholders with concrete task details, rerun `implementation ready`, print the READY TASK list, then start TASK-1.
```

The response must make the required user action obvious in the first screen: why work is paused, the restated user goal, the observable acceptance outcome, the Controlled Exploration recommendation when exploration is needed, what will be done, the planned TASK list, how the user can approve or correct it, and what happens next. Do not rely on phrases like "confirm this" without examples. Do not present A/B/C as an undecided homework assignment; recommend one default path and let `change: <correction>` handle disagreement.

The restated user goal is also the acceptance anchor for closeout. During final response, Completed Items, Incomplete Items, and Unverified Items must map back to that restated goal and the approved TASK list so the user can see whether any requested work was missed, dropped, or drifted.

If the user says the original idea was wrong:

- same idea with corrected details: record `clarification --changes-plan yes`, update intake/requirements/design/implementation, then rerun `implementation ready`;
- added acceptance or boundary case: record `expand --changes-plan yes`;
- replacement direction: record `switch --changes-plan yes` in the same bundle;
- unrelated task: record `new-task --changes-plan no`, archive the current bundle, then initialize the new task;
- canceled idea: archive or close with a concrete reason, do not delete evidence.

During autonomous delivery, do not ask routine "continue?" questions. Work through the implementation checklist until completion. Interrupt only for:

- implementation gate failure or missing Controlled Exploration / implementation-plan details in `00-idea.md`
- architecture/scope ambiguity that changes user-visible behavior
- destructive or irreversible action
- missing credential, permission, external service, or environment capability
- implementation plan contradicts the actual codebase in a way that needs a scope decision
- verification fails and cannot be fixed within the confirmed checklist

If the user provides a new consideration while work is active, classify it as continue, expand, switch, new-task, status, pause, blocked, clarification, or no-op before acting. Do not initialize a new bundle while an unfinished current bundle exists.

Mission-control rule: every non-trivial incoming request must first be routed against `.idea-to-code/current.json`. By default, a slug is a session ledger: one continuous conversation/cooperation context may contain multiple ideas, and those ideas are tracked as scoped IDEA/REQ/TASK units inside the same slug. `current.json` is the active session pointer, not proof that another chat session or agent should reuse that slug.

Session-ledger rule:

- Same conversation session: continue the current slug. A new idea in the same session becomes a new IDEA-scoped unit with its own REQ/TASK coverage; do not create one slug per user utterance or per idea by default.
- Same idea with corrected details: keep the same IDEA scope when possible, or add a follow-up TASK/REQ under that IDEA.
- New chat session or explicitly separate task/session: start a new slug. Record `new-task --changes-plan no` on the current bundle when needed, archive or finalize the current session as appropriate, then initialize the new session slug.
- Follow-up to an earlier idea inside the same session: keep the same session slug and add a scoped follow-up such as `IDEA-1 follow-up`, new REQ IDs, and new TASKs.
- Follow-up to a prior session: start a new session slug and cite the old session slug plus IDEA/REQ/TASK when known as `Related Session` / `Related IDEA`. Do not move, rewrite, or merge the historical ledger.
- Cross-session or cross-agent stale current: do not assume another conversation belongs to the old active slug just because `current.json` exists. Parallel sessions should use separate slugs or an explicitly selected slug.

Slug count control: one session ledger may contain many user inputs and multiple ideas because they share conversation context. Parallel sessions use separate slugs. A session that becomes too broad can be archived and a new session slug started by explicit user or agent decision.

Multi-agent ledger ownership:

- Same session ledger, parallel agents: use the same slug only after Planner assigns disjoint IDEA/TASK/REQ ownership and file/module write boundaries. Each agent must re-read `current status` before mutating, cite the visible READY excerpt for its TASK, and record role evidence/checkpoints against the shared slug.
- Different chat sessions, parallel agents: use separate slugs. Do not record independent live sessions in one bundle just because they run in the same repository or time window.
- Validator or Reviewer subagents: normally do not create a new slug. Record their evidence under the parent implementation slug with `/subagent` only when a real subagent returned usable evidence.
- Worker subagents implementing disjoint slices: stay in the parent slug when the slices are part of the same session ledger and assigned IDEA/TASK scope; their file ownership must be explicit before edits.
- Current pointer safety: before any agent archives, initializes, sets, resumes, or mutates a bundle, it must re-check `.idea-to-code/current.json`. If another agent changed current, reroute instead of writing to the previously assumed slug.

Historical bundle boundary: `.idea-to-code/<slug>` directories are persistent recovery and audit ledgers, not default repository context. Do not scan every historical bundle or treat old `00-idea.md`, `01-progress.md`, or `state.json` contents as current task context. Read a historical bundle only when `.idea-to-code/current.json` points to that slug, the user explicitly asks to resume or inspect that slug, or a lifecycle command such as `current status`, `ledger`, `verify`, or `current resume --slug` requires it. If `current.json` is missing, do not infer context by reading all bundle directories; ask for a known unfinished slug, use the history/current commands, or initialize a new bundle according to the workflow.

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
- `requires_unblock: true` means resolve the blocker and run `unblock` before implementation or ordinary mutation.
- A blocked bundle may still record another real blocker or be archived for an unrelated new task; it must not use pause/resume, status updates, or route output to hide unresolved blockers or make product edits eligible before unblock.
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
- New idea inside the same conversation session: record `expand --changes-plan yes`, add an IDEA-scoped REQ/TASK set, update requirements/design/implementation, rerun `implementation ready`, and continue in the same slug.
- Explicitly separate task or new chat session: record `new-task --changes-plan no` on the current bundle when needed, archive or finalize the current session slug, then run `init` for the new session slug.
- Follow-up on an earlier idea in the same session: add a scoped follow-up TASK/REQ under that IDEA; follow-up from a different session starts a new session slug and references the old session/IDEA.
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
- Pending plan update: `pending_plan_update` means user input changed the plan but requirements/design/implementation have not all been refreshed yet; `pending_plan_update_sections` names the stale sections when available. Updating only one named section must not clear the gate for the others. Older bundles without section metadata keep the legacy boolean gate. Do not edit code or close while this is true.
- Verification state: `last_verify_ok` and `last_verified_plan_revision` show whether current-plan pre-close verification passed.
- Closeout state: `gate_status`, `decision`, and `closeout_status` summarize acceptance after finalize.

On a new session or after interruption:

1. Run `doctor`, `current status`, or `route` with the latest user request.
2. Resolve the active bundle from `.idea-to-code/current.json`.
   If `current.json` is missing but the user knows the unfinished slug, restore it explicitly:
   ```bash
   python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" current resume \
     --root "$(pwd)" \
     --slug <known-unfinished-slug> \
     --reason "<why work is resuming>"
   ```
   This safely sets that unfinished bundle as current and resumes it if it was paused. It refuses missing, completed, or closed slugs and refuses to switch away from a different unfinished current bundle.
3. Inspect `state.json`, `00-idea.md`, role evidence, milestones, blocks, and user input decisions only for the resolved active bundle or for a user-specified slug being explicitly restored or audited. Historical bundle ledgers are recovery records; they must not become implicit context for unrelated work.
4. If `state` is `blocked` or `paused`, report the resume condition before editing.
5. If `state` is `paused`, run `current resume --reason "<why work is resuming>"` only after the user resumes.
6. If `pending_plan_update` is true, update every stale section named by `pending_plan_update_sections` before coding, then rerun `implementation ready`. If no stale section list is available, refresh the plan under the legacy boolean gate before coding.
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

For structured audit visibility:

- Run `status --full` for the machine-readable lifecycle account: requirements, user inputs, role evidence, milestones, blockers, verification state, and closeout.
- Run `ledger --root "$(pwd)" --slug <slug>` or open `01-progress.md` for the human-readable lifecycle event trail.
- Use `record add/list` for observed local sub-records: `A` acceptance, `D` discovery, `I` iteration, `R` risk, `V` validation, and `F` follow-up.
- Use `01-progress.md` for delivered slices and REQ coverage.
- Use `01-progress.md` for validation history.

`01-progress.md` is not a file-write audit log. Ordinary `update` commands update the relevant section and `state.json`, but they do not append human ledger noise. The ledger records lifecycle-significant events: init, requirement changes, implementation-ready, role evidence, local records, checkpoints, verification, blockers, pause/resume/archive, and finalize.

Project-level state:

- `.idea-to-code/current.json` points to exactly one active bundle.
- `.idea-to-code/history/index.jsonl` records closed bundles. Do not move old bundle directories; history is an index, not storage.
- New bundle slugs must use `YYYYMMDD-HHMM-<normalized-task-title>` in local project time. Use `init --unique` to create this shape; collisions append `-02`, `-03`, etc.
- Mutating commands must operate on the current bundle. `update`, `implementation ready`, `requirement add/remove`, `role record`, `checkpoint`, `link`, `block`, `unblock`, `rebuild-progress`, and `finalize` refuse non-current bundles.
- While a bundle is blocked, ordinary implementation mutations remain refused until `unblock`; `block` may append additional real blockers, and new-task/archive bookkeeping may park the blocked bundle without pretending the blocker was resolved.
- `verify` may inspect any bundle, including a finalized bundle, but writes `last_verify_*` only for the current bundle when it is not paused, completed, or closed.
- `current set` refuses completed or closed bundles; closed work cannot be resumed into `in_progress`.
- `current resume --slug <known-unfinished-slug> --reason "<reason>"` restores a known unfinished bundle as current after interruption; if it is paused, it resumes to `in_progress`, otherwise it preserves the existing unfinished state while restoring the pointer.
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
5. **Fill `00-idea.md` sections** with the `update` subcommand - don't leave them as empty templates. `00-idea.md` must include Intake Gate, Controlled Exploration, Task Classification, and an Acceptance Matrix row for each open `REQ-*`:
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
   Add requirements before marking READY whenever possible. Adding a requirement after READY, checkpoint, or role evidence invalidates the READY gate and requires refreshing requirements/design/implementation before implementation continues. Removing requirements after READY or execution evidence remains refused instead of silently changing scope.
6. **Inspect the current codebase, docs, project governance, and runnable paths** before proposing structure. If project-local rules define authority order, module boundaries, real product paths, validation types, or closeout gates, obey them before generic skill defaults.
7. **Decide the next smallest milestone** that creates real progress and keeps the system runnable.
8. **Before editing, fill and print `00-idea.md`.** This is the implementation gate. "Print" means send the task list in a user-visible assistant/commentary message; writing it only to `00-idea.md`, command stdout, a tool result, folded transcript, or internal notes is not enough. During intake and discovery, use the same `TASK-ID` or `IMP-ID` items as the visible task list; placeholder detail values such as `...` are acceptable while `Gate Status` is `DRAFT`. Use this shape even when there is only one task. Before marking the gate `READY`, replace every placeholder with concrete details that are specific enough to verify but not so fine-grained that they describe every line edit:
   ```text
   [idea-to-code][Planner/agent] Implementation Gate: DRAFT
   Bundle: .idea-to-code/<slug>
   Plan: 00-idea.md

   TASK-1: <change point>
   Files: ...
   Execution Details: ...
   Done Criteria: ...
   Planned Verification: ...

   TASK-2: ...
   ```
   Create items for user-visible behavior, protocol/API/data model changes, persistence/state changes, UI workflows, risky refactors, and test/acceptance paths. Do not create items for trivial mechanical edits unless they carry separate acceptance risk.
   Mark the gate ready only after every TASK has concrete, non-placeholder `Files`, `Execution Details`, `Done Criteria`, and `Planned Verification`:
   ```bash
   python ".../idea_to_code_bundle.py" implementation ready --root "$(pwd)" --slug <slug>
   ```
   If this command fails, refine the plan only. Do not edit code. `implementation ready` refuses unresolved confirmation, missing Controlled Exploration, required exploration without a decision, missing current Exploration Visibility Gate output, or placeholder task details. `checkpoint`, `verify`, and `finalize` are script-guarded against a non-ready implementation gate.
   When this command succeeds, it prints the user-visible `[idea-to-code][Planner/agent] Implementation Gate: READY` message with every TASK, `Files`, `Execution Details`, `Done Criteria`, `Planned Verification`, and `READY_TASK_OUTPUT_ID`. When another skill uses idea-to-code as a lifecycle foundation, it may pass `--profile <profile-name>` so the READY message starts with `[idea-to-code/<profile-name>][Planner/agent]`. The profile is display-only and must not be treated as bundle state, requirement scope, role evidence, or lifecycle policy. Do not infer trust, ownership, permissions, or scope from a profile name; it is only a user-visible label.

   Tool stdout or folded command transcripts are not enough for READY visibility. READY visibility has two layers:

   - **Plan-level READY**: the full implementation plan remains in `00-idea.md` and full READY output for traceability.
   - **Execution-level READY**: before executing each TASK in multi-task work, send a normal assistant message with the current TASK's focused READY excerpt.

   For multi-task work, default the user-visible execution message to the current TASK, not the entire long task list. `implementation ready` and `implementation show-ready` default to the first TASK/IMP focused excerpt; use `--task TASK-N` to print another focused READY TASK excerpt, and `--full-plan` only for a complete audit list. The generated READY output has a hard contract: every visible TASK/IMP block must include the `TASK-*` or `IMP-*` line, covered `REQ-*` or the script's covered REQ hint when inferable, `Files`, `Done Criteria`, and `Planned Verification`. If any of those fields are missing, the READY output is invalid and must be regenerated or fixed before product-file edits. Before moving from TASK-1 to TASK-2, show the TASK-2 focused READY excerpt / focused READY TASK excerpt unless the user explicitly asks to skip repeated visibility. This is not only a full-list-once rule: every current TASK transition needs visible task info for that TASK. The final formal result template must map each completed, incomplete, and validated item back to the same visible TASK/REQ excerpts.

   Preferred TASK entry command:
   ```bash
   python ".../idea_to_code_bundle.py" implementation enter-task --root "$(pwd)" --slug <slug> --task TASK-1
   ```
   `enter-task` records `current_task_id`, preserves the existing `READY_TASK_OUTPUT_ID`, and prints `Display Layer: READY Focus`. Use it before edits for TASK-1 and again before every TASK transition. Use `implementation overview` when the user asks where the work stands; it prints `Planned Scope`, current TASK, next TASKs, and the `--full-plan` audit hint without changing state.

   Required implementation write lease:
   ```bash
   python ".../idea_to_code_bundle.py" implementation lease acquire --root "$(pwd)" --slug <slug> --task TASK-1 --owner agent --file <path>
   python ".../idea_to_code_bundle.py" implementation lease status --root "$(pwd)" --slug <slug>
   python ".../idea_to_code_bundle.py" implementation lease release --root "$(pwd)" --slug <slug> --id <LEASE_ID> --reason "<why>"
   ```
   `lease acquire` refuses overlapping active leases for different owners on the same current plan/READY/file scope. Acquire the lease before `pre-edit`; read-only Validator/Reviewer work does not require a write lease.

   Required pre-edit guard:
   ```bash
   python ".../idea_to_code_bundle.py" implementation pre-edit --root "$(pwd)" --slug <slug> --task TASK-1 --file <path>
   ```
   `pre-edit` refuses when the bundle is not active, Exploration or READY is stale, `current_task_id` does not match, the current TASK entry is older than READY, or the requested file is not listed in that TASK's `Files`. A passing guard prints `PRE_EDIT_OK_ID`, appends a `pre_edit_records` entry, and must cover every file the current TASK will edit before Implementer evidence. Cite it in Implementer evidence together with `READY_TASK_OUTPUT_ID`.

   If an edit begins without a valid guard, record the lapse instead of hiding it:
   ```bash
   python ".../idea_to_code_bundle.py" implementation noncompliance --root "$(pwd)" --slug <slug> --task TASK-1 --reason "<what happened>" --file <path>
   ```
   Open pre-edit noncompliance appears in `implementation status`, `verify`, and `render-status`; accepted closeout must not bury it in technical details.

   Delegation evidence records:
   ```bash
   python ".../idea_to_code_bundle.py" delegation record --root "$(pwd)" --slug <slug> --role reviewer --status usable --scope "<scope>" --evidence-summary "<summary>" --agent-id "<id>"
   python ".../idea_to_code_bundle.py" delegation record --root "$(pwd)" --slug <slug> --role reviewer --status timeout --scope "<scope>" --evidence-summary "<summary>" --reason "<why>"
   python ".../idea_to_code_bundle.py" delegation resolve --root "$(pwd)" --slug <slug> --id <DELEGATION_ID> --resolution fallback-same-agent --reason "<why this closes the finding>"
   python ".../idea_to_code_bundle.py" delegation status --root "$(pwd)" --slug <slug>
   ```
   Use `status usable` only when a real delegated or fresh-agent run returned usable evidence. Timed-out, planned-only, unusable, or unverified attempts must not be cited as independent evidence. They remain open findings until resolved as `fallback-same-agent`, `superseded`, `accepted-risk`, or `invalid-record`; resolving them closes the finding but never turns the attempt into independent evidence.

   Same-session continuity audits:
   ```bash
   python ".../idea_to_code_bundle.py" session audit --root "$(pwd)" --slug <slug> --relation scope-correction --summary "<what changed>" --prior-scope "<prior scope>" --decision "<what this means>"
   python ".../idea_to_code_bundle.py" session status --root "$(pwd)" --slug <slug>
   ```
   Use this before answering, planning, or claiming completion for material related follow-ups in long sessions. `implementation status` and `render-status` surface the latest audit.

   Same-session idea records:
   ```bash
   python ".../idea_to_code_bundle.py" idea record --root "$(pwd)" --slug <slug> --id IDEA-1 --status active --summary "<English idea summary>" --related-reqs "REQ-1,REQ-2" --notes "<English trace notes>"
   python ".../idea_to_code_bundle.py" idea status --root "$(pwd)" --slug <slug>
   ```
   Use this when the user introduces, corrects, rejects, defers, completes, or reopens a material idea in the same conversation. The record is the state-backed link between follow-up conversation, REQs, and formal IDEA/TASK/REQ status mapping.

   Scope classification records:
   ```bash
   python ".../idea_to_code_bundle.py" scope classify --root "$(pwd)" --slug <slug> --classification scope-correction --summary "<message summary>" --rationale "<why>" --action "<next action>"
   python ".../idea_to_code_bundle.py" scope status --root "$(pwd)" --slug <slug>
   ```
   Use this when a follow-up may be same-scope, a correction, a new related scope, or unrelated. The latest classification is visible in `implementation status` and `render-status`.

   Master backlog commands for multi-issue work:
   ```bash
   python ".../idea_to_code_bundle.py" backlog sync --root "$(pwd)" --slug <slug>
   python ".../idea_to_code_bundle.py" backlog status --root "$(pwd)" --slug <slug>
   python ".../idea_to_code_bundle.py" backlog mark --root "$(pwd)" --slug <slug> --id MB-2 --status deferred --reason "<why>"
   ```
   `backlog sync` stores all `MB-*` IDs found in `00-idea.md` into `state.json`. `implementation ready` refuses stale or missing master backlog state when a plan contains multiple MB IDs. `checkpoint` updates covered MB items from covered REQs, and formal status output must keep incomplete MB IDs visible.

   Future extension point: exploration output and full READY lists can become noisy when one idea expands into many TASKs. Preserve this split for now: Exploration Visibility Gate explains why the plan was chosen, and focused READY excerpts explain what will be edited next. A later change may add a grouped or summarized READY overview, but it must keep per-TASK focused READY excerpts and final TASK/REQ mapping intact.

   For `Need Confirmation: no`, do not ask for routine approval after the visible READY task message; continue with TASK-1 unless the user interrupts. Implementer evidence must cite the generated READY output id as `READY_TASK_OUTPUT_ID <id>`. Use `implementation show-ready` to reprint or refresh the READY output for an already-ready bundle.
9. **Record Planner evidence before implementation**:
   Follow the Role Evidence Checklist in `references/roles-and-state.md` before recording any role evidence. Use `role explain --role <role>` as a read-only helper when you need the checklist in JSON form, or after `role record` rejects evidence. `role explain` does not change state and does not replace `role record`.
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
      --role closer --evidence "Pre-close verify passed; prior role evidence is current; REQ-1..REQ-N covered; final decision pass accepted" \
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
- Record Controlled Exploration before implementation planning; use it to compare options only when needed, then choose one decision before coding.
- Render and surface Exploration Visibility Gate output before READY; no tracked edit should begin from READY alone when the exploration decision was not visible.
- Use `implementation enter-task --task <TASK-ID>` before each TASK/IMP edit slice so the current TASK has a machine-recorded entry event and visible READY Focus.
- Use `implementation pre-edit --task <TASK-ID> --file <path>` before tracked edits; no tracked edit should begin without a visible `PRE_EDIT_OK_ID` unless the command is unavailable and the fallback is recorded as noncompliance.
- Never mutate a non-current, paused, completed, or closed bundle to make progress.
- Keep TASK/IMP IDs tied to files, done criteria, and planned verification.
- Record Planner, Implementer, Validator, Reviewer, and Closer evidence in order for the current `plan_revision`.
- Before recording role evidence, follow `references/roles-and-state.md` Role Evidence Checklist; if `role record` rejects evidence, run `role explain --role <role>` and rewrite the evidence instead of weakening the gate.
- Every validation claim must name a validation type; do not inflate mock/source/DOM evidence into real product-path proof.
- When this skill creates test files, record `Test Ownership`: `persistent-product-test`, `project-native-test`, or `task-evidence-only`. Persistent/project-native tests must be visibly namespaced with `idea_to_code` or the task slug; evidence-only scripts and outputs belong under `.idea-to-code/<slug>/artifacts/`.
- Run pre-close `verify` after Reviewer evidence and before Closer/finalize.
- Run final `verify` after finalize.
- Treat bundle upkeep as part of the work product.

For detailed role/state rules, read `references/roles-and-state.md`.
For verification, evidence, and closeout rules, read `references/verification-and-evidence.md`.
For milestone and implementation-plan patterns, read `references/planning-patterns.md`.

When validating this skill itself, prefer the official chunked regression runner when the full unittest suite is too large for one command:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" test-batch --chunk-size 40 --timeout-seconds 180
```

### Installed Skill Parity Checklist

When the tracked work changes this skill's source and the user expects the latest skill to be installed, install closeout is not complete after copying files alone. The formal install or final status must include TASK/REQ-mapped evidence for:

- install target path, normally `$CODEX_HOME/skills/idea-to-code`;
- installed focused tests run from the installed skill copy or against the installed script path;
- source/installed SHA256 parity for the files changed by the batch, including `SKILL.md`, referenced guidance files, scripts, and tests;
- `No commit made` under `Key Technical Details` when no commit was requested or made, not under `Incomplete Items`.

If installed focused tests or source/installed SHA256 parity have not passed, do not claim the latest skill code is installed and verified. Put the missing install evidence under `Unverified Items` or the relevant unfinished TASK/REQ instead.

For fresh-session validation, create a bundle-local artifact before running an external fresh session:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" fresh-benchmark init --root "$(pwd)" --slug <slug>
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" fresh-benchmark status --root "$(pwd)" --slug <slug>
```

`fresh-benchmark init` creates evidence scaffolding only. It is not proof that a fresh agent, multi-agent run, or new session actually followed the rules. Claim live fresh-session evidence only after raw outputs and scores are recorded in the artifact.

`fresh-benchmark status` is the machine-readable lifecycle check for that artifact. Treat `state: missing` as no scaffold, `state: scaffolded` as template created but no live evidence, and `state: completed` as raw outputs, scores, and `External run status: completed` recorded. Use `next_required_action` to decide what remains; booleans such as `external_run_required` and `live_evidence_created` are compatibility fields, not the full lifecycle explanation.

---

## Execution Visibility

When this skill is active, every user-visible assistant message MUST start with an idea-to-code role/source prefix. Direct idea-to-code use uses `[idea-to-code][Role/source]`, such as `[idea-to-code][Planner/agent]`. When another skill explicitly uses idea-to-code as its lifecycle foundation, it may declare a profile and use `[idea-to-code/<profile-name>][Role/source]`. The profile name is caller-provided and display-only; any valid profile label is shown in the user-visible prefix but does not change lifecycle gates, state files, ledger semantics, permissions, or closeout rules. Do not infer trust, ownership, permissions, or scope from a profile name; it is only a user-visible label. This includes commentary updates, plans, status answers, blocker reports, verification summaries, final responses, and follow-up explanations. Do not drop the marker just because the work is editing the skill itself.

`Role` must be the active lifecycle role: `Planner`, `Implementer`, `Validator`, `Reviewer`, or `Closer`. `source` must be `agent` when the current assistant is performing the role and `subagent` only when a real delegated subagent actually ran that role and returned usable evidence. Do not display `/subagent` as a plan or aspiration.

## User-Facing Language Contract

Meaningful user-facing prose follows the user's language by default. If the latest user request is primarily Chinese, answer the explanatory parts, recommendations, caveats, and conclusion in Chinese. If the user asks in English, answer those parts in English. If the user explicitly requests a different language, follow that request for user-facing prose.

Protocol tokens and state remain stable English/ASCII unless the command itself intentionally prints localized content. Keep these in English: fixed field names, role/source prefixes, TASK/REQ/IDEA/MB IDs, CLI commands and arguments, file paths, bundle artifacts, role evidence, validation types, acceptance records, reports, and state JSON. Do not translate identifiers or fixed protocol fields.

### Protocol Glossary / Do-Not-Translate List

This glossary is the canonical maintenance point for protocol terms that must remain English. Add, remove, or rename entries here when the protocol changes, then update the regression test that checks representative entries. Do not scatter new do-not-translate terms only in prose.

Never translate these categories in user-visible output, bundle artifacts, reports, state, role evidence, tests, or command examples:

- Role/source prefixes: `[idea-to-code][Planner/agent]`, `[idea-to-code][Implementer/agent]`, `[idea-to-code][Validator/agent]`, `[idea-to-code][Reviewer/agent]`, `[idea-to-code][Closer/agent]`, `[idea-to-code][Validator/subagent]`.
- Role names: `Planner`, `Implementer`, `Validator`, `Reviewer`, `Closer`.
- Source names: `agent`, `subagent`.
- Status labels: `Completed`, `Progress`, `Blocked`.
- Formal status fields: `Status`, `Changes`, `Completed Items`, `Incomplete Items`, `Validation Results`, `Unverified Items`, `Residual Risks`, `Key Technical Details`.
- Display and gate labels: `Exploration Result`, `Confirmation Required`, `Implementation Gate: READY`, `Display Layer`, `Next Layer`, `READY Focus`, `Full Plan`.
- Scope and trace IDs: `TASK-*`, `REQ-*`, `IDEA-*`, `MB-*`, `IMP-*`.
- Output and guard IDs: `EXPLORATION_OUTPUT_ID`, `READY_TASK_OUTPUT_ID`, `PRE_EDIT_OK_ID`, `LEASE_ID`.
- CLI command names and arguments: `render-status`, `implementation ready`, `implementation enter-task`, `implementation pre-edit`, `implementation lease acquire`, `idea record`, `idea status`, `backlog sync`, `--root`, `--slug`, `--task`, `--file`, `--covers`.
- File, artifact, and state names: `00-idea.md`, `01-progress.md`, `02-report.md`, `state.json`, `bundle`, `ledger`, `current.json`.
- Validation types: `real-product-path`, `mock-only`, `fixture-only`, `source-only`, `dom-only`, `manual-inspection`, `unverified`.
- Evidence and report content that is written to bundle state: role evidence, acceptance records, milestone records, final reports, validation evidence, and command output excerpts.

Meaningful prose around those tokens should still follow the user's language. For example, keep `Changes` and `TASK-1 / REQ-1` in English, but write the explanatory sentence after the colon in the user's language when it is a user-facing response.

For mixed-language responses, use this split:

- user-facing meaning, reasoning, recommendations, status interpretation, and next-step explanation: user's language;
- formal field labels, IDs, command snippets, evidence strings, and bundle/state content: English-only ASCII;
- quoted user text may stay in the original language, but summarize it in English inside bundle state when state commands require ASCII.

Do not use fixed status templates merely to satisfy language consistency. Ordinary explanation-only replies remain natural in the user's language while still keeping the required idea-to-code prefix.

The first line SHOULD name mode, bundle, and gate/state when useful:

```text
[idea-to-code][Planner/agent] Mode: delivery | Bundle: <slug> | Gate: ready
[idea-to-code/<profile-name>][Planner/agent] Mode: delivery | Bundle: <slug> | Gate: ready
[idea-to-code][Validator/subagent] Mode: validation | Bundle: <slug> | State: reviewing evidence
```

If the message is a short answer rather than a lifecycle update, still start with the default or profile-aware idea-to-code role/source prefix.

### Console Response Contract

Use the fixed field contract only for formal tracked delivery status: final closeout, blocked handoff, review handoff, keep/revise/rollback handoff, or when the user explicitly asks for progress, completion, summary, validation, or commit/publish state for work that entered todo/REQ/TASK accounting.

Do not use the fixed field contract for ordinary questions, explanations, naming discussions, quick clarifications, or lightweight working updates, even when a bundle is active. Those replies should stay concise and natural while still starting with a role/source prefix such as `[idea-to-code][Planner/agent]` when this skill is active. The boundary is semantic: if no tracked delivery status, install, validation, commit, blocked handoff, review handoff, keep/revise/rollback decision, or final status is being reported, answer naturally and do not add READY, `render-status`, or fixed fields just because a bundle exists.

Mixed-response split rule: when one user message combines a tracked status check with ordinary review, architecture evaluation, naming, "what is good/missing", or "what should we improve" discussion, do not let the fixed field contract swallow the whole answer. Answer the tracked status part first in one concise status sentence, using TASK/REQ IDs and `No commit made` when relevant. Then answer the review or discussion part naturally in the user's language with short sections such as "Current strengths", "Current gaps", and "Suggested TODO". Do not introduce a second fixed response template and do not run `render-status` merely for the ordinary review portion. Use full `render-status` fields only when the user asks for formal tracked delivery status as the primary request or when making a final tracked handoff.

For formal tracked `Progress`, validation, install, or status responses, every `Changes`, `Completed Items`, `Incomplete Items`, and `Validation Results` bullet must name the relevant `TASK-*` and `REQ-*` IDs when the work entered bundle accounting. Those IDs must map back to the READY TASK list or focused READY excerpt surfaced in a normal assistant message before implementation. Do not report substantial check/install/validation work as tracked Progress unless that work is represented by a READY TASK. If a response cannot map to a TASK/REQ, answer naturally as an ordinary explanation or first update the bundle plan.

Status labels describe the scope of the current user-visible response. Use `Completed` when every TASK/REQ in that response's stated scope is implemented and validated. If `Incomplete Items` is `none` for the stated response scope and validation passed, default to `Status: Completed`; do not downgrade to `Progress` only because the bundle remains open, no commit was made, fresh-session retest remains external, or user acceptance has not been separately collected. For an interim TASK/REQ slice, `Completed` does not claim the whole bundle is finalized, accepted, committed, or published; disclose those facts under `Key Technical Details` or `Unverified Items`. Use `Progress` when at least one in-scope TASK/REQ is still being implemented or validated. Use `Blocked` when in-scope work cannot continue without an external dependency or decision.

`Incomplete Items` must contain only unfinished in-scope TASK/REQ work. Do not list `No commit made`, `bundle not finalized`, `awaiting user review`, or fresh-session/user acceptance retest as incomplete unless commit, finalize, review, or retest is itself an explicit in-scope TASK/REQ. Put no-commit and bundle-finalization state in `Key Technical Details`; put fresh-session checks, user acceptance, or other external checks in `Unverified Items`.

Decision table:

| Response situation | Output shape |
|---|---|
| Formal tracked delivery status or final handoff | Use fixed fields. |
| Mixed tracked status plus ordinary review/evaluation | Concise tracked status sentence, then natural review sections; no second fixed template. |
| Ordinary question/explanation/naming discussion | Natural concise answer. |
| In-progress commentary update | Short action-oriented update. |

If ambiguous, use fixed fields only when the user needs formal delivery status.

For formal tracked delivery status, run the read-only render helper before writing the response whenever the helper is available. If `render-status` is unavailable or fails, state that reason in the response and then use the same fixed field contract manually. Do not skip the helper because the answer seems short.

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" render-status \
  --root "$(pwd)" --slug <slug> --status Completed|Progress|Blocked
```

The helper prints the fixed field skeleton with the idea-to-code role/source prefix, TASK/REQ mapping placeholders, `EXPLORATION_OUTPUT_ID`, `READY_TASK_OUTPUT_ID`, and `No commit made` under Key Technical Details by default. When milestone, IDEA ledger, backlog, session, scope, delegation, or noncompliance evidence exists, the helper should surface that evidence directly and keep placeholders only where evidence is genuinely missing. Formal tracked status MUST use render-status generated fields when the helper is available: edit the skeleton with actual evidence before sending it; do not remove fixed fields, rename them, reorder them, or hand-invent them; do not drop TASK/REQ mapping from `Changes`, `Completed Items`, `Incomplete Items`, or `Validation Results`; do not drop IDEA/TASK/REQ mapping when multiple ideas exist in the session ledger; and do not move no-commit state into `Incomplete Items`. Do not use it for ordinary untracked answers.

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
- none | <remaining risk>

Key Technical Details:
- <paths, behavior contracts, generated tests, migration notes, or important implementation facts>
```

Do not use `Completed` to claim final accepted closeout for the whole bundle until pre-close verify, Closer evidence, finalize, and final verify have passed. If any TASK/REQ in the response scope is incomplete, failed, unverified, or blocked, label the response `Progress` or `Blocked` and do not claim that response scope is complete. For small tasks, keep bullets short, but do not omit field names.

When tracked local work is intentionally left uncommitted, say that explicitly in `Key Technical Details` using direct wording such as `No commit made`, unless commit was an explicit in-scope TASK/REQ and is therefore genuinely unfinished. Do this even when implementation and validation have passed, so the user can distinguish verified local work from committed/published work.

Default to autonomous delivery unless the user explicitly asks for planning-only, status, pause, review, or analysis.

---

## Completion Standard

Do not claim done until:

- implementation exists
- intake gate is resolved with `Need Confirmation: no`
- open REQs are covered
- acceptance matrix is concrete
- user-intent acceptance evidence shows the result matches the restated user goal and observable outcome
- role evidence is current and ordered
- validation evidence names validation types
- known gaps and risks are explicit
- pre-close verify, finalize, and final verify have passed

Use `partial`, `accepted-with-followup`, `fail`, or `not-accepted` when evidence does not support full acceptance.

---

## Reference

Read only the reference needed for the current situation:

- `references/workflow.md` - bundle contract, lifecycle commands, routing, preflight, pause/resume/archive, checkpoint, verify, finalize.
- `references/roles-and-state.md` - role duties, task states, task classification, acceptance matrix, trace coverage, evidence quality, and multi-role output compliance.
- `references/verification-and-evidence.md` - validation types, verification summaries, UI/runtime evidence, acceptance and closeout checks.
- `references/planning-patterns.md` - vague idea clarification, milestone decomposition, implementation plan shape, final report shape.
- `references/controlled-exploration-benchmark.md` - prompt-level scenario library plus fresh-session live benchmark protocol and rubric for evaluating real model outputs after Controlled Exploration changes.
- `references/fresh-session-live-benchmark-template.md` - copyable result template for recording raw new-session outputs and scores.
