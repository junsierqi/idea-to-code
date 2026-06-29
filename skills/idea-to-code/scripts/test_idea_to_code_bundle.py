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
WORKFLOW_MD = REFERENCES_DIR / "workflow.md"
ROLES_STATE_MD = REFERENCES_DIR / "roles-and-state.md"
VERIFICATION_MD = REFERENCES_DIR / "verification-and-evidence.md"
CONTROLLED_EXPLORATION_BENCHMARK_MD = REFERENCES_DIR / "controlled-exploration-benchmark.md"
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

    def acquire_lease(self, slug: str, task: str = "TASK-1", files: list[str] | None = None, owner: str = "agent") -> subprocess.CompletedProcess[str]:
        args = ["implementation", "lease", "acquire", "--root", str(self.root), "--slug", slug, "--task", task, "--owner", owner]
        for file_path in files or ["state.json"]:
            args.extend(["--file", file_path])
        return self.run_bundle(*args)

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
            "route/current -> intake gate -> controlled exploration -> Exploration Visibility Gate -> bundle",
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

    def test_historical_bundle_ledgers_are_not_default_context(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text])

        for required in [
            "persistent recovery and audit ledgers",
            "not default repository context",
            "Do not scan every historical bundle",
            "Read a historical bundle only when",
            "current.json` points to that slug",
            "user explicitly asks to resume or inspect that slug",
            "If `current.json` is missing, do not infer context by reading all bundle directories",
        ]:
            self.assertIn(required, combined)

    def test_session_ledger_mode_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        planning_text = (REFERENCES_DIR / "planning-patterns.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, planning_text])

        for required in [
            "a slug is a session ledger",
            "one continuous conversation/cooperation context may contain multiple ideas",
            "IDEA/REQ/TASK units inside the same slug",
            "Same conversation session",
            "new idea in the same session becomes a new IDEA-scoped unit",
            "do not create one slug per user utterance or per idea by default",
            "New chat session or explicitly separate task/session",
            "Follow-up to an earlier idea inside the same session",
            "Related Session",
            "Related IDEA",
            "Use the chat session as the default ledger boundary",
        ]:
            self.assertIn(required, combined)

    def test_session_ledger_simulation_scenarios_are_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        planning_text = (REFERENCES_DIR / "planning-patterns.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, planning_text])

        for required in [
            "Session-Ledger Routing Scenarios",
            "`idea1` plus several clarifications before implementation finishes",
            "Continue same session slug with `clarification` or `expand`",
            "One slug for the session",
            "Same chat: `idea1` completes, then user asks unrelated `idea2`",
            "Continue same session slug and add an IDEA-2 scope",
            "One slug with multiple IDEA scopes",
            "Same chat: user reports a defect in delivered `idea1` after `idea2` completed",
            "add an IDEA-1 follow-up TASK/REQ",
            "Later session: user reports a defect in prior-session `idea1`",
            "Initialize a new session slug and reference the old session/IDEA",
            "New related session slug; old ledger remains historical",
            "multiple old bundles could match",
            "No mutation until scope is clear",
            "User changes wording but stays in the same conversation session",
            "Slug count remains controlled",
            "one stale slug absorbing a different live session",
        ]:
            self.assertIn(required, combined)

    def test_session_ledger_followup_scope_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        planning_text = (REFERENCES_DIR / "planning-patterns.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, planning_text])

        for required in [
            "Follow-up to an earlier idea inside the same session",
            "keep the same session slug",
            "IDEA-1 follow-up",
            "Follow-up to a prior session",
            "start a new session slug",
            "Related Session",
            "Related IDEA",
        ]:
            self.assertIn(required, combined)

    def test_multi_agent_ledger_ownership_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, roles_text])

        for required in [
            "Multi-agent ledger ownership",
            "Same session ledger, parallel agents",
            "disjoint IDEA/TASK/REQ ownership and file/module write boundaries",
            "Different chat sessions, parallel agents",
            "use separate slugs",
            "Validator or Reviewer subagents",
            "Record their evidence under the parent implementation slug",
            "Worker subagents implementing disjoint slices",
            "re-check `.idea-to-code/current.json`",
            "reroute instead of writing to the previously assumed slug",
            "current pointer conflict",
        ]:
            self.assertIn(required, combined)

    def test_session_ledger_status_scope_is_documented(self) -> None:
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        for required in [
            "same visible IDEA/TASK/REQ set",
            "Scope: IDEA-2 / TASK-4 / REQ-7",
            "whenever multiple ideas exist",
            "every IDEA/TASK/REQ in that response's stated scope",
            "does not claim the whole session ledger is finalized",
        ]:
            self.assertIn(required, verification_text)

    def test_session_ledger_does_not_require_session_registry(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL_MD, *sorted(REFERENCES_DIR.glob("*.md"))]
        )
        script_text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Parallel sessions use separate slugs", combined)
        self.assertNotIn(".idea-to-code/sessions/", combined)
        self.assertNotIn("/claims/", combined)
        self.assertNotIn("separate delivery scope", script_text)

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

    def test_exploration_visibility_gate_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        planning_text = (REFERENCES_DIR / "planning-patterns.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, planning_text, verification_text, roles_text])

        for required in [
            "Exploration Visibility Gate",
            "EXPLORATION_OUTPUT_ID",
            "exploration render",
            "Exploration Result",
            "Confirmation Required",
            "Selected Approach",
            "Why This Approach",
            "Implementation Will Proceed To",
            "Planned Scope",
            "Required Now",
            "What READY Will Cover",
            "Decision Options",
            "Display Layer",
            "Next Layer",
            "READY Focus",
            "Full Plan",
            "Recommended Option",
            "explore more: <direction>",
            "before READY",
            "visible Exploration Visibility Gate output and READY excerpt",
            "missing Exploration Visibility Gate output",
            "future extension",
            "grouped or summarized READY",
            "focused READY excerpts",
        ]:
            self.assertIn(required, combined)

    def test_exploration_revision_rule_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        planning_text = (REFERENCES_DIR / "planning-patterns.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, planning_text, verification_text])

        for required in [
            "Exploration Revision Rule",
            "Exploration Revision Pattern",
            "Required Now",
            "Deferred",
            "Rejected Options",
            "New / Selected Option",
            "What READY Will Cover",
            "Generate a new `EXPLORATION_OUTPUT_ID`",
            "direction is not automatically Option 3",
            "keep `Confirmation Required`",
            "do not silently promote the direction to a selected route",
            "Deferred items must not appear in READY",
            "rejected options must not remain the default route",
        ]:
            self.assertIn(required, combined)

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
            "EXPLORATION_OUTPUT_ID",
            "run the read-only render helper before writing the response whenever the helper is available",
            "If `render-status` is unavailable or fails, state that reason",
            "Formal tracked status MUST use render-status generated fields when the helper is available",
            "do not remove fixed fields",
            "rename them, reorder them, or hand-invent them",
            "do not drop TASK/REQ mapping from `Changes`, `Completed Items`, `Incomplete Items`, or `Validation Results`",
            "do not drop IDEA/TASK/REQ mapping when multiple ideas exist in the session ledger",
            "do not move no-commit state into `Incomplete Items`",
            "must name the relevant `TASK-*` and `REQ-*` IDs",
            "A formal tracked response that cannot map each result bullet to TASK/REQ",
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

    def test_mixed_response_split_rule_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = VERIFICATION_MD.read_text(encoding="utf-8")
        benchmark = CONTROLLED_EXPLORATION_BENCHMARK_MD.read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text, benchmark])

        for required in [
            "Mixed-response split rule",
            "combines a tracked status check with ordinary review",
            "do not let the fixed field contract swallow the whole answer",
            "Answer the tracked status part first in one concise status sentence",
            "Then answer the review or discussion part naturally in the user's language",
            "Current strengths",
            "Current gaps",
            "Suggested TODO",
            "Do not introduce a second fixed response template",
            "Mixed tracked status plus ordinary review/evaluation",
            "Response Scenario P: Mixed Status And Review Split",
            "mixed-status-review",
            "硬化规则都做完了吗",
            "我们现在 skill 有什么缺的",
            "有什么优点",
            "Does not paste the full fixed field contract",
            "`TASK-*`",
            "`REQ-*`",
            "`render-status`",
            "`No commit made`",
        ]:
            self.assertIn(required, combined)

    def test_review_discovered_todo_capture_rule_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = ROLES_STATE_MD.read_text(encoding="utf-8")
        verification_text = VERIFICATION_MD.read_text(encoding="utf-8")
        benchmark = CONTROLLED_EXPLORATION_BENCHMARK_MD.read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, verification_text, benchmark])

        for required in [
            "Review-discovered TODO capture rule",
            "when a review, weakness list, architecture assessment, or mixed-response review identifies a `new gap`",
            "state whether that gap should enter TODO/REQ/backlog, be deferred, or be rejected",
            "Do not silently drop a `new gap`",
            "do not describe it as completed unless a TASK/REQ with validation evidence already covers it",
            "convert accepted TODO candidates into tracked REQ/TASK scope before editing",
            "Reviewer output captures every review-discovered `new gap` as a TODO candidate, deferred item, or rejected item",
            "must not mention a `new gap` once and then drop it from follow-up planning",
            "suggested TODO, a proposed REQ/TASK for the next bundle, deferred, or rejected",
            "Any `new gap` in the review section is followed by an explicit suggested TODO",
            "Does not claim a review-discovered `new gap` is completed without tracked TASK/REQ and validation evidence",
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
        exploration_match = re.search(r"EXPLORATION_OUTPUT_ID:\s*(\S+)", result.stdout)
        self.assertIsNotNone(exploration_match)
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
            "EXPLORATION_OUTPUT_ID:",
            exploration_match.group(1),
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
            "Current TASK loop",
            "Overview loop",
            "Status semantics",
            "Small-task friction",
            "Fresh-session score: `0-9` per output",
            ">= 54/63",
            "Time and cost bounds",
            "Default run uses exactly seven prompts",
            "Maximum wall-clock budget is 45 minutes",
            "Stop early",
            "Elapsed time",
            "Prompt count",
            "FS-6",
            "FS-7",
            "Current TASK Entry",
            "Read-Only Overview",
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
            "does not skip exploration and task-list visibility",
            "before any product-file edit",
            "`implementation ready` prints the generated",
            "EXPLORATION_OUTPUT_ID",
            "READY_TASK_OUTPUT_ID",
            "[idea-to-code][Planner/agent] Implementation Gate: READY",
            "Files",
            "Execution Details",
            "Done Criteria",
            "Planned Verification",
            "transparency, not an approval request",
            "Command stdout, tool output, or a folded transcript is not enough by itself",
            "Tool stdout or folded command transcripts are not enough for READY visibility",
            "send a normal assistant message",
            "Exploration Visibility Check",
            "Plan-level READY",
            "Execution-level READY",
            "For multi-task work, default the user-visible execution message to the current TASK",
            "not the entire long task list",
            "Every current TASK transition needs visible task info for that TASK",
            "focused READY TASK excerpt",
            "--task TASK-N",
            "Focused READY output is for user visibility only",
            "hard contract",
            "covered REQ hint",
            "covered `REQ-*`",
            "If any of those fields are missing, the READY output is invalid",
            "same visible Exploration Visibility Gate output plus TASK/REQ set",
            "Before moving from TASK-1 to TASK-2, show the TASK-2 focused READY excerpt",
            "each result bullet maps to the focused execution-level READY excerpt shown before that TASK",
            "must not introduce unshown or unmapped work",
            "Before product-file edits, the READY task list must be visible to the user in a normal assistant message",
            "Implementer evidence must cite the generated READY output id",
            "Use `implementation show-ready` to reprint or refresh",
            "Use `quickstart --json` only for automation",
        ]:
            self.assertIn(required, combined)

    def test_tracked_work_compliance_checklist_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, roles_text, verification_text, benchmark_text])

        for required in [
            "Tracked Work Compliance Checklist",
            "mandatory, not style preferences",
            "Rule loading",
            "must read `SKILL.md` as the behavior authority",
            "Do not rely on partial snippets, old chat memory, or historical bundle ledgers",
            "Non-bypassable pre-edit self-check",
            "immediately before calling any file-editing tool for tracked work",
            "the focused READY TASK excerpt for the exact TASK/REQ and files about to be edited",
            "If that visible excerpt is missing, do not edit",
            "Before any tracked repository or artifact edit",
            "implementation show-ready --task <TASK-ID>",
            "paste the relevant READY TASK excerpt in a normal assistant message",
            "code, docs, tests, config, scripts, and tracked bundle artifacts",
            "Reusing a prior READY result still requires showing the relevant excerpt again",
            "Tool stdout, folded transcripts, and internal notes do not satisfy this requirement",
            "Late READY rule",
            "printing READY after edits have already started is remediation only",
            "does not make earlier edits compliant",
            "Action boundary for this checklist",
            "`tracked-edit`",
            "`plan-correction`",
            "`read-only-status`",
            "`ordinary-answer`",
            "`formal-tracked-handoff`",
            "do not run pre-edit READY because no edit is starting",
            "do not run READY only for the answer",
            "Before final tracked handoff",
            "install, validation, commit, delivery, blocked, review, keep/revise/rollback, or final status",
            "run `render-status` first",
            "If `render-status` is unavailable or fails, state that reason",
            "Mapping rule",
            "must map to the visible Exploration Visibility Gate output and READY TASK/REQ excerpt",
            "Stable enumeration traceability rule",
            "Same-session continuity rule",
            "Master backlog rule",
            "record them as stable master backlog IDs such as `MB-1..MB-N` before implementation",
            "run `backlog sync`",
            "do not claim \"all done\" while any MB item is pending, active, blocked, or uncovered",
            "`multi-issue-master-backlog`",
            "within one conversation session, related ideas, corrections, numbered lists, scope decisions, and completion claims must remain traceable and consistent across turns",
            "`related-session-follow-up`",
            "First audit the related scope and state whether it is `same scope`, `scope correction`, `new related scope`, or `unrelated ordinary answer`",
            "Unrelated questions may stay ordinary concise answers",
            "numbered issue lists are stable scope IDs",
            "Previous ID",
            "Current ID",
            "Change Reason",
            "Do not create a fresh unrelated 1-7 list",
            "`enumerated-scope-reference`",
            "Preserves the meaning of prior numbered issue lists",
            "Noncompliance rule",
            "say so plainly, correct the process",
            "Multi-role regression rule",
            "Planner, Implementer, Validator, Reviewer, and Closer expectations",
            "ordinary untracked explanations, naming discussions, or lightweight commentary updates",
            "Command stdout, folded transcript output, internal notes, or a READY message printed after edits have already started are not compliant",
        ]:
            self.assertIn(required, combined)

    def test_multi_role_output_compliance_scenario_is_documented(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        workflow_text = (REFERENCES_DIR / "workflow.md").read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        benchmark_text = (REFERENCES_DIR / "controlled-exploration-benchmark.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, roles_text, verification_text, benchmark_text])

        for required in [
            "multi-role output compliance scenario",
            "Output Compliance Testing",
            "references/roles-and-state.md#multi-role-output-compliance",
            "agents may read `.idea-to-code/current.json` to identify the active slug",
            "must not treat the active slug directory, historical slug directories",
            "Read a slug directory only when the user explicitly asks to inspect or resume it",
            "evidence files are not default context and are not regression-test inputs",
            "Workflow owns the lifecycle trigger and context boundary",
            "roles-and-state.md` owns the role-by-role expectations",
            "Branch closure checks for output compliance",
            "Tracked edit branch",
            "Same-session continuity branch",
            "Master backlog branch",
            "Plan-correction branch",
            "Read-only status branch",
            "Ordinary-answer branch",
            "Formal tracked handoff branch",
            "Noncompliance branch",
            "Multi-Role Output Compliance",
            "This section owns the role-by-role output matrix",
            "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle:",
            "tracked repository or artifact edits",
            "code, docs, tests, config, scripts, and tracked bundle artifacts",
            "Exploration Visibility Gate output",
            "Validator output names validation type, command/evidence, and covered TASK/REQ IDs",
            "Reviewer output flags missing Exploration Visibility Gate output, missing READY visibility, late READY remediation, or missing fixed final status fields as noncompliance",
            "Planner output preserves user-provided or agent-created numbered issue lists as stable scope IDs",
            "Planner output preserves same-session continuity",
            "Planner output creates and syncs a master backlog for multi-issue related work before READY",
            "Reviewer output flags missing, stale, or incomplete master backlog coverage when a multi-issue request is reported as complete",
            "Master backlog control",
            "Reviewer output flags same-session drift, failure to audit related prior scope, or treating a related correction as an unrelated ordinary answer as continuity noncompliance",
            "same-session continuity",
            "For same-session related follow-ups, final or status responses must also map back to the prior related session scope",
            "Reviewer output flags unstable numbering, unmapped renumbering, or a second unrelated same-number list as traceability noncompliance",
            "stable enumeration traceability",
            "Do not claim \"1-7 completed\", \"item 3 fixed\", or similar status unless the response maps to the same numbered meanings",
            "runs `render-status` first",
            "Over-templates ordinary untracked replies",
            "must fail if it adds READY output, `render-status`, or fixed status fields",
            "Require every role simulation or subagent to read installed `SKILL.md` as the behavior authority",
            "then read only the relevant referenced files",
            "Ask separate role simulations or subagents to inspect the installed guidance without editing files",
            "Record exact drift, not guessed causes",
            "If any role fails, revise guidance or tests before claiming output compliance",
            "evidence files are not default context and are not regression-test inputs",
        ]:
            self.assertIn(required, combined)

    def test_multi_task_ready_visibility_defaults_to_current_task_pairing(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, verification_text])

        for required in [
            "READY visibility has two layers",
            "`Plan-level READY`: the complete TASK list remains in `00-idea.md`",
            "use `implementation ready --full-plan` or `implementation show-ready --full-plan`",
            "`Execution-level READY`: the current TASK excerpt is shown immediately before that TASK is executed",
            "For multi-task work, default user-visible execution display to the current TASK's focused READY excerpt",
            "`implementation ready` and `implementation show-ready` default to the first TASK/IMP focused excerpt",
            "before moving from one TASK to the next, show the next TASK's focused READY excerpt",
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

    def test_multi_role_output_compliance_requires_render_status_mapping(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, verification_text])

        for required in [
            "run the read-only render helper before writing the response whenever the helper is available",
            "If `render-status` is unavailable or fails, state that reason",
            "Closer formal tracked status fails compliance",
            "omits any fixed field",
            "`Changes`, `Completed Items`, `Incomplete Items`, `Validation Results`, `Unverified Items`, `Residual Risks`, or `Key Technical Details`",
            "drops TASK/REQ mapping from `Changes`, `Completed Items`, `Incomplete Items`, or `Validation Results`",
            "puts `No commit made` under `Incomplete Items`",
            "hand-writes a formal tracked handoff without first using `render-status` when it is available",
            "Do not use it for ordinary untracked answers",
            "The boundary is semantic",
            "do not add READY, `render-status`, or fixed fields just because a bundle exists",
            "The ordinary-answer role check is explicit",
        ]:
            self.assertIn(required, combined)

    def test_multi_role_output_compliance_requires_render_status_fields_and_mapping(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        roles_text = (REFERENCES_DIR / "roles-and-state.md").read_text(encoding="utf-8")
        verification_text = (REFERENCES_DIR / "verification-and-evidence.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, roles_text, verification_text])

        for required in [
            "Planner output shows `[idea-to-code][Planner/agent] Exploration Result | Bundle: <slug>`",
            "Confirmation Required | Bundle: <slug>",
            "Display Layer",
            "Next Layer",
            "Every current TASK transition needs visible task info for that TASK",
            "Implementer output does not start tracked repository or artifact edits until the visible Exploration Visibility Gate output and READY excerpt have appeared",
            "Reviewer output flags missing Exploration Visibility Gate output",
            "Formal tracked status MUST use render-status generated fields when `render-status` is available",
            "Formal tracked status MUST use render-status generated fields when the helper is available",
            "must not omit, rename, reorder, or hand-invent the fixed field set",
            "do not omit, rename, reorder, or hand-invent the fixed field set",
            "do not remove fixed fields, rename them, reorder them, or hand-invent them",
            "omits any fixed field",
            "drops TASK/REQ mapping from `Changes`, `Completed Items`, `Incomplete Items`, or `Validation Results`",
            "drops IDEA/TASK/REQ mapping when multiple ideas exist in the session ledger",
            "When the session ledger contains multiple ideas",
            "A formal tracked response that cannot map each result bullet to TASK/REQ",
            "IDEA/TASK/REQ for multi-idea session ledgers",
            "is noncompliant and must be regenerated from `render-status` or corrected before sending",
            "Do not use it for ordinary untracked answers",
            "must fail if it adds READY output, `render-status`, or fixed status fields",
        ]:
            self.assertIn(required, combined)

    def test_multi_role_output_compliance_simulation_covers_exploration_gate(self) -> None:
        outputs = {
            "planner": (
                "[idea-to-code][Planner/agent] Exploration Result | Bundle: sample\n"
                "EXPLORATION_OUTPUT_ID: sample-explore-r1-20260101000000\n"
                "Selected Approach:\n- Direct path.\n\n"
                "[idea-to-code][Planner/agent] Implementation Gate: READY | Bundle: sample\n"
                "READY_TASK_OUTPUT_ID: sample-r1-20260101000001\n"
                "EXPLORATION_OUTPUT_ID: sample-explore-r1-20260101000000\n"
                "TASK-1: Update sample behavior\nCovered REQ hint: REQ-1\nFiles:\n- sample.py\n"
                "Done Criteria:\n- behavior updated\nPlanned Verification:\n- source-only unittest"
            ),
            "implementer": (
                "[idea-to-code][Implementer/agent] TASK-1 / REQ-1 editing starts only after "
                "EXPLORATION_OUTPUT_ID sample-explore-r1-20260101000000 and READY_TASK_OUTPUT_ID sample-r1-20260101000001 were visible."
            ),
            "validator": (
                "[idea-to-code][Validator/agent] TASK-1 / REQ-1 source-only validation: "
                "python -m unittest passed."
            ),
            "reviewer": (
                "[idea-to-code][Reviewer/agent] same-agent review: checked Exploration Visibility Gate output, "
                "READY visibility, TASK-1 / REQ-1 scope, validation strength, and residual risks."
            ),
            "closer": (
                "[idea-to-code][Closer/agent] Status: Completed\n\n"
                "Changes:\n- TASK-1 / REQ-1: change\n\n"
                "Completed Items:\n- TASK-1 / REQ-1: complete\n\n"
                "Incomplete Items:\n- none\n\n"
                "Validation Results:\n- TASK-1 / REQ-1: source-only unittest passed\n\n"
                "Unverified Items:\n- none\n\nResidual Risks:\n- none\n\n"
                "Key Technical Details:\n- EXPLORATION_OUTPUT_ID: sample-explore-r1-20260101000000\n"
                "- READY_TASK_OUTPUT_ID: sample-r1-20260101000001\n- No commit made"
            ),
            "ordinary": (
                "[idea-to-code][Planner/agent] Controlled Exploration means the planner briefly evaluates "
                "whether a real fork exists and then chooses a path."
            ),
        }

        self.assertIn("Exploration Result", outputs["planner"])
        self.assertIn("Implementation Gate: READY", outputs["planner"])
        self.assertLess(outputs["planner"].index("Exploration Result"), outputs["planner"].index("Implementation Gate: READY"))
        self.assertIn("EXPLORATION_OUTPUT_ID sample-explore-r1-20260101000000", outputs["implementer"])
        self.assertIn("READY_TASK_OUTPUT_ID sample-r1-20260101000001", outputs["implementer"])
        self.assertIn("source-only", outputs["validator"])
        self.assertIn("TASK-1 / REQ-1", outputs["validator"])
        self.assertIn("checked Exploration Visibility Gate output", outputs["reviewer"])
        for field in [
            "Changes:",
            "Completed Items:",
            "Incomplete Items:",
            "Validation Results:",
            "Unverified Items:",
            "Residual Risks:",
            "Key Technical Details:",
        ]:
            self.assertIn(field, outputs["closer"])
        self.assertIn("EXPLORATION_OUTPUT_ID:", outputs["closer"])
        self.assertNotIn("Implementation Gate: READY", outputs["ordinary"])
        self.assertNotIn("Changes:", outputs["ordinary"])

    def test_exploration_revision_simulation_keeps_directional_feedback_in_confirmation(self) -> None:
        revised_output = (
            "[idea-to-code][Planner/agent] Confirmation Required | Bundle: sample\n"
            "EXPLORATION_OUTPUT_ID: sample-explore-r2-20260101000002\n\n"
            "Exploration Revision:\n"
            "- Required Now: A, C\n"
            "- Deferred: B\n"
            "- Rejected Options: Option 1, Option 2\n"
            "- New / Selected Option: direction only - more options needed\n"
            "- What READY Will Cover: no READY until a revised option is approved\n\n"
            "Decision Options:\n"
            "- Option 3A: route derived from the requested direction\n"
            "- Option 3B: narrower route derived from the requested direction\n\n"
            "Recommended Option:\n"
            "- Option 3A\n\n"
            "Please reply with one of:\n"
            "- approve\n"
            "- choose: <option>\n"
            "- change: <correction>\n"
            "- explore more: <direction>\n"
            "- pause\n"
            "- cancel\n"
        )

        self.assertIn("Confirmation Required", revised_output)
        self.assertIn("EXPLORATION_OUTPUT_ID: sample-explore-r2-20260101000002", revised_output)
        self.assertIn("Required Now: A, C", revised_output)
        self.assertIn("Deferred: B", revised_output)
        self.assertIn("Rejected Options: Option 1, Option 2", revised_output)
        self.assertIn("direction only - more options needed", revised_output)
        self.assertIn("no READY until a revised option is approved", revised_output)
        self.assertIn("explore more: <direction>", revised_output)
        self.assertNotIn("Implementation Gate: READY", revised_output)

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

    def test_control_hardening_goal_and_closure_rules_are_documented(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        workflow = WORKFLOW_MD.read_text(encoding="utf-8")
        roles = ROLES_STATE_MD.read_text(encoding="utf-8")
        verification = VERIFICATION_MD.read_text(encoding="utf-8")
        benchmark = CONTROLLED_EXPLORATION_BENCHMARK_MD.read_text(encoding="utf-8")

        for text in (skill, workflow, roles, verification):
            self.assertIn("intelligent, controllable", text)
        self.assertIn("use idea-to-code to improve idea-to-code", skill)
        self.assertIn("delegation resolve", skill)
        self.assertIn("delegation resolve", verification)
        self.assertIn("delegation resolve", benchmark)
        self.assertIn("every tracked implementation edit", workflow)
        self.assertIn("finalize closes any remaining active leases", workflow)
        self.assertIn("Negated disclosures", roles)

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
- Planned Scope:
  - Required Now: TASK-1 / REQ-1 source-only bundle command flow.
  - Deferred: Production code changes and unrelated command behavior.
  - What READY Will Cover: TASK-1 / REQ-1 only.
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

    def write_master_backlog_bundle(self, slug: str) -> None:
        requirements = f"""# Requirements

- Target outcome: Master backlog fixture is tracked.
- Primary user: Maintainer.
- Main flow: Sync MB-1 and MB-2 before implementation.
- Success criteria: MB coverage is visible.
- Non-goals: Production changes.
- Constraints: Keep MB IDs stable.
- Unknowns: no open unknowns.

## Intake Gate

- Understanding: Multi-issue work needs a persisted master backlog.
- Assumptions: Fixture uses two MB items.
- Acceptance Criteria: MB-1 and MB-2 stay visible.
- Need Confirmation: no
- Confirmation Reason: Deterministic test fixture.

## Controlled Exploration

- Exploration Needed: no
- Trigger: Test fixture has a direct master backlog implementation path.
- Constraints:
  - Preserve MB-1 and MB-2.
- Planned Scope:
  - Required Now: TASK-1 / REQ-1 / MB-1 only.
  - Deferred: MB-2 pending for a later task.
  - What READY Will Cover: TASK-1 / REQ-1 / MB-1.
- Options Considered:
  - Not required for this deterministic test fixture.
- Decision:
  - Chosen option: Use direct master backlog fixture.
  - Decision reason: No behavior fork is needed.
  - Rejected options: none.
  - Unverified items: MB-2 remains pending.

## Task Classification

- File changes: yes
- Semantic impact: yes
- Tracking required: yes
- Reason: Behavior-changing tracked test flow.

## Acceptance Matrix

{TEST_ACCEPTANCE_HEADER}
| REQ-1 / MB-1 | MB-1 is tracked in state. | MB-1 becomes covered after checkpoint. | Missing MB state must not be accepted. | MB-2 is outside TASK-1. | command exits zero | missing sync reports a failure | two MB IDs stay stable | state.json records master backlog | no rollback state is created | stderr reports command failures | status prints JSON output | temporary script path only | source-only |
| REQ-2 / MB-2 | MB-2 remains visible as pending. | render-status lists MB-2 incomplete. | MB-2 is silently dropped. | TASK-1 does not implement MB-2. | command exits zero | missing pending item is a failure | pending item remains visible | state.json records pending item | no rollback state is created | stderr reports command failures | status prints JSON output | temporary script path only | source-only |
"""
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Cover MB-1 only

Status: pending

Files:
- state.json

Execution Details:
- Sync master backlog and cover MB-1.

Done Criteria:
- MB-1 is covered and MB-2 remains pending.

Planned Verification:
- source-only backlog status and render-status checks.
"""
        verification = """# Verification

Validation types: real-product-path, mock-only, fixture-only, source-only, dom-only, manual-inspection, unverified.

## Coverage Expectations

- Build: not required for fixture.
- Unit/Integration: source-only bundle command flow.
- End-to-end flow: sync to render-status.
- Remaining gaps: MB-2 remains pending.

## Verification History

- REQ-1: source-only master backlog command flow.
"""
        req_path = self.root / "mb-requirements.md"
        impl_path = self.root / "mb-implementation.md"
        ver_path = self.root / "mb-verification.md"
        req_path.write_text(requirements, encoding="utf-8")
        impl_path.write_text(implementation, encoding="utf-8")
        ver_path.write_text(verification, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "requirements", "--content-file", str(req_path))
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "verification", "--content-file", str(ver_path))
        self.run_bundle("requirement", "add", "--root", str(self.root), "--slug", slug, "--id", "REQ-1", "--description", "MB-1 master backlog item is covered", "--type", "functional")
        self.run_bundle("requirement", "add", "--root", str(self.root), "--slug", slug, "--id", "REQ-2", "--description", "MB-2 remains pending and visible", "--type", "functional")

    def run_ready_output(self, slug: str) -> str:
        result = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        match = re.search(r"READY_TASK_OUTPUT_ID:\s*(\S+)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        return match.group(1)

    def run_exploration_output(self, slug: str) -> str:
        result = self.run_bundle("exploration", "render", "--root", str(self.root), "--slug", slug)
        match = re.search(r"EXPLORATION_OUTPUT_ID:\s*(\S+)", result.stdout)
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
- Planned Scope:
  - Required Now: TASK-1 negative verification fixture.
  - Deferred: Production code changes and unrelated behavior.
  - What READY Will Cover: TASK-1 only.
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
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        pre_edit_suffix = f"; PRE_EDIT_OK_ID {status['pre_edit_ok_id']}" if status.get("pre_edit_ok_id") else ""
        self.run_bundle(
            "role", "record", "--root", str(self.root), "--slug", slug,
            "--role", "implementer",
            "--evidence", f"TASK-1 implemented through state.json bundle records for REQ-1 after READY_TASK_OUTPUT_ID {output_id}{pre_edit_suffix}",
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

    def test_finalize_releases_active_implementation_leases(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        acquired = self.acquire_lease(slug)
        lease_id = re.search(r"LEASE_ID: (\S+)", acquired.stdout).group(1)
        self.run_bundle("implementation", "pre-edit", "--root", str(self.root), "--slug", slug, "--task", "TASK-1", "--file", "state.json")
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.record_closer(slug)

        self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation complete", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted")

        status = self.run_bundle("implementation", "lease", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["active"], [])
        leases = {lease["id"]: lease for lease in payload["implementation_leases"]}
        self.assertIn(lease_id, leases)
        self.assertIn("bundle finalized", leases[lease_id]["release_reason"])

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

    def test_checkpoint_after_verify_invalidates_preclose_verify(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.record_roles_through_reviewer(slug)
        self.checkpoint(slug)
        preclose = self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ok": true', preclose.stdout)
        status_after_verify = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        verified_sequence = status_after_verify["last_verified_event_sequence"]
        self.assertTrue(status_after_verify["last_verify_ok"])

        self.run_bundle(
            "checkpoint",
            "--root", str(self.root),
            "--slug", slug,
            "--milestone", "Post verify milestone",
            "--delivered", "REQ-1 second bundle record created after pre-close verify",
            "--verified", "source-only command flow evidence in 01-progress.md",
            "--next", "rerun verify",
            "--focus", "closing after post verify checkpoint",
            "--gate", "acceptance",
            "--gate-status", "pass",
            "--covers", "REQ-1",
        )
        status_after_checkpoint = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status_after_checkpoint["last_verify_ok"])
        self.assertIsNone(status_after_checkpoint["last_verified_plan_revision"])
        self.assertGreater(status_after_checkpoint["milestones"][-1]["event_sequence"], verified_sequence)

        closer = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "closer",
            "--evidence", "REQ-1 covered by Sample milestone and Post verify milestone; pre-close source-only verify passed; final decision pass accepted",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(closer.returncode, 0)
        self.assertIn("closer evidence refused", closer.stderr)
        finalize = self.run_bundle(
            "finalize",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "Sample implementation complete",
            "--verification", "source-only command flow passed",
            "--risks", "none",
            "--acceptance", "REQ-1 delivered",
            "--gate-status", "pass",
            "--decision", "accepted",
            check=False,
        )
        self.assertNotEqual(finalize.returncode, 0)
        self.assertIn("pre-close verify has not passed", finalize.stderr)

        refreshed = self.run_bundle("verify", "--root", str(self.root), "--slug", slug)
        self.assertIn('"ok": true', refreshed.stdout)
        self.record_closer(slug)
        accepted = self.run_bundle("finalize", "--root", str(self.root), "--slug", slug, "--summary", "Sample implementation complete", "--verification", "source-only command flow passed", "--risks", "none", "--acceptance", "REQ-1 delivered", "--gate-status", "pass", "--decision", "accepted")
        self.assertEqual(accepted.returncode, 0)

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
        replacement = """\n## Controlled Exploration\n\n- Exploration Needed: yes\n- Trigger: Two user-visible approaches need comparison before implementation.\n- Constraints:\n  - Keep scope narrow.\n- Planned Scope:\n  - Required Now: TASK-1 comparison fixture.\n  - Deferred: Production code changes and unrelated behavior.\n  - What READY Will Cover: TASK-1 only after a decision exists.\n- Options Considered:\n  - Option A: Direct command flow.\n    - Hypothesis: The direct path satisfies the fixture.\n    - Fit to user goal: Strong fit for the test fixture.\n    - Cost: Low.\n    - Risk: Low.\n    - Verification path: implementation ready command.\n    - Rejection condition: The command rejects the bundle.\n- Decision:\n  - Chosen option:\n  - Decision reason:\n  - Rejected options:\n  - Unverified items:\n"""
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

    def test_implementation_ready_rejects_missing_structured_planned_scope(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        idea_path = self.root / ".idea-to-code" / slug / "00-idea.md"
        text = idea_path.read_text(encoding="utf-8")
        text = re.sub(
            r"\n- Planned Scope:\n  - Required Now:.*\n  - Deferred:.*\n  - What READY Will Cover:.*\n",
            "\n",
            text,
            count=1,
        )
        idea_path.write_text(text, encoding="utf-8")

        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Controlled Exploration missing structured Planned Scope", result.stderr)

    def test_implementation_ready_accepts_intake_without_confirmation_needed(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("[idea-to-code][Planner/agent] Exploration Result", result.stdout)
        self.assertIn("EXPLORATION_OUTPUT_ID:", result.stdout)
        self.assertIn("Selected Approach:", result.stdout)
        self.assertIn("Implementation Will Proceed To:", result.stdout)
        self.assertIn("[idea-to-code][Planner/agent] Implementation Gate: READY", result.stdout)
        self.assertIn("READY_TASK_OUTPUT_ID:", result.stdout)
        self.assertIn("EXPLORATION_OUTPUT_ID:", result.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", result.stdout)
        self.assertNotIn(str(self.root / ".idea-to-code" / slug), result.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["implementation_ready"])
        self.assertTrue(status["exploration_output_required"])
        self.assertEqual(status["exploration_output_plan_revision"], status["plan_revision"])
        self.assertTrue(status["exploration_output_id"])
        self.assertEqual(status["exploration_output_mode"], "autonomous")
        self.assertTrue(status["ready_task_output_required"])
        self.assertEqual(status["ready_task_output_plan_revision"], status["plan_revision"])
        self.assertTrue(status["ready_task_output_id"])

    def test_exploration_render_outputs_confirmation_required_options(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="yes", mark_ready=False)
        result = self.run_bundle("exploration", "render", "--root", str(self.root), "--slug", slug)
        self.assertIn("[idea-to-code][Planner/agent] Confirmation Required", result.stdout)
        self.assertIn("EXPLORATION_OUTPUT_ID:", result.stdout)
        self.assertIn("Display Layer: Exploration Decision Request", result.stdout)
        self.assertIn("Next Layer: READY Focus", result.stdout)
        self.assertIn("Planned Scope:", result.stdout)
        self.assertIn("Required Now: TASK-1 / REQ-1 source-only bundle command flow.", result.stdout)
        self.assertIn("Deferred: Production code changes and unrelated command behavior.", result.stdout)
        self.assertIn("What READY Will Cover: TASK-1 / REQ-1 only.", result.stdout)
        self.assertIn("Decision Options:", result.stdout)
        self.assertIn("Recommended Option:", result.stdout)
        self.assertIn("Please reply with one of:", result.stdout)
        self.assertIn("explore more: <direction>", result.stdout)
        self.assertNotIn("Implementation Gate: READY", result.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["exploration_output_mode"], "confirmation-required")
        self.assertTrue(status["exploration_output_id"])

    def test_exploration_render_outputs_autonomous_result_without_routine_confirmation(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        result = self.run_bundle("exploration", "render", "--root", str(self.root), "--slug", slug)
        self.assertIn("[idea-to-code][Planner/agent] Exploration Result", result.stdout)
        self.assertIn("Display Layer: Exploration Result", result.stdout)
        self.assertIn("Next Layer: READY Focus", result.stdout)
        self.assertIn("Required Now: TASK-1 / REQ-1 source-only bundle command flow.", result.stdout)
        self.assertIn("Selected Approach:", result.stdout)
        self.assertIn("Why This Approach:", result.stdout)
        self.assertIn("This is not an approval request", result.stdout)
        self.assertNotIn("Please reply with one of:", result.stdout)
        self.assertNotIn("Confirmation Required", result.stdout)

    def test_ready_output_carries_exploration_output_id(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, need_confirmation="no", mark_ready=False)
        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertIn(f"EXPLORATION_OUTPUT_ID: {status['exploration_output_id']}", result.stdout)
        ready_output = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        self.assertIn(f"EXPLORATION_OUTPUT_ID: {status['exploration_output_id']}", ready_output.stdout)

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
            "Display Layer: READY Focus",
            "Current TASK info must be shown before executing that TASK",
            "Focused READY TASK excerpt: yes",
            "This excerpt is for visibility only",
            "Full READY plan remains in 00-idea.md; use --full-plan",
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
        self.assertEqual(after["ready_task_output_scope"], "focused-default")

    def test_implementation_ready_defaults_to_focused_first_task_for_multi_task_bundle(self) -> None:
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

        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("Focused READY TASK excerpt: yes", ready.stdout)
        self.assertIn("Full READY plan remains in 00-idea.md; use --full-plan", ready.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", ready.stdout)
        self.assertNotIn("TASK-2: Verify second task visibility", ready.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["ready_task_output_scope"], "focused-default")

        focused_second = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug, "--task", "TASK-2")
        self.assertIn("TASK-2: Verify second task visibility", focused_second.stdout)
        status_after = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status_after["ready_task_output_id"], status["ready_task_output_id"])
        self.assertEqual(status_after["ready_task_output_scope"], "focused-default")

        full_plan = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug, "--full-plan")
        self.assertIn("Display Layer: Full Plan", full_plan.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", full_plan.stdout)
        self.assertIn("TASK-2: Verify second task visibility", full_plan.stdout)
        status_full = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status_full["ready_task_output_scope"], "full-plan")

    def test_implementation_enter_task_records_current_task_and_prints_ready_focus(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

        result = self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")

        self.assertIn("Display Layer: READY Focus", result.stdout)
        self.assertIn("Current TASK info must be shown before executing that TASK", result.stdout)
        self.assertIn("TASK-1: Verify sample bundle flow", result.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["current_task_id"], "TASK-1")
        self.assertEqual(status["current_task_ready_output_id"], status["ready_task_output_id"])
        self.assertTrue(status["current_task_event_sequence"])

    def test_implementation_overview_reports_scope_current_task_and_full_plan_hint(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")

        result = self.run_bundle("implementation", "overview", "--root", str(self.root), "--slug", slug)

        self.assertIn("Implementation Overview", result.stdout)
        self.assertIn("Display Layer: Overview", result.stdout)
        self.assertIn("Required Now: TASK-1 / REQ-1 source-only bundle command flow.", result.stdout)
        self.assertIn("Current TASK:", result.stdout)
        self.assertIn("TASK-1", result.stdout)
        self.assertIn("Next Tasks:", result.stdout)
        self.assertIn("Full Plan:", result.stdout)
        self.assertIn("--full-plan", result.stdout)

    def test_implementation_pre_edit_records_guard_and_requires_matching_task_files(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        self.acquire_lease(slug)

        result = self.run_bundle(
            "implementation", "pre-edit",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
            "--file", "state.json",
        )

        self.assertIn("[idea-to-code][Implementer/agent] Pre-Edit Guard: OK", result.stdout)
        self.assertIn("Display Layer: Pre-Edit Guard", result.stdout)
        self.assertIn("PRE_EDIT_OK_ID:", result.stdout)
        self.assertIn("Files Approved For Edit:", result.stdout)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["pre_edit_task_id"], "TASK-1")
        self.assertEqual(status["pre_edit_files"], ["state.json"])
        self.assertEqual(status["pre_edit_ready_task_output_id"], status["ready_task_output_id"])

    def test_implementation_pre_edit_rejects_without_write_lease(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")

        result = self.run_bundle(
            "implementation", "pre-edit",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
            "--file", "state.json",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("implementation lease missing for TASK-1 owner agent file(s): state.json", result.stderr)

    def test_implementation_lease_acquire_status_release_and_overlap_refusal(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")

        acquired = self.acquire_lease(slug, owner="agent-a")
        self.assertIn("Implementation Lease: acquired", acquired.stdout)
        lease_id = re.search(r"LEASE_ID: (\S+)", acquired.stdout).group(1)

        conflict = self.run_bundle(
            "implementation", "lease", "acquire",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
            "--owner", "agent-b",
            "--file", "state.json",
            check=False,
        )
        self.assertNotEqual(conflict.returncode, 0)
        self.assertIn("overlapping active lease", conflict.stderr)

        status = self.run_bundle("implementation", "lease", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["active"][0]["id"], lease_id)

        self.run_bundle("implementation", "lease", "release", "--root", str(self.root), "--slug", slug, "--id", lease_id, "--reason", "TASK slice finished")
        reacquired = self.run_bundle(
            "implementation", "lease", "acquire",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
            "--owner", "agent-b",
            "--file", "state.json",
        )
        self.assertIn("Implementation Lease: acquired", reacquired.stdout)

    def test_read_only_role_evidence_does_not_require_write_lease(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        ready_id = re.search(r"READY_TASK_OUTPUT_ID: (\S+)", ready.stdout).group(1)
        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "planner",
            "--covers", "REQ-1",
            "--evidence", f"REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 implementation plan; READY_TASK_OUTPUT_ID {ready_id}",
        )
        state_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(state_path.read_text(encoding="utf-8"))
        status["event_sequence"] = int(status.get("event_sequence") or 0) + 1
        status.setdefault("role_evidence", {}).setdefault("implementer", []).append({
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "event_sequence": status["event_sequence"],
            "role": "implementer",
            "evidence": f"REQ-1 implemented TASK-1 by updating state.json after READY_TASK_OUTPUT_ID {ready_id}; PRE_EDIT_OK_ID fixture-preedit",
            "covers": ["REQ-1"],
            "plan_revision": status["plan_revision"],
        })
        state_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "validator",
            "--covers", "REQ-1",
            "--evidence", "REQ-1 validation type source-only: command inspection checked TASK-1 without write edits",
        )

        self.assertEqual(result.returncode, 0)

    def test_delegation_record_supports_independent_role_claims(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        ready_id = re.search(r"READY_TASK_OUTPUT_ID: (\S+)", ready.stdout).group(1)
        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "planner",
            "--covers", "REQ-1",
            "--evidence", f"REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 implementation plan; READY_TASK_OUTPUT_ID {ready_id}",
        )
        state_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(state_path.read_text(encoding="utf-8"))
        status["event_sequence"] = int(status.get("event_sequence") or 0) + 1
        status.setdefault("role_evidence", {}).setdefault("implementer", []).append({
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "event_sequence": status["event_sequence"],
            "role": "implementer",
            "evidence": f"REQ-1 implemented TASK-1 by updating state.json after READY_TASK_OUTPUT_ID {ready_id}; PRE_EDIT_OK_ID fixture-preedit",
            "covers": ["REQ-1"],
            "plan_revision": status["plan_revision"],
        })
        status["event_sequence"] = int(status.get("event_sequence") or 0) + 1
        status.setdefault("role_evidence", {}).setdefault("validator", []).append({
            "timestamp_utc": "2026-01-01T00:00:01+00:00",
            "event_sequence": status["event_sequence"],
            "role": "validator",
            "evidence": "REQ-1 validation type source-only: command inspection checked TASK-1",
            "covers": ["REQ-1"],
            "plan_revision": status["plan_revision"],
        })
        state_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        refused = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "reviewer",
            "--covers", "REQ-1",
            "--evidence", "REQ-1 independent review checked TASK-1 scope, diff, and residual risk",
            check=False,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("requires a usable delegation record", refused.stderr)

        self.run_bundle(
            "delegation", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "reviewer",
            "--status", "usable",
            "--scope", "TASK-1 scope and diff review",
            "--evidence-summary", "Independent reviewer returned usable scope and risk notes",
            "--agent-id", "agent-123",
        )
        accepted = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "reviewer",
            "--covers", "REQ-1",
            "--evidence", "REQ-1 independent review checked TASK-1 scope, diff, and residual risk",
        )
        self.assertEqual(accepted.returncode, 0)

    def test_unusable_delegation_surfaces_in_status_verify_and_render_status(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle(
            "delegation", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "reviewer",
            "--status", "timeout",
            "--scope", "TASK-1 independent review attempt",
            "--evidence-summary", "Review attempt did not return usable evidence",
            "--agent-id", "agent-timeout",
            "--reason", "subagent timed out before returning evidence",
        )

        status = self.run_bundle("delegation", "status", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(status.returncode, 0)
        self.assertIn("delegation evidence not usable", status.stdout)

        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("delegation evidence not usable", verify.stdout)

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug, "--status", "Progress")
        self.assertIn("Delegation evidence not usable", rendered.stdout)

    def test_delegation_resolve_closes_non_usable_finding_without_making_evidence(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle(
            "delegation", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "reviewer",
            "--status", "timeout",
            "--scope", "TASK-1 independent review attempt",
            "--evidence-summary", "Review attempt did not return usable evidence",
            "--agent-id", "agent-timeout",
            "--reason", "subagent timed out before returning evidence",
        )
        status_before = self.run_bundle("delegation", "status", "--root", str(self.root), "--slug", slug, check=False)
        record_id = json.loads(status_before.stdout)["delegation_records"][0]["id"]

        self.run_bundle(
            "delegation", "resolve",
            "--root", str(self.root),
            "--slug", slug,
            "--id", record_id,
            "--resolution", "fallback-same-agent",
            "--reason", "Recorded timeout is carried as same-agent fallback risk",
        )

        status_after = self.run_bundle("delegation", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status_after.stdout)
        self.assertEqual(payload["open_findings"], [])
        self.assertEqual(payload["problems"], [])
        self.assertEqual(payload["delegation_records"][0]["resolution"], "fallback-same-agent")

    def test_negated_independent_review_disclosure_does_not_require_delegation(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        ready_id = re.search(r"READY_TASK_OUTPUT_ID: (\S+)", ready.stdout).group(1)
        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "planner",
            "--covers", "REQ-1",
            "--evidence", f"REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 implementation plan; READY_TASK_OUTPUT_ID {ready_id}",
        )
        state_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(state_path.read_text(encoding="utf-8"))
        status["event_sequence"] = int(status.get("event_sequence") or 0) + 1
        status.setdefault("role_evidence", {}).setdefault("implementer", []).append({
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "event_sequence": status["event_sequence"],
            "role": "implementer",
            "evidence": f"REQ-1 implemented TASK-1 by updating state.json after READY_TASK_OUTPUT_ID {ready_id}",
            "covers": ["REQ-1"],
            "plan_revision": status["plan_revision"],
        })
        status["event_sequence"] = int(status.get("event_sequence") or 0) + 1
        status.setdefault("role_evidence", {}).setdefault("validator", []).append({
            "timestamp_utc": "2026-01-01T00:00:01+00:00",
            "event_sequence": status["event_sequence"],
            "role": "validator",
            "evidence": "REQ-1 validation type source-only: command inspection checked TASK-1",
            "covers": ["REQ-1"],
            "plan_revision": status["plan_revision"],
        })
        state_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        accepted = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "reviewer",
            "--covers", "REQ-1",
            "--evidence", "REQ-1 same-agent review checked TASK-1 scope and residual risk; independent review not run",
        )

        self.assertEqual(accepted.returncode, 0)

    def test_session_audit_status_and_render_status_surface_latest_scope(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

        self.run_bundle(
            "session", "audit",
            "--root", str(self.root),
            "--slug", slug,
            "--relation", "scope-correction",
            "--summary", "User corrected the previous task scope",
            "--prior-scope", "TASK-1 covered the prior implementation plan",
            "--decision", "Revise the plan before claiming completion",
        )

        status = self.run_bundle("session", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["latest"]["relation"], "scope-correction")
        self.assertIn("User corrected", payload["latest"]["summary"])

        implementation_status = self.run_bundle("implementation", "status", "--root", str(self.root), "--slug", slug)
        status_payload = json.loads(implementation_status.stdout)
        self.assertEqual(status_payload["session_continuity_audits"][-1]["relation"], "scope-correction")

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug, "--status", "Progress")
        self.assertIn("Latest session continuity audit: scope-correction", rendered.stdout)

    def test_scope_classify_status_and_render_status_surface_latest_classification(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

        self.run_bundle(
            "scope", "classify",
            "--root", str(self.root),
            "--slug", slug,
            "--classification", "new-related-scope",
            "--summary", "User added a related follow-up request",
            "--rationale", "The message refers to the active bundle but adds a new scope item",
            "--action", "Record classification before changing the implementation plan",
        )

        status = self.run_bundle("scope", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["latest"]["classification"], "new-related-scope")

        implementation_status = self.run_bundle("implementation", "status", "--root", str(self.root), "--slug", slug)
        status_payload = json.loads(implementation_status.stdout)
        self.assertEqual(status_payload["scope_classifications"][-1]["classification"], "new-related-scope")

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug, "--status", "Progress")
        self.assertIn("Latest scope classification: new-related-scope", rendered.stdout)

    def test_implementation_pre_edit_rejects_without_current_task_entry(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

        result = self.run_bundle(
            "implementation", "pre-edit",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
            "--file", "state.json",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run implementation enter-task --task TASK-1 first", result.stderr)

    def test_implementation_pre_edit_rejects_files_outside_task_scope(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        self.acquire_lease(slug)

        result = self.run_bundle(
            "implementation", "pre-edit",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
            "--file", "README.md",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("file(s) not listed under TASK-1 Files", result.stderr)

    def test_pre_edit_records_history_and_status_exposes_records(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        self.acquire_lease(slug)

        self.run_bundle("implementation", "pre-edit", "--root", str(self.root), "--slug", slug, "--task", "TASK-1", "--file", "state.json")
        self.run_bundle("implementation", "pre-edit", "--root", str(self.root), "--slug", slug, "--task", "TASK-1", "--file", "state.json")

        status = self.run_bundle("implementation", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        self.assertGreaterEqual(len(payload["pre_edit_records"]), 2)
        self.assertEqual(payload["pre_edit_records"][-1]["task_id"], "TASK-1")
        self.assertEqual(payload["pre_edit_records"][-1]["files"], ["state.json"])

    def test_implementer_evidence_refuses_incomplete_pre_edit_file_coverage(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        implementation = """# Implementation

Gate Status: READY

## TASK-1: Verify sample bundle flow

Status: pending

Files:
- state.json
- 01-progress.md

Execution Details:
- Record one requirement and all role evidence.

Done Criteria:
- finalize and verify succeed.

Planned Verification:
- source-only python idea_to_code_bundle.py verify exits zero.
"""
        impl_path = self.root / "implementation-two-files.md"
        impl_path.write_text(implementation, encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        ready_id = re.search(r"READY_TASK_OUTPUT_ID: (\S+)", ready.stdout).group(1)
        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "planner",
            "--covers", "REQ-1",
            "--evidence", f"REQ-1 planned in 00-idea.md with acceptance matrix and TASK-1 implementation plan; READY_TASK_OUTPUT_ID {ready_id}",
        )
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        self.acquire_lease(slug, files=["state.json"])
        pre_edit = self.run_bundle("implementation", "pre-edit", "--root", str(self.root), "--slug", slug, "--task", "TASK-1", "--file", "state.json")
        pre_edit_id = re.search(r"PRE_EDIT_OK_ID: (\S+)", pre_edit.stdout).group(1)

        result = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "implementer",
            "--covers", "REQ-1",
            "--evidence", f"REQ-1 implemented TASK-1 by updating state.json; READY_TASK_OUTPUT_ID {ready_id}; PRE_EDIT_OK_ID {pre_edit_id}",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pre-edit guard missing current records for TASK-1 file(s): 01-progress.md", result.stderr)

    def test_pre_edit_noncompliance_surfaces_in_status_verify_and_render_status(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        self.acquire_lease(slug)
        self.run_bundle("implementation", "pre-edit", "--root", str(self.root), "--slug", slug, "--task", "TASK-1", "--file", "state.json")

        recorded = self.run_bundle(
            "implementation", "noncompliance",
            "--root", str(self.root),
            "--slug", slug,
            "--task", "TASK-1",
            "--reason", "edited file before the visible pre-edit guard",
            "--file", "state.json",
        )
        self.assertIn("Pre-Edit Noncompliance: recorded", recorded.stdout)

        status = self.run_bundle("implementation", "status", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(status.returncode, 0)
        self.assertIn("open pre-edit noncompliance", status.stdout)

        verify = self.run_bundle("verify", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("open pre-edit noncompliance", verify.stdout)

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug, "--status", "Progress")
        self.assertIn("Pre-edit noncompliance open", rendered.stdout)

    def test_master_backlog_sync_records_mb_ids_and_blocks_ready_until_synced(self) -> None:
        slug = self.init_bundle()
        self.write_master_backlog_bundle(slug)

        missing = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("master backlog required but not synced", missing.stderr)

        self.run_bundle("backlog", "sync", "--root", str(self.root), "--slug", slug)
        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("Implementation Gate: READY", ready.stdout)

        status = self.run_bundle("backlog", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        self.assertEqual([item["id"] for item in payload["items"]], ["MB-1", "MB-2"])
        self.assertTrue(payload["items"][0]["title"].startswith("REQ-1 / MB-1 | MB-1 is tracked in state."))
        self.assertEqual([item["id"] for item in payload["incomplete"]], ["MB-1", "MB-2"])

    def test_master_backlog_checkpoint_coverage_and_render_status_keep_pending_visible(self) -> None:
        slug = self.init_bundle()
        self.write_master_backlog_bundle(slug)
        self.run_bundle("backlog", "sync", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)

        self.run_bundle(
            "checkpoint",
            "--root", str(self.root),
            "--slug", slug,
            "--milestone", "Cover MB-1",
            "--delivered", "TASK-1 delivered MB-1 only.",
            "--verified", "source-only backlog status checked.",
            "--next", "MB-2 remains pending.",
            "--focus", "MB-1 covered.",
            "--gate", "continue",
            "--gate-status", "pass",
            "--covers", "REQ-1",
        )

        status = self.run_bundle("backlog", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        states = {item["id"]: item["status"] for item in payload["items"]}
        self.assertEqual(states["MB-1"], "covered")
        self.assertEqual(states["MB-2"], "pending")

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug, "--status", "Completed")
        self.assertIn("Master backlog incomplete: MB-2 (pending)", rendered.stdout)
        self.assertIn("Master backlog: MB-1=covered, MB-2=pending", rendered.stdout)

    def test_idea_record_tracks_same_session_scope_and_updates_by_id(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)

        self.run_bundle(
            "idea", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "IDEA-1",
            "--status", "active",
            "--summary", "Same-session control hardening remains the active product idea.",
            "--related-reqs", "REQ-1",
            "--notes", "Follow-up questions must map back to this recorded idea before implementation claims.",
        )
        self.run_bundle(
            "idea", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "IDEA-1",
            "--status", "completed",
            "--summary", "Same-session control hardening is now represented by state-backed IDEA records.",
            "--related-reqs", "REQ-1",
            "--notes", "The prior active IDEA record is updated instead of creating a disconnected duplicate.",
        )

        status = self.run_bundle("idea", "status", "--root", str(self.root), "--slug", slug)
        payload = json.loads(status.stdout)
        self.assertEqual(len(payload["idea_records"]), 1)
        self.assertEqual(payload["idea_records"][0]["id"], "IDEA-1")
        self.assertEqual(payload["idea_records"][0]["status"], "completed")
        self.assertEqual(payload["idea_records"][0]["related_reqs"], ["REQ-1"])
        self.assertEqual(payload["closed"][0]["id"], "IDEA-1")

        implementation = self.run_bundle("implementation", "status", "--root", str(self.root), "--slug", slug, check=False)
        implementation_payload = json.loads(implementation.stdout)
        self.assertEqual(implementation_payload["idea_records"][0]["id"], "IDEA-1")

    def test_idea_record_rejects_unknown_related_requirement_ids(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)

        result = self.run_bundle(
            "idea", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "IDEA-1",
            "--status", "active",
            "--summary", "Same-session idea record must not point at missing requirements.",
            "--related-reqs", "REQ-404",
            "--notes", "Unknown requirement references would break traceability in later status output.",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown related REQ IDs: REQ-404", result.stderr)

    def test_render_status_uses_latest_milestone_and_idea_scope_when_available(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle(
            "idea", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "IDEA-1",
            "--status", "active",
            "--summary", "Render status should map generated bullets to the active idea.",
            "--related-reqs", "REQ-1",
            "--notes", "Formal status should not require manual placeholder replacement when milestone evidence exists.",
        )
        self.run_bundle(
            "checkpoint",
            "--root", str(self.root),
            "--slug", slug,
            "--milestone", "Render evidence",
            "--delivered", "TASK-1 delivered evidence-backed render-status bullets.",
            "--verified", "source-only render-status output checked.",
            "--next", "No next step in this fixture.",
            "--focus", "Render status evidence.",
            "--gate", "continue",
            "--gate-status", "pass",
            "--covers", "REQ-1",
        )

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug, "--status", "Completed")

        self.assertIn("IDEA-1 / TASK-* / REQ-1: TASK-1 delivered evidence-backed render-status bullets.", rendered.stdout)
        self.assertIn("IDEA-1 / TASK-* / REQ-1: milestone Render evidence is recorded for this scope.", rendered.stdout)
        self.assertIn("IDEA-1 / TASK-* / REQ-1: source-only render-status output checked.", rendered.stdout)
        self.assertIn("Idea ledger: IDEA-1=active", rendered.stdout)
        self.assertNotIn("summarize the user-visible or workflow change", rendered.stdout)
        self.assertIn("Incomplete Items:\n- none", rendered.stdout)
        self.assertIn("Unverified Items:\n- none", rendered.stdout)
        self.assertIn("Residual Risks:\n- none", rendered.stdout)
        self.assertNotIn("none | <", rendered.stdout)

    def test_render_status_defaults_to_completed_for_accepted_bundle(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        status_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["state"] = "completed"
        status["phase"] = "accepted"
        status["decision"] = "accepted"
        status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug)

        self.assertIn("[idea-to-code][Closer/agent] Status: Completed", rendered.stdout)

    def test_render_status_defaults_to_blocked_for_blocked_bundle(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        status_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["state"] = "blocked"
        status["phase"] = "blocked"
        status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

        rendered = self.run_bundle("render-status", "--root", str(self.root), "--slug", slug)

        self.assertIn("[idea-to-code][Closer/agent] Status: Blocked", rendered.stdout)

    def test_test_batch_command_runs_limited_chunked_unittest_subset(self) -> None:
        result = self.run_bundle("test-batch", "--chunk-size", "1", "--limit", "2", "--timeout-seconds", "60")

        self.assertIn("test-batch: total_tests=2 chunk_size=1 chunks=2", result.stdout)
        self.assertIn("chunk 1/2: PASS tests 1-1", result.stdout)
        self.assertIn("chunk 2/2: PASS tests 2-2", result.stdout)
        self.assertIn("test-batch: PASS total_tests=2", result.stdout)

    def test_user_facing_language_contract_preserves_protocol_english(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        workflow = WORKFLOW_MD.read_text(encoding="utf-8")
        verification = VERIFICATION_MD.read_text(encoding="utf-8")
        roles = ROLES_STATE_MD.read_text(encoding="utf-8")

        self.assertIn("## User-Facing Language Contract", skill)
        self.assertIn("Meaningful user-facing prose follows the user's language by default", skill)
        self.assertIn("If the latest user request is primarily Chinese", skill)
        self.assertIn("Protocol tokens and state remain stable English/ASCII", skill)
        self.assertIn("Do not translate identifiers or fixed protocol fields", skill)
        self.assertIn("bundle/state/protocol content English-only ASCII", workflow)
        self.assertIn("entries from `SKILL.md#Protocol Glossary / Do-Not-Translate List` stay English-only ASCII", verification)
        self.assertIn("user-facing explanations, recommendations, and conclusions follow the user's language by default", roles)

    def test_install_parity_checklist_is_documented(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        verification = VERIFICATION_MD.read_text(encoding="utf-8")
        combined = "\n".join([skill, verification])

        for required in [
            "Installed Skill Parity Checklist",
            "install target path",
            "$CODEX_HOME/skills/idea-to-code",
            "installed focused tests",
            "source/installed SHA256 parity",
            "files changed by the batch",
            "No commit made",
            "Key Technical Details",
            "not under `Incomplete Items`",
            "do not claim the latest skill code is installed and verified",
            "Formal install, validation, or final status must name the relevant TASK/REQ",
            "Report the gap in `Unverified Items`",
        ]:
            self.assertIn(required, combined)

    def test_tool_layer_edit_wrapper_design_is_documented(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        workflow = WORKFLOW_MD.read_text(encoding="utf-8")
        verification = VERIFICATION_MD.read_text(encoding="utf-8")
        combined = "\n".join([skill, workflow, verification])

        for required in [
            "Tool-layer edit wrapper design",
            "tracked-edit wrapper",
            "host pre-edit hook",
            "physically sits before file writes",
            "resolve the active bundle",
            "visible Exploration",
            "READY Focus",
            "non-overlapping lease",
            "implementation pre-edit",
            "TASK file scope",
            "capture `PRE_EDIT_OK_ID`",
            "Implementer evidence",
            "Current Codex edit tools are not physically blocked",
            "`residual risk`",
            "do not describe current guidance as non-bypassable physical enforcement",
        ]:
            self.assertIn(required, combined)

    def test_protocol_glossary_lists_do_not_translate_terms_and_maintenance_rule(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        workflow = WORKFLOW_MD.read_text(encoding="utf-8")
        verification = VERIFICATION_MD.read_text(encoding="utf-8")
        roles = ROLES_STATE_MD.read_text(encoding="utf-8")

        self.assertIn("### Protocol Glossary / Do-Not-Translate List", skill)
        self.assertIn("canonical maintenance point", skill)
        self.assertIn("Add, remove, or rename entries here when the protocol changes", skill)
        self.assertIn("Do not scatter new do-not-translate terms only in prose", skill)
        for expected in [
            "[idea-to-code][Planner/agent]",
            "[idea-to-code][Closer/agent]",
            "Planner",
            "Implementer",
            "Validator",
            "Reviewer",
            "Closer",
            "Status",
            "Changes",
            "Completed Items",
            "Validation Results",
            "TASK-*",
            "REQ-*",
            "IDEA-*",
            "MB-*",
            "EXPLORATION_OUTPUT_ID",
            "READY_TASK_OUTPUT_ID",
            "PRE_EDIT_OK_ID",
            "LEASE_ID",
            "render-status",
            "implementation enter-task",
            "00-idea.md",
            "state.json",
            "source-only",
            "unverified",
        ]:
            self.assertIn(expected, skill)
        self.assertIn("SKILL.md#Protocol Glossary / Do-Not-Translate List", workflow)
        self.assertIn("SKILL.md#Protocol Glossary / Do-Not-Translate List", verification)
        self.assertIn("SKILL.md#Protocol Glossary / Do-Not-Translate List", roles)
        self.assertIn("Role/source prefixes, role names", roles)
        self.assertIn("translated protocol glossary entries", roles)

    def test_reviewer_weakness_reports_require_status_taxonomy(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        verification = VERIFICATION_MD.read_text(encoding="utf-8")
        workflow = WORKFLOW_MD.read_text(encoding="utf-8")
        roles = ROLES_STATE_MD.read_text(encoding="utf-8")

        self.assertIn("## Risk And Weakness Taxonomy", skill)
        self.assertIn("## Weakness Report Taxonomy", verification)
        for label in ["already hardened", "residual risk", "new gap", "external validation"]:
            self.assertIn(f"`{label}`", skill)
            self.assertIn(f"`{label}`", verification)
            self.assertIn(f"`{label}`", roles)
            self.assertIn(f"`{label}`", workflow)
        self.assertIn("Do not mix old and new weaknesses in one unlabeled list", skill)
        self.assertIn("SKILL.md#Risk And Weakness Taxonomy", workflow)
        self.assertIn("SKILL.md#Risk And Weakness Taxonomy", verification)
        self.assertIn("Repeating an older issue without saying which class it belongs to is ambiguous", roles)
        self.assertIn("repeats a prior weakness without one of these labels is ambiguous", verification)

    def test_controlled_exploration_benchmark_has_chinese_language_boundary_scenario(self) -> None:
        benchmark = CONTROLLED_EXPLORATION_BENCHMARK_MD.read_text(encoding="utf-8")

        self.assertIn("### Response Scenario N: Chinese Language Boundary", benchmark)
        self.assertIn("我用中文问", benchmark)
        self.assertIn("协议字段不要翻译", benchmark)
        for expected in [
            "[idea-to-code][Closer/agent]",
            "`Status`",
            "`Changes`",
            "`Completed Items`",
            "`Validation Results`",
            "`TASK-*`",
            "`REQ-*`",
            "`READY_TASK_OUTPUT_ID`",
            "`Planner`",
            "`Implementer`",
            "`Validator`",
            "`Reviewer`",
            "`Closer`",
        ]:
            self.assertIn(expected, benchmark)
        self.assertIn("Writes meaningful explanatory prose in Chinese", benchmark)
        self.assertIn("answers naturally in Chinese without `render-status`", benchmark)

    def test_controlled_exploration_benchmark_has_non_chinese_language_boundary_scenario(self) -> None:
        benchmark = CONTROLLED_EXPLORATION_BENCHMARK_MD.read_text(encoding="utf-8")

        self.assertIn("### Response Scenario O: Non-Chinese Language Boundary", benchmark)
        self.assertIn("En espanol", benchmark)
        self.assertIn("No traduzcas los campos de protocolo", benchmark)
        for expected in [
            "tracked-delivery-status",
            "Writes meaningful explanatory prose in Spanish",
            "[idea-to-code][Closer/agent]",
            "`Status`",
            "`Changes`",
            "`Completed Items`",
            "`Incomplete Items`",
            "`Validation Results`",
            "`TASK-*`",
            "`REQ-*`",
            "`READY_TASK_OUTPUT_ID`",
            "`render-status`",
            "`Planner`",
            "`Implementer`",
            "`Validator`",
            "`Reviewer`",
            "`Closer`",
            "Does not treat all non-English prompts as Chinese",
            "answers naturally in Spanish without `render-status`",
        ]:
            self.assertIn(expected, benchmark)

    def test_fresh_benchmark_init_and_status_create_artifact_without_claiming_live_evidence(self) -> None:
        slug = self.init_bundle()

        missing = self.run_bundle("fresh-benchmark", "status", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(missing.returncode, 0)
        missing_payload = json.loads(missing.stdout)
        self.assertFalse(missing_payload["exists"])
        self.assertEqual(missing_payload["state"], "missing")
        self.assertTrue(missing_payload["external_run_required"])
        self.assertFalse(missing_payload["live_evidence_created"])
        self.assertIn("run fresh-benchmark init", missing_payload["next_required_action"])

        init = self.run_bundle("fresh-benchmark", "init", "--root", str(self.root), "--slug", slug)
        init_payload = json.loads(init.stdout)
        artifact = Path(init_payload["path"])
        self.assertTrue(artifact.exists())
        self.assertEqual(init_payload["state"], "scaffolded")
        self.assertTrue(init_payload["external_run_required"])
        self.assertFalse(init_payload["live_evidence_created"])
        self.assertFalse(init_payload["evidence_ready"])
        self.assertIn("separate fresh session", init_payload["next_required_action"])
        self.assertIn("This is not live evidence", artifact.read_text(encoding="utf-8"))

        status = self.run_bundle("fresh-benchmark", "status", "--root", str(self.root), "--slug", slug)
        status_payload = json.loads(status.stdout)
        self.assertTrue(status_payload["exists"])
        self.assertEqual(status_payload["state"], "scaffolded")
        self.assertTrue(status_payload["external_run_required"])
        self.assertFalse(status_payload["live_evidence_created"])
        self.assertFalse(status_payload["evidence_ready"])
        self.assertFalse(status_payload["scores_present"])
        self.assertFalse(status_payload["external_run_completed"])
        self.assertEqual(status_payload["recorded_artifact"], "artifacts\\fresh-session-live-benchmark.md" if os.name == "nt" else "artifacts/fresh-session-live-benchmark.md")

        text = artifact.read_text(encoding="utf-8")
        artifact.write_text(
            text
            .replace("External run status: `not-started | in-progress | completed`", "External run status: `completed`")
            .replace("- Total score: `<n>/63`", "- Total score: `60/63`")
            .replace("Raw output: `<transcript id or artifact path>`", "Raw output: `artifacts/fresh-run-raw.md`"),
            encoding="utf-8",
        )
        completed = self.run_bundle("fresh-benchmark", "status", "--root", str(self.root), "--slug", slug)
        completed_payload = json.loads(completed.stdout)
        self.assertEqual(completed_payload["state"], "completed")
        self.assertFalse(completed_payload["external_run_required"])
        self.assertTrue(completed_payload["live_evidence_created"])
        self.assertTrue(completed_payload["evidence_ready"])
        self.assertTrue(completed_payload["raw_outputs_present"])
        self.assertTrue(completed_payload["scores_present"])
        self.assertTrue(completed_payload["external_run_completed"])
        self.assertIn("review the recorded raw outputs and scores", completed_payload["next_required_action"])

        duplicate = self.run_bundle("fresh-benchmark", "init", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("artifact already exists", duplicate.stderr)

    def test_implementer_evidence_must_cite_latest_pre_edit_guard_when_present(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        self.run_bundle("implementation", "enter-task", "--root", str(self.root), "--slug", slug, "--task", "TASK-1")
        self.acquire_lease(slug)
        self.run_bundle("implementation", "pre-edit", "--root", str(self.root), "--slug", slug, "--task", "TASK-1", "--file", "state.json")
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "planner",
            "--evidence", (
                f"REQ-1 planned in 00-idea.md with TASK-1 ready after EXPLORATION_OUTPUT_ID {status['exploration_output_id']} "
                f"and READY_TASK_OUTPUT_ID {status['ready_task_output_id']}"
            ),
            "--covers", "REQ-1",
        )

        missing = self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "implementer",
            "--evidence", f"TASK-1 updated state.json for REQ-1 after READY_TASK_OUTPUT_ID {status['ready_task_output_id']}",
            "--covers", "REQ-1",
            check=False,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("cite the latest pre-edit guard as PRE_EDIT_OK_ID", missing.stderr)

        self.run_bundle(
            "role", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--role", "implementer",
            "--evidence", (
                f"TASK-1 updated state.json for REQ-1 after READY_TASK_OUTPUT_ID {status['ready_task_output_id']} "
                f"and PRE_EDIT_OK_ID {status['pre_edit_ok_id']}"
            ),
            "--covers", "REQ-1",
        )

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
        self.assertTrue(payload["exploration_output_id"])
        self.assertIn("[idea-to-code][Planner/agent] Implementation Gate: READY", ready_output_part)
        self.assertIn("Display Layer: READY Focus", ready_output_part)
        self.assertIn("EXPLORATION_OUTPUT_ID:", ready_output_part)
        self.assertIn("READY_TASK_OUTPUT_ID:", ready_output_part)
        self.assertIn("TASK-1: Add one concise README sentence.", ready_output_part)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["slug"], slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["implementation_ready"])
        self.assertTrue(status["exploration_output_required"])
        self.assertEqual(status["exploration_output_plan_revision"], status["plan_revision"])
        self.assertTrue(status["exploration_output_id"])
        self.assertTrue(status["ready_task_output_required"])
        self.assertEqual(status["ready_task_output_plan_revision"], status["plan_revision"])
        self.assertTrue(status["ready_task_output_id"])
        self.assertEqual(len(status["requirements"]), 1)
        self.assertTrue(status["role_evidence"]["planner"])
        idea = (self.root / ".idea-to-code" / slug / "00-idea.md").read_text(encoding="utf-8")
        self.assertIn("## Controlled Exploration", idea)
        self.assertIn("- Exploration Needed: no", idea)
        self.assertIn("- Planned Scope:", idea)
        self.assertIn("- Required Now: TASK-1 / REQ-1 scoped edit to `README.md`.", idea)
        self.assertIn("- What READY Will Cover: TASK-1 / REQ-1 only.", idea)
        ready_output = self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug)
        self.assertIn("Display Layer: READY Focus", ready_output.stdout)
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
        self.assertTrue(payload["exploration_output_id"])
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
        self.run_bundle("implementation", "show-ready", "--root", str(self.root), "--slug", slug, "--full-plan")
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

    def test_checkpoint_repeated_covers_preserve_all_requirements(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        state_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(state_path.read_text(encoding="utf-8"))
        status["requirements"].append({
            "id": "REQ-2",
            "description": "REQ-2 behavior is tracked",
            "type": "functional",
            "status": "open",
            "created_at_utc": status["created_at_utc"],
        })
        state_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        self.run_bundle(
            "checkpoint",
            "--root", str(self.root),
            "--slug", slug,
            "--milestone", "Repeated covers milestone",
            "--delivered", "REQ-1 and REQ-2 command flow delivered",
            "--verified", "source-only command flow evidence",
            "--next", "finalize",
            "--focus", "closing",
            "--gate", "acceptance",
            "--gate-status", "pass",
            "--covers", "REQ-1",
            "--covers", "REQ-2",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["milestones"][-1]["covers"], ["REQ-1", "REQ-2"])

        self.run_bundle(
            "checkpoint",
            "--root", str(self.root),
            "--slug", slug,
            "--milestone", "Mixed covers milestone",
            "--delivered", "REQ-1 and REQ-2 mixed covers delivered",
            "--verified", "source-only command flow evidence",
            "--next", "finalize",
            "--focus", "closing",
            "--gate", "acceptance",
            "--gate-status", "pass",
            "--covers", "REQ-1,REQ-2",
            "--covers", "REQ-1",
        )
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["milestones"][-1]["covers"], ["REQ-1", "REQ-2"])

    def test_branch_map_command_outputs_required_lifecycle_branches(self) -> None:
        result = self.run_bundle("branch-map", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "idea-to-code.branch-map.v1")
        branch_ids = {branch["id"] for branch in payload["branches"]}
        for expected in [
            "branch-coverage-map",
            "tracked-edit",
            "delegation-evidence",
            "same-session-continuity",
            "idea-ledger",
            "scope-classification",
            "master-backlog",
            "enumerated-scope",
            "current-task-entry",
            "implementation-lease",
            "pre-edit-guard",
            "tool-layer-edit-wrapper",
            "pre-edit-noncompliance",
            "plan-correction",
            "read-only-status",
            "ordinary-answer",
            "formal-tracked-handoff",
            "skill-self-validation",
            "user-facing-language",
            "weakness-review",
            "noncompliance",
        ]:
            self.assertIn(expected, branch_ids)
        for branch in payload["branches"]:
            for field in ["id", "workflow_branch", "entry", "exit", "validation", "failure_handling"]:
                self.assertIn(field, branch)
                self.assertTrue(branch[field])

        text_result = self.run_bundle("branch-map")
        self.assertIn("[idea-to-code][Reviewer/agent] Branch Coverage Map", text_result.stdout)
        self.assertIn("Workflow Branch", text_result.stdout)
        self.assertIn("Failure Handling", text_result.stdout)

    def test_branch_map_matches_workflow_branch_closure_bullets(self) -> None:
        result = self.run_bundle("branch-map", "--json")
        payload = json.loads(result.stdout)
        map_labels = [branch["workflow_branch"] for branch in payload["branches"]]

        workflow = WORKFLOW_MD.read_text(encoding="utf-8")
        section = workflow.split("Branch closure checks for output compliance:", 1)[1]
        section = section.split("\n## ", 1)[0]
        workflow_labels = re.findall(r"^- ([^:\n]+ branch):", section, flags=re.MULTILINE)

        self.assertGreater(len(workflow_labels), 10)
        self.assertEqual(workflow_labels, map_labels)

    def test_branch_coverage_map_is_documented(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        workflow = WORKFLOW_MD.read_text(encoding="utf-8")
        verification = VERIFICATION_MD.read_text(encoding="utf-8")
        combined = "\n".join([skill, workflow, verification])

        for required in [
            "Branch Coverage Map",
            "branch-map --json",
            "id",
            "entry",
            "exit",
            "validation",
            "failure_handling",
            "workflow_branch",
            "mirrors the branch closure checks",
            "observability and self-check aid",
            "not proof that a live agent followed the branch",
            "live compliance still requires actual bundle state",
            "Branch coverage map branch",
        ]:
            self.assertIn(required, combined)

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
        self.assertEqual(status["pending_plan_update_sections"], ["requirements", "design", "implementation"])
        self.write_ready_bundle(slug, mark_ready=False)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["pending_plan_update"])
        self.assertEqual(status["pending_plan_update_sections"], ["design"])
        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(ready.returncode, 0)
        self.assertIn("pending plan update sections remain stale: design", ready.stderr)
        design_path = self.root / "design.md"
        design_path.write_text(
            "# Design\n\nPlan-changing clarification is reflected in the design before implementation resumes.\n",
            encoding="utf-8",
        )
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "design", "--content-file", str(design_path))
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status["pending_plan_update"])
        self.assertEqual(status["pending_plan_update_sections"], [])
        self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug)
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status["pending_plan_update"])
        self.assertEqual(status["pending_plan_update_sections"], [])

    def test_implementation_ready_rejects_pending_plan_update(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug, mark_ready=False)
        state_path = self.root / ".idea-to-code" / slug / "state.json"
        status = json.loads(state_path.read_text(encoding="utf-8"))
        status["pending_plan_update"] = True
        status["pending_plan_update_sections"] = ["requirements", "design"]
        status["implementation_ready"] = False
        state_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

        result = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pending plan update sections remain stale: requirements, design", result.stderr)
        status = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(status["pending_plan_update"])
        self.assertFalse(status["implementation_ready"])

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

    def test_current_json_competing_task_initialization_is_conflict_safe(self) -> None:
        commands = []
        for slug, title in (("alpha", "Alpha task"), ("beta", "Beta task")):
            commands.append([
                sys.executable,
                str(SCRIPT),
                "init",
                "--root",
                str(self.root),
                "--slug",
                slug,
                "--title",
                title,
                "--idea",
                f"Deliver {title.lower()} behavior",
            ])
        procs = [
            subprocess.Popen(cmd, cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for cmd in commands
        ]
        outputs = [proc.communicate(timeout=10) for proc in procs]
        returncodes = [proc.returncode for proc in procs]
        self.assertEqual(returncodes.count(0), 1, outputs)
        self.assertEqual(returncodes.count(1), 1, outputs)
        current = json.loads((self.root / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        self.assertIn(current["slug"], {"alpha", "beta"})
        failed = outputs[returncodes.index(1)]
        self.assertIn("init refused because active bundle", failed[1])

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

    def test_current_json_parallel_archive_init_keeps_single_active_pointer(self) -> None:
        active = self.init_bundle()
        commands = [
            [
                sys.executable,
                str(SCRIPT),
                "current",
                "archive",
                "--root",
                str(self.root),
                "--reason",
                "parallel archive before new task",
            ],
            [
                sys.executable,
                str(SCRIPT),
                "init",
                "--root",
                str(self.root),
                "--slug",
                "other",
                "--title",
                "Other task",
                "--idea",
                "Deliver other behavior",
            ],
        ]
        procs = [
            subprocess.Popen(cmd, cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for cmd in commands
        ]
        outputs = [proc.communicate(timeout=10) for proc in procs]
        self.assertTrue(any(proc.returncode == 0 for proc in procs), outputs)
        current_file = self.root / ".idea-to-code" / "current.json"
        if current_file.exists():
            current = json.loads(current_file.read_text(encoding="utf-8"))
            self.assertIn(current["slug"], {active, "other"})
            self.assertNotEqual(current["slug"], active, "Archived bundle must not remain current after archive succeeds.")
        history = (self.root / ".idea-to-code" / "history" / "index.jsonl").read_text(encoding="utf-8")
        self.assertIn(active, history)

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

    def test_current_resume_uses_current_pointer_lock(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        resume_start = source.index("def current_resume(")
        helper_start = source.index("def _current_resume_locked(")
        resume_body = source[resume_start:helper_start]
        self.assertIn("with current_lock(root):", resume_body)
        self.assertIn("return _current_resume_locked(root, reason, slug)", resume_body)

        helper_end = source.index("def _coverage_by_requirement(", helper_start)
        helper_body = source[helper_start:helper_end]
        self.assertIn("_current_set_locked(root, slug)", helper_body)
        self.assertNotIn("current_set(root, slug)", helper_body)

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

    def test_requirement_add_after_ready_invalidates_implementation_gate(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        before = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(before["implementation_ready"])
        self.assertTrue(before["ready_task_output_id"])

        self.run_bundle(
            "requirement", "add",
            "--root", str(self.root),
            "--slug", slug,
            "--id", "REQ-2",
            "--description", "Second requirement added after ready must refresh the plan",
            "--type", "functional",
        )

        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(status["implementation_ready"])
        self.assertIsNone(status["ready_task_output_id"])
        self.assertEqual(status["plan_revision"], before["plan_revision"] + 1)
        self.assertTrue(status["pending_plan_update"])
        self.assertEqual(status["pending_plan_update_sections"], ["requirements", "design", "implementation"])

        result = self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["route_gate"], "plan-update-required")
        self.assertFalse(payload["can_edit_product_files"])
        self.assertIn("REQ-2", payload["active_bundle"]["open_requirements"])

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

    def test_route_new_same_session_idea_expands_session_ledger(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Build a billing dashboard app")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["active_bundle"]["slug"], slug)
        self.assertEqual(payload["active_bundle"]["title"], "Sample task")
        self.assertEqual(payload["recommended_classification"], "expand")
        self.assertFalse(payload["scope_decision_required"])
        self.assertEqual(payload["route_gate"], "plan-update-required")
        self.assertFalse(payload["can_edit_product_files"])
        self.assertIn("new IDEA scope", payload["next_action"])
        self.assertTrue(any("implementation ready" in command for command in payload["required_next_commands"]))

    def test_route_explicit_separate_session_requires_scope_decision(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Start a separate session for the billing dashboard")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["active_bundle"]["slug"], slug)
        self.assertTrue(payload["scope_decision_required"])
        self.assertEqual(payload["route_gate"], "scope-decision-required")
        self.assertFalse(payload["can_edit_product_files"])
        self.assertIn("different session", payload["scope_decision_reason"])

    def test_route_create_separate_session_app_requires_scope_decision(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Create a separate session for the billing dashboard app")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["active_bundle"]["slug"], slug)
        self.assertEqual(payload["recommended_classification"], "continue")
        self.assertTrue(payload["scope_decision_required"])
        self.assertEqual(payload["route_gate"], "scope-decision-required")
        self.assertFalse(payload["can_edit_product_files"])
        self.assertNotIn("new IDEA scope", payload["next_action"])
        self.assertIn("different session", payload["scope_decision_reason"])

    def test_route_separate_session_scope_decision_overrides_pending_plan_update(self) -> None:
        slug = self.init_bundle()
        result = self.run_bundle("route", "--root", str(self.root), "--input", "Create a separate session for the billing dashboard app")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["active_bundle"]["slug"], slug)
        self.assertTrue(payload["scope_decision_required"])
        self.assertEqual(payload["route_gate"], "scope-decision-required")
        self.assertTrue(payload["must_update_plan_before_code"])
        self.assertFalse(payload["can_edit_product_files"])
        self.assertTrue(any("current archive" in command for command in payload["required_next_commands"]))
        self.assertFalse(any("implementation ready" in command for command in payload["required_next_commands"]))
        self.assertNotIn("pending plan update", payload["next_action"].lower())

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

    def test_partial_plan_update_does_not_clear_pending_gate(self) -> None:
        slug = self.init_bundle()
        self.write_ready_bundle(slug)
        self.run_bundle(
            "user-input", "record",
            "--root", str(self.root),
            "--slug", slug,
            "--summary", "User added another acceptance case",
            "--classification", "expand",
            "--rationale", "The new acceptance case changes requirements and design",
            "--action", "Update requirements design and implementation before coding",
            "--changes-plan", "yes",
        )
        impl_path = self.root / "implementation-only.md"
        impl_path.write_text("""# Implementation

Gate Status: READY

## TASK-1: Verify sample bundle flow

Status: pending

Files:
- state.json

Execution Details:
- Record one requirement and all role evidence after the new acceptance case.

Done Criteria:
- finalize and verify succeed with the new acceptance case.

Planned Verification:
- source-only python idea_to_code_bundle.py verify exits zero.
""", encoding="utf-8")
        self.run_bundle("update", "--root", str(self.root), "--slug", slug, "--file", "implementation", "--content-file", str(impl_path))
        status = json.loads((self.root / ".idea-to-code" / slug / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(status["pending_plan_update"])
        self.assertEqual(status["pending_plan_update_sections"], ["requirements", "design"])

        ready = self.run_bundle("implementation", "ready", "--root", str(self.root), "--slug", slug, check=False)
        self.assertNotEqual(ready.returncode, 0)
        self.assertIn("pending plan update sections remain stale: requirements, design", ready.stderr)

        result = self.run_bundle("route", "--root", str(self.root), "--input", "Continue implementation")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["route_gate"], "plan-update-required")
        self.assertFalse(payload["can_edit_product_files"])
        self.assertIn("requirements, design", payload["next_action"])
        self.assertTrue(any("--file requirements" in command for command in payload["required_next_commands"]))
        self.assertTrue(any("--file design" in command for command in payload["required_next_commands"]))
        self.assertFalse(any("--file implementation" in command for command in payload["required_next_commands"]))

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
- Planned Scope:
  - Required Now: REQ-1 through REQ-3 dogfood governance path.
  - Deferred: Product code changes outside the fixture.
  - What READY Will Cover: TASK-1 through TASK-3 fixture milestones.
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
