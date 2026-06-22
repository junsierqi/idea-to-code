#!/usr/bin/env python3
"""Regression tests for idea_to_code_bundle.py governance controls."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("idea_to_code_bundle.py")
SKILL_DIR = SCRIPT.parent.parent
REPO_ROOT = SKILL_DIR.parent.parent
README_MD = REPO_ROOT / "README.md"
INSTALL_SKILL = REPO_ROOT / "scripts" / "install_skill.py"
REFERENCES_DIR = SKILL_DIR / "references"
SKILL_MD = SKILL_DIR / "SKILL.md"
ALLOWED_REFERENCES = {
    "planning-patterns.md",
    "roles-and-state.md",
    "verification-and-evidence.md",
    "workflow.md",
}


class BundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_bundle(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check and result.returncode != 0:
            self.fail(f"command failed: {args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def init_bundle(self) -> str:
        self.run_bundle("init", "--root", str(self.root), "--slug", "sample", "--title", "Sample task", "--unique", "--idea", "Deliver sample behavior")
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        return current["slug"]

    def test_reference_directory_contains_only_routed_files(self) -> None:
        actual = {path.name for path in REFERENCES_DIR.glob("*.md")}
        self.assertEqual(actual, ALLOWED_REFERENCES)

    def test_skill_reference_links_exist(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        refs = set(re.findall(r"references/([A-Za-z0-9_.-]+\.md)", text))
        self.assertTrue(refs)
        self.assertLessEqual(refs, ALLOWED_REFERENCES)
        for ref in refs:
            self.assertTrue((REFERENCES_DIR / ref).exists(), ref)

    def test_skill_text_does_not_embed_third_party_project_names(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL_MD, *sorted(REFERENCES_DIR.glob("*.md"))]
        )
        forbidden_patterns = [
            r"\bMaskPilot\b",
            r"\bmaskpilot\b",
            r"\bMP-\d+\b",
            r"\bComposio\b",
            r"\bawesome-codex-skills\b",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, combined), pattern)

    def test_readme_documents_current_bundle_script(self) -> None:
        if not README_MD.exists():
            self.skipTest("repository README.md is not present in this installed skill context")
        text = README_MD.read_text(encoding="utf-8")
        expected_path = "skills/idea-to-code/scripts/idea_to_code_bundle.py"
        self.assertIn(expected_path, text)
        self.assertIn(f"python {expected_path} --help", text)
        self.assertNotIn("manage_delivery_bundle.py", text)

    def test_readme_documents_one_command_install_update(self) -> None:
        if not README_MD.exists():
            self.skipTest("repository README.md is not present in this installed skill context")
        text = README_MD.read_text(encoding="utf-8")
        self.assertIn("python scripts/install_skill.py", text)
        self.assertIn("installs or updates", text)
        self.assertIn("$HOME/.codex/skills/idea-to-code", text)

    def test_install_skill_updates_existing_target_and_skips_generated_files(self) -> None:
        if not INSTALL_SKILL.exists():
            self.skipTest("repository install script is not present in this installed skill context")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "idea-to-code"
            target = root / "target" / "idea-to-code"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            (source / "scripts").mkdir()
            (source / "scripts" / "idea_to_code_bundle.py").write_text("print('ok')\n", encoding="utf-8")
            (source / "scripts" / "__pycache__").mkdir()
            (source / "scripts" / "__pycache__" / "skip.pyc").write_bytes(b"cache")
            target.mkdir(parents=True)
            (target / "stale.txt").write_text("remove me\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALL_SKILL),
                    "--source",
                    str(source),
                    "--target",
                    str(target),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / "SKILL.md").exists())
            self.assertTrue((target / "scripts" / "idea_to_code_bundle.py").exists())
            self.assertFalse((target / "stale.txt").exists())
            self.assertFalse((target / "scripts" / "__pycache__").exists())

    def test_install_skill_dry_run_does_not_create_target(self) -> None:
        if not INSTALL_SKILL.exists():
            self.skipTest("repository install script is not present in this installed skill context")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "idea-to-code"
            target = root / "target" / "idea-to-code"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALL_SKILL),
                    "--source",
                    str(source),
                    "--target",
                    str(target),
                    "--dry-run",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mode: dry-run", result.stdout)
            self.assertFalse(target.exists())

    def test_skill_description_is_concise_and_capability_focused(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        self.assertIsNotNone(match)
        description = match.group(1)
        self.assertLess(len(description), 520)
        self.assertIn("verified software changes", description)
        self.assertIn("intake confirmation", description)
        self.assertIn("structured closeout", description)
        for overly_specific in [
            "current.json pointer",
            "02-report.md",
            "state.json",
            "READY implementation plan",
        ]:
            self.assertNotIn(overly_specific, description)

    def test_test_runner_rejects_zero_test_selection(self) -> None:
        result = subprocess.run(
            [sys.executable, __file__, "-k", "definitely_no_idea_to_code_tests_match"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ran 0 tests", result.stderr)

    def test_skill_entry_contract_orients_fresh_agents(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        for required in [
            "Core Operating Contract",
            "turn an idea into a verified software change",
            "not through chat memory",
            "This skill can:",
            "Standard flow:",
            "route/current -> intake gate -> bundle",
            "Tool-owned gates are not optional",
            "does not narrow ordinary coding capability",
        ]:
            self.assertIn(required, text)
        for outdated in [
            "Core Contract For Fresh Agents",
            "console handoff",
            "delivery engine",
        ]:
            self.assertNotIn(outdated, text)

    def test_generated_test_ownership_rules_are_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, verification_text])

        for required in [
            "Test Ownership",
            "persistent-product-test",
            "project-native-test",
            "task-evidence-only",
            "tests/idea_to_code/<slug>/",
            "test_idea_to_code_<slug>",
            ".idea-to-code/<slug>/artifacts/",
            "Validation Type",
        ]:
            self.assertIn(required, combined)

    def test_zero_test_runs_are_not_validation_evidence(self) -> None:
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        self.assertIn("Ran 0 tests", verification_text)
        self.assertIn("not validation evidence", verification_text)
        self.assertIn("fix the command/test runner", verification_text)

    def test_console_handoff_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "Console Handoff Contract",
            "[idea-to-code] Status: Completed | Progress | Blocked",
            "Changes",
            "Completed Items",
            "Incomplete Items",
            "Validation Results",
            "Unverified Items",
            "Residual Risks",
            "Key Technical Details",
            "Use `Completed` only",
            "write `none`",
        ]:
            self.assertIn(required, combined)

    def test_intake_confirmation_gate_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        planning_text = (REFERENCES_DIR / "planning-patterns.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, planning_text, verification_text])

        for required in [
            "Intake Gate",
            "Understanding",
            "Assumptions",
            "Acceptance Criteria",
            "Need Confirmation",
            "Confirmation Reason",
            "Need Confirmation: yes",
            "Need Confirmation: no",
            "intake gate is resolved",
            "clarification",
            "switch",
            "new-task",
            "archive",
        ]:
            self.assertIn(required, combined)

    def test_confirmation_handoff_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "Confirmation Required",
            "explicit decision request",
            "paused before implementation",
            "Proposed scope after approval",
            "Please reply with one of:",
            '"yes" or "approved"',
            '"change: <correction>"',
            '"pause"',
            '"cancel"',
            "what happens next",
            "If the user cannot tell how to answer",
        ]:
            self.assertIn(required, combined)

    def test_user_intent_acceptance_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, verification_text])

        for required in [
            "user-intent acceptance",
            "restated user goal",
            "observable user outcome",
            "acceptance examples",
            "counterexamples",
            "wrong-but-working",
            "non-goal boundaries",
            "technically working but solves a different problem",
            "Command success is not enough for acceptance",
            "result fits the user's intended outcome",
        ]:
            self.assertIn(required, combined)

    def test_role_execution_mode_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, verification_text])

        for required in [
            "Role Execution Mode",
            "same-agent",
            "hybrid-team",
            "independent-team",
            "Check visible tool availability",
            "independent Validator or Reviewer",
            "same-agent review",
            "fallback reason",
            "Do not fabricate independent work",
            "Do not claim an independent agent ran unless",
            "implementation-confirmation bias",
        ]:
            self.assertIn(required, combined)

    def test_subagent_delegation_health_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, verification_text])

        for required in [
            "bounded delegation health check",
            "recent successful subagent result",
            "one role, one question, one file set",
            "clear output shape",
            "If a subagent times out",
            "split the task smaller",
            "closed-without-result subagent is a risk record",
            "not validation or review evidence",
        ]:
            self.assertIn(required, combined)

    def test_delegation_failure_root_cause_must_not_be_guessed(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, verification_text])

        for required in [
            "Do not guess delegation failure causes",
            "classify the cause only from observed data",
            "bounded comparison tests",
            "ping, scoped file review",
            "broader review",
            "root cause `unverified`",
            "Do not turn fallback into root-cause proof",
            "The broad timeout cause remains `unverified`",
            "Record unknown causes explicitly",
        ]:
            self.assertIn(required, combined)

    def test_fact_hypothesis_decision_verification_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "Fact / Hypothesis / Decision / Verification",
            "`Fact`: observed evidence only",
            "`Hypothesis`: possible explanation",
            "Hypotheses are allowed",
            "`Decision`: the next action",
            "`Verification`: evidence that proves",
            "cannot use an unverified Hypothesis as if it were a Fact",
            "do not present a hypothesis as a conclusion",
            "Unverified Items",
            "Residual Risks",
        ]:
            self.assertIn(required, combined)

    def test_init_creates_exact_standard_bundle_artifacts(self) -> None:
        slug = self.init_bundle()
        files = sorted(path.name for path in (self.root / ".idea-to-code" / slug).iterdir() if path.is_file())
        self.assertEqual(
            files,
            [
                "00-idea.md",
                "01-progress.md",
                "02-report.md",
                "state.json",
            ],
        )

    def test_contract_reports_standard_artifacts_states_and_roles(self) -> None:
        result = self.run_bundle("contract")
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["standard_bundle_files"],
            [
                "00-idea.md",
                "01-progress.md",
                "02-report.md",
                "state.json",
            ],
        )
        self.assertEqual(payload["bundle_states"], ["in_progress", "blocked", "paused", "completed", "closed"])
        self.assertEqual(payload["role_order"], ["planner", "implementer", "validator", "reviewer", "closer"])
        self.assertIn("01-progress.md", payload["artifact_responsibilities"])
        self.assertIn("Intake Gate", payload["artifact_responsibilities"]["00-idea.md"])
        self.assertEqual(payload["role_artifact_map"]["planner"]["primary"], ["00-idea.md"])
        self.assertIn("01-progress.md", payload["role_artifact_map"]["validator"]["evidence"])
        self.assertEqual(payload["local_record_kinds"]["A"], "acceptance")
        self.assertEqual(payload["local_record_kinds"]["V"], "validation")

    def write_ready_bundle(
        self,
        slug: str,
        weak_matrix: bool = False,
        matrix_value: str | None = None,
        need_confirmation: str = "no",
        include_intake: bool = True,
        mark_ready: bool = True,
    ) -> None:
        validation_type = "source-only"
        expected_path = "command exits zero"
        negative = "invalid command reports a failure"
        boundary = "empty input is explicitly outside scope"
        state = "state.json records role evidence"
        rollback = "no rollback state is created"
        error = "stderr reports command failures"
        observability = "verify prints JSON output"
        product_path = "temporary script path only"
        if weak_matrix:
            negative = "none"
        if matrix_value is not None:
            expected_path = matrix_value
            negative = matrix_value
            boundary = matrix_value
            state = matrix_value
            rollback = matrix_value
            error = matrix_value
            observability = matrix_value
            product_path = matrix_value

        intake = ""
        if include_intake:
            intake = f"""
## Intake Gate

- Understanding: Sample behavior should be validated in a temporary bundle.
- Assumptions: The request is clear and confirmation setting is {need_confirmation}.
- Acceptance Criteria: REQ-1 is represented in the acceptance matrix and verified.
- Need Confirmation: {need_confirmation}
- Confirmation Reason: Test fixture records whether implementation may proceed.
"""

        requirements = f"""# Requirements

- Target outcome: Sample behavior is delivered.
- Primary user: Maintainer.
- Main flow: Run the sample command.
- Success criteria: REQ-1 is verified.
- Non-goals: Production code.
- Constraints: Temporary test only.
- Unknowns: no open unknowns.
{intake}

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Behavior-changing tracked test flow.

## Acceptance Matrix

| ID | Expected Path | Negative/Invalid Inputs | Boundary Cases | State/Persistence | Rollback/Cancellation | Error Reporting | Observability | Real Product Path | Validation Type |
|----|---------------|-------------------------|----------------|-------------------|-----------------------|-----------------|---------------|-------------------|-----------------|
| REQ-1 | {expected_path} | {negative} | {boundary} | {state} | {rollback} | {error} | {observability} | {product_path} | {validation_type} |
"""
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Verify sample bundle flow

Status: pending

Files:
- state.json

Execution Details:
- Record one requirement and all role evidence.

Done Criteria:
- finalize and verify succeed.

Planned Verification:
- source-only python idea_to_code_bundle.py verify exits zero.
"""
        verification = """# Verification

Validation types: real-product-path, mock-only, fixture-only, source-only, dom-only, manual-inspection, unverified.

## Coverage Expectations

- Build: python py_compile passed.
- Unit/Integration: source-only bundle command flow.
- End-to-end flow: init to finalize.
- Remaining gaps: no remaining gaps.

## Verification History

- REQ-1: source-only validation with idea_to_code_bundle.py command flow.
"""
        req_path = self.root / "requirements.md"
        impl_path = self.root / "implementation.md"
        ver_path = self.root / "verification.md"
        req_path.write_text(requirements, encoding="utf-8")
        impl_path.write_text(implementation, encoding="utf-8")
        ver_path.write_text(verification, encoding="utf-8")

        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "requirements", "--content-file", str(req_path))
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "verification", "--content-file", str(ver_path))
        self.run_bundle("requirement", "add", "--root", str(self.root), "--slug", slug, "--id", "REQ-1", "--description", "Sample behavior is verified", "--type", "functional")
        if mark_ready:
            self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

    def write_inline_ready_bundle(self, slug: str) -> None:
        self.write_ready_bundle(slug)
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Verify sample bundle flow

Status: pending

Files: state.json
Execution Details: Record one requirement and all role evidence.
Done Criteria: finalize and verify succeed.
Planned Verification: source-only python idea_to_code_bundle.py verify exits zero.
"""
        impl_path = self.root / "implementation-inline.md"
        impl_path.write_text(implementation, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

    def write_no_requirement_ready_bundle(self, slug: str) -> None:
        requirements = """# Requirements

- Target outcome: Sample behavior is delivered.
- Primary user: Maintainer.
- Main flow: Run the sample command.
- Success criteria: tracked behavior is verified.
- Non-goals: Production code.
- Constraints: Temporary test only.
- Unknowns: no open unknowns.

## Intake Gate

- Understanding: Sample behavior should be validated without registered requirements.
- Assumptions: The fixture intentionally omits requirements for negative testing.
- Acceptance Criteria: The bundle records classification and an empty matrix for rejection.
- Need Confirmation: no
- Confirmation Reason: Test fixture has explicit scope and no risky ambiguity.

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Behavior-changing tracked test flow.

## Acceptance Matrix

| ID | Expected Path | Negative/Invalid Inputs | Boundary Cases | State/Persistence | Rollback/Cancellation | Error Reporting | Observability | Real Product Path | Validation Type |
|----|---------------|-------------------------|----------------|-------------------|-----------------------|-----------------|---------------|-------------------|-----------------|
"""
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Verify sample bundle flow

Status: pending

Files:
- state.json

Execution Details:
- Record no requirement coverage.

Done Criteria:
- verify refuses missing requirements.

Planned Verification:
- source-only python idea_to_code_bundle.py verify exits non-zero.
"""
        req_path = self.root / "requirements-no-req.md"
        impl_path = self.root / "implementation-no-req.md"
        req_path.write_text(requirements, encoding="utf-8")
        impl_path.write_text(implementation, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "requirements", "--content-file", str(req_path))
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

    def record_roles_through_reviewer(self, slug: str) -> None:
        role_evidence = {
            "planner": "REQ-1 planned in 00-idea.md with TASK-1 in 00-idea.md",
            "implementer": "TASK-1 implemented through state.json bundle records for REQ-1",
            "validator": "REQ-1 source-only validation with python idea_to_code_bundle.py verify recorded in 01-progress.md",
            "reviewer": "REQ-1 review checked 00-idea.md, 00-idea.md, and 01-progress.md coverage",
        }
        for role, evidence in role_evidence.items():
            self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", role, "--evidence", evidence, "--covers", "REQ-1")

    def record_closer(self, slug: str) -> None:
        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "closer",
            "--evidence", "REQ-1 covered by Sample milestone; pre-close source-only verify passed; final decision pass accepted",
            "--covers", "REQ-1",
        )

    def checkpoint(self, slug: str) -> None:
        self.run_bundle(
            "checkpoint",
            "--root", str(self.root),
            "--slug", slug,
            "--milestone", "Sample milestone",
            "--delivered", "REQ-1 bundle records created",
            "--verified", "source-only command flow evidence in 01-progress.md",
            "--next", "finalize",
            "--focus", "closing",
            "--gate", "acceptance",
            "--gate-status", "pass",
            "--covers", "REQ-1",
        )

    def test_full_governance_flow_verifies(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        preclose = self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ok": true', preclose.stdout)
        self.record_closer(slug)
        self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation complete", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted")
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ok": true', verify.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["closeout_status"]["completed"])
        self.assertTrue(status["closeout_status"]["final_verify_ok"])
        self.assertEqual(status["closeout_status"]["closed_by"], "closer")
        ledger = (self.root / ".idea-to-code" / slug / "01-progress.md").read_text(encoding="utf-8")
        for event in (
            "init",
            "requirement-add",
            "implementation-ready",
            "role-planner",
            "role-implementer",
            "role-validator",
            "role-reviewer",
            "checkpoint",
            "verify",
            "role-closer",
            "finalize-start",
            "finalize-complete",
        ):
            self.assertIn(f" - {event}", ledger)
        self.assertNotIn(" - update", ledger)

    def test_finalize_rejects_missing_role_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.checkpoint(slug)
        result = self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation complete", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("role evidence missing", result.stderr)

    def test_force_cannot_override_accepted_missing_role_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.checkpoint(slug)
        result = self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation complete", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted", "--force", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--force cannot override accepted closeout integrity failures", result.stderr)

    def test_role_record_rejects_vague_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "reviewer", "--evidence", "reviewed", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("role evidence is too vague", result.stderr)

    def test_verify_rejects_weak_acceptance_matrix(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, weak_matrix=True)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("weak column", verify.stdout)

    def test_finalize_requires_preclose_verify(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        result = self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation complete", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pre-close verify has not passed", result.stderr)

    def test_closer_requires_preclose_verify(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "closer",
            "--evidence", "REQ-1 covered by Sample milestone; pre-close verify passed; final decision pass",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("closer evidence refused", result.stderr)

    def test_closer_requires_verify_after_latest_reviewer(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        time.sleep(1.1)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "reviewer", "--evidence", "REQ-1 review checked residual risk and coverage in 01-progress.md after prior verify", "--covers", "REQ-1")
        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "closer",
            "--evidence", "REQ-1 covered by Sample milestone; pre-close source-only verify passed; final decision pass accepted",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pre-close verify is older than the latest Reviewer evidence", result.stderr)

    def test_role_order_is_enforced(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "validator", "--evidence", "REQ-1 source-only validation with python verify command", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("role evidence order violation", result.stderr)

    def test_planner_requires_planning_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 source-only python validation passed in 01-progress.md", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Planner evidence must reference the implementation plan", result.stderr)

    def test_planner_rejects_wrong_role_keyword_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "Validator performed REQ-1 coverage using acceptance matrix in 00-idea.md and TASK-1 in 00-idea.md", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Planner evidence must describe planning work", result.stderr)

    def test_implementer_requires_implementation_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", "REQ-1 review checked scope and risk in 01-progress.md", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Implementer evidence must name implemented TASK/IMP IDs", result.stderr)

    def test_validator_requires_validation_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", "TASK-1 implemented by updating state.json behavior in 00-idea.md", "--covers", "REQ-1")
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "validator", "--evidence", "REQ-1 reviewed in 01-progress.md with coverage notes", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Validator evidence must name a validation type", result.stderr)

    def test_reviewer_requires_review_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", "TASK-1 implemented by updating state.json behavior in 00-idea.md", "--covers", "REQ-1")
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "validator", "--evidence", "REQ-1 source-only validation ran python idea_to_code_bundle.py verify command", "--covers", "REQ-1")
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "reviewer", "--evidence", "REQ-1 source-only python validation ran in 01-progress.md", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Reviewer evidence must describe scope", result.stderr)

    def test_progress_role_gates_summary_updates_with_latest_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        progress = (self.root / ".idea-to-code" / slug / "01-progress.md").read_text(encoding="utf-8")
        role_block = progress.split("## Role Gates", 1)[1].split("## Milestone History", 1)[0]
        self.assertIn("| Planner | REQ-1 planned", role_block)
        self.assertIn("| Validator | REQ-1 source-only validation", role_block)
        self.assertNotIn("- Planner:", role_block)
        self.assertNotIn("- Validator:", role_block)

    def test_closer_requires_closeout_evidence_content(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "closer", "--evidence", "REQ-1 source-only python validation ran in 01-progress.md", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Closer evidence must state pre-close verify passed", result.stderr)

    def test_inline_implementation_sections_are_accepted(self) -> None:
        slug = self.init_bundle()
        self.write_inline_ready_bundle(slug)
        status = self.run_bundle("implementation", "status", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ready": true', status.stdout)

    def test_implementation_ready_rejects_placeholder_fields(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Placeholder task

Files: x
Execution Details: x
Done Criteria: x
Planned Verification: x
"""
        impl_path = self.root / "implementation-placeholder.md"
        impl_path.write_text(implementation, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty Files", result.stderr)

    def test_implementation_ready_rejects_missing_intake_gate(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, include_intake=False, mark_ready=False)
        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing Intake Gate section", result.stderr)

    def test_implementation_ready_rejects_unresolved_confirmation(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="yes", mark_ready=False)
        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Need Confirmation is yes", result.stderr)

    def test_implementation_ready_accepts_intake_without_confirmation_needed(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["implementation_ready"])

    def test_content_file_utf8_bom_does_not_hide_gate_status(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        implementation = """Gate Status: READY

### TASK-1: Verify sample bundle flow

Status: pending

Files:
- state.json

Execution Details:
- Record one requirement and all role evidence.

Done Criteria:
- finalize and verify succeed.

Planned Verification:
- source-only python idea_to_code_bundle.py verify exits zero.
"""
        impl_path = self.root / "implementation-bom.md"
        impl_path.write_bytes(("\ufeff" + implementation).encode("utf-8"))
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["implementation_ready"])

    def test_imp_implementation_sections_are_accepted(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        implementation = """# Implementation

Gate Status: READY

## IMP-1: Verify sample bundle flow

Status: pending

Files: state.json
Execution Details: Record one requirement and all role evidence.
Done Criteria: finalize and verify succeed.
Planned Verification: source-only python idea_to_code_bundle.py verify exits zero.
"""
        impl_path = self.root / "implementation-imp.md"
        impl_path.write_text(implementation, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        status = self.run_bundle("implementation", "status", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ready": true', status.stdout)

    def test_verify_rejects_non_ascii_bundle_docs(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        idea_path = self.root / "idea.txt"
        idea_path.write_text("Non ASCII marker: cafe\u00e9", encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "idea", "--content-file", str(idea_path))
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("English-only", verify.stdout)

    def test_plan_revision_stales_role_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        preclose = self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ok": true', preclose.stdout)
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Verify revised bundle flow

Status: pending

Files:
- state.json

Execution Details:
- Record revised plan evidence for REQ-1.

Done Criteria:
- revised gate and verify succeed.

Planned Verification:
- source-only python idea_to_code_bundle.py verify exits zero.
"""
        impl_path = self.root / "implementation-revised.md"
        impl_path.write_text(implementation, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("role evidence missing for current plan revision", verify.stdout)

    def test_parallel_requirement_adds_do_not_lose_updates(self) -> None:
        slug = self.init_bundle()
        commands = []
        for rid in ("REQ-1", "REQ-2"):
            commands.append([
                sys.executable,
                str(SCRIPT),
                "requirement",
                "add",
                "--root",
                str(self.root),
                "--slug",
                slug,
                "--id",
                rid,
                "--description",
                f"{rid} behavior is tracked",
                "--type",
                "functional",
            ])
        procs = [
            subprocess.Popen(cmd, cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for cmd in commands
        ]
        outputs = [proc.communicate(timeout=10) for proc in procs]
        for proc, (stdout, stderr) in zip(procs, outputs):
            self.assertEqual(proc.returncode, 0, f"stdout:\n{stdout}\nstderr:\n{stderr}")
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        ids = {req["id"] for req in status["requirements"]}
        self.assertEqual(ids, {"REQ-1", "REQ-2"})

    def test_requirement_remove_allowed_only_before_execution_starts(self) -> None:
        slug = self.init_bundle()
        self.run_bundle("requirement", "add", "--root", str(self.root), "--slug", slug, "--id", "REQ-1", "--description", "REQ-1 behavior is tracked", "--type", "functional")
        self.run_bundle("requirement", "remove", "--root", str(self.root), "--slug", slug, "--id", "REQ-1")
        self.write_ready_bundle(slug)
        result = self.run_bundle("requirement", "remove", "--root", str(self.root), "--slug", slug, "--id", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement remove is allowed only before execution starts", result.stderr)

    def test_verify_rejects_zero_recorded_requirements(self) -> None:
        slug = self.init_bundle()
        self.write_no_requirement_ready_bundle(slug)
        self.run_bundle(
            "checkpoint",
            "--root", str(self.root),
            "--slug", slug,
            "--milestone", "No requirement milestone",
            "--delivered", "no requirement coverage",
            "--verified", "source-only command flow evidence",
            "--next", "finalize",
            "--focus", "closing",
            "--gate", "acceptance",
            "--gate-status", "pass",
        )
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("no open requirements recorded", verify.stdout)

    def test_requirement_close_command_is_not_available(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("requirement", "close", "--root", str(self.root), "--slug", slug, "--id", "REQ-1", "--note", "User dropped this requirement from scope.", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_user_input_plan_change_requires_plan_update_before_verify(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User expanded scope to include another acceptance path",
            "--classification", "expand",
            "--rationale", "The new request changes acceptance scope for REQ-1",
            "--action", "Update requirements and implementation before more code edits",
            "--changes-plan", "yes",
        )
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("user input changed the plan", verify.stdout)

    def test_user_input_status_cannot_be_marked_plan_changing(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User asked for current progress status",
            "--classification", "status",
            "--rationale", "The user requested read-only progress information",
            "--action", "Inspect current bundle without editing product files",
            "--changes-plan", "yes",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status user input must not use --changes-plan yes", result.stderr)

    def test_user_input_new_task_cannot_be_marked_plan_changing(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User introduced an unrelated new delivery task",
            "--classification", "new-task",
            "--rationale", "The request belongs in a separate delivery bundle",
            "--action", "Park current bundle before initializing the new task",
            "--changes-plan", "yes",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("new-task user input must not use --changes-plan yes", result.stderr)

    def test_user_input_new_task_does_not_mark_pending_plan_update(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User introduced an unrelated new delivery task",
            "--classification", "new-task",
            "--rationale", "The request belongs in a separate delivery bundle",
            "--action", "Archive current bundle before initializing the new task",
            "--changes-plan", "no",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status["pending_plan_update"])
        self.assertEqual(status["last_user_input_decision"]["classification"], "new-task")

    def test_plan_changing_user_input_clears_after_plan_update(self) -> None:
        slug = self.init_bundle()
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User clarified the intended command behavior",
            "--classification", "clarification",
            "--rationale", "The clarification changes implementation acceptance details",
            "--action", "Revise requirements before marking implementation ready",
            "--changes-plan", "yes",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["pending_plan_update"])
        self.write_ready_bundle(slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status["pending_plan_update"])

    def test_user_input_non_ascii_fails_without_traceback(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "Cafe\u00e9 scope was mentioned",
            "--classification", "continue",
            "--rationale", "The input does not change acceptance scope",
            "--action", "Continue the current implementation plan",
            "--changes-plan", "no",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("English-only ASCII", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_mutating_commands_reject_non_current_bundle(self) -> None:
        active = self.init_bundle()
        self.run_bundle("init", "--root", str(self.root), "--slug", "other", "--title", "Other task", "--idea", "Other behavior", "--no-current")
        other = "other"
        content_path = self.root / "other-requirements.md"
        content_path.write_text("# Requirements\n", encoding="utf-8")
        for command in (
            ("update", "--root", str(self.root), "--slug", other, "--file", "requirements", "--content-file", str(content_path)),
            ("checkpoint", "--root", str(self.root), "--slug", other, "--milestone", "Other milestone", "--delivered", "changed files", "--verified", "source-only inspection", "--next", "continue", "--focus", "other", "--gate", "verify", "--gate-status", "pass"),
            ("role", "record", "--root", str(self.root), "--slug", other, "--role", "planner", "--evidence", "REQ-1 planned with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1"),
            ("finalize", "--root", str(self.root), "--slug", other, "--summary", "Other summary", "--verification", "source-only verify passed", "--risks", "none", "--acceptance", "REQ-1 accepted", "--gate-status", "pass", "--decision", "accepted"),
        ):
            result = self.run_bundle(*command, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing to mutate non-current bundle", result.stderr)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], active)

    def test_init_refuses_to_replace_unfinished_current_bundle(self) -> None:
        active = self.init_bundle()
        result = self.run_bundle(
            "init",
            "--root", str(self.root),
            "--slug", "other",
            "--title", "Other task",
            "--idea", "Other behavior",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("init refused because active bundle", result.stderr)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], active)

    def test_new_task_after_archiving_current_can_start_cleanly(self) -> None:
        active = self.init_bundle()
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", active,
            "--summary", "User introduced an unrelated new delivery task",
            "--classification", "new-task",
            "--rationale", "The request belongs in a separate delivery bundle",
            "--action", "Archive current bundle before initializing the new task",
            "--changes-plan", "no",
        )
        self.run_bundle("current", "archive", "--root", str(self.root), "--reason", "parked for unrelated new task")
        self.run_bundle("init", "--root", str(self.root), "--slug", "other", "--title", "Other task", "--idea", "Other behavior")
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], "other")
        self.run_bundle("current", "archive", "--root", str(self.root), "--reason", "parked second task before resuming first task")
        self.run_bundle("current", "set", "--root", str(self.root), "--slug", active)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], active)

    def test_current_set_rejects_switching_away_from_unfinished_current(self) -> None:
        active = self.init_bundle()
        self.run_bundle("init", "--root", str(self.root), "--slug", "other", "--title", "Other task", "--idea", "Other behavior", "--no-current")
        result = self.run_bundle("current", "set", "--root", str(self.root), "--slug", "other", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot switch current from unfinished bundle", result.stderr)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], active)

    def test_current_clear_rejects_unfinished_current(self) -> None:
        active = self.init_bundle()
        result = self.run_bundle("current", "clear", "--root", str(self.root), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("current clear refused", result.stderr)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], active)

    def test_duplicate_task_description_routes_to_existing_current_bundle(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle(
            "init",
            "--root", str(self.root),
            "--slug", "same-task-different-words",
            "--title", "Same task different words",
            "--idea", "Deliver sample behavior with alternate phrasing",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("active bundle", result.stderr)
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User restated the same sample behavior task differently",
            "--classification", "continue",
            "--rationale", "The restatement matches the active bundle outcome",
            "--action", "Continue using the existing active bundle",
            "--changes-plan", "no",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status["pending_plan_update"])
        self.assertEqual(status["last_user_input_decision"]["classification"], "continue")

    def test_paused_bundle_blocks_mutation_until_resume(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("current", "pause", "--root", str(self.root), "--reason", "User asked to pause work")
        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned with acceptance matrix and TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Bundle is paused", result.stderr)
        self.run_bundle("current", "resume", "--root", str(self.root), "--reason", "User resumed delivery")
        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned with acceptance matrix and TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
        )

    def test_verify_non_current_bundle_is_read_only(self) -> None:
        self.init_bundle()
        self.run_bundle("init", "--root", str(self.root), "--slug", "other", "--title", "Other task", "--idea", "Other behavior", "--no-current")
        other_status_path = self.root / ".idea-to-code" / "other" / "state.json"
        before = json.loads(other_status_path.read_text(encoding="utf-8"))
        self.run_bundle("verify", "--root", str(self.root), "--slug", "other", check=False)
        after = json.loads(other_status_path.read_text(encoding="utf-8"))
        self.assertEqual(before.get("last_verified_at_utc"), after.get("last_verified_at_utc"))
        self.assertEqual(before.get("last_verify_ok"), after.get("last_verify_ok"))

    def test_verify_paused_bundle_is_read_only(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        status_path = self.root / ".idea-to-code" / slug / "state.json"
        self.run_bundle("current", "pause", "--root", str(self.root), "--reason", "User asked to pause work")
        before = json.loads(status_path.read_text(encoding="utf-8"))
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        after = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(before.get("last_verified_at_utc"), after.get("last_verified_at_utc"))
        self.assertEqual(before.get("last_verify_ok"), after.get("last_verify_ok"))
        self.assertEqual(after["state"], "paused")

    def test_current_set_rejects_completed_bundle(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.record_closer(slug)
        self.run_bundle(
            "finalize",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "Sample implementation complete",
            "--verification", "source-only command flow passed",
            "--risks", "none",
            "--acceptance", "REQ-1 delivered",
            "--gate-status", "pass",
            "--decision", "accepted",
        )
        result = self.run_bundle("current", "set", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot set completed bundle as current", result.stderr)

    def test_verify_rejects_one_character_acceptance_matrix_cells(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, matrix_value="x")
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("weak column", verify.stdout)

    def test_verify_rejects_repeated_character_acceptance_matrix_cells(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, matrix_value="aaaaaaaa")
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("weak column", verify.stdout)

    def test_requirement_add_rejects_non_ascii_description(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle("requirement", "add", "--root", str(self.root), "--slug", slug, "--id", "REQ-1", "--description", "Cafe\u00e9 capability", "--type", "functional", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("English-only ASCII", result.stderr)

    def test_finalize_rejects_non_ascii_arguments(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.record_closer(slug)
        result = self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation cafe\u00e9", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("English-only ASCII", result.stderr)

    def test_finalize_rejects_verification_without_validation_type(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.record_closer(slug)
        result = self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation complete", "--verification", "all tests passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--verification must name a validation type", result.stderr)

    def test_route_without_current_recommends_new_bundle(self) -> None:
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Build the sample behavior")
        payload = json.loads(result.stdout)
        self.assertIsNone(payload["active_bundle"])
        self.assertEqual(payload["recommended_classification"], "new-task")
        self.assertEqual(payload["route_gate"], "init-required")
        self.assertFalse(payload["changes_plan"])
        self.assertTrue(any(command.startswith("init ") for command in payload["required_next_commands"]))
        self.assertIn("Initialize a new current bundle", payload["next_action"])
        self.assertIn("recommended_need_confirmation", payload)

    def test_route_vague_new_idea_recommends_confirmation(self) -> None:
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Build a dashboard app")
        payload = json.loads(result.stdout)
        self.assertIsNone(payload["active_bundle"])
        self.assertEqual(payload["recommended_classification"], "new-task")
        self.assertEqual(payload["route_gate"], "init-required")
        self.assertTrue(payload["recommended_need_confirmation"])
        self.assertIn("multi-interpretation", payload["confirmation_reason"])

    def test_route_trivial_typo_recommends_skipping_delivery_bundle(self) -> None:
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Fix a typo in README")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["recommended_classification"], "no-op")
        self.assertEqual(payload["route_gate"], "skip-delivery")
        self.assertFalse(payload["changes_plan"])
        self.assertFalse(payload["can_edit_product_files"])
        self.assertEqual(payload["required_next_commands"], [])
        self.assertIn("one-shot mechanical edit", payload["next_action"])

    def test_route_status_request_is_read_only(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle("route", "--root", str(self.root), "--input", "What is the current progress?")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["active_bundle"]["slug"], slug)
        self.assertEqual(payload["recommended_classification"], "status")
        self.assertEqual(payload["route_gate"], "read-only")
        self.assertFalse(payload["changes_plan"])
        self.assertIn("current status --root <root>", payload["required_next_commands"])
        self.assertIn("without editing product files", payload["next_action"])

    def test_route_expansion_marks_plan_changing(self) -> None:
        self.init_bundle()
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Also include an edge case for empty input")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["recommended_classification"], "expand")
        self.assertEqual(payload["route_gate"], "plan-update-required")
        self.assertTrue(payload["changes_plan"])
        self.assertTrue(any("implementation ready" in command for command in payload["required_next_commands"]))
        self.assertIn("rerun the implementation gate", payload["next_action"])

    def test_route_new_task_preserves_active_bundle(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Start a separate task for release notes")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["active_bundle"]["slug"], slug)
        self.assertEqual(payload["recommended_classification"], "new-task")
        self.assertEqual(payload["route_gate"], "archive-current-first")
        self.assertFalse(payload["changes_plan"])
        self.assertTrue(any("current archive" in command for command in payload["required_next_commands"]))
        self.assertIn("archive it with a reason", payload["next_action"])

    def test_route_paused_bundle_requires_resume_before_code(self) -> None:
        self.init_bundle()
        self.run_bundle("current", "pause", "--root", str(self.root), "--reason", "User paused work")
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["recommended_classification"], "continue")
        self.assertEqual(payload["route_gate"], "resume-required")
        self.assertTrue(payload["requires_resume"])
        self.assertFalse(payload["can_edit_product_files"])
        self.assertTrue(any("current resume" in command for command in payload["required_next_commands"]))
        self.assertIn("Run current resume", payload["next_action"])

    def test_route_pending_plan_update_blocks_product_edits(self) -> None:
        slug = self.init_bundle()
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User added another edge case",
            "--classification", "expand",
            "--rationale", "The edge case changes acceptance scope",
            "--action", "Update requirements and implementation before coding",
            "--changes-plan", "yes",
        )
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["route_gate"], "plan-update-required")
        self.assertTrue(payload["must_update_plan_before_code"])
        self.assertFalse(payload["can_edit_product_files"])
        self.assertTrue(any("update --root" in command for command in payload["required_next_commands"]))
        self.assertIn("pending plan update", payload["next_action"])

    def test_route_blocked_bundle_requires_unblock_before_code(self) -> None:
        slug = self.init_bundle()
        self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing external API key",
            "--need", "Provide API key or mock decision",
        )
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["route_gate"], "unblock-required")
        self.assertTrue(payload["requires_unblock"])
        self.assertFalse(payload["can_edit_product_files"])
        self.assertTrue(any("unblock --root" in command for command in payload["required_next_commands"]))
        self.assertIn("run unblock", payload["next_action"])

    def test_route_non_ascii_fails_without_traceback(self) -> None:
        result = self.run_bundle("route", "--root", str(self.root), "--input", "优化这个任务", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("English-only ASCII", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_dogfood_published_scenario_matrix(self) -> None:
        # Small task: route should not force idea-to-code for a one-shot mechanical edit.
        small = self.run_bundle("route", "--root", str(self.root), "--input", "Fix a typo in README")
        small_payload = json.loads(small.stdout)
        self.assertEqual(small_payload["recommended_classification"], "no-op")
        self.assertEqual(small_payload["route_gate"], "skip-delivery")

        # Medium task: complete lifecycle from requirements through finalize.
        medium = self.init_bundle()
        self.write_ready_bundle(medium)
        self.record_roles_through_reviewer(medium)
        self.checkpoint(medium)
        self.run_bundle("verify", "--root", str(self.root), "--slug", medium)
        self.record_closer(medium)
        self.run_bundle(
            "finalize",
            "--root", str(self.root),
            "--slug", medium,
            "--summary", "Medium CLI-style lifecycle complete",
            "--verification", "source-only command flow passed",
            "--risks", "none",
            "--acceptance", "REQ-1 delivered",
            "--gate-status", "pass",
            "--decision", "accepted",
        )

        # Large task: multiple milestones all bind back to the same requirement set.
        self.run_bundle("init", "--root", str(self.root), "--slug", "large", "--title", "Large task", "--unique", "--idea", "Large task")
        large = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))["slug"]
        requirements = """# Requirements

- Target outcome: Large task is delivered across multiple milestones.
- Primary user: Maintainer.
- Main flow: Run four milestone checkpoints.
- Success criteria: REQ-1, REQ-2, and REQ-3 are all covered by passing milestones.
- Non-goals: Product implementation.
- Constraints: Temporary dogfood only.
- Unknowns: no open unknowns.

## Intake Gate

- Understanding: Large task should be validated across multiple milestones.
- Assumptions: The dogfood request is explicit and does not need external confirmation.
- Acceptance Criteria: REQ-1, REQ-2, and REQ-3 stay covered by milestone evidence.
- Need Confirmation: no
- Confirmation Reason: Test fixture has explicit scope and no risky ambiguity.

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Large dogfood flow validates multi-milestone governance.

## Acceptance Matrix

| ID | Expected Path | Negative/Invalid Inputs | Boundary Cases | State/Persistence | Rollback/Cancellation | Error Reporting | Observability | Real Product Path | Validation Type |
|----|---------------|-------------------------|----------------|-------------------|-----------------------|-----------------|---------------|-------------------|-----------------|
| REQ-1 | command path covers planning | missing evidence rejected | temporary root only | state.json records planning coverage | archive preserves state | verify reports failures | verify prints JSON | temporary bundle path only | source-only |
| REQ-2 | command path covers execution | missing evidence rejected | temporary root only | state.json records execution coverage | archive preserves state | verify reports failures | verify prints JSON | temporary bundle path only | source-only |
| REQ-3 | command path covers acceptance | missing evidence rejected | temporary root only | state.json records acceptance coverage | archive preserves state | verify reports failures | verify prints JSON | temporary bundle path only | source-only |
"""
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Large planning slice

Status: pending

Files:
- state.json

Execution Details:
- Record planning coverage.

Done Criteria:
- REQ-1 is covered.

Planned Verification:
- source-only verify result.

## TASK-2: Large execution slice

Status: pending

Files:
- 01-progress.md

Execution Details:
- Record execution coverage.

Done Criteria:
- REQ-2 is covered.

Planned Verification:
- source-only verify result.

## TASK-3: Large acceptance slice

Status: pending

Files:
- 01-progress.md

Execution Details:
- Record acceptance coverage.

Done Criteria:
- REQ-3 is covered.

Planned Verification:
- source-only verify result.

## TASK-4: Large closeout slice

Status: pending

Files:
- 02-report.md

Execution Details:
- Finalize all covered requirements.

Done Criteria:
- finalize and verify succeed.

Planned Verification:
- source-only final verify result.
"""
        verification = """# Verification

Validation types: real-product-path, mock-only, fixture-only, source-only, dom-only, manual-inspection, unverified.

## Coverage Expectations

- Build: script command execution.
- Unit/Integration: source-only bundle command flow.
- End-to-end flow: multi-milestone lifecycle.
- Remaining gaps: no remaining gaps.

## Verification History

- REQ-1/REQ-2/REQ-3: source-only command flow evidence.
"""
        req_path = self.root / "large-requirements.md"
        impl_path = self.root / "large-implementation.md"
        ver_path = self.root / "large-verification.md"
        req_path.write_text(requirements, encoding="utf-8")
        impl_path.write_text(implementation, encoding="utf-8")
        ver_path.write_text(verification, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", large, "--file", "requirements", "--content-file", str(req_path))
        self.run_bundle("update", "--root", str(self.root), "--slug", large, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("update", "--root", str(self.root), "--slug", large, "--file", "verification", "--content-file", str(ver_path))
        for rid in ("REQ-1", "REQ-2", "REQ-3"):
            self.run_bundle("requirement", "add", "--root", str(self.root), "--slug", large, "--id", rid, "--description", f"{rid} large dogfood behavior is verified", "--type", "functional")
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", large)
        covers = "REQ-1,REQ-2,REQ-3"
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "planner", "--evidence", "REQ-1/REQ-2/REQ-3 planned in 00-idea.md with TASK-1..TASK-4 ready in 00-idea.md", "--covers", covers)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "implementer", "--evidence", "TASK-1..TASK-4 implemented through state.json 01-progress.md 01-progress.md and 02-report.md records", "--covers", covers)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "validator", "--evidence", "REQ-1/REQ-2/REQ-3 source-only validation ran idea_to_code_bundle.py verify command flow", "--covers", covers)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "reviewer", "--evidence", "REQ-1/REQ-2/REQ-3 review checked 00-idea.md 00-idea.md and 01-progress.md coverage", "--covers", covers)
        for index in range(1, 5):
            self.run_bundle("checkpoint", "--root", str(self.root), "--slug", large, "--milestone", f"Large milestone {index}", "--delivered", "REQ-1/REQ-2/REQ-3 evidence recorded", "--verified", "source-only command flow evidence", "--next", "continue", "--focus", f"milestone {index}", "--gate", "acceptance", "--gate-status", "pass", "--covers", covers)
        listed = self.run_bundle("requirement", "list", "--root", str(self.root), "--slug", large)
        self.assertTrue(all(row["aggregate_gate"] == "pass" for row in json.loads(listed.stdout)["requirements"]))
        self.run_bundle("verify", "--root", str(self.root), "--slug", large)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "closer", "--evidence", "REQ-1/REQ-2/REQ-3 covered by large milestones; pre-close source-only verify passed; final decision pass accepted", "--covers", covers)
        self.run_bundle("finalize", "--root", str(self.root), "--slug", large, "--summary", "Large lifecycle complete", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1/REQ-2/REQ-3 delivered", "--gate-status", "pass", "--decision", "accepted")

        # Mid-stream expansion and switch must block code until the plan is updated.
        self.run_bundle("init", "--root", str(self.root), "--slug", "change", "--title", "Change task", "--unique", "--idea", "Change task")
        change = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))["slug"]
        expanded = self.run_bundle("route", "--root", str(self.root), "--input", "Also include another boundary case")
        self.assertEqual(json.loads(expanded.stdout)["recommended_classification"], "expand")
        self.run_bundle("user-input", "record", "--root", str(self.root), "--slug", change, "--summary", "User added another boundary case", "--classification", "expand", "--rationale", "The boundary case changes acceptance scope", "--action", "Update requirements and implementation before coding", "--changes-plan", "yes")
        blocked_route = json.loads(self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation").stdout)
        self.assertTrue(blocked_route["must_update_plan_before_code"])
        self.assertFalse(blocked_route["can_edit_product_files"])
        switched = json.loads(self.run_bundle("route", "--root", str(self.root), "--input", "Actually switch to a different direction").stdout)
        self.assertEqual(switched["recommended_classification"], "switch")
        self.run_bundle("user-input", "record", "--root", str(self.root), "--slug", change, "--summary", "User switched to a different direction", "--classification", "switch", "--rationale", "The user changed the target outcome", "--action", "Update requirements design and implementation for the replacement goal", "--changes-plan", "yes")
        current_status = json.loads(self.run_bundle("current", "status", "--root", str(self.root)).stdout)
        self.assertEqual(current_status["current"]["slug"], change)
        self.assertTrue(current_status["bundle_status"]["pending_plan_update"])

        # Error closeout: uncovered requirements and missing pre-close verify must fail.
        self.run_bundle("current", "archive", "--root", str(self.root), "--reason", "park change task for negative closeout")
        self.run_bundle("init", "--root", str(self.root), "--slug", "negative", "--title", "Negative task", "--unique", "--idea", "Negative task")
        negative = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))["slug"]
        self.write_ready_bundle(negative)
        self.run_bundle("requirement", "add", "--root", str(self.root), "--slug", negative, "--id", "REQ-2", "--description", "Second requirement must be covered", "--type", "functional")
        verify_bad = self.run_bundle("verify", "--root", str(self.root), "--slug", negative, check=False)
        self.assertNotEqual(verify_bad.returncode, 0)
        self.assertIn("uncovered requirements", verify_bad.stdout)
        finalize_bad = self.run_bundle("finalize", "--root", str(self.root), "--slug", negative, "--summary", "Bad closeout", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted", check=False)
        self.assertNotEqual(finalize_bad.returncode, 0)

        # Multi-task switching: archive unfinished work, start another task, then resume the old one.
        self.run_bundle("user-input", "record", "--root", str(self.root), "--slug", negative, "--summary", "User introduced a separate task", "--classification", "new-task", "--rationale", "The task is unrelated to the active negative closeout flow", "--action", "Archive current bundle before initializing the separate task", "--changes-plan", "no")
        self.run_bundle("current", "archive", "--root", str(self.root), "--reason", "dogfood separate task")
        self.run_bundle("init", "--root", str(self.root), "--slug", "independent", "--title", "Independent task", "--unique", "--idea", "Independent task")
        independent = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))["slug"]
        self.assertNotEqual(independent, negative)
        self.run_bundle("current", "archive", "--root", str(self.root), "--reason", "park independent task")
        self.run_bundle("current", "set", "--root", str(self.root), "--slug", negative)
        resumed = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))["slug"]
        self.assertEqual(resumed, negative)

    def test_verify_rejects_ad_hoc_extra_bundle_markdown(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        extra = self.root / ".idea-to-code" / slug / "09-ledger.md"
        extra.write_text("# Ad Hoc Ledger\n", encoding="utf-8")
        result = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected bundle markdown file", result.stdout)

    def test_full_status_exposes_lifecycle_accounting(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        result = self.run_bundle("status", "--root", str(self.root), "--slug", slug, "--full")
        payload = json.loads(result.stdout)
        self.assertIn("requirements", payload)
        self.assertIn("user_input_decisions", payload)
        self.assertIn("role_evidence", payload)
        self.assertIn("planner", payload["role_evidence"])
        self.assertIn("implementation_ready", payload)
        self.assertIn("pending_plan_update", payload)
        self.assertIn("last_verify_ok", payload)
        self.assertIn("local_records", payload)

    def test_ledger_command_prints_progress_timeline_events(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        result = self.run_bundle("ledger", "--root", str(self.root), "--slug", slug)
        self.assertIn("# Progress", result.stdout)
        self.assertIn("## Timeline", result.stdout)
        self.assertIn(" - init", result.stdout)
        self.assertNotIn(" - update", result.stdout)
        self.assertIn(" - requirement-add", result.stdout)
        self.assertIn(" - implementation-ready", result.stdout)
        self.assertIn(" - role-planner", result.stdout)

    def test_rebuild_progress_regenerates_progress_file(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        progress = self.root / ".idea-to-code" / slug / "01-progress.md"
        progress.write_text("# Progress\n\nbroken\n", encoding="utf-8")
        result = self.run_bundle("rebuild-progress", "--root", str(self.root), "--slug", slug)
        self.assertIn("01-progress.md", result.stdout)
        rebuilt = progress.read_text(encoding="utf-8")
        self.assertIn("## Current Phase", rebuilt)
        self.assertIn("## Milestone History", rebuilt)

    def test_rebuild_markdown_command_is_not_available(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle("rebuild-markdown", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_update_commands_do_not_spam_human_ledger(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        ledger = self.run_bundle("ledger", "--root", str(self.root), "--slug", slug)
        self.assertIn(" - init", ledger.stdout)
        self.assertIn(" - requirement-add", ledger.stdout)
        self.assertIn(" - implementation-ready", ledger.stdout)
        self.assertNotIn(" - update", ledger.stdout)

    def test_local_record_add_list_status_and_ledger(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle(
            "record", "add",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "A1",
            "--kind", "A",
            "--text", "REQ-1 acceptance requires source-only verify coverage",
            "--covers", "REQ-1",
        )
        listed = json.loads(self.run_bundle("record", "list", "--root", str(self.root), "--slug", slug).stdout)
        self.assertEqual(listed["records"][0]["id"], "A1")
        self.assertEqual(listed["records"][0]["kind_label"], "acceptance")
        status = json.loads(self.run_bundle("status", "--root", str(self.root), "--slug", slug, "--full").stdout)
        self.assertEqual(status["local_records"][0]["id"], "A1")
        ledger = self.run_bundle("ledger", "--root", str(self.root), "--slug", slug)
        self.assertIn(" - record-A", ledger.stdout)
        self.assertIn("A1: REQ-1 acceptance requires source-only verify coverage", ledger.stdout)

    def test_local_record_rejects_unknown_kind(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle(
            "record", "add",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "X1",
            "--kind", "X",
            "--text", "REQ-1 unknown record kind should fail",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_local_record_rejects_unknown_covers(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle(
            "record", "add",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "A2",
            "--kind", "A",
            "--text", "REQ-2 acceptance should fail because requirement is unknown",
            "--covers", "REQ-2",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown requirement IDs", result.stderr)

    def test_doctor_reports_project_governance(self) -> None:
        (self.root / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
        result = self.run_bundle("doctor", "--root", str(self.root))
        payload = json.loads(result.stdout)
        self.assertTrue(payload["has_project_agent_entry"])
        self.assertIn("AGENTS.md", payload["project_governance_found"])
        self.assertIn("CONTRIBUTING.md", payload["project_governance_missing"])
        self.assertEqual(payload["project_governance_optional_found"], [])

    def test_doctor_treats_docs_markdown_as_optional_governance(self) -> None:
        result = self.run_bundle("doctor", "--root", str(self.root))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["project_governance_missing"], ["AGENTS.md", "CONTRIBUTING.md"])
        self.assertEqual(payload["project_governance_optional_found"], [])

        process = self.root / "docs" / "process"
        process.mkdir(parents=True)
        (process / "testing.md").write_text("# Testing\n", encoding="utf-8")
        result = self.run_bundle("doctor", "--root", str(self.root))
        payload = json.loads(result.stdout)
        self.assertIn("docs/process/testing.md", payload["project_governance_found"])
        self.assertIn("docs/process/testing.md", payload["project_governance_optional_found"])
        self.assertNotIn("docs/process/testing.md", payload["project_governance_missing"])


class NonZeroTextTestResult(unittest.TextTestResult):
    def wasSuccessful(self) -> bool:
        return self.testsRun > 0 and super().wasSuccessful()


class NonZeroTextTestRunner(unittest.TextTestRunner):
    resultclass = NonZeroTextTestResult


if __name__ == "__main__":
    unittest.main(testRunner=NonZeroTextTestRunner)

