"""Real filesystem and CLI counterexamples for the delivery controller."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from delivery_evidence import (
    acceptance_problems, build_record, candidate_manifest, evolution_problems,
    resume_problems,
)


class DeliveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.status = {"requirements": [{"id": "REQ-1"}], "local_records": [], "plan_revision": 3}
        self.write("src/main.py", "print('normal behavior')\n")
        self.write("artifacts/result.txt", "Actual observed normal and rejection results.\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def record(self, action, payload):
        before = copy.deepcopy(self.status)
        result = build_record(self.root, self.status, action, payload, ["TASK-1", "TASK-2"])
        self.assertEqual(self.status, before, "builder must not mutate owned state")
        self.status["local_records"].append(result)
        state_file = self.root / ".idea-to-code/business/state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state.update(self.status)
            state_file.write_text(json.dumps(state), encoding="utf-8")
        return result

    def declare_payload(self, case="CASE-1", **updates):
        payload = {
            "id": case, "task_id": "TASK-1", "requirement_ids": ["REQ-1"],
            "object_id": "implementation-" + case, "validation_type": "real-product-path",
            "candidate_files": ["src/main.py"], "expected": "Normal input produces the required output.",
            "expected_basis": "The original requirement defines the observable result.",
            "polarity": "positive",
        }
        payload.update(updates)
        return payload

    def declare(self, case="CASE-1", **updates):
        return self.record("acceptance-declare", self.declare_payload(case, **updates))

    def evidence_payload(self, case="CASE-1", record_id=None, **updates):
        payload = {
            "id": record_id or "EVID-" + case, "case_id": case, "result": "pass",
            "validation_type": "real-product-path", "artifacts": ["artifacts/result.txt"],
            "observed": "Actual normal output and rejection state match expected results.",
            "command": "python src/main.py", "environment": "isolated temporary test instance",
        }
        payload.update(updates)
        return payload

    def evidence(self, case="CASE-1", record_id=None, **updates):
        return self.record("acceptance-evidence", self.evidence_payload(case, record_id, **updates))

    def link(self):
        self.write(".idea-to-code/business/00-idea.md", "### TASK-1: original work\n### TASK-2: improvement\n")
        self.write(".idea-to-code/business/state.json", json.dumps({"current_task_id": "TASK-1", "plan_revision": 3}))
        self.write(".idea-to-code/current.json", json.dumps({"slug": "business", "status": "working"}))
        return {"root": str(self.root), "bundle": "business", "task_id": "TASK-1",
                "plan_revision": 3, "next_action": "Resume the remaining real acceptance cases."}

    def capture(self):
        if not self.status["local_records"]:
            self.declare()
            self.evidence()
        return self.record("evolution-capture", {
            "id": "EVOL-1", "task_id": "TASK-1", "requirement_ids": ["REQ-1"],
            "fact": "A required rejection case was missing from the first acceptance run.",
            "evidence_refs": [self.status["local_records"][0]["id"]],
            "hypotheses": ["The verification mechanism does not compare declared coverage."],
            "resume": self.link(),
        })

    def disposition(self, **updates):
        payload = {"id": "DISP-1", "incident_id": "EVOL-1", "diagnosis": "verification-mechanism-gap",
                   "action": "improve-skill", "reason": "Reproduced with a generic missing-case scenario.",
                   "evidence_refs": ["EVOL-1"],
                   "improvement": {"root": str(self.root), "bundle": "business", "task_id": "TASK-1"}}
        payload.update(updates)
        return self.record("evolution-disposition", payload)

    def activation_ready(self):
        self.capture()
        self.disposition()
        self.write("skill/SKILL.md", "A generic skill entrypoint.\n")
        self.write("skill/scripts/control.py", "print('checked')\n")
        self.write("skill/scripts/test_control.py", "assert True\n")
        files = ["skill/SKILL.md", "skill/scripts/control.py", "skill/scripts/test_control.py"]
        for case, polarity in (("POS", "positive"), ("NEG", "negative")):
            self.declare(case, candidate_files=files, polarity=polarity)
            self.evidence(case)
        shutil.copytree(self.root / "skill", self.root / "installed")
        return {"id": "ACT-1", "incident_id": "EVOL-1", "case_ids": ["POS", "NEG"],
                "source_dir": str(self.root / "skill"), "installed_dir": str(self.root / "installed")}

    def test_legacy_prose_is_not_required_or_converted(self):
        self.status["local_records"].append({"id": "OLD", "kind": "V", "text": "all adapters passed real-product-path"})
        self.assertEqual(acceptance_problems(self.root, self.status), [])
        self.declare()
        self.assertIn("missing acceptance evidence", acceptance_problems(self.root, self.status)[0])

    def test_one_of_nine_does_not_complete_coverage(self):
        for index in range(9):
            self.declare(f"CASE-{index}")
        self.evidence("CASE-0")
        self.assertEqual(len(acceptance_problems(self.root, self.status)), 8)
        for index in range(1, 9):
            self.evidence(f"CASE-{index}")
        self.assertEqual(acceptance_problems(self.root, self.status), [])

    def test_scoped_acceptance_requires_case_and_ignores_other_task_cases(self):
        self.assertIn("missing declared", " ".join(acceptance_problems(self.root, self.status, "TASK-1")))
        self.declare()
        self.evidence()
        self.declare("OTHER-TASK", task_id="TASK-2")
        self.assertEqual(acceptance_problems(self.root, self.status, "TASK-1"), [])
        self.assertIn("missing acceptance", " ".join(acceptance_problems(self.root, self.status, "TASK-2")))

    def test_changed_then_deleted_candidate_invalidates_evidence(self):
        self.declare()
        self.evidence()
        self.write("src/main.py", "print('changed')\n")
        self.assertIn("stale", " ".join(acceptance_problems(self.root, self.status)))
        (self.root / "src/main.py").unlink()
        self.assertIn("stale", " ".join(acceptance_problems(self.root, self.status)))

    def test_new_plan_revision_invalidates_old_acceptance(self):
        self.declare()
        self.evidence()
        self.status["plan_revision"] += 1
        self.assertIn("plan revision", " ".join(acceptance_problems(self.root, self.status)))

    def test_missing_candidate_is_explicit_tombstone(self):
        self.declare(candidate_files=["src/removed.py"])
        evidence = self.evidence()
        self.assertEqual(evidence["data"]["candidate"], {"src/removed.py": None})
        self.assertEqual(acceptance_problems(self.root, self.status), [])
        self.write("src/removed.py", "restored")
        self.assertTrue(acceptance_problems(self.root, self.status))

    def test_changed_artifact_and_missing_artifact_are_not_success(self):
        self.declare()
        self.evidence()
        self.write("artifacts/result.txt", "different result")
        self.assertTrue(acceptance_problems(self.root, self.status))
        (self.root / "artifacts/result.txt").unlink()
        self.assertTrue(acceptance_problems(self.root, self.status))

    def test_wrong_scope_unknown_refs_and_duplicate_ids_rejected(self):
        self.declare()
        for payload in [self.evidence_payload(validation_type="fixture-only"), self.evidence_payload(case="ABSENT")]:
            with self.assertRaises(ValueError):
                self.record("acceptance-evidence", payload)
        for updates in [{"task_id": "TASK-99"}, {"requirement_ids": ["REQ-99"]}]:
            with self.assertRaises(ValueError):
                self.declare("OTHER", **updates)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.declare()

    def test_candidate_and_artifact_path_escape_rejected(self):
        self.declare()
        for value in ["../outside.py", str(self.root / "src/main.py"), "src"]:
            with self.assertRaises(ValueError):
                candidate_manifest(self.root, [value])
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.evidence(artifacts=["missing.log"])

    def test_latest_failed_result_replaces_previous_pass(self):
        self.declare()
        self.evidence()
        self.evidence(record_id="FAIL-1", result="fail")
        self.assertIn("did not pass", " ".join(acceptance_problems(self.root, self.status)))

    def test_reported_execution_cannot_be_upgraded_by_payload(self):
        self.declare()
        record = self.evidence(provenance="independently-observed", candidate_sha256="made-up")
        self.assertEqual(record["data"]["provenance"], "reported")
        self.assertNotEqual(record["data"]["candidate_sha256"], "made-up")

    def test_amendment_preserves_history_and_invalidates_evidence(self):
        self.declare()
        self.evidence()
        self.record("acceptance-amend", {"id": "AMEND-1", "case_id": "CASE-1",
                    "reason": "User clarified the expected rejection output.", "expected": "A specific rejection is required."})
        self.assertIn("amended", " ".join(acceptance_problems(self.root, self.status)))
        self.evidence(record_id="EVID-NEW")
        self.assertEqual(acceptance_problems(self.root, self.status), [])
        with self.assertRaisesRegex(ValueError, "silently change"):
            self.record("acceptance-amend", {"id": "AMEND-2", "case_id": "CASE-1", "reason": "attempted shrink", "object_id": "different"})

    def test_capture_keeps_hypothesis_distinct_and_resume_checks_plan(self):
        incident = self.capture()
        self.assertIn("fact", incident["data"])
        self.assertIn("hypotheses", incident["data"])
        self.assertEqual(resume_problems(self.root, self.status, "EVOL-1"), [])
        self.write(".idea-to-code/business/00-idea.md", "### TASK-1: replaced plan\n")
        self.assertIn("plan changed", " ".join(resume_problems(self.root, self.status, "EVOL-1")))

    def test_resume_pointer_and_task_drift_detected(self):
        self.capture()
        self.assertIn("pointer changed", " ".join(resume_problems(self.root, self.status, "EVOL-1", {"slug": "other"})))
        self.write(".idea-to-code/business/state.json", json.dumps({"current_task_id": "TASK-2", "plan_revision": 3}))
        self.assertIn("task changed", " ".join(resume_problems(self.root, self.status, "EVOL-1")))

    def test_unconfirmed_cause_cannot_activate(self):
        self.capture()
        with self.assertRaisesRegex(ValueError, "unconfirmed"):
            self.disposition(diagnosis="unconfirmed")
        self.disposition(diagnosis="unconfirmed", action="defer")
        self.assertTrue(evolution_problems(self.root, self.status))

    def test_non_actionable_incident_can_close_without_skill_edit(self):
        self.capture()
        self.disposition(diagnosis="environment", action="no-change")
        self.assertEqual(evolution_problems(self.root, self.status), [])

    def test_repair_requires_real_current_case_evidence(self):
        self.capture()
        self.disposition(action="repair-project")
        self.assertTrue(evolution_problems(self.root, self.status))
        self.disposition(id="DISP-2", action="repair-project", resolved=True, case_ids=["CASE-1"])
        self.assertEqual(evolution_problems(self.root, self.status), [])
        self.write("src/main.py", "later edit")
        self.assertTrue(evolution_problems(self.root, self.status))

    def test_activation_requires_both_cases_and_exact_parity(self):
        payload = self.activation_ready()
        with self.assertRaisesRegex(ValueError, "positive and negative"):
            self.record("evolution-activate", dict(payload, case_ids=["POS"]))
        self.write("installed/SKILL.md", "different installed version")
        with self.assertRaisesRegex(ValueError, "manifests differ"):
            self.record("evolution-activate", payload)

    def test_equal_copies_with_stale_validation_cannot_activate(self):
        payload = self.activation_ready()
        self.write("skill/SKILL.md", "new unvalidated source")
        self.write("installed/SKILL.md", "new unvalidated source")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.record("evolution-activate", payload)

    def test_activation_rejects_uncovered_new_source_file(self):
        payload = self.activation_ready()
        self.write("skill/new.py", "uncovered")
        self.write("installed/new.py", "uncovered")
        with self.assertRaisesRegex(ValueError, "does not cover"):
            self.record("evolution-activate", payload)

    def test_activation_is_not_effectiveness_and_later_drift_is_visible(self):
        payload = self.activation_ready()
        self.write("installed/__pycache__/junk.pyc", "ignored generated bytes")
        activated = self.record("evolution-activate", payload)
        self.assertEqual(activated["data"]["effectiveness"], "not-yet-observed")
        self.assertEqual(evolution_problems(self.root, self.status), [])
        observation = self.record("evolution-observe", {"id": "OBS-1", "incident_id": "EVOL-1",
            "outcome": "insufficient", "evidence_refs": ["EVID-POS"], "note": "No later task has tested effectiveness."})
        self.assertEqual(observation["data"]["outcome"], "insufficient")
        self.write("installed/SKILL.md", "drift")
        self.assertTrue(evolution_problems(self.root, self.status))

    def test_observed_ineffectiveness_requires_new_diagnosis(self):
        payload = self.activation_ready()
        self.record("evolution-activate", payload)
        self.record("evolution-observe", {"id": "OBS-FAIL", "incident_id": "EVOL-1",
            "outcome": "ineffective", "evidence_refs": ["EVID-POS"], "note": "A later task repeated the same omission."})
        self.assertIn("renewed diagnosis", " ".join(evolution_problems(self.root, self.status)))

    def test_later_effective_observation_does_not_mask_unresolved_ineffectiveness(self):
        payload = self.activation_ready()
        self.record("evolution-activate", payload)
        self.record("evolution-observe", {"id": "OBS-FAIL", "incident_id": "EVOL-1",
            "outcome": "ineffective", "evidence_refs": ["EVID-POS"],
            "note": "A later task repeated the same omission."})
        self.record("evolution-observe", {"id": "OBS-PASS", "incident_id": "EVOL-1",
            "outcome": "effective", "evidence_refs": ["EVID-POS"],
            "note": "A separate later task followed the rule."})

        self.assertIn("renewed diagnosis", " ".join(evolution_problems(self.root, self.status)))

    def test_later_false_positive_reopens_decision_without_erasing_evidence(self):
        payload = self.activation_ready()
        self.record("evolution-activate", payload)
        accepted_records = copy.deepcopy(self.status["local_records"])
        self.record("evolution-observe", {"id": "OBS-FALSE", "incident_id": "EVOL-1",
            "outcome": "false-positive", "evidence_refs": ["EVID-NEG"],
            "note": "The accepted rule rejected a valid normal task in a later trial."})
        self.assertIn("renewed diagnosis", " ".join(evolution_problems(self.root, self.status)))
        self.assertEqual(self.status["local_records"][:len(accepted_records)], accepted_records)
        self.disposition(id="DISP-REVISED", diagnosis="unconfirmed", action="defer",
                         reason="Cause is not yet confirmed; keep the observation unresolved.")
        revised_problems = " ".join(evolution_problems(self.root, self.status))
        self.assertIn("verified resolution", revised_problems)
        self.assertNotIn("renewed diagnosis", revised_problems)

    def test_effective_and_insufficient_observations_keep_distinct_claims(self):
        payload = self.activation_ready()
        self.record("evolution-activate", payload)
        accepted = copy.deepcopy(self.status)
        for outcome in ("effective", "insufficient"):
            with self.subTest(outcome=outcome):
                self.status = copy.deepcopy(accepted)
                observation = self.record("evolution-observe", {"id": "OBS-NEXT", "incident_id": "EVOL-1",
                    "outcome": outcome, "evidence_refs": ["EVID-POS"],
                    "note": "Observation applies only to the named fixture trial."})
                self.assertEqual(observation["data"]["outcome"], outcome)
                self.assertEqual(evolution_problems(self.root, self.status), [])

    def test_linked_task_requires_heading_not_arbitrary_mention(self):
        self.capture()
        self.write(".idea-to-code/business/00-idea.md", "The text merely mentions TASK-1 without declaring it.\n")
        with self.assertRaisesRegex(ValueError, "absent from plan"):
            self.disposition()

    def test_cross_project_activation_reads_linked_evidence_and_preserves_resume(self):
        self.capture()
        skill_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(skill_temporary.cleanup)
        skill_root = Path(skill_temporary.name).resolve()
        bundle = skill_root / ".idea-to-code/improve"
        bundle.mkdir(parents=True)
        (bundle / "00-idea.md").write_text("### TASK-2: Improve generic coverage check\n", encoding="utf-8")
        skill_state = {"requirements": [{"id": "REQ-1"}], "local_records": [], "plan_revision": 1}
        (bundle / "state.json").write_text(json.dumps(skill_state), encoding="utf-8")
        source = skill_root / "skill"
        source.mkdir()
        (source / "SKILL.md").write_text("Generic coverage rules.", encoding="utf-8")
        (skill_root / "run.txt").write_text("Both normal and rejection output checked.", encoding="utf-8")
        self.disposition(improvement={"root": str(skill_root), "bundle": "improve", "task_id": "TASK-2"})
        for case_id, polarity in (("CROSS-POS", "positive"), ("CROSS-NEG", "negative")):
            declaration = self.declare_payload(case_id, task_id="TASK-2", polarity=polarity, candidate_files=["skill/SKILL.md"])
            skill_state["local_records"].append(build_record(skill_root, skill_state, "acceptance-declare", declaration, ["TASK-2"]))
            evidence = self.evidence_payload(case_id, artifacts=["run.txt"])
            skill_state["local_records"].append(build_record(skill_root, skill_state, "acceptance-evidence", evidence, ["TASK-2"]))
        (bundle / "state.json").write_text(json.dumps(skill_state), encoding="utf-8")
        shutil.copytree(source, skill_root / "installed")
        activation = {"id": "CROSS-ACT", "incident_id": "EVOL-1",
            "case_ids": ["CROSS-POS", "CROSS-NEG"], "source_dir": str(source), "installed_dir": str(skill_root / "installed")}
        failed_case = self.declare_payload("CROSS-THIRD", task_id="TASK-2", candidate_files=["skill/SKILL.md"])
        skill_state["local_records"].append(build_record(skill_root, skill_state, "acceptance-declare", failed_case, ["TASK-2"]))
        failed_evidence = self.evidence_payload("CROSS-THIRD", artifacts=["run.txt"], result="fail")
        skill_state["local_records"].append(build_record(skill_root, skill_state, "acceptance-evidence", failed_evidence, ["TASK-2"]))
        (bundle / "state.json").write_text(json.dumps(skill_state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "CROSS-THIRD.*did not pass"):
            self.record("evolution-activate", activation)
        passing_evidence = self.evidence_payload("CROSS-THIRD", record_id="THIRD-RETEST", artifacts=["run.txt"])
        skill_state["local_records"].append(build_record(skill_root, skill_state, "acceptance-evidence", passing_evidence, ["TASK-2"]))
        (bundle / "state.json").write_text(json.dumps(skill_state), encoding="utf-8")
        self.record("evolution-activate", activation)
        self.assertEqual(evolution_problems(self.root, self.status), [])
        self.assertEqual(resume_problems(self.root, self.status, "EVOL-1"), [])
        later_case = self.declare_payload("CROSS-LATER", task_id="TASK-2", candidate_files=["skill/SKILL.md"])
        skill_state["local_records"].append(build_record(skill_root, skill_state, "acceptance-declare", later_case, ["TASK-2"]))
        (bundle / "state.json").write_text(json.dumps(skill_state), encoding="utf-8")
        self.assertIn("CROSS-LATER: missing acceptance", " ".join(evolution_problems(self.root, self.status)))
        later_evidence = self.evidence_payload("CROSS-LATER", artifacts=["run.txt"])
        skill_state["local_records"].append(build_record(skill_root, skill_state, "acceptance-evidence", later_evidence, ["TASK-2"]))
        (bundle / "state.json").write_text(json.dumps(skill_state), encoding="utf-8")
        self.assertEqual(evolution_problems(self.root, self.status), [])
        (source / "SKILL.md").write_text("Changed after activation.", encoding="utf-8")
        self.assertTrue(evolution_problems(self.root, self.status))

    def test_unknown_typed_action_is_not_silently_ignored(self):
        self.status["local_records"].append({"id": "UNKNOWN", "kind": "ACCEPTANCE", "data": {"schema_version": 1, "action": "made-up"}})
        self.assertIn("unknown typed", " ".join(acceptance_problems(self.root, self.status)))

    def test_incomplete_known_typed_action_is_reported_not_crashed(self):
        self.status["local_records"].append({"id": "INCOMPLETE", "kind": "EVOLUTION", "data": {"schema_version": 1, "action": "evolution-capture"}})
        self.assertIn("malformed", " ".join(acceptance_problems(self.root, self.status)))
        self.assertEqual(evolution_problems(self.root, self.status), [])


class DeliveryCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.script = Path(__file__).with_name("idea_to_code_bundle.py")
        self.slug = "delivery-test"
        self.cli("init", "--title", "Declared coverage verification", "--idea", "Verify all declared implementation objects.")
        self.cli("requirement", "add", "--id", "REQ-1", "--description", "Every declared implementation has current evidence.")
        self.bundle = self.root / ".idea-to-code" / self.slug
        plan = self.bundle / "00-idea.md"
        self.assertIn("TASK-1", plan.read_text(encoding="utf-8"))
        (self.root / "candidate.py").write_text("print('candidate')\n", encoding="utf-8")
        (self.root / "result.txt").write_text("Observed required normal behavior.\n", encoding="utf-8")

    def cli(self, *args, expected=0):
        command = [sys.executable, str(self.script), *args, "--root", str(self.root), "--slug", self.slug]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def record(self, action, payload, expected=0):
        path = self.root / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return self.cli("delivery", "record", "--action", action, "--input", str(path), expected=expected)

    def declaration(self, index):
        return {"id": f"CASE-{index}", "task_id": "TASK-1", "requirement_ids": ["REQ-1"],
                "object_id": f"implementation-{index}", "validation_type": "real-product-path",
                "candidate_files": ["candidate.py"], "expected": "Required output appears.",
                "expected_basis": "Original requirement explicitly states the output."}

    def evidence(self, index):
        return {"id": f"EVID-{index}", "case_id": f"CASE-{index}", "result": "pass",
                "validation_type": "real-product-path", "artifacts": ["result.txt"],
                "observed": "Required output appeared.", "command": "python candidate.py", "environment": "isolated test instance"}

    def test_real_cli_nine_objects_and_stale_candidate(self):
        for index in range(9):
            self.record("acceptance-declare", self.declaration(index))
        self.record("acceptance-evidence", self.evidence(0))
        missing = self.cli("delivery", "check", expected=1)
        self.assertEqual(len(json.loads(missing.stdout)["problems"]), 8)
        for index in range(1, 9):
            self.record("acceptance-evidence", self.evidence(index))
        self.assertTrue(json.loads(self.cli("delivery", "check").stdout)["ok"])
        (self.root / "candidate.py").write_text("unvalidated edit", encoding="utf-8")
        stale = self.cli("delivery", "check", expected=1)
        self.assertTrue(all("stale" in item for item in json.loads(stale.stdout)["problems"]))

    def test_rejected_record_and_read_only_check_preserve_state(self):
        self.record("acceptance-declare", self.declaration(1))
        state = self.bundle / "state.json"
        before = state.read_bytes()
        invalid = self.evidence(1)
        invalid["validation_type"] = "fixture-only"
        self.record("acceptance-evidence", invalid, expected=1)
        self.assertEqual(state.read_bytes(), before)
        self.cli("delivery", "check", expected=1)
        self.assertEqual(state.read_bytes(), before)

    def test_omitted_whole_task_is_rejected_then_complete_plan_passes(self):
        plan = self.bundle / "00-idea.md"
        content = plan.read_text(encoding="utf-8")
        content += "\n### TASK-2: Verify the second affected implementation\n\nStatus: pending\n"
        plan.write_text(content, encoding="utf-8")
        first = self.declaration(1)
        first["task_id"] = "TASK-1"
        self.record("acceptance-declare", first)
        self.record("acceptance-evidence", self.evidence(1))
        result = json.loads(self.cli("delivery", "check", expected=1).stdout)
        self.assertTrue(any("TASK-2" in problem for problem in result["problems"]), result)
        second = self.declaration(2)
        second["task_id"] = "TASK-2"
        self.record("acceptance-declare", second)
        self.record("acceptance-evidence", self.evidence(2))
        self.assertTrue(json.loads(self.cli("delivery", "check").stdout)["ok"])

    def test_render_completed_refuses_stale_declared_evidence(self):
        self.record("acceptance-declare", self.declaration(1))
        self.record("acceptance-evidence", self.evidence(1))
        self.assertTrue(json.loads(self.cli("delivery", "check").stdout)["ok"])
        (self.root / "candidate.py").write_text("changed after acceptance", encoding="utf-8")
        state = self.bundle / "state.json"
        before = state.read_bytes()
        result = self.cli("render-status", "--status", "Completed", expected=1)
        self.assertIn("stale", result.stdout + result.stderr)
        self.assertEqual(state.read_bytes(), before)

    def test_render_completed_refuses_unfinalized_work_even_with_passing_cases(self):
        self.record("acceptance-declare", self.declaration(1))
        self.record("acceptance-evidence", self.evidence(1))
        self.assertTrue(json.loads(self.cli("delivery", "check").stdout)["ok"])
        state = self.bundle / "state.json"
        before = state.read_bytes()
        result = self.cli("render-status", "--status", "Completed", expected=1)
        self.assertIn("accepted lifecycle closeout", (result.stdout + result.stderr).lower())
        self.assertEqual(state.read_bytes(), before)

    def test_checkpoint_pass_requires_current_task_acceptance_before_writes(self):
        import test_idea_to_code_bundle as lifecycle_tests

        self.root = self.root / "checkpoint-project"
        self.root.mkdir()
        fixture = lifecycle_tests.BundleTest(methodName="runTest")
        fixture.root = self.root
        self.slug = fixture.init_bundle()
        self.bundle = self.root / ".idea-to-code" / self.slug
        fixture.write_ready_bundle(self.slug)
        (self.root / "candidate.py").write_text("print('candidate')\n", encoding="utf-8")
        (self.root / "result.txt").write_text("Observed acceptance outcome.\n", encoding="utf-8")
        self.cli("exploration", "render")
        self.cli("implementation", "show-ready", "--task", "TASK-1")
        self.cli("implementation", "enter-task", "--task", "TASK-1")
        self.record("acceptance-declare", self.declaration(1))
        args = ("checkpoint", "--milestone", "TASK-1 acceptance", "--delivered", "REQ-1 implementation candidate prepared",
                "--verified", "real-product-path actual acceptance records", "--next", "review complete evidence",
                "--focus", "TASK-1", "--gate", "acceptance", "--gate-status", "pass", "--covers", "REQ-1")
        protected = [self.bundle / name for name in ("state.json", "01-progress.md", "02-report.md")]
        before = {path.name: path.read_bytes() for path in protected}
        missing = self.cli(*args, expected=1)
        self.assertIn("missing acceptance evidence", missing.stdout + missing.stderr)
        self.assertEqual({path.name: path.read_bytes() for path in protected}, before)
        failed = self.evidence(1)
        failed["result"] = "fail"
        self.record("acceptance-evidence", failed)
        before = {path.name: path.read_bytes() for path in protected}
        failure = self.cli(*args, expected=1)
        self.assertIn("did not pass", failure.stdout + failure.stderr)
        self.assertEqual({path.name: path.read_bytes() for path in protected}, before)
        passed = self.evidence(1)
        passed["id"] = "EVID-RETEST"
        self.record("acceptance-evidence", passed)
        self.cli(*args)


if __name__ == "__main__":
    unittest.main()
