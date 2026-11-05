#!/usr/bin/env bash
# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

# =============================================================================
# MR1 Nanopore Reader — Automated EM & Electrostatics Execution Wrapper
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUN_PY="${SCRIPT_DIR}/run_python.sh"

"${RUN_PY}" "${REPO_ROOT}/simulations/em_board_analysis.py" "$@"
