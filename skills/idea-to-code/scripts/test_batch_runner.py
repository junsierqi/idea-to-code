#!/usr/bin/env python3
"""Chunked unittest runner for the idea-to-code skill."""

from __future__ import annotations

import ast
import subprocess
import sys
import time
from pathlib import Path


TEST_BATCH_PROFILE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "full": (),
    "quick": (
        "contract",
        "command_guide",
        "branch_map",
        "lifecycle_audit",
        "output_compliance_self_test",
        "install_parity",
        "test_batch",
    ),
    "output": (
        "output_compliance",
        "visible_output",
        "ready_output",
        "render_status",
        "formal_status",
        "transcript_audit",
    ),
    "lifecycle": (
        "lifecycle",
        "branch_map",
        "implementation_ready",
        "enter_task",
        "pre_edit",
        "lease",
        "delegation",
        "backlog",
        "verify",
        "finalize",
        "next_action",
    ),
}


def discover_unittest_methods(test_script: Path) -> list[str]:
    module_name = test_script.stem
    tree = ast.parse(test_script.read_text(encoding="utf-8"), filename=str(test_script))
    methods: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                methods.append(f"{module_name}.{node.name}.{item.name}")
    return methods


def filter_tests_by_profile(tests: list[str], profile: str) -> list[str]:
    keywords = TEST_BATCH_PROFILE_KEYWORDS[profile]
    if not keywords:
        return tests
    return [
        test
        for test in tests
        if any(keyword in test.lower() for keyword in keywords)
    ]


def run_test_batch(
    chunk_size: int,
    timeout_seconds: int,
    limit: int | None,
    profile: str = "full",
    slow_count: int = 3,
) -> int:
    if chunk_size <= 0:
        raise SystemExit("test-batch refused - --chunk-size must be greater than zero.")
    if timeout_seconds <= 0:
        raise SystemExit("test-batch refused - --timeout-seconds must be greater than zero.")
    if profile not in TEST_BATCH_PROFILE_KEYWORDS:
        raise SystemExit("test-batch refused - --profile must be one of: " + ", ".join(TEST_BATCH_PROFILE_KEYWORDS))
    if slow_count < 0:
        raise SystemExit("test-batch refused - --slow-count must be zero or greater.")
    test_script = Path(__file__).with_name("test_idea_to_code_bundle.py")
    discovered = discover_unittest_methods(test_script)
    tests = filter_tests_by_profile(discovered, profile)
    if limit is not None:
        if limit <= 0:
            raise SystemExit("test-batch refused - --limit must be greater than zero.")
        tests = tests[:limit]
    if not tests:
        raise SystemExit(f"test-batch refused - no unittest methods discovered for profile {profile} in {test_script}.")
    chunks = [tests[index:index + chunk_size] for index in range(0, len(tests), chunk_size)]
    print(f"test-batch: profile={profile} total_tests={len(tests)} chunk_size={chunk_size} chunks={len(chunks)}")
    timings: list[tuple[float, int, int, int]] = []
    for index, chunk in enumerate(chunks, start=1):
        first = (index - 1) * chunk_size + 1
        last = first + len(chunk) - 1
        command = [sys.executable, "-m", "unittest", *chunk]
        print(f"chunk {index}/{len(chunks)}: RUN tests {first}-{last}")
        started = time.perf_counter()
        result = subprocess.run(
            command,
            cwd=test_script.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        elapsed = time.perf_counter() - started
        timings.append((elapsed, index, first, last))
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
        if result.returncode != 0:
            print(f"chunk {index}/{len(chunks)}: FAIL tests {first}-{last}")
            return result.returncode
        print(f"chunk {index}/{len(chunks)}: PASS tests {first}-{last} elapsed={elapsed:.3f}s")
    if slow_count:
        print("test-batch: slow_chunks")
        for elapsed, index, first, last in sorted(timings, reverse=True)[:slow_count]:
            print(f"- chunk {index}/{len(chunks)} tests {first}-{last}: {elapsed:.3f}s")
    print(f"test-batch: PASS profile={profile} total_tests={len(tests)}")
    return 0
