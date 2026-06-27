# Verification And Evidence

## Purpose

Use this reference when validating behavior, recording evidence, collecting screenshots or runtime artifacts, reviewing acceptance, or closing a task.

## Validation Types

Every validation claim must name one:

- `real-product-path`: same user-observable or product entry point affected by the task.
- `mock-only`: mocked service or dependency.
- `fixture-only`: fixture or sample data path.
- `source-only`: code, docs, type, or static inspection.
- `dom-only`: DOM/render structure without full product behavior.
- `manual-inspection`: human inspection path with concrete file, screen, or artifact.
- `unverified`: not validated; must name the missing dependency or deferral.

Use `real-product-path` for real product behavior when locally available. Lower-level evidence can support it but should not be claimed as equivalent.

## Verification Summary

Before checkpointing or finalizing, summarize:

```text
=== VERIFICATION SUMMARY: <milestone> ===
Implementation Items:
- IMP-1 PASS|PARTIAL|FAIL - <evidence or missing piece>
- IMP-2 PASS|PARTIAL|FAIL - <evidence or missing piece>
[ ] Code change lands in: <file(s)>
[ ] Build/compile: <command + result>
[ ] Tests/runtime check: <command + result>
[ ] Behavior observed: <log / output / screenshot reference>
Result: PASS | PARTIAL | FAIL
===
```

Rollup:

- `PASS`: all critical items pass with evidence.
- `PARTIAL`: non-critical or explicitly deferred gaps remain.
- `FAIL`: critical item failed, is missing, or lacks required validation.

## Fact / Hypothesis / Decision / Verification

Use these categories when diagnosing failures, explaining causes, choosing experiments, or closing a task:

- `Fact`: observed evidence only.
- `Hypothesis`: a possible explanation, candidate cause, or proposed approach that is not yet proven.
- `Decision`: the next action chosen from facts or explicitly marked hypotheses.
- `Verification`: evidence that proves, disproves, or narrows a hypothesis or acceptance claim.

Controlled Exploration may use brainstorming hypotheses when the plan has real uncertainty. The rule is separation: do not present a hypothesis as a conclusion, do not use it as accepted evidence, and do not hide unresolved hypotheses. If a hypothesis matters to acceptance, verify it first. If it remains unverified, record it under `Unverified Items`, `Residual Risks`, or next experiment plan.

## Evidence Capture

For UI or runtime-visible work:

- Capture screenshots, logs, command output, or saved artifacts when they materially support acceptance.
- Name the product path exercised.
- Mention viewport, route, account/data fixture, or environment when relevant.
- Do not substitute DOM/source checks for available product-path behavior.

For automated tests, confirm the command actually ran at least one relevant test. A command that exits successfully with `Ran 0 tests`, `0 passed`, no collected tests, or an empty filtered selection is not validation evidence; treat it as `unverified` or fix the command/test runner before claiming coverage.

## Generated Test Evidence

When idea-to-code generates tests or validation scripts, evidence must identify ownership:

- `persistent-product-test`: kept in the project test suite.
- `project-native-test`: kept in the project test suite using the project's native framework or layout.
- `task-evidence-only`: kept under `.idea-to-code/<slug>/artifacts/` and not treated as a permanent product test.

Each evidence entry must include `Test Ownership`, `Test file`, covered REQ IDs, and `Validation Type`. Persistent or project-native generated tests must include `idea_to_code` or the task slug in the path/name unless the project already has a clearer local convention. Task-evidence-only files must stay under `.idea-to-code/<slug>/artifacts/`.

## Acceptance Check

Before accepted closeout, confirm:

- implementation exists in the repository
- intake gate is resolved with `Need Confirmation: no`
- Controlled Exploration is either skipped with a concrete Trigger or resolved with options and one decision
- the chosen decision fits the user's real goal and does not blindly follow a flawed requested implementation
- the plan recommends one default path instead of dumping unresolved options on the user
- when Controlled Exploration selected an option, validation and review checked whether the decision reason and verification path held up
- recommendation quality is evidenced by user-goal fit, risk/cost reduction, constraint and non-goal preservation, and verifiability
- small-task friction remains a hard guardrail: clear single-path tasks do not gain unnecessary exploration, option dumping, or routine confirmation
- the workflow used no extra confirmation layer beyond the existing Intake Gate confirmation
- acceptance matrix is concrete
- Role Execution Mode is recorded as `same-agent`, `hybrid-team`, or `independent-team`
- same-agent fallback or independent Validator/Reviewer evidence is explained
- the final behavior matches the restated user goal and observable user outcome
- acceptance examples pass and counterexamples of wrong-but-working behavior are not accepted
- non-goal boundaries and user-requested exclusions are respected
- all open REQs are covered
- role evidence is current for the current `plan_revision`
- validation types are named
- generated tests or evidence scripts have ownership, path, covered REQs, and validation type recorded
- real product-path evidence exists when locally available
- risks and deferred work are explicit
- pre-close `verify` passed after Reviewer evidence
- Closer evidence was recorded after pre-close verify
- final `verify` passed after finalize

Use `accepted-with-followup` or `not-accepted` when the evidence does not support full acceptance.

## User-Intent Acceptance Check

Treat user-intent fit as first-class evidence. Before `accepted` closeout, the final report and console response should answer:

- What did the user ask for in implementation terms?
- What observable outcome now proves that request is satisfied?
- Which acceptance examples were exercised?
- Which counterexamples or wrong-result cases were rejected?
- Which non-goals or exclusions were preserved?
- If Controlled Exploration selected a path, what evidence showed the recommendation quality was better than the rejected options?
- Did validation cover the chosen option's decision reason and verification path?
- If the result is only partially aligned, why is it `Progress`, `Blocked`, `partial`, `accepted-with-followup`, `fail`, or `not-accepted`?
- If the user proposed an implementation, did the final decision follow it for good reasons or replace it with a better recommendation?
- Did the agent ask for confirmation only where a true product, security, data, cost, or architecture fork existed?

If a result is technically working but solves a different problem than the user asked for, it is not accepted.

## Role Independence Check

Before accepted closeout, disclose the role execution mode:

- `same-agent`: explain why subagents were unavailable, unnecessary, or riskier than sequential same-agent gates; Reviewer evidence must say `same-agent review`.
- `hybrid-team`: name the independent Validator or Reviewer role and summarize that subagent's evidence.
- `independent-team`: name the independent role/slice ownership and summarize each independent result.

Independent review is stronger because it reduces implementation-confirmation bias, but it must be real. Do not claim an independent agent ran unless the tool call or returned result exists.

For subagent evidence, include the delegation health check or recent successful subagent result, the delegated scope, the agent id/name when available, and whether the result returned before timeout. A timed-out or closed-without-result subagent is a risk record, not validation or review evidence.

Do not turn fallback into root-cause proof. If a broad delegation times out but a ping or scoped review succeeds, the only proven facts are those outcomes. The broad timeout cause remains `unverified` until comparison tests isolate it. Record unknown causes explicitly instead of saying the issue was prompt size, queue latency, tool health, or model behavior without evidence.

## Console Response Check

## READY Visibility Check

Before product-file edits, the READY task list must be visible to the user in a normal assistant message, not only command stdout, tool output, or a folded transcript.

READY visibility has two layers:

- `Plan-level READY`: the complete TASK list remains in `00-idea.md` and full READY output for traceability.
- `Execution-level READY`: the current TASK excerpt is shown immediately before that TASK is executed.

For multi-task work, default user-visible execution display to the current TASK's focused READY excerpt, not the full long TASK list. Before moving from one TASK to the next, show the next TASK's focused READY excerpt unless the user explicitly asks to skip repeated visibility.

Use the READY task filter when a long bundle would hide the current work:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation show-ready --root "$(pwd)" --slug <slug> --task TASK-17
```

Focused READY output is for user visibility only. It does not change bundle scope, requirements, gate state, or role evidence expectations.

The generated READY output has a hard excerpt contract. Every visible TASK/IMP block must include:

- the `TASK-*` or `IMP-*` line
- covered `REQ-*` or the script's covered REQ hint when inferable
- `Files`
- `Done Criteria`
- `Planned Verification`

If generated READY output omits any of these fields, it is invalid. Regenerate or fix the parser/formatter before product-file edits; do not treat a folded transcript, partial copy, or field-only snippet as sufficient READY visibility.

The final formal `Progress` or `Completed` response must map `Changes`, `Completed Items`, `Incomplete Items`, and `Validation Results` back to the same visible TASK/REQ set for single-idea sessions, and to the same visible IDEA/TASK/REQ set when a session ledger contains multiple ideas. For single-idea sessions, TASK/REQ mapping is enough when the idea scope is unambiguous.

For multi-task or multi-idea work, "same visible IDEA/TASK/REQ set" means each result bullet maps to the focused execution-level READY excerpt shown before that TASK and to the relevant IDEA scope when more than one idea exists in the session. The final summary may aggregate TASKs, but it must not introduce unshown or unmapped work.

The final user-visible console/chat response is a closeout artifact. Use the fixed field contract only for formal tracked delivery status: final closeout, blocked handoff, review handoff, keep/revise/rollback handoff, or when the user explicitly asks for progress, completion, summary, validation, or commit/publish state for work that entered todo/REQ/TASK accounting. For tracked delivery-status work, it must start with an idea-to-code role/source prefix such as `[idea-to-code][Closer/agent]` and use these field names:

- `Status`
- `Changes`
- `Completed Items`
- `Incomplete Items`
- `Validation Results`
- `Unverified Items`
- `Residual Risks`
- `Key Technical Details`

Before sending formal tracked delivery status, run the read-only `render-status` helper whenever it is available:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" render-status --root "$(pwd)" --slug <slug> --status Completed|Progress|Blocked
```

The helper does not finalize, verify, or mutate the bundle. It emits a fixed-field skeleton with TASK/REQ placeholders, `READY_TASK_OUTPUT_ID`, and default no-commit placement under `Key Technical Details`. Formal tracked status MUST use render-status generated fields when the helper is available: replace placeholders with actual evidence before sending, but do not omit, rename, reorder, or hand-invent the fixed field set. If `render-status` is unavailable or fails, state that reason and manually use the same fixed fields. Do not omit fields, do not drop TASK/REQ mapping from `Changes`, `Completed Items`, `Incomplete Items`, or `Validation Results`, do not drop IDEA/TASK/REQ mapping when multiple ideas exist in the session ledger, and do not move no-commit state into `Incomplete Items`. Do not use it for ordinary untracked answers.

Allowed status labels are `Completed`, `Progress`, and `Blocked`. Status labels describe the scope of the current user-visible response. In session-ledger mode, state or imply the active scope, such as `Scope: IDEA-2 / TASK-4 / REQ-7`, whenever multiple ideas exist. Use `Completed` when every IDEA/TASK/REQ in that response's stated scope is implemented and validated. If `Incomplete Items` is `none` for the stated response scope and validation passed, default to `Status: Completed`; do not downgrade to `Progress` only because the session ledger remains open, no commit was made, fresh-session retest remains external, or user acceptance has not been separately collected. For an interim IDEA/TASK/REQ slice, `Completed` does not claim the whole session ledger is finalized, accepted, committed, or published; disclose those facts under `Key Technical Details` or `Unverified Items`. Use `Progress` when at least one in-scope IDEA/TASK/REQ is still being implemented or validated. Use `Blocked` when in-scope work cannot continue without an external dependency or decision. If there are no incomplete items, unverified items, or residual risks, write `none` under those fields instead of omitting them.

Do not use `Completed` to claim final accepted closeout for the whole bundle until accepted closeout is supported by current role evidence, pre-close verify, finalize, and final verify.

For formal tracked `Progress`, validation, install, or status responses, require TASK/REQ mapping in the user-visible bullets:

- `Changes`: name the relevant `TASK-*` and `REQ-*`.
- `Completed Items`: name the completed `TASK-*` and covered `REQ-*`.
- `Incomplete Items`: name only unfinished in-scope `TASK-*` or `REQ-*`, or write `none`.
- `Validation Results`: name the checked `TASK-*`/`REQ-*`, validation type, command/evidence, and result.

When the session ledger contains multiple ideas, the same bullets must also name or clearly imply the relevant `IDEA-*` scope. A formal tracked response that cannot map each result bullet to TASK/REQ, or to IDEA/TASK/REQ for multi-idea session ledgers, is noncompliant and must be regenerated from `render-status` or corrected before sending.

Do not report substantial check/install/validation work as tracked Progress unless that work was represented by a READY TASK before the report. If the user asks an ordinary explanation question, do not invent TASK accounting just to use the fixed template.

Do not list `No commit made`, `bundle not finalized`, `awaiting user review`, or fresh-session/user acceptance retest as `Incomplete Items` unless commit, finalize, review, or retest is itself an explicit in-scope TASK/REQ. Put no-commit and bundle-finalization state in `Key Technical Details`; put fresh-session checks, user acceptance, or other external checks in `Unverified Items`.

If tracked local changes have not been committed, explicitly state `No commit made` in `Key Technical Details` unless commit was an explicit in-scope TASK/REQ and is therefore genuinely unfinished. Do not leave commit/publish state implicit.

Do not use the fixed field contract for ordinary questions, short explanations, naming discussions, quick clarifications, or lightweight commentary updates, even when a bundle is active. These replies should stay concise and natural while still using the role/source prefix; the template is for formal tracked delivery status, not every message.

### Response Mode Check

Before a user-facing response at the end of a turn, choose the output shape:

| Response situation | Output shape |
|---|---|
| Formal tracked delivery status or final handoff | Fixed fields. |
| Ordinary question/explanation/naming discussion | Natural concise answer. |
| In-progress commentary update | Short action-oriented update. |

If uncertain, use fixed fields only when the user needs formal tracked delivery status. Otherwise answer naturally and concisely.

## Confirmation Handoff Check

When `Need Confirmation: yes`, the user-visible response is also a gate artifact. It must not look like a normal progress update. Check that it includes:

- `[idea-to-code][Planner/agent] Confirmation Required`
- why implementation is paused
- the proposed scope after approval
- exact accepted replies such as `yes`, `approved`, `change: <correction>`, `pause`, and `cancel`
- what happens next after approval

If the user cannot tell how to answer from the message itself, the confirmation request is incomplete.
