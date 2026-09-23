"""Typed delivery evidence kept in the bundle's existing local_records.

Builders read files but never execute commands or write state. The caller owns
locking, timestamps and ledger persistence. Reported test execution is explicitly
an attestation; hashes establish freshness, not truth or host-level enforcement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Iterable


ACTIONS = (
    "acceptance-declare", "acceptance-amend", "acceptance-evidence",
    "evolution-capture", "evolution-disposition", "evolution-activate",
    "evolution-observe",
)
VALIDATION_TYPES = {
    "real-product-path", "mock-only", "fixture-only", "source-only",
    "dom-only", "manual-inspection", "unverified",
}
DIAGNOSES = {
    "implementation-defect", "design-defect", "execution-noncompliance",
    "verification-mechanism-gap", "environment", "unconfirmed",
}
DISPOSITIONS = {
    "improve-skill", "repair-project", "enforce-existing-rule", "no-change", "defer",
}
EXCLUDED_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
REQUIRED_FIELDS = {
    "acceptance-declare": {"task_id", "requirement_ids", "object_id", "validation_type", "candidate_files", "expected", "expected_basis", "polarity"},
    "acceptance-amend": {"case_id", "reason", "task_id", "requirement_ids", "object_id", "validation_type", "candidate_files", "expected", "expected_basis", "polarity"},
    "acceptance-evidence": {"case_id", "declaration_id", "result", "validation_type", "candidate", "candidate_sha256", "artifacts", "provenance", "observed", "command", "environment", "plan_revision"},
    "evolution-capture": {"task_id", "requirement_ids", "fact", "evidence_refs", "hypotheses", "resume"},
    "evolution-disposition": {"incident_id", "diagnosis", "disposition", "reason", "evidence_refs"},
    "evolution-activate": {"incident_id", "disposition_id", "case_ids", "validation", "evidence_ids", "source_dir", "installed_dir", "source_manifest", "source_sha256", "effectiveness"},
    "evolution-observe": {"incident_id", "activation_id", "outcome", "evidence_refs", "note"},
}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _strings(value: object, name: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{name} must be a {'possibly empty ' if allow_empty else ''}list")
    values = [_text(item, name) for item in value]
    if len(set(values)) != len(values):
        raise ValueError(f"{name} contains duplicates")
    return values


def _choice(value: object, name: str, choices: set[str]) -> str:
    value = _text(value, name)
    if value not in choices:
        raise ValueError(f"invalid {name}: {value}")
    return value


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _contained(root: Path, value: str) -> tuple[str, Path]:
    path = Path(_text(value, "file path"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"file path must be relative and contained: {value}")
    resolved_root = root.resolve()
    resolved = (resolved_root / path).resolve()
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"file path escapes root: {value}") from exc
    if not relative.parts or resolved.is_dir():
        raise ValueError(f"file path is a directory: {value}")
    return path.as_posix(), resolved


def candidate_manifest(root: Path, files: list[str], require_exists: bool = False) -> dict:
    """Missing paths are explicit deletion tombstones, never silently omitted."""
    result = {}
    for value in _strings(files, "candidate files"):
        name, path = _contained(root, value)
        if name in result:
            raise ValueError(f"duplicate normalized path: {name}")
        if not path.exists():
            if require_exists:
                raise ValueError(f"evidence artifact does not exist: {name}")
            result[name] = None
        elif not path.is_file():
            raise ValueError(f"not a regular file: {name}")
        else:
            result[name] = _hash(path)
    return dict(sorted(result.items()))


def _shape_problem(record: dict) -> str | None:
    data = record.get("data")
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return "unsupported typed evidence schema"
    action = data.get("action")
    if action not in ACTIONS:
        return "unknown typed evidence action"
    expected_kind = "ACCEPTANCE" if action.startswith("acceptance-") else "EVOLUTION"
    if record.get("kind") != expected_kind:
        return "typed evidence kind/action mismatch"
    missing = REQUIRED_FIELDS[action] - set(data)
    if missing:
        return "malformed typed evidence; missing " + ", ".join(sorted(missing))
    for key in ("requirement_ids", "candidate_files", "case_ids", "evidence_ids", "evidence_refs", "hypotheses"):
        if key in data and (not isinstance(data[key], list) or any(not isinstance(item, str) for item in data[key])):
            return f"malformed typed evidence list: {key}"
    for key in ("candidate", "artifacts", "resume", "validation", "source_manifest", "improvement"):
        if key in data and not isinstance(data[key], dict):
            return f"malformed typed evidence object: {key}"
    if action == "evolution-disposition":
        if data.get("disposition") == "improve-skill" and "improvement" not in data:
            return "improvement disposition lacks task link"
        if data.get("resolved") and not data.get("case_ids"):
            return "verified disposition lacks acceptance cases"
    return None


def _records(status: dict, action: str | None = None) -> list[dict]:
    records = []
    for record in status.get("local_records", []):
        if record.get("kind") not in {"ACCEPTANCE", "EVOLUTION"} or _shape_problem(record):
            continue
        data = record["data"]
        if action is None or data.get("action") == action:
            records.append(record)
    return records


def _find(status: dict, record_id: str, action: str | None = None) -> dict:
    for record in _records(status, action):
        if record.get("id") == record_id:
            return record
    raise ValueError(f"unknown {action or 'typed'} record: {record_id}")


def _references(status: dict, values: object) -> list[str]:
    refs = _strings(values, "evidence_refs")
    known = {record.get("id") for record in status.get("local_records", [])}
    for ref in refs:
        if ref not in known:
            raise ValueError(f"unknown evidence reference: {ref}")
    return refs


def _requirements(status: dict, values: object) -> list[str]:
    refs = _strings(values, "requirement_ids")
    known = {item.get("id") for item in status.get("requirements", [])}
    for ref in refs:
        if ref not in known:
            raise ValueError(f"unknown requirement: {ref}")
    return refs


def _task(value: object, known_task_ids: Iterable[str]) -> str:
    task_id = _text(value, "task_id")
    if task_id not in known_task_ids:
        raise ValueError(f"unknown task: {task_id}")
    return task_id


def _case(status: dict, case_id: str) -> dict:
    latest = _find(status, case_id, "acceptance-declare")
    for record in _records(status, "acceptance-amend"):
        if record["data"].get("case_id") == case_id:
            latest = record
    return latest


def _case_evidence(status: dict, case_id: str) -> dict | None:
    records = [record for record in _records(status, "acceptance-evidence")
               if record["data"].get("case_id") == case_id]
    return records[-1] if records else None


def _case_problems(root: Path, status: dict, case_id: str) -> list[str]:
    case = _case(status, case_id)
    evidence = _case_evidence(status, case_id)
    if evidence is None:
        return [f"{case_id}: missing acceptance evidence"]
    data = evidence["data"]
    problems = []
    if data.get("declaration_id") != case["id"]:
        problems.append(f"{case_id}: evidence predates amended declaration")
    if data.get("plan_revision") != status.get("plan_revision"):
        problems.append(f"{case_id}: evidence predates current plan revision")
    if data.get("result") != "pass":
        problems.append(f"{case_id}: latest evidence did not pass")
    if data.get("validation_type") != case["data"].get("validation_type"):
        problems.append(f"{case_id}: evidence validation type does not match declaration")
    try:
        current = candidate_manifest(root, case["data"]["candidate_files"])
        if current != data.get("candidate") or _digest(current) != data.get("candidate_sha256"):
            problems.append(f"{case_id}: candidate evidence is stale")
        artifacts = data.get("artifacts", {})
        if not artifacts or candidate_manifest(root, list(artifacts), True) != artifacts:
            problems.append(f"{case_id}: evidence artifacts are stale or absent")
    except (ValueError, OSError) as exc:
        problems.append(f"{case_id}: {exc}")
    return problems


def acceptance_problems(root: Path, status: dict, task_id: str | None = None) -> list[str]:
    """Check every declared case in scope; an explicit task requires a case."""
    problems = []
    for record in status.get("local_records", []):
        if record.get("kind") in {"ACCEPTANCE", "EVOLUTION"}:
            shape_problem = _shape_problem(record)
            if shape_problem:
                problems.append(f"{record.get('id')}: {shape_problem}")
    cases = [case for case in _records(status, "acceptance-declare")
             if task_id is None or case["data"]["task_id"] == task_id]
    if task_id is not None and not cases:
        problems.append(f"{task_id}: missing declared acceptance case")
    for case in cases:
        try:
            problems.extend(_case_problems(root, status, case["id"]))
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"{case.get('id')}: malformed acceptance record: {exc}")
    return problems


def _linked_task(link: object) -> tuple[dict, dict, Path]:
    if not isinstance(link, dict):
        raise ValueError("linked task must be an object")
    root = Path(_text(link.get("root"), "linked root")).expanduser().resolve()
    slug = _text(link.get("bundle"), "linked bundle")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", slug):
        raise ValueError("invalid linked bundle slug")
    task = _text(link.get("task_id"), "linked task_id")
    target = (root / ".idea-to-code" / slug).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("linked bundle escapes root") from exc
    try:
        state = json.loads((target / "state.json").read_text(encoding="utf-8"))
        plan = (target / "00-idea.md").read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read linked task: {exc}") from exc
    if not isinstance(state, dict) or not re.search(r"^#{3,6}\s+" + re.escape(task) + r"(?:\s*:|\s+-|\s*$)", plan, re.M):
        raise ValueError(f"linked task absent from plan: {task}")
    return {"root": str(root), "bundle": slug, "task_id": task}, state, target


def _resume_snapshot(link: object) -> dict:
    result, state, target = _linked_task(link)
    if state.get("current_task_id") != result["task_id"]:
        raise ValueError("resume task is not the linked current task")
    if link.get("plan_revision") != state.get("plan_revision"):
        raise ValueError("resume plan revision does not match linked state")
    result.update({
        "plan_revision": state.get("plan_revision"),
        "plan_sha256": _hash(target / "00-idea.md"),
        "next_action": _text(link.get("next_action"), "resume next_action"),
    })
    try:
        pointer = json.loads((Path(result["root"]) / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read resume pointer: {exc}") from exc
    if not isinstance(pointer, dict) or pointer.get("slug") != result["bundle"]:
        raise ValueError("resume bundle is not active")
    return result


def resume_problems(root: Path, status: dict, incident_id: str, current: dict | None = None) -> list[str]:
    """Inspect original business pointer, not the improvement project's pointer."""
    try:
        incident = _find(status, incident_id, "evolution-capture")
        saved = incident["data"]["resume"]
        link, state, target = _linked_task(saved)
        if current is None:
            current = json.loads((Path(link["root"]) / ".idea-to-code" / "current.json").read_text(encoding="utf-8"))
        problems = []
        if not isinstance(current, dict) or current.get("slug") != link["bundle"]:
            problems.append(f"{incident_id}: original bundle pointer changed")
        if state.get("current_task_id") != saved["task_id"]:
            problems.append(f"{incident_id}: original task changed")
        if state.get("plan_revision") != saved["plan_revision"] or _hash(target / "00-idea.md") != saved["plan_sha256"]:
            problems.append(f"{incident_id}: original plan changed; reconcile before resuming")
        return problems
    except (ValueError, OSError, KeyError) as exc:
        return [f"{incident_id}: cannot verify resume point: {exc}"]


def _tree_manifest(directory: Path) -> dict:
    directory = directory.expanduser().resolve()
    if not directory.is_dir():
        raise ValueError(f"skill directory does not exist: {directory}")
    files = []
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if any(Path(part).suffix in EXCLUDED_SUFFIXES for part in relative.parts):
            continue
        if path.is_file():
            files.append(relative.as_posix())
    if not files:
        raise ValueError("skill manifest is empty")
    return candidate_manifest(directory, files, True)


def _activation_problems(root: Path, status: dict, record: dict) -> list[str]:
    data = record["data"]
    problems = []
    try:
        link, validation_status, _ = _linked_task(data["validation"])
    except (ValueError, KeyError) as exc:
        return [f"{record.get('id')}: activation validation task unavailable: {exc}"]
    validation_root = Path(link["root"])
    problems.extend(acceptance_problems(validation_root, validation_status, link["task_id"]))
    for case_id in data["case_ids"]:
        try:
            _case(validation_status, case_id)
        except ValueError as exc:
            problems.append(f"{record['id']}: activation case unavailable: {exc}")
        evidence = _case_evidence(validation_status, case_id)
        if evidence is None or evidence["id"] not in data["evidence_ids"]:
            problems.append(f"{record['id']}: activation evidence superseded")
    try:
        source = _tree_manifest(Path(data["source_dir"]))
        installed = _tree_manifest(Path(data["installed_dir"]))
        if source != data["source_manifest"] or installed != source:
            problems.append(f"{record['id']}: activation source/install manifest changed")
    except (ValueError, OSError) as exc:
        problems.append(f"{record['id']}: {exc}")
    return problems


def evolution_problems(root: Path, status: dict) -> list[str]:
    problems = []
    for incident in _records(status, "evolution-capture"):
        incident_id = incident["id"]
        dispositions = [record for record in _records(status, "evolution-disposition")
                        if record["data"]["incident_id"] == incident_id]
        if not dispositions:
            problems.append(f"{incident_id}: missing diagnosis and disposition")
            continue
        disposition = dispositions[-1]
        observations = [record for record in _records(status, "evolution-observe")
                        if record["data"]["incident_id"] == incident_id]
        records = status.get("local_records", [])
        unresolved_negative_observations = [
            observation for observation in observations
            if observation["data"]["outcome"] in {"ineffective", "false-positive"}
            and records.index(observation) > records.index(disposition)
        ]
        if unresolved_negative_observations:
            problems.append(f"{incident_id}: ineffective change requires renewed diagnosis")
        if disposition["data"]["disposition"] in {"repair-project", "enforce-existing-rule", "defer"}:
            if not disposition["data"].get("resolved"):
                problems.append(f"{incident_id}: disposition still needs verified resolution")
            else:
                for case_id in disposition["data"]["case_ids"]:
                    try:
                        problems.extend(_case_problems(root, status, case_id))
                    except (ValueError, KeyError, TypeError) as exc:
                        problems.append(f"{incident_id}: resolution case unavailable: {exc}")
        elif disposition["data"]["disposition"] == "improve-skill":
            activations = [record for record in _records(status, "evolution-activate")
                           if record["data"]["incident_id"] == incident_id
                           and record["data"]["disposition_id"] == disposition["id"]]
            if not activations:
                problems.append(f"{incident_id}: improvement not validated and activated")
            else:
                problems.extend(_activation_problems(root, status, activations[-1]))
    return problems


def build_record(root: Path, status: dict, action: str, payload: dict,
                 known_task_ids: Iterable[str]) -> dict:
    """Validate and construct one immutable record; caller appends under its lock."""
    if action not in ACTIONS or not isinstance(payload, dict):
        raise ValueError("unknown delivery action or invalid JSON object")
    record_id = _text(payload.get("id"), "id")
    if any(item.get("id") == record_id for item in status.get("local_records", [])):
        raise ValueError(f"duplicate local record: {record_id}")
    data = {"schema_version": 1, "action": action}
    covers = []
    if action in {"acceptance-declare", "acceptance-amend"}:
        if action == "acceptance-amend":
            case_id = _text(payload.get("case_id"), "case_id")
            previous = _case(status, case_id)["data"]
            data.update({"case_id": case_id, "reason": _text(payload.get("reason"), "amendment reason")})
            for key in ("task_id", "requirement_ids", "object_id"):
                if key in payload and payload[key] != previous[key]:
                    raise ValueError(f"amendment cannot silently change {key}")
            merged = dict(previous, **payload)
        else:
            merged = payload
        covers = _requirements(status, merged.get("requirement_ids"))
        files = _strings(merged.get("candidate_files"), "candidate_files")
        manifest = candidate_manifest(root, files)
        data.update({
            "task_id": _task(merged.get("task_id"), known_task_ids),
            "requirement_ids": covers,
            "object_id": _text(merged.get("object_id"), "object_id"),
            "validation_type": _choice(merged.get("validation_type"), "validation_type", VALIDATION_TYPES - {"unverified"}),
            "candidate_files": list(manifest),
            "expected": _text(merged.get("expected"), "expected"),
            "expected_basis": _text(merged.get("expected_basis"), "expected_basis"),
            "polarity": _choice(merged.get("polarity", "positive"), "polarity", {"positive", "negative"}),
        })
    elif action == "acceptance-evidence":
        case_id = _text(payload.get("case_id"), "case_id")
        case = _case(status, case_id)
        case_data = case["data"]
        validation_type = _choice(payload.get("validation_type"), "validation_type", VALIDATION_TYPES)
        if validation_type != case_data["validation_type"]:
            raise ValueError("evidence validation type does not match declaration")
        artifacts = candidate_manifest(root, _strings(payload.get("artifacts"), "artifacts"), True)
        candidate = candidate_manifest(root, case_data["candidate_files"])
        covers = case_data["requirement_ids"]
        data.update({
            "case_id": case_id, "declaration_id": case["id"],
            "plan_revision": status.get("plan_revision"),
            "result": _choice(payload.get("result"), "result", {"pass", "fail"}),
            "validation_type": validation_type,
            "candidate": candidate, "candidate_sha256": _digest(candidate),
            "artifacts": artifacts, "provenance": "reported",
            "observed": _text(payload.get("observed"), "observed"),
            "command": _text(payload.get("command"), "command"),
            "environment": _text(payload.get("environment"), "environment"),
        })
    elif action == "evolution-capture":
        covers = _requirements(status, payload.get("requirement_ids"))
        data.update({
            "task_id": _task(payload.get("task_id"), known_task_ids),
            "requirement_ids": covers,
            "fact": _text(payload.get("fact"), "fact"),
            "evidence_refs": _references(status, payload.get("evidence_refs")),
            "hypotheses": _strings(payload.get("hypotheses", []), "hypotheses", True),
            "resume": _resume_snapshot(payload.get("resume")),
        })
    else:
        incident_id = _text(payload.get("incident_id"), "incident_id")
        incident = _find(status, incident_id, "evolution-capture")
        covers = incident["covers"]
        data["incident_id"] = incident_id
        if action == "evolution-disposition":
            disposition = _choice(payload.get("action"), "disposition", DISPOSITIONS)
            diagnosis = _choice(payload.get("diagnosis"), "diagnosis", DIAGNOSES)
            if diagnosis == "unconfirmed" and disposition != "defer":
                raise ValueError("unconfirmed diagnosis can only be deferred")
            data.update({"diagnosis": diagnosis, "disposition": disposition,
                         "reason": _text(payload.get("reason"), "reason"),
                         "evidence_refs": _references(status, payload.get("evidence_refs"))})
            if disposition == "improve-skill":
                data["improvement"] = _linked_task(payload.get("improvement"))[0]
            if "resolved" in payload and not isinstance(payload["resolved"], bool):
                raise ValueError("resolved must be boolean")
            if payload.get("resolved"):
                if disposition not in {"repair-project", "enforce-existing-rule"}:
                    raise ValueError("verified resolution applies to repair or rule enforcement")
                case_ids = _strings(payload.get("case_ids"), "case_ids")
                for case_id in case_ids:
                    problems = _case_problems(root, status, case_id)
                    if problems:
                        raise ValueError("resolution refused: " + "; ".join(problems))
                data.update({"resolved": True, "case_ids": case_ids})
        elif action == "evolution-activate":
            dispositions = [record for record in _records(status, "evolution-disposition")
                            if record["data"]["incident_id"] == incident_id]
            if not dispositions or dispositions[-1]["data"]["disposition"] != "improve-skill":
                raise ValueError("activation requires an improve-skill disposition")
            disposition = dispositions[-1]
            validation_link, validation_status, _ = _linked_task(disposition["data"]["improvement"])
            validation_root = Path(validation_link["root"])
            case_ids = _strings(payload.get("case_ids"), "case_ids")
            cases = [_case(validation_status, case_id) for case_id in case_ids]
            if {case["data"]["polarity"] for case in cases} != {"positive", "negative"}:
                raise ValueError("activation requires positive and negative accepted cases")
            for case in cases:
                if case["data"]["task_id"] != disposition["data"]["improvement"]["task_id"]:
                    raise ValueError("activation case does not belong to improvement task")
            problems = acceptance_problems(validation_root, validation_status, validation_link["task_id"])
            if problems:
                raise ValueError("activation refused: " + "; ".join(problems))
            source_dir = Path(_text(payload.get("source_dir"), "source_dir")).expanduser().resolve()
            installed_dir = Path(_text(payload.get("installed_dir"), "installed_dir")).expanduser().resolve()
            if source_dir == installed_dir:
                raise ValueError("source and installed directories must differ")
            source = _tree_manifest(source_dir)
            if source != _tree_manifest(installed_dir):
                raise ValueError("source and installed skill manifests differ")
            try:
                source_dir.relative_to(validation_root)
            except ValueError as exc:
                raise ValueError("source skill must be inside evidence root") from exc
            evidence = [_case_evidence(validation_status, case_id) for case_id in case_ids]
            for item in evidence:
                for name, digest in source.items():
                    relative = (source_dir / name).relative_to(validation_root).as_posix()
                    if item["data"]["candidate"].get(relative) != digest:
                        raise ValueError(f"activation evidence does not cover source file: {relative}")
            data.update({"disposition_id": disposition["id"], "case_ids": case_ids,
                         "validation": validation_link,
                         "evidence_ids": [item["id"] for item in evidence],
                         "source_dir": str(source_dir), "installed_dir": str(installed_dir),
                         "source_manifest": source, "source_sha256": _digest(source),
                         "effectiveness": "not-yet-observed"})
        elif action == "evolution-observe":
            activations = [record for record in _records(status, "evolution-activate")
                           if record["data"]["incident_id"] == incident_id]
            if not activations:
                raise ValueError("effectiveness observation requires an activation")
            data.update({"activation_id": activations[-1]["id"],
                         "outcome": _choice(payload.get("outcome"), "outcome", {"effective", "ineffective", "false-positive", "insufficient"}),
                         "evidence_refs": _references(status, payload.get("evidence_refs")),
                         "note": _text(payload.get("note"), "note")})
    return {"id": record_id, "kind": "ACCEPTANCE" if action.startswith("acceptance-") else "EVOLUTION",
            "text": action + ": " + record_id, "covers": list(covers), "data": data}
