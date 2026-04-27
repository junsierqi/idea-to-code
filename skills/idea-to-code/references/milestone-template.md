# Milestone Template

## Purpose

Use this template when a user request is too large to complete safely in one shot.

## Good Milestone Shape

A milestone should:

- deliver one coherent capability
- keep the repository runnable
- create artifacts that can be tested
- reduce uncertainty for the next milestone

## Default Order

1. clarify scope and boundaries
2. define data model or protocol
3. implement control-plane behavior
4. implement local state behavior
5. implement user-facing behavior
6. harden with tests and acceptance cleanup

## Milestone Summary Format

When reporting a milestone, summarize:

- what changed
- how it was verified
- what remains
- the next concrete move

## Anti-Patterns

Avoid milestones that:

- only produce a plan with no code or docs change
- spread tiny edits across unrelated subsystems
- leave the project unable to build or run
- defer all testing to the final step
