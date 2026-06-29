# Product Charter

This charter is the maintainable product direction for idea-to-code. Use it when reviewing architecture, drift, repeated weaknesses, scope choices, or whether a new hardening idea fits the skill target.

## Product Target

idea-to-code is an intelligent, controllable, traceable delivery workflow that can turn a user's idea into verified software change. The current form is a Codex skill; the long-term direction is an agent foundation that can understand and improve user intent, plan implementation, execute with evidence, and close every idea, branch, task, and validation path without relying on chat memory.

The skill should make good engineering behavior easier to follow than ad hoc delivery:

- optimize vague or risky ideas into implementable requirements;
- show exploration and selected scope before tracked edits;
- keep IDEA/REQ/TASK/MB identities stable across a conversation;
- execute only visible, approved scope;
- validate with named evidence and honest validation types;
- review fit to the user's intended outcome, not just code or test success;
- install and verify latest skill code before claiming runtime readiness;
- make every open branch explicit as completed, deferred, rejected, blocked, residual risk, or external validation.
- make every controlled branch structurally auditable through an owner, gate/state record, evidence artifact, regression test, closeout surface, and enforcement boundary.

## Anti-Goals

Do not let the skill drift into any of these behaviors:

- command transcript noise that hides the decision path from the user;
- template-only status that looks compliant but does not answer the user's real question;
- chat-memory-only continuity without bundle state, stable IDs, or evidence;
- quickstart compression of complex scope into one file, one REQ, or one vague TASK;
- rule pileups that add process but do not improve user outcome, traceability, or verification;
- isolated hard rules that are not connected to a command, state record, test, and closeout surface;
- hidden or silently deferred scope;
- false "all done" claims while TODO, MB, REQ, validation, install, or branch items remain open;
- repeated weakness lists that do not use explicit classification for already hardened, residual risk, new gap, or external validation;
- pretending repo code can fully enforce host-required behavior such as native edit-tool interception.

## Drift Signals

Treat these as signals that the current flow may be leaving the product target:

- the answer cannot map current work back to a stable IDEA/REQ/TASK/MB record;
- the user asks "why was this not in TODO" or "which 1-7 is this" and the skill has no mapping;
- READY appears after editing starts, or only IDs are shown without meaningful exploration and task fields;
- a complex workflow, policy, docs, tests, install, or multi-file skill-hardening request enters quickstart;
- final or validation output uses fixed fields for ordinary discussion and obscures the actual answer;
- a weakness repeats across turns without status, enforcement boundary, prior evidence, or next action;
- a branch is described in prose but is missing from `branch-map --json` or fails `lifecycle-audit --json`;
- install is claimed without source/installed hash parity and installed focused tests;
- subagent, fresh-session, or independent review is claimed without a usable delegation record.

## Corrective Actions

When drift is detected, correct the process before continuing implementation:

- classify the issue as `already hardened`, `residual risk`, `new gap`, or `external validation`;
- label enforcement as `repo-enforced`, `skill-enforced`, or `host-required`;
- if it is a `new gap`, convert it into an explicit TODO, REQ/TASK, defer it, or reject it with a reason;
- run `lifecycle-audit --json` when the issue is structural or branch-level, and add the missing owner/gate/evidence/test/closeout/boundary before claiming the branch is hardened;
- use structured planning instead of quickstart for complex workflow, policy, docs, tests, install, multi-file, or skill-hardening work;
- record or update IDEA/REQ/TASK/MB mappings before claiming progress;
- re-render Exploration Result and focused READY when scope changes;
- validate source and installed skill behavior when skill runtime files changed;
- keep ordinary explanations natural in the user's language while preserving English protocol tokens.

## How To Use This Charter

Use this file as a product compass, not as a replacement for workflow gates. `SKILL.md` and the reference files define the runtime rules; this charter explains why those rules exist and how to detect drift from the target.

When adding new rules, tests, or commands, check them against three questions:

- Does this improve user-visible control, traceability, or delivery quality?
- Can a later agent verify the behavior from state, files, commands, or tests rather than chat memory?
- Does it close a real branch or failure mode without over-templating ordinary conversation?
- Does `lifecycle-audit --json` have enough structure to catch future drift in this branch?
