# Acceptance Checklist

## Purpose

Use this checklist before declaring a substantial task complete.

## Checklist

- Is the requested capability actually implemented?
- Are the changed paths consistent with the current architecture?
- Were affected docs updated where needed?
- Was the strongest available local validation run?
- Were failures, skips, or unverified areas stated explicitly?
- Can the user see the outcome through code, output, or observed behavior?
- Is the next follow-up work clearly separated from what is already done?

## Close-Out Rule

Do not say a task is done if the code exists but has not been validated in any meaningful way.

## If Validation Is Incomplete

Say:

- what was attempted
- what succeeded
- what could not be verified
- what the remaining risk is

When finalizing the bundle in this situation, use `--gate-status partial` (or `fail`) and `--decision accepted-with-followup` (or `not-accepted`). Never write `pass`/`accepted` to paper over partial validation.

## Bundle Sanity Check

Before claiming done, run:

```bash
python ".../manage_delivery_bundle.py" verify \
  --root "$(pwd)" --slug <slug>
```

This exits non-zero when required files are missing, `00-idea.md` is still on the template, or no milestones were recorded. Treat a non-zero exit as a gate failure, not a warning.
