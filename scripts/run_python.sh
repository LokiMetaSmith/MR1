#!/usr/bin/env bash
# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

# =============================================================================
# MR1 Nanopore Reader - Python Virtual Environment Wrapper Script
# =============================================================================
# Usage:
#   From scripts/ directory:
#     ./run_python.sh generate_footprint.py --help
#   From repository root:
#     ./scripts/run_python.sh scripts/generate_footprint.py --help
#     ./scripts/run_python.sh run_tests.py
#     ./scripts/run_python.sh -m unittest discover tests
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VENV_DIR="${REPO_ROOT}/.venv"

# Detect Python interpreter in virtual environment
if [ -f "${VENV_DIR}/bin/python" ]; then
    PYTHON_BIN="${VENV_DIR}/bin/python"
elif [ -f "${VENV_DIR}/Scripts/python.exe" ]; then
    PYTHON_BIN="${VENV_DIR}/Scripts/python.exe"
else
    # Auto-bootstrap virtual environment if missing
    echo ">> Virtual environment (.venv) not found. Running setup_env.sh..."
    bash "${REPO_ROOT}/setup_env.sh"
    if [ -f "${VENV_DIR}/bin/python" ]; then
        PYTHON_BIN="${VENV_DIR}/bin/python"
    elif [ -f "${VENV_DIR}/Scripts/python.exe" ]; then
        PYTHON_BIN="${VENV_DIR}/Scripts/python.exe"
    else
        echo "[ERROR] Failed to locate Python in virtual environment at ${VENV_DIR}." >&2
        exit 1
    fi
fi

# Ensure PYTHONPATH contains repository root so modules in src/ and scripts/ resolve cleanly
if [ -z "${PYTHONPATH}" ]; then
    export PYTHONPATH="${REPO_ROOT}"
else
    export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH}"
fi

# Execute Python in the virtual environment, passing all arguments and preserving exit code
exec "${PYTHON_BIN}" "$@"
