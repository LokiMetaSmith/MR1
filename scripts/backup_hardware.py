# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

"""
scripts/backup_hardware.py
==========================
Automatic snapshot utility for KiCad schematics and PCB layout files.

Creates timestamped snapshots in an untracked local backup directory
(e.g., .hardware_backups/ or Amplifier/*-backups/) before any script performs
write operations to .kicad_pcb or .kicad_sch.

Usage:
    ./scripts/run_python.sh scripts/backup_hardware.py [--label <tag>] [--board <name>]
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

BACKUP_ROOT = REPO_ROOT / ".hardware_backups"

HARDWARE_FILES = [
    # Amplifier Cartridge
    REPO_ROOT / "Amplifier" / "Amplifier.kicad_pcb",
    REPO_ROOT / "Amplifier" / "Amplifier.kicad_sch",
    REPO_ROOT / "Amplifier" / "Amplifier.kicad_pro",
    # PTFE Interposer
    REPO_ROOT / "Interposer" / "Interposer.kicad_pcb",
    REPO_ROOT / "Interposer" / "Interposer.kicad_pro",
    # Main Controller
    REPO_ROOT / "MR1" / "MR1.kicad_pcb",
    REPO_ROOT / "MR1" / "MR1.kicad_sch",
    REPO_ROOT / "MR1" / "MR1.kicad_pro",
    # Pump Board
    REPO_ROOT / "Pump" / "Pump.kicad_pcb",
    REPO_ROOT / "Pump" / "Pump.kicad_sch",
    REPO_ROOT / "Pump" / "Pump.kicad_pro",
]


def create_snapshot(label: Optional[str] = None, files: Optional[List[Path]] = None) -> Path:
    """Creates a timestamped snapshot of all existing hardware design files."""
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"snapshot_{now}" + (f"_{label}" if label else "")
    dest_dir = BACKUP_ROOT / dir_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    targets = files if files is not None else HARDWARE_FILES
    copied = 0
    for file_path in targets:
        if file_path.exists():
            rel_path = file_path.relative_to(REPO_ROOT)
            out_file = dest_dir / rel_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, out_file)
            copied += 1

    manifest = dest_dir / "snapshot_manifest.txt"
    manifest.write_text(
        f"Timestamp: {now}\n"
        f"Label: {label or 'auto'}\n"
        f"Copied files: {copied}\n",
        encoding="utf-8",
    )
    print(f"[BACKUP] Preserved {copied} hardware design files to:\n         {dest_dir}")
    return dest_dir


def main():
    parser = argparse.ArgumentParser(description="Snapshot hardware schematic and layout files.")
    parser.add_argument("--label", "-l", type=str, default=None, help="Descriptive label for the snapshot")
    args = parser.parse_args()

    create_snapshot(label=args.label)


if __name__ == "__main__":
    main()
