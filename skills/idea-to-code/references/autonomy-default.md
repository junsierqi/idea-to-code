# Autonomy By Default

## Intent

Use this when the user has already made the product direction clear and wants delivery momentum more than conversational steering.

## Default Execution Rule

Once the objective is clear enough to implement safely, keep moving without asking the user to confirm ordinary next steps.

- Choose the next milestone yourself.
- Implement it end to end.
- Run the strongest available verification.
- Record the milestone.
- Continue into the next milestone.

## Ask Only When Necessary

Ask the user only for:

- requirement conflicts
- major architectural forks with materially different cost or lock-in
- missing permissions, credentials, external services, or environment capabilities
- destructive or irreversible actions
- cases where repository context is insufficient to choose safely

## Do Not Ask For

Do not ask the user to confirm:

- whether to continue after a successful milestone
- whether to do the obvious next hardening or integration step
- whether to follow the established roadmap already implied by the work
- whether to fix a discovered issue that is clearly on the critical path

## Reporting Pattern

Use reports to keep the user informed, not to request routine permission.

- During execution: short milestone report
- At major completion: fuller delivery report
- On blocker: concise blocker report with the exact missing decision or dependency

## Next-Step Selection Heuristic

When several useful steps exist, prefer this order unless the repository strongly suggests otherwise:

1. unblock the critical path
2. tighten protocol or state consistency
3. improve persistence or reliability
4. harden validation and tests
5. improve UX, ergonomics, or secondary polish
