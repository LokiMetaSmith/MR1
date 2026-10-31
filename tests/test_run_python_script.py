#!/usr/bin/env python3
# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0
"""
test_run_python_script.py
=========================
Validates the `run_python.sh` virtual environment wrapper script:
- Correct execution and exit code forwarding.
- Argument passing (CLI flags, strings, evaluation flags).
- Working directory flexibility (from repo root and subdirectories like scripts/).
- Module resolution with PYTHONPATH configured to repository root (importing build123d and src).
"""

import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "run_python.sh"
SCRIPTS_DIR_SCRIPT = REPO_ROOT / "scripts" / "run_python.sh"


class TestRunPythonScript(unittest.TestCase):
    def test_script_exists_and_executable(self):
        self.assertTrue(SCRIPT_PATH.is_file(), "run_python.sh must exist in repository root")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "run_python.sh must be executable")
        self.assertTrue(SCRIPTS_DIR_SCRIPT.exists(), "scripts/run_python.sh must exist")
        self.assertTrue(os.access(SCRIPTS_DIR_SCRIPT, os.X_OK), "scripts/run_python.sh must be executable")

    def test_executes_simple_python_command(self):
        res = subprocess.run(
            [str(SCRIPT_PATH), "-c", "import sys; print('PYTHON_OK', sys.version_info.major)"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("PYTHON_OK 3", res.stdout)

    def test_imports_build123d_and_src_modules(self):
        res = subprocess.run(
            [
                str(SCRIPT_PATH),
                "-c",
                "import build123d; import src.constants; print('IMPORTS_SUCCESS')",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("IMPORTS_SUCCESS", res.stdout)

    def test_run_from_scripts_directory(self):
        # Reproduce the user's exact scenario:
        # loki@loki-omega:~/Projects/daemon-pore/scripts$ ./run_python.sh generate_footprint.py --help
        res = subprocess.run(
            [str(SCRIPTS_DIR_SCRIPT), "generate_footprint.py", "--help"],
            cwd=REPO_ROOT / "scripts",
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("generate_footprint.py", res.stdout)
        self.assertIn("--pins", res.stdout)

    def test_exit_code_forwarding(self):
        res = subprocess.run(
            [str(SCRIPT_PATH), "-c", "import sys; sys.exit(42)"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 42)


if __name__ == "__main__":
    unittest.main()
