#!/usr/bin/env python3
"""Regression tests for idea_to_code_bundle.py governance controls."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("idea_to_code_bundle.py")
SKILL_DIR = SCRIPT.parent.parent
REPO_ROOT = SKILL_DIR.parent.parent
README_MD = REPO_ROOT / "README.md"
ROOT_AGENTS_MD = REPO_ROOT / "AGENTS.md"
INSTALL_SKILL = REPO_ROOT / "scripts" / "install_skill.py"
REFERENCES_DIR = SKILL_DIR / "references"
SKILL_MD = SKILL_DIR / "SKILL.md"
ROLES_STATE_MD = REFERENCES_DIR / "roles-and-state.md"
ALLOWED_REFERENCES = {
    "controlled-exploration-benchmark.md",
    "fresh-session-live-benchmark-template.md",
    "planning-patterns.md",
    "roles-and-state.md",
    "verification-and-evidence.md",
    "workflow.md",
}
TEST_SUBPROCESS_TIMEOUT_SECONDS = 30
TEST_ACCEPTANCE_HEADER = (
    "| ID | User Goal Fit | Acceptance Examples | Counterexamples | Non-Goal Boundaries | "
    "Expected Path | Negative/Invalid Inputs | Boundary Cases | State/Persistence | "
    "Rollback/Cancellation | Error Reporting | Observability | Real Product Path | Validation Type |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
)


def load_bundle_module():
    spec = importlib.util.spec_from_file_location("idea_to_code_bundle_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load module spec for {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_test_subprocess(
    command: list[str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TEST_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        raise AssertionError(
            "test subprocess timed out after "
            f"{TEST_SUBPROCESS_TIMEOUT_SECONDS} seconds: {command}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        ) from exc


def role_checklist_items(text: str, role: str, heading: str) -> list[str]:
    role_heading = f"### {role.title()} Evidence"
    section = text.split(role_heading, 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    subsection = section.split(f"{heading}:", 1)[1]
    for next_heading in ["Must include:", "Must not include:"]:
        if next_heading != f"{heading}:" and next_heading in subsection:
            subsection = subsection.split(next_heading, 1)[0]
    return [
        line[2:].strip().strip("`")
        for line in subsection.splitlines()
        if line.startswith("- ")
    ]


class BundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_bundle(
        self,
        *args: str,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
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

    def test_role_evidence_checklist_covers_all_roles(self) -> None:
        text = ROLES_STATE_MD.read_text(encoding="utf-8")
        self.assertIn("## Role Evidence Checklist", text)
        self.assertIn("role explain --role <planner|implementer|validator|reviewer|closer>", text)
        self.assertIn("not a state transition", text)
        self.assertIn("not a replacement for `role record`", text)
        for role in ["Planner", "Implementer", "Validator", "Reviewer", "Closer"]:
            self.assertIn(f"### {role} Evidence", text)
            section = text.split(f"### {role} Evidence", 1)[1].split("\n### ", 1)[0]
            self.assertIn("Must include:", section)
            self.assertIn("Must not include:", section)

    def test_role_explain_guidance_matches_checklist_bidirectionally(self) -> None:
        text = ROLES_STATE_MD.read_text(encoding="utf-8")
        result = self.run_bundle("role", "explain")
        payload = json.loads(result.stdout)
        for entry in payload["roles"]:
            documented_must = role_checklist_items(text, entry["role"], "Must include")
            documented_must_not = role_checklist_items(text, entry["role"], "Must not include")
            self.assertEqual(entry["must_include"], documented_must)
            self.assertEqual(entry["must_not_include"], documented_must_not)
        reviewer = next(entry for entry in payload["roles"] if entry["role"] == "reviewer")
        self.assertIn(
            "same-agent review when the reviewer is not a real independent subagent",
            reviewer["must_include"],
        )

    def test_skill_points_role_record_flow_to_checklist_helper(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("Role Evidence Checklist", text)
        self.assertIn("role explain --role <role>", text)
        self.assertIn("does not change state", text)
        self.assertIn("does not replace `role record`", text)
        self.assertIn("if `role record` rejects evidence", text)

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

    def test_readme_documents_skill_install_boundary(self) -> None:
        if not README_MD.exists():
            self.skipTest("repository README.md is not present in this installed skill context")
        text = README_MD.read_text(encoding="utf-8")
        self.assertIn("This repository is the development wrapper", text)
        self.assertIn("The installable skill source is only", text)
        self.assertIn("skills/idea-to-code/", text)
        self.assertIn("not installed as skill runtime instructions", text)
        self.assertIn("Do not add repository-root rule files such as `AGENTS.md`", text)

    def test_root_agents_md_is_not_used_for_skill_runtime_rules(self) -> None:
        if not README_MD.exists():
            self.skipTest("repository README.md is not present in this installed skill context")
        self.assertFalse(
            ROOT_AGENTS_MD.exists(),
            "Root AGENTS.md is not installed with the skill; put runtime rules under skills/idea-to-code/.",
        )

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
        result = run_test_subprocess(
            [sys.executable, __file__, "-k", "definitely_no_idea_to_code_tests_match"],
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
            "route/current -> intake gate -> controlled exploration -> bundle",
            "Tool-owned gates are not optional",
            "does not narrow ordinary coding capability",
        ]:
            self.assertIn(required, text)
        for outdated in [
            "Core Contract For Fresh Agents",
            "Console " + "Handoff Contract",
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

    def test_console_ready_output_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "Console Response Contract",
            "[idea-to-code][Closer/agent] Status: Completed | Progress | Blocked",
            "Changes",
            "Completed Items",
            "Incomplete Items",
            "Validation Results",
            "Unverified Items",
            "Residual Risks",
            "Key Technical Details",
            "Do not use `Completed` to claim final accepted closeout for the whole bundle",
            "write `none`",
            "use these field names",
            "entered todo/REQ/TASK accounting",
            "formal tracked delivery status",
            "final handoff",
            "formal delivery status",
            "[idea-to-code][Closer/agent]",
            "formal tracked `Progress`, validation, install, or status responses",
            "render-status",
            "The helper prints the fixed field skeleton",
            "The helper does not finalize, verify, or mutate the bundle",
            "must name the relevant `TASK-*` and `REQ-*` IDs",
            "represented by a READY TASK",
            "If a response cannot map to a TASK/REQ",
            "Status labels describe the scope of the current user-visible response",
            "Use `Completed` when every TASK/REQ in that response's stated scope is implemented and validated",
            "For an interim TASK/REQ slice, `Completed` does not claim the whole bundle is finalized",
            "Use `Progress` when at least one in-scope TASK/REQ is still being implemented or validated",
            "`Incomplete Items` must contain only unfinished in-scope TASK/REQ work",
            "Do not list `No commit made`, `bundle not finalized`, `awaiting user review`, or fresh-session/user acceptance retest as incomplete",
            "Put no-commit and bundle-finalization state in `Key Technical Details`",
            "put fresh-session checks, user acceptance, or other external checks in `Unverified Items`",
            "<TASK/REQ-mapped change>",
            "<TASK/REQ-mapped accepted item or coverage>",
            "<TASK/REQ-mapped validation type + command/evidence + result>",
            "awaiting user review",
            "No commit made",
            "Do not leave commit/publish state implicit",
            "Do not use the fixed field contract for ordinary questions",
            "short explanations",
            "naming discussions",
            "even when a bundle is active",
            "the template is for formal tracked delivery status, not every message",
        ]:
            self.assertIn(required, combined)

    def test_render_status_outputs_fixed_field_skeleton(self) -> None:
        result = self.run_bundle(
            "quickstart",
            "--root", str(self.root),
            "--slug", "render-status",
            "--title", "Render status",
            "--idea", "Render a formal status response skeleton.",
            "--file", "README.md",
            "--task", "Document the status render behavior.",
            "--unique",
        )
        slug = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))["slug"]
        ready_match = re.search(r"READY_TASK_OUTPUT_ID:\s*(\S+)", result.stdout)
        self.assertIsNotNone(ready_match)

        rendered = self.run_bundle(
            "render-status",
            "--root", str(self.root),
            "--slug", slug,
            "--status", "Completed",
        )

        for required in [
            "[idea-to-code][Closer/agent] Status: Completed",
            "Changes:",
            "Completed Items:",
            "Incomplete Items:",
            "Validation Results:",
            "Unverified Items:",
            "Residual Risks:",
            "Key Technical Details:",
            "TASK-*",
            "REQ-1",
            "READY_TASK_OUTPUT_ID:",
            ready_match.group(1),
            "No commit made",
            "Bundle finalization/commit/publish state belongs here unless explicitly in scope.",
        ]:
            self.assertIn(required, rendered.stdout)

    def test_status_scope_semantics_prevent_false_incomplete_items(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text, benchmark_text])

        for required in [
            "Status labels describe the scope of the current user-visible response",
            "Use `Completed` when every TASK/REQ in that response's stated scope is implemented and validated",
            "If `Incomplete Items` is `none` for the stated response scope and validation passed, default to `Status: Completed`",
            "do not downgrade to `Progress` only because the bundle remains open, no commit was made, fresh-session retest remains external, or user acceptance has not been separately collected",
            "Do not use `Completed` to claim final accepted closeout for the whole bundle",
            "`Incomplete Items` must contain only unfinished in-scope TASK/REQ work",
            "Do not list `No commit made`, `bundle not finalized`, `awaiting user review`, or fresh-session/user acceptance retest as incomplete",
            "Put no-commit and bundle-finalization state in `Key Technical Details`",
            "put fresh-session checks, user acceptance, or other external checks in `Unverified Items`",
            "Uses `Status: Completed` for fully validated response-scoped TASK/REQ slices with `Incomplete Items: none`",
            "Does not downgrade a fully validated response-scoped slice to `Status: Progress`",
            "Lists `No commit made` under Key Technical Details by default, not Incomplete Items",
            "Explicitly says `No commit made` in Key Technical Details unless commit was an explicit in-scope TASK/REQ",
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

    def test_controlled_exploration_is_documented_as_bounded_and_not_extra_approval(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        planning_text = (REFERENCES_DIR / "planning-patterns.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, planning_text, verification_text, benchmark_text])

        for required in [
            "Controlled Exploration",
            "Exploration Needed: yes|no",
            "Options Considered",
            "Decision reason",
            "not a second approval gate",
            "2-4 options",
            "Need Confirmation: yes",
            "Need Confirmation: no",
            "recommended decision",
            "implementation ready",
            "Default to `Exploration Needed: no`",
            "Use `yes` only for a real fork or risk",
            "treat it as a candidate path",
            "recommend a better default path",
            "not a fixed answer template",
            "Do not hard-code fixed answers",
            "does not blindly follow a flawed requested implementation",
            "controlled-exploration-benchmark.md",
            "live model outputs",
            "Scenario Library",
            "Run Protocol",
        ]:
            self.assertIn(required, combined)

    def test_controlled_exploration_benchmark_has_required_scenarios_and_rubric(self) -> None:
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")

        for required in [
            "Do not score a hard-coded sample answer",
            "Scoring Rubric",
            "Real goal",
            "Flawed proposal",
            "Better default",
            "Confirmation burden",
            "Verification",
            "Alignment",
            "Small-task friction",
            "Scenario score: `0-7`",
            "Total: <n>/7",
            "unnecessary exploration",
            "no option dump, no confirmation",
            "Scenario 1: Destructive Security Request",
            "Scenario 2: Overbroad Rewrite",
            "Scenario 3: Low-Risk Better Implementation",
            "Scenario 4: Ambiguous Product Direction",
            "Scenario 5: Clear Small Task",
            "Scenario 6: Inappropriate Data Shortcut",
            "Response Mode Scenarios",
            "Response Scenario A: Tracked Progress Status",
            "Response Scenario B: Ordinary Explanation",
            "Response Scenario C: Naming Discussion",
            "Response Scenario D: In-Progress Working Update",
            "Response Scenario E: Tracked Conversation, No Status Request",
            "Response Scenario F: Explicit No-Commit Status Request",
            "Expected mode: `tracked-delivery-status`",
            "Expected mode: `tracked-work-update`",
            "Expected mode: `untracked-answer`",
            "Expected mode: `commentary-update`",
            "Reporting Format",
            "Instruction gap",
        ]:
            self.assertIn(required, benchmark_text)

    def test_benchmark_reporting_rows_match_scoring_rubric_dimensions(self) -> None:
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")
        rubric = re.search(r"## Scoring Rubric[\s\S]*?\n\n\| Dimension \| Passing behavior \|\n\|---\|---\|\n(?P<table>[\s\S]*?)\n\nScenario score", benchmark_text)
        self.assertIsNotNone(rubric)
        rubric_dimensions = [
            line.split("|")[1].strip()
            for line in rubric.group("table").splitlines()
            if line.startswith("|")
        ]

        reporting = re.search(r"## Reporting Format[\s\S]*?Scores:\n(?P<scores>[\s\S]*?)Total: <n>/7", benchmark_text)
        self.assertIsNotNone(reporting)
        reporting_dimensions = [
            line[2:].split(":", 1)[0].strip()
            for line in reporting.group("scores").splitlines()
            if line.startswith("- ")
        ]

        self.assertEqual(reporting_dimensions, rubric_dimensions)
        self.assertIn("Small-task friction", reporting_dimensions)

    def test_controlled_exploration_quality_closure_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text, benchmark_text])

        for required in [
            "Small-task friction remains a hard guardrail",
            "the selected option's `Decision reason` and `Verification path` held up",
            "decision reason and verification path held up",
            "Recommendation quality checks",
            "user-goal fit",
            "risk/cost reduction",
            "Constraint and non-goal preservation",
            "Verifiability",
            "Decision closure",
            "recommendation quality was better than the rejected options",
            "confirmation request compression is deferred",
            "over-compressing the request can distort user intent",
        ]:
            self.assertIn(required, combined)

    def test_fresh_session_live_benchmark_protocol_is_documented(self) -> None:
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        template_path = REFERENCES_DIR / "fresh-session-live-benchmark-template.md"
        template_text = template_path.read_text(encoding="utf-8")
        combined = "\n".join([benchmark_text, skill_text, template_text])

        for required in [
            "Fresh-Session Live Benchmark Protocol",
            "Controlled samples and instruction-level reviews are useful, but they are not production proof",
            "Use the exact installed skill; do not paste corrected guidance into the chat",
            "Capture raw assistant output before editing or correcting it",
            "Fresh-session score dimensions",
            "Controlled Exploration fit",
            "READY visibility",
            "Response mode",
            "Status semantics",
            "Small-task friction",
            "Fresh-session score: `0-7` per output",
            ">= 32/35",
            "Time and cost bounds",
            "Default run uses exactly five prompts",
            "Maximum wall-clock budget is 45 minutes",
            "Stop early",
            "Elapsed time",
            "Prompt count",
            "Stop reason",
            "Fresh-Session Reporting Format",
            "Fresh-session run id",
            "Raw output",
            "Instruction drift",
            "prompt-level scenario library plus fresh-session live benchmark protocol",
        ]:
            self.assertIn(required, combined)

    def test_confirmation_ready_output_contract_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "Confirmation Required",
            "[idea-to-code][Planner/agent] Confirmation Required",
            "explicit decision request",
            "paused before implementation",
            "Restated user goal",
            "Observable acceptance outcome",
            "Proposed scope after approval",
            "Planned TASK list before approval",
            "TASK-1: <change point>",
            "Files:",
            "Execution Details:",
            "Done Criteria:",
            "Planned Verification:",
            "Please reply with one of:",
            '"yes" or "approved"',
            '"change: <correction>"',
            '"pause"',
            '"cancel"',
            "print the READY TASK list",
            "acceptance anchor for closeout",
            "approved TASK list",
            "what happens next",
            "If the user cannot tell how to answer",
        ]:
            self.assertIn(required, combined)

    def test_need_confirmation_no_still_requires_user_visible_ready_task_list(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "`Need Confirmation: no` skips the approval wait",
            "does not skip task-list visibility",
            "before any product-file edit",
            "`implementation ready` prints the generated",
            "READY_TASK_OUTPUT_ID",
            "user-visible `[idea-to-code][Planner/agent] Implementation Gate: READY`",
            "Files",
            "Execution Details",
            "Done Criteria",
            "Planned Verification",
            "transparency, not an approval request",
            "Command stdout, tool output, or a folded transcript is not enough by itself",
            "Tool stdout or folded command transcripts are not enough for READY visibility",
            "send a normal assistant message",
            "Plan-level READY",
            "Execution-level READY",
            "For multi-task work, default the user-visible execution message to the current TASK",
            "not the entire long task list",
            "focused READY TASK excerpt",
            "--task TASK-N",
            "Focused READY output is for user visibility only",
            "hard contract",
            "covered REQ hint",
            "covered `REQ-*`",
            "If any of those fields are missing, the READY output is invalid",
            "same visible TASK/REQ set",
            "Before moving from TASK-1 to TASK-2, show the TASK-2 focused READY excerpt",
            "each result bullet maps to the focused execution-level READY excerpt shown before that TASK",
            "must not introduce unshown or unmapped work",
            "Before product-file edits, the READY task list must be visible to the user in a normal assistant message",
            "Implementer evidence must cite the generated READY output id",
            "Use `implementation show-ready` to reprint or refresh",
            "Use `quickstart --json` only for automation",
        ]:
            self.assertIn(required, combined)

    def test_multi_task_ready_visibility_defaults_to_current_task_pairing(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "READY visibility has two layers",
            "`Plan-level READY`: the complete TASK list remains in `00-idea.md`",
            "`Execution-level READY`: the current TASK excerpt is shown immediately before that TASK is executed",
            "For multi-task work, default user-visible execution display to the current TASK's focused READY excerpt",
            "Before moving from one TASK to the next, show the next TASK's focused READY excerpt",
            "The generated READY output has a hard excerpt contract",
            "the `TASK-*` or `IMP-*` line",
            "covered `REQ-*` or the script's covered REQ hint when inferable",
            "If generated READY output omits any of these fields, it is invalid",
            "The final summary may aggregate TASKs, but it must not introduce unshown or unmapped work",
        ]:
            self.assertIn(required, combined)

    def test_execution_visibility_documents_profile_prefix(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, workflow_text])

        for required in [
            "Direct idea-to-code use uses `[idea-to-code][Role/source]`",
            "use `[idea-to-code/<profile-name>][Role/source]`",
            "[idea-to-code/<profile-name>][Planner/agent] Mode: delivery",
            "[idea-to-code][Planner/agent]",
            "[idea-to-code][Validator/subagent]",
            "`Planner`, `Implementer`, `Validator`, `Reviewer`, or `Closer`",
            "`subagent` only when a real delegated subagent actually ran",
            "Do not display `/subagent` as a plan or aspiration",
            "caller-provided and display-only",
            "does not change lifecycle gates, state files, ledger semantics, permissions, or closeout rules",
            "Do not infer trust, ownership, permissions, or scope from a profile name",
            "default or profile-aware idea-to-code role/source prefix",
            "Do not remove or shorten existing READY TASK, confirmation, validation, or closeout fields",
        ]:
            self.assertIn(required, combined)

    def test_delegation_healthcheck_protocol_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text])

        for required in [
            "Delegation Healthcheck Protocol",
            "Use this protocol before claiming `/subagent`",
            "`Ping`",
            "`Scoped review`",
            "`Broader review`",
            "`Timeout/fallback record`",
            "role delegated: `Validator` or `Reviewer`",
            "scope delegated: files, TASK/REQ IDs, or question",
            "result returned before timeout",
            "whether the result is used as independent evidence or rejected as unusable",
            "Do not display `/subagent` for planned, timed-out, unavailable, or unusable delegation",
            "Use the Delegation Healthcheck Protocol",
        ]:
            self.assertIn(required, combined)

    def test_user_visible_prefix_examples_do_not_drift_to_old_forms(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL_MD, *sorted(REFERENCES_DIR.glob("*.md"))]
        )

        old_bare_lifecycle_examples = [
            r"\[idea-to-code\]\s+Implementation Gate:",
            r"\[idea-to-code\]\s+Confirmation Required",
            r"\[idea-to-code\]\s+Status:",
            r"\[idea-to-code\]\s+Mode:",
            r"\[idea-to-code/<profile-name>\]\s+Implementation Gate:",
            r"\[idea-to-code/<profile-name>\]\s+Mode:",
        ]
        for pattern in old_bare_lifecycle_examples:
            self.assertIsNone(re.search(pattern, combined), pattern)

        self.assertIsNone(
            re.search(r"\[idea-to-code(?:/[^\]]+)?\]\[[A-Za-z]+/same-agent\]", combined),
            "Visible source labels should be agent/subagent; same-agent is only an internal execution mode.",
        )

        for expected in [
            "[idea-to-code][Planner/agent] Implementation Gate: READY",
            "[idea-to-code][Planner/agent] Confirmation Required",
            "[idea-to-code][Closer/agent] Status: Completed | Progress | Blocked",
            "[idea-to-code/<profile-name>][Planner/agent] Mode: delivery",
        ]:
            self.assertIn(expected, combined)

    def test_formal_response_template_keeps_required_fields_and_task_req_placeholders(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        template = skill_text.split("```text\n[idea-to-code][Closer/agent] Status: Completed | Progress | Blocked", 1)[1].split("```", 1)[0]

        expected_order = [
            "Changes:",
            "Completed Items:",
            "Incomplete Items:",
            "Validation Results:",
            "Unverified Items:",
            "Residual Risks:",
            "Key Technical Details:",
        ]
        last_index = -1
        for field in expected_order:
            next_index = template.find(field)
            self.assertGreater(next_index, last_index, field)
            last_index = next_index

        for required in [
            "<TASK/REQ-mapped change>",
            "<TASK/REQ-mapped accepted item or coverage>",
            "<TASK/REQ-mapped unfinished item and why>",
            "<TASK/REQ-mapped validation type + command/evidence + result>",
        ]:
            self.assertIn(required, template)

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
            "User Goal Fit",
            "Acceptance Examples",
            "Counterexamples",
            "Non-Goal Boundaries",
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
        self.assertIn("implementation-ready-required", payload["route_gates"])

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

## Controlled Exploration

- Exploration Needed: no
- Trigger: Test fixture has one direct command-flow implementation path.
- Constraints:
  - Keep the fixture scoped to state.json and bundle commands.
- Options Considered:
  - Not required for this deterministic test fixture.
- Decision:
  - Chosen option: Use the direct ready-bundle fixture.
  - Decision reason: No architecture or behavior fork requires option exploration.
  - Rejected options: none.
  - Unverified items: none.

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Behavior-changing tracked test flow.

## Acceptance Matrix

{TEST_ACCEPTANCE_HEADER}
| REQ-1 | Sample behavior matches the requested command outcome. | Final bundle verification succeeds for REQ-1. | Missing evidence must not be accepted. | Production code changes are outside this fixture. | {expected_path} | {negative} | {boundary} | {state} | {rollback} | {error} | {observability} | {product_path} | {validation_type} |
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

    def run_ready_output(self, slug: str) -> str:
        result = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        match = re.search(r"READY_TASK_OUTPUT_ID:\s*(\S+)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        return match.group(1)

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
        requirements = f"""# Requirements

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

## Controlled Exploration

- Exploration Needed: no
- Trigger: Test fixture has one direct negative verification path.
- Constraints:
  - Keep the fixture scoped to missing requirement coverage.
- Options Considered:
  - Not required for this deterministic test fixture.
- Decision:
  - Chosen option: Use the direct no-requirement fixture.
  - Decision reason: No implementation alternative is needed for this negative test.
  - Rejected options: none.
  - Unverified items: none.

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Behavior-changing tracked test flow.

## Acceptance Matrix

{TEST_ACCEPTANCE_HEADER}
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
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned in 00-idea.md with TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
        )
        output_id = self.run_ready_output(slug)
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", f"TASK-1 implemented through state.json bundle records for REQ-1 after READY_TASK_OUTPUT_ID {output_id}",
            "--covers", "REQ-1",
        )
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "validator",
            "--evidence", "REQ-1 source-only validation with python idea_to_code_bundle.py verify recorded in 01-progress.md",
            "--covers", "REQ-1",
        )
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "reviewer",
            "--evidence", "same-agent review checked REQ-1 scope, 00-idea.md, 00-idea.md, and 01-progress.md coverage",
            "--covers", "REQ-1",
        )

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
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        if status.get("ready_task_output_required") and not status.get("ready_task_output_id"):
            self.run_ready_output(slug)
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

    def test_role_explain_all_roles(self) -> None:
        result = self.run_bundle("role", "explain")
        payload = json.loads(result.stdout)
        roles = {entry["role"]: entry for entry in payload["roles"]}
        self.assertEqual(set(roles), {"planner", "implementer", "validator", "reviewer", "closer"})
        self.assertIn("covered REQ IDs", roles["validator"]["must_include"])
        self.assertIn("pre-close verify passed", roles["closer"]["must_include"])
        self.assertIn("example", roles["planner"])

    def test_role_explain_single_role(self) -> None:
        result = self.run_bundle("role", "explain", "--role", "validator")
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["roles"]), 1)
        self.assertEqual(payload["roles"][0]["role"], "validator")
        self.assertIn("validation type", " ".join(payload["roles"][0]["must_include"]))

    def test_verify_rejects_weak_acceptance_matrix(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, weak_matrix=True)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("weak column", verify.stdout)

    def test_verify_rejects_legacy_acceptance_matrix_without_user_intent_columns(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        idea_path = self.root / ".idea-to-code" / slug / "00-idea.md"
        text = idea_path.read_text(encoding="utf-8")
        legacy_header = (
            "| ID | Expected Path | Negative/Invalid Inputs | Boundary Cases | State/Persistence | "
            "Rollback/Cancellation | Error Reporting | Observability | Real Product Path | Validation Type |\n"
            "|----|---------------|-------------------------|----------------|-------------------|-----------------------|"
            "-----------------|---------------|-------------------|-----------------|\n"
            "| REQ-1 | command exits zero | invalid command reports a failure | empty input is explicitly outside scope | "
            "state.json records role evidence | no rollback state is created | stderr reports command failures | "
            "verify prints JSON output | temporary script path only | source-only |"
        )
        text = re.sub(
            r"\| ID \| User Goal Fit \|[\s\S]*?(?=\n## Design)",
            legacy_header + "\n",
            text,
        )
        idea_path.write_text(text, encoding="utf-8")
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)

        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)

        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("Acceptance Matrix header missing column: User Goal Fit", verify.stdout)
        self.assertIn("Acceptance Matrix header missing column: Acceptance Examples", verify.stdout)

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
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "reviewer", "--evidence", "same-agent review checked REQ-1 residual risk and coverage in 01-progress.md after prior verify", "--covers", "REQ-1")
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        latest_reviewer = status["role_evidence"]["reviewer"][-1]
        self.assertGreater(latest_reviewer["event_sequence"], status["last_verified_event_sequence"])
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
        refreshed = self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ok": true', refreshed.stdout)
        accepted = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "closer",
            "--evidence", "REQ-1 covered by Sample milestone; pre-close source-only verify passed; final decision pass accepted",
            "--covers", "REQ-1",
        )
        self.assertEqual(accepted.returncode, 0)

    def test_bundle_lock_timeout_reports_owner_and_recovery_hint(self) -> None:
        slug = self.init_bundle()
        lock_dir = self.root / ".idea-to-code" / slug / ".status.lock"
        lock_dir.mkdir()
        (lock_dir / "owner.json").write_text(
            json.dumps({"pid": 424242, "created_at_utc": "2026-01-01T00:00:00+00:00"}) + "\n",
            encoding="utf-8",
        )

        result = self.run_bundle(
            "requirement", "add",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "REQ-LOCK",
            "--description", "Lock diagnostic requirement",
            "--type", "functional",
            check=False,
            env={"IDEA_TO_CODE_LOCK_TIMEOUT_SECONDS": "0.01"},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".status.lock", result.stderr)
        self.assertIn("owner pid=424242", result.stderr)
        self.assertIn("created_at_utc=2026-01-01T00:00:00+00:00", result.stderr)
        self.assertIn("remove", result.stderr)

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
        output_id = self.run_ready_output(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", f"TASK-1 implemented by updating state.json behavior in 00-idea.md after READY_TASK_OUTPUT_ID {output_id}", "--covers", "REQ-1")
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "validator", "--evidence", "REQ-1 reviewed in 01-progress.md with coverage notes", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Validator evidence must name a validation type", result.stderr)

    def test_validator_allows_role_words_inside_test_identifiers(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        output_id = self.run_ready_output(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", f"TASK-1 implemented by updating state.json behavior in 00-idea.md after READY_TASK_OUTPUT_ID {output_id}", "--covers", "REQ-1")

        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "validator",
            "--evidence", "REQ-1 source-only validation command python test_idea_to_code_bundle.py BundleTest.test_closer_requires_verify_after_latest_reviewer passed",
            "--covers", "REQ-1",
        )

        self.assertEqual(result.returncode, 0)

    def test_validator_still_rejects_wrong_role_prose(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        output_id = self.run_ready_output(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", f"TASK-1 implemented by updating state.json behavior in 00-idea.md after READY_TASK_OUTPUT_ID {output_id}", "--covers", "REQ-1")

        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "validator",
            "--evidence", "Reviewer performed REQ-1 source-only validation with python verify command",
            "--covers", "REQ-1",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Validator evidence must describe validation work, not another role", result.stderr)

    def test_reviewer_requires_review_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        output_id = self.run_ready_output(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", f"TASK-1 implemented by updating state.json behavior in 00-idea.md after READY_TASK_OUTPUT_ID {output_id}", "--covers", "REQ-1")
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "validator", "--evidence", "REQ-1 source-only validation ran python idea_to_code_bundle.py verify command", "--covers", "REQ-1")
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "reviewer", "--evidence", "REQ-1 source-only python validation ran in 01-progress.md", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Reviewer evidence must describe scope", result.stderr)

    def test_reviewer_requires_role_independence_disclosure(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "planner", "--evidence", "REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 in 00-idea.md", "--covers", "REQ-1")
        output_id = self.run_ready_output(slug)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "implementer", "--evidence", f"TASK-1 implemented by updating state.json behavior in 00-idea.md after READY_TASK_OUTPUT_ID {output_id}", "--covers", "REQ-1")
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "validator", "--evidence", "REQ-1 source-only validation ran python idea_to_code_bundle.py verify command", "--covers", "REQ-1")
        result = self.run_bundle("role", "record", "--root", str(self.root), "--slug", slug, "--role", "reviewer", "--evidence", "REQ-1 review checked scope, coverage, boundary, and residual risk in 01-progress.md", "--covers", "REQ-1", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Reviewer evidence must disclose role independence", result.stderr)

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
        ready_output = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("Files:\nstate.json", ready_output.stdout)
        self.assertIn("Execution Details:\nRecord one requirement and all role evidence.", ready_output.stdout)
        self.assertIn("Done Criteria:\nfinalize and verify succeed.", ready_output.stdout)
        self.assertIn("Planned Verification:\nsource-only python idea_to_code_bundle.py verify exits zero.", ready_output.stdout)

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

    def test_implementation_ready_rejects_missing_controlled_exploration(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        idea_path = self.root / ".idea-to-code" / slug / "00-idea.md"
        text = idea_path.read_text(encoding="utf-8")
        text = re.sub(
            r"\n## Controlled Exploration\n[\s\S]*?(?=\n## Task Classification\n)",
            "",
            text,
            count=1,
        )
        idea_path.write_text(text, encoding="utf-8")

        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing Controlled Exploration section", result.stderr)

    def test_implementation_ready_rejects_required_controlled_exploration_without_decision(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        idea_path = self.root / ".idea-to-code" / slug / "00-idea.md"
        text = idea_path.read_text(encoding="utf-8")
        replacement = """\n## Controlled Exploration\n\n- Exploration Needed: yes\n- Trigger: Two user-visible approaches need comparison before implementation.\n- Constraints:\n  - Keep scope narrow.\n- Options Considered:\n  - Option A: Direct command flow.\n    - Hypothesis: The direct path satisfies the fixture.\n    - Fit to user goal: Strong fit for the test fixture.\n    - Cost: Low.\n    - Risk: Low.\n    - Verification path: implementation ready command.\n    - Rejection condition: The command rejects the bundle.\n- Decision:\n  - Chosen option:\n  - Decision reason:\n  - Rejected options:\n  - Unverified items:\n"""
        text = re.sub(
            r"\n## Controlled Exploration\n[\s\S]*?(?=\n## Task Classification\n)",
            replacement,
            text,
            count=1,
        )
        idea_path.write_text(text, encoding="utf-8")

        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Decision missing concrete Chosen option", result.stderr)
        self.assertIn("Decision missing concrete Decision reason", result.stderr)

    def test_implementation_ready_accepts_intake_without_confirmation_needed(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("[idea-to-code][Planner/agent] Implementation Gate: READY", result.stdout)
        self.assertIn("READY_TASK_OUTPUT_ID:", result.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", result.stdout)
        self.assertNotIn(str(self.root / ".idea-to-code" / slug), result.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["implementation_ready"])
        self.assertTrue(status["ready_task_output_required"])
        self.assertEqual(status["ready_task_output_plan_revision"], status["plan_revision"])
        self.assertTrue(status["ready_task_output_id"])

    def test_implementation_ready_supports_profile_prefix(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        result = self.run_bundle(
            "implementation", "ready",
            "--root", str(self.root),
            "--slug", slug,
            "--profile", "upper-layer",
        )
        self.assertIn("[idea-to-code/upper-layer][Planner/agent] Implementation Gate: READY", result.stdout)
        self.assertIn("READY_TASK_OUTPUT_ID:", result.stdout)
        self.assertNotIn("[idea-to-code][Planner/agent] Implementation Gate: READY", result.stdout)

    def test_implementation_ready_rejects_role_source_override(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        result = self.run_bundle(
            "implementation", "ready",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "validator",
            "--source", "subagent",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("implementation READY output is always a Planner/agent gate", result.stderr)

    def test_implementation_ready_normalizes_role_case(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        result = self.run_bundle(
            "implementation", "ready",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "Planner",
            "--source", "agent",
        )
        self.assertIn("[idea-to-code][Planner/agent] Implementation Gate: READY", result.stdout)

    def test_implementation_profile_is_display_only_not_persisted(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        self.run_bundle(
            "implementation", "ready",
            "--root", str(self.root),
            "--slug", slug,
            "--profile", "upper-layer",
        )

        bundle_path = self.root / ".idea-to-code" / slug
        status = json.loads((bundle_path / "state.json").read_text(encoding="utf-8"))
        ledger = (bundle_path / "01-progress.md").read_text(encoding="utf-8")

        self.assertNotIn("profile", status)
        self.assertNotIn("upper-layer", json.dumps(status))
        self.assertNotIn("upper-layer", ledger)

    def test_implementation_show_ready_prints_ready_task_list_and_records_id(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("[idea-to-code][Planner/agent] Implementation Gate: READY", result.stdout)
        self.assertIn("READY_TASK_OUTPUT_ID:", result.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", result.stdout)
        self.assertIn("Files:", result.stdout)
        self.assertIn("Execution Details:", result.stdout)
        self.assertIn("Done Criteria:", result.stdout)
        self.assertIn("Planned Verification:", result.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["ready_task_output_plan_revision"], status["plan_revision"])
        self.assertTrue(status["ready_task_output_id"])

    def test_implementation_show_ready_can_reprint_ready_task_list(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("[idea-to-code][Planner/agent] Implementation Gate: READY", result.stdout)
        self.assertIn("READY_TASK_OUTPUT_ID:", result.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", result.stdout)
        self.assertIn("Files:", result.stdout)

    def test_implementation_show_ready_supports_focused_task_output(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        before = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        result = self.run_bundle(
            "implementation", "show-ready",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
        )

        for required in [
            "Focused READY TASK excerpt: yes",
            "This excerpt is for visibility only",
            "TASK-1: Verify sample bundle flow",
            "Covered REQ hint: REQ-1",
            "Files:",
            "Done Criteria:",
            "Planned Verification:",
            "READY_TASK_OUTPUT_ID:",
        ]:
            self.assertIn(required, result.stdout)
        after = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(after["ready_task_output_id"], before["ready_task_output_id"])
        self.assertEqual(after["ready_task_output_event_sequence"], before["ready_task_output_event_sequence"])
        self.assertEqual(after["ready_task_output_scope"], "full-plan")

    def test_implementation_ready_task_keeps_full_plan_ready_anchor(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
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

### TASK-2: Verify second task visibility

Status: pending

Files:
- state.json

Execution Details:
- Confirm focused READY can show a later task.

Done Criteria:
- TASK-2 focused READY output is available.

Planned Verification:
- source-only implementation show-ready --task TASK-2 exits zero.
"""
        impl_path = self.root / "implementation-two-tasks.md"
        impl_path.write_text(implementation, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))

        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        self.assertIn("Focused READY TASK excerpt: yes", ready.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", ready.stdout)
        self.assertNotIn("TASK-2: Verify second task visibility", ready.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["ready_task_output_scope"], "full-plan")

        focused_second = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug, "--task", "TASK-2")
        self.assertIn("TASK-2: Verify second task visibility", focused_second.stdout)
        status_after = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status_after["ready_task_output_id"], status["ready_task_output_id"])
        self.assertEqual(status_after["ready_task_output_scope"], "full-plan")

    def test_ready_output_contract_accepts_complete_focused_output(self) -> None:
        module = load_bundle_module()
        blocks = [(
            "TASK-1: Verify sample bundle flow",
            "Files:\n- README.md\n\nDone Criteria:\n- Change is visible\n\nPlanned Verification:\n- source-only check",
        )]
        lines = module._format_ready_output(
            "sample",
            "Sample task",
            "sample-r1-20260626000000",
            blocks,
            focused=True,
        )
        self.assertEqual(module._ready_output_contract_problems(lines, blocks), [])

    def test_ready_output_contract_rejects_missing_task_line(self) -> None:
        module = load_bundle_module()
        blocks = [(
            "TASK-1: Verify sample bundle flow",
            "Files:\n- README.md\n\nDone Criteria:\n- Change is visible\n\nPlanned Verification:\n- source-only check",
        )]
        lines = [
            "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample",
            "Covered REQ hint: REQ-1",
            "Files:",
            "- README.md",
            "Done Criteria:",
            "- Change is visible",
            "Planned Verification:",
            "- source-only check",
        ]
        problems = module._ready_output_contract_problems(lines, blocks)
        self.assertIn("READY output missing task line: TASK-1: Verify sample bundle flow", problems)

    def test_ready_output_contract_rejects_missing_req_hint(self) -> None:
        module = load_bundle_module()
        blocks = [(
            "TASK-1: Verify sample bundle flow",
            "Files:\n- README.md\n\nDone Criteria:\n- Change is visible\n\nPlanned Verification:\n- source-only check",
        )]
        lines = [
            "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample",
            "TASK-1: Verify sample bundle flow",
            "Files:",
            "- README.md",
            "Done Criteria:",
            "- Change is visible",
            "Planned Verification:",
            "- source-only check",
        ]
        problems = module._ready_output_contract_problems(lines, blocks)
        self.assertIn("READY output missing covered REQ hint for TASK-1: Verify sample bundle flow: REQ-1", problems)

    def test_ready_output_contract_rejects_missing_required_section(self) -> None:
        module = load_bundle_module()
        blocks = [(
            "TASK-1: Verify sample bundle flow",
            "Files:\n- README.md\n\nDone Criteria:\n- Change is visible\n\nPlanned Verification:\n- source-only check",
        )]
        lines = [
            "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample",
            "TASK-1: Verify sample bundle flow",
            "Covered REQ hint: REQ-1",
            "Files:",
            "- README.md",
            "Done Criteria:",
            "- Change is visible",
        ]
        problems = module._ready_output_contract_problems(lines, blocks)
        self.assertIn("READY output missing Planned Verification: for TASK-1: Verify sample bundle flow", problems)

    def test_implementation_show_ready_rejects_unknown_focused_task(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle(
            "implementation", "show-ready",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-99",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("READY task filter did not match: TASK-99", result.stderr)

    def test_implementation_show_ready_supports_profile_prefix(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle(
            "implementation", "show-ready",
            "--root", str(self.root),
            "--slug", slug,
            "--profile", "upper-layer",
        )
        self.assertIn("[idea-to-code/upper-layer][Planner/agent] Implementation Gate: READY", result.stdout)
        self.assertIn("READY_TASK_OUTPUT_ID:", result.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", result.stdout)

    def test_implementation_show_ready_rejects_role_source_override(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        bad_role = self.run_bundle(
            "implementation", "show-ready",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "architect",
            check=False,
        )
        self.assertNotEqual(bad_role.returncode, 0)
        self.assertIn("implementation READY output is always a Planner/agent gate", bad_role.stderr)

        bad_source = self.run_bundle(
            "implementation", "show-ready",
            "--root", str(self.root),
            "--slug", slug,
            "--source", "planned-subagent",
            check=False,
        )
        self.assertNotEqual(bad_source.returncode, 0)
        self.assertIn("implementation READY output is always a Planner/agent gate", bad_source.stderr)

    def test_implementation_profile_rejects_unsafe_name(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle(
            "implementation", "show-ready",
            "--root", str(self.root),
            "--slug", slug,
            "--profile", "../bad",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--profile must use", result.stderr)

    def test_implementation_show_ready_rejects_non_ready_bundle(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        result = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("implementation show-ready refused", result.stderr)

    def test_quickstart_creates_ready_bundle_and_ready_output(self) -> None:
        result = self.run_bundle(
            "quickstart",
            "--root", str(self.root),
            "--slug", "readme-note",
            "--title", "Add README note",
            "--idea", "Add one concise README sentence.",
            "--file", "README.md",
            "--task", "Add one concise README sentence.",
            "--unique",
        )
        json_part, ready_output_part = result.stdout.split("\n\n", 1)
        payload = json.loads(json_part)
        slug = payload["slug"]
        self.assertTrue(payload["ready"])
        self.assertIn("[idea-to-code][Planner/agent] Implementation Gate: READY", ready_output_part)
        self.assertIn("READY_TASK_OUTPUT_ID:", ready_output_part)
        self.assertIn("TASK-1: Add one concise README sentence.", ready_output_part)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["implementation_ready"])
        self.assertTrue(status["ready_task_output_required"])
        self.assertEqual(status["ready_task_output_plan_revision"], status["plan_revision"])
        self.assertTrue(status["ready_task_output_id"])
        self.assertEqual(len(status["requirements"]), 1)
        self.assertTrue(status["role_evidence"]["planner"])
        idea = (self.root / ".idea-to-code" / slug / "00-idea.md").read_text(encoding="utf-8")
        self.assertIn("## Controlled Exploration", idea)
        self.assertIn("- Exploration Needed: no", idea)
        ready_output = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("READY_TASK_OUTPUT_ID:", ready_output.stdout)
        self.assertIn("TASK-1: Add one concise README sentence.", ready_output.stdout)

    def test_quickstart_json_mode_outputs_only_json(self) -> None:
        result = self.run_bundle(
            "quickstart",
            "--root", str(self.root),
            "--slug", "readme-json-note",
            "--title", "Add README JSON note",
            "--idea", "Add one concise README sentence for JSON mode.",
            "--file", "README.md",
            "--task", "Add one concise README sentence for JSON mode.",
            "--unique",
            "--json",
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ready"])
        self.assertTrue(payload["ready_task_output_id"])
        self.assertNotIn("[idea-to-code][Planner/agent] Implementation Gate: READY", result.stdout)

    def test_quickstart_validates_generated_bundle_and_sanitizes_matrix_cells(self) -> None:
        result = self.run_bundle(
            "quickstart",
            "--root", str(self.root),
            "--slug", "pipe-note",
            "--title", "Add README pipe note",
            "--idea", "Add one concise README sentence about A/B behavior.",
            "--file", "README.md",
            "--task", "Add one concise README sentence about A|B behavior.",
            "--unique",
        )
        json_part, ready_output_part = result.stdout.split("\n\n", 1)
        payload = json.loads(json_part)
        slug = payload["slug"]
        self.assertIn("TASK-1: Add one concise README sentence about A|B behavior.", ready_output_part)
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotIn("Acceptance Matrix row for REQ-1 has", verify.stdout)
        idea = (self.root / ".idea-to-code" / slug / "00-idea.md").read_text(encoding="utf-8")
        self.assertIn("Add one concise README sentence about A/B behavior.", idea)

    def test_quickstart_rejects_vague_task(self) -> None:
        result = self.run_bundle(
            "quickstart",
            "--root", str(self.root),
            "--slug", "bad",
            "--title", "Bad",
            "--idea", "Do it",
            "--file", "README.md",
            "--task", "x",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("too vague", result.stderr)

    def test_implementer_evidence_requires_ready_output_and_id(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        output_id = status["ready_task_output_id"]
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned in 00-idea.md with TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
        )
        missing = self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", "TASK-1 implemented through state.json bundle records for REQ-1",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn(f"READY_TASK_OUTPUT_ID {output_id}", missing.stderr)
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", f"TASK-1 implemented through state.json bundle records for REQ-1 after READY_TASK_OUTPUT_ID {output_id}",
            "--covers", "REQ-1",
        )

    def test_implementer_evidence_rejects_before_ready(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned in 00-idea.md with TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
        )
        result = self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", "TASK-1 implemented through state.json bundle records for REQ-1",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("implementation gate is not READY", result.stderr)

    def test_verify_rejects_implementer_evidence_older_than_latest_ready_output(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        old_output_id = status["ready_task_output_id"]
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned in 00-idea.md with TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
        )
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", f"TASK-1 implemented through state.json bundle records for REQ-1 after READY_TASK_OUTPUT_ID {old_output_id}",
            "--covers", "REQ-1",
        )
        self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "validator",
            "--evidence", "REQ-1 source-only validation ran python idea_to_code_bundle.py verify command",
            "--covers", "REQ-1",
        )
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "reviewer",
            "--evidence", "same-agent review checked REQ-1 scope, READY output, and 01-progress.md coverage",
            "--covers", "REQ-1",
        )
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("Implementer evidence READY output check failed", verify.stdout)
        self.assertIn("Implementer evidence must be recorded after the latest READY output", verify.stdout)

    def test_focused_ready_output_does_not_stale_implementer_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        output_id = status["ready_task_output_id"]
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned in 00-idea.md with TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
        )
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", f"TASK-1 implemented through state.json bundle records for REQ-1 after READY_TASK_OUTPUT_ID {output_id}",
            "--covers", "REQ-1",
        )
        self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        status_after_focused = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status_after_focused["ready_task_output_id"], output_id)
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "validator",
            "--evidence", "REQ-1 source-only validation ran python idea_to_code_bundle.py verify command",
            "--covers", "REQ-1",
        )
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "reviewer",
            "--evidence", "same-agent review checked REQ-1 scope, READY output, and 01-progress.md coverage",
            "--covers", "REQ-1",
        )
        self.run_bundle(
            "checkpoint", "--root", str(self.root), "--slug", slug,
            "--milestone", "Focused ready remains visibility only",
            "--delivered", "Focused READY output did not rotate global READY output id",
            "--verified", "source-only focused READY output preserved implementation evidence",
            "--next", "verify",
            "--focus", "REQ-1",
            "--gate", "verify",
            "--gate-status", "pass",
            "--covers", "REQ-1",
        )
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ok": true', verify.stdout)

    def test_missing_ready_output_blocks_evidence_checkpoint_and_verify(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        status_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["ready_task_output_id"] = None
        status["ready_task_output_plan_revision"] = None
        status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "planner",
            "--evidence", "REQ-1 planned in 00-idea.md with TASK-1 in 00-idea.md",
            "--covers", "REQ-1",
        )
        missing = self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", "TASK-1 implemented through state.json bundle records for REQ-1",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("READY output refresh required", missing.stderr)
        checkpoint = self.run_bundle(
            "checkpoint", "--root", str(self.root), "--slug", slug,
            "--milestone", "No ready output milestone",
            "--delivered", "No ready output",
            "--verified", "source-only no ready output",
            "--next", "ready output",
            "--focus", "ready output",
            "--gate", "ready output",
            "--gate-status", "pass",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(checkpoint.returncode, 0)
        self.assertIn("READY output refresh required", checkpoint.stderr)
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("READY output refresh required", verify.stdout)

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
        self.run_ready_output(slug)
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

    def test_implementation_ready_clears_pending_plan_update(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        state_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(state_path.read_text(encoding="utf-8"))
        status["pending_plan_update"] = True
        status["implementation_ready"] = False
        state_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

        status = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(status["pending_plan_update"])
        self.assertTrue(status["implementation_ready"])

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

    def test_lifecycle_reasons_reject_non_ascii_without_traceback(self) -> None:
        slug = self.init_bundle()
        for command in (
            ("checkpoint", "--root", str(self.root), "--slug", slug, "--milestone", "caf\u00e9 milestone", "--delivered", "changed files", "--verified", "source-only inspection", "--next", "continue", "--focus", "focus", "--gate", "verify", "--gate-status", "pass"),
            ("current", "archive", "--root", str(self.root), "--reason", "paus\u00e9"),
            ("current", "pause", "--root", str(self.root), "--reason", "paus\u00e9"),
            ("block", "--root", str(self.root), "--slug", slug, "--reason", "caf\u00e9 outage", "--need", "network access"),
            ("unblock", "--root", str(self.root), "--slug", slug, "--note", "r\u00e9solved"),
        ):
            result = self.run_bundle(*command, check=False)
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

    def test_current_resume_with_slug_restores_lost_paused_current(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("current", "pause", "--root", str(self.root), "--reason", "User asked to pause work")
        (self.root / ".idea-to-code" / "current.json").unlink()

        self.run_bundle("current", "resume", "--root", str(self.root), "--slug", slug, "--reason", "Known slug resume after restart")

        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], slug)
        self.assertEqual(status["state"], "in_progress")
        self.assertEqual(status["phase"], "in_progress")
        self.assertEqual(status["current_focus"], "RESUMED: Known slug resume after restart")

    def test_current_resume_with_slug_restores_lost_in_progress_current(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        (self.root / ".idea-to-code" / "current.json").unlink()

        self.run_bundle("current", "resume", "--root", str(self.root), "--slug", slug, "--reason", "Known slug resume after restart")

        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], slug)
        self.assertEqual(status["state"], "in_progress")
        self.assertEqual(status["phase"], "ready_to_implement")

    def test_current_resume_with_slug_rejects_missing_slug(self) -> None:
        result = self.run_bundle(
            "current", "resume",
            "--root", str(self.root),
            "--slug", "missing-task",
            "--reason", "Known slug resume after restart",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Bundle does not exist", result.stderr)

    def test_current_resume_with_slug_rejects_conflicting_unfinished_current(self) -> None:
        active = self.init_bundle()
        self.run_bundle("init", "--root", str(self.root), "--slug", "other", "--title", "Other task", "--idea", "Other behavior", "--no-current")

        result = self.run_bundle(
            "current", "resume",
            "--root", str(self.root),
            "--slug", "other",
            "--reason", "Known slug resume after restart",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot switch current from unfinished bundle", result.stderr)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], active)

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

    def test_closer_accepts_prior_role_evidence_current_phrase(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)

        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "closer",
            "--evidence", "Pre-close verify passed; prior role evidence is current; REQ-1 covered by Sample milestone; final decision pass accepted",
            "--covers", "REQ-1",
        )

        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        latest = status["role_evidence"]["closer"][-1]
        self.assertIn("prior role evidence is current", latest["evidence"])

    def test_closer_rejects_other_role_work_claims(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)

        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "closer",
            "--evidence", "Pre-close verify passed; reviewer reviewed REQ-1 scope; REQ-1 covered; final decision pass accepted",
            "--covers", "REQ-1",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Closer evidence must describe closeout work", result.stderr)

    def test_current_resume_with_slug_rejects_completed_bundle(self) -> None:
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

        result = self.run_bundle(
            "current", "resume",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Known slug resume after restart",
            check=False,
        )
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

    def test_route_blocks_product_edits_when_implementation_ready_is_false(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        replacement = (self.root / ".idea-to-code" / slug / "00-idea.md").read_text(encoding="utf-8") + "\n"
        self.run_bundle(
            "update",
            "--root", str(self.root),
            "--slug", slug,
            "--file", "requirements",
            "--content", replacement,
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status["implementation_ready"])
        self.assertFalse(status["pending_plan_update"])

        result = self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["route_gate"], "implementation-ready-required")
        self.assertFalse(payload["can_edit_product_files"])
        self.assertFalse(payload["must_update_plan_before_code"])
        self.assertTrue(any("implementation ready" in command for command in payload["required_next_commands"]))
        self.assertIn("Implementation gate is not READY", payload["next_action"])

    def test_route_blocks_product_edits_when_gate_problems_exist_despite_ready_flag(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        idea_path = self.root / ".idea-to-code" / slug / "00-idea.md"
        broken = idea_path.read_text(encoding="utf-8").replace("## Controlled Exploration", "## Removed Exploration", 1)
        idea_path.write_text(broken, encoding="utf-8")
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["implementation_ready"])

        result = self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["route_gate"], "implementation-ready-required")
        self.assertFalse(payload["can_edit_product_files"])
        self.assertTrue(payload["active_bundle"]["implementation_gate_problems"])
        self.assertIn("Implementation gate is not READY", payload["next_action"])

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

    def test_unblock_refuses_bundle_without_unresolved_blocker(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle(
            "unblock",
            "--root", str(self.root),
            "--slug", slug,
            "--note", "Nothing to resolve",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no unresolved blocker", result.stderr)

    def test_blocked_bundle_rejects_mutating_commands_until_unblock(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing API key",
            "--need", "Provide API key",
        )

        blocked_again = self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing fixture",
            "--need", "Provide fixture",
        )
        self.assertEqual(blocked_again.returncode, 0)
        blocked_status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(len([block for block in blocked_status["blocks"] if "resolved_at_utc" not in block]), 2)

        for command in [
            ("requirement", "add", "--id", "REQ-2", "--description", "Blocked mutation", "--type", "constraint"),
            ("update", "--file", "idea", "--content", "Blocked mutation"),
            ("checkpoint", "--milestone", "Blocked", "--delivered", "blocked", "--verified", "source-only blocked", "--next", "unblock", "--focus", "blocked", "--gate", "blocked", "--gate-status", "pass", "--covers", "REQ-1"),
            ("role", "record", "--role", "planner", "--evidence", "REQ-1 planned while blocked", "--covers", "REQ-1"),
            ("finalize", "--summary", "Blocked", "--verification", "source-only blocked", "--risks", "blocked", "--acceptance", "REQ-1 blocked", "--gate-status", "pass", "--decision", "accepted"),
        ]:
            result = self.run_bundle(
                *command,
                "--root", str(self.root),
                "--slug", slug,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, command)
            self.assertIn("Bundle is blocked", result.stderr, command)

        before = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        after = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(before.get("last_verify_ok"), after.get("last_verify_ok"))
        self.assertEqual(before.get("last_verified_event_sequence"), after.get("last_verified_event_sequence"))

    def test_unblock_keeps_bundle_blocked_until_all_blockers_resolve(self) -> None:
        slug = self.init_bundle()
        self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing API key",
            "--need", "Provide API key",
        )
        self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing fixture",
            "--need", "Provide fixture",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "blocked")
        route = json.loads(self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation").stdout)
        self.assertEqual(route["route_gate"], "unblock-required")
        self.assertFalse(route["can_edit_product_files"])

        self.run_bundle(
            "unblock",
            "--root", str(self.root),
            "--slug", slug,
            "--note", "Fixture provided",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "blocked")
        self.assertNotIn("resolved_at_utc", status["blocks"][0])
        self.assertIn("resolved_at_utc", status["blocks"][1])
        route = json.loads(self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation").stdout)
        self.assertEqual(route["route_gate"], "unblock-required")
        self.assertTrue(route["requires_unblock"])

    def test_unblock_clears_single_blocker_and_restores_route(self) -> None:
        slug = self.init_bundle()
        self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing API key",
            "--need", "Provide API key",
        )
        self.run_bundle(
            "unblock",
            "--root", str(self.root),
            "--slug", slug,
            "--note", "API key provided",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "in_progress")
        self.assertTrue(all("resolved_at_utc" in block for block in status["blocks"]))
        route = json.loads(self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation").stdout)
        self.assertNotEqual(route["route_gate"], "unblock-required")
        self.assertFalse(route["requires_unblock"])

    def test_resume_paused_blocked_bundle_preserves_unblock_gate(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing API key",
            "--need", "Provide API key",
        )
        self.run_bundle("current", "pause", "--root", str(self.root), "--reason", "Pause while waiting")
        self.run_bundle("current", "resume", "--root", str(self.root), "--reason", "Resume review")
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "blocked")
        route = json.loads(self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation").stdout)
        self.assertEqual(route["route_gate"], "unblock-required")
        self.assertTrue(route["requires_unblock"])
        self.assertFalse(route["can_edit_product_files"])

    def test_blocked_new_task_route_required_commands_are_executable(self) -> None:
        slug = self.init_bundle()
        self.run_bundle(
            "block",
            "--root", str(self.root),
            "--slug", slug,
            "--reason", "Missing API key",
            "--need", "Provide API key",
        )
        route = json.loads(self.run_bundle("route", "--root", str(self.root), "--input", "Start a new unrelated task instead").stdout)
        self.assertEqual(route["route_gate"], "archive-current-first")
        self.assertFalse(route["requires_unblock"])
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User chose to start a new unrelated task instead.",
            "--classification", "new-task",
            "--rationale", "The requested work is unrelated to the blocked bundle.",
            "--action", "Archive the blocked bundle and initialize the new task.",
            "--changes-plan", "no",
        )
        self.run_bundle("current", "archive", "--root", str(self.root), "--reason", "Park blocked bundle for new task")

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
        requirements = f"""# Requirements

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

## Controlled Exploration

- Exploration Needed: no
- Trigger: Large dogfood fixture has a predefined multi-milestone command path.
- Constraints:
  - Keep the fixture scoped to bundle governance commands.
- Options Considered:
  - Not required for this deterministic dogfood scenario.
- Decision:
  - Chosen option: Use the predefined planning, execution, and acceptance milestones.
  - Decision reason: The scenario is a regression fixture, not an architecture fork.
  - Rejected options: none.
  - Unverified items: none.

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Large dogfood flow validates multi-milestone governance.

## Acceptance Matrix

{TEST_ACCEPTANCE_HEADER}
| REQ-1 | Planning satisfies the requested governance outcome. | Planning evidence covers REQ-1. | Missing planning evidence is rejected. | Production code is outside this fixture. | command path covers planning | missing evidence rejected | temporary root only | state.json records planning coverage | archive preserves state | verify reports failures | verify prints JSON | temporary bundle path only | source-only |
| REQ-2 | Execution satisfies the requested governance outcome. | Execution evidence covers REQ-2. | Missing execution evidence is rejected. | Production code is outside this fixture. | command path covers execution | missing evidence rejected | temporary root only | state.json records execution coverage | archive preserves state | verify reports failures | verify prints JSON | temporary bundle path only | source-only |
| REQ-3 | Acceptance satisfies the requested governance outcome. | Acceptance evidence covers REQ-3. | Missing acceptance evidence is rejected. | Production code is outside this fixture. | command path covers acceptance | missing evidence rejected | temporary root only | state.json records acceptance coverage | archive preserves state | verify reports failures | verify prints JSON | temporary bundle path only | source-only |
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
        output_id = self.run_ready_output(large)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "implementer", "--evidence", f"TASK-1..TASK-4 implemented through state.json 01-progress.md 01-progress.md and 02-report.md records after READY_TASK_OUTPUT_ID {output_id}", "--covers", covers)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "validator", "--evidence", "REQ-1/REQ-2/REQ-3 source-only validation ran idea_to_code_bundle.py verify command flow", "--covers", covers)
        self.run_bundle("role", "record", "--root", str(self.root), "--slug", large, "--role", "reviewer", "--evidence", "same-agent review checked REQ-1/REQ-2/REQ-3 00-idea.md 00-idea.md and 01-progress.md coverage", "--covers", covers)
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
