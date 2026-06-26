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

## Controlled Exploration Pattern

Controlled Exploration is the bounded brainstorming step after Intake Gate and before Task Classification. It is not a separate user approval gate. It records whether exploration is needed, compares a small set of options only when needed, and chooses one decision before implementation planning.

Use this shape in `00-idea.md`:

```text
## Controlled Exploration

- Exploration Needed: yes|no
- Trigger: <why exploration is needed or safely skipped>
- Constraints:
  - <hard constraint from user, repository, governance, or runtime>
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

Default to `Exploration Needed: no`. Use `Exploration Needed: yes` only for real user-visible, architecture, API, cross-module, security, data, cost, migration, destructive-action, ambiguity, failure-cause, verification, or meaningful risk forks. Keep it to 2-4 options, then pick exactly one option before `implementation ready`.

When the user's requested implementation is flawed, treat it as a candidate path, explain the issue, and recommend a better default path. Do not dump low-level engineering choices on the user.

When `Need Confirmation: yes`, include the recommended decision in the existing confirmation request. The user still replies once with `yes`, `approved`, `change: <correction>`, `pause`, or `cancel`.

For optional prompt-level evaluation, use `controlled-exploration-benchmark.md`. The benchmark is a reference for maintainers, not part of the normal delivery flow.

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

Use `TASK-*` or `IMP-*` entries in `00-idea.md`. During intake and discovery,
the same entries are also the visible task list. It is acceptable for DRAFT
plans to use placeholder values such as `...` when concrete files, execution
details, done criteria, or verification commands are not known yet.

```text
Gate Status: DRAFT

### TASK-1: <change point>

Status: pending

Files:
- ...

Execution Details:
- ...

Done Criteria:
- ...

Planned Verification:
- ...
```

Use this shape even when there is only one task.

Do not mark READY until every placeholder has been replaced and every task has
concrete Files, Execution Details, Done Criteria, and Planned Verification.

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

Keep the final user response shorter than the report. The report is the durable detail; the response is the closeout summary.
