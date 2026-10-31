#!/usr/bin/env bash
# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

# =============================================================================
# MR1 Nanopore Reader - Python Virtual Environment Wrapper Script
# =============================================================================
# Usage:
#   ./run_python.sh [python arguments / script]
# Examples:
#   ./run_python.sh scripts/generate_footprint.py --help
#   ./run_python.sh run_tests.py
#   ./run_python.sh -m unittest discover tests
#   ./run_python.sh -c "import build123d; print(build123d.__version__)"
#   ./run_python.sh    # Launches interactive Python REPL in venv
# =============================================================================

set -e

# Resolve target file if invoked via symlink
SOURCE="${BASH_SOURCE[0]}"
while [ -h "${SOURCE}" ]; do
    DIR="$(cd -P "$(dirname "${SOURCE}")" >/dev/null 2>&1 && pwd)"
    SOURCE="$(readlink "${SOURCE}")"
    [[ ${SOURCE} != /* ]] && SOURCE="${DIR}/${SOURCE}"
done
SCRIPT_DIR="$(cd -P "$(dirname "${SOURCE}")" >/dev/null 2>&1 && pwd)"

# Find repo root by looking for pyproject.toml or setup_env.sh
REPO_ROOT="${SCRIPT_DIR}"
while [ "${REPO_ROOT}" != "/" ] && [ ! -f "${REPO_ROOT}/setup_env.sh" ]; do
    REPO_ROOT="$(dirname "${REPO_ROOT}")"
done

if [ ! -f "${REPO_ROOT}/setup_env.sh" ]; then
    echo "[ERROR] Could not determine MR1 repository root." >&2
    exit 1
fi

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
