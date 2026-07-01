#!/usr/bin/env python3
"""Delivery-bundle manager for the idea-to-code skill.

Cross-platform: works anywhere Python 3.8+ is installed.
Invocation (bash on Windows/macOS/Linux):
    python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" <command> ...

The bundle lives under <project-root>/.idea-to-code/<slug>/ and holds:
    00-idea.md, 01-progress.md, 02-report.md, state.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from test_batch_runner import TEST_BATCH_PROFILE_KEYWORDS, run_test_batch


SCHEMA_VERSION = 6

REQUIREMENT_TYPES = ("functional", "nonfunctional", "constraint")
ROLE_NAMES = ("planner", "implementer", "validator", "reviewer", "closer")
USER_INPUT_CLASSIFICATIONS = (
    "continue",
    "expand",
    "switch",
    "new-task",
    "status",
    "pause",
    "blocked",
    "clarification",
    "no-op",
)
SESSION_RELATIONS = ("same-scope", "scope-correction", "new-related-scope", "unrelated")
PLAN_CHANGING_CLASSIFICATIONS = {"expand", "switch", "clarification"}
VALIDATION_TYPES = (
    "real-product-path",
    "mock-only",
    "fixture-only",
    "source-only",
    "dom-only",
    "manual-inspection",
    "unverified",
)
DELEGATION_STATUSES = ("usable", "timeout", "unusable", "planned", "unverified")
ENFORCEMENT_BOUNDARIES = ("repo-enforced", "skill-enforced", "host-required")
TASK_REQUIRED_SECTIONS = ("Files:", "Execution Details:", "Done Criteria:", "Planned Verification:")
TASK_SECTION_RESERVED_HEADINGS = {
    "## Requirements",
    "## Intake Gate",
    "## Controlled Exploration",
    "## Task Classification",
    "## Acceptance Matrix",
    "## Design",
    "## Implementation Plan",
    "## Verification",
    "## Visual Evidence",
    "## Risks And Follow-Up",
}
TASK_SECTION_PLACEHOLDER_RE = re.compile(r"<(?![!/?])(?:[^>\n]{1,80})>")
VALIDATION_TYPE_RE = re.compile(r"\b(" + "|".join(re.escape(kind) for kind in VALIDATION_TYPES) + r")\b", re.I)
ACCEPTANCE_MATRIX_COLUMNS = (
    "ID",
    "User Goal Fit",
    "Acceptance Examples",
    "Counterexamples",
    "Non-Goal Boundaries",
    "Expected Path",
    "Negative/Invalid Inputs",
    "Boundary Cases",
    "State/Persistence",
    "Rollback/Cancellation",
    "Error Reporting",
    "Observability",
    "Real Product Path",
    "Validation Type",
)
READY_TASK_OUTPUT_ID_LABEL = "READY_TASK_OUTPUT_ID"
EXPLORATION_OUTPUT_ID_LABEL = "EXPLORATION_OUTPUT_ID"
PRE_EDIT_OK_ID_LABEL = "PRE_EDIT_OK_ID"
READY_OUTPUT_FIELDS = (
    "ready_task_output_required",
    "ready_task_output_id",
    "ready_task_output_plan_revision",
    "ready_task_output_plan_fingerprint",
    "ready_task_output_at_utc",
    "ready_task_output_event_sequence",
    "ready_task_output_scope",
)
EXPLORATION_OUTPUT_FIELDS = (
    "exploration_output_required",
    "exploration_output_id",
    "exploration_output_plan_revision",
    "exploration_output_plan_fingerprint",
    "exploration_output_at_utc",
    "exploration_output_event_sequence",
    "exploration_output_mode",
)
PRE_EDIT_OUTPUT_FIELDS = (
    "pre_edit_guard_required",
    "pre_edit_ok_id",
    "pre_edit_plan_revision",
    "pre_edit_at_utc",
    "pre_edit_event_sequence",
    "pre_edit_task_id",
    "pre_edit_files",
    "pre_edit_ready_task_output_id",
    "pre_edit_exploration_output_id",
)
MASTER_BACKLOG_STATUSES = ("pending", "active", "deferred", "covered", "completed", "blocked")
IDEA_RECORD_STATUSES = ("active", "completed", "deferred", "rejected", "superseded", "blocked", "reference")
PLAN_UPDATE_SECTIONS = ("requirements", "design", "implementation")
BRANCH_COVERAGE_MAP = [
    {
        "id": "branch-coverage-map",
        "workflow_branch": "Branch coverage map branch",
        "entry": "reviewer needs to inspect idea-to-code lifecycle branch coverage",
        "exit": "branch-map exposes every workflow.md branch closure bullet with required fields",
        "validation": "branch-map --json matches workflow.md Branch closure checks",
        "failure_handling": "update the map or workflow branch text until coverage is exact",
    },
    {
        "id": "tracked-edit",
        "workflow_branch": "Tracked edit branch",
        "entry": "tracked implementation edit is about to start",
        "exit": "visible Exploration Result and focused READY exist for the exact TASK/REQ and files",
        "validation": "current EXPLORATION_OUTPUT_ID and READY_TASK_OUTPUT_ID predate edits",
        "failure_handling": "stop editing, refresh exploration or READY, and record noncompliance if edits already started",
    },
    {
        "id": "delegation-evidence",
        "workflow_branch": "Delegation evidence branch",
        "entry": "agent claims independent, subagent, fresh-agent, or team review evidence",
        "exit": "delegation record is usable for the current plan revision or resolved as a known fallback",
        "validation": "delegation status, verify, and render-status expose unusable or unresolved attempts",
        "failure_handling": "do not count planned, timed-out, unusable, or unverified delegation as independent evidence",
    },
    {
        "id": "same-session-continuity",
        "workflow_branch": "Same-session continuity branch",
        "entry": "a user message relates to earlier same-session work",
        "exit": "session audit and idea records preserve same-scope, correction, related, or unrelated classification",
        "validation": "idea status carries stable IDEA-* continuity across turns",
        "failure_handling": "audit prior related scope before answering, planning, or claiming completion",
    },
    {
        "id": "idea-ledger",
        "workflow_branch": "Idea ledger branch",
        "entry": "material same-session ideas may need future formal status",
        "exit": "idea record stores stable IDEA-* status, summary, related REQs, and notes",
        "validation": "idea status is checked before where-are-we or all-done answers",
        "failure_handling": "add or update idea records instead of relying on conversational memory",
    },
    {
        "id": "scope-classification",
        "workflow_branch": "Scope classification branch",
        "entry": "a follow-up could change or relate to active scope",
        "exit": "scope classify records same-scope, scope-correction, new-related-scope, or unrelated",
        "validation": "related corrections route to planning while unrelated questions remain ordinary answers",
        "failure_handling": "classify before planning, editing, or claiming tracked status",
    },
    {
        "id": "master-backlog",
        "workflow_branch": "Master backlog branch",
        "entry": "one related request contains multiple issues or work items",
        "exit": "backlog sync assigns stable MB-* IDs before READY",
        "validation": "READY and closeout keep pending or deferred MB IDs visible",
        "failure_handling": "accepted closeout is refused while master backlog items remain incomplete",
    },
    {
        "id": "enumerated-scope",
        "workflow_branch": "Enumerated scope branch",
        "entry": "user uses a numbered issue list as scope",
        "exit": "stable visible numbers preserve meanings or a mapping table explains changes",
        "validation": "Previous ID, Current ID, and Change Reason are visible before status claims use renumbered scope",
        "failure_handling": "do not silently reuse numbers for different work",
    },
    {
        "id": "current-task-entry",
        "workflow_branch": "Current TASK entry branch",
        "entry": "agent is about to work on a READY TASK",
        "exit": "implementation enter-task records current_task_id and prints READY Focus",
        "validation": "current task state matches the TASK being edited",
        "failure_handling": "use show-ready only as a fallback with a recorded reason",
    },
    {
        "id": "validation-type-preflight",
        "workflow_branch": "Validation type preflight branch",
        "entry": "TASK or IMP Planned Verification is written before READY",
        "exit": "implementation plan-check and READY reject missing approved validation types",
        "validation": "plan-check tests cover missing and accepted validation type cases",
        "failure_handling": "add an approved validation type before retrying READY",
    },
    {
        "id": "ready-recovery",
        "workflow_branch": "READY recovery branch",
        "entry": "READY, show-ready, enter-task, or pre-edit refuses because READY or Exploration is missing or stale",
        "exit": "implementation recover-ready prints concrete problems and exact recovery commands without mutating state",
        "validation": "missing, stale, and current READY recovery cases are covered by tests",
        "failure_handling": "follow recover-ready recommended commands before retrying lifecycle gates",
    },
    {
        "id": "implementation-lease",
        "workflow_branch": "Implementation lease branch",
        "entry": "tracked implementation edit needs file ownership",
        "exit": "implementation lease acquire records non-overlapping ownership for TASK files",
        "validation": "lease status shows active or released leases and finalize closes remaining active leases",
        "failure_handling": "refuse overlapping active leases for different owners",
    },
    {
        "id": "pre-edit-guard",
        "workflow_branch": "Pre-edit guard branch",
        "entry": "tracked edit is about to write TASK files",
        "exit": "implementation pre-edit prints PRE_EDIT_OK_ID and records approved files",
        "validation": "Implementer evidence cites the current guard ID and every edited file has guard coverage",
        "failure_handling": "the current TASK is not compliant until all planned edit files are covered",
    },
    {
        "id": "tool-layer-edit-wrapper",
        "workflow_branch": "Tool-layer edit wrapper branch",
        "entry": "future wrapper or host hook is available before file-editing tools",
        "exit": "wrapper verifies bundle, exploration, READY, lease, pre-edit, file scope, edit, and evidence linkage",
        "validation": "absence of the wrapper remains visible as residual risk",
        "failure_handling": "do not claim physical edit blocking until a real wrapper or host hook exists",
    },
    {
        "id": "pre-edit-noncompliance",
        "workflow_branch": "Pre-edit noncompliance branch",
        "entry": "an edit starts without a valid pre-edit guard",
        "exit": "implementation noncompliance records task, reason, and files as remediation evidence",
        "validation": "implementation status, verify, and render-status expose open noncompliance",
        "failure_handling": "accepted closeout cannot treat open noncompliance as complete work",
    },
    {
        "id": "plan-correction",
        "workflow_branch": "Plan-correction branch",
        "entry": "bundle planning files need correction before implementation",
        "exit": "READY is refreshed after the planning correction",
        "validation": "implementation edits wait for refreshed visible READY",
        "failure_handling": "limit planning-file correction to making READY accurate",
    },
    {
        "id": "read-only-status",
        "workflow_branch": "Read-only status branch",
        "entry": "user asks for tracked status without starting file edits",
        "exit": "formal tracked status uses render-status",
        "validation": "no pre-edit READY is required because no file edit starts",
        "failure_handling": "do not start implementation edits from a read-only status path",
    },
    {
        "id": "ordinary-answer",
        "workflow_branch": "Ordinary-answer branch",
        "entry": "user asks an unrelated or explanatory question outside tracked delivery",
        "exit": "concise natural answer with role/source prefix",
        "validation": "no fixed status template and no pre-edit READY are required",
        "failure_handling": "do not over-template ordinary explanations",
    },
    {
        "id": "formal-tracked-handoff",
        "workflow_branch": "Formal tracked handoff branch",
        "entry": "agent is giving final, validation, installation, or formal tracked status",
        "exit": "render-status runs first or the response states why it could not",
        "validation": "fixed fields map formal claims to TASK/REQ evidence",
        "failure_handling": "manual fixed-field status is only allowed with explicit render-status failure reason",
    },
    {
        "id": "display-artifact",
        "workflow_branch": "Display artifact branch",
        "entry": "required Display Layer output is generated by a command",
        "exit": "assistant-visible body contains the required Exploration, READY, or render-status block",
        "validation": "output-compliance check compares tool_stdout and assistant_visible_body",
        "failure_handling": "fail when required output exists only in command output or folded transcript",
    },
    {
        "id": "skill-self-validation",
        "workflow_branch": "Skill self-validation branch",
        "entry": "idea-to-code itself is being validated and full unittest is too slow or flaky",
        "exit": "official chunked runner records total test count, chunks, and pass/fail output",
        "validation": "test-batch --chunk-size 40 --timeout-seconds 180 is accepted self-validation evidence",
        "failure_handling": "record slow or flaky full-suite limits instead of claiming unrun coverage",
    },
    {
        "id": "user-facing-language",
        "workflow_branch": "User-facing language branch",
        "entry": "reply contains meaningful explanatory prose for a user",
        "exit": "explanatory prose uses the user's language while protocol terms remain English",
        "validation": "Protocol Glossary / Do-Not-Translate List protects IDs, commands, fields, paths, roles, and validation types",
        "failure_handling": "add new protocol terms to the glossary instead of inventing localized variants",
    },
    {
        "id": "weakness-review",
        "workflow_branch": "Weakness review branch",
        "entry": "agent lists architecture or process weaknesses",
        "exit": "each weakness uses already hardened, residual risk, new gap, or external validation",
        "validation": "residual risks are not converted into tasks without concrete remaining failure modes",
        "failure_handling": "reclassify vague weakness claims before planning work",
    },
    {
        "id": "enforcement-boundary",
        "workflow_branch": "Enforcement boundary branch",
        "entry": "agent reviews a weakness, residual risk, or control boundary",
        "exit": "the weakness is labeled repo-enforced, skill-enforced, or host-required",
        "validation": "host-required risks are not repeatedly converted into repo-only TODOs",
        "failure_handling": "separate repository fixes from host/tool integration requests before planning work",
    },
    {
        "id": "noncompliance",
        "workflow_branch": "Noncompliance branch",
        "entry": "READY, pre-edit, or other required control happened late or was missed",
        "exit": "noncompliant remediation is recorded and not counted as proof of prior compliance",
        "validation": "late controls remain visible in status and evidence",
        "failure_handling": "do not claim the earlier action followed the rule",
    },
]

BRANCH_INVARIANT_DEFAULTS = {
    "owner": "references/workflow.md",
    "gate": "branch-map plus branch-specific lifecycle command or state record",
    "evidence": "branch-specific command output, state.json record, role evidence, or visible assistant body",
    "test": "test_branch_map_matches_workflow_branch_closure_bullets and lifecycle invariant tests",
    "closeout_surface": "verify, render-status, reviewer evidence, or explicit residual risk",
    "enforcement_boundary": "skill-enforced",
}

BRANCH_INVARIANT_OVERRIDES = {
    "branch-coverage-map": {
        "owner": "references/workflow.md + scripts/idea_to_code_bundle.py",
        "gate": "branch-map --json and lifecycle-audit --json",
        "evidence": "BRANCH_COVERAGE_MAP output matching workflow branch bullets",
        "test": "test_branch_map_matches_workflow_branch_closure_bullets",
        "closeout_surface": "Reviewer evidence and lifecycle-audit output",
        "enforcement_boundary": "repo-enforced",
    },
    "tool-layer-edit-wrapper": {
        "gate": "implementation guarded-apply when available; host hook deferred",
        "evidence": "guarded-apply output or host-required residual risk disclosure",
        "test": "guarded-apply and residual-risk tests",
        "closeout_surface": "Residual Risks",
        "enforcement_boundary": "host-required",
    },
    "skill-self-validation": {
        "gate": "test-batch or full unittest command",
        "evidence": "test command output with total tests and pass/fail",
        "test": "test-batch and full-suite regression tests",
        "closeout_surface": "Validation Results",
        "enforcement_boundary": "repo-enforced",
    },
    "display-artifact": {
        "owner": "references/verification-and-evidence.md + references/roles-and-state.md",
        "gate": "output-compliance check",
        "evidence": "tool_stdout versus assistant_visible_body compliance result",
        "test": "output_compliance tests",
        "closeout_surface": "Validation Results and formal final body",
        "enforcement_boundary": "skill-enforced",
    },
}

BRANCH_INVARIANT_REQUIRED_FIELDS = (
    "owner",
    "gate",
    "evidence",
    "test",
    "closeout_surface",
    "enforcement_boundary",
)
LOCAL_RECORD_KINDS = {
    "A": "acceptance",
    "D": "discovery",
    "I": "iteration",
    "R": "risk",
    "V": "validation",
    "F": "follow-up",
}
QUICKSTART_INELIGIBLE_PATTERNS = (
    (
        re.compile(r"\b(workflow|lifecycle|process|policy|governance|compliance|rule|rules|guard|gate|ready|exploration)\b", re.I),
        "workflow/rule/lifecycle control work needs structured planning",
    ),
    (
        re.compile(r"\b(skill|agent foundation|product charter|product goal|self-hardening|self hardening)\b", re.I),
        "skill or product-direction hardening needs structured planning",
    ),
    (
        re.compile(r"\b(docs?|documentation|references?|test|tests|regression|install|installation|installed|hash|parity)\b", re.I),
        "scope involving docs, tests, install, or runtime evidence needs structured planning",
    ),
    (
        re.compile(r"\b(multi-file|multiple files|several files|more than one file)\b", re.I),
        "multi-file work needs structured planning",
    ),
)

FILES = {
    "00-idea.md": (
        "# Idea\n\n"
        "- Title: {title}\n"
        "- Slug: {slug}\n"
        "- Created At (UTC): {created_at}\n\n"
        "## Original Idea\n\n"
        "{idea_body}\n\n"
        "## Requirements\n\n"
        "- Target outcome:\n"
        "- Primary user:\n"
        "- Main flow:\n"
        "- Success criteria:\n"
        "- Non-goals:\n"
        "- Constraints:\n"
        "- Unknowns:\n"
        "\n## Intake Gate\n\n"
        "- Understanding:\n"
        "- Assumptions:\n"
        "- Acceptance Criteria:\n"
        "- Need Confirmation: yes/no\n"
        "- Confirmation Reason:\n"
        "\n## Controlled Exploration\n\n"
        "- Exploration Needed: yes/no\n"
        "- Trigger: <why exploration is needed or safely skipped>\n"
        "- Constraints:\n"
        "  - <hard constraint from user, repository, governance, or runtime>\n"
        "- Planned Scope:\n"
        "  - Required Now: <scope included in the next READY output>\n"
        "  - Deferred: <scope explicitly excluded or postponed>\n"
        "  - What READY Will Cover: <TASK/REQ scope allowed after this exploration output>\n"
        "- Options Considered:\n"
        "  - Option A: <approach>\n"
        "    - Hypothesis:\n"
        "    - Fit to user goal:\n"
        "    - Cost:\n"
        "    - Risk:\n"
        "    - Verification path:\n"
        "    - Rejection condition:\n"
        "- Decision:\n"
        "  - Chosen option:\n"
        "  - Decision reason:\n"
        "  - Rejected options:\n"
        "  - Unverified items:\n"
        "\n## Task Classification\n\n"
        "- File changes: yes/no\n"
        "- Semantic impact: yes/no/unclear\n"
        "- Tracking required: yes/no\n"
        "- Reason:\n"
        "\n## Acceptance Matrix\n\n"
        "{acceptance_matrix_header}\n"
        "\n## Design\n\n"
        "-\n\n"
        "## Implementation Plan\n\n"
        "Gate Status: DRAFT\n\n"
        "Rule: Do not edit code until Gate Status is READY and every TASK has "
        "Execution Details, Files, Done Criteria, and Planned Verification.\n\n"
        "During DRAFT, TASK blocks are the visible task list. Placeholder values "
        "such as `...` are allowed until repository discovery and intake confirmation "
        "make concrete implementation details available.\n\n"
        "### TASK-1: Define the first executable slice\n\n"
        "Status: pending\n\n"
        "Files:\n"
        "- ...\n\n"
        "Execution Details:\n"
        "- ...\n\n"
        "Done Criteria:\n"
        "- ...\n\n"
        "Planned Verification:\n"
        "- ...\n"
    ),
    "01-progress.md": (
        "# Progress\n\n"
        "## Current Phase\n\n"
        "- Status: in_progress\n"
        "- Current focus:\n"
        "- Next gate:\n\n"
        "## Local Records\n\n"
        "## Role Gates\n\n"
        "| Role | Latest Evidence | Covers |\n"
        "|------|-----------------|--------|\n"
        "| Planner | _(missing)_ | |\n"
        "| Implementer | _(missing)_ | |\n"
        "| Validator | _(missing)_ | |\n"
        "| Reviewer | _(missing)_ | |\n"
        "| Closer | _(missing)_ | |\n\n"
        "## Milestone History\n\n"
        "## Verification\n\n"
        "Validation types: real-product-path, mock-only, fixture-only, source-only, dom-only, manual-inspection, unverified.\n\n"
        "### Coverage Expectations\n\n"
        "- Build:\n"
        "- Unit/Integration:\n"
        "- End-to-end flow:\n"
        "- Remaining gaps:\n\n"
        "### Verification History\n\n"
        "## Risks\n\n"
        "-\n\n"
        "## Acceptance\n\n"
        "- Requested scope delivered:\n"
        "- Verification gate:\n"
        "- Decision:\n"
        "- Acceptance notes:\n"
        "- Deferred work:\n"
        "## Timeline\n\n"
    ),
    "02-report.md": (
        "# Report\n\n"
        "_Generated by finalize. Edit before finalize or pass --force to overwrite._\n\n"
        "## Target\n\n-\n\n"
        "## Milestones\n\n-\n\n"
        "## Implementation\n\n-\n\n"
        "## Verification\n\n-\n\n"
        "## Visual Evidence\n\n-\n\n"
        "## Risks And Follow-Up\n\n-\n"
    ),
}

EDITABLE_SECTIONS = {
    "idea": "00-idea.md",
    "requirements": "00-idea.md",
    "design": "00-idea.md",
    "implementation": "00-idea.md",
    "verification": "01-progress.md",
}
# 01-progress.md and 02-report.md include script-managed sections.

SECTION_HEADINGS = {
    "idea": "## Original Idea",
    "requirements": "## Requirements",
    "design": "## Design",
    "implementation": "## Implementation Plan",
    "verification": "## Verification",
}
SECTION_END_HEADINGS = {
    "idea": "## Requirements",
    "requirements": ("## Intake Gate", "## Controlled Exploration", "## Task Classification", "## Acceptance Matrix", "## Design"),
    "design": "## Implementation Plan",
    "implementation": None,
    "verification": "## Risks",
}
NEXT_TOP_LEVEL_HEADING = "__NEXT_TOP_LEVEL_HEADING__"

COMPACT_CONTRACT = "compact-v2"

GATE_CHOICES = ("pass", "partial", "fail")
DECISION_CHOICES = ("accepted", "accepted-with-followup", "not-accepted")

ARTIFACT_RESPONSIBILITIES = {
    "00-idea.md": "Original idea, Intake Gate, Controlled Exploration, requirements, design, acceptance matrix, and implementation plan.",
    "01-progress.md": "Human-readable progress ledger: local records, role gates, milestones, verification, risks, acceptance notes, and lifecycle events.",
    "02-report.md": "Final user-facing delivery report generated by finalize.",
    "state.json": "Machine-readable source of truth for state, phase, requirements, role evidence, local records, milestones, blockers, verification, and closeout.",
}

ROLE_ARTIFACT_MAP = {
    "planner": {
        "primary": ["00-idea.md"],
        "evidence": ["state.json", "01-progress.md"],
    },
    "implementer": {
        "primary": ["00-idea.md", "01-progress.md"],
        "evidence": ["state.json", "01-progress.md"],
    },
    "validator": {
        "primary": ["01-progress.md"],
        "evidence": ["state.json", "01-progress.md"],
    },
    "reviewer": {
        "primary": ["00-idea.md", "01-progress.md"],
        "evidence": ["state.json", "01-progress.md"],
    },
    "closer": {
        "primary": ["01-progress.md", "02-report.md", "state.json"],
        "evidence": ["01-progress.md", "state.json"],
    },
}

ROLE_GUIDANCE = {
    "planner": {
        "purpose": "Plan requirements, acceptance matrix, design, and TASK/IMP implementation plan before code edits.",
        "must_include": [
            "planned REQ IDs",
            "00-idea.md, Controlled Exploration, Exploration Visibility Gate output, requirements, acceptance matrix, or implementation plan",
            "TASK/IMP IDs or implementation-plan reference",
            "EXPLORATION_OUTPUT_ID and READY_TASK_OUTPUT_ID when the plan reached READY",
            "planning work, not validation, review, or closeout work",
        ],
        "must_not_include": [
            "claims that implementation or validation already happened unless those role gates have actually run",
            "vague phrases such as planned, ready, or looks good without REQ/TASK context",
        ],
        "example": "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 ready in 00-idea.md",
    },
    "implementer": {
        "purpose": "Record concrete implementation work after scoped files or modules are changed.",
        "must_include": [
            "implemented TASK/IMP IDs",
            "changed files or modules",
            "latest `PRE_EDIT_OK_ID` when a pre-edit guard exists for the current plan revision",
            "implementation verbs such as added, updated, changed, created, or refactored",
            "implementation work, not planning, validation, review, or closeout work",
        ],
        "must_not_include": [
            "test-only evidence without naming the implemented change",
            "broad claims such as done without file/module and TASK/IMP context",
        ],
        "example": "TASK-1 implemented by updating skills/idea-to-code/scripts/idea_to_code_bundle.py",
    },
    "validator": {
        "purpose": "Record validation evidence with the validation type, command, and covered requirements.",
        "must_include": [
            "covered REQ IDs",
            "one validation type from the approved validation taxonomy",
            "validation action, command, or inspection path",
            "validation work, not another role",
        ],
        "must_not_include": [
            "a passing command without explaining the validation type or covered requirement",
            "unverified evidence without naming the missing dependency or reason",
        ],
        "example": "REQ-1 source-only validation ran python skills/idea-to-code/scripts/test_idea_to_code_bundle.py BundleTest.test_example",
    },
    "reviewer": {
        "purpose": "Review scope, diff, acceptance coverage, boundaries, validation strength, and residual risks.",
        "must_include": [
            "scope, coverage, boundary, architecture, acceptance matrix, or residual risk review",
            "reviewed requirements, implementation, verification, or REQ/TASK/IMP IDs",
            "review work, not another role",
            "same-agent review when the reviewer is not a real independent subagent",
        ],
        "must_not_include": [
            "independent-review claims unless a real subagent/person actually ran and returned evidence",
            "acceptance claims that ignore counterexamples, non-goals, unverified items, or residual risks",
        ],
        "example": "same-agent review checked REQ-1 scope, diff, acceptance matrix, validation strength, and residual risk",
    },
    "closer": {
        "purpose": "Close the task after pre-close verify passes and final decision/gate alignment is known.",
        "must_include": [
            "pre-close verify passed",
            "final decision, gate alignment, or REQ coverage",
            "closeout work, not another role",
            "accepted closeout-status wording such as `prior role evidence is current` when referring to earlier role gates",
        ],
        "must_not_include": [
            "closeout before Reviewer evidence and pre-close verify",
            "accepted/completed claims when coverage, validation, role evidence, or final verify is still missing",
            "claims that the closer performed planning, implementation, validation, or review work",
        ],
        "example": "Pre-close verify passed; prior role evidence is current; REQ-1 covered by passing milestone evidence; final decision pass accepted",
    },
}

IDEA_FILE = "00-idea.md"
PROGRESS_FILE = "01-progress.md"
REPORT_FILE = "02-report.md"
STATE_FILE = "state.json"
MILESTONES_FILE = PROGRESS_FILE
VERIFICATION_FILE = PROGRESS_FILE
ACCEPTANCE_FILE = PROGRESS_FILE
EXECUTION_LOG_FILE = PROGRESS_FILE
FINAL_REPORT_FILE = REPORT_FILE
IMPLEMENTATION_FILE = IDEA_FILE
LEDGER_FILE = EXECUTION_LOG_FILE


# ---------- helpers ----------

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def local_slug_prefix() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M")


def normalize_slug(raw: str) -> str:
    base = raw.strip().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = re.sub(r"-{2,}", "-", base).strip("-")
    return (base or "task")[:64].strip("-") or "task"


def timestamped_slug(raw: str) -> str:
    normalized = normalize_slug(raw)
    if re.match(r"^\d{8}-\d{4}-", normalized):
        return normalized
    return f"{local_slug_prefix()}-{normalized}"


def project_state_dir(root: Path) -> Path:
    return root / ".idea-to-code"


def bundle_dir(root: Path, slug: str) -> Path:
    return project_state_dir(root) / slug


def current_path(root: Path) -> Path:
    return project_state_dir(root) / "current.json"


def history_dir(root: Path) -> Path:
    return project_state_dir(root) / "history"


def history_index_path(root: Path) -> Path:
    return history_dir(root) / "index.jsonl"


def ensure_bundle(root: Path, slug: str) -> Path:
    target = bundle_dir(root, slug)
    if not target.exists():
        raise SystemExit(
            f"Bundle does not exist: {target}\n"
            "Run 'init' first, or check --root / --slug."
        )
    return target


def unique_bundle_slug(root: Path, slug: str) -> str:
    candidate = slug
    suffix = 2
    while bundle_dir(root, candidate).exists():
        candidate = f"{slug}-{suffix:02d}"
        suffix += 1
    return candidate


def write_current(root: Path, slug: str, status: str = "planning") -> None:
    target = bundle_dir(root, slug)
    current_path(root).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "slug": slug,
        "path": str(Path(".idea-to-code") / slug),
        "status": status,
        "created_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "implementation_file": IMPLEMENTATION_FILE,
    }
    if target.exists() and state_exists(target):
        bundle_status = read_status(target)
        payload["status"] = bundle_status.get("phase") or bundle_status.get("state", status)
        payload["created_at_utc"] = bundle_status.get("created_at_utc", payload["created_at_utc"])
    current_path(root).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_current(root: Path) -> dict | None:
    path = current_path(root)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def append_history(root: Path, slug: str, status: dict, reason: str) -> None:
    history_dir(root).mkdir(parents=True, exist_ok=True)
    row = {
        "slug": slug,
        "status": status.get("state", "unknown"),
        "decision": status.get("decision"),
        "gate_status": status.get("gate_status"),
        "closed_at_utc": status.get("finalized_at_utc") or utc_now(),
        "summary": status.get("title", ""),
        "reason": reason,
        "path": str(Path(".idea-to-code") / slug),
    }
    with history_index_path(root).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def render_template(content: str, **fields: str) -> str:
    defaults = {"idea_body": ""}
    defaults.update(fields)
    return content.format(**defaults)


def acceptance_matrix_header() -> str:
    header = "| " + " | ".join(ACCEPTANCE_MATRIX_COLUMNS) + " |"
    separator = "|" + "|".join("---" for _ in ACCEPTANCE_MATRIX_COLUMNS) + "|"
    return header + "\n" + separator


def ensure_file(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def state_path(target: Path) -> Path:
    return target / STATE_FILE


def state_exists(target: Path) -> bool:
    return state_path(target).exists()


def read_status(target: Path) -> dict:
    status_path = state_path(target)
    for attempt in range(8):
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            break
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.025 * (attempt + 1))
    status.setdefault("schema_version", 1)
    status.setdefault("artifact_contract", COMPACT_CONTRACT)
    status.setdefault("milestones", [])
    status.setdefault("blocks", [])
    status.setdefault("requirements", [])
    status.setdefault("local_records", [])
    status.setdefault("plan_revision", 0)
    status.setdefault("last_verify_ok", False)
    status.setdefault("last_verified_plan_revision", None)
    status.setdefault("user_input_decisions", [])
    status.setdefault("pending_plan_update", False)
    status.setdefault("pending_plan_update_sections", [])
    _migrate_exploration_output_fields(status)
    _migrate_ready_output_fields(status)
    _migrate_current_task_fields(status)
    _migrate_pre_edit_output_fields(status)
    _migrate_master_backlog_fields(status)
    _migrate_idea_record_fields(status)
    status.setdefault("role_evidence", {})
    for role in ROLE_NAMES:
        status["role_evidence"].setdefault(role, [])
    return status


def _migrate_ready_output_fields(status: dict) -> None:
    status.setdefault("ready_task_output_required", False)
    status.setdefault("ready_task_output_id", None)
    status.setdefault("ready_task_output_plan_revision", None)
    status.setdefault("ready_task_output_at_utc", None)
    status.setdefault("ready_task_output_event_sequence", None)
    status.setdefault("ready_task_output_scope", None)
    status.setdefault("ready_task_output_history", [])
    status.setdefault("event_sequence", 0)
    status.setdefault("last_verified_event_sequence", None)


def _migrate_exploration_output_fields(status: dict) -> None:
    status.setdefault("exploration_output_required", False)
    status.setdefault("exploration_output_id", None)
    status.setdefault("exploration_output_plan_revision", None)
    status.setdefault("exploration_output_at_utc", None)
    status.setdefault("exploration_output_event_sequence", None)
    status.setdefault("exploration_output_mode", None)


def _migrate_current_task_fields(status: dict) -> None:
    status.setdefault("current_task_id", None)
    status.setdefault("current_task_entered_at_utc", None)
    status.setdefault("current_task_event_sequence", None)
    status.setdefault("current_task_ready_output_id", None)


def _migrate_pre_edit_output_fields(status: dict) -> None:
    status.setdefault("pre_edit_guard_required", False)
    status.setdefault("pre_edit_ok_id", None)
    status.setdefault("pre_edit_plan_revision", None)
    status.setdefault("pre_edit_at_utc", None)
    status.setdefault("pre_edit_event_sequence", None)
    status.setdefault("pre_edit_task_id", None)
    status.setdefault("pre_edit_files", [])
    status.setdefault("pre_edit_owner", None)
    status.setdefault("pre_edit_ready_task_output_id", None)
    status.setdefault("pre_edit_exploration_output_id", None)
    status.setdefault("pre_edit_records", [])
    status.setdefault("pre_edit_noncompliance", [])
    status.setdefault("implementation_leases", [])
    status.setdefault("delegation_records", [])
    status.setdefault("session_continuity_audits", [])
    status.setdefault("scope_classifications", [])
    status.setdefault("visible_output_required", False)
    status.setdefault("visible_output_id", None)
    status.setdefault("visible_output_records", [])
    if status.get("pre_edit_ok_id") and not status["pre_edit_records"]:
        status["pre_edit_records"].append({
            "id": status.get("pre_edit_ok_id"),
            "task_id": status.get("pre_edit_task_id"),
            "files": status.get("pre_edit_files") or [],
            "ready_task_output_id": status.get("pre_edit_ready_task_output_id"),
            "exploration_output_id": status.get("pre_edit_exploration_output_id"),
            "plan_revision": status.get("pre_edit_plan_revision"),
            "event_sequence": status.get("pre_edit_event_sequence"),
            "at_utc": status.get("pre_edit_at_utc"),
        })


def _current_visible_output_record(status: dict, task_id: str) -> dict | None:
    plan_revision = int(status.get("plan_revision", 0))
    ready_id = status.get("ready_task_output_id")
    exploration_id = status.get("exploration_output_id")
    normalized_task_id = task_id.strip().upper()
    for record in reversed(status.get("visible_output_records", [])):
        if record.get("plan_revision") != plan_revision:
            continue
        if record.get("ready_task_output_id") != ready_id:
            continue
        if record.get("exploration_output_id") != exploration_id:
            continue
        if (record.get("task_id") or "").strip().upper() != normalized_task_id:
            continue
        if not record.get("ok", False):
            continue
        return record
    return None


def _visible_output_problem(status: dict, task_id: str) -> str | None:
    if not status.get("ready_task_output_required") and not status.get("exploration_output_required"):
        return None
    if _current_visible_output_record(status, task_id):
        return None
    return (
        "visible output record missing or stale for current Exploration Result and READY Focus; "
        "paste the assistant-visible Display Layer block, then run implementation visible-output record"
    )


def _migrate_master_backlog_fields(status: dict) -> None:
    status.setdefault("master_backlog_required", False)
    status.setdefault("master_backlog", [])
    status.setdefault("master_backlog_synced_at_utc", None)
    status.setdefault("master_backlog_plan_revision", None)
    status.setdefault("master_backlog_event_sequence", None)


def _migrate_idea_record_fields(status: dict) -> None:
    status.setdefault("idea_records", [])
    status.setdefault("idea_record_event_sequence", None)


def _next_event_sequence(status: dict) -> int:
    status["event_sequence"] = int(status.get("event_sequence") or 0) + 1
    return status["event_sequence"]


def _entry_order_value(entry: dict) -> tuple[int, int | str]:
    sequence = int(entry.get("event_sequence") or 0)
    if sequence:
        return (1, sequence)
    return (0, entry.get("timestamp_utc", ""))


def _verify_is_older_than_entry(status: dict, entry: dict) -> bool:
    entry_sequence = int(entry.get("event_sequence") or 0)
    verified_sequence = int(status.get("last_verified_event_sequence") or 0)
    if entry_sequence and verified_sequence:
        return verified_sequence < entry_sequence
    entry_timestamp = entry.get("timestamp_utc", "")
    verified_timestamp = status.get("last_verified_at_utc", "")
    return bool(entry_timestamp and verified_timestamp < entry_timestamp)


def _clear_ready_output(status: dict) -> None:
    for field in READY_OUTPUT_FIELDS:
        status[field] = False if field.endswith("_required") else None


def _clear_exploration_output(status: dict) -> None:
    for field in EXPLORATION_OUTPUT_FIELDS:
        status[field] = False if field.endswith("_required") else None


def _set_pending_plan_update(status: dict, sections: tuple[str, ...] | list[str] = PLAN_UPDATE_SECTIONS) -> None:
    existing = {
        str(section)
        for section in status.get("pending_plan_update_sections", [])
        if str(section) in PLAN_UPDATE_SECTIONS
    }
    existing.update(section for section in sections if section in PLAN_UPDATE_SECTIONS)
    status["pending_plan_update_sections"] = [
        section for section in PLAN_UPDATE_SECTIONS if section in existing
    ]
    status["pending_plan_update"] = bool(status["pending_plan_update_sections"])


def _clear_pending_plan_section(status: dict, section: str) -> None:
    pending = [
        item
        for item in status.get("pending_plan_update_sections", [])
        if item in PLAN_UPDATE_SECTIONS and item != section
    ]
    status["pending_plan_update_sections"] = pending
    status["pending_plan_update"] = bool(pending)


def _pending_plan_update_problem(status: dict) -> str | None:
    if not status.get("pending_plan_update"):
        return None
    sections = [
        item
        for item in status.get("pending_plan_update_sections", [])
        if item in PLAN_UPDATE_SECTIONS
    ]
    if sections:
        return "pending plan update sections remain stale: " + ", ".join(sections)
    return "user input changed the plan but requirements/design/implementation were not updated"


def _master_backlog_ids_from_text(text: str) -> list[str]:
    ids = {match.group(0).upper() for match in re.finditer(r"\bMB-\d+\b", text, re.I)}
    range_pattern = re.compile(
        r"\bMB-(?P<start>\d+)\b\s*(?:\.\.|through|to)\s*\bMB-(?P<end>\d+)\b",
        re.I,
    )
    for match in range_pattern.finditer(text):
        start = int(match.group("start"))
        end = int(match.group("end"))
        low, high = sorted((start, end))
        if high - low > 200:
            continue
        ids.update(f"MB-{index}" for index in range(low, high + 1))
    return sorted(
        ids,
        key=lambda value: int(value.split("-", 1)[1]),
    )


def _master_backlog_label_from_text(text: str, mb_id: str) -> str:
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or mb_id not in _master_backlog_ids_from_text(cells[0]):
            continue
        cleaned_cells = [re.sub(r"\s+", " ", cell) for cell in cells[:3] if cell]
        cleaned = " | ".join(cleaned_cells)[:120].strip()
        if cleaned:
            return cleaned
    fallback = ""
    for line in text.splitlines():
        if "|" not in line or mb_id not in _master_backlog_ids_from_text(line):
            continue
        line_mb_ids = _master_backlog_ids_from_text(line)
        if len(line_mb_ids) == 1:
            cleaned = re.sub(r"\s+", " ", line.strip(" |-"))
            cleaned = cleaned[:120].strip()
            if cleaned:
                return cleaned
    for line in text.splitlines():
        line_mb_ids = _master_backlog_ids_from_text(line)
        if mb_id not in line_mb_ids:
            continue
        if len(line_mb_ids) > 1:
            fallback = fallback or re.sub(r"\s+", " ", line.strip(" |-"))[:120].strip()
            continue
        cleaned = re.sub(r"\s+", " ", line.strip(" |-"))
        cleaned = cleaned[:120].strip()
        if cleaned:
            return cleaned
    return fallback or mb_id


def _master_backlog_ids_from_plan(target: Path) -> list[str]:
    idea_path = target / IDEA_FILE
    if not idea_path.exists():
        return []
    return _master_backlog_ids_from_text(idea_path.read_text(encoding="utf-8"))


def _requirement_mb_map(status: dict) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for requirement in status.get("requirements", []):
        rid = requirement.get("id", "")
        text = f"{rid} {requirement.get('description', '')}"
        mb_ids = _master_backlog_ids_from_text(text)
        if mb_ids:
            mapping[rid] = mb_ids
    return mapping


def _master_backlog_item_map(status: dict) -> dict[str, dict]:
    return {
        str(item.get("id", "")).upper(): item
        for item in status.get("master_backlog", [])
        if item.get("id")
    }


def _master_backlog_incomplete_items(status: dict) -> list[dict]:
    incomplete = []
    for item in status.get("master_backlog", []):
        if item.get("status") not in {"covered", "completed", "deferred"}:
            incomplete.append(item)
    return incomplete


def _master_backlog_remaining_items(status: dict) -> list[dict]:
    remaining = []
    for item in status.get("master_backlog", []):
        if item.get("status") not in {"covered", "completed"}:
            remaining.append(item)
    return remaining


def _master_backlog_problems(target: Path, status: dict) -> list[str]:
    plan_ids = _master_backlog_ids_from_plan(target)
    if len(plan_ids) <= 1 and not status.get("master_backlog_required"):
        return []
    problems: list[str] = []
    items = _master_backlog_item_map(status)
    if not items:
        problems.append("master backlog required but not synced; run backlog sync before READY or completion claims")
        return problems
    missing = [mb_id for mb_id in plan_ids if mb_id not in items]
    extra = [mb_id for mb_id in items if mb_id not in plan_ids]
    if missing:
        problems.append("master backlog missing IDs from plan: " + ", ".join(missing))
    if extra:
        problems.append("master backlog has IDs not present in plan: " + ", ".join(extra))
    if status.get("master_backlog_plan_revision") != status.get("plan_revision"):
        problems.append("master backlog is stale for current plan revision; run backlog sync")
    return problems


def _open_pre_edit_noncompliance(status: dict) -> list[dict]:
    return [
        event for event in status.get("pre_edit_noncompliance", [])
        if not event.get("resolved_at_utc")
    ]


def _pre_edit_records_for_task(status: dict, task_id: str) -> list[dict]:
    wanted = task_id.strip().upper()
    return [
        record for record in status.get("pre_edit_records", [])
        if str(record.get("task_id", "")).strip().upper() == wanted
    ]


def _active_implementation_leases(status: dict) -> list[dict]:
    return [
        lease for lease in status.get("implementation_leases", [])
        if not lease.get("released_at_utc")
    ]


def _lease_covered_files(status: dict, task_id: str, owner: str = "agent") -> set[str]:
    covered: set[str] = set()
    wanted_task = task_id.strip().upper()
    wanted_owner = owner.strip() or "agent"
    plan_revision = int(status.get("plan_revision", 0))
    ready_id = status.get("ready_task_output_id")
    for lease in _active_implementation_leases(status):
        if str(lease.get("task_id", "")).strip().upper() != wanted_task:
            continue
        if str(lease.get("owner", "")).strip() != wanted_owner:
            continue
        if lease.get("plan_revision") != plan_revision:
            continue
        if lease.get("ready_task_output_id") != ready_id:
            continue
        for item in lease.get("files") or []:
            covered.add(_normalize_guard_file(str(item)))
    return covered


def _lease_conflicts(status: dict, task_id: str, owner: str, files: list[str]) -> list[dict]:
    requested = {_normalize_guard_file(item) for item in files}
    conflicts: list[dict] = []
    plan_revision = int(status.get("plan_revision", 0))
    ready_id = status.get("ready_task_output_id")
    for lease in _active_implementation_leases(status):
        if str(lease.get("owner", "")).strip() == owner:
            continue
        if lease.get("plan_revision") != plan_revision:
            continue
        if lease.get("ready_task_output_id") != ready_id:
            continue
        leased_files = {_normalize_guard_file(str(item)) for item in lease.get("files") or []}
        overlap = sorted(requested & leased_files)
        if overlap:
            conflict = dict(lease)
            conflict["overlap"] = overlap
            conflicts.append(conflict)
    return conflicts


def _lease_compliance_problems(status: dict, task_id: str, requested_files: list[str], owner: str = "agent") -> list[str]:
    requested = {_normalize_guard_file(item) for item in requested_files}
    covered = _lease_covered_files(status, task_id, owner)
    missing = sorted(requested - covered)
    if not missing:
        return []
    return [
        f"implementation lease missing for {task_id.strip().upper()} owner {owner} file(s): "
        + ", ".join(missing)
    ]


def _usable_delegation_records(status: dict, role: str | None = None) -> list[dict]:
    records = []
    plan_revision = int(status.get("plan_revision", 0))
    wanted_role = role.strip().lower() if role else None
    for record in status.get("delegation_records", []):
        if record.get("plan_revision") != plan_revision:
            continue
        if record.get("status") != "usable":
            continue
        if wanted_role and str(record.get("role", "")).lower() != wanted_role:
            continue
        records.append(record)
    return records


def _open_delegation_findings(status: dict) -> list[dict]:
    plan_revision = int(status.get("plan_revision", 0))
    return [
        record for record in status.get("delegation_records", [])
        if record.get("plan_revision") == plan_revision
        and record.get("status") != "usable"
        and not record.get("resolved_at_utc")
    ]


def _delegation_record_by_id(status: dict, record_id: str) -> dict | None:
    wanted = record_id.strip()
    for record in status.get("delegation_records", []):
        if record.get("id") == wanted:
            return record
    return None


def _delegation_problems(status: dict) -> list[str]:
    problems = []
    for record in _open_delegation_findings(status):
        problems.append(
            f"delegation evidence not usable {record.get('id', 'unknown')} "
            f"role={record.get('role', 'unknown')} status={record.get('status', 'unknown')}: "
            f"{record.get('reason') or record.get('evidence_summary') or 'no reason recorded'}"
        )
    return problems


def _evidence_claims_independent_delegation(evidence: str) -> bool:
    normalized = " ".join(evidence.lower().split())
    negative_patterns = (
        r"\b(no|not|without|unavailable|timed out|timeout|failed|unusable|not usable|did not|didn't)\b.{0,48}\b(independent review|independent validation|subagent|fresh-agent|hybrid-team|independent-team)\b",
        r"\b(independent review|independent validation|subagent|fresh-agent|hybrid-team|independent-team)\b.{0,48}\b(no|not|without|unavailable|timed out|timeout|failed|unusable|not usable|did not|didn't|not run|not rerun)\b",
        r"\b(test|tests|tested|validation|validated|focused tests|test case|test name)\b.{0,80}\b(independent review|independent validation|subagent|fresh-agent|hybrid-team|independent-team)\b",
    )
    scrubbed = normalized
    for pattern in negative_patterns:
        scrubbed = re.sub(pattern, " ", scrubbed)
    return bool(re.search(
        r"\b(independent review|independent validation|hybrid-team|independent-team|subagent|fresh-agent)\b",
        scrubbed,
        re.I,
    ))


def _pre_edit_covered_files(status: dict, task_id: str) -> set[str]:
    covered: set[str] = set()
    plan_revision = int(status.get("plan_revision", 0))
    ready_id = status.get("ready_task_output_id")
    exploration_id = status.get("exploration_output_id")
    for record in _pre_edit_records_for_task(status, task_id):
        if record.get("plan_revision") != plan_revision:
            continue
        if record.get("ready_task_output_id") != ready_id:
            continue
        if record.get("exploration_output_id") != exploration_id:
            continue
        for item in record.get("files") or []:
            covered.add(_normalize_guard_file(str(item)))
    return covered


def _pre_edit_compliance_problems(target: Path, status: dict, task_id: str | None = None) -> list[str]:
    problems: list[str] = []
    current_task = (task_id or status.get("current_task_id") or "").strip().upper()
    if current_task:
        visible_problem = _visible_output_problem(status, current_task)
        if visible_problem:
            problems.append(visible_problem)
        expected = {_normalize_guard_file(item) for item in _task_files_for_id(target, current_task)}
        covered = _pre_edit_covered_files(status, current_task)
        missing = sorted(expected - covered)
        if missing:
            problems.append(
                f"pre-edit guard missing current records for {current_task} file(s): "
                + ", ".join(missing)
            )
    for event in _open_pre_edit_noncompliance(status):
        event_id = event.get("id", "unknown")
        event_task = event.get("task_id") or "unknown-task"
        reason = event.get("reason") or "no reason recorded"
        problems.append(f"open pre-edit noncompliance {event_id} for {event_task}: {reason}")
    return problems


def _pre_edit_compliance_problems_for_verify(status: dict) -> list[str]:
    problems: list[str] = []
    current_task = (status.get("current_task_id") or "").strip().upper()
    if current_task:
        visible_problem = _visible_output_problem(status, current_task)
        if visible_problem:
            problems.append(visible_problem)
    problems.extend([
        f"open pre-edit noncompliance {event.get('id', 'unknown')} for "
        f"{event.get('task_id') or 'unknown-task'}: {event.get('reason') or 'no reason recorded'}"
        for event in _open_pre_edit_noncompliance(status)
    ])
    return problems


def _update_master_backlog_coverage(status: dict, covers: list[str], milestone: str) -> None:
    req_map = _requirement_mb_map(status)
    covered_mb_ids = sorted({mb_id for rid in covers for mb_id in req_map.get(rid, [])}, key=lambda value: int(value.split("-", 1)[1]))
    if not covered_mb_ids:
        return
    for item in status.get("master_backlog", []):
        if item.get("id") in covered_mb_ids:
            item.setdefault("covered_by", [])
            if milestone not in item["covered_by"]:
                item["covered_by"].append(milestone)
            if item.get("status") not in {"completed", "deferred"}:
                item["status"] = "covered"


def _reset_ready_for_plan_change(status: dict, focus: str, pending_sections: tuple[str, ...] | list[str] | None = None) -> None:
    status["implementation_ready"] = False
    _clear_exploration_output(status)
    _clear_ready_output(status)
    status["plan_revision"] = int(status.get("plan_revision", 0)) + 1
    status["last_verify_ok"] = False
    status["last_verified_plan_revision"] = None
    status["phase"] = "planning"
    status["current_focus"] = focus
    if pending_sections is not None:
        _set_pending_plan_update(status, pending_sections)


def write_status(target: Path, status: dict) -> None:
    status["updated_at_utc"] = utc_now()
    status["artifact_contract"] = COMPACT_CONTRACT
    _migrate_exploration_output_fields(status)
    _migrate_ready_output_fields(status)
    _migrate_current_task_fields(status)
    _migrate_pre_edit_output_fields(status)
    _migrate_master_backlog_fields(status)
    status_path = state_path(target)
    tmp_path = target / f"{status_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    tmp_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        for attempt in range(8):
            try:
                tmp_path.replace(status_path)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.025 * (attempt + 1))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


@contextmanager
def bundle_lock(target: Path, timeout_seconds: float = 10.0):
    """Serialize bundle status mutations across concurrent agent processes."""
    lock_dir = target / ".status.lock"
    env_timeout = os.environ.get("IDEA_TO_CODE_LOCK_TIMEOUT_SECONDS")
    if env_timeout:
        try:
            timeout_seconds = float(env_timeout)
        except ValueError:
            pass
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_dir.mkdir()
            owner = {
                "pid": os.getpid(),
                "created_at_utc": utc_now(),
                "lock_path": str(lock_dir),
            }
            (lock_dir / "owner.json").write_text(
                json.dumps(owner, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                owner_path = lock_dir / "owner.json"
                owner_detail = "owner metadata unavailable"
                if owner_path.exists():
                    try:
                        owner_payload = json.loads(owner_path.read_text(encoding="utf-8"))
                        owner_detail = (
                            f"owner pid={owner_payload.get('pid', 'unknown')}, "
                            f"created_at_utc={owner_payload.get('created_at_utc', 'unknown')}"
                        )
                    except (OSError, json.JSONDecodeError):
                        owner_detail = "owner metadata unreadable"
                raise SystemExit(
                    "Timed out waiting for bundle lock: "
                    f"{lock_dir}; {owner_detail}; timeout_seconds={timeout_seconds}. "
                    "If no idea_to_code_bundle.py process with that pid is running, "
                    f"remove {lock_dir} and retry."
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            owner_path = lock_dir / "owner.json"
            if owner_path.exists():
                owner_path.unlink()
            lock_dir.rmdir()
        except FileNotFoundError:
            pass


@contextmanager
def current_lock(root: Path, timeout_seconds: float = 10.0):
    """Serialize .idea-to-code/current.json mutations across agent processes."""
    lock_dir = project_state_dir(root) / ".current.lock"
    env_timeout = os.environ.get("IDEA_TO_CODE_LOCK_TIMEOUT_SECONDS")
    if env_timeout:
        try:
            timeout_seconds = float(env_timeout)
        except ValueError:
            pass
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_dir.mkdir()
            owner = {
                "pid": os.getpid(),
                "created_at_utc": utc_now(),
                "lock_path": str(lock_dir),
            }
            (lock_dir / "owner.json").write_text(
                json.dumps(owner, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                owner_path = lock_dir / "owner.json"
                owner_detail = "owner metadata unavailable"
                if owner_path.exists():
                    try:
                        owner_payload = json.loads(owner_path.read_text(encoding="utf-8"))
                        owner_detail = (
                            f"owner pid={owner_payload.get('pid', 'unknown')}, "
                            f"created_at_utc={owner_payload.get('created_at_utc', 'unknown')}"
                        )
                    except (OSError, json.JSONDecodeError):
                        owner_detail = "owner metadata unreadable"
                raise SystemExit(
                    "Timed out waiting for current pointer lock: "
                    f"{lock_dir}; {owner_detail}; timeout_seconds={timeout_seconds}. "
                    "If no idea_to_code_bundle.py process with that pid is running, "
                    f"remove {lock_dir} and retry."
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            owner_path = lock_dir / "owner.json"
            if owner_path.exists():
                owner_path.unlink()
            lock_dir.rmdir()
        except FileNotFoundError:
            pass


def rewrite_current_phase(milestones_path: Path, replacement_lines: list[str]) -> None:
    """Replace or insert the `## Current Phase` block inside 01-progress.md.

    - Replaces the existing block if found.
    - Prepends the block (with a trailing blank line before any other content)
      if the header is missing. Previous version silently dropped it.
    """
    original = milestones_path.read_text(encoding="utf-8") if milestones_path.exists() else ""
    lines = original.splitlines()
    out: list[str] = []
    in_phase = False
    written = False
    for line in lines:
        if line.strip() == "## Current Phase":
            in_phase = True
            written = True
            out.extend(replacement_lines)
            continue
        if in_phase and line.startswith("## ") and line.strip() != "## Current Phase":
            in_phase = False
            out.append(line)
            continue
        if not in_phase:
            out.append(line)
    if not written:
        header_idx = 0
        for i, line in enumerate(out):
            if line.startswith("# "):
                header_idx = i + 1
                break
        prefix, suffix = out[:header_idx], out[header_idx:]
        if prefix and prefix[-1] != "":
            prefix.append("")
        out = prefix + replacement_lines + suffix
    # Keep a trailing blank line so subsequent `append` calls produce
    # a blank separator line before their own `## ` section header.
    milestones_path.write_text("\n".join(out).rstrip() + "\n\n", encoding="utf-8")


def rewrite_role_gates(progress_path: Path, status: dict) -> None:
    """Replace or insert the top-level `## Role Gates` summary in 01-progress.md."""
    original = progress_path.read_text(encoding="utf-8") if progress_path.exists() else ""
    replacement = ["## Role Gates", "", *_render_role_evidence(status).rstrip().splitlines(), ""]
    lines = original.splitlines()
    out: list[str] = []
    in_role_gates = False
    written = False
    for line in lines:
        if line.strip() == "## Role Gates":
            in_role_gates = True
            written = True
            out.extend(replacement)
            continue
        if in_role_gates and line.startswith("## ") and line.strip() != "## Role Gates":
            in_role_gates = False
            out.append(line)
            continue
        if not in_role_gates:
            out.append(line)
    if not written:
        insert_at = len(out)
        for i, line in enumerate(out):
            if line.strip() == "## Milestone History":
                insert_at = i
                break
        out = out[:insert_at] + replacement + out[insert_at:]
    progress_path.write_text("\n".join(out).rstrip() + "\n\n", encoding="utf-8")


def append_ledger(target: Path, event: str, detail: str, covers: list[str] | None = None) -> None:
    path = target / LEDGER_FILE
    if not path.exists():
        path.write_text(FILES[EXECUTION_LOG_FILE], encoding="utf-8")
    covers_line = f"\n- Covers: {', '.join(covers)}" if covers else ""
    with path.open("a", encoding="utf-8") as f:
        f.write(
            f"### {utc_now()} - {event}\n\n"
            f"- Detail: {detail}{covers_line}\n\n"
        )


def current_phase_block(status: str, focus: str, next_gate: str) -> list[str]:
    return [
        "## Current Phase",
        "",
        f"- Status: {status}",
        f"- Current focus: {focus}",
        f"- Next gate: {next_gate}",
        "",
    ]


def is_template_unchanged(path: Path, default: str) -> bool:
    if not path.exists():
        return True
    return path.read_text(encoding="utf-8").strip() == default.strip()


def backup_if_edited(path: Path, default: str) -> Path | None:
    if path.exists() and not is_template_unchanged(path, default):
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        return backup
    return None


def replace_markdown_section(text: str, heading: str, content: str, append: bool, end_heading: str | tuple[str, ...] | None = None) -> str:
    """Replace or append to a top-level bundle section without disturbing siblings."""
    if isinstance(end_heading, tuple):
        stop = r"^(?:" + "|".join(re.escape(item) for item in end_heading) + r")\s*$"
    elif end_heading == NEXT_TOP_LEVEL_HEADING:
        stop = r"^##\s+\S.*$"
    else:
        stop = rf"^{re.escape(end_heading)}\s*$" if end_heading else r"\Z"
    pattern = re.compile(rf"(?ms)^{re.escape(heading)}\s*\n(?P<body>.*?)(?={stop})")
    match = pattern.search(text)
    normalized = content.rstrip() + "\n"
    if not match:
        prefix = text.rstrip()
        return (prefix + "\n\n" if prefix else "") + heading + "\n\n" + normalized
    existing_body = match.group("body")
    if append:
        body = existing_body.rstrip()
        replacement_body = (body + "\n\n" if body else "") + normalized
    else:
        replacement_body = "\n" + normalized
    return text[: match.start("body")] + replacement_body + text[match.end("body") :]


def update_section_end_heading(file_key: str, content: str) -> str | tuple[str, ...] | None:
    end_heading = SECTION_END_HEADINGS[file_key]
    if file_key == "requirements" and re.search(
        r"^## (?:Intake Gate|Controlled Exploration|Task Classification|Acceptance Matrix)\s*$",
        content,
        re.MULTILINE,
    ):
        return "## Design"
    if file_key == "design":
        return NEXT_TOP_LEVEL_HEADING
    return end_heading


def read_content_arg(content: str | None, content_file: str | None) -> str:
    if content is not None and content_file is not None:
        raise SystemExit("Pass either --content or --content-file, not both.")
    if content_file is not None:
        return Path(content_file).read_text(encoding="utf-8").lstrip("\ufeff")
    if content is None:
        raise SystemExit("Provide --content or --content-file.")
    return content.lstrip("\ufeff")


# ---------- subcommands ----------

def init_bundle(root: Path, slug: str, title: str, idea: str, unique: bool, set_current: bool) -> Path:
    if not _is_ascii(title) or not _is_ascii(idea):
        raise SystemExit("init title and idea must be English-only ASCII text. Summarize non-English user input in English before writing the bundle.")
    lock_context = current_lock(root) if set_current else nullcontext()
    with lock_context:
        return _init_bundle_locked(root, slug, title, idea, unique, set_current)


def _init_bundle_locked(root: Path, slug: str, title: str, idea: str, unique: bool, set_current: bool) -> Path:
    if set_current:
        current = read_current(root)
        if current:
            current_slug = current.get("slug", "")
            current_target = bundle_dir(root, current_slug)
            if not current_target.exists() or not state_exists(current_target):
                raise SystemExit(
                    "init refused because .idea-to-code/current.json points to a missing or invalid bundle. "
                    "Inspect current status and clear or repair it explicitly."
                )
            current_status = read_status(current_target)
            if current_status.get("state") not in {"completed", "closed"}:
                raise SystemExit(
                    f"init refused because active bundle '{current_slug}' is not closed. "
                    "Classify the user input, then continue the active bundle or archive it before starting a new one."
                )
    slug = timestamped_slug(slug) if unique else normalize_slug(slug)
    slug = unique_bundle_slug(root, slug)
    target = bundle_dir(root, slug)
    target.mkdir(parents=True, exist_ok=True)
    created_at = utc_now()
    for filename, template in FILES.items():
        ensure_file(
            target / filename,
            render_template(
                template,
                title=title,
                slug=slug,
                created_at=created_at,
                idea_body=idea or "-",
                acceptance_matrix_header=acceptance_matrix_header(),
            ),
        )
    status_path = state_path(target)
    if not status_path.exists():
        status = {
            "schema_version": SCHEMA_VERSION,
            "title": title,
            "slug": slug,
            "created_at_utc": created_at,
            "updated_at_utc": created_at,
            "state": "in_progress",
            "phase": "planning",
            "implementation_ready": False,
            "exploration_output_required": False,
            "exploration_output_id": None,
            "exploration_output_plan_revision": None,
            "exploration_output_at_utc": None,
            "ready_task_output_required": False,
            "ready_task_output_id": None,
            "ready_task_output_plan_revision": None,
            "ready_task_output_at_utc": None,
            "current_focus": "",
            "next_gate": "",
            "finalized_at_utc": None,
            "milestones": [],
            "blocks": [],
            "requirements": [],
            "plan_revision": 0,
            "event_sequence": 0,
            "last_verified_event_sequence": None,
            "last_verify_ok": False,
            "last_verified_plan_revision": None,
            "user_input_decisions": [
                {
                    "timestamp_utc": created_at,
                    "summary": idea or title,
                    "classification": "continue",
                    "rationale": "Initial idea created the active delivery bundle.",
                    "action": "Initialized bundle and entered planning.",
                    "changes_plan": True,
                    "plan_revision": 0,
                }
            ],
            "pending_plan_update": True,
            "role_evidence": {role: [] for role in ROLE_NAMES},
            "gate_status": None,
            "decision": None,
        }
        write_status(target, status)
    if set_current:
        write_current(root, slug, "planning")
    append_ledger(target, "init", f"Bundle initialized for title '{title}'")
    return target


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def quickstart_ineligibility_reason(
    title: str,
    idea: str,
    file_path: str,
    task: str,
    verification: str,
) -> str | None:
    text = " ".join([title, idea, file_path, task, verification])
    reasons: list[str] = []
    if re.search(r"[,;]", file_path):
        reasons.append("multi-file work needs structured planning")
    for pattern, reason in QUICKSTART_INELIGIBLE_PATTERNS:
        if pattern.search(text):
            reasons.append(reason)
    if not reasons:
        return None
    return "; ".join(sorted(set(reasons)))


def quickstart_bundle(
    root: Path,
    slug: str,
    title: str,
    idea: str,
    file_path: str,
    task: str,
    verification: str,
    unique: bool,
) -> tuple[Path, list[str]]:
    if not all(_is_ascii(value) for value in [slug, title, idea, file_path, task, verification]):
        raise SystemExit("quickstart arguments must be English-only ASCII text.")
    for label, value in {
        "title": title,
        "idea": idea,
        "file": file_path,
        "task": task,
        "verification": verification,
    }.items():
        if _weak_text_value(value, min_len=5):
            raise SystemExit(f"quickstart --{label} is too vague.")
    ineligible = quickstart_ineligibility_reason(title, idea, file_path, task, verification)
    if ineligible:
        raise SystemExit(
            "quickstart refused - task is not eligible for quickstart: "
            f"{ineligible}. Use init plus structured requirements, design, implementation ready, "
            "role evidence, validation, review, and closeout instead."
        )
    if not re.search(r"\b(real-product-path|mock-only|fixture-only|source-only|dom-only|manual-inspection|unverified)\b", verification, re.I):
        verification = f"source-only {verification}"

    target = init_bundle(root, slug, title, idea, unique, True)
    actual_slug = target.name
    created_at = utc_now()
    matrix_task = _markdown_table_cell(task)
    matrix_file_path = _markdown_table_cell(file_path)
    content = f"""# Idea

- Title: {title}
- Slug: {actual_slug}
- Created At (UTC): {created_at}

## Original Idea

{idea}

## Requirements

- REQ-1: {task}

## Intake Gate

- Understanding: {idea}
- Assumptions: This is a clear, low-risk, single-slice task suitable for quickstart.
- Acceptance Criteria: {task}
- Need Confirmation: no
- Confirmation Reason: Quickstart is limited to clear low-risk work with concrete acceptance.

## Controlled Exploration

- Exploration Needed: no
- Trigger: Quickstart is limited to clear, low-risk, single-slice work with one direct implementation path.
- Constraints:
  - Keep the change scoped to `{file_path}`.
- Planned Scope:
  - Required Now: TASK-1 / REQ-1 scoped edit to `{file_path}`.
  - Deferred: Broad refactors and unrelated edits.
  - What READY Will Cover: TASK-1 / REQ-1 only.
- Options Considered:
  - Not required for this quickstart task.
- Decision:
  - Chosen option: Use the direct scoped edit described in TASK-1.
  - Decision reason: No architecture, confirmation, or user-visible behavior fork requires option exploration.
  - Rejected options: Broad refactors and unrelated edits.
  - Unverified items: none.

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Quickstart creates a tracked one-slice implementation path.

## Acceptance Matrix

{acceptance_matrix_header()}
| REQ-1 | The requested small scoped change is the user outcome. | `{matrix_file_path}` contains the requested change after implementation. | Unrelated edits outside `{matrix_file_path}` are not accepted. | Broad refactors and behavior changes outside the requested file are non-goals. | {matrix_task} | Unrelated edits outside `{matrix_file_path}` are not accepted. | The change remains concise and scoped to the requested file. | Repository file content persists after edit. | User can revert the small file change if needed. | Validation reports whether the expected text/change is present. | The diff and verification output show the result. | `{matrix_file_path}` is the affected product path. | source-only |

## Design

Use the smallest direct edit to `{file_path}` that satisfies REQ-1. Do not refactor unrelated content.

## Implementation Plan

Gate Status: READY

### TASK-1: {task}

Status: pending

Files:
- {file_path}

Execution Details:
- {task}

Done Criteria:
- `{file_path}` contains the requested scoped update and no unrelated edits.

Planned Verification:
- {verification}
"""
    (target / IDEA_FILE).write_text(content, encoding="utf-8")
    problems = implementation_gate_problems(target, ignore_pending_plan_update=True)
    problems.extend(_acceptance_matrix_problems(content, [{"id": "REQ-1", "state": "open"}]))
    if problems:
        raise SystemExit("quickstart generated an invalid ready bundle:\n  - " + "\n  - ".join(problems))
    with bundle_lock(target):
        status = read_status(target)
        status["requirements"] = [
            {
                "id": "REQ-1",
                "description": task,
                "type": "functional",
                "created_at_utc": utc_now(),
                "state": "open",
            }
        ]
        status["plan_revision"] = int(status.get("plan_revision", 0)) + 1
        status["pending_plan_update"] = False
        status["pending_plan_update_sections"] = []
        status["implementation_ready"] = True
        status["phase"] = "ready_to_implement"
        exploration_id, _ = _record_exploration_output(target, actual_slug, status)
        output_id, ready_output_lines = _record_ready_output(target, actual_slug, status)
        status["current_focus"] = f"quickstart ready; exploration_output={exploration_id}; ready_output={output_id}"
        status.setdefault("role_evidence", {role: [] for role in ROLE_NAMES})
        status["role_evidence"].setdefault("planner", []).append(
            {
                "timestamp_utc": utc_now(),
                "event_sequence": _next_event_sequence(status),
                "role": "planner",
                "evidence": "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 implementation plan ready through quickstart.",
                "covers": ["REQ-1"],
                "plan_revision": status["plan_revision"],
            }
        )
        write_status(target, status)
        append_ledger(target, "quickstart", f"Quickstart generated ready single-task bundle; exploration_output={exploration_id}; ready_output={output_id}")
    write_current(root, actual_slug, "ready_to_implement")
    return target, ready_output_lines


def _parse_ids(raw: str | list[str] | None) -> list[str]:
    if not raw:
        return []
    values = raw if isinstance(raw, list) else [raw]
    seen: set[str] = set()
    parsed: list[str] = []
    for value in values:
        for item in str(value).split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                parsed.append(cleaned)
    return parsed


def _combined_file_args(files: list[str] | None, file_groups: list[list[str]] | None) -> list[str]:
    combined: list[str] = []
    seen: set[str] = set()
    for item in files or []:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            combined.append(cleaned)
            seen.add(cleaned)
    for group in file_groups or []:
        for item in group:
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                combined.append(cleaned)
                seen.add(cleaned)
    return combined


def checkpoint_bundle(
    root: Path,
    slug: str,
    milestone: str,
    delivered: str,
    verified: str,
    next_step: str,
    focus: str,
    gate: str,
    gate_status: str | None,
    covers: list[str],
) -> Path:
    values = [milestone, delivered, verified, next_step, focus, gate]
    if gate_status:
        values.append(gate_status)
    if not all(_is_ascii(value) for value in values):
        raise SystemExit("checkpoint arguments must be English-only ASCII text.")
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        timestamp = utc_now()
        status = read_status(target)
        if not status.get("implementation_ready") or implementation_gate_problems(target):
            raise SystemExit(
                "checkpoint refused - implementation gate is not READY. "
                f"Fill {IMPLEMENTATION_FILE} and run 'implementation ready' before recording executed work."
            )
        ready_output_problem = _ready_output_problem(status, target)
        if ready_output_problem:
            raise SystemExit("checkpoint refused - " + ready_output_problem)
        known_ids = {r["id"] for r in status.get("requirements", [])}
        unknown = [c for c in covers if c not in known_ids]
        if unknown and known_ids:
            raise SystemExit(
                "checkpoint --covers references unknown requirement IDs: "
                + ", ".join(unknown)
                + "\nAdd them first with 'requirement add' or drop them from --covers."
            )

        gate_suffix = f" (gate: {gate_status})" if gate_status else ""
        covers_line = f"- Covers: {', '.join(covers)}\n" if covers else ""
        (target / MILESTONES_FILE).open("a", encoding="utf-8").write(
            f"## {milestone}{gate_suffix}\n\n"
            f"- Timestamp: {timestamp}\n"
            f"- Delivered: {delivered}\n"
            f"- Verified: {verified}\n"
            f"- Next: {next_step}\n"
            f"{covers_line}"
            f"\n"
        )
        (target / VERIFICATION_FILE).open("a", encoding="utf-8").write(
            f"### Verification - {milestone}{gate_suffix}\n\n"
            f"- Timestamp: {timestamp}\n"
            f"- Verified: {verified}\n"
            f"{covers_line}"
            f"\n"
        )

        status["current_focus"] = focus
        status["next_gate"] = gate
        event_sequence = _next_event_sequence(status)
        status["milestones"].append(
            {
                "name": milestone,
                "timestamp_utc": timestamp,
                "event_sequence": event_sequence,
                "delivered": delivered,
                "verified": verified,
                "next": next_step,
                "gate_status": gate_status,
                "covers": covers,
            }
        )
        _update_master_backlog_coverage(status, covers, milestone)
        status["last_verify_ok"] = False
        status["last_verified_plan_revision"] = None
        write_status(target, status)
        append_ledger(target, "checkpoint", f"{milestone}: {delivered}; verified: {verified}; gate: {gate_status}", covers)

        rewrite_current_phase(
            target / MILESTONES_FILE,
            current_phase_block("in_progress", focus, gate),
        )
    return target


def ensure_active_bundle(
    root: Path,
    slug: str,
    allow_paused: bool = False,
    allow_blocked: bool = False,
) -> Path:
    target = ensure_bundle(root, slug)
    current = read_current(root)
    if not current:
        raise SystemExit("No active .idea-to-code/current.json exists. Use current set before mutating a bundle.")
    active_slug = current.get("slug")
    if active_slug != slug:
        raise SystemExit(f"Refusing to mutate non-current bundle '{slug}'. Active bundle is '{active_slug}'.")
    status = read_status(target)
    if status.get("state") == "paused" and not allow_paused:
        raise SystemExit("Bundle is paused. Use current resume with a reason before mutating it.")
    if status.get("state") == "blocked" and not allow_blocked:
        raise SystemExit("Bundle is blocked. Resolve the dependency and run unblock before mutating it.")
    if status.get("state") in {"completed", "closed"}:
        raise SystemExit(f"Bundle is already {status.get('state')}; start or set a new active bundle before mutating.")
    return target


def _unresolved_block_indexes(status: dict) -> list[int]:
    return [
        index
        for index, block in enumerate(status.get("blocks", []))
        if "resolved_at_utc" not in block
    ]


def block_bundle(root: Path, slug: str, reason: str, need: str) -> Path:
    if not _is_ascii(reason) or not _is_ascii(need):
        raise SystemExit("block reason and need must be English-only ASCII text.")
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    with bundle_lock(target):
        timestamp = utc_now()
        status = read_status(target)
        status["state"] = "blocked"
        status["blocks"].append(
            {"timestamp_utc": timestamp, "reason": reason, "need": need}
        )
        write_status(target, status)
        append_ledger(target, "block", f"Blocked: {reason}; need: {need}")

        (target / MILESTONES_FILE).open("a", encoding="utf-8").write(
            f"## Blocker at {timestamp}\n\n"
            f"- Reason: {reason}\n"
            f"- Needed to proceed: {need}\n\n"
        )
        rewrite_current_phase(
            target / MILESTONES_FILE,
            current_phase_block("blocked", f"BLOCKED: {reason}", f"unblock: {need}"),
        )
    return target


def unblock_bundle(root: Path, slug: str, note: str) -> Path:
    if not _is_ascii(note):
        raise SystemExit("unblock note must be English-only ASCII text.")
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    with bundle_lock(target):
        timestamp = utc_now()
        status = read_status(target)
        unresolved_indexes = _unresolved_block_indexes(status)
        if status.get("state") != "blocked" or not unresolved_indexes:
            raise SystemExit("unblock refused: current bundle has no unresolved blocker.")
        status["blocks"][unresolved_indexes[-1]]["resolved_at_utc"] = timestamp
        status["blocks"][unresolved_indexes[-1]]["resolution"] = note
        remaining_unresolved = [
            block
            for block in status.get("blocks", [])
            if "resolved_at_utc" not in block
        ]
        if remaining_unresolved:
            latest = remaining_unresolved[-1]
            status["state"] = "blocked"
            phase_status = "blocked"
            phase_focus = f"BLOCKED: {latest.get('reason', '')}"
            phase_gate = f"unblock: {latest.get('need', '')}"
        else:
            status["state"] = "in_progress"
            phase_status = "in_progress"
            phase_focus = status.get("current_focus") or ""
            phase_gate = status.get("next_gate") or ""
        write_status(target, status)
        append_ledger(target, "unblock", f"Unblocked: {note}")

        (target / MILESTONES_FILE).open("a", encoding="utf-8").write(
            f"## Unblocked at {timestamp}\n\n- Resolution: {note}\n\n"
        )
        rewrite_current_phase(
            target / MILESTONES_FILE,
            current_phase_block(phase_status, phase_focus, phase_gate),
        )
    return target


def update_section(
    root: Path,
    slug: str,
    file_key: str,
    content: str,
    append: bool,
) -> Path:
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        filename = EDITABLE_SECTIONS[file_key]
        path = target / filename
        heading = SECTION_HEADINGS[file_key]
        end_heading = update_section_end_heading(file_key, content)
        existing = path.read_text(encoding="utf-8") if path.exists() else render_template(FILES[filename])
        if append:
            path.write_text(
                replace_markdown_section(existing, heading, content, append=True, end_heading=end_heading),
                encoding="utf-8",
            )
        else:
            path.write_text(
                replace_markdown_section(existing, heading, content, append=False, end_heading=end_heading),
                encoding="utf-8",
            )
        status = read_status(target)
        if file_key in {"requirements", "design", "implementation"}:
            _reset_ready_for_plan_change(
                status,
                "implementation plan changed; rerun implementation ready",
            )
            _clear_pending_plan_section(status, file_key)
        write_status(target, status)
    return path


def user_input_record(
    root: Path,
    slug: str,
    summary: str,
    classification: str,
    rationale: str,
    action: str,
    changes_plan: str,
) -> Path:
    classification = classification.strip().lower()
    if classification not in USER_INPUT_CLASSIFICATIONS:
        raise SystemExit(
            f"Unknown user input classification: {classification}. "
            f"Expected one of: {', '.join(USER_INPUT_CLASSIFICATIONS)}"
        )
    changes_plan_bool = changes_plan.strip().lower() == "yes"
    for label, value in {
        "summary": summary,
        "rationale": rationale,
        "action": action,
    }.items():
        if not _is_ascii(value):
            raise SystemExit(f"{label} must be English-only ASCII text.")
        if _weak_text_value(value, min_len=8):
            raise SystemExit(f"{label} is too vague for a user input decision record")
    if classification in PLAN_CHANGING_CLASSIFICATIONS and not changes_plan_bool:
        raise SystemExit(f"{classification} user input must use --changes-plan yes")
    if classification in {"new-task", "status", "pause", "no-op"} and changes_plan_bool:
        raise SystemExit(f"{classification} user input must not use --changes-plan yes")

    target = ensure_active_bundle(root, slug, allow_blocked=classification in {"new-task", "status", "pause", "no-op"})
    with bundle_lock(target):
        status = read_status(target)
        entry = {
            "timestamp_utc": utc_now(),
            "summary": summary,
            "classification": classification,
            "rationale": rationale,
            "action": action,
            "changes_plan": changes_plan_bool,
            "plan_revision": status.get("plan_revision", 0),
        }
        status.setdefault("user_input_decisions", []).append(entry)
        status["last_user_input_decision"] = entry
        if changes_plan_bool:
            _reset_ready_for_plan_change(
                status,
                "user input changed plan; update requirements/design/implementation",
                PLAN_UPDATE_SECTIONS,
            )
        write_status(target, status)
        append_ledger(target, "user-input", f"{classification}: {summary}; action: {action}", [])
    return target


def _task_section_blocks(text: str) -> list[tuple[str, dict[str, str]]]:
    task_matches = list(re.finditer(r"^#{2,3} ((?:TASK|IMP)-\d+:[^\n]*)", text, re.MULTILINE))
    section_names = "|".join(re.escape(section) for section in TASK_REQUIRED_SECTIONS)
    blocks: list[tuple[str, dict[str, str]]] = []
    for index, match in enumerate(task_matches):
        start = match.end()
        end = task_matches[index + 1].start() if index + 1 < len(task_matches) else len(text)
        block = text[start:end]
        task_name = match.group(1).strip()
        sections: dict[str, str] = {}
        for required in TASK_REQUIRED_SECTIONS:
            section_match = re.search(
                rf"^{re.escape(required)}\s*(?P<inline>[^\n]*)\n(?P<body>.*?)(?=^(?:{section_names})|^#{{2,3}} (?:TASK|IMP)-\d+:|\Z)",
                block,
                re.MULTILINE | re.DOTALL,
            )
            if not section_match:
                continue
            candidate_lines = []
            inline = section_match.group("inline").strip()
            if inline:
                candidate_lines.append(inline)
            candidate_lines.extend(line.rstrip() for line in section_match.group("body").splitlines())
            while candidate_lines and not candidate_lines[-1].strip():
                candidate_lines.pop()
            sections[required] = "\n".join(candidate_lines).strip()
        blocks.append((task_name, sections))
    return blocks


def _task_section_pollution_problems(task_name: str, section: str, value: str) -> list[str]:
    problems: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in TASK_SECTION_RESERVED_HEADINGS:
            problems.append(f"{task_name} {section} contains reserved bundle heading: {line}")
        elif re.match(r"^##\s+(?!TASK-\d+:|IMP-\d+:).+", line):
            problems.append(f"{task_name} {section} contains unexpected top-level heading: {line}")
        if TASK_SECTION_PLACEHOLDER_RE.search(line):
            problems.append(f"{task_name} {section} contains unresolved placeholder: {line}")
    return problems


def _task_sections_quality_problems(task_name: str, sections: dict[str, str]) -> list[str]:
    task_problems: list[str] = []
    for required in TASK_REQUIRED_SECTIONS:
        value = sections.get(required, "")
        if not value:
            task_problems.append(f"{task_name} missing {required}")
            continue
        meaningful = [
            line.strip()
            for line in value.splitlines()
            if line.strip() and not _weak_text_value(line.strip(), min_len=8)
        ]
        if not meaningful:
            task_problems.append(f"{task_name} has empty {required}")
        task_problems.extend(_task_section_pollution_problems(task_name, required, value))
        if required == "Planned Verification:" and not VALIDATION_TYPE_RE.search(value):
            task_problems.append(
                f"{task_name} Planned Verification: missing approved validation type "
                f"({', '.join(VALIDATION_TYPES)})"
            )
    return task_problems


def implementation_gate_problems(target: Path, ignore_pending_plan_update: bool = False) -> list[str]:
    path = target / IMPLEMENTATION_FILE
    if not path.exists():
        return [f"missing: {IMPLEMENTATION_FILE}"]
    text = path.read_text(encoding="utf-8")
    status = read_status(target) if state_exists(target) else {}
    problems: list[str] = _intake_gate_problems(target)
    pending_problem = _pending_plan_update_problem(status)
    if pending_problem and not ignore_pending_plan_update:
        problems.append(f"{STATE_FILE}: {pending_problem}")
    problems.extend(f"{STATE_FILE}: {problem}" for problem in _master_backlog_problems(target, status))
    problems.extend(_controlled_exploration_problems(target))
    if not re.search(r"^Gate Status:\s*READY\s*$", text, re.MULTILINE):
        problems.append(f"{IMPLEMENTATION_FILE}: Gate Status is not READY")
    task_blocks = _task_section_blocks(text)
    if not task_blocks:
        problems.append(f"{IMPLEMENTATION_FILE}: no TASK or IMP items found")
        return problems
    for task_name, sections in task_blocks:
        problems.extend(f"{IMPLEMENTATION_FILE}: {problem}" for problem in _task_sections_quality_problems(task_name, sections))
    return problems


def _task_id_from_name(task_name: str) -> str:
    match = re.match(r"((?:TASK|IMP)-\d+):", task_name)
    return match.group(1) if match else task_name.split(":", 1)[0].strip()


def _task_files_from_section(files_text: str) -> list[str]:
    files: list[str] = []
    for raw_line in files_text.splitlines():
        cleaned = raw_line.strip()
        if not cleaned:
            continue
        cleaned = cleaned.lstrip("-").strip()
        if cleaned and cleaned not in {"...", "<path>", "<paths>"}:
            files.append(cleaned)
    return files


def _implementation_plan_check_payload(target: Path) -> dict[str, Any]:
    path = target / IMPLEMENTATION_FILE
    if not path.exists():
        return {
            "schema": "idea-to-code.implementation-plan-check.v1",
            "ok": False,
            "path": str(path),
            "tasks": [],
            "problems": [f"missing: {IMPLEMENTATION_FILE}"],
        }
    text = path.read_text(encoding="utf-8")
    blocks = _task_section_blocks(text)
    problems: list[str] = []
    tasks: list[dict[str, Any]] = []
    if not blocks:
        problems.append(f"{IMPLEMENTATION_FILE}: no TASK or IMP items found")
    for task_name, sections in blocks:
        task_id = _task_id_from_name(task_name)
        task_problems = _task_sections_quality_problems(task_name, sections)
        files = _task_files_from_section(sections.get("Files:", ""))
        tasks.append({
            "id": task_id,
            "name": task_name,
            "files": files,
            "sections_present": [section for section in TASK_REQUIRED_SECTIONS if sections.get(section)],
            "missing_sections": [section for section in TASK_REQUIRED_SECTIONS if not sections.get(section)],
            "problems": task_problems,
        })
        problems.extend(f"{IMPLEMENTATION_FILE}: {problem}" for problem in task_problems)
    return {
        "schema": "idea-to-code.implementation-plan-check.v1",
        "ok": not problems,
        "path": str(path),
        "task_count": len(tasks),
        "tasks": tasks,
        "problems": problems,
    }


def implementation_plan_check(root: Path, slug: str, json_only: bool) -> int:
    target = ensure_bundle(root, slug)
    payload = _implementation_plan_check_payload(target)
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif payload["ok"]:
        print(f"implementation plan-check: PASS tasks={payload['task_count']}")
        for task in payload["tasks"]:
            print(f"- {task['id']}: files={', '.join(task['files']) if task['files'] else 'none'}")
    else:
        print("implementation plan-check: FAIL")
        for problem in payload["problems"]:
            print(f"- {problem}")
    return 0 if payload["ok"] else 1


def _section_text(text: str, heading: str) -> str | None:
    match = re.search(rf"^{re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    if not match:
        return None
    return match.group(1)


def _controlled_exploration_problems(target: Path) -> list[str]:
    idea_path = target / IDEA_FILE
    if not idea_path.exists():
        return [f"missing: {IDEA_FILE}"]
    text = idea_path.read_text(encoding="utf-8")
    block = _section_text(text, "## Controlled Exploration")
    if block is None:
        return [f"{IDEA_FILE}: missing Controlled Exploration section"]

    problems: list[str] = []
    field = re.search(r"^-\s*Exploration Needed:[ \t]*(.*)$", block, re.MULTILINE)
    if not field:
        problems.append(f"{IDEA_FILE}: Controlled Exploration missing Exploration Needed")
        return problems
    needed = field.group(1).strip().lower()
    if needed not in {"yes", "no"}:
        problems.append(f"{IDEA_FILE}: Exploration Needed must be yes or no")
        return problems

    trigger = re.search(r"^-\s*Trigger:[ \t]*(.*)$", block, re.MULTILINE)
    if not trigger or _weak_text_value(trigger.group(1).strip(), min_len=8):
        problems.append(f"{IDEA_FILE}: Controlled Exploration has weak Trigger")

    planned_scope = _controlled_exploration_subsection(block, "Planned Scope", ("Options Considered", "Decision"))
    if _weak_text_value(planned_scope, min_len=24):
        problems.append(f"{IDEA_FILE}: Controlled Exploration missing structured Planned Scope")
    else:
        for label in ("Required Now", "Deferred", "What READY Will Cover"):
            value = _field_value(planned_scope, label)
            if _weak_text_value(value, min_len=4):
                problems.append(f"{IDEA_FILE}: Controlled Exploration Planned Scope missing concrete {label}")

    if needed == "no":
        return problems

    options = re.search(r"^-\s*Options Considered:[ \t]*$([\s\S]*?)(?=^-\s*Decision:|\Z)", block, re.MULTILINE)
    decision = re.search(r"^-\s*Decision:[ \t]*$([\s\S]*?)\Z", block, re.MULTILINE)
    if not options or _weak_text_value(options.group(1).strip(), min_len=24):
        problems.append(f"{IDEA_FILE}: Exploration Needed is yes but Options Considered is missing or weak")
    if not decision or _weak_text_value(decision.group(1).strip(), min_len=24):
        problems.append(f"{IDEA_FILE}: Exploration Needed is yes but Decision is missing or weak")
    else:
        decision_block = decision.group(1)
        for label in ("Chosen option", "Decision reason"):
            item = re.search(
                rf"^\s*-\s*{re.escape(label)}:[ \t]*(?P<inline>[^\n]*)"
                rf"(?P<body>.*?)(?=^\s*-\s*(?:Chosen option|Decision reason|Rejected options|Unverified items):|\Z)",
                decision_block,
                re.MULTILINE | re.DOTALL,
            )
            if not item:
                problems.append(f"{IDEA_FILE}: Controlled Exploration Decision missing concrete {label}")
                continue
            value_lines = [item.group("inline").strip()]
            value_lines.extend(line.strip() for line in item.group("body").splitlines())
            value = " ".join(line for line in value_lines if line)
            if _weak_text_value(value, min_len=8):
                problems.append(f"{IDEA_FILE}: Controlled Exploration Decision missing concrete {label}")
    return problems


def _intake_gate_problems(target: Path) -> list[str]:
    idea_path = target / IDEA_FILE
    if not idea_path.exists():
        return [f"missing: {IDEA_FILE}"]
    text = idea_path.read_text(encoding="utf-8")
    match = re.search(r"^## Intake Gate\s*$([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    if not match:
        return [f"{IDEA_FILE}: missing Intake Gate section"]
    block = match.group(1)
    problems: list[str] = []
    for label in ("Understanding", "Assumptions", "Acceptance Criteria", "Need Confirmation", "Confirmation Reason"):
        field = re.search(rf"^-\s*{re.escape(label)}:\s*(.*)$", block, re.MULTILINE)
        if not field:
            problems.append(f"{IDEA_FILE}: Intake Gate missing {label}")
            continue
        value = field.group(1).strip()
        if label == "Need Confirmation":
            lowered = value.lower()
            if lowered not in {"yes", "no"}:
                problems.append(f"{IDEA_FILE}: Need Confirmation must be yes or no")
            elif lowered == "yes":
                problems.append(f"{IDEA_FILE}: Need Confirmation is yes; get user confirmation or update Intake Gate before implementation ready")
        elif _weak_text_value(value, min_len=8):
            problems.append(f"{IDEA_FILE}: Intake Gate has weak {label}: {value or '(empty)'}")
    return problems


def _field_value(block: str, label: str) -> str:
    match = re.search(rf"^\s*-\s*{re.escape(label)}:[ \t]*(.*)$", block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _controlled_exploration_subsection(block: str, label: str, next_labels: tuple[str, ...]) -> str:
    next_pattern = "|".join(re.escape(item) for item in next_labels)
    match = re.search(
        rf"^-\s*{re.escape(label)}:[ \t]*$([\s\S]*?)(?=^-\s*(?:{next_pattern}):|\Z)",
        block,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else ""


def _intake_gate_values(target: Path) -> dict[str, str]:
    text = (target / IDEA_FILE).read_text(encoding="utf-8")
    block = _section_text(text, "## Intake Gate") or ""
    return {
        "understanding": _field_value(block, "Understanding"),
        "assumptions": _field_value(block, "Assumptions"),
        "acceptance_criteria": _field_value(block, "Acceptance Criteria"),
        "need_confirmation": _field_value(block, "Need Confirmation").lower(),
        "confirmation_reason": _field_value(block, "Confirmation Reason"),
    }


def _controlled_exploration_values(target: Path) -> dict[str, str]:
    text = (target / IDEA_FILE).read_text(encoding="utf-8")
    block = _section_text(text, "## Controlled Exploration") or ""
    planned_scope_block = _controlled_exploration_subsection(block, "Planned Scope", ("Options Considered", "Decision"))
    options_match = re.search(r"^-\s*Options Considered:[ \t]*$([\s\S]*?)(?=^-\s*Decision:|\Z)", block, re.MULTILINE)
    decision_match = re.search(r"^-\s*Decision:[ \t]*$([\s\S]*?)\Z", block, re.MULTILINE)
    decision_block = decision_match.group(1) if decision_match else ""
    return {
        "needed": _field_value(block, "Exploration Needed").lower(),
        "trigger": _field_value(block, "Trigger"),
        "required_now": _field_value(planned_scope_block, "Required Now"),
        "deferred": _field_value(planned_scope_block, "Deferred"),
        "ready_coverage": _field_value(planned_scope_block, "What READY Will Cover"),
        "options": (options_match.group(1).strip() if options_match else ""),
        "chosen_option": _field_value(decision_block, "Chosen option"),
        "decision_reason": _field_value(decision_block, "Decision reason"),
        "rejected_options": _field_value(decision_block, "Rejected options"),
        "unverified_items": _field_value(decision_block, "Unverified items"),
    }


ROLE_LABELS = {"planner", "implementer", "validator", "reviewer", "closer"}
SOURCE_LABELS = {"agent", "subagent"}


def _visibility_prefix(profile: str | None = None, role: str = "planner", source: str = "agent") -> str:
    if not profile:
        base = "[idea-to-code]"
    else:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", profile):
            raise SystemExit(
                "--profile must use 1-64 characters: letters, numbers, underscore, or hyphen; "
                "it is display-only and must not contain path or shell characters."
            )
        base = f"[idea-to-code/{profile}]"
    normalized_role = role.strip().lower()
    if normalized_role not in ROLE_LABELS:
        raise SystemExit("--role must be one of: planner, implementer, validator, reviewer, closer.")
    normalized_source = source.strip().lower()
    if normalized_source not in SOURCE_LABELS:
        raise SystemExit("--source must be one of: agent, subagent.")
    return f"{base}[{normalized_role.title()}/{normalized_source}]"


def _reject_ready_role_source_override(role: str, source: str) -> None:
    if role.strip().lower() != "planner" or source.strip().lower() != "agent":
        raise SystemExit("implementation READY output is always a Planner/agent gate; use --profile only for display labels.")


def _profile_prefix(profile: str | None = None) -> str:
    if not profile:
        return "[idea-to-code]"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", profile):
        raise SystemExit(
            "--profile must use 1-64 characters: letters, numbers, underscore, or hyphen; "
            "it must start with a letter or number."
        )
    return f"[idea-to-code/{profile}]"


def _plan_fingerprint(target: Path) -> str:
    path = target / IDEA_FILE
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _plan_fingerprint_problem(
    target: Path | None,
    status: dict,
    output_name: str,
    state_key: str,
    refresh_command: str,
) -> str | None:
    if target is None:
        return None
    recorded = status.get(state_key)
    if not recorded:
        return None
    current = _plan_fingerprint(target)
    if recorded != current:
        return (
            f"{output_name} stale because 00-idea.md changed after it was generated; "
            f"run {refresh_command} and send the refreshed output to the user before continuing."
        )
    return None


def _exploration_output_problem(status: dict, target: Path | None = None) -> str | None:
    if not status.get("exploration_output_required"):
        return (
            "Exploration output required: run exploration render --root <root> --slug <slug> "
            "and send its output to the user before implementation READY."
        )
    plan_revision = int(status.get("plan_revision", 0))
    output_id = status.get("exploration_output_id")
    output_revision = status.get("exploration_output_plan_revision")
    if not output_id or output_revision != plan_revision:
        return (
            "Exploration output refresh required: run exploration render --root <root> --slug <slug> "
            "and send its output to the user before implementation READY."
        )
    fingerprint_problem = _plan_fingerprint_problem(
        target,
        status,
        "Exploration output",
        "exploration_output_plan_fingerprint",
        "exploration render --root <root> --slug <slug>",
    )
    if fingerprint_problem:
        return fingerprint_problem
    return None


def _format_exploration_output(
    slug: str,
    title: str,
    output_id: str,
    intake: dict[str, str],
    exploration: dict[str, str],
    profile: str | None = None,
) -> list[str]:
    need_confirmation = intake.get("need_confirmation") == "yes"
    heading = "Confirmation Required" if need_confirmation else "Exploration Result"
    lines = [
        f"{_visibility_prefix(profile, 'planner', 'agent')} {heading} | Bundle: {slug}",
        "",
        f"Display Layer: {'Exploration Result' if not need_confirmation else 'Exploration Decision Request'}",
        "Next Layer: READY Focus after this output is visible; Full Plan only on --full-plan.",
        "",
        f"Restated user goal: {title}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {output_id}",
        "",
        "User Goal:",
        f"- {intake.get('understanding') or title}",
        "",
        "Acceptance Target:",
        f"- {intake.get('acceptance_criteria') or 'See Intake Gate acceptance criteria.'}",
        "",
        "Exploration:",
        f"- Needed: {exploration.get('needed') or 'unknown'}",
        f"- Reason: {exploration.get('trigger') or intake.get('confirmation_reason') or 'See Controlled Exploration.'}",
        "",
        "Planned Scope:",
        f"- Required Now: {exploration.get('required_now') or 'See current requirements and implementation plan.'}",
        f"- Deferred: {exploration.get('deferred') or 'See Controlled Exploration decision and acceptance notes.'}",
        f"- What READY Will Cover: {exploration.get('ready_coverage') or 'TASK/REQ items in the current implementation plan after this exploration output is visible.'}",
        "",
    ]
    if need_confirmation:
        lines.extend([
            "Decision Options:",
            exploration.get("options") or "- See Controlled Exploration options in 00-idea.md.",
            "",
            "Recommended Option:",
            f"- {exploration.get('chosen_option') or 'See Controlled Exploration decision.'}",
            "",
            "Why This Option:",
            f"- {exploration.get('decision_reason') or 'See Controlled Exploration decision reason.'}",
            "",
            "Please reply with one of:",
            "- approve",
            "- choose: <option>",
            "- change: <correction>",
            "- explore more: <direction>",
            "- pause",
            "- cancel",
        ])
    else:
        lines.extend([
            "Selected Approach:",
            f"- {exploration.get('chosen_option') or 'Use the direct implementation path recorded in Controlled Exploration.'}",
            "",
            "Why This Approach:",
            f"- {exploration.get('decision_reason') or 'The plan has no unresolved confirmation gate.'}",
            "",
            "Implementation Will Proceed To:",
            "- Implementation Gate READY after this exploration output is visible.",
            "",
            "This is not an approval request; continue unless the user interrupts.",
        ])
    return lines


def _exploration_output_contract_problems(lines: list[str], need_confirmation: bool) -> list[str]:
    text = "\n".join(lines)
    problems: list[str] = []
    if EXPLORATION_OUTPUT_ID_LABEL + ":" not in text:
        problems.append("Exploration output missing EXPLORATION_OUTPUT_ID")
    if "User Goal:" not in text:
        problems.append("Exploration output missing User Goal")
    if "Exploration:" not in text:
        problems.append("Exploration output missing Exploration summary")
    if "Planned Scope:" not in text:
        problems.append("Exploration output missing Planned Scope")
    for required in ("Required Now:", "Deferred:", "What READY Will Cover:"):
        if required not in text:
            problems.append(f"Exploration output missing Planned Scope field {required}")
    if "Display Layer:" not in text or "Next Layer:" not in text:
        problems.append("Exploration output missing display layer guidance")
    if need_confirmation:
        for required in ("Confirmation Required", "Decision Options:", "Recommended Option:", "Please reply with one of:"):
            if required not in text:
                problems.append(f"Confirmation exploration output missing {required}")
    else:
        for required in ("Exploration Result", "Selected Approach:", "Why This Approach:", "Implementation Will Proceed To:"):
            if required not in text:
                problems.append(f"Autonomous exploration output missing {required}")
        if "Please reply with one of:" in text:
            problems.append("Autonomous exploration output must not ask for routine confirmation")
    return problems


def _record_exploration_output(
    target: Path,
    slug: str,
    status: dict,
    profile: str | None = None,
) -> tuple[str, list[str]]:
    problems = _intake_gate_problems(target)
    problems.extend(_controlled_exploration_problems(target))
    blocking = [
        problem for problem in problems
        if "Need Confirmation is yes" not in problem
    ]
    if blocking:
        raise SystemExit("exploration output refused:\n  - " + "\n  - ".join(blocking))
    plan_revision = int(status.get("plan_revision", 0))
    timestamp = utc_now()
    compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
    output_id = f"{slug}-explore-r{plan_revision}-{compact_time}"
    intake = _intake_gate_values(target)
    exploration = _controlled_exploration_values(target)
    need_confirmation = intake.get("need_confirmation") == "yes"
    lines = _format_exploration_output(slug, status.get("title", slug), output_id, intake, exploration, profile)
    output_problems = _exploration_output_contract_problems(lines, need_confirmation)
    if output_problems:
        raise SystemExit("Exploration output contract failed:\n  - " + "\n  - ".join(output_problems))
    status["exploration_output_required"] = True
    status["exploration_output_id"] = output_id
    status["exploration_output_plan_revision"] = plan_revision
    status["exploration_output_plan_fingerprint"] = _plan_fingerprint(target)
    status["exploration_output_at_utc"] = timestamp
    status["exploration_output_event_sequence"] = _next_event_sequence(status)
    status["exploration_output_mode"] = "confirmation-required" if need_confirmation else "autonomous"
    return output_id, lines


def exploration_render(
    root: Path,
    slug: str,
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        status = read_status(target)
        output_id, lines = _record_exploration_output(target, slug, status, profile)
        write_status(target, status)
        append_ledger(target, "exploration-render", f"Exploration output generated/refreshed: {output_id}")
    print("\n".join(lines))
    return 0


def mark_implementation_ready(
    root: Path,
    slug: str,
    profile: str | None = None,
    role: str = "planner",
    source: str = "agent",
    task_filters: list[str] | None = None,
    full_plan: bool = False,
) -> Path:
    _reject_ready_role_source_override(role, source)
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        problems = implementation_gate_problems(target)
        if problems:
            raise SystemExit(
                "implementation gate is not ready:\n  - " + "\n  - ".join(problems)
            )
        status = read_status(target)
        exploration_lines: list[str] = []
        exploration_problem = _exploration_output_problem(status, target)
        if exploration_problem:
            _, exploration_lines = _record_exploration_output(target, slug, status, profile)
        status["phase"] = "ready_to_implement"
        status["pending_plan_update"] = False
        status["pending_plan_update_sections"] = []
        status["implementation_ready"] = True
        output_id, lines = _record_ready_output(target, slug, status, profile, role, source, task_filters, full_plan)
        write_status(target, status)
        append_ledger(target, "implementation-ready", f"Implementation gate marked READY; ready_output={output_id}")
    current = read_current(root)
    if current and current.get("slug") == slug:
        write_current(root, slug, "ready_to_implement")
    if exploration_lines:
        print("\n".join(exploration_lines))
        print()
    print("\n".join(lines))
    return target


def _ready_task_blocks(target: Path) -> list[tuple[str, str]]:
    text = (target / IMPLEMENTATION_FILE).read_text(encoding="utf-8")
    blocks: list[tuple[str, str]] = []
    for task_name, sections in _task_section_blocks(text):
        kept: list[str] = []
        for section in TASK_REQUIRED_SECTIONS:
            kept.append(section)
            value = sections.get(section, "")
            if value:
                kept.extend(value.splitlines())
            kept.append("")
        blocks.append((task_name, "\n".join(kept).strip()))
    return blocks


def _filter_ready_task_blocks(blocks: list[tuple[str, str]], task_filters: list[str] | None) -> list[tuple[str, str]]:
    if not task_filters:
        return blocks
    wanted = {item.strip().upper() for item in task_filters if item.strip()}
    filtered: list[tuple[str, str]] = []
    for task_name, block in blocks:
        task_id = task_name.split(":", 1)[0].strip().upper()
        if task_id in wanted:
            filtered.append((task_name, block))
    missing = sorted(wanted - {name.split(":", 1)[0].strip().upper() for name, _ in filtered})
    if missing:
        raise SystemExit(f"READY task filter did not match: {', '.join(missing)}")
    return filtered


def _default_ready_task_blocks(blocks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return blocks[:1]


def _task_files_for_id(target: Path, task_id: str) -> list[str]:
    wanted = task_id.strip().upper()
    text = (target / IMPLEMENTATION_FILE).read_text(encoding="utf-8")
    for task_name, sections in _task_section_blocks(text):
        if task_name.split(":", 1)[0].strip().upper() != wanted:
            continue
        files_section = sections.get("Files:", "")
        files: list[str] = []
        for line in files_section.splitlines():
            item = line.strip()
            if item.startswith("- "):
                item = item[2:].strip()
            item = item.strip("`").strip()
            if item:
                files.append(item)
        return files
    raise SystemExit(f"READY task filter did not match: {wanted}")


def _normalize_guard_file(path_text: str) -> str:
    return path_text.strip().strip("`").replace("\\", "/").lower()


def _covered_req_hint(task_name: str) -> str | None:
    match = re.match(r"(TASK|IMP)-(\d+)\b", task_name.strip(), re.IGNORECASE)
    if not match:
        return None
    return f"REQ-{match.group(2)}"


def _ready_output_problem(status: dict, target: Path | None = None) -> str | None:
    if not status.get("ready_task_output_required"):
        return None
    plan_revision = int(status.get("plan_revision", 0))
    output_id = status.get("ready_task_output_id")
    output_revision = status.get("ready_task_output_plan_revision")
    if not output_id or output_revision != plan_revision:
        return (
            "READY output refresh required: run implementation show-ready --root <root> --slug <slug> "
            "and send its output to the user before implementation evidence."
        )
    fingerprint_problem = _plan_fingerprint_problem(
        target,
        status,
        "READY output",
        "ready_task_output_plan_fingerprint",
        "implementation ready --root <root> --slug <slug>",
    )
    if fingerprint_problem:
        return fingerprint_problem
    return None


def _ready_recovery_payload(target: Path, slug: str, task_id: str | None = None) -> dict[str, Any]:
    status = read_status(target)
    gate_problems = implementation_gate_problems(target)
    exploration_problem = _exploration_output_problem(status, target)
    ready_problem = _ready_output_problem(status, target)
    normalized_task = task_id.strip().upper() if task_id and task_id.strip() else None
    task_problem = None
    if normalized_task:
        try:
            _filter_ready_task_blocks(_ready_task_blocks(target), [normalized_task])
        except SystemExit as exc:
            task_problem = str(exc)

    problems: list[str] = []
    if gate_problems:
        problems.extend(gate_problems)
    if exploration_problem:
        problems.append(exploration_problem)
    if ready_problem:
        problems.append(ready_problem)
    if task_problem:
        problems.append(task_problem)

    commands: list[str] = []
    if exploration_problem:
        commands.append(f"implementation plan-check --root <root> --slug {slug} --json")
        commands.append(f"exploration render --root <root> --slug {slug}")
    if gate_problems or not status.get("implementation_ready") or ready_problem:
        commands.append(f"backlog sync --root <root> --slug {slug}")
        ready_command = f"implementation ready --root <root> --slug {slug}"
        if normalized_task and not task_problem:
            ready_command += f" --task {normalized_task}"
        commands.append(ready_command)
    elif normalized_task and not task_problem:
        commands.append(f"implementation show-ready --root <root> --slug {slug} --task {normalized_task}")
        commands.append(f"implementation enter-task --root <root> --slug {slug} --task {normalized_task}")
    else:
        commands.append(f"implementation show-ready --root <root> --slug {slug}")

    seen: set[str] = set()
    deduped_commands = []
    for command in commands:
        if command not in seen:
            seen.add(command)
            deduped_commands.append(command)

    ready_current = (
        status.get("implementation_ready")
        and not gate_problems
        and not exploration_problem
        and not ready_problem
        and not task_problem
    )
    required_visible_outputs = [
        "Display Layer: Exploration Result",
        "Display Layer: READY Focus",
    ]
    return {
        "schema": "idea-to-code.ready-recovery.v1",
        "ok": bool(ready_current),
        "slug": slug,
        "phase": status.get("phase"),
        "plan_revision": status.get("plan_revision"),
        "implementation_ready": bool(status.get("implementation_ready")),
        "exploration_output_id": status.get("exploration_output_id"),
        "exploration_output_current": exploration_problem is None,
        "ready_task_output_id": status.get("ready_task_output_id"),
        "ready_task_output_current": ready_problem is None,
        "task": normalized_task,
        "task_current": task_problem is None,
        "can_continue_to_edit": bool(ready_current and normalized_task),
        "assistant_visible_redisplay_required": True,
        "required_visible_outputs": required_visible_outputs,
        "redisplay_instruction": (
            "Run the recommended commands, then paste the refreshed Exploration Result and READY Focus blocks "
            "in the assistant-visible body before retrying pre-edit or editing tracked files."
        ),
        "problems": problems,
        "recommended_commands": deduped_commands,
    }


def implementation_recover_ready(root: Path, slug: str, task_id: str | None, json_only: bool) -> int:
    target = ensure_active_bundle(root, slug)
    payload = _ready_recovery_payload(target, slug, task_id)
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        prefix = _visibility_prefix(None, "planner", "agent")
        print(f"{prefix} READY Recovery | Bundle: {slug}")
        print()
        print("Display Layer: READY Recovery")
        print(f"READY_TASK_OUTPUT_ID: {payload.get('ready_task_output_id') or 'missing'}")
        print(f"EXPLORATION_OUTPUT_ID: {payload.get('exploration_output_id') or 'missing'}")
        print(f"Current TASK: {payload.get('task') or 'not selected'}")
        print(f"Can Continue To Edit: {'yes' if payload.get('can_continue_to_edit') else 'no'}")
        print("Visible Redisplay Required: yes")
        print("Required Visible Outputs:")
        for output_name in payload["required_visible_outputs"]:
            print(f"- {output_name}")
        print(f"Redisplay Instruction: {payload['redisplay_instruction']}")
        print()
        if payload["problems"]:
            print("Recovery Problems:")
            for problem in payload["problems"]:
                print(f"- {problem}")
            print()
        print("Recommended Commands:")
        for command in payload["recommended_commands"]:
            print(f"- {command}")
        print()
        print(
            "Do not edit tracked files until the required visible outputs are pasted in the assistant-visible "
            "body and pre-edit guard passes."
        )
    return 0 if payload["ok"] else 1


def _implementer_ready_output_problem(status: dict, evidence: str | None = None, target: Path | None = None) -> str | None:
    plan_revision = int(status.get("plan_revision", 0))
    output_id = status.get("ready_task_output_id")
    output_revision = status.get("ready_task_output_plan_revision")
    if not status.get("implementation_ready"):
        return "implementation gate is not READY; run implementation ready before recording Implementer evidence."
    if not status.get("ready_task_output_required") or not output_id or output_revision != plan_revision:
        return (
            "READY output refresh required: run implementation show-ready --root <root> --slug <slug> "
            "and send its output to the user before implementation evidence."
        )
    ready_problem = _ready_output_problem(status, target)
    if ready_problem:
        return ready_problem
    exploration_problem = _exploration_output_problem(status, target)
    if exploration_problem:
        return exploration_problem
    if evidence is not None and f"{READY_TASK_OUTPUT_ID_LABEL} {output_id}" not in evidence:
        return f"cite the latest READY output as {READY_TASK_OUTPUT_ID_LABEL} {output_id}."
    pre_edit_id = status.get("pre_edit_ok_id")
    if evidence is not None and pre_edit_id and f"{PRE_EDIT_OK_ID_LABEL} {pre_edit_id}" not in evidence:
        return f"cite the latest pre-edit guard as {PRE_EDIT_OK_ID_LABEL} {pre_edit_id}."
    return None


def _format_ready_output(
    slug: str,
    title: str,
    output_id: str,
    blocks: list[tuple[str, str]],
    profile: str | None = None,
    role: str = "planner",
    source: str = "agent",
    focused: bool = False,
    exploration_output_id: str | None = None,
    exploration: dict[str, str] | None = None,
) -> list[str]:
    implementation_granularity = "task+imp" if any(
        task_name.strip().startswith("IMP-") for task_name, _ in blocks
    ) else "task-only"
    lines = [
        f"{_visibility_prefix(profile, 'planner', 'agent')} Implementation Gate: READY | Bundle: {slug}",
        "",
        f"Display Layer: {'READY Focus' if focused else 'Full Plan'}",
        "Current TASK info must be shown before executing that TASK; use --task TASK-N when moving to another TASK.",
        "",
        f"Restated user goal: {title}",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {output_id}",
    ]
    if exploration_output_id:
        lines.append(f"{EXPLORATION_OUTPUT_ID_LABEL}: {exploration_output_id}")
    lines.extend([
        f"Implementation Granularity: {implementation_granularity}",
        "Trace Hierarchy: IDEA-* -> REQ-* -> TASK-* -> optional IMP-*",
        "",
    ])
    if exploration:
        lines.extend([
            "Exploration Summary:",
            f"- Required Now: {exploration.get('required_now') or 'See current requirements and implementation plan.'}",
            f"- Deferred: {exploration.get('deferred') or 'See Controlled Exploration decision and acceptance notes.'}",
            f"- Selected Option: {exploration.get('chosen_option') or 'See Controlled Exploration decision.'}",
            f"- What READY Will Cover: {exploration.get('ready_coverage') or 'TASK/REQ items in the current implementation plan.'}",
            "",
        ])
    if focused:
        lines.extend([
            "Focused READY TASK excerpt: yes",
            "This excerpt is for visibility only; it does not change bundle scope or gate state.",
            "Full READY plan remains in 00-idea.md; use --full-plan to print every TASK/IMP block.",
            "",
        ])
    for task_name, block in blocks:
        lines.append(task_name)
        req_hint = _covered_req_hint(task_name)
        if req_hint:
            lines.append(f"Covered REQ hint: {req_hint}")
        if block:
            lines.append(block)
        lines.append("")
    lines.append("Send this READY TASK info to the user before product-file edits for the current TASK. Continue after sending it unless the user interrupts.")
    return lines


def _ready_output_contract_problems(lines: list[str], blocks: list[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    if not blocks:
        return ["READY output has no TASK/IMP blocks"]
    text = "\n".join(lines)
    if "Display Layer:" not in text:
        problems.append("READY output missing Display Layer")
    if "Current TASK info must be shown before executing that TASK" not in text:
        problems.append("READY output missing current TASK visibility rule")
    if "Implementation Granularity:" not in text:
        problems.append("READY output missing Implementation Granularity")
    if "Trace Hierarchy: IDEA-* -> REQ-* -> TASK-* -> optional IMP-*" not in text:
        problems.append("READY output missing Trace Hierarchy")
    for required in ("Exploration Summary:", "Required Now:", "Deferred:", "Selected Option:", "What READY Will Cover:"):
        if required not in text:
            problems.append(f"READY output missing exploration context field {required}")

    task_line_indexes: dict[str, int] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        for task_name, _ in blocks:
            if stripped == task_name:
                task_line_indexes[task_name] = index

    for block_index, (task_name, _) in enumerate(blocks):
        start = task_line_indexes.get(task_name)
        if start is None:
            problems.append(f"READY output missing task line: {task_name}")
            continue

        following_starts = [
            task_line_indexes[name]
            for name, _ in blocks[block_index + 1 :]
            if name in task_line_indexes
        ]
        end = min(following_starts) if following_starts else len(lines)
        visible_block = "\n".join(lines[start:end])

        req_hint = _covered_req_hint(task_name)
        if req_hint and f"Covered REQ hint: {req_hint}" not in visible_block:
            problems.append(f"READY output missing covered REQ hint for {task_name}: {req_hint}")
        for required in ("Files:", "Execution Details:", "Done Criteria:", "Planned Verification:"):
            if not re.search(rf"^{re.escape(required)}\s*$", visible_block, re.MULTILINE):
                problems.append(f"READY output missing {required} for {task_name}")
    return problems


def _record_ready_output(
    target: Path,
    slug: str,
    status: dict,
    profile: str | None = None,
    role: str = "planner",
    source: str = "agent",
    task_filters: list[str] | None = None,
    full_plan: bool = False,
) -> tuple[str, list[str]]:
    plan_revision = int(status.get("plan_revision", 0))
    timestamp = utc_now()
    compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
    output_id = f"{slug}-r{plan_revision}-{compact_time}"
    status["ready_task_output_required"] = True
    status["ready_task_output_id"] = output_id
    status["ready_task_output_plan_revision"] = plan_revision
    status["ready_task_output_plan_fingerprint"] = _plan_fingerprint(target)
    status["ready_task_output_at_utc"] = timestamp
    event_sequence = _next_event_sequence(status)
    status["ready_task_output_event_sequence"] = event_sequence
    all_blocks = _ready_task_blocks(target)
    if task_filters:
        blocks = _filter_ready_task_blocks(all_blocks, task_filters)
        focused = True
        status["ready_task_output_scope"] = "focused"
    elif full_plan:
        blocks = all_blocks
        focused = False
        status["ready_task_output_scope"] = "full-plan"
    else:
        blocks = _default_ready_task_blocks(all_blocks)
        focused = True
        status["ready_task_output_scope"] = "focused-default"
    history_entry = {
        "id": output_id,
        "timestamp_utc": timestamp,
        "plan_revision": plan_revision,
        "event_sequence": event_sequence,
        "scope": status.get("ready_task_output_scope"),
        "task_filters": task_filters or [],
        "full_plan": bool(full_plan),
    }
    history = list(status.get("ready_task_output_history", []))
    history.append(history_entry)
    status["ready_task_output_history"] = history[-20:]
    lines = _format_ready_output(
        slug,
        status.get("title", slug),
        output_id,
        blocks,
        profile,
        "planner",
        "agent",
        focused=focused,
        exploration_output_id=status.get("exploration_output_id"),
        exploration=_controlled_exploration_values(target),
    )
    output_problems = _ready_output_contract_problems(lines, blocks)
    if output_problems:
        raise SystemExit("READY output contract failed:\n  - " + "\n  - ".join(output_problems))
    return output_id, lines


def implementation_show_ready(
    root: Path,
    slug: str,
    profile: str | None = None,
    role: str = "planner",
    source: str = "agent",
    task_filters: list[str] | None = None,
    full_plan: bool = False,
) -> int:
    _reject_ready_role_source_override(role, source)
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        problems = implementation_gate_problems(target)
        status = read_status(target)
        if problems or not status.get("implementation_ready"):
            raise SystemExit(
                "implementation show-ready refused - implementation gate is not READY:\n  - "
                + "\n  - ".join(problems or [f"{STATE_FILE}: implementation_ready is not true"])
            )
        if task_filters or not full_plan:
            ready_output_problem = _ready_output_problem(status, target)
            if ready_output_problem:
                raise SystemExit("implementation show-ready refused - " + ready_output_problem)
            output_id = status["ready_task_output_id"]
            all_blocks = _ready_task_blocks(target)
            blocks = _filter_ready_task_blocks(all_blocks, task_filters) if task_filters else _default_ready_task_blocks(all_blocks)
            lines = _format_ready_output(
                slug,
                status.get("title", slug),
                output_id,
                blocks,
                profile,
                "planner",
                "agent",
                focused=True,
                exploration_output_id=status.get("exploration_output_id"),
                exploration=_controlled_exploration_values(target),
            )
            output_problems = _ready_output_contract_problems(lines, blocks)
            if output_problems:
                raise SystemExit("READY output contract failed:\n  - " + "\n  - ".join(output_problems))
        else:
            output_id, lines = _record_ready_output(target, slug, status, profile, "planner", "agent", task_filters, full_plan=True)
            write_status(target, status)
            append_ledger(target, "implementation-show-ready", f"READY task output generated/refreshed: {output_id}")
    print("\n".join(lines))
    return 0


def implementation_enter_task(
    root: Path,
    slug: str,
    task_id: str,
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        problems = implementation_gate_problems(target)
        status = read_status(target)
        if problems or not status.get("implementation_ready"):
            raise SystemExit(
                "implementation enter-task refused - implementation gate is not READY:\n  - "
                + "\n  - ".join(problems or [f"{STATE_FILE}: implementation_ready is not true"])
            )
        ready_output_problem = _ready_output_problem(status, target)
        if ready_output_problem:
            raise SystemExit("implementation enter-task refused - " + ready_output_problem)
        normalized_task_id = task_id.strip().upper()
        blocks = _filter_ready_task_blocks(_ready_task_blocks(target), [normalized_task_id])
        output_id = status["ready_task_output_id"]
        lines = _format_ready_output(
            slug,
            status.get("title", slug),
            output_id,
            blocks,
            profile,
            "planner",
            "agent",
            focused=True,
            exploration_output_id=status.get("exploration_output_id"),
            exploration=_controlled_exploration_values(target),
        )
        output_problems = _ready_output_contract_problems(lines, blocks)
        if output_problems:
            raise SystemExit("READY output contract failed:\n  - " + "\n  - ".join(output_problems))
        status["current_task_id"] = normalized_task_id
        status["current_task_entered_at_utc"] = utc_now()
        status["current_task_event_sequence"] = _next_event_sequence(status)
        status["current_task_ready_output_id"] = output_id
        write_status(target, status)
        append_ledger(target, "implementation-enter-task", f"Entered {normalized_task_id}; ready_output={output_id}")
    print("\n".join(lines))
    return 0


def implementation_overview(
    root: Path,
    slug: str,
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    status = read_status(target)
    exploration = _controlled_exploration_values(target)
    task_blocks = _ready_task_blocks(target)
    current_task_id = (status.get("current_task_id") or "").strip().upper()
    task_ids = [name.split(":", 1)[0].strip().upper() for name, _ in task_blocks]
    next_tasks = [task_id for task_id in task_ids if task_id != current_task_id]
    lines = [
        f"{_visibility_prefix(profile, 'planner', 'agent')} Implementation Overview | Bundle: {slug}",
        "",
        "Display Layer: Overview",
        "Use READY Focus before editing the current TASK; use Full Plan only for audit.",
        "",
        f"Restated user goal: {status.get('title', slug)}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {status.get('exploration_output_id') or 'missing'}",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {status.get('ready_task_output_id') or 'missing'}",
        "",
        "Planned Scope:",
        f"- Required Now: {exploration.get('required_now') or 'See current requirements and implementation plan.'}",
        f"- Deferred: {exploration.get('deferred') or 'See Controlled Exploration decision and acceptance notes.'}",
        f"- What READY Will Cover: {exploration.get('ready_coverage') or 'TASK/REQ items in the current implementation plan.'}",
        "",
        "Current TASK:",
        f"- {current_task_id or 'none entered; run implementation enter-task --task TASK-N before edits.'}",
        "",
        "Next Tasks:",
    ]
    if next_tasks:
        lines.extend(f"- {task_id}" for task_id in next_tasks)
    else:
        lines.append("- none")
    lines.extend([
        "",
        "Full Plan:",
        f"- Run implementation show-ready --root <root> --slug {slug} --full-plan for the complete TASK/IMP audit list.",
    ])
    print("\n".join(lines))
    return 0


def implementation_next_action(
    root: Path,
    slug: str,
    task_id: str,
    files: list[str],
    owner: str = "agent",
    json_only: bool = False,
    profile: str | None = None,
) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    normalized_task_id = task_id.strip().upper()
    requested_files = [item for item in files if item.strip()] or _task_files_for_id(target, normalized_task_id)
    gate_problems = implementation_gate_problems(target)
    problems: list[str] = []
    action = "READY_FOR_EDIT"
    assistant_visible_required = False
    recommended_commands: list[str] = []
    required_visible_fields = [
        "Display Layer: Exploration Result",
        "EXPLORATION_OUTPUT_ID:",
        "Required Now:",
        "Deferred:",
        "Selected Option:",
        "What READY Will Cover:",
        "Display Layer: READY Focus",
        "READY_TASK_OUTPUT_ID:",
        "Files:",
        "Execution Details:",
        "Done Criteria:",
        "Planned Verification:",
    ]

    if gate_problems or not status.get("implementation_ready"):
        action = "NEEDS_READY"
        assistant_visible_required = True
        problems.extend(gate_problems or [f"{STATE_FILE}: implementation_ready is not true"])
        recommended_commands.extend([
            f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" exploration render --root "$(pwd)" --slug {slug}',
            f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation ready --root "$(pwd)" --slug {slug} --task {normalized_task_id}',
        ])
    else:
        exploration_problem = _exploration_output_problem(status, target)
        ready_problem = _ready_output_problem(status, target)
        if exploration_problem or ready_problem:
            action = "NEEDS_READY"
            assistant_visible_required = True
            problems.extend([item for item in (exploration_problem, ready_problem) if item])
            recommended_commands.append(
                f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation recover-ready --root "$(pwd)" --slug {slug} --task {normalized_task_id}'
            )
        else:
            current_task = (status.get("current_task_id") or "").strip().upper()
            if current_task != normalized_task_id or status.get("current_task_ready_output_id") != status.get("ready_task_output_id"):
                action = "NEEDS_TASK_ENTRY"
                assistant_visible_required = True
                if current_task != normalized_task_id:
                    problems.append(
                        f"current_task_id is {current_task or '(missing)'}; enter {normalized_task_id} before edits"
                    )
                else:
                    problems.append("current TASK entry is older than latest READY output")
                recommended_commands.append(
                    f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation enter-task --root "$(pwd)" --slug {slug} --task {normalized_task_id}'
                )
            else:
                visible_problem = _visible_output_problem(status, normalized_task_id)
                if visible_problem:
                    action = "NEEDS_VISIBLE_OUTPUT_RECORD"
                    assistant_visible_required = True
                    problems.append(visible_problem)
                    recommended_commands.extend([
                        f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation show-ready --root "$(pwd)" --slug {slug} --task {normalized_task_id}',
                        f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation visible-output record --root "$(pwd)" --slug {slug} --task {normalized_task_id} --assistant-body-file <assistant-visible-body.txt>',
                    ])
                else:
                    lease_problems = _lease_compliance_problems(status, normalized_task_id, requested_files, owner.strip() or "agent")
                    if lease_problems:
                        action = "NEEDS_LEASE"
                        problems.extend(lease_problems)
                        command_files = " ".join(requested_files)
                        recommended_commands.append(
                            f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation lease acquire --root "$(pwd)" --slug {slug} --task {normalized_task_id} --owner {owner.strip() or "agent"} --files {command_files}'
                        )
                    else:
                        requested = {_normalize_guard_file(item) for item in requested_files}
                        covered = _pre_edit_covered_files(status, normalized_task_id)
                        missing_pre_edit = sorted(requested - covered)
                        if missing_pre_edit:
                            action = "NEEDS_PRE_EDIT"
                            problems.append("pre-edit guard missing current records for file(s): " + ", ".join(missing_pre_edit))
                            command_files = " ".join(requested_files)
                            recommended_commands.append(
                                f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation pre-edit --root "$(pwd)" --slug {slug} --task {normalized_task_id} --owner {owner.strip() or "agent"} --files {command_files}'
                            )

    payload = {
        "schema": "idea-to-code.implementation.next-action.v1",
        "bundle": slug,
        "task": normalized_task_id,
        "action": action,
        "assistant_visible_required": assistant_visible_required,
        "required_visible_fields": required_visible_fields if assistant_visible_required else [],
        "recommended_commands": recommended_commands,
        "problems": problems,
        "files": requested_files,
        "owner": owner.strip() or "agent",
        "exploration_output_id": status.get("exploration_output_id"),
        "ready_task_output_id": status.get("ready_task_output_id"),
        "visible_output_id": status.get("visible_output_id"),
        "pre_edit_ok_id": status.get("pre_edit_ok_id"),
        "current_task_id": status.get("current_task_id"),
        "host_required_boundary": "Native edit-tool interception is not physically enforced by this command.",
    }
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if action == "READY_FOR_EDIT" else 1

    lines = [
        f"{_visibility_prefix(profile, 'planner', 'agent')} Next Action: {action} | Bundle: {slug}",
        "",
        "Display Layer: Next Action",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {payload.get('ready_task_output_id') or 'missing'}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {payload.get('exploration_output_id') or 'missing'}",
        f"VISIBLE_OUTPUT_ID: {payload.get('visible_output_id') or 'missing'}",
        f"{PRE_EDIT_OK_ID_LABEL}: {payload.get('pre_edit_ok_id') or 'missing'}",
        "",
        "Current TASK:",
        f"- {normalized_task_id}",
        "",
        "Assistant Visible Required:",
        f"- {'yes' if assistant_visible_required else 'no'}",
    ]
    if assistant_visible_required:
        lines.extend(["", "Required Visible Fields:"])
        lines.extend(f"- {item}" for item in required_visible_fields)
    if problems:
        lines.extend(["", "Problems:"])
        lines.extend(f"- {item}" for item in problems)
    lines.extend(["", "Recommended Commands:"])
    if recommended_commands:
        lines.extend(f"- {item}" for item in recommended_commands)
    else:
        lines.append("- none; tracked edit may proceed only through the approved edit path and current pre-edit evidence.")
    lines.extend([
        "",
        "Boundary:",
        "- Native edit-tool interception is host-required; this command is read-only guidance plus machine-checkable evidence.",
    ])
    print("\n".join(lines))
    return 0 if action == "READY_FOR_EDIT" else 1


def implementation_lease_acquire(
    root: Path,
    slug: str,
    task_id: str,
    owner: str,
    files: list[str],
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    normalized_task_id = task_id.strip().upper()
    normalized_owner = owner.strip() or "agent"
    requested_files = [item for item in files if item.strip()]
    if not requested_files:
        raise SystemExit("implementation lease acquire refused - provide at least one --file path.")
    with bundle_lock(target):
        problems = implementation_gate_problems(target)
        status = read_status(target)
        if problems or not status.get("implementation_ready"):
            raise SystemExit(
                "implementation lease acquire refused - implementation gate is not READY:\n  - "
                + "\n  - ".join(problems or [f"{STATE_FILE}: implementation_ready is not true"])
            )
        current_task = (status.get("current_task_id") or "").strip().upper()
        if current_task != normalized_task_id:
            raise SystemExit(
                "implementation lease acquire refused - current_task_id is "
                f"{current_task or '(missing)'}; run implementation enter-task --task {normalized_task_id} first."
            )
        allowed_files = _task_files_for_id(target, normalized_task_id)
        allowed = {_normalize_guard_file(item) for item in allowed_files}
        requested = {_normalize_guard_file(item) for item in requested_files}
        missing = sorted(requested - allowed)
        if missing:
            raise SystemExit(
                "implementation lease acquire refused - file(s) not listed under "
                f"{normalized_task_id} Files: " + ", ".join(missing)
            )
        conflicts = _lease_conflicts(status, normalized_task_id, normalized_owner, requested_files)
        if conflicts:
            details = []
            for conflict in conflicts:
                details.append(
                    f"{conflict.get('id', 'unknown')} owner={conflict.get('owner', 'unknown')} "
                    f"files={', '.join(conflict.get('overlap') or [])}"
                )
            raise SystemExit("implementation lease acquire refused - overlapping active lease(s): " + "; ".join(details))
        timestamp = utc_now()
        compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
        event_sequence = _next_event_sequence(status)
        lease_id = f"{slug}-lease-r{status.get('plan_revision', 0)}-{compact_time}"
        lease = {
            "id": lease_id,
            "owner": normalized_owner,
            "task_id": normalized_task_id,
            "files": requested_files,
            "plan_revision": int(status.get("plan_revision", 0)),
            "ready_task_output_id": status.get("ready_task_output_id"),
            "exploration_output_id": status.get("exploration_output_id"),
            "event_sequence": event_sequence,
            "acquired_at_utc": timestamp,
        }
        status.setdefault("implementation_leases", []).append(lease)
        write_status(target, status)
        append_ledger(target, "implementation-lease-acquire", f"{lease_id}: {normalized_owner} owns {normalized_task_id}")
    lines = [
        f"{_visibility_prefix(profile, 'implementer', 'agent')} Implementation Lease: acquired | Bundle: {slug}",
        "",
        "Display Layer: Implementation Lease",
        f"LEASE_ID: {lease_id}",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {lease.get('ready_task_output_id')}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {lease.get('exploration_output_id')}",
        "",
        "Current TASK:",
        f"- {normalized_task_id}",
        "Owner:",
        f"- {normalized_owner}",
        "",
        "Files Owned For Edit:",
    ]
    lines.extend(f"- {item}" for item in requested_files)
    print("\n".join(lines))
    return 0


def implementation_lease_release(root: Path, slug: str, lease_id: str, reason: str) -> Path:
    target = ensure_active_bundle(root, slug)
    if _weak_text_value(reason, min_len=8):
        raise SystemExit("implementation lease release refused - --reason is too vague.")
    with bundle_lock(target):
        status = read_status(target)
        matched = None
        for lease in status.get("implementation_leases", []):
            if lease.get("id") == lease_id:
                matched = lease
                break
        if not matched:
            raise SystemExit(f"implementation lease release refused - unknown lease id: {lease_id}")
        if matched.get("released_at_utc"):
            raise SystemExit(f"implementation lease release refused - lease already released: {lease_id}")
        matched["released_at_utc"] = utc_now()
        matched["release_reason"] = reason
        matched["release_event_sequence"] = _next_event_sequence(status)
        write_status(target, status)
        append_ledger(target, "implementation-lease-release", f"{lease_id}: {reason}")
    return target


def implementation_lease_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    payload = {
        "path": str(target),
        "implementation_leases": status.get("implementation_leases", []),
        "active": _active_implementation_leases(status),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _release_active_leases_for_closeout(status: dict, timestamp: str, reason: str) -> None:
    for lease in status.get("implementation_leases", []):
        if lease.get("released_at_utc"):
            continue
        lease["released_at_utc"] = timestamp
        lease["release_reason"] = reason
        lease["release_event_sequence"] = _next_event_sequence(status)


def delegation_record(
    root: Path,
    slug: str,
    role: str,
    status_value: str,
    scope: str,
    evidence_summary: str,
    agent_id: str,
    reason: str,
) -> Path:
    target = ensure_active_bundle(root, slug)
    role_key = role.strip().lower()
    if role_key not in ROLE_NAMES:
        raise SystemExit(f"delegation record refused - --role must be one of: {', '.join(ROLE_NAMES)}")
    if status_value not in DELEGATION_STATUSES:
        raise SystemExit(f"delegation record refused - --status must be one of: {', '.join(DELEGATION_STATUSES)}")
    for label, value in {"scope": scope, "evidence-summary": evidence_summary}.items():
        if not _is_ascii(value):
            raise SystemExit(f"delegation record refused - --{label} must be English-only ASCII text.")
        if _weak_text_value(value, min_len=10):
            raise SystemExit(f"delegation record refused - --{label} is too vague.")
    if status_value != "usable" and _weak_text_value(reason, min_len=8):
        raise SystemExit("delegation record refused - non-usable records require --reason.")
    with bundle_lock(target):
        status = read_status(target)
        timestamp = utc_now()
        compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
        event_sequence = _next_event_sequence(status)
        record_id = f"{slug}-delegation-r{status.get('plan_revision', 0)}-{compact_time}"
        record = {
            "id": record_id,
            "role": role_key,
            "status": status_value,
            "scope": scope,
            "evidence_summary": evidence_summary,
            "agent_id": agent_id,
            "reason": reason,
            "plan_revision": int(status.get("plan_revision", 0)),
            "event_sequence": event_sequence,
            "recorded_at_utc": timestamp,
        }
        status.setdefault("delegation_records", []).append(record)
        write_status(target, status)
        append_ledger(target, "delegation-record", f"{record_id}: {role_key} {status_value} {scope}")
    return target


def delegation_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    payload = {
        "path": str(target),
        "delegation_records": status.get("delegation_records", []),
        "usable": _usable_delegation_records(status),
        "open_findings": _open_delegation_findings(status),
        "problems": _delegation_problems(status),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not payload["problems"] else 1


def delegation_resolve(root: Path, slug: str, record_id: str, resolution: str, reason: str) -> Path:
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    if resolution not in ("fallback-same-agent", "superseded", "accepted-risk", "invalid-record"):
        raise SystemExit(
            "delegation resolve refused - --resolution must be one of: "
            "fallback-same-agent, superseded, accepted-risk, invalid-record"
        )
    if not _is_ascii(reason):
        raise SystemExit("delegation resolve refused - --reason must be English-only ASCII text.")
    if _weak_text_value(reason, min_len=10):
        raise SystemExit("delegation resolve refused - --reason is too vague.")
    with bundle_lock(target):
        status = read_status(target)
        record = _delegation_record_by_id(status, record_id)
        if not record:
            raise SystemExit(f"delegation resolve refused - unknown delegation record id: {record_id}")
        if record.get("status") == "usable":
            raise SystemExit("delegation resolve refused - usable delegation records are evidence, not findings.")
        if record.get("resolved_at_utc"):
            raise SystemExit(f"delegation resolve refused - record already resolved: {record_id}")
        timestamp = utc_now()
        record["resolved_at_utc"] = timestamp
        record["resolution"] = resolution
        record["resolution_reason"] = reason
        record["resolution_event_sequence"] = _next_event_sequence(status)
        write_status(target, status)
        append_ledger(target, "delegation-resolve", f"{record_id}: {resolution} - {reason}")
    return target


def idea_record(
    root: Path,
    slug: str,
    idea_id: str,
    status_value: str,
    summary: str,
    related_reqs: list[str],
    notes: str,
) -> Path:
    normalized_id = idea_id.strip().upper()
    normalized_status = status_value.strip().lower()
    if not re.fullmatch(r"IDEA-[A-Z0-9][A-Z0-9_.-]*", normalized_id):
        raise SystemExit("idea record refused - --id must look like IDEA-1 or IDEA-CONTROL.")
    if normalized_status not in IDEA_RECORD_STATUSES:
        raise SystemExit("idea record refused - --status must be one of: " + ", ".join(IDEA_RECORD_STATUSES))
    for label, value in {"summary": summary, "notes": notes}.items():
        if not _is_ascii(value):
            raise SystemExit(f"idea record refused - --{label} must be English-only ASCII text.")
        if _weak_text_value(value, min_len=10):
            raise SystemExit(f"idea record refused - --{label} is too vague.")
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    with bundle_lock(target):
        status = read_status(target)
        known_ids = {r["id"] for r in status.get("requirements", [])}
        unknown = [rid for rid in related_reqs if rid not in known_ids]
        if unknown and known_ids:
            raise SystemExit("idea record refused - unknown related REQ IDs: " + ", ".join(unknown))
        timestamp = utc_now()
        event_sequence = _next_event_sequence(status)
        existing = {entry.get("id"): entry for entry in status.get("idea_records", [])}
        previous = existing.get(normalized_id, {})
        record = {
            "id": normalized_id,
            "status": normalized_status,
            "summary": summary,
            "related_reqs": related_reqs,
            "notes": notes,
            "plan_revision": int(status.get("plan_revision", 0)),
            "event_sequence": event_sequence,
            "created_at_utc": previous.get("created_at_utc") or timestamp,
            "updated_at_utc": timestamp,
        }
        status["idea_records"] = [
            entry for entry in status.get("idea_records", [])
            if entry.get("id") != normalized_id
        ]
        status["idea_records"].append(record)
        status["idea_records"].sort(key=lambda item: item.get("id", ""))
        status["idea_record_event_sequence"] = event_sequence
        write_status(target, status)
        append_ledger(
            target,
            "idea-record",
            f"{normalized_id} -> {normalized_status}: {summary}",
            related_reqs,
        )
    return target


def idea_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    payload = {
        "path": str(target),
        "plan_revision": status.get("plan_revision"),
        "idea_records": status.get("idea_records", []),
        "active": [
            entry for entry in status.get("idea_records", [])
            if entry.get("status") in {"active", "blocked"}
        ],
        "deferred": [
            entry for entry in status.get("idea_records", [])
            if entry.get("status") == "deferred"
        ],
        "closed": [
            entry for entry in status.get("idea_records", [])
            if entry.get("status") in {"completed", "rejected", "superseded", "reference"}
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def session_audit(
    root: Path,
    slug: str,
    relation: str,
    summary: str,
    prior_scope: str,
    decision: str,
) -> Path:
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    if relation not in SESSION_RELATIONS:
        raise SystemExit(f"session audit refused - --relation must be one of: {', '.join(SESSION_RELATIONS)}")
    for label, value in {"summary": summary, "prior-scope": prior_scope, "decision": decision}.items():
        if not _is_ascii(value):
            raise SystemExit(f"session audit refused - --{label} must be English-only ASCII text.")
        if _weak_text_value(value, min_len=10):
            raise SystemExit(f"session audit refused - --{label} is too vague.")
    with bundle_lock(target):
        status = read_status(target)
        timestamp = utc_now()
        compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
        event_sequence = _next_event_sequence(status)
        audit_id = f"{slug}-session-r{status.get('plan_revision', 0)}-{compact_time}"
        record = {
            "id": audit_id,
            "relation": relation,
            "summary": summary,
            "prior_scope": prior_scope,
            "decision": decision,
            "plan_revision": int(status.get("plan_revision", 0)),
            "event_sequence": event_sequence,
            "recorded_at_utc": timestamp,
        }
        status.setdefault("session_continuity_audits", []).append(record)
        write_status(target, status)
        append_ledger(target, "session-audit", f"{audit_id}: {relation} {summary}")
    return target


def session_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    audits = status.get("session_continuity_audits", [])
    payload = {
        "path": str(target),
        "session_continuity_audits": audits,
        "latest": audits[-1] if audits else None,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def scope_classify(
    root: Path,
    slug: str,
    classification: str,
    summary: str,
    rationale: str,
    action: str,
) -> Path:
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    if classification not in SESSION_RELATIONS:
        raise SystemExit(f"scope classify refused - --classification must be one of: {', '.join(SESSION_RELATIONS)}")
    for label, value in {"summary": summary, "rationale": rationale, "action": action}.items():
        if not _is_ascii(value):
            raise SystemExit(f"scope classify refused - --{label} must be English-only ASCII text.")
        if _weak_text_value(value, min_len=10):
            raise SystemExit(f"scope classify refused - --{label} is too vague.")
    with bundle_lock(target):
        status = read_status(target)
        timestamp = utc_now()
        compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
        event_sequence = _next_event_sequence(status)
        classification_id = f"{slug}-scope-r{status.get('plan_revision', 0)}-{compact_time}"
        record = {
            "id": classification_id,
            "classification": classification,
            "summary": summary,
            "rationale": rationale,
            "action": action,
            "plan_revision": int(status.get("plan_revision", 0)),
            "event_sequence": event_sequence,
            "recorded_at_utc": timestamp,
        }
        status.setdefault("scope_classifications", []).append(record)
        write_status(target, status)
        append_ledger(target, "scope-classify", f"{classification_id}: {classification} {summary}")
    return target


def scope_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    records = status.get("scope_classifications", [])
    payload = {
        "path": str(target),
        "scope_classifications": records,
        "latest": records[-1] if records else None,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def implementation_visible_output_record(
    root: Path,
    slug: str,
    task_id: str,
    assistant_body: str,
    source: str = "agent",
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    normalized_task_id = task_id.strip().upper()
    body = assistant_body.strip()
    if not body:
        raise SystemExit("implementation visible-output record refused - assistant-visible body is empty.")
    with bundle_lock(target):
        status = read_status(target)
        problems = implementation_gate_problems(target)
        if problems or not status.get("implementation_ready"):
            raise SystemExit(
                "implementation visible-output record refused - implementation gate is not READY:\n  - "
                + "\n  - ".join(problems or [f"{STATE_FILE}: implementation_ready is not true"])
            )
        current_task = (status.get("current_task_id") or "").strip().upper()
        if current_task and current_task != normalized_task_id:
            raise SystemExit(
                "implementation visible-output record refused - current_task_id is "
                f"{current_task}; record visible output for {current_task} or enter {normalized_task_id} first."
            )
        validation_problems = validate_visible_ready_output("", body)
        current_ready_id = status.get("ready_task_output_id")
        current_exploration_id = status.get("exploration_output_id")
        if current_ready_id and str(current_ready_id) not in body:
            validation_problems.append(f"assistant-visible body missing current {READY_TASK_OUTPUT_ID_LABEL}: {current_ready_id}")
        if current_exploration_id and str(current_exploration_id) not in body:
            validation_problems.append(f"assistant-visible body missing current {EXPLORATION_OUTPUT_ID_LABEL}: {current_exploration_id}")
        if validation_problems:
            raise SystemExit(
                "implementation visible-output record refused - assistant-visible body is not a complete Display Layer:\n  - "
                + "\n  - ".join(validation_problems)
            )
        plan_revision = int(status.get("plan_revision", 0))
        timestamp = utc_now()
        compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
        visible_id = f"{slug}-visible-r{plan_revision}-{compact_time}"
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        status["visible_output_required"] = True
        status["visible_output_id"] = visible_id
        event_sequence = _next_event_sequence(status)
        record = {
            "id": visible_id,
            "task_id": normalized_task_id,
            "source": source.strip() or "agent",
            "ready_task_output_id": current_ready_id,
            "exploration_output_id": current_exploration_id,
            "plan_revision": plan_revision,
            "event_sequence": event_sequence,
            "at_utc": timestamp,
            "assistant_body_sha256": body_hash,
            "ok": True,
        }
        status.setdefault("visible_output_records", []).append(record)
        write_status(target, status)
        append_ledger(target, "implementation-visible-output", f"Visible output recorded: {visible_id} for {normalized_task_id}")
    lines = [
        f"{_visibility_prefix(profile, 'planner', source.strip() or 'agent')} Visible Output: recorded | Bundle: {slug}",
        "",
        "Display Layer: Visible Output Record",
        f"VISIBLE_OUTPUT_ID: {visible_id}",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {record['ready_task_output_id']}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {record['exploration_output_id']}",
        "",
        "Current TASK:",
        f"- {normalized_task_id}",
        "Assistant Body SHA256:",
        f"- {body_hash}",
    ]
    print("\n".join(lines))
    return 0


def implementation_visible_output_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    current_task = (status.get("current_task_id") or "").strip().upper()
    result = {
        "path": str(target),
        "visible_output_required": status.get("visible_output_required", False),
        "visible_output_id": status.get("visible_output_id"),
        "current_task_id": current_task or None,
        "current_record": _current_visible_output_record(status, current_task) if current_task else None,
        "visible_output_records": status.get("visible_output_records", []),
        "problem": _visible_output_problem(status, current_task) if current_task else None,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def implementation_pre_edit(
    root: Path,
    slug: str,
    task_id: str,
    files: list[str],
    owner: str = "agent",
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    normalized_task_id = task_id.strip().upper()
    requested_files = [item for item in files if item.strip()]
    if not requested_files:
        raise SystemExit("implementation pre-edit refused - provide at least one --file path.")
    with bundle_lock(target):
        problems = implementation_gate_problems(target)
        status = read_status(target)
        if problems or not status.get("implementation_ready"):
            raise SystemExit(
                "implementation pre-edit refused - implementation gate is not READY:\n  - "
                + "\n  - ".join(problems or [f"{STATE_FILE}: implementation_ready is not true"])
            )
        exploration_problem = _exploration_output_problem(status, target)
        if exploration_problem:
            raise SystemExit("implementation pre-edit refused - " + exploration_problem)
        ready_output_problem = _ready_output_problem(status, target)
        if ready_output_problem:
            raise SystemExit("implementation pre-edit refused - " + ready_output_problem)
        current_task = (status.get("current_task_id") or "").strip().upper()
        if current_task != normalized_task_id:
            raise SystemExit(
                "implementation pre-edit refused - current_task_id is "
                f"{current_task or '(missing)'}; run implementation enter-task --task {normalized_task_id} first."
            )
        if status.get("current_task_ready_output_id") != status.get("ready_task_output_id"):
            raise SystemExit("implementation pre-edit refused - current TASK entry is older than latest READY output.")
        visible_problem = _visible_output_problem(status, normalized_task_id)
        if visible_problem:
            raise SystemExit("implementation pre-edit refused - " + visible_problem)
        allowed_files = _task_files_for_id(target, normalized_task_id)
        allowed = {_normalize_guard_file(item) for item in allowed_files}
        requested = {_normalize_guard_file(item) for item in requested_files}
        missing = sorted(requested - allowed)
        if missing:
            raise SystemExit(
                "implementation pre-edit refused - file(s) not listed under "
                f"{normalized_task_id} Files: " + ", ".join(missing)
            )
        lease_problems = _lease_compliance_problems(status, normalized_task_id, requested_files, owner.strip() or "agent")
        if lease_problems:
            raise SystemExit("implementation pre-edit refused - " + "; ".join(lease_problems))
        plan_revision = int(status.get("plan_revision", 0))
        timestamp = utc_now()
        compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
        pre_edit_id = f"{slug}-preedit-r{plan_revision}-{compact_time}"
        status["pre_edit_guard_required"] = True
        status["pre_edit_ok_id"] = pre_edit_id
        status["pre_edit_plan_revision"] = plan_revision
        status["pre_edit_at_utc"] = timestamp
        status["pre_edit_event_sequence"] = _next_event_sequence(status)
        status["pre_edit_task_id"] = normalized_task_id
        status["pre_edit_files"] = requested_files
        status["pre_edit_owner"] = owner.strip() or "agent"
        status["pre_edit_ready_task_output_id"] = status.get("ready_task_output_id")
        status["pre_edit_exploration_output_id"] = status.get("exploration_output_id")
        visible_record = _current_visible_output_record(status, normalized_task_id)
        status.setdefault("pre_edit_records", []).append({
            "id": pre_edit_id,
            "task_id": normalized_task_id,
            "owner": owner.strip() or "agent",
            "files": requested_files,
            "ready_task_output_id": status.get("ready_task_output_id"),
            "exploration_output_id": status.get("exploration_output_id"),
            "visible_output_id": visible_record.get("id") if visible_record else None,
            "plan_revision": plan_revision,
            "event_sequence": status["pre_edit_event_sequence"],
            "at_utc": timestamp,
        })
        write_status(target, status)
        append_ledger(target, "implementation-pre-edit", f"Pre-edit guard OK: {pre_edit_id} for {normalized_task_id}")
    lines = [
        f"{_visibility_prefix(profile, 'implementer', 'agent')} Pre-Edit Guard: OK | Bundle: {slug}",
        "",
        "Display Layer: Pre-Edit Guard",
        f"{PRE_EDIT_OK_ID_LABEL}: {pre_edit_id}",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {status.get('ready_task_output_id')}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {status.get('exploration_output_id')}",
        f"VISIBLE_OUTPUT_ID: {visible_record.get('id') if visible_record else None}",
        "",
        "Current TASK:",
        f"- {normalized_task_id}",
        "Owner:",
        f"- {owner.strip() or 'agent'}",
        "",
        "Files Approved For Edit:",
    ]
    lines.extend(f"- {item}" for item in requested_files)
    lines.extend([
        "",
        "Next Step:",
        "- Edit only the approved files for this TASK, then cite PRE_EDIT_OK_ID in Implementer evidence.",
    ])
    print("\n".join(lines))
    return 0


def _guarded_patch_paths(patch_text: str) -> list[str]:
    paths: set[str] = set()
    for line in patch_text.splitlines():
        candidates: list[str] = []
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                candidates.extend([parts[2], parts[3]])
        elif line.startswith("+++ ") or line.startswith("--- "):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                candidates.append(parts[1])
        for raw in candidates:
            path_text = raw.strip()
            if path_text == "/dev/null":
                continue
            if path_text.startswith(("a/", "b/")):
                path_text = path_text[2:]
            path_text = path_text.replace("\\", "/")
            if not path_text or path_text.startswith("/") or path_text.startswith("../") or "/../" in path_text:
                raise SystemExit(f"guarded apply refused - unsafe patch path: {raw}")
            paths.add(path_text)
    if not paths:
        raise SystemExit("guarded apply refused - patch has no changed file paths.")
    return sorted(paths)


def implementation_guarded_apply(
    root: Path,
    slug: str,
    task_id: str,
    patch_file: str,
    owner: str = "agent",
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    patch_path = Path(patch_file)
    if not patch_path.is_absolute():
        patch_path = root / patch_path
    if not patch_path.exists():
        raise SystemExit(f"guarded apply refused - patch file not found: {patch_file}")
    patch_text = patch_path.read_text(encoding="utf-8")
    changed_files = _guarded_patch_paths(patch_text)
    check = subprocess.run(
        ["git", "apply", "--check", str(patch_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check.returncode != 0:
        raise SystemExit("guarded apply refused - git apply --check failed:\n" + (check.stderr or check.stdout).strip())

    implementation_pre_edit(root, slug, task_id, changed_files, owner, profile)

    apply_result = subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if apply_result.returncode != 0:
        raise SystemExit("guarded apply failed after pre-edit - git apply failed:\n" + (apply_result.stderr or apply_result.stdout).strip())

    status = read_status(target)
    pre_edit_id = status.get("pre_edit_ok_id") or "<PRE_EDIT_OK_ID>"
    lines = [
        f"{_visibility_prefix(profile, 'implementer', 'agent')} Guarded Apply: applied | Bundle: {slug}",
        "",
        "Display Layer: Guarded Apply",
        f"{PRE_EDIT_OK_ID_LABEL}: {pre_edit_id}",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {status.get('ready_task_output_id')}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {status.get('exploration_output_id')}",
        "",
        "Current TASK:",
        f"- {task_id.strip().upper()}",
        "",
        "Patch File:",
        f"- {patch_path}",
        "",
        "Files Applied:",
    ]
    lines.extend(f"- {item}" for item in changed_files)
    print("\n".join(lines))
    append_ledger(target, "implementation-guarded-apply", f"Applied guarded patch for {task_id.strip().upper()}: {', '.join(changed_files)}")
    return 0


def implementation_noncompliance(
    root: Path,
    slug: str,
    task_id: str,
    reason: str,
    files: list[str],
    profile: str | None = None,
) -> int:
    target = ensure_active_bundle(root, slug)
    normalized_task_id = task_id.strip().upper()
    if _weak_text_value(reason, min_len=12):
        raise SystemExit("implementation noncompliance refused - --reason must describe the compliance lapse.")
    if not _is_ascii(reason):
        raise SystemExit("implementation noncompliance refused - --reason must be English-only ASCII text.")
    with bundle_lock(target):
        status = read_status(target)
        timestamp = utc_now()
        compact_time = re.sub(r"[^0-9]", "", timestamp)[:14]
        event_sequence = _next_event_sequence(status)
        event_id = f"{slug}-preedit-noncompliance-r{status.get('plan_revision', 0)}-{compact_time}"
        event = {
            "id": event_id,
            "task_id": normalized_task_id,
            "reason": reason,
            "files": files,
            "plan_revision": status.get("plan_revision", 0),
            "ready_task_output_id": status.get("ready_task_output_id"),
            "exploration_output_id": status.get("exploration_output_id"),
            "event_sequence": event_sequence,
            "at_utc": timestamp,
        }
        status.setdefault("pre_edit_noncompliance", []).append(event)
        write_status(target, status)
        append_ledger(target, "implementation-noncompliance", f"{event_id}: {reason}")
    lines = [
        f"{_visibility_prefix(profile, 'implementer', 'agent')} Pre-Edit Noncompliance: recorded | Bundle: {slug}",
        "",
        "Display Layer: Pre-Edit Noncompliance",
        f"NONCOMPLIANCE_ID: {event_id}",
        f"{READY_TASK_OUTPUT_ID_LABEL}: {event.get('ready_task_output_id')}",
        f"{EXPLORATION_OUTPUT_ID_LABEL}: {event.get('exploration_output_id')}",
        "",
        "Current TASK:",
        f"- {normalized_task_id}",
        "",
        "Reason:",
        f"- {reason}",
    ]
    if files:
        lines.extend(["", "Files:"])
        lines.extend(f"- {item}" for item in files)
    lines.extend([
        "",
        "Effect:",
        "- verify, render-status, and accepted closeout must surface this until it is resolved or the plan is corrected.",
    ])
    print("\n".join(lines))
    return 0


def implementation_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    problems = implementation_gate_problems(target)
    status = read_status(target)
    exploration_problem = _exploration_output_problem(status, target)
    if exploration_problem:
        problems.append(exploration_problem)
    ready_problem = _ready_output_problem(status, target)
    if ready_problem:
        problems.append(ready_problem)
    problems.extend(_pre_edit_compliance_problems(target, status))
    problems.extend(_delegation_problems(status))
    result = {
        "path": str(target),
        "implementation_file": IMPLEMENTATION_FILE,
        "ready": not problems and bool(status.get("implementation_ready")),
        "status_flag": status.get("implementation_ready", False),
        "phase": status.get("phase"),
        "exploration_output_required": status.get("exploration_output_required", False),
        "exploration_output_id": status.get("exploration_output_id"),
        "exploration_output_plan_revision": status.get("exploration_output_plan_revision"),
        "ready_task_output_required": status.get("ready_task_output_required", False),
        "ready_task_output_id": status.get("ready_task_output_id"),
        "ready_task_output_plan_revision": status.get("ready_task_output_plan_revision"),
        "ready_task_output_history": status.get("ready_task_output_history", []),
        "current_task_id": status.get("current_task_id"),
        "current_task_ready_output_id": status.get("current_task_ready_output_id"),
        "visible_output_required": status.get("visible_output_required", False),
        "visible_output_id": status.get("visible_output_id"),
        "visible_output_records": status.get("visible_output_records", []),
        "pre_edit_ok_id": status.get("pre_edit_ok_id"),
        "pre_edit_task_id": status.get("pre_edit_task_id"),
        "pre_edit_files": status.get("pre_edit_files"),
        "pre_edit_owner": status.get("pre_edit_owner"),
        "pre_edit_records": status.get("pre_edit_records", []),
        "pre_edit_noncompliance": status.get("pre_edit_noncompliance", []),
        "implementation_leases": status.get("implementation_leases", []),
        "delegation_records": status.get("delegation_records", []),
        "session_continuity_audits": status.get("session_continuity_audits", []),
        "scope_classifications": status.get("scope_classifications", []),
        "idea_records": status.get("idea_records", []),
        "master_backlog_required": status.get("master_backlog_required"),
        "master_backlog_plan_revision": status.get("master_backlog_plan_revision"),
        "master_backlog": status.get("master_backlog", []),
        "problems": problems,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ready"] else 1


def link_milestone(
    root: Path, slug: str, milestone: str, covers: list[str], replace: bool
) -> Path:
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        status = read_status(target)
        known = {r["id"] for r in status.get("requirements", [])}
        unknown = [c for c in covers if c not in known]
        if unknown:
            raise SystemExit(
                "link references unknown requirement IDs: "
                + ", ".join(unknown)
                + "\nAdd them first with 'requirement add'."
            )
        found = False
        for m in status["milestones"]:
            if m["name"] == milestone:
                found = True
                existing = set(m.get("covers") or [])
                new = set(covers)
                m["covers"] = sorted(new if replace else existing | new)
        if not found:
            raise SystemExit(f"Unknown milestone: {milestone}")
        write_status(target, status)
        append_ledger(target, "link", f"Linked milestone '{milestone}' to requirements; replace={replace}", covers)
    return target


def requirement_add(
    root: Path, slug: str, rid: str, description: str, rtype: str
) -> Path:
    target = ensure_active_bundle(root, slug)
    if not _is_ascii(rid) or not _is_ascii(description):
        raise SystemExit("requirement id and description must be English-only ASCII text.")
    with bundle_lock(target):
        status = read_status(target)
        if any(r["id"] == rid for r in status["requirements"]):
            raise SystemExit(f"Requirement already exists: {rid}")
        status["requirements"].append(
            {
                "id": rid,
                "description": description,
                "type": rtype,
                "created_at_utc": utc_now(),
                "state": "open",
            }
        )
        has_role_evidence = any(status.get("role_evidence", {}).get(role) for role in ROLE_NAMES)
        if status.get("implementation_ready") or status.get("ready_task_output_id") or status.get("milestones") or has_role_evidence:
            _reset_ready_for_plan_change(
                status,
                f"{rid} added after READY or execution evidence; update requirements/design/implementation",
                PLAN_UPDATE_SECTIONS,
            )
        write_status(target, status)
        append_ledger(target, "requirement-add", f"{rid}: {description}", [rid])
    return target


def master_backlog_sync(root: Path, slug: str) -> Path:
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        status = read_status(target)
        idea_text = (target / IDEA_FILE).read_text(encoding="utf-8")
        mb_ids = _master_backlog_ids_from_text(idea_text)
        if len(mb_ids) <= 1:
            raise SystemExit("backlog sync refused - master backlog requires at least two MB-* IDs in 00-idea.md.")
        existing = _master_backlog_item_map(status)
        items = []
        for mb_id in mb_ids:
            old = existing.get(mb_id, {})
            items.append(
                {
                    "id": mb_id,
                    "title": _master_backlog_label_from_text(idea_text, mb_id),
                    "status": old.get("status") if old.get("status") in MASTER_BACKLOG_STATUSES else "pending",
                    "covered_by": old.get("covered_by", []),
                    "deferred_reason": old.get("deferred_reason", ""),
                }
            )
        status["master_backlog_required"] = True
        status["master_backlog"] = items
        status["master_backlog_synced_at_utc"] = utc_now()
        status["master_backlog_plan_revision"] = status.get("plan_revision")
        status["master_backlog_event_sequence"] = _next_event_sequence(status)
        write_status(target, status)
        append_ledger(target, "backlog-sync", "Synced master backlog: " + ", ".join(mb_ids), [])
    return target


def master_backlog_mark(root: Path, slug: str, mb_id: str, item_status: str, reason: str) -> Path:
    mb_id = mb_id.upper()
    item_status = item_status.lower()
    if item_status not in MASTER_BACKLOG_STATUSES:
        raise SystemExit("backlog mark refused - --status must be one of: " + ", ".join(MASTER_BACKLOG_STATUSES))
    if not _is_ascii(reason):
        raise SystemExit("backlog mark refused - --reason must be English-only ASCII text.")
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        status = read_status(target)
        items = _master_backlog_item_map(status)
        if mb_id not in items:
            raise SystemExit(f"backlog mark refused - unknown master backlog ID: {mb_id}. Run backlog sync first.")
        item = items[mb_id]
        item["status"] = item_status
        if item_status == "deferred":
            if _weak_text_value(reason, min_len=8):
                raise SystemExit("backlog mark refused - deferred items require a concrete --reason.")
            item["deferred_reason"] = reason
        item["updated_at_utc"] = utc_now()
        item["update_reason"] = reason
        status["master_backlog_event_sequence"] = _next_event_sequence(status)
        write_status(target, status)
        append_ledger(target, "backlog-mark", f"{mb_id} -> {item_status}: {reason}", [])
    return target


def master_backlog_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    problems = _master_backlog_problems(target, status)
    payload = {
        "path": str(target),
        "required": status.get("master_backlog_required"),
        "plan_revision": status.get("master_backlog_plan_revision"),
        "items": status.get("master_backlog", []),
        "incomplete": _master_backlog_incomplete_items(status),
        "problems": problems,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not problems else 1


def requirement_remove(root: Path, slug: str, rid: str) -> Path:
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        status = read_status(target)
        has_role_evidence = any(status.get("role_evidence", {}).get(role) for role in ROLE_NAMES)
        if status.get("milestones") or status.get("blocks") or has_role_evidence or status.get("implementation_ready"):
            raise SystemExit(
                "requirement remove is allowed only before execution starts: no milestones, role evidence, blockers, or READY implementation gate."
            )
        before = len(status["requirements"])
        status["requirements"] = [r for r in status["requirements"] if r["id"] != rid]
        if len(status["requirements"]) == before:
            raise SystemExit(f"Unknown requirement: {rid}")
        write_status(target, status)
        append_ledger(target, "requirement-remove", f"Removed {rid} before execution started")
    return target


def requirement_list(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    coverage = _coverage_by_requirement(status)
    rows = []
    for r in status["requirements"]:
        covers = coverage.get(r["id"], [])
        rows.append({
            "id": r["id"],
            "type": r.get("type", "functional"),
            "state": r.get("state", "open"),
            "description": r["description"],
            "covered_by": [c["name"] for c in covers],
            "aggregate_gate": _aggregate_gate(covers),
        })
    print(json.dumps({"path": str(target), "requirements": rows}, indent=2, ensure_ascii=False))
    return 0


def local_record_add(root: Path, slug: str, record_id: str, kind: str, text: str, covers: list[str]) -> Path:
    target = ensure_active_bundle(root, slug)
    kind = kind.strip().upper()
    if kind not in LOCAL_RECORD_KINDS:
        raise SystemExit(f"Unknown local record kind: {kind}. Expected one of: {', '.join(LOCAL_RECORD_KINDS)}")
    if not _is_ascii(record_id) or not _is_ascii(text):
        raise SystemExit("record id and text must be English-only ASCII text.")
    if _weak_text_value(text, min_len=8):
        raise SystemExit("record text is too vague")
    with bundle_lock(target):
        status = read_status(target)
        known_ids = {r["id"] for r in status.get("requirements", [])}
        unknown = [c for c in covers if c not in known_ids]
        if unknown and known_ids:
            raise SystemExit(
                "record --covers references unknown requirement IDs: "
                + ", ".join(unknown)
                + "\nAdd them first with 'requirement add' or drop them from --covers."
            )
        if any(r.get("id") == record_id for r in status.get("local_records", [])):
            raise SystemExit(f"Local record already exists: {record_id}")
        entry = {
            "timestamp_utc": utc_now(),
            "id": record_id,
            "kind": kind,
            "kind_label": LOCAL_RECORD_KINDS[kind],
            "text": text,
            "covers": covers,
            "plan_revision": status.get("plan_revision", 0),
        }
        status.setdefault("local_records", []).append(entry)
        write_status(target, status)
        append_ledger(target, f"record-{kind}", f"{record_id}: {text}", covers)
    return target


def local_record_list(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    print(json.dumps({"path": str(target), "records": status.get("local_records", [])}, indent=2, ensure_ascii=False))
    return 0


def _meaningful_evidence(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip()).lower()
    if not normalized:
        return False
    weak = {
        "done",
        "complete",
        "completed",
        "implemented",
        "tested",
        "reviewed",
        "looks good",
        "all good",
        "passed",
        "ok",
        "n/a",
        "none",
        "recorded",
    }
    if normalized in weak:
        return False
    return bool(
        re.search(r"\bREQ-\d+\b|\bTASK-\d+\b|\bIMP-\d+\b|\bACCEPT-\d+\b", text)
        or re.search(r"\b(npm|pnpm|yarn|node|python|pytest|cargo|go test|dotnet|mvn|gradle|git)\b", text, re.I)
        or re.search(r"\b(real-product-path|mock-only|fixture-only|source-only|dom-only|manual-inspection|unverified)\b", text, re.I)
        or re.search(r"[\\/][\w.-]+|[\w.-]+\.(md|ts|tsx|js|jsx|py|go|rs|java|cs|json|yaml|yml)", text, re.I)
    )


def _role_specific_evidence_problems(role: str, evidence: str) -> list[str]:
    lowered = evidence.lower()
    problems: list[str] = []
    if role == "planner":
        if re.search(r"\b(?:validator|validated|ran|pytest|unittest|reviewer|closer)\b", lowered):
            problems.append("Planner evidence must describe planning work, not validation/review/closeout work")
        if not re.search(r"\bREQ-\d+\b", evidence):
            problems.append("Planner evidence must name planned REQ IDs")
        if not re.search(r"\b(00-idea\.md|implementation plan|TASK-\d+|IMP-\d+)\b", evidence, re.I):
            problems.append("Planner evidence must reference the implementation plan or TASK/IMP IDs")
        if not re.search(r"\b(acceptance matrix|00-idea\.md|requirements)\b", evidence, re.I):
            problems.append("Planner evidence must reference requirements or the acceptance matrix")
    elif role == "implementer":
        if re.search(r"\b(?:planner|validator|reviewer|closer|validated|reviewed)\b", lowered):
            problems.append("Implementer evidence must describe implementation work, not another role")
        if not re.search(r"\b(TASK-\d+|IMP-\d+)\b", evidence):
            problems.append("Implementer evidence must name implemented TASK/IMP IDs")
        if not re.search(r"\b(implemented|changed|updated|created|modified|wired|added|removed|refactored)\b", lowered):
            problems.append("Implementer evidence must describe concrete implementation work")
        if not re.search(r"[\\/][\w.-]+|[\w.-]+\.(md|ts|tsx|js|jsx|py|go|rs|java|cs|json|yaml|yml)", evidence, re.I):
            problems.append("Implementer evidence must name changed files or modules")
    elif role == "validator":
        if re.search(r"\b(?:planner|implementer|reviewer|closer)\b", lowered):
            problems.append("Validator evidence must describe validation work, not another role")
        if not re.search(r"\b(real-product-path|mock-only|fixture-only|source-only|dom-only|manual-inspection|unverified)\b", evidence, re.I):
            problems.append("Validator evidence must name a validation type")
        if not re.search(r"\b(test|verify|validated|ran|command|pytest|unittest|npm|pnpm|yarn|node|python|cargo|go test|dotnet|mvn|gradle|manual-inspection)\b", lowered):
            problems.append("Validator evidence must name validation action, command, or inspection path")
        if not re.search(r"\bREQ-\d+\b", evidence):
            problems.append("Validator evidence must name covered REQ IDs")
    elif role == "reviewer":
        if re.search(r"\b(?:planner|implementer|validator|closer)\b", lowered):
            problems.append("Reviewer evidence must describe review work, not another role")
        if not re.search(r"\b(review|checked|scope|diff|risk|coverage|acceptance matrix|boundary|architecture|residual)\b", lowered):
            problems.append("Reviewer evidence must describe scope, coverage, boundary, or risk review")
        if not re.search(r"\b(00-idea\.md|01-progress\.md|REQ-\d+|TASK-\d+|IMP-\d+)\b", evidence, re.I):
            problems.append("Reviewer evidence must reference reviewed requirements, implementation, verification, or IDs")
        if not re.search(r"\b(same-agent review|independent review|hybrid-team|independent-team)\b", lowered):
            problems.append(
                "Reviewer evidence must disclose role independence with same-agent review, independent review, hybrid-team, or independent-team"
            )
    elif role == "closer":
        closer_role_text = re.sub(
            r"\b(prior|previous|earlier)?\s*role evidence (is|are)?\s*current\b",
            " ",
            lowered,
        )
        closer_role_text = re.sub(
            r"\b(prior|previous|earlier)\s+(planner|implementer|validator|reviewer)\s+evidence (is|are)?\s*current\b",
            " ",
            closer_role_text,
        )
        if re.search(r"\b(?:planner|implementer|validator|reviewer)\b", closer_role_text):
            problems.append("Closer evidence must describe closeout work, not another role")
        if not re.search(r"\bpre-close\b.*\bverify\b|\bverify\b.*\bpassed\b", lowered):
            problems.append("Closer evidence must state pre-close verify passed")
        if not re.search(r"\b(accepted|pass|partial|fail|decision|final|covered|REQ-\d+)\b", evidence, re.I):
            problems.append("Closer evidence must state final decision/gate alignment or REQ coverage")
    return problems


def _is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _weak_text_value(text: str, min_len: int = 8) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    weak_values = {"", "-", "x", "xx", "xxx", "tbd", "todo", "n/a", "na", "none", "unknown", "pending"}
    if normalized in weak_values or len(normalized) < min_len:
        return True
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    if compact and len(set(compact)) <= 2:
        return True
    return False


def _status_ascii_problems(status: dict) -> list[str]:
    problems: list[str] = []

    def walk(value, path: str) -> None:
        if isinstance(value, str):
            if not _is_ascii(value):
                problems.append(f"{STATE_FILE}: non-ASCII text at {path}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}")

    walk(status, "status")
    return problems


def role_record(root: Path, slug: str, role: str, evidence: str, covers: list[str]) -> Path:
    target = ensure_active_bundle(root, slug)
    role_key = role.lower()
    if role_key not in ROLE_NAMES:
        raise SystemExit(f"Unknown role: {role}. Expected one of: {', '.join(ROLE_NAMES)}")
    if not _is_ascii(evidence):
        raise SystemExit("role evidence must be English-only ASCII text.")
    if not _meaningful_evidence(evidence):
        raise SystemExit(
            "role evidence is too vague. Name concrete acceptance/requirement IDs, "
            "files, commands, validation type, or observed artifacts."
        )
    role_specific_problems = _role_specific_evidence_problems(role_key, evidence)
    if role_specific_problems:
        raise SystemExit(
            "role evidence does not satisfy "
            + role_key
            + " responsibilities:\n  - "
            + "\n  - ".join(role_specific_problems)
        )
    with bundle_lock(target):
        status = read_status(target)
        plan_revision = int(status.get("plan_revision", 0))
        role_index = ROLE_NAMES.index(role_key)
        if role_index > 0:
            previous_role = ROLE_NAMES[role_index - 1]
            previous_entries = [
                entry for entry in status.get("role_evidence", {}).get(previous_role, [])
                if entry.get("plan_revision") == plan_revision
            ]
            if not previous_entries:
                raise SystemExit(
                    f"role evidence order violation: record {previous_role} evidence for plan revision {plan_revision} before {role_key}."
                )
        if role_key == "closer":
            if not status.get("last_verify_ok") or status.get("last_verified_plan_revision") != plan_revision:
                raise SystemExit(
                    "closer evidence refused: run pre-close verify successfully for the current plan revision after Reviewer evidence."
                )
            reviewer_entries = [
                entry for entry in status.get("role_evidence", {}).get("reviewer", [])
                if entry.get("plan_revision") == plan_revision
            ]
            latest_reviewer = reviewer_entries[-1] if reviewer_entries else {}
            if latest_reviewer and _verify_is_older_than_entry(status, latest_reviewer):
                raise SystemExit(
                    "closer evidence refused: pre-close verify is older than the latest Reviewer evidence."
                )
        if role_key == "implementer":
            ready_output_problem = _implementer_ready_output_problem(status, evidence, target)
            if ready_output_problem:
                raise SystemExit("implementer evidence refused - " + ready_output_problem)
            pre_edit_problems = _pre_edit_compliance_problems(target, status)
            if pre_edit_problems:
                raise SystemExit("implementer evidence refused - " + "; ".join(pre_edit_problems))
        if _evidence_claims_independent_delegation(evidence):
            if not _usable_delegation_records(status, role_key):
                raise SystemExit(
                    f"{role_key} evidence refused - independent/subagent/fresh-agent claim requires a usable delegation record for plan revision {plan_revision}."
                )
        known_ids = {r["id"] for r in status.get("requirements", [])}
        unknown = [c for c in covers if c not in known_ids]
        if unknown and known_ids:
            raise SystemExit(
                "role evidence --covers references unknown requirement IDs: "
                + ", ".join(unknown)
                + "\nAdd them first with 'requirement add' or drop them from --covers."
            )
        entry = {
            "timestamp_utc": utc_now(),
            "event_sequence": _next_event_sequence(status),
            "role": role_key,
            "evidence": evidence,
            "covers": covers,
            "plan_revision": plan_revision,
        }
        status.setdefault("role_evidence", {}).setdefault(role_key, []).append(entry)
        write_status(target, status)
        append_ledger(target, f"role-{role_key}", evidence, covers)
        rewrite_role_gates(target / PROGRESS_FILE, status)
    return target


def role_explain(role: str | None = None) -> int:
    roles = [role] if role else list(ROLE_NAMES)
    payload = {
        "roles": [
            {
                "role": role_name,
                **ROLE_GUIDANCE[role_name],
            }
            for role_name in roles
        ]
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _role_draft_task_files(target: Path, task_id: str | None) -> list[str]:
    if not task_id:
        return []
    try:
        return _task_files_for_id(target, task_id)
    except SystemExit:
        return []


def _role_draft_payload(target: Path, slug: str, role: str, covers: list[str], task_id: str | None) -> dict[str, Any]:
    role_key = role.lower()
    if role_key not in ROLE_NAMES:
        raise SystemExit(f"Unknown role: {role}. Expected one of: {', '.join(ROLE_NAMES)}")
    status = read_status(target)
    plan_revision = int(status.get("plan_revision", 0))
    known_reqs = {item.get("id") for item in status.get("requirements", [])}
    cover_ids = covers or sorted(item for item in known_reqs if item)
    task = (task_id or status.get("current_task_id") or "TASK-1").strip().upper()
    files = _role_draft_task_files(target, task)
    files_text = ", ".join(files) if files else "files listed in " + task
    covers_text = ", ".join(cover_ids) if cover_ids else "REQ-IDS"
    ready_id = status.get("ready_task_output_id") or "READY_TASK_OUTPUT_ID missing"
    exploration_id = status.get("exploration_output_id") or "EXPLORATION_OUTPUT_ID missing"
    pre_edit_id = status.get("pre_edit_ok_id") or "PRE_EDIT_OK_ID missing"
    blockers: list[str] = []
    if not cover_ids:
        blockers.append("no requirement IDs supplied and no requirements are registered")
    unknown = [item for item in cover_ids if known_reqs and item not in known_reqs]
    if unknown:
        blockers.append("unknown requirement IDs: " + ", ".join(unknown))
    if role_key in {"planner", "implementer"} and not status.get("ready_task_output_id"):
        blockers.append("READY_TASK_OUTPUT_ID missing; run implementation ready before recording this role")
    if role_key == "implementer" and status.get("pre_edit_guard_required") and not status.get("pre_edit_ok_id"):
        blockers.append("PRE_EDIT_OK_ID missing; run implementation pre-edit before recording implementer evidence")
    if role_key == "closer" and not status.get("last_verify_ok"):
        blockers.append("pre-close verify has not passed")

    if role_key == "planner":
        evidence = (
            f"{task} / {covers_text} planner evidence: requirements and Acceptance Matrix in 00-idea.md define "
            f"{covers_text}; implementation plan covers {task} files {files_text}. "
            f"EXPLORATION_OUTPUT_ID {exploration_id}. READY_TASK_OUTPUT_ID {ready_id}."
        )
    elif role_key == "implementer":
        evidence = (
            f"{task} / {covers_text} source-only implementation updated {files_text}. "
            f"READY_TASK_OUTPUT_ID {ready_id}. PRE_EDIT_OK_ID {pre_edit_id}."
        )
    elif role_key == "validator":
        evidence = (
            f"{task} / {covers_text} validation type source-only passed. Commands: name the exact command output "
            "or inspection evidence before recording this draft."
        )
    elif role_key == "reviewer":
        evidence = (
            f"{task} / {covers_text} same-agent review checked scope, diff, acceptance matrix, validation strength, "
            "boundary conditions, and residual risks."
        )
    else:
        evidence = (
            f"{task} / {covers_text} closeout work: pre-close verify passed; prior role evidence is current; "
            f"{covers_text} covered by passing milestone evidence; final decision pass accepted or accepted-with-followup."
        )

    command = (
        f'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" role record '
        f'--root . --slug {slug} --role {role_key} --covers {",".join(cover_ids) if cover_ids else "REQ-1"} '
        '--evidence "EVIDENCE_FROM_DRAFT"'
    )
    return {
        "schema": "idea-to-code.role-evidence-draft.v1",
        "bundle": slug,
        "role": role_key,
        "task": task,
        "covers": cover_ids,
        "plan_revision": plan_revision,
        "ready_task_output_id": status.get("ready_task_output_id"),
        "exploration_output_id": status.get("exploration_output_id"),
        "pre_edit_ok_id": status.get("pre_edit_ok_id"),
        "files": files,
        "ready_to_record": not blockers,
        "blockers": blockers,
        "evidence": evidence,
        "record_command": command,
    }


def role_draft(root: Path, slug: str, role: str, covers: list[str], task_id: str | None, json_only: bool) -> int:
    target = ensure_active_bundle(root, slug)
    payload = _role_draft_payload(target, slug, role, covers, task_id)
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload["ready_to_record"] else 1
    role_label = payload["role"].capitalize()
    print(f"[idea-to-code][{role_label}/agent] Role Evidence Draft | Bundle: {slug}")
    print()
    print("Display Layer: Role Evidence Draft")
    print(f"Role: {payload['role']}")
    print(f"Task: {payload['task']}")
    print("Covers: " + (", ".join(payload["covers"]) if payload["covers"] else "none"))
    print("Ready To Record: " + ("yes" if payload["ready_to_record"] else "no"))
    if payload["blockers"]:
        print("Blockers:")
        for blocker in payload["blockers"]:
            print(f"- {blocker}")
    print("Evidence Draft:")
    print(payload["evidence"])
    print("Record Command:")
    print(payload["record_command"])
    return 0 if payload["ready_to_record"] else 1


def current_status(root: Path) -> int:
    current = read_current(root)
    if not current:
        print(json.dumps({"ok": False, "current": None}, indent=2, ensure_ascii=False))
        return 1
    slug = current.get("slug", "")
    target = bundle_dir(root, slug)
    payload = {"ok": target.exists(), "current": current, "bundle_exists": target.exists()}
    if target.exists() and state_exists(target):
        payload["bundle_status"] = read_status(target)
        payload["implementation_gate"] = {
            "ready": not implementation_gate_problems(target),
            "problems": implementation_gate_problems(target),
        }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


def contract() -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "standard_bundle_files": list(ARTIFACT_RESPONSIBILITIES),
        "artifact_responsibilities": ARTIFACT_RESPONSIBILITIES,
        "role_artifact_map": ROLE_ARTIFACT_MAP,
        "local_record_kinds": LOCAL_RECORD_KINDS,
        "bundle_states": ["in_progress", "blocked", "paused", "completed", "closed"],
        "phase_examples": ["planning", "ready_to_implement", "in_progress", "paused", "accepted", "closed"],
        "role_order": list(ROLE_NAMES),
        "route_gates": [
            "execution-ready",
            "skip-delivery",
            "read-only",
            "init-required",
            "archive-current-first",
            "plan-update-required",
            "implementation-ready-required",
            "resume-required",
            "unblock-required",
            "pause",
        ],
        "contract_rules": [
            "Do not add ad hoc top-level markdown files to a bundle.",
            "state.json is the machine-readable state source.",
            "01-progress.md is the unified human event ledger.",
            "Role evidence must be recorded in order for the current plan revision.",
            "verify/finalize enforce the artifact contract.",
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _route_classification(user_input: str, has_active_current: bool) -> tuple[str, bool, str]:
    """Return a conservative routing recommendation for the next user input."""
    text = user_input.strip().lower()
    if re.search(r"\b(fix|correct|update)\s+(a\s+)?(typo|spelling|grammar|comment)\b", text) or re.search(
        r"\b(rename|format|reformat)\b.*\b(readme|comment|label|variable|file)\b", text
    ):
        return (
            "no-op",
            False,
            "This looks like a one-shot mechanical edit. Skip idea-to-code delivery unless the user explicitly invoked it or the edit changes behavior.",
        )
    if not has_active_current:
        return (
            "new-task",
            False,
            "No active bundle exists. Initialize a new current bundle before editing.",
        )
    if re.search(r"\b(status|progress|where are we|what is left|what remains|done yet)\b", text):
        return (
            "status",
            False,
            "Inspect the active bundle and report status without editing product files.",
        )
    if re.search(r"\b(stop|pause|wait|hold|do not continue|don't continue)\b", text):
        return (
            "pause",
            False,
            "Record a pause on the active bundle and stop after the current safe operation.",
        )
    if re.search(r"\b(blocked|can't proceed|cannot proceed|missing credential|permission denied|external dependency)\b", text):
        return (
            "blocked",
            False,
            "Record a blocker on the active bundle with the concrete dependency needed.",
        )
    if has_active_current and _looks_like_other_session(text):
        return (
            "continue",
            False,
            "Input looks like another session while a session ledger is active. Require a scope decision before mutating any bundle.",
        )
    if re.search(r"\b(new task|unrelated|separate task|another task|different task)\b", text):
        return (
            "new-task",
            False,
            "Record the new-task decision on the active bundle, archive it with a reason, then initialize the new bundle.",
        )
    if has_active_current and re.search(
        r"\b(build|create|make|develop|implement|design)\b.*\b(app|dashboard|system|platform|workflow|feature|integration|tool|page|api|service)\b",
        text,
    ):
        return (
            "expand",
            True,
            "Record a new IDEA scope inside the active session ledger, update requirements/design/implementation, and rerun the implementation gate.",
        )
    if re.search(r"\b(replace|instead|switch to|change goal|different direction)\b", text):
        return (
            "switch",
            True,
            "Record a plan-changing switch, update requirements/design/implementation, then continue in the same bundle.",
        )
    if re.search(r"\b(add|also|include|support|extend|expand|another case|edge case)\b", text):
        return (
            "expand",
            True,
            "Record a plan-changing expansion, update requirements/design/implementation, and rerun the implementation gate.",
        )
    if re.search(r"\b(clarify|actually|correction|means|should be|instead of)\b", text):
        return (
            "clarification",
            True,
            "Record a plan-changing clarification, update requirements/design/implementation, and rerun the implementation gate.",
        )
    return (
        "continue",
        False,
        "Treat this as part of the active bundle. Record the input if it affects execution, then continue the current plan.",
    )


def _route_need_confirmation(user_input: str, classification: str, has_active_current: bool) -> tuple[bool, str]:
    text = user_input.lower()
    if classification in {"status", "pause", "no-op"}:
        return False, "Read-only or control request does not start implementation."
    if classification in {"expand", "switch", "clarification"}:
        return True, "Plan-changing input must update intake and requirements before implementation continues."
    if has_active_current:
        return False, "Existing bundle intake and implementation gates control execution."
    risky = re.search(
        r"\b(build|create|make|develop|implement|add|improve|optimize|design)\b.*\b(app|dashboard|system|platform|workflow|feature|integration|auth|payment|database|migration|security)\b",
        text,
    )
    vague = re.search(r"\b(something|anything|whatever|better|optimize|improve it|make it good|dashboard|app|system|platform)\b", text)
    if risky or vague:
        return True, "New idea appears broad or multi-interpretation; capture it, ask for confirmation, and keep Need Confirmation: yes until clarified."
    return False, "Request appears concrete enough for intake capture with Need Confirmation: no if acceptance criteria are explicit."


def _looks_like_other_session(text: str) -> re.Match[str] | None:
    return re.search(
        r"\b(other session|another session|different session|new session|separate session)\b",
        text,
    )


def _route_scope_decision_required(user_input: str, classification: str, has_active_current: bool) -> tuple[bool, str]:
    if not has_active_current or classification not in {"continue"}:
        return False, ""
    text = user_input.lower()
    if _looks_like_other_session(text):
        return (
            True,
            "Input looks like a different session while another session ledger is active. Confirm whether to continue the active session slug or archive it and start a new session slug.",
        )
    return False, ""


def route_task(root: Path, user_input: str) -> int:
    """Read-only mission-control router for arbitrary incoming task text."""
    if not _is_ascii(user_input):
        raise SystemExit("route --input must be English-only ASCII text. Summarize non-English input in English first.")
    current = read_current(root)
    active = None
    has_active_current = False
    active_state = None
    pending_plan_update = False
    pending_plan_update_sections: list[str] = []
    active_implementation_ready = False
    active_gate_problems: list[str] = []
    active_unresolved_blockers = 0
    if current:
        slug = current.get("slug", "")
        target = bundle_dir(root, slug)
        active = {
            "slug": slug,
            "path": str(Path(".idea-to-code") / slug),
            "exists": target.exists(),
            "status": current.get("status"),
        }
        if target.exists() and state_exists(target):
            status = read_status(target)
            active_state = status.get("state")
            pending_plan_update = bool(status.get("pending_plan_update"))
            pending_plan_update_sections = [
                section
                for section in status.get("pending_plan_update_sections", [])
                if section in PLAN_UPDATE_SECTIONS
            ]
            active_implementation_ready = bool(status.get("implementation_ready"))
            active_gate_problems = implementation_gate_problems(target) if active_state not in {"completed", "closed"} else []
            active_unresolved_blockers = len(_unresolved_block_indexes(status))
            active.update(
                {
                    "state": active_state,
                    "phase": status.get("phase"),
                    "implementation_ready": active_implementation_ready,
                    "implementation_gate_problems": active_gate_problems,
                    "unresolved_blockers": active_unresolved_blockers,
                    "pending_plan_update": pending_plan_update,
                    "pending_plan_update_sections": pending_plan_update_sections,
                    "plan_revision": status.get("plan_revision"),
                    "title": status.get("title"),
                    "current_focus": status.get("current_focus"),
                    "open_requirements": [
                        r.get("id")
                        for r in status.get("requirements", [])
                        if r.get("state") != "closed"
                    ],
                }
            )
            has_active_current = active_state not in {"completed", "closed"}
    classification, changes_plan, action = _route_classification(user_input, has_active_current)
    scope_decision_required, scope_decision_reason = _route_scope_decision_required(user_input, classification, has_active_current)
    need_confirmation, confirmation_reason = _route_need_confirmation(user_input, classification, has_active_current)
    requires_resume = active_state == "paused" and classification not in {"status", "pause", "new-task"}
    requires_unblock = (
        active_state != "paused"
        and active_unresolved_blockers > 0
        and classification not in {"status", "new-task", "pause"}
    )
    plan_update_applies = classification not in {"status", "pause", "new-task", "no-op", "blocked"}
    must_update_plan = (pending_plan_update and plan_update_applies) or changes_plan
    can_edit_product_files = bool(
        has_active_current
        and not requires_resume
        and not requires_unblock
        and not scope_decision_required
        and not must_update_plan
        and active_implementation_ready
        and not active_gate_problems
        and classification not in {"status", "pause", "blocked", "new-task"}
    )
    state_actions = []
    if requires_resume:
        state_actions.append("Current bundle is paused. Run current resume with a reason before mutating it.")
    if requires_unblock:
        state_actions.append("Current bundle is blocked. Resolve the dependency and run unblock before mutating it.")
    if pending_plan_update and not scope_decision_required:
        stale = ", ".join(pending_plan_update_sections) if pending_plan_update_sections else "requirements/design/implementation"
        state_actions.append(f"A pending plan update already exists. Update stale plan sections ({stale}) and rerun implementation ready before editing product files.")
    if scope_decision_required:
        state_actions.append(scope_decision_reason)
    if (
        has_active_current
        and classification not in {"status", "pause", "blocked", "new-task", "no-op"}
        and not must_update_plan
        and (not active_implementation_ready or active_gate_problems)
    ):
        state_actions.append("Implementation gate is not READY. Update requirements/design/implementation and rerun implementation ready before editing product files.")
    if state_actions:
        action = " ".join(state_actions + [action])
    required_next_commands: list[str] = []
    route_gate = "ready"
    active_slug = active.get("slug") if isinstance(active, dict) else "<slug>"
    if classification == "no-op":
        route_gate = "skip-delivery"
    elif classification == "status":
        route_gate = "read-only"
        required_next_commands.append("current status --root <root>")
    elif classification == "pause":
        route_gate = "pause"
        required_next_commands.append('current pause --root <root> --reason "<reason>"')
    elif not has_active_current and classification == "new-task":
        route_gate = "init-required"
        required_next_commands.append('init --root <root> --slug <slug> --title "<title>" --unique --idea "<idea>"')
    elif classification == "new-task":
        route_gate = "archive-current-first"
        required_next_commands.extend(
            [
                f'user-input record --root <root> --slug {active_slug} --classification new-task --changes-plan no ...',
                'current archive --root <root> --reason "<parked reason>"',
                'init --root <root> --slug <slug> --title "<title>" --unique --idea "<idea>"',
            ]
        )
    if requires_resume:
        route_gate = "resume-required"
        required_next_commands.insert(0, 'current resume --root <root> --reason "<resume reason>"')
    if requires_unblock:
        route_gate = "unblock-required"
        required_next_commands.insert(0, 'unblock --root <root> --slug <slug> --note "<resolution>"')
    if scope_decision_required:
        route_gate = "scope-decision-required"
        required_next_commands.extend(
            [
                f'user-input record --root <root> --slug {active_slug} --classification new-task|clarification|expand --changes-plan no|yes ...',
                'current archive --root <root> --reason "<parked reason>"  # only if this is a separate session/task scope',
                'init --root <root> --slug <slug> --title "<title>" --unique --idea "<idea>"  # only for separate/follow-up scope',
            ]
        )
    if must_update_plan and not scope_decision_required:
        if not scope_decision_required:
            route_gate = "plan-update-required"
        if changes_plan:
            required_next_commands.append(
                f'user-input record --root <root> --slug {active_slug} --classification {classification} --changes-plan yes ...'
            )
        required_next_commands.extend(
            [
                *[
                    f'update --root <root> --slug {active_slug} --file {section} --content-file <{section}.md>'
                    for section in (pending_plan_update_sections or list(PLAN_UPDATE_SECTIONS))
                ],
                f'implementation ready --root <root> --slug {active_slug}',
                f'role record --root <root> --slug {active_slug} --role planner --covers <REQ-IDs> --evidence "<planning evidence>"',
            ]
        )
    elif (
        has_active_current
        and not scope_decision_required
        and classification not in {"status", "pause", "blocked", "new-task", "no-op"}
        and (not active_implementation_ready or active_gate_problems)
    ):
        route_gate = "implementation-ready-required"
        required_next_commands.extend(
            [
                f'update --root <root> --slug {active_slug} --file requirements --content-file <requirements.md>',
                f'update --root <root> --slug {active_slug} --file implementation --content-file <implementation.md>',
                f'implementation ready --root <root> --slug {active_slug}',
                f'role record --root <root> --slug {active_slug} --role planner --covers <REQ-IDs> --evidence "<planning evidence>"',
            ]
        )
    elif can_edit_product_files and classification == "continue":
        route_gate = "execution-ready"
    if requires_unblock:
        route_gate = "unblock-required"
    elif requires_resume:
        route_gate = "resume-required"
    elif scope_decision_required:
        route_gate = "scope-decision-required"
    elif must_update_plan:
        route_gate = "plan-update-required"
    payload = {
        "ok": True,
        "active_bundle": active,
        "recommended_classification": classification,
        "recommended_need_confirmation": need_confirmation,
        "confirmation_reason": confirmation_reason,
        "route_gate": route_gate,
        "changes_plan": changes_plan,
        "must_update_plan_before_code": must_update_plan,
        "scope_decision_required": scope_decision_required,
        "scope_decision_reason": scope_decision_reason,
        "requires_resume": requires_resume,
        "requires_unblock": requires_unblock,
        "can_edit_product_files": can_edit_product_files,
        "required_next_commands": required_next_commands,
        "next_action": action,
        "must_not": [
            "Do not edit product files before resolving this route.",
            "Do not initialize a new bundle over an unfinished current bundle.",
            "Do not mutate a non-current bundle.",
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def doctor(root: Path) -> int:
    """Inspect project governance and active idea-to-code state."""
    required_governance_candidates = [
        "AGENTS.md",
        "CONTRIBUTING.md",
    ]
    found = []
    missing = []
    for rel in required_governance_candidates:
        path = root / rel
        if path.exists():
            found.append(rel)
        else:
            missing.append(rel)
    optional_found = []
    docs_dir = root / "docs"
    if docs_dir.exists():
        for path in sorted(docs_dir.rglob("*.md")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root)).replace("\\", "/")
            found.append(rel)
            optional_found.append(rel)

    current = read_current(root)
    active_bundle = None
    active_gate = None
    if current:
        slug = current.get("slug", "")
        target = bundle_dir(root, slug)
        active_bundle = {
            "slug": slug,
            "exists": target.exists(),
            "path": str(Path(".idea-to-code") / slug),
        }
        if target.exists() and state_exists(target):
            status = read_status(target)
            active_gate = {
                "phase": status.get("phase"),
                "state": status.get("state"),
                "implementation_ready": bool(status.get("implementation_ready")),
                "implementation_problems": implementation_gate_problems(target),
            "role_evidence_problems": _role_gate_problems(status),
            }

    payload = {
        "root": str(root),
        "english_only": True,
        "project_governance_found": found,
        "project_governance_missing": missing,
        "project_governance_optional_found": optional_found,
        "has_project_agent_entry": "AGENTS.md" in found,
        "active_bundle": active_bundle,
        "active_gate": active_gate,
        "recommendations": [
            "Read project governance files found by doctor before planning or editing.",
            "Use direct-trigger delivery by default; stop at planning only when explicitly requested.",
            "Run verify before accepted finalize or completed closeout.",
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def current_set(root: Path, slug: str) -> Path:
    with current_lock(root):
        return _current_set_locked(root, slug)


def _current_set_locked(root: Path, slug: str) -> Path:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    if status.get("state") in {"completed", "closed"}:
        raise SystemExit(f"Cannot set {status.get('state')} bundle as current. Start a new bundle instead.")
    current = read_current(root)
    if current and current.get("slug") != slug:
        current_slug = current.get("slug", "")
        current_target = bundle_dir(root, current_slug)
        if not current_target.exists() or not state_exists(current_target):
            raise SystemExit("Cannot switch current because the existing current pointer is invalid. Inspect and repair it explicitly.")
        current_status = read_status(current_target)
        if current_status.get("state") not in {"completed", "closed"}:
            raise SystemExit(
                f"Cannot switch current from unfinished bundle '{current_slug}' to '{slug}'. "
                "Archive the current bundle first with a reason."
            )
    write_current(root, slug, status.get("phase") or status.get("state", "in_progress"))
    return target


def current_clear(root: Path) -> Path:
    with current_lock(root):
        path = current_path(root)
        if path.exists():
            current = read_current(root)
            current_slug = current.get("slug", "") if current else ""
            current_target = bundle_dir(root, current_slug)
            if current_target.exists() and state_exists(current_target):
                status = read_status(current_target)
                if status.get("state") not in {"completed", "closed"}:
                    raise SystemExit(
                        f"current clear refused because active bundle '{current_slug}' is unfinished. "
                        "Use current archive with a reason to park it."
                    )
            path.unlink()
        return path


def current_archive(root: Path, reason: str) -> Path:
    if not _is_ascii(reason):
        raise SystemExit("archive reason must be English-only ASCII text.")
    with current_lock(root):
        current = read_current(root)
        if not current:
            raise SystemExit("No .idea-to-code/current.json exists.")
        slug = current.get("slug")
        target = ensure_bundle(root, slug)
        status = read_status(target)
        append_history(root, slug, status, reason)
        append_ledger(target, "archive", f"Archived current bundle: {reason}")
        current_path(root).unlink(missing_ok=True)
        return history_index_path(root)


def current_pause(root: Path, reason: str) -> Path:
    if not _is_ascii(reason):
        raise SystemExit("pause reason must be English-only ASCII text.")
    with current_lock(root):
        current = read_current(root)
        if not current:
            raise SystemExit("No .idea-to-code/current.json exists.")
        slug = current.get("slug")
        target = ensure_bundle(root, slug)
        with bundle_lock(target):
            status = read_status(target)
            if status.get("state") in {"completed", "closed"}:
                raise SystemExit(f"Cannot pause {status.get('state')} bundle.")
            status["phase"] = "paused"
            status["state"] = "paused"
            status["current_focus"] = f"PAUSED: {reason}"
            write_status(target, status)
            current["status"] = "paused"
            current["updated_at_utc"] = utc_now()
            current["pause_reason"] = reason
            current_path(root).write_text(
                json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with (target / EXECUTION_LOG_FILE).open("a", encoding="utf-8") as f:
                f.write(f"## Paused at {utc_now()}\n\n- Reason: {reason}\n\n")
            append_ledger(target, "pause", f"Paused: {reason}")
        return target


def current_resume(root: Path, reason: str, slug: str | None = None) -> Path:
    if not _is_ascii(reason):
        raise SystemExit("resume reason must be English-only ASCII text.")
    with current_lock(root):
        return _current_resume_locked(root, reason, slug)


def _current_resume_locked(root: Path, reason: str, slug: str | None = None) -> Path:
    selected_by_slug = slug is not None
    if selected_by_slug:
        target = _current_set_locked(root, slug)
        current = read_current(root)
    else:
        current = read_current(root)
        if not current:
            raise SystemExit("No .idea-to-code/current.json exists. Use current resume --slug <slug> when the active pointer was lost.")
        target = ensure_bundle(root, current.get("slug"))
    if not current:
        raise SystemExit("No .idea-to-code/current.json exists.")
    slug = current.get("slug")
    with bundle_lock(target):
        status = read_status(target)
        if status.get("state") != "paused":
            if selected_by_slug:
                current["status"] = status.get("phase") or status.get("state", "in_progress")
                current["updated_at_utc"] = utc_now()
                current["resume_reason"] = reason
                current.pop("pause_reason", None)
                current_path(root).write_text(
                    json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                append_ledger(target, "resume", f"Selected unfinished slug for resume: {reason}")
                return target
            raise SystemExit("Current bundle is not paused.")
        unresolved_indexes = _unresolved_block_indexes(status)
        if unresolved_indexes:
            latest = status.get("blocks", [])[unresolved_indexes[-1]]
            status["phase"] = "blocked"
            status["state"] = "blocked"
            status["current_focus"] = f"BLOCKED: {latest.get('reason', '')}"
            status["next_gate"] = f"unblock: {latest.get('need', '')}"
        else:
            status["phase"] = "planning" if not status.get("implementation_ready") else "in_progress"
            status["state"] = "in_progress"
            status["current_focus"] = f"RESUMED: {reason}"
        write_status(target, status)
        current["status"] = status["phase"]
        current["updated_at_utc"] = utc_now()
        current["resume_reason"] = reason
        current.pop("pause_reason", None)
        current_path(root).write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        with (target / EXECUTION_LOG_FILE).open("a", encoding="utf-8") as f:
            f.write(f"## Resumed at {utc_now()}\n\n- Reason: {reason}\n\n")
        append_ledger(target, "resume", f"Resumed: {reason}")
    return target


def _coverage_by_requirement(status: dict) -> dict[str, list[dict]]:
    coverage: dict[str, list[dict]] = {}
    for m in status.get("milestones", []):
        for rid in m.get("covers", []) or []:
            coverage.setdefault(rid, []).append(m)
    return coverage


def _aggregate_gate(covering_milestones: list[dict]) -> str:
    """Aggregate gate-status across the covering milestones.

    - any 'fail' -> fail
    - any 'partial' -> partial
    - all 'pass' -> pass
    - nothing covering -> 'uncovered'
    """
    if not covering_milestones:
        return "uncovered"
    statuses = {m.get("gate_status") for m in covering_milestones}
    if "fail" in statuses:
        return "fail"
    if "partial" in statuses or None in statuses:
        return "partial"
    if statuses == {"pass"}:
        return "pass"
    return "partial"


def _render_trace_matrix(status: dict) -> str:
    requirements = status.get("requirements", [])
    if not requirements:
        return "- No explicit requirements were recorded. Use `requirement add` to start a trace matrix.\n"
    coverage = _coverage_by_requirement(status)
    lines = [
        "| ID | Type | State | Description | Covered By | Aggregate Gate |",
        "|----|------|-------|-------------|-----------|----------------|",
    ]
    for r in requirements:
        covers = coverage.get(r["id"], [])
        covered_names = ", ".join(m["name"] for m in covers) if covers else "_(uncovered)_"
        lines.append(
            f"| {r['id']} | {r.get('type', 'functional')} | {r.get('state', 'open')} | "
            f"{r['description']} | {covered_names} | {_aggregate_gate(covers)} |"
        )
    return "\n".join(lines) + "\n"


def _render_milestones_rollup(milestones: list[dict]) -> str:
    if not milestones:
        return "- No milestones were recorded.\n"
    lines: list[str] = []
    for i, m in enumerate(milestones, start=1):
        gate = f" (gate: {m['gate_status']})" if m.get("gate_status") else ""
        lines.append(f"{i}. **{m['name']}**{gate} - {m['timestamp_utc']}")
        lines.append(f"   - Delivered: {m.get('delivered', '')}")
        lines.append(f"   - Verified: {m.get('verified', '')}")
        lines.append(f"   - Next: {m.get('next', '')}")
    return "\n".join(lines) + "\n"


def _render_role_evidence(status: dict) -> str:
    role_evidence = status.get("role_evidence", {})
    lines = [
        "| Role | Latest Evidence | Covers |",
        "|------|-----------------|--------|",
    ]
    for role in ROLE_NAMES:
        entries = role_evidence.get(role) or []
        if not entries:
            lines.append(f"| {role.title()} | _(missing)_ | |")
            continue
        latest = entries[-1]
        evidence = str(latest.get("evidence", "")).replace("|", "\\|")
        covers = ", ".join(latest.get("covers") or [])
        lines.append(f"| {role.title()} | {evidence} | {covers} |")
    return "\n".join(lines) + "\n"


def _role_gate_problems(status: dict, require_closer: bool = True) -> list[str]:
    problems: list[str] = []
    role_evidence = status.get("role_evidence", {})
    plan_revision = int(status.get("plan_revision", 0))
    required_roles = ROLE_NAMES if require_closer else ROLE_NAMES[:-1]
    latest_entries: dict[str, dict] = {}
    for role in required_roles:
        entries = [
            entry for entry in (role_evidence.get(role) or [])
            if entry.get("plan_revision") == plan_revision
        ]
        if not entries:
            problems.append(f"role evidence missing for current plan revision {plan_revision}: {role}")
            continue
        latest = entries[-1]
        latest_entries[role] = latest
        evidence = str(latest.get("evidence", ""))
        if not _meaningful_evidence(evidence):
            problems.append(f"role evidence is vague: {role}")
        if not _is_ascii(evidence):
            problems.append(f"role evidence is not English-only ASCII: {role}")
        if status.get("requirements") and not latest.get("covers"):
            problems.append(f"role evidence must name covered requirement IDs: {role}")
    for earlier, later in zip(required_roles, required_roles[1:]):
        if earlier in latest_entries and later in latest_entries:
            if _entry_order_value(latest_entries[earlier]) > _entry_order_value(latest_entries[later]):
                problems.append(f"role evidence order is stale: {earlier} is newer than {later}")
    implementer_entry = latest_entries.get("implementer")
    if implementer_entry:
        evidence = str(implementer_entry.get("evidence", ""))
        ready_problem = _implementer_ready_output_problem(status, evidence)
        if ready_problem:
            problems.append("Implementer evidence READY output check failed: " + ready_problem)
        pre_edit_problems = _pre_edit_compliance_problems_for_verify(status)
        for problem in pre_edit_problems:
            problems.append("Implementer evidence pre-edit check failed: " + problem)
        ready_event_sequence = status.get("ready_task_output_event_sequence")
        if ready_event_sequence is not None and _entry_order_value(implementer_entry) <= (1, int(ready_event_sequence)):
            problems.append("Implementer evidence must be recorded after the latest READY output")
    validator_entry = latest_entries.get("validator")
    if validator_entry:
        evidence = validator_entry.get("evidence", "")
        if not re.search(r"\b(real-product-path|mock-only|fixture-only|source-only|dom-only|manual-inspection|unverified)\b", evidence, re.I):
            problems.append("Validator evidence must name a validation type")
    if require_closer and "reviewer" in latest_entries and status.get("last_verified_at_utc", ""):
        if _verify_is_older_than_entry(status, latest_entries["reviewer"]):
            problems.append("pre-close verify is older than latest Reviewer evidence")
    return problems


def _acceptance_matrix_problems(requirements_text: str, requirements: list[dict]) -> list[str]:
    problems: list[str] = []
    if "## Acceptance Matrix" not in requirements_text:
        return [f"{IDEA_FILE}: missing Acceptance Matrix section"]

    header_cells: list[str] | None = None
    rows: dict[str, list[str]] = {}
    for line in requirements_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] == "ID":
            header_cells = cells
            continue
        if not cells or not re.match(r"^[A-Z]+-\d+\b", cells[0]):
            continue
        rid_match = re.search(r"\bREQ-\d+\b", cells[0])
        rows[rid_match.group(0) if rid_match else cells[0]] = cells

    if header_cells is None:
        problems.append(f"{IDEA_FILE}: Acceptance Matrix missing header row")
    else:
        for column in ACCEPTANCE_MATRIX_COLUMNS:
            if column not in header_cells:
                problems.append(f"{IDEA_FILE}: Acceptance Matrix header missing column: {column}")

    open_requirements = [r for r in requirements if r.get("state") != "closed"]
    if not open_requirements:
        problems.append(f"{IDEA_FILE}: no open requirements recorded; accepted closeout requires at least one open REQ-* with acceptance matrix coverage")

    expected_columns = len(header_cells or ACCEPTANCE_MATRIX_COLUMNS)
    validation_type_index = (header_cells or list(ACCEPTANCE_MATRIX_COLUMNS)).index("Validation Type")
    for requirement in open_requirements:
        rid = requirement["id"]
        cells = rows.get(rid)
        if not cells:
            problems.append(f"{IDEA_FILE}: Acceptance Matrix missing {rid}")
            continue
        if len(cells) < expected_columns:
            problems.append(f"{IDEA_FILE}: Acceptance Matrix row for {rid} has {len(cells)} columns; expected at least {expected_columns}")
            continue
        for index, cell in enumerate(cells[1:expected_columns], start=2):
            if _weak_text_value(cell, min_len=8):
                problems.append(f"{IDEA_FILE}: Acceptance Matrix row for {rid} has weak column {index}: {cell or '(empty)'}")
        validation_type = cells[validation_type_index].strip().lower()
        if validation_type not in VALIDATION_TYPES:
            problems.append(f"{IDEA_FILE}: Acceptance Matrix row for {rid} has invalid validation type: {cells[validation_type_index]}")
    return problems


def _closed_requirement_problems(status: dict) -> list[str]:
    problems: list[str] = []
    allowed = re.compile(r"\b(user|requester|product owner)\b.*\b(drop|dropped|remove|removed|defer|deferred|out of scope|supersede|superseded)\b", re.I)
    for requirement in status.get("requirements", []):
        if requirement.get("state") != "closed":
            continue
        note = str(requirement.get("closed_note", ""))
        if not allowed.search(note):
            problems.append(
                f"requirement {requirement.get('id', '')} is closed without explicit user drop/defer/supersede evidence"
            )
    return problems


def _english_only_doc_problems(target: Path) -> list[str]:
    problems: list[str] = []
    for name in FILES:
        path = target / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if not _is_ascii(text):
                problems.append(f"{name}: contains non-ASCII text; bundle artifacts must be English-only")
    return problems


def _unexpected_bundle_doc_problems(target: Path) -> list[str]:
    allowed = set(FILES)
    problems: list[str] = []
    for path in target.glob("*.md"):
        if path.name not in allowed and not path.name.endswith(".bak"):
            problems.append(
                f"{path.name}: unexpected bundle markdown file. Use only 00-idea.md, 01-progress.md, and 02-report.md."
            )
    return problems


def _bundle_integrity_problems(target: Path, require_closer: bool) -> list[str]:
    problems: list[str] = []
    for name in FILES:
        p = target / name
        if not p.exists():
            problems.append(f"missing: {name}")
    if not state_exists(target):
        problems.append(f"missing: {STATE_FILE}")
        return problems

    status = read_status(target)
    problems.extend(_status_ascii_problems(status))
    if not status.get("milestones"):
        problems.append(f"{STATE_FILE}: no milestones recorded")
    if not status.get("implementation_ready"):
        problems.append(f"{STATE_FILE}: implementation_ready is not true")
    exploration_output_problem = _exploration_output_problem(status, target)
    if exploration_output_problem:
        problems.append(exploration_output_problem)
    ready_output_problem = _ready_output_problem(status, target)
    if ready_output_problem:
        problems.append(ready_output_problem)
    if not status.get("user_input_decisions"):
        problems.append(f"{STATE_FILE}: no user input decision records")
    if status.get("pending_plan_update"):
        problems.append(f"{STATE_FILE}: user input changed the plan but requirements/design/implementation were not updated")
    problems.extend(implementation_gate_problems(target))
    problems.extend(_pre_edit_compliance_problems(target, status))
    problems.extend(_delegation_problems(status))
    problems.extend(_english_only_doc_problems(target))
    problems.extend(_unexpected_bundle_doc_problems(target))

    idea_text = (target / "00-idea.md").read_text(encoding="utf-8") if (target / "00-idea.md").exists() else ""
    if "{idea_body}" in idea_text or "## Original Idea\n\n-\n" in idea_text:
        problems.append(
            "00-idea.md: still on template. Fix with: "
            "update --root <root> --slug <slug> --file idea --content-file <path>"
        )

    requirements_text = idea_text
    if "## Task Classification" not in requirements_text:
        problems.append(f"{IDEA_FILE}: missing Task Classification section")
    else:
        if re.search(r"File changes:\s*yes/no\b|Semantic impact:\s*yes/no/unclear\b|Tracking required:\s*yes/no\b", requirements_text, re.I):
            problems.append(f"{IDEA_FILE}: Task Classification still contains template choices")
        classification_patterns = {
            "File changes": r"^\s*-?\s*File changes:\s*(yes|no)\s*$",
            "Semantic impact": r"^\s*-?\s*Semantic impact:\s*(yes|no|unclear)\s*$",
            "Tracking required": r"^\s*-?\s*Tracking required:\s*(yes|no)\s*$",
            "Reason": r"Reason:\s*\S+",
        }
        for label, pattern in classification_patterns.items():
            if not re.search(pattern, requirements_text, re.I | re.M):
                problems.append(f"{IDEA_FILE}: Task Classification missing concrete {label}")

    problems.extend(_acceptance_matrix_problems(requirements_text, status.get("requirements", [])))
    problems.extend(_closed_requirement_problems(status))

    validation_types_pattern = r"\b(real-product-path|mock-only|fixture-only|source-only|dom-only|manual-inspection|unverified)\b"
    for milestone in status.get("milestones", []):
        if not re.search(validation_types_pattern, milestone.get("verified", ""), re.I):
            problems.append(f"milestone '{milestone.get('name', '')}' verified evidence must name a validation type")

    problems.extend(_role_gate_problems(status, require_closer=require_closer))

    coverage = _coverage_by_requirement(status)
    uncovered: list[str] = []
    failing: list[str] = []
    for r in status.get("requirements", []):
        if r.get("state") == "closed":
            continue
        covers = coverage.get(r["id"], [])
        if not covers:
            uncovered.append(r["id"])
        elif _aggregate_gate(covers) == "fail":
            failing.append(r["id"])
    if uncovered:
        problems.append(
            "trace matrix: uncovered requirements -> "
            + ", ".join(uncovered)
            + ". Fix by adding --covers to the relevant checkpoint, "
            + "running 'link --milestone <name> --covers <ids>' to attach an existing milestone, "
            + "or asking the user for a scope decision before finalizing."
        )
    if failing:
        problems.append(
            "trace matrix: covered but failing verification -> "
            + ", ".join(failing)
            + ". Run another milestone with gate-status pass/partial to improve the aggregate."
        )
    return problems


def _finalize_integrity_problems(
    status: dict, gate_status: str, decision: str, gate_problems: list[str] | None = None
) -> list[str]:
    """Cross-check claimed outcome against the bundle's actual trace matrix and blockers.

    Returns a list of human-readable problems. Empty list = claim is consistent.
    """
    problems: list[str] = []
    coverage = _coverage_by_requirement(status)
    open_reqs = [r for r in status.get("requirements", []) if r.get("state") != "closed"]
    if not open_reqs:
        problems.append("accepted/pass closeout requires at least one open requirement")
    uncovered = [r["id"] for r in open_reqs if not coverage.get(r["id"])]
    failing = [
        r["id"] for r in open_reqs
        if coverage.get(r["id"]) and _aggregate_gate(coverage[r["id"]]) == "fail"
    ]
    partial = [
        r["id"] for r in open_reqs
        if coverage.get(r["id"]) and _aggregate_gate(coverage[r["id"]]) == "partial"
    ]
    open_blockers = [
        b for b in status.get("blocks", []) if "resolved_at_utc" not in b
    ]
    if not status.get("implementation_ready"):
        problems.append("implementation gate was not marked ready")
    if gate_problems:
        problems.append(
            "implementation gate has open problems: " + "; ".join(gate_problems)
        )

    if gate_status == "pass" and (failing or uncovered):
        parts = []
        if failing:
            parts.append(f"failing aggregates: {', '.join(failing)}")
        if uncovered:
            parts.append(f"uncovered requirements: {', '.join(uncovered)}")
        problems.append(
            "--gate-status pass conflicts with trace matrix (" + "; ".join(parts) + ")"
        )
    if gate_status == "pass" and partial:
        problems.append(
            "--gate-status pass conflicts with partial aggregates: "
            + ", ".join(partial)
        )

    if decision == "accepted":
        problems.extend(_role_gate_problems(status))
        incomplete_backlog = _master_backlog_incomplete_items(status)
        if incomplete_backlog:
            problems.append(
                "--decision accepted with incomplete master backlog items: "
                + ", ".join(f"{item.get('id')} ({item.get('status', 'pending')})" for item in incomplete_backlog)
            )
        open_pre_edit_noncompliance = _open_pre_edit_noncompliance(status)
        if open_pre_edit_noncompliance:
            problems.append(
                "--decision accepted with open pre-edit noncompliance: "
                + ", ".join(event.get("id", "unknown") for event in open_pre_edit_noncompliance)
            )
        open_delegation_findings = _open_delegation_findings(status)
        if open_delegation_findings:
            problems.append(
                "--decision accepted with unusable delegation evidence: "
                + ", ".join(record.get("id", "unknown") for record in open_delegation_findings)
            )
        if uncovered:
            problems.append(
                "--decision accepted with uncovered requirements: "
                + ", ".join(uncovered)
            )
        if failing:
            problems.append(
                "--decision accepted with failing aggregates: "
                + ", ".join(failing)
            )
        if open_blockers:
            problems.append(
                f"--decision accepted with {len(open_blockers)} unresolved blocker(s)"
            )
    return problems


def finalize_bundle(
    root: Path,
    slug: str,
    summary: str,
    verification: str,
    risks: str,
    acceptance: str,
    gate_status: str,
    decision: str,
    acceptance_notes: str,
    deferred: str,
    force: bool,
) -> Path:
    target = ensure_active_bundle(root, slug)
    with bundle_lock(target):
        return _finalize_bundle_locked(
            root, slug, target, summary, verification, risks, acceptance,
            gate_status, decision, acceptance_notes, deferred, force,
        )


def _finalize_bundle_locked(
    root: Path,
    slug: str,
    target: Path,
    summary: str,
    verification: str,
    risks: str,
    acceptance: str,
    gate_status: str,
    decision: str,
    acceptance_notes: str,
    deferred: str,
    force: bool,
) -> Path:
    argument_text = "\n".join([summary, verification, risks, acceptance, acceptance_notes, deferred])
    if not _is_ascii(argument_text):
        raise SystemExit("finalize refused - summary, verification, risks, acceptance, notes, and deferred text must be English-only ASCII.")
    if not re.search(r"\b(real-product-path|mock-only|fixture-only|source-only|dom-only|manual-inspection|unverified)\b", verification, re.I):
        raise SystemExit("finalize refused - --verification must name a validation type.")

    timestamp = utc_now()
    status = read_status(target)
    structural_problems = _bundle_integrity_problems(target, require_closer=True)
    if not status.get("last_verify_ok") or status.get("last_verified_plan_revision") != status.get("plan_revision"):
        structural_problems.append(
            "pre-close verify has not passed for the current plan revision. Run verify after Reviewer evidence and before Closer/finalize."
        )

    integrity_problems = _finalize_integrity_problems(
        status, gate_status, decision, implementation_gate_problems(target)
    )
    if structural_problems:
        force_note = ""
        if force and decision == "accepted":
            force_note = "\n--force cannot override accepted closeout integrity failures."
        elif force and gate_status == "pass":
            force_note = "\n--force cannot override pass-gate integrity failures."
        raise SystemExit(
            "finalize refused - bundle integrity verification failed:\n  - "
            + "\n  - ".join(structural_problems)
            + "\nRun verify, fix the bundle evidence, then finalize again."
            + force_note
        )
    hard_gate_problems: list[str] = []
    if not status.get("implementation_ready"):
        hard_gate_problems.append("implementation gate was not marked ready")
    hard_gate_problems.extend(implementation_gate_problems(target))
    if hard_gate_problems:
        raise SystemExit(
            "finalize refused - implementation gate is incomplete and cannot be bypassed with --force:\n  - "
            + "\n  - ".join(hard_gate_problems)
            + f"\nFill {IMPLEMENTATION_FILE} and run 'implementation ready' first."
        )
    if integrity_problems and decision == "accepted":
        raise SystemExit(
            "finalize refused - accepted closeout contradicts the bundle state:\n  - "
            + "\n  - ".join(integrity_problems)
            + "\nFix the milestones / requirements / blockers / role evidence, "
            "or lower --gate-status / --decision to match reality. "
            "--force cannot override accepted closeout integrity failures."
        )
    if integrity_problems and gate_status == "pass":
        raise SystemExit(
            "finalize refused - pass gate contradicts the bundle state:\n  - "
            + "\n  - ".join(integrity_problems)
            + "\nFix the evidence or lower --gate-status. "
            "--force cannot override pass-gate integrity failures."
        )
    if integrity_problems and not force:
        raise SystemExit(
            "finalize refused - the claim contradicts the bundle state:\n  - "
            + "\n  - ".join(integrity_problems)
            + "\nFix the milestones / requirements / blockers, lower --gate-status "
            "or --decision to match reality, or pass --force to override (the "
            "override is recorded in the final report)."
        )

    status["state"] = "completed" if decision == "accepted" else "closed"
    status["phase"] = "accepted" if decision == "accepted" else "closed"
    status["finalized_at_utc"] = timestamp
    status["gate_status"] = gate_status
    status["decision"] = decision
    status["closeout_status"] = {
        "completed": decision == "accepted",
        "closed": True,
        "final_verify_ok": False,
        "closed_by": "closer",
        "plan_revision": status.get("plan_revision"),
        "preclose_verified_at_utc": status.get("last_verified_at_utc"),
        "final_verified_at_utc": None,
        "gate_status": gate_status,
        "decision": decision,
    }
    _release_active_leases_for_closeout(status, timestamp, "bundle finalized; implementation ownership closed")
    if force and integrity_problems:
        status.setdefault("force_overrides", []).append(
            {
                "timestamp_utc": timestamp,
                "problems": integrity_problems,
                "gate_status": gate_status,
                "decision": decision,
            }
        )
    write_status(target, status)
    append_ledger(target, "finalize-start", f"Finalizing with gate={gate_status}, decision={decision}")

    default_final = render_template(FILES[FINAL_REPORT_FILE])
    final_path = target / FINAL_REPORT_FILE
    accept_path = target / ACCEPTANCE_FILE

    if not force:
        final_backup = backup_if_edited(final_path, default_final)
        if final_backup:
            msgs = []
            msgs.append(f"  {FINAL_REPORT_FILE} -> {final_backup.name}")
            print(
                "Backed up edited files before overwriting:\n" + "\n".join(msgs),
                file=sys.stderr,
            )

    milestone_rollup = _render_milestones_rollup(status["milestones"])
    matrix_block = _render_trace_matrix(status)
    role_block = _render_role_evidence(status)
    block_summary = ""
    if status.get("blocks"):
        unresolved = [b for b in status["blocks"] if "resolved_at_utc" not in b]
        block_summary = f"- Total blockers encountered: {len(status['blocks'])} (unresolved: {len(unresolved)})\n"

    override_block = ""
    if force and integrity_problems:
        override_block = (
            "\n## Force Overrides\n\n"
            "The following integrity checks were bypassed via --force at finalize time:\n\n"
            + "".join(f"- {p}\n" for p in integrity_problems)
        )

    final_path.write_text(
        "# Final Report\n\n"
        f"## Target\n\n- {status['title']}\n\n"
        f"## Trace Matrix\n\n{matrix_block}\n"
        f"## Role Evidence\n\n{role_block}\n"
        f"## Milestones\n\n{milestone_rollup}\n"
        f"## Implementation\n\n- {summary}\n\n"
        f"## Verification\n\n- Gate status: {gate_status}\n- {verification}\n{block_summary}\n"
        "## Visual Evidence\n\n- Attach screenshots or saved artifacts here when the task has UI or runtime output.\n\n"
        f"## Risks And Follow-Up\n\n- {risks}\n"
        f"{override_block}",
        encoding="utf-8",
    )

    with accept_path.open("a", encoding="utf-8") as f:
        f.write(
            "\n## Final Acceptance\n\n"
            f"- Requested scope delivered: {acceptance}\n"
            f"- Verification gate: {gate_status}\n"
            f"- Decision: {decision}\n"
            f"- Acceptance notes: {acceptance_notes or '-'}\n"
            f"- Deferred work: {deferred or '-'}\n"
        )
        f.write(f"\n### Role Evidence\n\n{role_block}\n")

    rewrite_current_phase(
        target / MILESTONES_FILE,
        [
            "## Current Phase",
            "",
            f"- Status: {status['state']}",
            "- Current focus: final report delivered",
            f"- Gate status: {gate_status}",
            f"- Decision: {decision}",
            "",
        ],
    )
    final_verify_problems = _bundle_integrity_problems(target, require_closer=True)
    if final_verify_problems:
        raise SystemExit(
            "finalize refused - final verification failed after writing closeout artifacts:\n  - "
            + "\n  - ".join(final_verify_problems)
            + "\nFix the bundle state or final report inputs and rerun finalize."
        )
    status = read_status(target)
    status["last_verify_ok"] = True
    status["last_verified_plan_revision"] = status.get("plan_revision")
    status["last_verified_at_utc"] = utc_now()
    status["last_verified_event_sequence"] = _next_event_sequence(status)
    status.setdefault("closeout_status", {})
    status["closeout_status"].update(
        {
            "final_verify_ok": True,
            "final_verified_at_utc": status["last_verified_at_utc"],
            "completed": decision == "accepted",
            "closed": True,
            "closed_by": "closer",
            "plan_revision": status.get("plan_revision"),
            "gate_status": gate_status,
            "decision": decision,
        }
    )
    write_status(target, status)
    append_ledger(target, "finalize-complete", f"Final verification passed; gate={gate_status}, decision={decision}")
    current = read_current(root)
    if current and current.get("slug") == slug:
        append_history(root, slug, status, "finalize")
        current_path(root).unlink(missing_ok=True)
    return target


def print_status(root: Path, slug: str, full: bool) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    summary = {
        "title": status["title"],
        "slug": status["slug"],
        "state": status.get("state", "in_progress"),
        "current_focus": status.get("current_focus", ""),
        "next_gate": status.get("next_gate", ""),
        "milestone_count": len(status.get("milestones", [])),
        "open_blockers": len(
            [b for b in status.get("blocks", []) if "resolved_at_utc" not in b]
        ),
        "gate_status": status.get("gate_status"),
        "decision": status.get("decision"),
        "updated_at_utc": status["updated_at_utc"],
        "path": str(target),
    }
    if full:
        summary["milestones"] = status.get("milestones", [])
        summary["blocks"] = status.get("blocks", [])
        summary["requirements"] = status.get("requirements", [])
        summary["master_backlog_required"] = status.get("master_backlog_required")
        summary["master_backlog_plan_revision"] = status.get("master_backlog_plan_revision")
        summary["master_backlog"] = status.get("master_backlog", [])
        summary["user_input_decisions"] = status.get("user_input_decisions", [])
        summary["role_evidence"] = status.get("role_evidence", {})
        summary["local_records"] = status.get("local_records", [])
        summary["plan_revision"] = status.get("plan_revision")
        summary["implementation_ready"] = status.get("implementation_ready")
        summary["pending_plan_update"] = status.get("pending_plan_update")
        summary["last_verify_ok"] = status.get("last_verify_ok")
        summary["last_verified_plan_revision"] = status.get("last_verified_plan_revision")
        summary["last_verified_at_utc"] = status.get("last_verified_at_utc")
        summary["closeout_status"] = status.get("closeout_status", {})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _latest_milestone_entry(status: dict) -> dict | None:
    milestones = status.get("milestones", [])
    if not milestones:
        return None
    latest = milestones[-1]
    return latest if isinstance(latest, dict) else None


def _status_scope_label(status: dict, req_ids: list[str], focus: str = "") -> str:
    req_label = ", ".join(req_ids) if req_ids else "<REQ-* IDs>"
    task_ids = sorted(set(re.findall(r"\bTASK-\d+\b", focus or "")))
    if not task_ids and status.get("current_task_id"):
        task_ids = [status["current_task_id"]]
    task_label = ", ".join(task_ids) if task_ids else "TASK-*"
    idea_records = status.get("idea_records", [])
    matched_ideas = [
        entry.get("id")
        for entry in idea_records
        if entry.get("id") and (
            not req_ids
            or not entry.get("related_reqs")
            or sorted(set(req_ids) & set(entry.get("related_reqs", [])))
        )
    ]
    if len(idea_records) > 1 or matched_ideas:
        idea_label = ", ".join(sorted(set(matched_ideas))) if matched_ideas else "<IDEA-* IDs>"
        return f"{idea_label} / {task_label} / {req_label}"
    return f"{task_label} / {req_label}"


def _render_status_evidence_lines(status: dict, req_hint: str) -> tuple[list[str], list[str], list[str]]:
    latest = _latest_milestone_entry(status)
    if not latest:
        placeholder = f"- <TASK-* / {req_hint}: "
        return (
            [placeholder + "summarize the user-visible or workflow change>"],
            [placeholder + "completed and validated item; latest milestone: <latest milestone>"],
            [placeholder + "validation type + command/evidence + result>"],
        )
    covers = [item for item in latest.get("covers", []) if item]
    scope_source = " ".join(
        str(latest.get(key, ""))
        for key in ("focus", "delivered", "verified", "name")
    )
    scope_source = " ".join([scope_source, str(status.get("current_focus", ""))]).strip()
    scope = _status_scope_label(status, covers, scope_source)
    milestone_name = latest.get("name") or "<latest milestone>"
    delivered = latest.get("delivered") or "latest milestone recorded delivered work"
    verified = latest.get("verified") or "validation evidence not recorded"
    return (
        [f"- {scope}: {delivered}"],
        [f"- {scope}: milestone {milestone_name} is recorded for this scope."],
        [f"- {scope}: {verified}"],
    )


def _same_agent_only_unverified_lines(status: dict, req_ids: list[str]) -> list[str]:
    plan_revision = int(status.get("plan_revision", 0))
    reviewer_entries = [
        entry for entry in status.get("role_evidence", {}).get("reviewer", [])
        if entry.get("plan_revision") == plan_revision
        and "same-agent review" in str(entry.get("evidence", "")).lower()
    ]
    if not reviewer_entries or _usable_delegation_records(status, "reviewer"):
        return []
    latest = _latest_milestone_entry(status) or {}
    scope_source = " ".join(
        str(latest.get(key, ""))
        for key in ("focus", "delivered", "verified", "name")
    )
    scope_source = " ".join([scope_source, str(status.get("current_focus", ""))]).strip()
    scope = _status_scope_label(status, req_ids, scope_source)
    return [
        f"- {scope}: independent subagent/fresh-agent reviewer evidence not run; current reviewer evidence is same-agent only."
    ]


def _ready_history_summary(status: dict, limit: int = 5) -> str:
    history = [
        item for item in status.get("ready_task_output_history", [])
        if item.get("id")
    ]
    if not history:
        return "none"
    recent = history[-limit:]
    return ", ".join(
        f"{item.get('id')}@r{item.get('plan_revision')}:{item.get('scope', 'unknown')}"
        for item in recent
    )


def _default_render_status_label(status: dict) -> str:
    if status.get("state") == "completed" and status.get("decision") == "accepted":
        return "Completed"
    if status.get("state") == "blocked" or status.get("phase") == "blocked":
        return "Blocked"
    return "Progress"


def render_status_response(
    root: Path,
    slug: str,
    status_label: str | None,
    profile: str | None = None,
    role: str = "Closer",
    source: str = "agent",
) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    status_label = status_label or _default_render_status_label(status)
    prefix = _visibility_prefix(profile, role, source)
    if status_label not in {"Completed", "Progress", "Blocked"}:
        raise SystemExit("render-status refused - --status must be Completed, Progress, or Blocked")

    latest_milestone = _latest_milestone_entry(status)
    milestone_reqs = [item for item in (latest_milestone or {}).get("covers", []) if item]
    requirements = milestone_reqs or [
        req.get("id", "")
        for req in status.get("requirements", [])
        if req.get("state", "open") == "open"
    ]
    req_hint = ", ".join(requirements) if requirements else "<REQ-* IDs>"
    exploration_id = status.get("exploration_output_id") or "<EXPLORATION_OUTPUT_ID>"
    ready_id = status.get("ready_task_output_id") or "<READY_TASK_OUTPUT_ID>"
    commit_note = "No commit made unless a commit was explicitly completed outside this bundle."
    backlog = status.get("master_backlog", [])
    incomplete_backlog = _master_backlog_incomplete_items(status)
    remaining_backlog = _master_backlog_remaining_items(status)
    open_pre_edit_noncompliance = _open_pre_edit_noncompliance(status)
    open_delegation_findings = _open_delegation_findings(status)
    session_audits = status.get("session_continuity_audits", [])
    scope_classifications = status.get("scope_classifications", [])
    incomplete_line = "- none"
    incomplete_lines: list[str] = []
    if backlog and incomplete_backlog:
        incomplete_lines.append("- Master backlog incomplete: " + ", ".join(
            f"{item.get('id')} ({item.get('status', 'pending')})" for item in incomplete_backlog
        ))
    if open_pre_edit_noncompliance:
        incomplete_lines.append("- Pre-edit noncompliance open: " + ", ".join(
            f"{event.get('id', 'unknown')} ({event.get('task_id') or 'unknown-task'})" for event in open_pre_edit_noncompliance
        ))
    if open_delegation_findings:
        incomplete_lines.append("- Delegation evidence not usable: " + ", ".join(
            f"{record.get('id', 'unknown')} ({record.get('role', 'unknown')}={record.get('status', 'unknown')})"
            for record in open_delegation_findings
        ))
    if incomplete_lines:
        incomplete_line = "\n".join(incomplete_lines)
    backlog_line = None
    if backlog:
        backlog_line = "Master backlog: " + ", ".join(
            f"{item.get('id')}={item.get('status', 'pending')}" for item in backlog
        )
    remaining_backlog_line = None
    next_batch_line = None
    if remaining_backlog:
        remaining_backlog_line = "Remaining Backlog: " + ", ".join(
            f"{item.get('id')}={item.get('status', 'pending')}" for item in remaining_backlog
        )
        next_batch_items = remaining_backlog[:5]
        next_batch_line = "Next Batch: " + ", ".join(
            f"{item.get('id')} ({item.get('title', '').strip() or 'untitled'})" for item in next_batch_items
        )
    change_lines, completed_lines, validation_lines = _render_status_evidence_lines(status, req_hint)
    unverified_lines = _same_agent_only_unverified_lines(status, requirements) or ["- none"]
    idea_records = status.get("idea_records", [])

    lines = [
        f"{prefix} Status: {status_label}",
        "",
        "Changes:",
        *change_lines,
        "",
        "Completed Items:",
        *completed_lines,
        "",
        "Incomplete Items:",
        incomplete_line,
        "",
        "Validation Results:",
        *validation_lines,
        "",
        "Unverified Items:",
        *unverified_lines,
        "",
        "Residual Risks:",
        "- none",
        "",
        "Key Technical Details:",
        f"- EXPLORATION_OUTPUT_ID: {exploration_id}",
        f"- READY_TASK_OUTPUT_ID: {ready_id}",
        f"- READY_TASK_OUTPUT_HISTORY: {_ready_history_summary(status)}",
        f"- {commit_note}",
        "- Bundle finalization/commit/publish state belongs here unless explicitly in scope.",
    ]
    if backlog_line:
        lines.append(f"- {backlog_line}")
    if remaining_backlog_line:
        lines.append(f"- {remaining_backlog_line}")
    if next_batch_line:
        lines.append(f"- {next_batch_line}")
    if idea_records:
        lines.append(
            "- Idea ledger: "
            + ", ".join(
                f"{entry.get('id')}={entry.get('status', 'active')}"
                for entry in idea_records
            )
        )
    if session_audits:
        latest_session = session_audits[-1]
        lines.append(
            f"- Latest session continuity audit: {latest_session.get('relation')} | "
            f"{latest_session.get('summary')}"
        )
    if scope_classifications:
        latest_scope = scope_classifications[-1]
        lines.append(
            f"- Latest scope classification: {latest_scope.get('classification')} | "
            f"{latest_scope.get('summary')}"
        )
    print("\n".join(lines))
    return 0


FORMAL_STATUS_FIELDS = [
    "Changes:",
    "Completed Items:",
    "Incomplete Items:",
    "Validation Results:",
    "Unverified Items:",
    "Residual Risks:",
    "Key Technical Details:",
]

FORMAL_STATUS_PREFIX_PATTERN = r"\[idea-to-code(?:/[^\]]+)?\]\[Closer/(?:agent|subagent)\] Status: (Completed|Progress|Blocked)"


def _fields_in_order(text: str, fields: list[str]) -> list[str]:
    problems: list[str] = []
    last_index = -1
    for field in fields:
        index = text.find(field)
        if index < 0:
            problems.append(f"assistant-visible body missing fixed field: {field}")
            continue
        if index < last_index:
            problems.append(f"assistant-visible body field out of order: {field}")
        last_index = index
    return problems


def _section_between(text: str, start: str, end: str | None) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    start_index += len(start)
    if end is None:
        return text[start_index:]
    end_index = text.find(end, start_index)
    if end_index < 0:
        return text[start_index:]
    return text[start_index:end_index]


CONCRETE_SCOPE_ID_RE = re.compile(r"\b(?:TASK|REQ|MB|IDEA)-\d+\b")


def _residual_risk_scope_problems(section: str) -> list[str]:
    problems: list[str] = []
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    risk_lines = [line for line in lines if line.startswith("-")]
    if not lines:
        return problems
    for line in risk_lines or lines:
        value = line[1:].strip() if line.startswith("-") else line
        if value.lower() == "none":
            continue
        if not CONCRETE_SCOPE_ID_RE.search(value):
            problems.append("Residual Risks: section has unmapped risk; use none or concrete TASK/REQ/MB/IDEA scope")
    return problems


def _section_is_none(section: str) -> bool:
    values = [
        (line.strip()[1:].strip() if line.strip().startswith("-") else line.strip()).lower()
        for line in section.splitlines()
        if line.strip()
    ]
    return bool(values) and all(value == "none" for value in values)


EXPLORATION_VISIBLE_FIELDS = [
    "Display Layer: Exploration Result",
    "Next Layer:",
    "EXPLORATION_OUTPUT_ID:",
    "Required Now:",
    "Deferred:",
    "Selected Option:",
    "What READY Will Cover:",
]

READY_VISIBLE_FIELDS = [
    "READY_TASK_OUTPUT_ID:",
    "EXPLORATION_OUTPUT_ID:",
    "Implementation Granularity:",
    "Trace Hierarchy: IDEA-* -> REQ-* -> TASK-* -> optional IMP-*",
    "Required Now:",
    "Deferred:",
    "Selected Option:",
    "What READY Will Cover:",
    "Files:",
    "Execution Details:",
    "Done Criteria:",
    "Planned Verification:",
]


def _looks_like_exploration_summary(text: str) -> bool:
    return bool(re.search(r"\bExploration Result\s*:", text)) and "Display Layer: Exploration Result" not in text


def _looks_like_ready_summary(text: str) -> bool:
    if "Display Layer: READY Focus" in text:
        return False
    return bool(
        re.search(r"\bREADY Focus\s+TASK-\d+\s*/\s*REQ-\d+\s*:", text)
        or re.search(r"\bRefreshed Implementation Gate:\s*READY\b", text)
        or re.search(r"\bImplementation Gate:\s*READY[^\n]*(Required Now|Current READY focus|TASK-\d+)", text)
    )


def validate_visible_ready_output(tool_stdout: str, assistant_visible_body: str) -> list[str]:
    problems: list[str] = []
    if "Exploration Result | Bundle:" in tool_stdout and "Exploration Result | Bundle:" not in assistant_visible_body:
        problems.append("Exploration Result was only present in tool stdout, not assistant-visible body")
    if "Implementation Gate: READY | Bundle:" in tool_stdout and "Implementation Gate: READY | Bundle:" not in assistant_visible_body:
        problems.append("Implementation Gate: READY was only present in tool stdout, not assistant-visible body")
    if _looks_like_exploration_summary(assistant_visible_body):
        problems.append("assistant-visible Exploration Result is only a one-line summary; show the Display Layer block")
    if _looks_like_ready_summary(assistant_visible_body):
        problems.append("assistant-visible READY is only a one-line summary; show the READY Focus Display Layer block")
    if "Exploration Result | Bundle:" in tool_stdout or "Exploration Result | Bundle:" in assistant_visible_body:
        for required in EXPLORATION_VISIBLE_FIELDS:
            if required not in assistant_visible_body:
                problems.append(f"assistant-visible Exploration body missing: {required}")
    if (
        "Implementation Gate: READY | Bundle:" in tool_stdout
        or "Implementation Gate: READY | Bundle:" in assistant_visible_body
        or _looks_like_ready_summary(assistant_visible_body)
    ):
        if "Display Layer: READY Focus" not in assistant_visible_body and "Display Layer: Full Plan" not in assistant_visible_body:
            problems.append("assistant-visible READY body missing: Display Layer: READY Focus or Display Layer: Full Plan")
        for required in READY_VISIBLE_FIELDS:
            if required not in assistant_visible_body:
                problems.append(f"assistant-visible READY body missing: {required}")
    return problems


def validate_formal_status_visible_output(tool_stdout: str, assistant_visible_body: str) -> list[str]:
    problems: list[str] = []
    helper_available = bool(re.search(FORMAL_STATUS_PREFIX_PATTERN, tool_stdout))
    body_has_status = bool(re.search(r"^" + FORMAL_STATUS_PREFIX_PATTERN, assistant_visible_body))
    if helper_available and not body_has_status:
        problems.append("render-status output was only present in tool stdout, not assistant-visible body")
    if not helper_available and "render-status unavailable" not in assistant_visible_body and "render-status failed" not in assistant_visible_body:
        problems.append("manual formal status must state why render-status was unavailable or failed")
    if not body_has_status:
        problems.append("assistant-visible formal status must start with [idea-to-code][Closer/agent] Status: Completed|Progress|Blocked")
    problems.extend(_fields_in_order(assistant_visible_body, FORMAL_STATUS_FIELDS))
    for section_name in ["Changes:", "Completed Items:", "Validation Results:"]:
        next_fields = FORMAL_STATUS_FIELDS[FORMAL_STATUS_FIELDS.index(section_name) + 1:]
        next_field = next((field for field in next_fields if field in assistant_visible_body), None)
        section = _section_between(assistant_visible_body, section_name, next_field)
        if not re.search(r"\bTASK-\d+\b", section) or not re.search(r"\bREQ-\d+\b", section):
            problems.append(f"{section_name} section missing concrete TASK/REQ mapping")
        if "TASK-*" in section or "REQ-*" in section:
            problems.append(f"{section_name} section contains placeholder TASK/REQ mapping")
    incomplete = _section_between(assistant_visible_body, "Incomplete Items:", "Validation Results:")
    if "No commit made" in incomplete:
        problems.append("No commit made must not appear under Incomplete Items")
    unverified = _section_between(assistant_visible_body, "Unverified Items:", "Residual Risks:")
    if re.search(r"\bsame-agent\b|\bsame agent\b", assistant_visible_body, re.I):
        if _section_is_none(unverified):
            problems.append("Unverified Items must disclose same-agent-only independent evidence gap")
        elif not CONCRETE_SCOPE_ID_RE.search(unverified):
            problems.append("Unverified Items same-agent disclosure must use concrete TASK/REQ/MB/IDEA scope")
    key_details = _section_between(assistant_visible_body, "Key Technical Details:", None)
    exploration_match = re.search(r"EXPLORATION_OUTPUT_ID:\s*(\S+)", key_details)
    ready_match = re.search(r"READY_TASK_OUTPUT_ID:\s*(\S+)", key_details)
    if not exploration_match:
        problems.append("Key Technical Details missing EXPLORATION_OUTPUT_ID")
    elif exploration_match.group(1) == "<EXPLORATION_OUTPUT_ID>":
        problems.append("Key Technical Details has placeholder EXPLORATION_OUTPUT_ID")
    if not ready_match:
        problems.append("Key Technical Details missing READY_TASK_OUTPUT_ID")
    elif ready_match.group(1) == "<READY_TASK_OUTPUT_ID>":
        problems.append("Key Technical Details has placeholder READY_TASK_OUTPUT_ID")
    residual_risks = _section_between(assistant_visible_body, "Residual Risks:", "Key Technical Details:")
    problems.extend(_residual_risk_scope_problems(residual_risks))
    if "No commit made" in tool_stdout and "No commit made" not in key_details:
        problems.append("Key Technical Details missing No commit made from render-status")
    return problems


def validate_ordinary_visible_output(assistant_visible_body: str) -> list[str]:
    problems: list[str] = []
    for item in [
        "Implementation Gate: READY",
        "READY_TASK_OUTPUT_ID:",
        "[idea-to-code][Closer/agent] Status:",
        "Changes:",
        "Completed Items:",
        "Validation Results:",
    ]:
        if item in assistant_visible_body:
            problems.append(f"ordinary answer is over-templated with tracked output: {item}")
    return problems


def output_compliance_check(kind: str, tool_stdout: str, assistant_visible_body: str, json_only: bool) -> int:
    if kind == "ready":
        problems = validate_visible_ready_output(tool_stdout, assistant_visible_body)
    elif kind == "formal-status":
        problems = validate_formal_status_visible_output(tool_stdout, assistant_visible_body)
    elif kind == "ordinary":
        problems = validate_ordinary_visible_output(assistant_visible_body)
    else:
        raise SystemExit("output-compliance check refused - --kind must be ready, formal-status, or ordinary")
    payload = {"kind": kind, "ok": not problems, "problems": problems}
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif problems:
        print("output-compliance: FAIL")
        for problem in problems:
            print(f"- {problem}")
    else:
        print("output-compliance: PASS")
    return 0 if not problems else 1


TOOL_ACTION_PREFIXES = (
    "• Ran ",
    "• Running ",
    "• Edited ",
    "• Added ",
    "• Deleted ",
)


def _is_visible_assistant_start(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped.startswith("• "):
        return False
    return not stripped.startswith(TOOL_ACTION_PREFIXES)


def extract_visible_assistant_messages(transcript: str) -> list[str]:
    messages: list[str] = []
    current: list[str] = []
    in_message = False
    for raw_line in transcript.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()
        if stripped.startswith("› ") or stripped.startswith("────────────────"):
            if current:
                messages.append("\n".join(current).strip())
                current = []
            in_message = False
            continue
        if stripped.startswith("• "):
            if current:
                messages.append("\n".join(current).strip())
                current = []
            if _is_visible_assistant_start(line):
                current.append(stripped[2:].strip())
                in_message = True
            else:
                in_message = False
            continue
        if not in_message:
            continue
        continuation = stripped
        if (
            continuation.startswith("└")
            or continuation.startswith("│")
            or continuation.startswith("…")
            or continuation.startswith("◦ ")
            or continuation.startswith("⚠")
        ):
            if current:
                messages.append("\n".join(current).strip())
                current = []
            in_message = False
            continue
        current.append(continuation)
    if current:
        messages.append("\n".join(current).strip())
    return [message for message in messages if message]


def _transcript_problem(kind: str, message: str, mb_id: str | None = None) -> dict[str, str]:
    problem = {"kind": kind, "message": message}
    if mb_id:
        problem["mb_id"] = mb_id
    return problem


def _ready_problem_mb_id(problem: str) -> str | None:
    if "Exploration Result was only present in tool stdout" in problem:
        return "MB-1"
    if "Implementation Gate: READY was only present in tool stdout" in problem:
        return "MB-2"
    if "assistant-visible READY body missing" in problem or "assistant-visible READY is only" in problem:
        return "MB-3"
    if "assistant-visible Exploration body missing" in problem or "assistant-visible Exploration Result is only" in problem:
        return "MB-4"
    return None


def _first_line_index(lines: list[str], patterns: tuple[str, ...]) -> int | None:
    for index, line in enumerate(lines):
        if any(pattern in line for pattern in patterns):
            return index
    return None


def detect_late_active_bundle_binding(transcript: str) -> str | None:
    lines = transcript.splitlines()
    trigger_index = _first_line_index(lines, ("使用idea-to-code", "use idea-to-code", "idea-to-code"))
    if trigger_index is None:
        return None
    first_bundle_index = _first_line_index(lines, (
        " init --root ",
        " quickstart --root ",
        " current set ",
        " current resume ",
        "current bundle",
        "Bundle 已创建",
        "Bundle:",
    ))
    if first_bundle_index is None:
        return "idea-to-code work is present but no active bundle creation/resume is visible in the transcript"
    pre_bundle = lines[trigger_index:first_bundle_index]
    assistant_updates = sum(1 for line in pre_bundle if _is_visible_assistant_start(line))
    tool_actions = sum(1 for line in pre_bundle if line.lstrip().startswith(TOOL_ACTION_PREFIXES))
    current_null_seen = any('"current": null' in line or "active_bundle" in line and "null" in line for line in pre_bundle)
    if assistant_updates >= 3 or tool_actions >= 8 or current_null_seen:
        return (
            "extended idea-to-code analysis occurred before active bundle creation/resume "
            f"({assistant_updates} assistant updates, {tool_actions} tool actions before first bundle signal)"
        )
    return None


def audit_transcript_output(transcript: str) -> dict[str, Any]:
    messages = extract_visible_assistant_messages(transcript)
    visible_body = "\n\n".join(messages)
    problems: list[dict[str, str]] = []

    for index, message in enumerate(messages, start=1):
        if "idea-to-code" in message and not re.match(r"^\[idea-to-code(?:/[^\]]+)?\]\[(Planner|Implementer|Validator|Reviewer|Closer)/(agent|subagent)\]", message):
            problems.append(_transcript_problem(
                "visible-prefix",
                f"assistant message {index} mentions idea-to-code but does not start with role/source prefix",
            ))

    ready_problems = validate_visible_ready_output(transcript, visible_body)
    for problem in ready_problems:
        problems.append(_transcript_problem("ready-visible-body", problem, _ready_problem_mb_id(problem)))

    late_bundle = detect_late_active_bundle_binding(transcript)
    if late_bundle:
        problems.append(_transcript_problem("active-bundle-binding", late_bundle, "MB-5"))

    helper_or_status_seen = "[idea-to-code][Closer/agent] Status:" in transcript or "[idea-to-code][Closer/subagent] Status:" in transcript
    final_messages = [
        message for message in messages
        if re.match(r"^\[idea-to-code(?:/[^\]]+)?\]\[Closer/(?:agent|subagent)\] Status: (Completed|Progress|Blocked)", message)
    ]
    if helper_or_status_seen:
        if not final_messages:
            problems.append(_transcript_problem(
                "formal-status-visible-body",
                "tracked final status appears in transcript but no assistant-visible Closer status body was found",
            ))
        else:
            for problem in validate_formal_status_visible_output(transcript, final_messages[-1]):
                problems.append(_transcript_problem("formal-status-visible-body", problem))

    backlog_hits = sorted({problem["mb_id"] for problem in problems if problem.get("mb_id")})

    payload = {
        "schema": "idea-to-code.output-compliance.transcript-audit.v1",
        "ok": not problems,
        "message_count": len(messages),
        "backlog_hits": backlog_hits,
        "hard_output_seen": {
            "exploration": "Exploration Result | Bundle:" in transcript,
            "ready": "Implementation Gate: READY | Bundle:" in transcript,
            "formal_status": helper_or_status_seen,
        },
        "problems": problems,
    }
    return payload


def output_compliance_transcript_audit(transcript: str, json_only: bool) -> int:
    payload = audit_transcript_output(transcript)
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif payload["problems"]:
        print("output-compliance transcript-audit: FAIL")
        for problem in payload["problems"]:
            print(f"- {problem['kind']}: {problem['message']}")
    else:
        print("output-compliance transcript-audit: PASS")
    return 0 if payload["ok"] else 1


def _sample_visible_ready_body(display_layer: str = "READY Focus") -> str:
    return (
        "[idea-to-code][Planner/agent] Exploration Result | Bundle: sample\n"
        "Display Layer: Exploration Result\n"
        "Next Layer: READY Focus after this output is visible; Full Plan only on --full-plan.\n"
        "EXPLORATION_OUTPUT_ID: sample-explore\n"
        "Required Now: TASK-1 / REQ-1\n"
        "Deferred: none\n"
        "Selected Option: Option B\n"
        "What READY Will Cover: TASK-1\n\n"
        "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample\n"
        f"Display Layer: {display_layer}\n"
        "READY_TASK_OUTPUT_ID: sample-ready\n"
        "EXPLORATION_OUTPUT_ID: sample-explore\n"
        "Implementation Granularity: task-only\n"
        "Trace Hierarchy: IDEA-* -> REQ-* -> TASK-* -> optional IMP-*\n"
        "Required Now: TASK-1 / REQ-1\n"
        "Deferred: none\n"
        "Selected Option: Option B\n"
        "What READY Will Cover: TASK-1\n"
        "TASK-1: Sample\n"
        "Files:\n- sample.py\n"
        "Execution Details:\n- edit\n"
        "Done Criteria:\n- done\n"
        "Planned Verification:\n- source-only tests\n"
    )


def _sample_formal_status_body() -> str:
    return (
        "[idea-to-code][Closer/agent] Status: Completed\n\n"
        "Changes:\n- TASK-1 / REQ-1: implemented sample behavior.\n\n"
        "Completed Items:\n- TASK-1 / REQ-1: sample complete.\n\n"
        "Incomplete Items:\n- none\n\n"
        "Validation Results:\n- TASK-1 / REQ-1: source-only validation passed.\n\n"
        "Unverified Items:\n- none\n\n"
        "Residual Risks:\n- none\n\n"
        "Key Technical Details:\n- EXPLORATION_OUTPUT_ID: sample-explore\n- READY_TASK_OUTPUT_ID: sample-ready\n- No commit made\n"
    )


def output_compliance_self_test(json_only: bool) -> int:
    scenarios = [
        {
            "name": "ready_focus_valid",
            "expect_ok": True,
            "kind": "ready",
            "tool_stdout": "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample\n",
            "assistant_body": _sample_visible_ready_body("READY Focus"),
        },
        {
            "name": "ready_full_plan_valid",
            "expect_ok": True,
            "kind": "ready",
            "tool_stdout": "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample\n",
            "assistant_body": _sample_visible_ready_body("Full Plan"),
        },
        {
            "name": "exploration_summary_rejected",
            "expect_ok": False,
            "kind": "ready",
            "tool_stdout": "[idea-to-code][Planner/agent] Exploration Result | Bundle: sample\n",
            "assistant_body": "[idea-to-code][Planner/agent] Exploration Result: Required Now = TASK-1 / REQ-1.",
        },
        {
            "name": "ready_summary_rejected",
            "expect_ok": False,
            "kind": "ready",
            "tool_stdout": "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample\n",
            "assistant_body": "[idea-to-code][Implementer/agent] READY Focus TASK-1 / REQ-1: files are sample.py.",
        },
        {
            "name": "formal_status_valid",
            "expect_ok": True,
            "kind": "formal-status",
            "tool_stdout": _sample_formal_status_body(),
            "assistant_body": _sample_formal_status_body(),
        },
        {
            "name": "formal_status_missing_fields_rejected",
            "expect_ok": False,
            "kind": "formal-status",
            "tool_stdout": _sample_formal_status_body(),
            "assistant_body": "[idea-to-code][Closer/agent] Status: Completed\n\nChanges:\n- TASK-1 / REQ-1: done.\n",
        },
        {
            "name": "ordinary_answer_valid",
            "expect_ok": True,
            "kind": "ordinary",
            "tool_stdout": "",
            "assistant_body": "[idea-to-code][Planner/agent] IMP-* is optional and TASK-* remains the execution gate.",
        },
        {
            "name": "ordinary_overtemplated_rejected",
            "expect_ok": False,
            "kind": "ordinary",
            "tool_stdout": "",
            "assistant_body": "[idea-to-code][Planner/agent] Explanation.\n\nChanges:\n- TASK-1 / REQ-1: none.",
        },
    ]
    results = []
    for scenario in scenarios:
        kind = str(scenario["kind"])
        if kind == "ready":
            problems = validate_visible_ready_output(str(scenario["tool_stdout"]), str(scenario["assistant_body"]))
        elif kind == "formal-status":
            problems = validate_formal_status_visible_output(str(scenario["tool_stdout"]), str(scenario["assistant_body"]))
        else:
            problems = validate_ordinary_visible_output(str(scenario["assistant_body"]))
        actual_ok = not problems
        expect_ok = bool(scenario["expect_ok"])
        results.append({
            "name": scenario["name"],
            "kind": kind,
            "expect_ok": expect_ok,
            "actual_ok": actual_ok,
            "pass": actual_ok == expect_ok,
            "problems": problems,
        })
    payload = {
        "schema": "idea-to-code.output-compliance.self-test.v1",
        "ok": all(item["pass"] for item in results),
        "scenario_count": len(results),
        "results": results,
    }
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"output-compliance self-test: {'PASS' if payload['ok'] else 'FAIL'}")
        for item in results:
            print(f"- {item['name']}: {'PASS' if item['pass'] else 'FAIL'}")
            for problem in item["problems"]:
                print(f"  - {problem}")
    return 0 if payload["ok"] else 1


def print_ledger(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    path = target / EXECUTION_LOG_FILE
    if not path.exists():
        raise SystemExit(f"missing: {EXECUTION_LOG_FILE}")
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def _fresh_benchmark_artifact_path(target: Path) -> Path:
    return target / "artifacts" / "fresh-session-live-benchmark.md"


def _fresh_benchmark_raw_output_path(target: Path) -> Path:
    return target / "artifacts" / "fresh-session-raw-output.txt"


def _fresh_benchmark_scores_path(target: Path) -> Path:
    return target / "artifacts" / "fresh-session-scores.json"


FRESH_BENCHMARK_RAW_OUTPUT_MARKERS = (
    "[idea-to-code]",
    "/fresh-agent]",
    "Exploration Result",
    "Implementation Gate: READY",
    "EXPLORATION_OUTPUT_ID",
    "READY_TASK_OUTPUT_ID",
)

FRESH_BENCHMARK_SCORE_TOTAL_FIELDS = ("total", "total_score", "score")


def _fresh_benchmark_payload(target: Path, status: dict) -> dict:
    artifact = _fresh_benchmark_artifact_path(target)
    exists = artifact.exists()
    text = artifact.read_text(encoding="utf-8") if exists else ""
    lower_text = text.lower()
    raw_artifact_rel = status.get("fresh_benchmark_raw_output_artifact")
    raw_artifact = target / raw_artifact_rel if raw_artifact_rel else None
    raw_output_artifact_present = bool(raw_artifact and raw_artifact.exists() and raw_artifact.is_file())
    imported_scores = status.get("fresh_benchmark_scores")
    imported_scores_present = isinstance(imported_scores, dict) and bool(imported_scores)
    imported_external_status = status.get("fresh_benchmark_external_run_status")
    raw_outputs_present_from_text = (
        exists
        and "Raw output:" in text
        and "`<transcript id or artifact path>`" not in text
        and "<transcript id or artifact path>" not in text
        and "<paste" not in lower_text
    )
    raw_outputs_present = raw_output_artifact_present or raw_outputs_present_from_text
    scores_present_from_text = bool(exists and re.search(r"Total score:\s*`?\d+/63`?", text))
    scores_present = imported_scores_present or scores_present_from_text
    if imported_external_status:
        external_completed = imported_external_status == "completed"
        external_partial = imported_external_status == "partial"
        external_unavailable = imported_external_status == "unavailable"
    else:
        external_completed = bool(exists and re.search(r"External run status:\s*`?completed`?", text))
        external_partial = bool(exists and re.search(r"External run status:\s*`?partial`?", text))
        external_unavailable = bool(exists and re.search(r"External run status:\s*`?unavailable`?", text))
    live_evidence_created = exists and raw_outputs_present and scores_present and external_completed
    if not exists:
        state_value = "missing"
        next_required_action = "run fresh-benchmark init to create the scaffold artifact before any external fresh-session claim"
    elif live_evidence_created:
        state_value = "completed"
        next_required_action = "review the recorded raw outputs and scores before using them as live fresh-session evidence"
    elif external_unavailable:
        state_value = "unavailable"
        next_required_action = "record the external-run limitation in status or closeout; do not claim completed live fresh-session evidence"
    elif external_partial or raw_outputs_present or scores_present:
        state_value = "partial"
        missing = []
        if not raw_outputs_present:
            missing.append("raw output artifact")
        if not scores_present:
            missing.append("score JSON")
        if not external_completed:
            missing.append("External run status: completed")
        if imported_external_status or raw_outputs_present or scores_present:
            next_required_action = "complete missing fresh-session evidence: " + ", ".join(missing)
        else:
            next_required_action = "record which raw outputs or scores are missing, then complete or treat as partial external validation"
    else:
        state_value = "scaffolded"
        next_required_action = "run a separate fresh session, then import raw output and score JSON with fresh-benchmark import-result"
    return {
        "path": str(artifact),
        "exists": exists,
        "state": state_value,
        "external_run_required": not live_evidence_created,
        "live_evidence_created": live_evidence_created,
        "evidence_ready": live_evidence_created,
        "raw_outputs_present": raw_outputs_present,
        "scores_present": scores_present,
        "external_run_completed": external_completed,
        "external_run_partial": external_partial,
        "external_run_unavailable": external_unavailable,
        "next_required_action": next_required_action,
        "recorded_artifact": status.get("fresh_benchmark_artifact"),
        "raw_output_artifact": raw_artifact_rel,
        "score_artifact": status.get("fresh_benchmark_score_artifact"),
        "external_run_status": imported_external_status,
        "scores": imported_scores if isinstance(imported_scores, dict) else None,
    }


FRESH_SESSION_TEMPLATE_HEADING = "## Copyable Fresh-Session Result Template"


def _fresh_benchmark_template_text() -> str:
    benchmark = Path(__file__).parent.parent / "references" / "controlled-exploration-benchmark.md"
    if not benchmark.exists():
        raise SystemExit(f"fresh-benchmark init refused - missing benchmark reference: {benchmark}")
    text = benchmark.read_text(encoding="utf-8")
    marker = FRESH_SESSION_TEMPLATE_HEADING
    if marker not in text:
        raise SystemExit(f"fresh-benchmark init refused - missing template heading: {benchmark}#{marker}")
    section = text.split(marker, 1)[1]
    match = re.search(r"```text\s*\n(?P<body>.*?)\n```", section, flags=re.S)
    if not match:
        raise SystemExit(f"fresh-benchmark init refused - missing copyable template block: {benchmark}#{marker}")
    return "# Fresh-Session Live Benchmark Template\n\n" + match.group("body").strip() + "\n"


def fresh_benchmark_init(root: Path, slug: str, force: bool) -> int:
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    artifact = _fresh_benchmark_artifact_path(target)
    if artifact.exists() and not force:
        raise SystemExit(f"fresh-benchmark init refused - artifact already exists: {artifact}")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    text = _fresh_benchmark_template_text()
    header = (
        "<!-- Generated by idea-to-code fresh-benchmark init. "
        "This is not live evidence until a separate fresh-session run adds raw outputs and scores. -->\n\n"
    )
    artifact.write_text(header + text, encoding="utf-8")
    with bundle_lock(target):
        status = read_status(target)
        status["fresh_benchmark_artifact"] = str(artifact.relative_to(target))
        status["fresh_benchmark_external_run_required"] = True
        status["fresh_benchmark_initialized_at_utc"] = utc_now()
        status["fresh_benchmark_event_sequence"] = _next_event_sequence(status)
        write_status(target, status)
        append_ledger(target, "fresh-benchmark-init", f"Initialized fresh-session benchmark artifact: {artifact.relative_to(target)}")
    print(json.dumps(_fresh_benchmark_payload(target, status), indent=2, ensure_ascii=False))
    return 0


def fresh_benchmark_import_result(root: Path, slug: str, raw_output_file: str, scores_json: str, external_status: str) -> int:
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    artifact = _fresh_benchmark_artifact_path(target)
    if not artifact.exists():
        raise SystemExit(f"fresh-benchmark import-result refused - run fresh-benchmark init first: {artifact}")
    source = Path(raw_output_file).expanduser()
    if not source.is_file():
        raise SystemExit(f"fresh-benchmark import-result refused - raw output file not found: {source}")
    try:
        scores = json.loads(scores_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"fresh-benchmark import-result refused - invalid score JSON: {exc}") from exc
    if not isinstance(scores, dict) or not scores:
        raise SystemExit("fresh-benchmark import-result refused - scores-json must be a non-empty JSON object")

    raw_dest = _fresh_benchmark_raw_output_path(target)
    scores_dest = _fresh_benchmark_scores_path(target)
    raw_dest.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != raw_dest.resolve():
        shutil.copyfile(source, raw_dest)
    scores_dest.write_text(json.dumps(scores, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    raw_rel = str(raw_dest.relative_to(target))
    scores_rel = str(scores_dest.relative_to(target))
    summary = (
        "\n## Imported Fresh-Session Result\n\n"
        f"- Raw output: {raw_rel}\n"
        f"- Score JSON: {scores_rel}\n"
        f"- External run status: {external_status}\n"
    )
    if not artifact.read_text(encoding="utf-8").endswith(summary):
        artifact.write_text(artifact.read_text(encoding="utf-8").rstrip() + "\n" + summary, encoding="utf-8")
    with bundle_lock(target):
        status = read_status(target)
        status["fresh_benchmark_artifact"] = str(artifact.relative_to(target))
        status["fresh_benchmark_raw_output_artifact"] = raw_rel
        status["fresh_benchmark_score_artifact"] = scores_rel
        status["fresh_benchmark_scores"] = scores
        status["fresh_benchmark_external_run_status"] = external_status
        status["fresh_benchmark_external_run_required"] = external_status != "completed"
        status["fresh_benchmark_imported_at_utc"] = utc_now()
        status["fresh_benchmark_event_sequence"] = _next_event_sequence(status)
        write_status(target, status)
        append_ledger(target, "fresh-benchmark-import-result", f"Imported fresh-session result with external status: {external_status}")
    print(json.dumps(_fresh_benchmark_payload(target, status), indent=2, ensure_ascii=False))
    return 0


def _fresh_benchmark_import_verification(target: Path, status: dict) -> dict:
    payload = _fresh_benchmark_payload(target, status)
    problems: list[str] = []
    raw_rel = status.get("fresh_benchmark_raw_output_artifact")
    score_rel = status.get("fresh_benchmark_score_artifact")
    raw_text = ""
    scores = status.get("fresh_benchmark_scores")

    if not payload["exists"]:
        problems.append("fresh-benchmark scaffold artifact is missing; run fresh-benchmark init first")
    if payload["state"] != "completed":
        problems.append("fresh-benchmark status must be completed before verify-import can pass")
    if status.get("fresh_benchmark_external_run_status") != "completed":
        problems.append("external-status must be completed")

    if not raw_rel:
        problems.append("import-result has not recorded a raw output artifact")
    else:
        raw_path = target / raw_rel
        if not raw_path.is_file():
            problems.append(f"raw output artifact missing: {raw_rel}")
        else:
            raw_text = raw_path.read_text(encoding="utf-8")
            for marker in FRESH_BENCHMARK_RAW_OUTPUT_MARKERS:
                if marker not in raw_text:
                    problems.append(f"raw output missing marker: {marker}")

    if not score_rel:
        problems.append("import-result has not recorded a score JSON artifact")
    else:
        score_path = target / score_rel
        if not score_path.is_file():
            problems.append(f"score JSON artifact missing: {score_rel}")
        else:
            try:
                artifact_scores = json.loads(score_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                problems.append(f"score JSON artifact is invalid JSON: {exc}")
            else:
                if artifact_scores != scores:
                    problems.append("score JSON artifact does not match imported state scores")

    if not isinstance(scores, dict) or not scores:
        problems.append("scores-json must be a non-empty JSON object")
    else:
        total_fields_present = [field for field in FRESH_BENCHMARK_SCORE_TOTAL_FIELDS if field in scores]
        if not total_fields_present:
            problems.append("scores-json must contain one of: total, total_score, score")
        detail_fields = [field for field in scores if field not in FRESH_BENCHMARK_SCORE_TOTAL_FIELDS]
        if not detail_fields:
            problems.append("scores-json must contain at least one detail field besides total")

    return {
        "schema": "idea-to-code.fresh-benchmark.verify-import.v1",
        "ok": not problems,
        "problems": problems,
        "state": payload["state"],
        "raw_output_artifact": raw_rel,
        "score_artifact": score_rel,
        "external_run_status": status.get("fresh_benchmark_external_run_status"),
        "required_markers": list(FRESH_BENCHMARK_RAW_OUTPUT_MARKERS),
        "score_total_fields": list(FRESH_BENCHMARK_SCORE_TOTAL_FIELDS),
        "marker_results": {marker: marker in raw_text for marker in FRESH_BENCHMARK_RAW_OUTPUT_MARKERS},
    }


def fresh_benchmark_verify_import(root: Path, slug: str) -> int:
    target = ensure_active_bundle(root, slug, allow_blocked=True)
    with bundle_lock(target):
        status = read_status(target)
        result = _fresh_benchmark_import_verification(target, status)
        status["fresh_benchmark_verify_import_ok"] = result["ok"]
        status["fresh_benchmark_verify_import_at_utc"] = utc_now()
        status["fresh_benchmark_verify_import_problems"] = result["problems"]
        status["fresh_benchmark_verify_import_event_sequence"] = _next_event_sequence(status)
        write_status(target, status)
        event = "fresh-benchmark-verify-import-pass" if result["ok"] else "fresh-benchmark-verify-import-fail"
        detail = "Verified imported fresh-session evidence" if result["ok"] else "; ".join(result["problems"])
        append_ledger(target, event, detail)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


def fresh_benchmark_status(root: Path, slug: str) -> int:
    target = ensure_bundle(root, slug)
    status = read_status(target)
    payload = _fresh_benchmark_payload(target, status)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["exists"] else 1


def branch_map(json_only: bool) -> int:
    branches = [_branch_with_invariants(branch) for branch in BRANCH_COVERAGE_MAP]
    payload = {
        "schema": "idea-to-code.branch-map.v1",
        "purpose": "lifecycle branch coverage map for entry, exit, validation, and failure handling",
        "branches": branches,
    }
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print("[idea-to-code][Reviewer/agent] Branch Coverage Map")
    print("")
    print(f"Schema: {payload['schema']}")
    print(f"Purpose: {payload['purpose']}")
    print("")
    for branch in BRANCH_COVERAGE_MAP:
        print(f"- {branch['id']}")
        print(f"  - Workflow Branch: {branch['workflow_branch']}")
        print(f"  - Entry: {branch['entry']}")
        print(f"  - Exit: {branch['exit']}")
        print(f"  - Validation: {branch['validation']}")
        print(f"  - Failure Handling: {branch['failure_handling']}")
    return 0


def _branch_with_invariants(branch: dict) -> dict:
    enriched = dict(branch)
    invariants = dict(BRANCH_INVARIANT_DEFAULTS)
    invariants.update(BRANCH_INVARIANT_OVERRIDES.get(branch.get("id", ""), {}))
    enriched.update(invariants)
    return enriched


def _workflow_branch_labels() -> list[str]:
    workflow = Path(__file__).parent.parent / "references" / "workflow.md"
    if not workflow.exists():
        return []
    text = workflow.read_text(encoding="utf-8")
    if "Branch closure checks for output compliance:" not in text:
        return []
    section = text.split("Branch closure checks for output compliance:", 1)[1]
    return re.findall(r"^- ([^:\n]+ branch):", section, flags=re.MULTILINE)


def validate_lifecycle_invariants(branches: list[dict], workflow_labels: list[str] | None = None) -> list[str]:
    problems: list[str] = []
    labels = [branch.get("workflow_branch", "") for branch in branches]
    if len(labels) != len(set(labels)):
        problems.append("lifecycle invariant audit failed - duplicate workflow_branch labels")
    ids = [branch.get("id", "") for branch in branches]
    if len(ids) != len(set(ids)):
        problems.append("lifecycle invariant audit failed - duplicate branch ids")
    if workflow_labels is not None and labels != workflow_labels:
        problems.append("lifecycle invariant audit failed - branch-map order does not match workflow.md branch bullets")
    for branch in branches:
        branch_id = branch.get("id", "<missing-id>")
        for field in BRANCH_INVARIANT_REQUIRED_FIELDS:
            if not str(branch.get(field, "")).strip():
                problems.append(f"branch {branch_id} missing lifecycle invariant field: {field}")
        boundary = branch.get("enforcement_boundary")
        if boundary and boundary not in ENFORCEMENT_BOUNDARIES:
            problems.append(f"branch {branch_id} has invalid enforcement_boundary: {boundary}")
    return problems


def lifecycle_audit(json_only: bool) -> int:
    branches = [_branch_with_invariants(branch) for branch in BRANCH_COVERAGE_MAP]
    problems = validate_lifecycle_invariants(branches, _workflow_branch_labels())
    payload = {
        "schema": "idea-to-code.lifecycle-audit.v1",
        "ok": not problems,
        "branch_count": len(branches),
        "required_invariant_fields": list(BRANCH_INVARIANT_REQUIRED_FIELDS),
        "enforcement_boundaries": list(ENFORCEMENT_BOUNDARIES),
        "problems": problems,
    }
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif problems:
        print("lifecycle-audit: FAIL")
        for problem in problems:
            print(f"- {problem}")
    else:
        print(f"lifecycle-audit: PASS branches={len(branches)}")
    return 0 if not problems else 1


COMMAND_GUIDE_FLOWS: dict[str, list[dict[str, str]]] = {
    "start": [
        {
            "step": "Create a structured bundle",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" init --root "$(pwd)" --slug <slug> --title "<title>" --idea "<idea>"',
            "notes": "Use init for tracked work that needs docs, tests, install, or runtime evidence.",
        },
        {
            "step": "Create a ready one-task bundle only when eligible",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" quickstart --root "$(pwd)" --slug <slug> --title "<title>" --idea "<idea>" --task "<task>" --file <path> --verification "<validation type and command>"',
            "notes": "quickstart requires --task and may refuse broad work; use init when refused.",
        },
        {
            "step": "Read current bundle",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" current status --root "$(pwd)"',
            "notes": "current status does not take --slug; bundle status does.",
        },
        {
            "step": "Read a specific bundle status",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" status --root "$(pwd)" --slug <slug>',
            "notes": "status requires --slug.",
        },
    ],
    "planning-update": [
        {
            "step": "Record latest user input when it changes scope",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" user-input record --root "$(pwd)" --slug <slug> --summary "<summary>" --classification clarification|expand|switch --rationale "<rationale>" --action "<action>" --changes-plan yes',
            "notes": "Use --changes-plan yes only when requirements/design/implementation must refresh.",
        },
        {
            "step": "Update requirements",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" update --root "$(pwd)" --slug <slug> --file requirements --content-file <requirements.md>',
            "notes": "update for requirements/design/implementation clears the matching pending section and refreshes plan revision.",
        },
        {
            "step": "Update design",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" update --root "$(pwd)" --slug <slug> --file design --content-file <design.md>',
            "notes": "Use content files for substantial sections to avoid shell quoting mistakes.",
        },
        {
            "step": "Update implementation",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" update --root "$(pwd)" --slug <slug> --file implementation --content-file <implementation.md>',
            "notes": "Implementation plan must have concrete TASK blocks before READY.",
        },
        {
            "step": "Mark READY after plan update",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation ready --root "$(pwd)" --slug <slug> --task TASK-1',
            "notes": "If the plan has multiple MB IDs, run backlog sync first.",
        },
        {
            "step": "Check TASK/IMP markdown structure after manual edits",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation plan-check --root "$(pwd)" --slug <slug> --json',
            "notes": "Run before READY when 00-idea.md was edited manually.",
        },
    ],
    "implementation-edit": [
        {
            "step": "Ask the Display Layer controller for the next required action",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation next-action --root "$(pwd)" --slug <slug> --task TASK-1 --files <path-a> <path-b> --json',
            "notes": "If it reports NEEDS_READY, NEEDS_TASK_ENTRY, or NEEDS_VISIBLE_OUTPUT_RECORD, show and record the required assistant-visible Display Layer before editing.",
        },
        {
            "step": "Recover missing or stale READY before retrying edit gates",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation recover-ready --root "$(pwd)" --slug <slug> --task TASK-1',
            "notes": "Use once after READY/show-ready/enter-task/pre-edit refusal caused by missing or stale READY; then run the recommended command.",
        },
        {
            "step": "Enter the current TASK",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation enter-task --root "$(pwd)" --slug <slug> --task TASK-1',
            "notes": "Shows focused READY for the TASK and records current_task_id.",
        },
        {
            "step": "Acquire write lease for all edited files",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation lease acquire --root "$(pwd)" --slug <slug> --task TASK-1 --owner agent --files <path-a> <path-b>',
            "notes": "Use --files for grouped multi-file edits; repeat --file only for compatibility.",
        },
        {
            "step": "Run pre-edit guard",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation pre-edit --root "$(pwd)" --slug <slug> --task TASK-1 --files <path-a> <path-b>',
            "notes": "Do not edit until this prints PRE_EDIT_OK_ID.",
        },
    ],
    "evidence": [
        {
            "step": "Record role evidence serially",
            "command": "Do not run role record commands in parallel; record Planner, Implementer, Validator, Reviewer, then Closer one at a time.",
            "notes": "Role evidence is an ordered mutation sequence. Parallel role record calls can race the plan_revision and role-order gates.",
        },
        {
            "step": "Inspect role evidence requirements",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" role explain --role implementer',
            "notes": "Run after a role record rejection instead of guessing wording.",
        },
        {
            "step": "Record Implementer evidence",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" role record --root "$(pwd)" --slug <slug> --role implementer --covers REQ-1 --evidence "<TASK/REQ, READY_TASK_OUTPUT_ID, PRE_EDIT_OK_ID, files changed, validation boundary>"',
            "notes": "Implementer evidence must name TASK/IMP IDs and cite current PRE_EDIT_OK_ID when present.",
        },
        {
            "step": "Record Validator evidence",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" role record --root "$(pwd)" --slug <slug> --role validator --covers REQ-1 --evidence "<TASK/REQ validation type source-only|real-product-path plus commands and results>"',
            "notes": "Every validation claim needs a validation type.",
        },
        {
            "step": "Record Reviewer evidence",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" role record --root "$(pwd)" --slug <slug> --role reviewer --covers REQ-1 --evidence "<TASK/REQ same-agent review or independent review with usable delegation record>"',
            "notes": "Do not claim independent review without a usable delegation record.",
        },
    ],
    "closeout": [
        {
            "step": "Record checkpoint",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" checkpoint --root "$(pwd)" --slug <slug> --milestone "<name>" --delivered "<what changed>" --verified "<validation type and evidence>" --next "<next>" --focus "<TASK/REQ focus>" --gate "<gate>" --gate-status pass --covers REQ-1',
            "notes": "checkpoint requires --verified, --next, --focus, --gate, --gate-status, and --covers for traceability.",
        },
        {
            "step": "Run pre-close verify",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" verify --root "$(pwd)" --slug <slug>',
            "notes": "Run after Reviewer evidence and before Closer/finalize.",
        },
        {
            "step": "Record Closer evidence",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" role record --root "$(pwd)" --slug <slug> --role closer --covers REQ-1 --evidence "<TASK/REQ closeout work: pre-close verify passed, coverage, remaining risks, no incomplete scoped work>"',
            "notes": "Closer evidence must state pre-close verify passed.",
        },
        {
            "step": "Finalize accepted scope",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" finalize --root "$(pwd)" --slug <slug> --summary "<summary>" --verification "<validation type and evidence>" --risks "<risks or none>" --acceptance "<accepted scope>" --gate-status pass --decision accepted --deferred "<remaining backlog or none>"',
            "notes": "finalize requires full closeout fields; do not pass only --status.",
        },
        {
            "step": "Run final verify",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" verify --root "$(pwd)" --slug <slug>',
            "notes": "Run after finalize before final status.",
        },
        {
            "step": "Render formal status",
            "command": 'python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" render-status --root "$(pwd)" --slug <slug> --status Completed',
            "notes": "Use generated fields for formal tracked handoff.",
        },
    ],
}


def command_guide(flow: str, json_only: bool) -> int:
    flows = COMMAND_GUIDE_FLOWS if flow == "all" else {flow: COMMAND_GUIDE_FLOWS[flow]}
    payload = {
        "schema": "idea-to-code.command-guide.v1",
        "flow": flow,
        "flows": flows,
        "rule": "After an argparse usage failure or before an unfamiliar lifecycle command, inspect this guide or targeted --help before retrying.",
    }
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print("[idea-to-code][Planner/agent] Command Guide")
    print("")
    print(f"Flow: {flow}")
    print("Rule: " + payload["rule"])
    for flow_name, commands in flows.items():
        print("")
        print(f"## {flow_name}")
        for item in commands:
            print(f"- {item['step']}")
            print(f"  Command: {item['command']}")
            print(f"  Notes: {item['notes']}")
    return 0


def host_pre_edit_contract(json_only: bool) -> int:
    payload = {
        "schema": "idea-to-code.host-hook.pre-edit-contract.v1",
        "enforcement_boundary": "host-required",
        "purpose": "Physically block native file-editing tools until idea-to-code Display Layer and pre-edit gates pass.",
        "required_inputs": ["root", "slug", "task_id", "owner", "files", "assistant_visible_body"],
        "required_checks": [
            "implementation next-action returns READY_FOR_EDIT or a non-edit action that is resolved before writing",
            "assistant_visible_body contains current Exploration Result and READY Focus when next-action requires it",
            "implementation visible-output record exists for current READY_TASK_OUTPUT_ID and EXPLORATION_OUTPUT_ID",
            "implementation lease acquire has non-overlapping ownership for every file",
            "implementation pre-edit returns PRE_EDIT_OK_ID for the exact task and files",
            "write paths are a subset of the current TASK Files list",
        ],
        "deny_when": [
            "next-action is NEEDS_READY, NEEDS_TASK_ENTRY, or NEEDS_VISIBLE_OUTPUT_RECORD",
            "VISIBLE_OUTPUT_ID is missing or stale",
            "LEASE_ID is missing, stale, overlapping, or owned by another agent",
            "PRE_EDIT_OK_ID is missing, stale, wrong-task, or missing any write file",
            "any write file is outside TASK scope",
        ],
        "allow_evidence": [
            "EXPLORATION_OUTPUT_ID",
            "READY_TASK_OUTPUT_ID",
            "VISIBLE_OUTPUT_ID",
            "LEASE_ID",
            "PRE_EDIT_OK_ID",
        ],
        "host_integration_notes": [
            "This repository can expose and verify the contract but cannot physically intercept native edit tools.",
            "A compliant host hook must run before every native write operation and fail closed on missing evidence.",
            "Fallback repository commands such as guarded-apply remain useful but are not equivalent to host interception.",
        ],
    }
    if json_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print("[idea-to-code][Reviewer/agent] Host Hook Contract: pre-edit")
    print("")
    print(f"Schema: {payload['schema']}")
    print(f"Enforcement Boundary: {payload['enforcement_boundary']}")
    print(f"Purpose: {payload['purpose']}")
    print("")
    print("Required Checks:")
    for item in payload["required_checks"]:
        print(f"- {item}")
    print("")
    print("Deny When:")
    for item in payload["deny_when"]:
        print(f"- {item}")
    print("")
    print("Allow Evidence:")
    for item in payload["allow_evidence"]:
        print(f"- {item}")
    return 0


def verify_bundle(root: Path, slug: str) -> int:
    """Structural sanity check. Exits non-zero when required pieces are missing."""
    target = ensure_bundle(root, slug)
    with bundle_lock(target):
        status = read_status(target) if state_exists(target) else {}
        require_closer = status.get("state") in {"completed", "closed"} or bool(status.get("finalized_at_utc"))
        problems = _bundle_integrity_problems(target, require_closer=require_closer)
        coverage = _coverage_by_requirement(status)
        current = read_current(root)
        active_writable = (
            current is not None
            and current.get("slug") == slug
            and status.get("state") not in {"blocked", "paused", "completed", "closed"}
        )
        if target.exists() and state_exists(target) and active_writable:
            status["last_verify_ok"] = not problems
            status["last_verified_plan_revision"] = status.get("plan_revision")
            status["last_verified_at_utc"] = utc_now()
            status["last_verified_event_sequence"] = _next_event_sequence(status)
            write_status(target, status)
            outcome = "pass" if not problems else "fail"
            append_ledger(target, "verify", f"Verification {outcome}; problems={len(problems)}")

    result = {
        "path": str(target),
        "ok": not problems,
        "problems": problems,
        "requirement_count": len(status.get("requirements", [])),
        "coverage": {
            rid: [m["name"] for m in covers]
            for rid, covers in coverage.items()
        },
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not problems else 1


def rebuild_markdown(root: Path, slug: str) -> Path:
    """Regenerate 01-progress.md from state.json."""
    target = ensure_active_bundle(root, slug)
    status = read_status(target)
    progress_path = target / PROGRESS_FILE
    if progress_path.exists():
        backup = progress_path.with_suffix(progress_path.suffix + ".bak")
        shutil.copy2(progress_path, backup)

    lines: list[str] = ["# Progress", ""]

    state = status.get("state", "in_progress")
    focus = status.get("current_focus") or ""
    next_gate = status.get("next_gate") or ""
    current_block = ["## Current Phase", "", f"- Status: {state}"]
    if state == "completed" or state == "closed":
        gate_status = status.get("gate_status")
        decision = status.get("decision")
        current_block.append("- Current focus: final report delivered")
        if gate_status:
            current_block.append(f"- Gate status: {gate_status}")
        if decision:
            current_block.append(f"- Decision: {decision}")
    elif state == "blocked":
        latest_block = None
        for blk in status.get("blocks", []):
            if "resolved_at_utc" not in blk:
                latest_block = blk
                break
        reason = latest_block["reason"] if latest_block else ""
        need = latest_block["need"] if latest_block else ""
        current_block.append(f"- Current focus: BLOCKED: {reason}")
        current_block.append(f"- Next gate: unblock: {need}")
    else:
        current_block.append(f"- Current focus: {focus}")
        current_block.append(f"- Next gate: {next_gate}")
    current_block.append("")
    lines.extend(current_block)

    lines.append("## Milestone History")
    lines.append("")

    events: list[tuple[str, dict]] = []
    for m in status.get("milestones", []):
        events.append(("milestone", m))
    for blk in status.get("blocks", []):
        events.append(("block", blk))
    events.sort(key=lambda pair: pair[1].get("timestamp_utc", ""))

    for kind, entry in events:
        ts = entry.get("timestamp_utc", "")
        if kind == "milestone":
            gate_suffix = f" (gate: {entry['gate_status']})" if entry.get("gate_status") else ""
            lines.append(f"## {entry['name']}{gate_suffix}")
            lines.append("")
            lines.append(f"- Timestamp: {ts}")
            lines.append(f"- Delivered: {entry.get('delivered', '')}")
            lines.append(f"- Verified: {entry.get('verified', '')}")
            lines.append(f"- Next: {entry.get('next', '')}")
            if entry.get("covers"):
                lines.append(f"- Covers: {', '.join(entry['covers'])}")
            lines.append("")
        else:
            lines.append(f"## Blocker at {ts}")
            lines.append("")
            lines.append(f"- Reason: {entry.get('reason', '')}")
            lines.append(f"- Needed to proceed: {entry.get('need', '')}")
            if "resolved_at_utc" in entry:
                lines.append(f"- Resolved at: {entry['resolved_at_utc']}")
            lines.append(f"- Resolution: {entry.get('resolution', '')}")
            lines.append("")

    lines.extend([
        "## Local Records",
        "",
    ])
    for record in status.get("local_records", []):
        covers = f"; covers: {', '.join(record.get('covers') or [])}" if record.get("covers") else ""
        lines.extend([
            f"### {record.get('id', '')} ({record.get('kind', '')})",
            "",
            f"- Timestamp: {record.get('timestamp_utc', '')}",
            f"- Text: {record.get('text', '')}{covers}",
            "",
        ])

    lines.extend([
        "## Role Gates",
        "",
        _render_role_evidence(status).rstrip(),
        "",
        "## Verification",
        "",
        "Validation types: real-product-path, mock-only, fixture-only, source-only, dom-only, manual-inspection, unverified.",
        "",
        "## Coverage Expectations",
        "",
        "- Build:",
        "- Unit/Integration:",
        "- End-to-end flow:",
        "- Remaining gaps:",
        "",
        "## Verification History",
        "",
    ])
    for m in status.get("milestones", []):
        gate_suffix = f" (gate: {m['gate_status']})" if m.get("gate_status") else ""
        lines.append(f"### Verification - {m['name']}{gate_suffix}")
        lines.append("")
        lines.append(f"- Timestamp: {m.get('timestamp_utc', '')}")
        lines.append(f"- Verified: {m.get('verified', '')}")
        if m.get("covers"):
            lines.append(f"- Covers: {', '.join(m['covers'])}")
        lines.append("")

    lines.extend([
        "## Risks",
        "",
        "-",
        "",
        "## Acceptance",
        "",
        "- Requested scope delivered:",
        "- Verification gate:",
        "- Decision:",
        "- Acceptance notes:",
        "- Deferred work:",
        "",
        "## Timeline",
        "",
    ])
    progress_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    return progress_path


# ---------- CLI ----------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage idea-to-code delivery artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Create the delivery bundle.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--idea", default="", help="Seed text for 00-idea.md User Idea section.")
    p.add_argument("--unique", action="store_true", help="Use YYYYMMDD-HHMM-<normalized-slug> and add -02/-03 on collision.")
    p.add_argument("--no-current", action="store_true", help="Do not write .idea-to-code/current.json.")

    p = sub.add_parser("quickstart", help="Create a ready one-task bundle for clear low-risk work.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--idea", required=True)
    p.add_argument("--file", required=True, help="Primary file or module to edit.")
    p.add_argument("--task", required=True, help="Concrete TASK-1 description.")
    p.add_argument("--verification", default="source-only inspect the changed file for the requested update")
    p.add_argument("--unique", action="store_true", help="Use YYYYMMDD-HHMM-<normalized-slug> and add -02/-03 on collision.")
    p.add_argument("--json", action="store_true", help="Print only machine-readable JSON instead of JSON plus READY TASK text.")

    p = sub.add_parser("doctor", help="Inspect project governance files and active bundle state.")
    p.add_argument("--root", required=True)

    sub.add_parser("contract", help="Print the fixed idea-to-code artifact contract.")

    p = sub.add_parser("test-batch", help="Run this skill's unittest suite in deterministic chunks.")
    p.add_argument("--chunk-size", type=int, default=40)
    p.add_argument("--timeout-seconds", type=int, default=180)
    p.add_argument("--limit", type=int, default=None, help="Optional test count limit for smoke validation.")
    p.add_argument("--profile", choices=tuple(TEST_BATCH_PROFILE_KEYWORDS), default="full", help="Validation profile to run.")
    p.add_argument("--slow-count", type=int, default=3, help="Number of slow chunks to summarize after a passing run.")

    p = sub.add_parser("route", help="Route incoming user input against the active idea-to-code bundle.")
    p.add_argument("--root", required=True)
    p.add_argument("--input", required=True, help="English summary of the incoming user request.")

    p = sub.add_parser("exploration", help="Render the user-visible Controlled Exploration gate.")
    exp_sub = p.add_subparsers(dest="exploration_command", required=True)
    er = exp_sub.add_parser("render", help="Render or refresh Exploration Result / Confirmation Required output.")
    er.add_argument("--root", required=True)
    er.add_argument("--slug", required=True)
    er.add_argument("--profile", default=None, help="Optional upper-layer profile label for exploration output.")

    p = sub.add_parser("fresh-benchmark", help="Initialize or inspect fresh-session benchmark artifacts.")
    fb_sub = p.add_subparsers(dest="fresh_benchmark_command", required=True)
    fbi = fb_sub.add_parser("init", help="Create a bundle-local fresh-session benchmark artifact from the template.")
    fbi.add_argument("--root", required=True)
    fbi.add_argument("--slug", required=True)
    fbi.add_argument("--force", action="store_true")
    fbs = fb_sub.add_parser("status", help="Report whether the fresh-session benchmark artifact exists and has live evidence.")
    fbs.add_argument("--root", required=True)
    fbs.add_argument("--slug", required=True)
    fbir = fb_sub.add_parser("import-result", help="Import raw fresh-session output and score JSON produced by an external run.")
    fbir.add_argument("--root", required=True)
    fbir.add_argument("--slug", required=True)
    fbir.add_argument("--raw-output-file", required=True)
    fbir.add_argument("--scores-json", required=True)
    fbir.add_argument("--external-status", required=True, choices=("completed", "partial", "unavailable"))
    fbv = fb_sub.add_parser("verify-import", help="Audit imported fresh-session evidence before treating it as evidence ready.")
    fbv.add_argument("--root", required=True)
    fbv.add_argument("--slug", required=True)

    p = sub.add_parser("branch-map", help="Print the lifecycle branch coverage map.")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")

    p = sub.add_parser("lifecycle-audit", help="Validate lifecycle branch invariant coverage.")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")

    p = sub.add_parser("command-guide", help="Print valid command shapes for common lifecycle flows.")
    p.add_argument("--flow", default="all", choices=[*COMMAND_GUIDE_FLOWS.keys(), "all"])
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")

    p = sub.add_parser("host-hook", help="Print host integration contracts for enforcement outside the repository.")
    host_sub = p.add_subparsers(dest="host_hook_command", required=True)
    hpc = host_sub.add_parser("pre-edit-contract", help="Print the native edit preflight hook contract.")
    hpc.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")

    p = sub.add_parser("output-compliance", help="Check user-visible output against tool stdout for display-layer compliance.")
    oc_sub = p.add_subparsers(dest="output_compliance_command", required=True)
    occ = oc_sub.add_parser("check", help="Validate READY, formal status, or ordinary answer output shape.")
    occ.add_argument("--kind", required=True, choices=("ready", "formal-status", "ordinary"))
    occ.add_argument("--tool-stdout")
    occ.add_argument("--tool-stdout-file")
    occ.add_argument("--assistant-body")
    occ.add_argument("--assistant-body-file")
    occ.add_argument("--json", action="store_true")
    ocs = oc_sub.add_parser("self-test", help="Run built-in hard-output compliance acceptance scenarios.")
    ocs.add_argument("--json", action="store_true")
    octa = oc_sub.add_parser("transcript-audit", help="Audit an exported transcript for assistant-visible hard-output compliance.")
    octa.add_argument("--transcript")
    octa.add_argument("--transcript-file")
    octa.add_argument("--json", action="store_true")

    p = sub.add_parser("checkpoint", help="Record a milestone.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--milestone", required=True)
    p.add_argument("--delivered", required=True)
    p.add_argument("--verified", required=True)
    p.add_argument("--next", dest="next_step", required=True)
    p.add_argument("--focus", required=True)
    p.add_argument("--gate", required=True, help="Human-readable next gate description.")
    p.add_argument("--gate-status", required=True, choices=GATE_CHOICES,
                   help="Verification outcome for this milestone: pass / partial / fail. Required - be honest; 'pass' with no evidence is how bundles get corrupted.")
    p.add_argument("--covers", action="append", default=[],
                   help="Requirement IDs this milestone delivers against. Repeat the flag or pass comma-separated IDs.")

    p = sub.add_parser("requirement", help="Manage the trace matrix (requirement IDs and coverage).")
    req_sub = p.add_subparsers(dest="requirement_command", required=True)
    ra = req_sub.add_parser("add", help="Register a new requirement.")
    ra.add_argument("--root", required=True)
    ra.add_argument("--slug", required=True)
    ra.add_argument("--id", dest="rid", required=True)
    ra.add_argument("--description", required=True)
    ra.add_argument("--type", dest="rtype", default="functional", choices=REQUIREMENT_TYPES)
    rr = req_sub.add_parser("remove", help="Delete a requirement.")
    rr.add_argument("--root", required=True)
    rr.add_argument("--slug", required=True)
    rr.add_argument("--id", dest="rid", required=True)
    rl = req_sub.add_parser("list", help="List requirements with coverage and aggregate gate status.")
    rl.add_argument("--root", required=True)
    rl.add_argument("--slug", required=True)

    p = sub.add_parser("backlog", help="Manage stable master backlog IDs for multi-issue work.")
    backlog_sub = p.add_subparsers(dest="backlog_command", required=True)
    bs = backlog_sub.add_parser("sync", help="Sync MB-* IDs from 00-idea.md into state.json.")
    bs.add_argument("--root", required=True)
    bs.add_argument("--slug", required=True)
    bst = backlog_sub.add_parser("status", help="Print master backlog state and coverage.")
    bst.add_argument("--root", required=True)
    bst.add_argument("--slug", required=True)
    bm = backlog_sub.add_parser("mark", help="Mark a master backlog item state.")
    bm.add_argument("--root", required=True)
    bm.add_argument("--slug", required=True)
    bm.add_argument("--id", required=True, help="Master backlog ID such as MB-2.")
    bm.add_argument("--status", required=True, choices=MASTER_BACKLOG_STATUSES)
    bm.add_argument("--reason", required=True)

    p = sub.add_parser("idea", help="Record and inspect same-session idea continuity.")
    idea_sub = p.add_subparsers(dest="idea_command", required=True)
    ir = idea_sub.add_parser("record", help="Record how a same-session idea maps to REQ scope.")
    ir.add_argument("--root", required=True)
    ir.add_argument("--slug", required=True)
    ir.add_argument("--id", dest="idea_id", required=True, help="Stable idea id such as IDEA-1.")
    ir.add_argument("--status", required=True, choices=IDEA_RECORD_STATUSES)
    ir.add_argument("--summary", required=True)
    ir.add_argument("--related-reqs", default="", help="Comma-separated REQ IDs related to this idea.")
    ir.add_argument("--notes", required=True)
    ist = idea_sub.add_parser("status", help="Print same-session idea records.")
    ist.add_argument("--root", required=True)
    ist.add_argument("--slug", required=True)

    p = sub.add_parser("record", help="Manage local structured sub-records under the active bundle.")
    record_sub = p.add_subparsers(dest="record_command", required=True)
    radd = record_sub.add_parser("add", help="Add a local sub-record.")
    radd.add_argument("--root", required=True)
    radd.add_argument("--slug", required=True)
    radd.add_argument("--id", dest="record_id", required=True)
    radd.add_argument("--kind", required=True, choices=sorted(LOCAL_RECORD_KINDS))
    radd.add_argument("--text", required=True)
    radd.add_argument("--covers", default="", help="Comma-separated requirement IDs this record covers.")
    rlist = record_sub.add_parser("list", help="List local sub-records.")
    rlist.add_argument("--root", required=True)
    rlist.add_argument("--slug", required=True)

    p = sub.add_parser("delegation", help="Record and inspect subagent/fresh-agent evidence attempts.")
    delegation_sub = p.add_subparsers(dest="delegation_command", required=True)
    dr = delegation_sub.add_parser("record", help="Record a delegation or fresh-agent evidence attempt.")
    dr.add_argument("--root", required=True)
    dr.add_argument("--slug", required=True)
    dr.add_argument("--role", required=True, choices=ROLE_NAMES)
    dr.add_argument("--status", required=True, choices=DELEGATION_STATUSES)
    dr.add_argument("--scope", required=True)
    dr.add_argument("--evidence-summary", required=True)
    dr.add_argument("--agent-id", default="")
    dr.add_argument("--reason", default="")
    ds = delegation_sub.add_parser("status", help="Print delegation evidence records.")
    ds.add_argument("--root", required=True)
    ds.add_argument("--slug", required=True)
    dz = delegation_sub.add_parser("resolve", help="Resolve a non-usable delegation finding without counting it as evidence.")
    dz.add_argument("--root", required=True)
    dz.add_argument("--slug", required=True)
    dz.add_argument("--id", required=True, help="Delegation record id to resolve.")
    dz.add_argument("--resolution", required=True, choices=("fallback-same-agent", "superseded", "accepted-risk", "invalid-record"))
    dz.add_argument("--reason", required=True)

    p = sub.add_parser("session", help="Record and inspect same-session continuity audits.")
    session_sub = p.add_subparsers(dest="session_command", required=True)
    sa = session_sub.add_parser("audit", help="Record how a follow-up relates to prior same-session scope.")
    sa.add_argument("--root", required=True)
    sa.add_argument("--slug", required=True)
    sa.add_argument("--relation", required=True, choices=SESSION_RELATIONS)
    sa.add_argument("--summary", required=True)
    sa.add_argument("--prior-scope", required=True)
    sa.add_argument("--decision", required=True)
    ss = session_sub.add_parser("status", help="Print session continuity audit records.")
    ss.add_argument("--root", required=True)
    ss.add_argument("--slug", required=True)

    p = sub.add_parser("scope", help="Record and inspect related-vs-unrelated scope classifications.")
    scope_sub = p.add_subparsers(dest="scope_command", required=True)
    sc = scope_sub.add_parser("classify", help="Record how a user follow-up relates to the active scope.")
    sc.add_argument("--root", required=True)
    sc.add_argument("--slug", required=True)
    sc.add_argument("--classification", required=True, choices=SESSION_RELATIONS)
    sc.add_argument("--summary", required=True)
    sc.add_argument("--rationale", required=True)
    sc.add_argument("--action", required=True)
    st = scope_sub.add_parser("status", help="Print scope classification records.")
    st.add_argument("--root", required=True)
    st.add_argument("--slug", required=True)

    p = sub.add_parser("user-input", help="Record how the latest user input affects the active task.")
    ui_sub = p.add_subparsers(dest="user_input_command", required=True)
    ur = ui_sub.add_parser("record", help="Append a user input decision record.")
    ur.add_argument("--root", required=True)
    ur.add_argument("--slug", required=True)
    ur.add_argument("--summary", required=True, help="English summary of the user input.")
    ur.add_argument("--classification", required=True, choices=USER_INPUT_CLASSIFICATIONS)
    ur.add_argument("--rationale", required=True, help="Why this classification is correct.")
    ur.add_argument("--action", required=True, help="What the agent will do next.")
    ur.add_argument("--changes-plan", required=True, choices=("yes", "no"))

    p = sub.add_parser("role", help="Record Planner/Implementer/Validator/Reviewer/Closer evidence.")
    role_sub = p.add_subparsers(dest="role_command", required=True)
    rr = role_sub.add_parser("record", help="Append concrete role evidence.")
    rr.add_argument("--root", required=True)
    rr.add_argument("--slug", required=True)
    rr.add_argument("--role", required=True, choices=ROLE_NAMES)
    rr.add_argument("--evidence", required=True)
    rr.add_argument("--covers", default="", help="Comma-separated requirement IDs this role evidence covers.")
    rexp = role_sub.add_parser("explain", help="Print read-only role evidence guidance as JSON.")
    rexp.add_argument("--role", choices=ROLE_NAMES, help="Limit guidance to one role.")
    rdraft = role_sub.add_parser("draft", help="Print a read-only role evidence draft for the current bundle state.")
    rdraft.add_argument("--root", required=True)
    rdraft.add_argument("--slug", required=True)
    rdraft.add_argument("--role", required=True, choices=ROLE_NAMES)
    rdraft.add_argument("--covers", default="", help="Comma-separated requirement IDs this evidence should cover.")
    rdraft.add_argument("--task", default=None, help="TASK/IMP id to draft evidence for, such as TASK-1.")
    rdraft.add_argument("--json", action="store_true", help="Print machine-readable draft output.")

    p = sub.add_parser("implementation", help="Check or mark the implementation gate.")
    impl_sub = p.add_subparsers(dest="implementation_command", required=True)
    ir = impl_sub.add_parser("ready", help=f"Mark implementation gate ready after {IMPLEMENTATION_FILE} is complete.")
    ir.add_argument("--root", required=True)
    ir.add_argument("--slug", required=True)
    ir.add_argument("--profile", default=None, help="Optional upper-layer profile label for READY output.")
    ir.add_argument("--role", default="planner", help="Visible lifecycle role for READY output.")
    ir.add_argument("--source", default="agent", help="Visible execution source for READY output.")
    ir.add_argument("--task", action="append", default=None, help="Limit READY output to a specific TASK/IMP id such as TASK-17. Repeat for multiple tasks.")
    ir.add_argument("--full-plan", action="store_true", help="Print every TASK/IMP block instead of the default focused first TASK/IMP excerpt.")
    isr = impl_sub.add_parser("show-ready", help="Reprint or refresh the READY TASK output.")
    isr.add_argument("--root", required=True)
    isr.add_argument("--slug", required=True)
    isr.add_argument("--profile", default=None, help="Optional upper-layer profile label for READY output.")
    isr.add_argument("--role", default="planner", help="Visible lifecycle role for READY output.")
    isr.add_argument("--source", default="agent", help="Visible execution source for READY output.")
    isr.add_argument("--task", action="append", default=None, help="Limit READY output to a specific TASK/IMP id such as TASK-17. Repeat for multiple tasks.")
    isr.add_argument("--full-plan", action="store_true", help="Print every TASK/IMP block instead of the default focused first TASK/IMP excerpt.")
    irr = impl_sub.add_parser("recover-ready", help="Diagnose missing or stale READY and print exact recovery commands.")
    irr.add_argument("--root", required=True)
    irr.add_argument("--slug", required=True)
    irr.add_argument("--task", default=None, help="Current TASK/IMP id to recover for, such as TASK-1.")
    irr.add_argument("--json", action="store_true")
    ipc = impl_sub.add_parser("plan-check", help="Validate parseable TASK/IMP plan structure without changing state.")
    ipc.add_argument("--root", required=True)
    ipc.add_argument("--slug", required=True)
    ipc.add_argument("--json", action="store_true")
    iet = impl_sub.add_parser("enter-task", help="Record the current TASK and print its READY Focus before edits.")
    iet.add_argument("--root", required=True)
    iet.add_argument("--slug", required=True)
    iet.add_argument("--task", required=True, help="TASK/IMP id to enter, such as TASK-2.")
    iet.add_argument("--profile", default=None, help="Optional upper-layer profile label for READY output.")
    iov = impl_sub.add_parser("overview", help="Print a closed-loop implementation overview without changing state.")
    iov.add_argument("--root", required=True)
    iov.add_argument("--slug", required=True)
    iov.add_argument("--profile", default=None, help="Optional upper-layer profile label for overview output.")
    ina = impl_sub.add_parser("next-action", help="Print the next required Display Layer or edit-gate action without changing state.")
    ina.add_argument("--root", required=True)
    ina.add_argument("--slug", required=True)
    ina.add_argument("--task", required=True, help="TASK/IMP id to inspect, such as TASK-1.")
    ina.add_argument("--file", action="append", default=[], help="File path intended for edit. Repeat for multiple files.")
    ina.add_argument("--files", nargs="+", action="append", default=[], help="Grouped file paths intended for edit, e.g. --files a.py b.py.")
    ina.add_argument("--owner", default="agent", help="Agent/session owner label expected to hold the write lease.")
    ina.add_argument("--json", action="store_true", help="Print machine-readable next-action output.")
    ina.add_argument("--profile", default=None, help="Optional upper-layer profile label for next-action output.")
    ivo = impl_sub.add_parser("visible-output", help="Record or inspect assistant-visible Exploration/READY display evidence.")
    visible_sub = ivo.add_subparsers(dest="implementation_visible_output_command", required=True)
    ivr = visible_sub.add_parser("record", help="Record the assistant-visible Exploration/READY block before pre-edit.")
    ivr.add_argument("--root", required=True)
    ivr.add_argument("--slug", required=True)
    ivr.add_argument("--task", required=True, help="TASK/IMP id whose READY block was displayed, such as TASK-1.")
    ivr.add_argument("--assistant-body")
    ivr.add_argument("--assistant-body-file")
    ivr.add_argument("--source", default="agent", choices=("agent", "subagent"))
    ivr.add_argument("--profile", default=None, help="Optional upper-layer profile label for record output.")
    ivs = visible_sub.add_parser("status", help="Print visible-output evidence records.")
    ivs.add_argument("--root", required=True)
    ivs.add_argument("--slug", required=True)
    il = impl_sub.add_parser("lease", help="Acquire, inspect, or release implementation write ownership.")
    lease_sub = il.add_subparsers(dest="implementation_lease_command", required=True)
    ila = lease_sub.add_parser("acquire", help="Acquire a write lease for TASK files before pre-edit.")
    ila.add_argument("--root", required=True)
    ila.add_argument("--slug", required=True)
    ila.add_argument("--task", required=True, help="TASK/IMP id about to be edited, such as TASK-3.")
    ila.add_argument("--owner", default="agent", help="Agent/session owner label for this write lease.")
    ila.add_argument("--file", action="append", default=[], help="File path to own for editing. Repeat for multiple files.")
    ila.add_argument("--files", nargs="+", action="append", default=[], help="Grouped file paths to own for editing, e.g. --files a.py b.py.")
    ila.add_argument("--profile", default=None, help="Optional upper-layer profile label for lease output.")
    ils = lease_sub.add_parser("status", help="Print implementation write leases.")
    ils.add_argument("--root", required=True)
    ils.add_argument("--slug", required=True)
    ilr = lease_sub.add_parser("release", help="Release an implementation write lease.")
    ilr.add_argument("--root", required=True)
    ilr.add_argument("--slug", required=True)
    ilr.add_argument("--id", required=True, help="Lease id to release.")
    ilr.add_argument("--reason", required=True)
    ipe = impl_sub.add_parser("pre-edit", help="Check current TASK and file scope before tracked edits.")
    ipe.add_argument("--root", required=True)
    ipe.add_argument("--slug", required=True)
    ipe.add_argument("--task", required=True, help="TASK/IMP id about to be edited, such as TASK-2.")
    ipe.add_argument("--file", action="append", default=[], help="File path about to be edited. Repeat for multiple files.")
    ipe.add_argument("--files", nargs="+", action="append", default=[], help="Grouped file paths about to be edited, e.g. --files a.py b.py.")
    ipe.add_argument("--owner", default="agent", help="Agent/session owner label that must hold the write lease.")
    ipe.add_argument("--profile", default=None, help="Optional upper-layer profile label for pre-edit output.")
    iga = impl_sub.add_parser("guarded-apply", help="Apply a git patch only after lease, current TASK, and pre-edit checks pass.")
    iga.add_argument("--root", required=True)
    iga.add_argument("--slug", required=True)
    iga.add_argument("--task", required=True, help="TASK/IMP id about to be edited, such as TASK-2.")
    iga.add_argument("--patch-file", required=True, help="Unified diff patch file to check and apply with git apply.")
    iga.add_argument("--owner", default="agent", help="Agent/session owner label that must hold the write lease.")
    iga.add_argument("--profile", default=None, help="Optional upper-layer profile label for guarded-apply output.")
    inc = impl_sub.add_parser("noncompliance", help="Record a pre-edit compliance lapse so status and verification cannot hide it.")
    inc.add_argument("--root", required=True)
    inc.add_argument("--slug", required=True)
    inc.add_argument("--task", required=True, help="TASK/IMP id affected by the lapse, such as TASK-2.")
    inc.add_argument("--reason", required=True)
    inc.add_argument("--file", action="append", default=[], help="Affected file path. Repeat for multiple files.")
    inc.add_argument("--profile", default=None, help="Optional upper-layer profile label for noncompliance output.")
    ist = impl_sub.add_parser("status", help="Print implementation gate status.")
    ist.add_argument("--root", required=True)
    ist.add_argument("--slug", required=True)

    p = sub.add_parser("current", help="Manage .idea-to-code/current.json and history/index.jsonl.")
    cur_sub = p.add_subparsers(dest="current_command", required=True)
    cs = cur_sub.add_parser("status", help="Print the active bundle pointer.")
    cs.add_argument("--root", required=True)
    cset = cur_sub.add_parser("set", help="Point current.json at an existing bundle.")
    cset.add_argument("--root", required=True)
    cset.add_argument("--slug", required=True)
    cc = cur_sub.add_parser("clear", help="Remove current.json without touching bundles.")
    cc.add_argument("--root", required=True)
    ca = cur_sub.add_parser("archive", help="Append the current bundle to history/index.jsonl and clear current.json.")
    ca.add_argument("--root", required=True)
    ca.add_argument("--reason", default="manual archive")
    cp = cur_sub.add_parser("pause", help="Pause the active current bundle without archiving it.")
    cp.add_argument("--root", required=True)
    cp.add_argument("--reason", required=True)
    cr = cur_sub.add_parser("resume", help="Resume the active paused bundle with a reason, optionally selecting a known unfinished slug first.")
    cr.add_argument("--root", required=True)
    cr.add_argument("--reason", required=True)
    cr.add_argument("--slug", default=None, help="Known unfinished bundle slug to set as current before resuming.")

    p = sub.add_parser("link",
                       help="Retroactively attach requirement IDs to an already-recorded milestone.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--milestone", required=True, help="Exact milestone name as recorded.")
    p.add_argument("--covers", required=True, help="Comma-separated requirement IDs.")
    p.add_argument("--replace", action="store_true",
                   help="Replace existing covers instead of merging.")

    p = sub.add_parser("rebuild-progress",
                       help=f"Regenerate {PROGRESS_FILE} from {STATE_FILE}.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)

    p = sub.add_parser("block", help="Mark bundle blocked on an external dependency.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--need", required=True, help="What decision or dependency is needed to resume.")

    p = sub.add_parser("unblock", help="Clear the blocked state.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--note", required=True)

    p = sub.add_parser("update", help="Replace or append to editable bundle docs.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--file", required=True, choices=sorted(EDITABLE_SECTIONS))
    p.add_argument("--content", default=None)
    p.add_argument("--content-file", default=None)
    p.add_argument("--append", action="store_true", help="Append instead of replacing the file.")

    p = sub.add_parser("finalize", help="Close the bundle and emit the final report.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--verification", required=True)
    p.add_argument("--risks", required=True)
    p.add_argument("--acceptance", required=True)
    p.add_argument("--gate-status", required=True, choices=GATE_CHOICES)
    p.add_argument("--decision", required=True, choices=DECISION_CHOICES)
    p.add_argument("--acceptance-notes", default="")
    p.add_argument("--deferred", default="")
    p.add_argument("--force", action="store_true",
                   help=f"Overwrite {FINAL_REPORT_FILE} without creating a .bak backup.")

    p = sub.add_parser("status", help="Print bundle status as JSON.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--full", action="store_true", help="Include milestone and blocker history.")

    p = sub.add_parser("render-status", help="Render a fixed-field formal status response skeleton.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--status", default=None, choices=["Completed", "Progress", "Blocked"])
    p.add_argument("--profile", default=None, help="Optional display profile for [idea-to-code/<profile>].")
    p.add_argument("--role", default="Closer")
    p.add_argument("--source", default="agent")

    p = sub.add_parser("ledger", help=f"Print {PROGRESS_FILE} for human lifecycle audit.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)

    p = sub.add_parser("verify", help="Check that the bundle is structurally complete.")
    p.add_argument("--root", required=True)
    p.add_argument("--slug", required=True)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "contract":
        return contract()

    if args.command == "role" and args.role_command == "explain":
        return role_explain(args.role)

    if args.command == "test-batch":
        return run_test_batch(args.chunk_size, args.timeout_seconds, args.limit, args.profile, args.slow_count)

    if args.command == "branch-map":
        return branch_map(args.json)

    if args.command == "lifecycle-audit":
        return lifecycle_audit(args.json)

    if args.command == "command-guide":
        return command_guide(args.flow, args.json)

    if args.command == "host-hook":
        if args.host_hook_command == "pre-edit-contract":
            return host_pre_edit_contract(args.json)

    if args.command == "output-compliance":
        if args.output_compliance_command == "check":
            if args.kind == "ordinary" and not args.tool_stdout and not args.tool_stdout_file:
                tool_stdout = ""
            else:
                tool_stdout = read_content_arg(args.tool_stdout, args.tool_stdout_file)
            assistant_body = read_content_arg(args.assistant_body, args.assistant_body_file)
            return output_compliance_check(args.kind, tool_stdout, assistant_body, args.json)
        if args.output_compliance_command == "self-test":
            return output_compliance_self_test(args.json)
        if args.output_compliance_command == "transcript-audit":
            transcript = read_content_arg(args.transcript, args.transcript_file)
            return output_compliance_transcript_audit(transcript, args.json)

    root = Path(args.root).resolve()

    if args.command == "init":
        target = init_bundle(root, args.slug, args.title, args.idea, args.unique, not args.no_current)
        print(target)
        return 0

    if args.command == "quickstart":
        target, ready_output_lines = quickstart_bundle(root, args.slug, args.title, args.idea, args.file, args.task, args.verification, args.unique)
        status = read_status(target)
        print(json.dumps({
            "path": str(target),
            "slug": target.name,
            "ready": True,
            "exploration_output_id": status.get("exploration_output_id"),
            "ready_task_output_id": status.get("ready_task_output_id"),
        }, indent=2, ensure_ascii=False))
        if not args.json:
            print()
            print("\n".join(ready_output_lines))
        return 0

    if args.command == "doctor":
        return doctor(root)

    if args.command == "route":
        return route_task(root, args.input)

    if args.command == "exploration":
        if args.exploration_command == "render":
            return exploration_render(root, args.slug, args.profile)

    if args.command == "fresh-benchmark":
        if args.fresh_benchmark_command == "init":
            return fresh_benchmark_init(root, args.slug, args.force)
        if args.fresh_benchmark_command == "status":
            return fresh_benchmark_status(root, args.slug)
        if args.fresh_benchmark_command == "import-result":
            return fresh_benchmark_import_result(root, args.slug, args.raw_output_file, args.scores_json, args.external_status)
        if args.fresh_benchmark_command == "verify-import":
            return fresh_benchmark_verify_import(root, args.slug)

    if args.command == "checkpoint":
        target = checkpoint_bundle(
            root, args.slug, args.milestone, args.delivered, args.verified,
            args.next_step, args.focus, args.gate, args.gate_status,
            _parse_ids(args.covers),
        )
        print(target)
        return 0

    if args.command == "requirement":
        if args.requirement_command == "add":
            print(requirement_add(root, args.slug, args.rid, args.description, args.rtype))
            return 0
        if args.requirement_command == "remove":
            print(requirement_remove(root, args.slug, args.rid))
            return 0
        if args.requirement_command == "list":
            return requirement_list(root, args.slug)

    if args.command == "backlog":
        if args.backlog_command == "sync":
            print(master_backlog_sync(root, args.slug))
            return 0
        if args.backlog_command == "status":
            return master_backlog_status(root, args.slug)
        if args.backlog_command == "mark":
            print(master_backlog_mark(root, args.slug, args.id, args.status, args.reason))
            return 0

    if args.command == "idea":
        if args.idea_command == "record":
            print(idea_record(
                root,
                args.slug,
                args.idea_id,
                args.status,
                args.summary,
                _parse_ids(args.related_reqs),
                args.notes,
            ))
            return 0
        if args.idea_command == "status":
            return idea_status(root, args.slug)

    if args.command == "record":
        if args.record_command == "add":
            print(local_record_add(root, args.slug, args.record_id, args.kind, args.text, _parse_ids(args.covers)))
            return 0
        if args.record_command == "list":
            return local_record_list(root, args.slug)

    if args.command == "delegation":
        if args.delegation_command == "record":
            print(delegation_record(
                root, args.slug, args.role, args.status, args.scope,
                args.evidence_summary, args.agent_id, args.reason,
            ))
            return 0
        if args.delegation_command == "status":
            return delegation_status(root, args.slug)
        if args.delegation_command == "resolve":
            print(delegation_resolve(root, args.slug, args.id, args.resolution, args.reason))
            return 0

    if args.command == "session":
        if args.session_command == "audit":
            print(session_audit(root, args.slug, args.relation, args.summary, args.prior_scope, args.decision))
            return 0
        if args.session_command == "status":
            return session_status(root, args.slug)

    if args.command == "scope":
        if args.scope_command == "classify":
            print(scope_classify(root, args.slug, args.classification, args.summary, args.rationale, args.action))
            return 0
        if args.scope_command == "status":
            return scope_status(root, args.slug)

    if args.command == "user-input":
        if args.user_input_command == "record":
            print(user_input_record(
                root,
                args.slug,
                args.summary,
                args.classification,
                args.rationale,
                args.action,
                args.changes_plan,
            ))
            return 0

    if args.command == "role":
        if args.role_command == "record":
            print(role_record(root, args.slug, args.role, args.evidence, _parse_ids(args.covers)))
            return 0
        if args.role_command == "draft":
            return role_draft(root, args.slug, args.role, _parse_ids(args.covers), args.task, args.json)

    if args.command == "implementation":
        if args.implementation_command == "ready":
            mark_implementation_ready(root, args.slug, args.profile, args.role, args.source, args.task, args.full_plan)
            return 0
        if args.implementation_command == "show-ready":
            return implementation_show_ready(root, args.slug, args.profile, args.role, args.source, args.task, args.full_plan)
        if args.implementation_command == "recover-ready":
            return implementation_recover_ready(root, args.slug, args.task, args.json)
        if args.implementation_command == "plan-check":
            return implementation_plan_check(root, args.slug, args.json)
        if args.implementation_command == "enter-task":
            return implementation_enter_task(root, args.slug, args.task, args.profile)
        if args.implementation_command == "overview":
            return implementation_overview(root, args.slug, args.profile)
        if args.implementation_command == "next-action":
            return implementation_next_action(root, args.slug, args.task, _combined_file_args(args.file, args.files), args.owner, args.json, args.profile)
        if args.implementation_command == "visible-output":
            if args.implementation_visible_output_command == "record":
                assistant_body = read_content_arg(args.assistant_body, args.assistant_body_file)
                return implementation_visible_output_record(root, args.slug, args.task, assistant_body, args.source, args.profile)
            if args.implementation_visible_output_command == "status":
                return implementation_visible_output_status(root, args.slug)
        if args.implementation_command == "lease":
            if args.implementation_lease_command == "acquire":
                return implementation_lease_acquire(root, args.slug, args.task, args.owner, _combined_file_args(args.file, args.files), args.profile)
            if args.implementation_lease_command == "status":
                return implementation_lease_status(root, args.slug)
            if args.implementation_lease_command == "release":
                print(implementation_lease_release(root, args.slug, args.id, args.reason))
                return 0
        if args.implementation_command == "pre-edit":
            return implementation_pre_edit(root, args.slug, args.task, _combined_file_args(args.file, args.files), args.owner, args.profile)
        if args.implementation_command == "guarded-apply":
            return implementation_guarded_apply(root, args.slug, args.task, args.patch_file, args.owner, args.profile)
        if args.implementation_command == "noncompliance":
            return implementation_noncompliance(root, args.slug, args.task, args.reason, args.file, args.profile)
        if args.implementation_command == "status":
            return implementation_status(root, args.slug)

    if args.command == "current":
        if args.current_command == "status":
            return current_status(root)
        if args.current_command == "set":
            print(current_set(root, args.slug))
            return 0
        if args.current_command == "clear":
            print(current_clear(root))
            return 0
        if args.current_command == "archive":
            print(current_archive(root, args.reason))
            return 0
        if args.current_command == "pause":
            print(current_pause(root, args.reason))
            return 0
        if args.current_command == "resume":
            print(current_resume(root, args.reason, args.slug))
            return 0

    if args.command == "link":
        print(link_milestone(root, args.slug, args.milestone, _parse_ids(args.covers), args.replace))
        return 0

    if args.command == "rebuild-progress":
        print(rebuild_markdown(root, args.slug))
        return 0

    if args.command == "block":
        print(block_bundle(root, args.slug, args.reason, args.need))
        return 0

    if args.command == "unblock":
        print(unblock_bundle(root, args.slug, args.note))
        return 0

    if args.command == "update":
        content = read_content_arg(args.content, args.content_file)
        path = update_section(root, args.slug, args.file, content, args.append)
        print(path)
        return 0

    if args.command == "finalize":
        target = finalize_bundle(
            root, args.slug, args.summary, args.verification, args.risks,
            args.acceptance, args.gate_status, args.decision,
            args.acceptance_notes, args.deferred, args.force,
        )
        print(target)
        return 0

    if args.command == "status":
        return print_status(root, args.slug, args.full)

    if args.command == "render-status":
        return render_status_response(root, args.slug, args.status, args.profile, args.role, args.source)

    if args.command == "ledger":
        return print_ledger(root, args.slug)

    if args.command == "verify":
        return verify_bundle(root, args.slug)

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
