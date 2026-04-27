# Task Acceptance Template

## Purpose

Use this template when closing a feature or milestone that needs an explicit acceptance view.

## Acceptance Summary

- Requested outcome:
- Delivered scope:
- Verified evidence:
- Remaining risks:
- Deferred work:

## Acceptance Checklist

- The requested behavior exists in code
- The main flow was verified (command + result printed)
- Important supporting paths were checked where feasible
- Impacted docs were updated if needed
- The result is observable in output, logs, UI, or screenshots
- Remaining gaps are clearly separated from completed work
- `python ".../manage_delivery_bundle.py" verify --root ... --slug ...` exits 0

## Decision (aligns with `finalize --decision` argument)

- `accepted` — all gates pass, nothing blocking acceptance; bundle moves to `completed`.
- `accepted-with-followup` — main flow passes, known follow-up work is recorded in `--deferred`; bundle moves to `closed`.
- `not-accepted` — main flow did not verify or scope not delivered; bundle moves to `closed` so history is preserved. Do NOT claim completion.

## Gate Status (aligns with `finalize --gate-status`)

- `pass` — the verification block for every recorded milestone printed PASS, and the final end-to-end run succeeded.
- `partial` — at least one flow is unverified or the final end-to-end run covers only the happy path; name the uncovered flow in the report's Verification section.
- `fail` — validation regressed or the last run failed; finalize is only appropriate when the user explicitly wants to snapshot the attempt and stop.

## Rule

Never finalize `--gate-status pass --decision accepted` on work that only has partial evidence. The bundle is the audit trail — false PASS entries are worse than no bundle.
