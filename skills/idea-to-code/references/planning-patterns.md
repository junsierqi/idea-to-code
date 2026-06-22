# Planning Patterns

## Purpose

Use this reference when turning a vague idea into requirements, splitting a large task into milestones, writing implementation plans, or shaping the final report.

## Clarify Vague Ideas

Convert fuzzy input into:

- target outcome
- primary user
- main flow
- success criteria
- non-goals
- constraints
- unknowns

Ask only when the ambiguity changes architecture, user-visible behavior, security, irreversibility, or scope. Decide ordinary implementation details and record the decision.

## Intake Gate Pattern

Before implementation, write this in `00-idea.md`:

```text
## Intake Gate

- Understanding: <implementation-term restatement>
- Assumptions: <assumptions that affect behavior or scope>
- Acceptance Criteria: <observable result>
- Need Confirmation: yes|no
- Confirmation Reason: <why confirmation is required or safely skipped>
```

Use `Need Confirmation: yes` for vague, risky, irreversible, security-sensitive, architecture-shaping, expensive, or multi-interpretation ideas. Ask for confirmation before implementation ready.

Use `Need Confirmation: no` when the idea is clear, low-risk, reversible, and acceptance is concrete. Continue autonomously after recording the intake.

If the user corrects the idea, update the same bundle when it is the same task (`clarification`, `expand`, or `switch`). Archive and start a new bundle only for unrelated work.

## Milestone Sizing

A useful milestone should:

- deliver a coherent product or code slice
- map to one or more REQ IDs
- be small enough to verify locally
- leave the project buildable
- have an explicit next gate

Large ideas usually split by:

1. scope and boundaries
2. protocol or data model
3. control-plane behavior
4. local state or persistence
5. user-facing flow
6. reliability and hardening
7. acceptance cleanup

## Implementation Plan Shape

Use `TASK-*` or `IMP-*` entries in `00-idea.md`:

```text
Gate Status: READY

### TASK-1: <change point>

Status: pending

Files:
- <files/modules>

Execution Details:
- <behavior/data/UI/test change to make>

Done Criteria:
- <how this item is complete>

Planned Verification:
- <command/runtime check/evidence target>
```

Do not mark READY until every task has concrete Files, Execution Details, Done Criteria, and Planned Verification.

## Final Report Shape

`finalize` generates `02-report.md`. The final report should make these easy to scan:

- target outcome
- trace matrix
- role evidence
- milestone rollup
- implementation summary
- verification and gate status
- visual evidence when relevant
- risks and follow-up

Keep the final user response shorter than the report. The report is the durable detail; the response is the handoff summary.
