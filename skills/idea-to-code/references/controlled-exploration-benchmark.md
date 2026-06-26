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

Run shape:

1. Open a new Codex session after installing the skill.
2. Use the exact installed skill; do not paste corrected guidance into the chat.
3. Run the default prompt set exactly: three from the Scenario Library, one Response Mode scenario, and one clear small task.
4. Capture raw assistant output before editing or correcting it.
5. Capture generated bundle snippets when available: Intake Gate, Controlled Exploration, READY TASK excerpt, and final status response.
6. Score each output with both rubrics below.
7. Record failures as instruction drift, not as user error.
8. Revise the skill only when a repeated failure appears across sessions or when one failure is severe enough to break the workflow.

Time and cost bounds:

- Default run uses exactly five prompts unless the user explicitly asks for a larger sample.
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

Fresh-session score dimensions:

| Dimension | Passing behavior |
|---|---|
| Controlled Exploration fit | Uses `Exploration Needed: yes` only for real forks and `no` for clear single-path tasks. |
| User-goal critique | Identifies the real goal and challenges flawed requested implementations when needed. |
| Recommended decision | Gives one default path, not unresolved option dumping. |
| READY visibility | Surfaces the relevant READY TASK list or focused excerpt in a normal assistant message before edits. |
| Response mode | Uses fixed fields only for formal tracked delivery status and natural concise replies for ordinary questions. |
| Status semantics | Uses `Status: Completed` for fully validated response-scoped TASK/REQ slices with `Incomplete Items: none`; keeps `Incomplete Items` limited to unfinished in-scope TASK/REQ work, puts `No commit made` in Key Technical Details by default, and puts external retest/user acceptance in Unverified Items. |
| Small-task friction | Clear small tasks avoid unnecessary exploration, extra confirmation, and heavy process. |

Fresh-session score: `0-7` per output. Report both the total and the failure categories. A total can hide small-task friction, so always call out any friction failure separately.

Fresh-session decision thresholds:

- `>= 32/35` with no small-task friction failures: strong enough to keep for review.
- `25-31/35` or one small-task friction failure: revise the failing guidance before commit.
- `< 25/35` or repeated READY/response-mode failures: do not keep without another implementation pass.

Fresh-session evidence must include the raw output location or transcript id. Summaries alone are not enough because the failure may be in wording, ordering, or omitted fields.

## Scoring Rubric

Score each dimension as `1` for present and concrete, `0` for absent, vague, or contradicted by the output.

| Dimension | Passing behavior |
|---|---|
| Real goal | Identifies the user's underlying outcome, not only the proposed implementation. |
| Flawed proposal | Challenges risky, destructive, overcomplicated, or misaligned requested implementations. |
| Better default | Recommends one concrete default path instead of dumping unresolved choices. |
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
Total: <n>/6
Decision: strong | partial | weak
Instruction gap, if any: <what to revise>
```

## Fresh-Session Reporting Format

Use this format for real new-session benchmark results. A copyable template is available at `fresh-session-live-benchmark-template.md`.

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

Result:
- Total score: <n>/35
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
- Recommended decision: 0|1 - <evidence>
- READY visibility: 0|1 - <evidence>
- Response mode: 0|1 - <evidence>
- Status semantics: 0|1 - <evidence>
- Small-task friction: 0|1 - <evidence>
Instruction drift:
- none | <what the agent did that contradicted current policy>
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
