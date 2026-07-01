#!/usr/bin/env python3
"""Focused tests for the repository skill installer."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_skill


class InstallSkillCheckTest(unittest.TestCase):
    def make_source(self, root: Path) -> Path:
        source = root / "source"
        (source / "scripts").mkdir(parents=True)
        (source / "SKILL.md").write_text("skill\n", encoding="utf-8")
        (source / "scripts" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
        (source / "scripts" / "__pycache__").mkdir()
        (source / "scripts" / "__pycache__" / "tool.pyc").write_bytes(b"ignored")
        return source

    def test_check_installed_skill_accepts_matching_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            target = root / "target"
            install_skill.copy_skill_tree(source, target)

            output = StringIO()
            with redirect_stdout(output):
                ok = install_skill.check_installed_skill(source, target)

            self.assertTrue(ok)
            text = output.getvalue()
            self.assertIn("Mode: check", text)
            self.assertIn("Files: 2", text)
            self.assertIn("Missing: 0", text)
            self.assertIn("Extra: 0", text)
            self.assertIn("Different: 0", text)
            self.assertIn("Parity: ok", text)

    def test_check_installed_skill_reports_missing_extra_and_different_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            target = root / "target"
            install_skill.copy_skill_tree(source, target)
            (target / "SKILL.md").write_text("changed\n", encoding="utf-8")
            (target / "scripts" / "tool.py").unlink()
            (target / "extra.txt").write_text("extra\n", encoding="utf-8")

            output = StringIO()
            with redirect_stdout(output):
                ok = install_skill.check_installed_skill(source, target)

            self.assertFalse(ok)
            text = output.getvalue()
            self.assertIn("missing: scripts/tool.py", text)
            self.assertIn("extra: extra.txt", text)
            self.assertIn("different: SKILL.md", text)
            self.assertIn("Parity: failed", text)


if __name__ == "__main__":
    unittest.main()
