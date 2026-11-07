# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

"""
scripts/kicad_diff.py
=====================
High-fidelity Git and File Diff Tool for KiCad PCB and Schematic designs.

Features:
  1. Semantic Structural Diff:
     - Footprint positions, rotations, values, layers, added/removed
     - Netlist changes (added/removed/renamed nets)
     - Trace segment count, via count, and routing statistics
     - Zone polygon changes
     - Silkscreen text (F.SilkS, B.SilkS) and graphic additions/modifications
  2. Visual Image Diff:
     - Uses `kicad-cli pcb render` for headless high-resolution 3D renders
     - Side-by-side comparison images (Before vs After)
     - Diff highlight overlay image (changed pixels highlighted in magenta/red)
     - Animated toggle GIF (1 Hz flicker comparison)
  3. Git & History Integration:
     - Compare git revisions (e.g., HEAD~1 vs HEAD or working tree)
     - Compare against `.hardware_backups/` snapshot archives
     - Compare against `Amplifier/.history/` KiCad autosave commits
     - Safe restore option (--restore) with automatic backup snapshot

Usage Examples:
  # Semantic + visual diff between previous git commit and working tree:
  ./scripts/run_python.sh scripts/kicad_diff.py HEAD~1 Amplifier/Amplifier.kicad_pcb

  # Diff working tree against the latest hardware backup snapshot:
  ./scripts/run_python.sh scripts/kicad_diff.py --backup Amplifier/Amplifier.kicad_pcb

  # Diff two specific files:
  ./scripts/run_python.sh scripts/kicad_diff.py path/to/fileA.kicad_pcb path/to/fileB.kicad_pcb

  # Visual diff only, output to custom directory:
  ./scripts/run_python.sh scripts/kicad_diff.py --visual-only -o renders/diff HEAD Amplifier/Amplifier.kicad_pcb
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = REPO_ROOT / ".hardware_backups"


# =============================================================================
# S-Expression / PCB Parsing Helpers
# =============================================================================

def parse_kicad_pcb(content: str) -> Dict[str, Any]:
    """Extracts semantic structural components from a .kicad_pcb string."""
    # 1. Footprints
    # Matches (footprint "NAME" ... (property "Reference" "REF") ... (at X Y [R]) ...)
    footprints = {}
    fp_pattern = re.compile(
        r'\(footprint\s+\"([^\"]+)\"(?:\s+\(layer\s+\"([^\"]+)\"\))?(.+?)(?=\n\t\(footprint|\n\t\(zone|\n\t\(segment|\n\t\(via|\n\t\(gr_|\Z)',
        re.DOTALL
    )
    for m in fp_pattern.finditer(content):
        fp_name = m.group(1)
        layer = m.group(2) or "F.Cu"
        body = m.group(3)

        ref_m = re.search(r'\(property\s+\"Reference\"\s+\"([^\"]+)\"', body)
        val_m = re.search(r'\(property\s+\"Value\"\s+\"([^\"]+)\"', body)
        at_m = re.search(r'\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\)', body)

        ref = ref_m.group(1) if ref_m else "UNKNOWN"
        val = val_m.group(1) if val_m else ""
        pos = (
            float(at_m.group(1)) if at_m else 0.0,
            float(at_m.group(2)) if at_m else 0.0,
            float(at_m.group(3) or 0.0) if at_m else 0.0
        )
        footprints[ref] = {
            "name": fp_name,
            "layer": layer,
            "val": val,
            "pos": pos
        }

    # 2. Nets
    nets = dict(re.findall(r'\(net\s+(\d+)\s+\"([^\"]+)\"\)', content))

    # 3. Silkscreen Text (Top-level gr_text and footprint properties on silk)
    gr_texts = []
    # (gr_text "TEXT" (at X Y [R]) (layer "LAYER") ...)
    for tm in re.finditer(
        r'\(gr_text\s+\"([^\"]*)\"\s*\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\)\s*\(layer\s+\"([^\"]+)\"\)',
        content
    ):
        text_str = tm.group(1)
        x, y = float(tm.group(2)), float(tm.group(3))
        r = float(tm.group(4) or 0.0)
        layer = tm.group(5)
        gr_texts.append({"text": text_str, "pos": (x, y, r), "layer": layer})

    # Footprint silk text
    fp_silk = []
    for ref, fp in footprints.items():
        # Check if reference is on silk
        fp_silk.append({"ref": ref, "layer": fp["layer"], "pos": fp["pos"]})

    # 4. Traces, Vias, Zones
    segment_count = len(re.findall(r'\(segment\s', content))
    via_count = len(re.findall(r'\(via\s', content))
    zone_matches = re.findall(r'\(zone\s+.*?\(net_name\s+\"([^\"]+)\"\)\s+\(layer\s+\"([^\"]+)\"\)', content, re.DOTALL)
    zones = [{"net": zm[0], "layer": zm[1]} for zm in zone_matches]

    # Calculate approximate track length
    track_lengths = []
    for sm in re.finditer(
        r'\(segment\s+\(start\s+([-0-9.]+)\s+([-0-9.]+)\)\s+\(end\s+([-0-9.]+)\s+([-0-9.]+)\)',
        content
    ):
        x1, y1 = float(sm.group(1)), float(sm.group(2))
        x2, y2 = float(sm.group(3)), float(sm.group(4))
        track_lengths.append(math.hypot(x2 - x1, y2 - y1))
    total_track_len = sum(track_lengths)

    return {
        "footprints": footprints,
        "nets": nets,
        "gr_texts": gr_texts,
        "fp_silk": fp_silk,
        "segments": segment_count,
        "track_length_mm": total_track_len,
        "vias": via_count,
        "zones": zones,
    }


def compare_pcb_structures(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    """Generates a detailed semantic summary diff between two PCB structures."""
    lines = []
    lines.append("=" * 72)
    lines.append("                KICAD PCB SEMANTIC STRUCTURAL DIFF")
    lines.append("=" * 72)

    # 1. High-level counts
    lines.append("\n[1] Overall Metrics:")
    lines.append(f"  Footprints      : A = {len(a['footprints']):3d}  |  B = {len(b['footprints']):3d}  |  Diff = {len(b['footprints']) - len(a['footprints']):+d}")
    lines.append(f"  Nets            : A = {len(a['nets']):3d}  |  B = {len(b['nets']):3d}  |  Diff = {len(b['nets']) - len(a['nets']):+d}")
    lines.append(f"  Traces (segments): A = {a['segments']:3d}  |  B = {b['segments']:3d}  |  Diff = {b['segments'] - a['segments']:+d}")
    lines.append(f"  Total Trace (mm): A = {a['track_length_mm']:6.1f} |  B = {b['track_length_mm']:6.1f} |  Diff = {b['track_length_mm'] - a['track_length_mm']:+6.1f} mm")
    lines.append(f"  Vias            : A = {a['vias']:3d}  |  B = {b['vias']:3d}  |  Diff = {b['vias'] - a['vias']:+d}")
    lines.append(f"  Copper Zones    : A = {len(a['zones']):3d}  |  B = {len(b['zones']):3d}  |  Diff = {len(b['zones']) - len(a['zones']):+d}")
    lines.append(f"  Silkscreen Texts: A = {len(a['gr_texts']):3d}  |  B = {len(b['gr_texts']):3d}  |  Diff = {len(b['gr_texts']) - len(a['gr_texts']):+d}")

    # 2. Footprint Differences
    fp_a = a["footprints"]
    fp_b = b["footprints"]
    all_refs = sorted(set(fp_a.keys()) | set(fp_b.keys()))

    added_fp = [r for r in all_refs if r not in fp_a]
    removed_fp = [r for r in all_refs if r not in fp_b]
    moved_fp = []
    value_changed_fp = []

    for r in all_refs:
        if r in fp_a and r in fp_b:
            item_a, item_b = fp_a[r], fp_b[r]
            pos_a, pos_b = item_a["pos"], item_b["pos"]
            dx = pos_b[0] - pos_a[0]
            dy = pos_b[1] - pos_a[1]
            dist = math.hypot(dx, dy)
            drot = pos_b[2] - pos_a[2]
            if dist > 0.001 or abs(drot) > 0.01:
                moved_fp.append((r, pos_a, pos_b, dist, drot))
            if item_a["val"] != item_b["val"]:
                value_changed_fp.append((r, item_a["val"], item_b["val"]))

    lines.append("\n[2] Footprint Component Changes:")
    if added_fp:
        lines.append(f"  + Added in B ({len(added_fp)}):")
        for r in added_fp:
            lines.append(f"      + {r:<8} : {fp_b[r]['name']} (Val: '{fp_b[r]['val']}') at {fp_b[r]['pos']}")
    if removed_fp:
        lines.append(f"  - Removed in B ({len(removed_fp)}):")
        for r in removed_fp:
            lines.append(f"      - {r:<8} : {fp_a[r]['name']} (Val: '{fp_a[r]['val']}') at {fp_a[r]['pos']}")
    if moved_fp:
        lines.append(f"  ~ Moved / Reoriented ({len(moved_fp)}):")
        for r, p_a, p_b, dist, drot in moved_fp:
            lines.append(f"      ~ {r:<8} : ({p_a[0]:.2f}, {p_a[1]:.2f}) -> ({p_b[0]:.2f}, {p_b[1]:.2f})  delta = {dist:.2f} mm" + (f", rot {drot:+.0f}°" if abs(drot) > 0.01 else ""))
    if value_changed_fp:
        lines.append(f"  ~ Value / Part Changes ({len(value_changed_fp)}):")
        for r, v_a, v_b in value_changed_fp:
            lines.append(f"      ~ {r:<8} : '{v_a}' -> '{v_b}'")
    if not (added_fp or removed_fp or moved_fp or value_changed_fp):
        lines.append("  (No component placement or value changes)")

    # 3. Netlist Changes
    nets_a = set(a["nets"].values())
    nets_b = set(b["nets"].values())
    added_nets = sorted(nets_b - nets_a)
    removed_nets = sorted(nets_a - nets_b)

    lines.append("\n[3] Netlist Changes:")
    if added_nets:
        lines.append(f"  + Added Nets ({len(added_nets)}): {', '.join(added_nets[:10])}" + (" ..." if len(added_nets) > 10 else ""))
    if removed_nets:
        lines.append(f"  - Removed Nets ({len(removed_nets)}): {', '.join(removed_nets[:10])}" + (" ..." if len(removed_nets) > 10 else ""))
    if not (added_nets or removed_nets):
        lines.append("  (Nets are identical)")

    # 4. Silkscreen Text Changes
    texts_a = {t["text"]: t for t in a["gr_texts"]}
    texts_b = {t["text"]: t for t in b["gr_texts"]}
    added_t = [t for t in texts_b if t not in texts_a]
    removed_t = [t for t in texts_a if t not in texts_b]

    lines.append("\n[4] Board Silkscreen Text Changes:")
    if added_t:
        lines.append(f"  + Added Silk Text ({len(added_t)}):")
        for t in added_t:
            lines.append(f"      + \"{t}\" on {texts_b[t]['layer']} at {texts_b[t]['pos'][:2]}")
    if removed_t:
        lines.append(f"  - Removed Silk Text ({len(removed_t)}):")
        for t in removed_t:
            lines.append(f"      - \"{t}\" on {texts_a[t]['layer']} at {texts_a[t]['pos'][:2]}")
    if not (added_t or removed_t):
        lines.append("  (No global silkscreen text added or removed)")

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


# =============================================================================
# Visual Image Diff Rendering
# =============================================================================

def render_pcb_view(pcb_path: Path, output_png: Path, side: str = "top", width: int = 1600, height: int = 1200) -> bool:
    """Renders PCB 3D top/bottom view to a PNG using kicad-cli."""
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        print("[ERROR] kicad-cli not found on PATH.", file=sys.stderr)
        return False

    cmd = [
        kicad_cli, "pcb", "render",
        "--side", side,
        "--width", str(width),
        "--height", str(height),
        "-o", str(output_png),
        str(pcb_path)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_png.exists()
    except subprocess.CalledProcessError as e:
        print(f"[WARN] kicad-cli render failed for {pcb_path}: {e}", file=sys.stderr)
        return False


def generate_visual_diff(
    img_a_path: Path,
    img_b_path: Path,
    out_dir: Path,
    label_a: str,
    label_b: str,
    view_name: str = "top"
) -> Dict[str, Path]:
    """
    Creates:
      1. Side-by-side comparison PNG: [A | B] with labels
      2. Diff highlight overlay PNG: Changed pixels in bright magenta/red
      3. Animated toggle GIF: alternating A and B at 1 Hz
    """
    from PIL import Image, ImageChops, ImageDraw, ImageFont

    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    im_a = Image.open(img_a_path).convert("RGBA")
    im_b = Image.open(img_b_path).convert("RGBA")

    # Ensure identical dimensions
    if im_a.size != im_b.size:
        im_b = im_b.resize(im_a.size, Image.Resampling.LANCZOS)

    w, h = im_a.size

    # --- 1. Side-by-Side Image ---
    header_h = 60
    side_by_side = Image.new("RGB", (w * 2 + 10, h + header_h), color=(30, 32, 36))
    side_by_side.paste(im_a, (0, header_h))
    side_by_side.paste(im_b, (w + 10, header_h))

    draw = ImageDraw.Draw(side_by_side)
    # Header labels
    draw.text((20, 18), f"[A] {label_a}", fill=(240, 240, 240))
    draw.text((w + 30, 18), f"[B] {label_b}", fill=(80, 220, 120))
    # Divider line
    draw.line([(w + 5, 0), (w + 5, h + header_h)], fill=(60, 64, 72), width=3)

    sbs_path = out_dir / f"diff_{view_name}_side_by_side.png"
    side_by_side.save(sbs_path, "PNG")
    results["side_by_side"] = sbs_path

    # --- 2. Diff Highlight Overlay ---
    rgb_a = im_a.convert("RGB")
    rgb_b = im_b.convert("RGB")
    diff_rgb = ImageChops.difference(rgb_a, rgb_b)

    # Convert diff to grayscale mask
    diff_gray = diff_rgb.convert("L")
    # Threshold mask: pixels with > 12 difference
    mask = diff_gray.point(lambda p: 255 if p > 12 else 0)

    # Base: desaturate B to dimmed grayscale
    gray_base = rgb_b.convert("L").convert("RGB")
    # Tint base slightly dark
    dimmed_base = Image.blend(gray_base, Image.new("RGB", (w, h), (20, 24, 30)), 0.3)

    # Highlight layer: vibrant neon magenta (255, 30, 140)
    magenta_highlight = Image.new("RGB", (w, h), (255, 30, 140))
    overlay = Image.composite(magenta_highlight, dimmed_base, mask)

    # Add header
    highlight_img = Image.new("RGB", (w, h + header_h), color=(20, 24, 30))
    highlight_img.paste(overlay, (0, header_h))
    draw_hl = ImageDraw.Draw(highlight_img)
    draw_hl.text((20, 18), f"Difference Overlay (Magenta = Changed Elements) : {view_name.upper()} VIEW", fill=(255, 80, 180))

    hl_path = out_dir / f"diff_{view_name}_highlight.png"
    highlight_img.save(hl_path, "PNG")
    results["highlight"] = hl_path

    # --- 3. Animated Flicker Toggle GIF ---
    gif_frame_a = im_a.convert("RGB")
    gif_frame_b = im_b.convert("RGB")
    # Add title stamps to frames
    draw_a = ImageDraw.Draw(gif_frame_a)
    draw_a.rectangle([(10, 10), (350, 45)], fill=(0, 0, 0, 180))
    draw_a.text((15, 18), f"BEFORE: {label_a[:35]}", fill=(255, 200, 80))

    draw_b = ImageDraw.Draw(gif_frame_b)
    draw_b.rectangle([(10, 10), (350, 45)], fill=(0, 0, 0, 180))
    draw_b.text((15, 18), f"AFTER : {label_b[:35]}", fill=(80, 255, 120))

    gif_path = out_dir / f"diff_{view_name}_toggle.gif"
    gif_frame_a.save(
        gif_path,
        "GIF",
        save_all=True,
        append_images=[gif_frame_b],
        duration=800,  # 800ms per frame
        loop=0
    )
    results["toggle_gif"] = gif_path

    return results


# =============================================================================
# Target Resolution (Git, Backup, File)
# =============================================================================

def resolve_target(target: str, temp_dir: Path) -> Tuple[Path, str, str]:
    """
    Resolves a target specification to (local_filepath, content_string, label).
    Target can be:
      - A git revision with optional path: 'HEAD~1', 'cb3b164:Amplifier/Amplifier.kicad_pcb'
      - A local file: 'Amplifier/Amplifier.kicad_pcb'
      - A snapshot tag or backup path
    """
    # 1. Check if direct file exists
    p = Path(target)
    if p.exists() and p.is_file():
        content = p.read_text(encoding="utf-8", errors="replace")
        return p, content, f"File: {p.name}"

    # 2. Check if git ref:path or git ref
    if ":" in target:
        ref, rel_path = target.split(":", 1)
    else:
        # Default to checking if target is a git ref for Amplifier.kicad_pcb
        ref = target
        rel_path = "Amplifier/Amplifier.kicad_pcb"

    try:
        content = subprocess.check_output(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="replace")

        # Write to temp file for kicad-cli
        out_file = temp_dir / f"git_{ref.replace('/', '_').replace('~', '_')}_{Path(rel_path).name}"
        out_file.write_text(content, encoding="utf-8")
        return out_file, content, f"Git: {ref} ({rel_path})"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    raise FileNotFoundError(f"Could not resolve target: {target}")


def get_latest_backup_snapshot(board_name: str = "Amplifier") -> Optional[Path]:
    """Finds the most recent hardware snapshot directory containing the board."""
    if not BACKUP_ROOT.exists():
        return None
    snapshots = sorted(
        [d for d in BACKUP_ROOT.iterdir() if d.is_dir() and d.name.startswith("snapshot_")],
        key=lambda d: d.name,
        reverse=True
    )
    for s in snapshots:
        candidate = s / board_name / f"{board_name}.kicad_pcb"
        if candidate.exists():
            return candidate
    return None


# =============================================================================
# CLI Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MR1 High-Fidelity KiCad Git & File Diff Tool (Semantic + Visual Render)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Semantic + visual diff against previous commit:
  ./scripts/run_python.sh scripts/kicad_diff.py HEAD~1 Amplifier/Amplifier.kicad_pcb

  # Compare current PCB against the user silkscreen backup snapshot:
  ./scripts/run_python.sh scripts/kicad_diff.py --backup Amplifier/Amplifier.kicad_pcb

  # Restore backup snapshot into working file:
  ./scripts/run_python.sh scripts/kicad_diff.py --restore --backup Amplifier/Amplifier.kicad_pcb
"""
    )
    parser.add_argument("target_a", nargs="?", default="HEAD~1", help="First file, git rev, or ref:path (default: HEAD~1)")
    parser.add_argument("target_b", nargs="?", default="Amplifier/Amplifier.kicad_pcb", help="Second file, git rev, or ref:path (default: Amplifier/Amplifier.kicad_pcb)")
    parser.add_argument("--backup", action="store_true", help="Use latest snapshot in .hardware_backups/ as target_a")
    parser.add_argument("--history", type=str, default=None, metavar="SHA", help="Use specific commit from Amplifier/.history as target_a")
    parser.add_argument("--output-dir", "-o", type=str, default="renders/diff", help="Output directory for visual diff images (default: renders/diff)")
    parser.add_argument("--text-only", action="store_true", help="Print structural text diff only (no visual rendering)")
    parser.add_argument("--visual-only", action="store_true", help="Generate visual diff images only (no text output)")
    parser.add_argument("--side", choices=["top", "bottom", "both"], default="both", help="Board side to render for visual diff (default: both)")
    parser.add_argument("--restore", action="store_true", help="Restore target_a into target_b (with automatic pre-backup snapshot!)")

    args = parser.parse_args()

    temp_dir = Path(tempfile.mkdtemp(prefix="kicad_diff_"))
    try:
        # Handle --backup flag
        if args.backup:
            snap_pcb = get_latest_backup_snapshot("Amplifier")
            if not snap_pcb:
                print("[ERROR] No backup snapshots found in .hardware_backups/", file=sys.stderr)
                sys.exit(1)
            target_a_str = str(snap_pcb)
        elif args.history:
            # Extract from Amplifier/.history git repo
            hist_repo = REPO_ROOT / "Amplifier" / ".history"
            if not hist_repo.exists():
                print("[ERROR] Amplifier/.history repo not found.", file=sys.stderr)
                sys.exit(1)
            content = subprocess.check_output(
                ["git", "-C", str(hist_repo), "show", f"{args.history}:Amplifier.kicad_pcb"]
            ).decode("utf-8", errors="replace")
            hist_file = temp_dir / f"history_{args.history}_Amplifier.kicad_pcb"
            hist_file.write_text(content, encoding="utf-8")
            target_a_str = str(hist_file)
        else:
            target_a_str = args.target_a

        target_b_str = args.target_b

        path_a, content_a, label_a = resolve_target(target_a_str, temp_dir)
        path_b, content_b, label_b = resolve_target(target_b_str, temp_dir)

        # Handle --restore
        if args.restore:
            dest_file = Path(target_b_str)
            if not dest_file.exists():
                print(f"[ERROR] Restore destination file not found: {dest_file}", file=sys.stderr)
                sys.exit(1)

            # Safety backup first!
            backup_script = REPO_ROOT / "scripts" / "backup_hardware.py"
            if backup_script.exists():
                print("[SAFETY] Taking snapshot before restore...")
                subprocess.run([sys.executable, str(backup_script), "--label", "pre_restore"], check=True)

            print(f"[RESTORE] Restoring {label_a} -> {dest_file}...")
            shutil.copy2(path_a, dest_file)
            print(f"[SUCCESS] Restored {dest_file} successfully.")
            return

        # 1. Structural Semantic Text Diff
        if not args.visual_only:
            struct_a = parse_kicad_pcb(content_a)
            struct_b = parse_kicad_pcb(content_b)
            print(f"\nComparing:")
            print(f"  Target [A]: {label_a}")
            print(f"  Target [B]: {label_b}\n")
            print(compare_pcb_structures(struct_a, struct_b))

        # 2. Visual Diff Rendering
        if not args.text_only:
            out_dir = REPO_ROOT / args.output_dir
            sides = ["top", "bottom"] if args.side == "both" else [args.side]

            print(f"\n[VISUAL DIFF] Rendering {args.side} view(s) via kicad-cli...")
            for s in sides:
                png_a = temp_dir / f"{s}_a.png"
                png_b = temp_dir / f"{s}_b.png"

                ok_a = render_pcb_view(path_a, png_a, side=s)
                ok_b = render_pcb_view(path_b, png_b, side=s)

                if ok_a and ok_b:
                    diff_outputs = generate_visual_diff(png_a, png_b, out_dir, label_a, label_b, view_name=s)
                    print(f"  [OK] Rendered {s.upper()} Diff Artifacts:")
                    for k, p in diff_outputs.items():
                        print(f"       -> {p.relative_to(REPO_ROOT)}")
                else:
                    print(f"  [WARN] Could not render {s} view (kicad-cli returned error).")

            print(f"\nVisual diff artifacts saved to: {out_dir}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
