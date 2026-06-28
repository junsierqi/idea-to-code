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

If the user corrects or adds an idea inside the same conversation session, update the same bundle. Use `clarification`, `expand`, or `switch` for the active IDEA scope, or add a new IDEA-scoped unit with its own REQ/TASK rows for a new idea in the same session. Archive and start a new bundle for a new chat session or explicitly separate session/task. Do not move old ledger records into a new bundle; cite the old slug as `Related Session` or `Related IDEA` when known.

Use the chat session as the default ledger boundary. One session slug can contain multiple IDEA scopes because the ideas share context. Do not create one slug per user utterance or per idea by default: clarifications, acceptance details, new same-session ideas, and boundary cases belong in the same session bundle. If the relationship to the active session is ambiguous, ask a concise scope question before mutating bundle files.

## Controlled Exploration Pattern

Controlled Exploration is the bounded brainstorming step after Intake Gate and before Task Classification. It is also a required Exploration Visibility Gate before READY. It records whether exploration is needed, compares a small set of options only when needed, chooses one decision before implementation planning, and surfaces that decision to the user.

Rendered exploration output must separate `Planned Scope` from `Decision Options`. `Planned Scope` lists what is required now, what is deferred, and what READY may cover. `Decision Options` lists only mutually exclusive route choices. This keeps multi-change ideas readable: required items such as A and C are not presented as choices, while route options such as 1, 2, or a revised 3 remain explicit decisions.

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

When `Need Confirmation: no`, render `Exploration Result` and show `Planned Scope`, the selected approach, why it was chosen, and that implementation will proceed to READY. Do not ask for routine approval.

When `Need Confirmation: yes`, render `Confirmation Required` and include `Planned Scope`, `Decision Options`, the recommended decision, and explicit reply choices. The user can reply with `approve`, `choose: <option>`, `change: <correction>`, `explore more: <direction>`, `pause`, or `cancel`.

Each rendered output has an `EXPLORATION_OUTPUT_ID`. Planner evidence and final status should be able to trace the plan back to that output and to the later `READY_TASK_OUTPUT_ID`.

### Exploration Revision Pattern

When the user revises the exploration result, do not patch the old decision in prose. Treat it as a new exploration revision and generate a new `EXPLORATION_OUTPUT_ID`.

Use this revision shape when scope or route choices change:

```text
Exploration Revision:
- Required Now: <A, C>
- Deferred: <B>
- Rejected Options: <Option 1, Option 2>
- New / Selected Option: <Option 3, or direction only - more options needed>
- What READY Will Cover: <only the REQ/TASK scope approved for execution>
```

If the user says "1 and 2 are not what I want; explore in this direction", the direction is not automatically Option 3. Generate a new `Confirmation Required` output with new candidate options derived from that direction, recommend one, and keep `explore more: <direction>` available.

If the user says "use route 3" and route 3 is concrete, low-risk, and within the updated scope, generate `Exploration Result`, set `Required Now` and `What READY Will Cover`, and proceed to READY. Deferred items must not appear in READY except as explicit deferred/follow-up notes.

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

For large ideas, avoid making the exploration result compete with a long READY list. Keep the exploration result as a concise decision summary and use focused READY excerpts for the next executable TASK. A future extension may add grouped READY summaries, but it must preserve per-TASK Files, Done Criteria, Planned Verification, and TASK/REQ mapping.

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
