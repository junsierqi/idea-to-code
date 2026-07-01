#!/usr/bin/env python3
"""Install or update the local idea-to-code Codex skill."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO_ROOT / "skills" / "idea-to-code"
DEFAULT_TARGET = Path.home() / ".codex" / "skills" / "idea-to-code"

EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def should_skip(path: Path) -> bool:
    return path.name in EXCLUDED_DIRS or path.suffix in EXCLUDED_SUFFIXES


def iter_source_files(source: Path) -> list[Path]:
    files: list[Path] = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if any(should_skip(part) for part in relative.parents if str(part) != "."):
            continue
        if should_skip(path):
            continue
        if path.is_file():
            files.append(relative)
    return sorted(files)


def iter_target_files(target: Path) -> list[Path]:
    if not target.exists():
        return []
    if not target.is_dir():
        raise ValueError(f"target exists and is not a directory: {target}")
    files: list[Path] = []
    for path in target.rglob("*"):
        relative = path.relative_to(target)
        if any(should_skip(part) for part in relative.parents if str(part) != "."):
            continue
        if should_skip(path):
            continue
        if path.is_file():
            files.append(relative)
    return sorted(files)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_installed_skill(source: Path, target: Path) -> bool:
    source = source.resolve()
    target = target.expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"source skill directory does not exist: {source}")
    if source == target or source in target.parents:
        raise ValueError("target must not be the source directory or inside it")

    source_files = iter_source_files(source)
    target_files = iter_target_files(target)
    source_set = set(source_files)
    target_set = set(target_files)
    missing = sorted(source_set - target_set)
    extra = sorted(target_set - source_set)
    different = sorted(
        relative
        for relative in source_set & target_set
        if file_sha256(source / relative) != file_sha256(target / relative)
    )

    print(f"Source: {source}")
    print(f"Target: {target}")
    print("Mode: check")
    print(f"Files: {len(source_files)}")
    print(f"Missing: {len(missing)}")
    for relative in missing:
        print(f"  missing: {relative.as_posix()}")
    print(f"Extra: {len(extra)}")
    for relative in extra:
        print(f"  extra: {relative.as_posix()}")
    print(f"Different: {len(different)}")
    for relative in different:
        print(f"  different: {relative.as_posix()}")

    ok = not missing and not extra and not different
    print(f"Parity: {'ok' if ok else 'failed'}")
    return ok


def copy_skill_tree(source: Path, destination: Path) -> int:
    files = iter_source_files(source)
    destination.mkdir(parents=True, exist_ok=True)
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    return len(files)


def install_skill(source: Path, target: Path, dry_run: bool) -> int:
    source = source.resolve()
    target = target.expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"source skill directory does not exist: {source}")
    if source == target or source in target.parents:
        raise ValueError("target must not be the source directory or inside it")

    files = iter_source_files(source)
    print(f"Source: {source}")
    print(f"Target: {target}")
    print(f"Mode: {'dry-run' if dry_run else 'install/update'}")
    print(f"Files: {len(files)}")

    if dry_run:
        return len(files)

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{target.name}-", dir=str(target.parent)) as tmp:
        staged = Path(tmp) / target.name
        copied = copy_skill_tree(source, staged)
        if target.exists():
            if not target.is_dir():
                raise ValueError(f"target exists and is not a directory: {target}")
            shutil.rmtree(target)
        staged.replace(target)
    print(f"Installed: {target}")
    return copied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or update the idea-to-code skill in the Codex skills directory."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Source skill directory. Defaults to skills/idea-to-code in this repository.",
    )
    parser.add_argument(
        "--target",
        default=str(DEFAULT_TARGET),
        help="Install target. Defaults to ~/.codex/skills/idea-to-code.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned install/update without writing files.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Verify the installed skill matches source files by path and SHA256 without writing files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.check:
            return 0 if check_installed_skill(Path(args.source), Path(args.target)) else 1
        install_skill(Path(args.source), Path(args.target), args.dry_run)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
