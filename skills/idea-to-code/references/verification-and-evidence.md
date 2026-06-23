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

Brainstorming hypotheses is allowed and useful. The rule is separation: do not present a hypothesis as a conclusion, do not use it as accepted evidence, and do not hide unresolved hypotheses. If a hypothesis matters to acceptance, verify it first. If it remains unverified, record it under `Unverified Items`, `Residual Risks`, or next experiment plan.

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
- If the result is only partially aligned, why is it `Progress`, `Blocked`, `partial`, `accepted-with-followup`, `fail`, or `not-accepted`?

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

The final user-visible console/chat response is a closeout artifact. For tracked work, it must start with `[idea-to-code]` and use these field names:

- `Status`
- `Changes`
- `Completed Items`
- `Incomplete Items`
- `Validation Results`
- `Unverified Items`
- `Residual Risks`
- `Key Technical Details`

Allowed status labels are `Completed`, `Progress`, and `Blocked`. Use `Completed` only when accepted closeout is supported by current role evidence, pre-close verify, finalize, and final verify. If there are no incomplete items, unverified items, or residual risks, write `none` under those fields instead of omitting them.

## Confirmation Handoff Check

When `Need Confirmation: yes`, the user-visible response is also a gate artifact. It must not look like a normal progress update. Check that it includes:

- `[idea-to-code] Confirmation Required`
- why implementation is paused
- the proposed scope after approval
- exact accepted replies such as `yes`, `approved`, `change: <correction>`, `pause`, and `cancel`
- what happens next after approval

If the user cannot tell how to answer from the message itself, the confirmation request is incomplete.
