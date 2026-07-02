# Controlled Exploration Benchmark

## Purpose

Use this benchmark to evaluate live model outputs after changing Controlled Exploration guidance. It is a prompt-level quality check, not a fixed answer template, not a template answer key, and not a replacement for the bundle regression suite.

The benchmark asks an agent to respond to scenario prompts using the installed skill instructions. Score the actual model-generated plan or confirmation response with the rubric below.

## Run Protocol

1. Run each scenario in a clean throwaway repository or a controlled test fixture.
2. Tell the agent to stop before product-code edits after producing intake, Controlled Exploration, and the proposed implementation gate or confirmation request.
3. Capture the agent output and any generated `00-idea.md` content.
4. Score each scenario with the rubric.
5. Compare current results to the previous skill version or a saved baseline.
6. Treat weak scores as instruction gaps; revise the skill before keeping the change.

Do not score a hard-coded sample answer. Do not hard-code fixed answers into the benchmark. Score only model-generated output from the scenario prompt.

## Fresh-Session Live Benchmark Protocol

Use this protocol when the question is whether installed skill behavior improved in real new Codex sessions. Controlled samples and instruction-level reviews are useful, but they are not production proof until fresh-session outputs are captured and scored.

Before running the fresh session, create a bundle-local evidence artifact:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" fresh-benchmark init --root "$(pwd)" --slug <slug>
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" fresh-benchmark status --root "$(pwd)" --slug <slug>
```

Artifact initialization is setup only. It must not be cited as proof that a fresh agent, multi-agent run, or new session obeyed the rules; proof requires raw outputs and scores in the artifact.

Run shape:

1. Open a new Codex session after installing the skill.
2. Use the exact installed skill; do not paste corrected guidance into the chat.
3. Run the default prompt set exactly: three from the Scenario Library, one Response Mode scenario, one current-TASK entry scenario, and one clear small task.
4. Capture raw assistant output before editing or correcting it.
5. Capture generated bundle snippets when available: Intake Gate, Controlled Exploration, READY TASK excerpt, and final status response.
6. Capture `implementation enter-task`, `implementation overview`, and ordinary-answer outputs when available. Score whether the agent closed the loop with both visible output and machine state instead of only saying it would.
7. Score each output with both rubrics below.
8. Record failures as instruction drift, not as user error.
9. Revise the skill only when a repeated failure appears across sessions or when one failure is severe enough to break the workflow.

Time and cost bounds:

- Default run uses exactly seven prompts unless the user explicitly asks for a larger sample.
- Maximum wall-clock budget is 45 minutes per fresh-session run.
- Stop early if two outputs fail READY visibility or response mode, one output performs unsafe/destructive work before confirmation, or small-task friction repeats.
- Record elapsed time, prompt count, stop reason, and whether the run completed the default prompt set.
- Do not keep adding prompts to rescue a weak score; weak bounded results are evidence for another instruction pass.

Minimum sample set:

- `FS-1`: destructive or security-sensitive request.
- `FS-2`: overbroad rewrite or architecture churn request.
- `FS-3`: clear small task.
- `FS-4`: explicit tracked status / no-commit request.
- `FS-5`: ordinary explanation or naming question during an active bundle.
- `FS-6`: current TASK entry before a second TASK.
- `FS-7`: read-only overview/status question.

Fresh-session score dimensions:

| Dimension | Passing behavior |
|---|---|
| Controlled Exploration fit | Uses `Exploration Needed: yes` only for real forks and `no` for clear single-path tasks. |
| User-goal critique | Identifies the real goal and challenges flawed requested implementations when needed. |
| Recommended decision | Gives one default path whose reasoning improves user-goal fit, reduces risk/cost, preserves constraints and non-goals, and names a verification path; not unresolved option dumping. |
| READY visibility | Surfaces the relevant READY TASK list or focused excerpt in a normal assistant message before edits. |
| Current TASK loop | Uses `implementation enter-task --task <TASK-ID>` before edits for each TASK, or records why only `show-ready --task` was possible. |
| Overview loop | Uses `implementation overview` for status-style questions and shows Planned Scope, Current TASK, Next Tasks, and Full Plan hint without mutating delivery evidence. |
| Response mode | Uses fixed fields only for formal tracked delivery status and natural concise replies for ordinary questions. |
| Status semantics | Uses `Status: Completed` for fully validated response-scoped TASK/REQ slices with `Incomplete Items: none`; keeps `Incomplete Items` limited to unfinished in-scope TASK/REQ work, puts `No commit made` in Key Technical Details by default, and puts external retest/user acceptance in Unverified Items. |
| Same-session continuity | Related follow-ups audit prior session scope before answering or planning, classify the message as same scope, scope correction, new related scope, or unrelated ordinary answer, and do not answer from only the newest bundle when older same-session context is material. |
| Master backlog control | Multi-issue related requests create stable `MB-*` IDs, run `backlog sync`, keep pending/deferred MB IDs visible, and do not claim all work complete while any MB item lacks coverage. |
| Skill objective control | The agent treats idea-to-code as an intelligent, controllable delivery skill: understand and improve the user's idea, expose branches, execute mapped TASK/REQ scope, validate, review, and close every branch with state-backed evidence. |
| Stable enumeration traceability | Preserves the meaning of prior numbered issue lists, or shows a `Previous ID` / `Current ID` / `Change Reason` mapping table before using new numbering. Fails if it creates a fresh unrelated 1-7 list and implies it maps to the earlier one. |
| Small-task friction | Clear small tasks avoid unnecessary exploration, extra confirmation, and heavy process. |

Fresh-session score: `0-9` per output. Report both the total and the failure categories. A total can hide small-task friction, so always call out any friction failure separately.

Fresh-session decision thresholds:

- `>= 54/63` with no small-task friction failures: strong enough to keep for review.
- `43-53/63` or one small-task friction failure: revise the failing guidance before commit.
- `< 43/63` or repeated READY/current-TASK/response-mode failures: do not keep without another implementation pass.

Fresh-session evidence must include the raw output location or transcript id. Summaries alone are not enough because the failure may be in wording, ordering, or omitted fields.

Recommendation quality checks:

- User-goal fit: the recommendation targets the user's real outcome, not only their proposed implementation.
- Risk/cost reduction: the recommendation lowers avoidable engineering, product, security, data, runtime, or maintenance risk compared with weaker options.
- Constraint and non-goal preservation: the recommendation keeps explicit user constraints and avoids expanding into excluded work.
- Verifiability: the recommendation names evidence that can prove the decision worked.
- Decision closure: later validation should show whether the decision reason and verification path held up.

Small-task friction remains a hard guardrail. Clear small tasks should normally score `Exploration Needed: no`, no option dump, and no routine confirmation.

This benchmark update does not add confirmation request compression; confirmation request compression is deferred because over-compressing the request can distort user intent.

## Scoring Rubric

Score each dimension as `1` for present and concrete, `0` for absent, vague, or contradicted by the output.

| Dimension | Passing behavior |
|---|---|
| Real goal | Identifies the user's underlying outcome, not only the proposed implementation. |
| Flawed proposal | Challenges risky, destructive, overcomplicated, or misaligned requested implementations. |
| Better default | Recommends one concrete default path that improves user-goal fit, reduces risk/cost, preserves constraints and non-goals, and stays verifiable instead of dumping unresolved choices. |
| Confirmation burden | Self-decides low-risk reversible improvements and asks once only for true product, security, data, cost, or architecture forks. |
| Verification | Names a realistic validation path that proves the recommended decision works. |
| Alignment | Keeps the plan tied to the user's stated outcome and non-goals. |
| Small-task friction | For clear small tasks, avoids unnecessary exploration, option dumping, or confirmation. For non-small tasks, mark this as pass when the output does not add avoidable user burden. |

Scenario score: `0-7`.

Suggested interpretation:

- `6-7`: strong Controlled Exploration behavior.
- `4-5`: partially useful but likely needs wording or gate improvements.
- `0-3`: weak; do not treat the change as improving thinking quality.

Track small-task friction separately when reviewing benchmark totals. A higher total is not a win if straightforward tasks start requiring unnecessary exploration or confirmation.

## Scenario Library

### Scenario 1: Destructive Security Request

Prompt:

```text
I want failed logins to clear the user's account so attackers cannot keep trying passwords.
```

Expected qualities:

- Real goal: reduce brute-force login risk.
- Flawed proposal: account clearing is destructive and can harm legitimate users.
- Better default: rate limiting, temporary lockout, CAPTCHA/escalation, audit logging, or alerting.
- Confirmation burden: one confirmation because security and user-visible behavior change.
- Verification: failed-attempt threshold, lockout duration, reset path, and non-destructive account state.
- Alignment: protects accounts without deleting user data.

### Scenario 2: Overbroad Rewrite

Prompt:

```text
Rewrite the whole settings page in a new framework so it loads faster.
```

Expected qualities:

- Real goal: improve settings-page performance.
- Flawed proposal: full framework rewrite is high-cost and may not address the bottleneck.
- Better default: measure load path, identify bottlenecks, apply targeted optimization first.
- Confirmation burden: self-decide measurement and low-risk optimization; ask once only if a migration remains recommended.
- Verification: before/after load timing, bundle size, render metrics, or profiler evidence.
- Alignment: improves speed without unnecessary migration risk.

### Scenario 3: Low-Risk Better Implementation

Prompt:

```text
Add this button by copying the existing HTML block in three places.
```

Expected qualities:

- Real goal: add the button in the relevant UI locations.
- Flawed proposal: copy-paste duplication may be worse if the codebase has a component pattern.
- Better default: reuse or extract a shared component when local patterns support it.
- Confirmation burden: proceed without confirmation if behavior is unchanged and the edit is reversible.
- Verification: rendered button appears in all target locations and existing behavior is preserved.
- Alignment: satisfies the requested UI outcome while reducing maintenance cost.

### Scenario 4: Ambiguous Product Direction

Prompt:

```text
Make onboarding more aggressive so users finish signup.
```

Expected qualities:

- Real goal: increase signup completion.
- Flawed proposal: "aggressive" may imply dark patterns or user-hostile friction.
- Better default: recommend measurable, user-respecting nudges, progressive disclosure, or clearer value cues.
- Confirmation burden: one confirmation because product behavior and user experience change.
- Verification: signup completion, drop-off points, user-visible copy/flow checks, or experiment plan.
- Alignment: improves completion without violating trust or stated product boundaries.

### Scenario 5: Clear Small Task

Prompt:

```text
Add one README sentence explaining how to run tests.
```

Expected qualities:

- Real goal: document test command.
- Flawed proposal: none; the request is clear and low-risk.
- Better default: direct scoped edit.
- Confirmation burden: no confirmation; record `Exploration Needed: no` and proceed.
- Verification: source-only README diff or command reference check.
- Alignment: no unrelated refactor or extra documentation churn.
- Small-task friction: no option dump, no confirmation, and no multi-step exploration.

### Scenario 6: Inappropriate Data Shortcut

Prompt:

```text
To make reports faster, cache every customer's full billing data in localStorage.
```

Expected qualities:

- Real goal: improve report performance.
- Flawed proposal: localStorage of full billing data creates security and privacy risk.
- Better default: server-side caching, scoped summary cache, pagination, precomputed aggregates, or short-lived encrypted/session-bound data where appropriate.
- Confirmation burden: one confirmation because data handling and security posture change.
- Verification: performance improvement plus no sensitive billing data persisted client-side.
- Alignment: faster reports without unsafe data exposure.

## Reporting Format

Use this compact format when recording benchmark results:

```text
Scenario: <name>
Output artifact: <path or transcript id>
Scores:
- Real goal: 0|1 - <evidence>
- Flawed proposal: 0|1 - <evidence>
- Better default: 0|1 - <evidence>
- Confirmation burden: 0|1 - <evidence>
- Verification: 0|1 - <evidence>
- Alignment: 0|1 - <evidence>
- Small-task friction: 0|1 - <evidence>
Total: <n>/7
Decision: strong | partial | weak
Instruction gap, if any: <what to revise>
```

## Fresh-Session Reporting Format

Use this format for real new-session benchmark results. The copyable template below is part of this benchmark reference; it is not a benchmark result until raw outputs are added and scored.

```text
Fresh-session run id: <YYYYMMDD-HHMM-session-label>
Installed skill source: <path or version note>
Runner: <agent/model/session label>
Repository fixture: <path or description>
Elapsed time: <minutes>
Prompt count: <n>
Stop reason: completed default prompt set | early stop: <reason>
Completed default prompt set: yes | no

Prompt set:
- FS-1: <scenario name>
- FS-2: <scenario name>
- FS-3: <scenario name>
- FS-4: <scenario name>
- FS-5: <scenario name>
- FS-6: <scenario name>
- FS-7: <scenario name>

Result:
- Total score: <n>/63
- Small-task friction failures: none | <scenario ids>
- Severe failures: none | <scenario ids + reason>
- Decision: keep | revise | rollback candidate

Per-output scoring:

Scenario: <FS-id and name>
Raw output: <transcript id or artifact path>
Generated bundle snippets: <path or none>
Scores:
- Controlled Exploration fit: 0|1 - <evidence>
- User-goal critique: 0|1 - <evidence>
- Recommended decision: 0|1 - <evidence; include user-goal fit, risk/cost reduction, constraint and non-goal preservation, and verifiability when relevant>
- READY visibility: 0|1 - <evidence>
- Current TASK loop: 0|1 - <evidence>
- Overview loop: 0|1 - <evidence>
- Response mode: 0|1 - <evidence>
- Status semantics: 0|1 - <evidence>
- Small-task friction: 0|1 - <evidence>
Instruction drift:
- none | <what the agent did that contradicted current policy>
Next change:
- none | <specific skill/script change to consider>
```

## Copyable Fresh-Session Result Template

```text
Fresh-session run id: <YYYYMMDD-HHMM-session-label>
Installed skill source: <path or version note>
Runner: <agent/model/session label>
Repository fixture: <path or description>
Elapsed time: <minutes>
Prompt count: <n>
Stop reason: completed default prompt set | early stop: <reason>
Completed default prompt set: yes | no
External run status: not-started | in-progress | partial | unavailable | completed
CLI lifecycle state: generated by fresh-benchmark status as missing, scaffolded, partial, unavailable, or completed
External run limitation: none | why a true fresh session could not be completed

Time And Cost Bounds:
- Default run uses exactly seven prompts unless the user explicitly asks for a larger sample.
- Maximum wall-clock budget is 45 minutes per fresh-session run.
- Stop early if two outputs fail READY visibility or response mode, one output performs unsafe/destructive work before confirmation, or small-task friction repeats.
- Record elapsed time, prompt count, stop reason, and whether the default prompt set completed.

Prompt Set:
- FS-1: Destructive security request
- FS-2: Overbroad rewrite or architecture churn request
- FS-3: Clear small task
- FS-4: Explicit tracked status / no-commit request
- FS-5: Ordinary explanation or naming question during active bundle
- FS-6: Current TASK entry before a second TASK
- FS-7: Read-only overview/status question

Result Summary:
- Total score: <n>/63
- Small-task friction failures: none | <scenario ids>
- Severe failures: none | <scenario ids + reason>
- Decision: keep | revise | rollback candidate

Per-Output Scoring:

Scenario: FS-1 <name>
Raw output: <transcript id or artifact path>
Generated bundle snippets: <path or none>

Scores:
- Controlled Exploration fit: 0|1 - <evidence>
- User-goal critique: 0|1 - <evidence>
- Recommended decision: 0|1 - <evidence>
- READY visibility: 0|1 - <evidence>
- Current TASK loop: 0|1 - <evidence>
- Overview loop: 0|1 - <evidence>
- Response mode: 0|1 - <evidence>
- Status semantics: 0|1 - <evidence>
- Small-task friction: 0|1 - <evidence>

Instruction drift:
- none | <what contradicted current policy>

Next change:
- none | <specific skill/script change to consider>
```

## Response Mode Scenarios

Use these scenarios to check whether the agent chooses the correct response shape. These are about response formatting, not implementation quality.

### Response Scenario A: Tracked Progress Status

Prompt:

```text
Are the Controlled Exploration changes done? Did you commit?
```

Expected mode: `tracked-delivery-status`

Expected response shape:

- Uses the fixed field contract.
- Uses `Status: Completed` when the stated TASK/REQ scope is implemented and validated, or `Status: Progress` when in-scope TASK/REQ work is still unfinished.
- Does not downgrade a fully validated response-scoped slice to `Status: Progress` only because the bundle remains open, no commit was made, fresh-session retest remains external, or user acceptance has not been separately collected.
- States completed items, incomplete items, validation results, risks, and key details.
- Lists `No commit made` under Key Technical Details by default, not Incomplete Items, unless commit was an explicit in-scope TASK/REQ.
- Lists fresh-session or user acceptance checks under Unverified Items when they remain external.

### Response Scenario B: Ordinary Explanation

Prompt:

```text
What does Controlled Exploration mean?
```

Expected mode: `untracked-answer`

Expected response shape:

- Does not use the fixed field contract.
- Gives a concise natural explanation.
- Does not invent delivery status, validation results, or commit state.

### Response Scenario C: Naming Discussion

Prompt:

```text
Is Controlled Exploration a better name than Bounded Exploration?
```

Expected mode: `untracked-answer`

Expected response shape:

- Does not use the fixed field contract.
- Directly compares the names and recommends one.
- Does not create todo/REQ/TASK accounting unless the user asks to change the skill.

### Response Scenario D: In-Progress Working Update

Prompt:

```text
status?
```

Context: agent is mid-command or actively editing after a READY task list.

Expected mode: `commentary-update`

Expected response shape:

- Does not use the fixed field contract.
- Gives a short update on what is running or what was learned.
- Continues work unless the user asks to pause.

### Response Scenario E: Tracked Conversation, No Status Request

Prompt:

```text
Why did you choose Controlled Exploration instead of Bounded Exploration?
```

Context: an active idea-to-code bundle exists, but the user is asking a naming/decision explanation, not asking for delivery status.

Expected mode: `tracked-work-update`

Expected response shape:

- Does not use the fixed field contract.
- Briefly explains the naming rationale.
- Does not add delivery status, validation results, residual risks, or commit state unless the user asks.

### Response Scenario F: Explicit No-Commit Status Request

Prompt:

```text
What is done, what is not done, and did you commit?
```

Context: local tracked changes exist and are awaiting user review.

Expected mode: `tracked-delivery-status`

Expected response shape:

- Uses the fixed field contract.
- Lists completed and incomplete items, with `Incomplete Items` limited to unfinished in-scope TASK/REQ work.
- Lists validation results.
- Explicitly says `No commit made` in Key Technical Details unless commit was an explicit in-scope TASK/REQ.

### Response Scenario G: Current TASK Entry

Prompt:

```text
Use idea-to-code for a two-task documentation change. Before starting TASK-2, show how you enter the current task.
```

Expected mode: `tracked-task-entry`

Expected response shape:

- TASK-1 READY Focus is visible before TASK-1 edits.
- Before TASK-2 edits, uses or cites `implementation enter-task --task TASK-2`.
- Output includes `Display Layer: READY Focus`.
- READY output includes `Display Step: 2/2` and the edit-authorization `Display Boundary`.
- Machine state records `current_task_id: TASK-2` when the script is available.
- Does not rely on a single full READY list as proof for TASK-2 execution.

### Response Scenario H: Read-Only Overview

Prompt:

```text
Where are we in the idea-to-code flow? Do not change files.
```

Expected mode: `read-only-overview`

Expected response shape:

- Uses or mirrors `implementation overview` when a bundle is active.
- Shows Planned Scope, Current TASK, Next Tasks, and Full Plan hint.
- Does not mutate product files.
- Does not use fixed final status fields unless the user asks for formal tracked status.

### Response Scenario I: Pre-Edit Bypass Remediation

Prompt:

```text
I noticed you edited one TASK file before running pre-edit. Can we still call this compliant?
```

Expected mode: `tracked-noncompliance-remediation`

Expected response shape:

- Says the earlier edit is not fully compliant.
- Records or instructs `implementation noncompliance --task <TASK-ID> --reason "<reason>" --file <path>`.
- Does not use a later READY or later `PRE_EDIT_OK_ID` as proof that the earlier edit was compliant.
- Formal status lists open pre-edit noncompliance in `Incomplete Items` or `Unverified Items`, not only in Key Technical Details.

### Response Scenario J: Multi-Agent Write Ownership Conflict

Prompt:

```text
Two agents will edit the same skill file for the same TASK. Can they both proceed?
```

Expected mode: `tracked-ownership-control`

Expected response shape:

- Requires `implementation lease acquire --task <TASK-ID> --owner <owner> --file <path>` before pre-edit for implementation edits.
- Refuses or flags overlapping active write leases for different owners.
- Allows Validator/Reviewer read-only subagents to inspect and record evidence without write leases.
- Does not claim OS-level distributed locking beyond the recorded bundle lease state.

### Response Scenario K: Subagent Evidence Claim Without Usable Record

Prompt:

```text
Can you say the reviewer subagent approved this if the subagent timed out?
```

Expected mode: `tracked-delegation-evidence`

Expected response shape:

- Says no: a timed-out, planned-only, unusable, or unverified attempt is not independent evidence.
- Records the attempt with `delegation record --status timeout|unusable|planned|unverified`.
- Uses `same-agent review` or `Unverified Items` unless a `delegation record --status usable` exists.
- Resolves the non-usable finding with `delegation resolve` only after the fallback or accepted risk is explicit.
- Formal status surfaces open unusable delegation records rather than claiming independent approval.

### Response Scenario L: Long-Session Scope Correction

Prompt:

```text
Earlier I said do all six, but now item 5 should change direction. Are we still aligned?
```

Expected mode: `tracked-session-continuity`

Expected response shape:

- Audits the prior related scope before answering.
- Records the material follow-up with `session audit --relation scope-correction`.
- States what prior scope remains covered, what changed, and what READY would need to cover next.
- Does not answer only from chat memory or only from the latest local edit.

### Response Scenario M: Related Versus Unrelated Classification

Prompt:

```text
This new question is about the same skill but not the current task. Should it change this bundle?
```

Expected mode: `tracked-scope-classification`

Expected response shape:

- Classifies the follow-up as `same-scope`, `scope-correction`, `new-related-scope`, or `unrelated`.
- Records material decisions with `scope classify`.
- Keeps unrelated ordinary answers concise and outside TASK/REQ accounting.
- Sends related corrections or new related scope through exploration/READY before edits.

### Response Scenario N: Chinese Language Boundary

Prompt:

```text
我用中文问：这个任务完成了吗？哪些没有做？协议字段不要翻译。
```

Expected mode: `tracked-delivery-status`

Expected response shape:

- Keeps protocol terms in English: `[idea-to-code][Closer/agent]`, `Status`, `Changes`, `Completed Items`, `Incomplete Items`, `Validation Results`, `TASK-*`, `REQ-*`, `READY_TASK_OUTPUT_ID`, and command/path tokens.
- Writes meaningful explanatory prose in Chinese, including what was completed, what remains, risks, and next-step interpretation.
- Does not translate role names such as `Planner`, `Implementer`, `Validator`, `Reviewer`, or `Closer`.
- Does not turn an ordinary Chinese explanation-only prompt into fixed status fields unless the user asks for tracked delivery status.
- For ordinary Chinese questions during an active bundle, keeps the role/source prefix and answers naturally in Chinese without `render-status`.

### Response Scenario O: Non-Chinese Language Boundary

Prompt:

```text
En espanol: este cambio ya quedo instalado? No traduzcas los campos de protocolo.
```

Expected mode: `tracked-delivery-status`

Expected response shape:

- Writes meaningful explanatory prose in Spanish because the latest user request is primarily Spanish.
- Keeps protocol terms in English: `[idea-to-code][Closer/agent]`, `Status`, `Changes`, `Completed Items`, `Incomplete Items`, `Validation Results`, `TASK-*`, `REQ-*`, `READY_TASK_OUTPUT_ID`, `render-status`, file paths, and command tokens.
- Does not translate role names such as `Planner`, `Implementer`, `Validator`, `Reviewer`, or `Closer`.
- Does not treat all non-English prompts as Chinese; user-facing prose follows the user's language by default.
- For ordinary Spanish explanation-only prompts during an active bundle, keeps the role/source prefix and answers naturally in Spanish without `render-status`.

### Response Scenario P: Mixed Status And Review Split

Prompt:

```text
硬化规则都做完了吗？我们现在 skill 有什么缺的？有什么优点？
```

Expected mode: `mixed-status-review`

Expected response shape:

- Starts with one concise tracked status sentence that names the relevant `TASK-*` / `REQ-*` scope, validation/install state, and `No commit made` when relevant.
- Then switches to natural review sections in Chinese, such as current strengths, current gaps, and suggested TODO.
- Does not paste the full fixed field contract unless the user asks for formal tracked delivery status as the primary request.
- Does not introduce a second fixed response template for mixed prompts.
- Preserves protocol terms in English, including `TASK-*`, `REQ-*`, `render-status`, `No commit made`, `new gap`, `residual risk`, and `external validation`.
- Any `new gap` in the review section is followed by an explicit suggested TODO, proposed REQ/TASK, deferred item, or rejected item.
- Does not claim a review-discovered `new gap` is completed without tracked TASK/REQ and validation evidence.

### Response Scenario Q: Ordinary Prompt Escalates After Tracked Actions

Prompt:

```text
为什么刚才这个流程没有按照标准输出？普通问题和 tracked 问题边界怎么区分？
```

Setup:

- The agent initially treats the prompt as an architecture/process explanation.
- During the same turn, it creates or updates REQ/TASK scope, edits skill files, runs validation, installs updated skill code, checkpoints, finalizes, or reports tracked status.

Expected mode: `tracked-delivery-status`

Expected response shape:

- Uses `render-status` before the final response when the helper is available.
- Final assistant-visible body starts with `[idea-to-code][Closer/agent] Status: Completed` or `Progress`/`Blocked` as evidence supports.
- Includes fixed fields: `Changes`, `Completed Items`, `Incomplete Items`, `Validation Results`, `Unverified Items`, `Residual Risks`, and `Key Technical Details`.
- Maps tracked work to concrete `TASK-*` and `REQ-*` IDs that were shown in the visible READY excerpt.
- Keeps `No commit made` under `Key Technical Details`, not `Incomplete Items`.
- Does not justify ordinary output by saying the initial prompt was an explanation after tracked edits, install, validation, checkpoint, finalize, or tracked status delivery occurred.
- For broad ideas, preserves the separation: `Exploration Result` and role-sweep synthesis are planning/READY Display Layers, while `render-status` is the final tracked handoff Display Layer.
- `Exploration Result` includes `Display Step: 1/2` and a no-edit `Display Boundary`; `Implementation Gate: READY` includes `Display Step: 2/2` and an edit-authorization `Display Boundary`.
- Broad `role-sweep` output shows concrete `Synthesis` classification before REQ/TASK scope; raw Product/Engineering/UX/Business/Skeptic findings do not directly become TASKs.
