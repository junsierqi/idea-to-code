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

## Evidence Capture

For UI or runtime-visible work:

- Capture screenshots, logs, command output, or saved artifacts when they materially support acceptance.
- Name the product path exercised.
- Mention viewport, route, account/data fixture, or environment when relevant.
- Do not substitute DOM/source checks for available product-path behavior.

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

## Console Handoff Check

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
