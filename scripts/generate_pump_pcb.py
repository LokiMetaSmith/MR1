# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

"""
Deterministic, netlist-driven KiCad 10 PCB generator and 4-layer router for the
MR1 External Pump & USB-PD Controller Board (Pump/Pump.kicad_pcb).

Matches physical enclosure & schematic specifications:
- Board outline: 88.0 x 51.8 mm (X=[56.0, 144.0], Y=[56.0, 107.8]) with 2.0 mm corner chamfers,
  leaving 36.2 mm open at the bottom (Y=107.8..144.0) for peristaltic pump motor mounting
- 4-layer FR4 stackup (1.6 mm): F.Cu, In1.Cu (solid GND), In2.Cu (5 power islands), B.Cu
- Mounting holes: MH1..MH4 (M3) at (62, 62), (138, 62), (62, 100), (138, 100)
- Dual GCT USB4085 USB-C connectors: J7 (USB_C_HOST) at X=85.0 mm, J6 (USB_C_MR1_OUT) at X=115.0 mm
- Dual Honeywell ABPDAN pressure transducers: U301 (port left), U302 (port right)
- Central STM32G431CBU6 MCU (U11), STUSB4500 PD sink (U101), TPS54302 buck (U102),
  TPS22917 load switch (U103), TLV70233 LDO (U104), TS3USB30EDGSR USB mux (U503),
  coupled 90-ohm length-matched USB differential pairs, preliminary DRV8837C motor drivers
  (U12, U401), JST-XH motor headers (J401..J403), and SWD (J201).
"""

import argparse
from collections import defaultdict
import heapq
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def _ensure_pcbnew():
    """Import pcbnew, re-execing /usr/bin/python3 when invoked from a venv lacking pcbnew."""
    try:
        import pcbnew  # noqa: F401
        return pcbnew
    except ModuleNotFoundError:
        sys_py = "/usr/bin/python3"
        if Path(sys.executable).resolve() != Path(sys_py).resolve() and Path(sys_py).exists():
            os.execv(sys_py, [sys_py, *sys.argv])
        raise


REPO_ROOT = Path(__file__).resolve().parent.parent
PUMP_DIR = REPO_ROOT / "Pump"
PUMP_SCH_PATH = PUMP_DIR / "Pump.kicad_sch"
PUMP_PRO_PATH = PUMP_DIR / "Pump.kicad_pro"
PUMP_PCB_PATH = PUMP_DIR / "Pump.kicad_pcb"
PUMP_NET_PATH = PUMP_DIR / "Pump.net"
KICAD_FOOTPRINT_DIR = Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))

# Canonical KiCad 10 4-layer FR4 stackup (1.6 mm) & plot settings preserved from Pump.kicad_pcb
PCB_HEADER_TEMPLATE = """(kicad_pcb
\t(version 20260206)
\t(generator "pcbnew")
\t(generator_version "10.0")
\t(general
\t\t(thickness 1.6)
\t\t(legacy_teardrops no)
\t)
\t(paper "A4")
\t(layers
\t\t(0 "F.Cu" signal)
\t\t(4 "In1.Cu" signal)
\t\t(6 "In2.Cu" signal)
\t\t(2 "B.Cu" signal)
\t\t(9 "F.Adhes" user "F.Adhesive")
\t\t(11 "B.Adhes" user "B.Adhesive")
\t\t(13 "F.Paste" user)
\t\t(15 "B.Paste" user)
\t\t(5 "F.SilkS" user "F.Silkscreen")
\t\t(7 "B.SilkS" user "B.Silkscreen")
\t\t(1 "F.Mask" user)
\t\t(3 "B.Mask" user)
\t\t(17 "Dwgs.User" user "User.Drawings")
\t\t(19 "Cmts.User" user "User.Comments")
\t\t(21 "Eco1.User" user "User.Eco1")
\t\t(23 "Eco2.User" user "User.Eco2")
\t\t(25 "Edge.Cuts" user)
\t\t(27 "Margin" user)
\t\t(31 "F.CrtYd" user "F.Courtyard")
\t\t(29 "B.CrtYd" user "B.Courtyard")
\t\t(35 "F.Fab" user)
\t\t(33 "B.Fab" user)
\t)
\t(setup
\t\t(stackup
\t\t\t(layer "F.SilkS"
\t\t\t\t(type "Top Silk Screen")
\t\t\t)
\t\t\t(layer "F.Paste"
\t\t\t\t(type "Top Solder Paste")
\t\t\t)
\t\t\t(layer "F.Mask"
\t\t\t\t(type "Top Solder Mask")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "F.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "dielectric 1"
\t\t\t\t(type "prepreg")
\t\t\t\t(thickness 0.1)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.5)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "In1.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "dielectric 2"
\t\t\t\t(type "core")
\t\t\t\t(thickness 1.2)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.5)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "In2.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "dielectric 3"
\t\t\t\t(type "prepreg")
\t\t\t\t(thickness 0.1)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.5)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "B.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "B.Mask"
\t\t\t\t(type "Bottom Solder Mask")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "B.Paste"
\t\t\t\t(type "Bottom Solder Paste")
\t\t\t)
\t\t\t(layer "B.SilkS"
\t\t\t\t(type "Bottom Silk Screen")
\t\t\t)
\t\t\t(copper_finish "None")
\t\t\t(dielectric_constraints yes)
\t\t)
\t\t(pad_to_mask_clearance 0)
\t\t(allow_soldermask_bridges_in_footprints no)
\t\t(tenting
\t\t\t(front yes)
\t\t\t(back yes)
\t\t)
\t\t(covering
\t\t\t(front no)
\t\t\t(back no)
\t\t)
\t\t(plugging
\t\t\t(front no)
\t\t\t(back no)
\t\t)
\t\t(capping no)
\t\t(filling no)
\t\t(pcbplotparams
\t\t\t(layerselection 0x00000000_00000000_55555555_5755f5ff)
\t\t\t(plot_on_all_layers_selection 0x00000000_00000000_00000000_00000000)
\t\t\t(disableapertmacros no)
\t\t\t(usegerberextensions no)
\t\t\t(usegerberattributes yes)
\t\t\t(usegerberadvancedattributes yes)
\t\t\t(creategerberjobfile yes)
\t\t\t(dashed_line_dash_ratio 12)
\t\t\t(dashed_line_gap_ratio 3)
\t\t\t(svgprecision 4)
\t\t\t(plotframeref no)
\t\t\t(mode 1)
\t\t\t(useauxorigin no)
\t\t\t(pdf_front_fp_property_popups yes)
\t\t\t(pdf_back_fp_property_popups yes)
\t\t\t(pdf_metadata yes)
\t\t\t(pdf_single_document no)
\t\t\t(dxfpolygonmode yes)
\t\t\t(dxfimperialunits yes)
\t\t\t(dxfusepcbnewfont yes)
\t\t\t(psnegative no)
\t\t\t(psa4output no)
\t\t\t(plot_black_and_white yes)
\t\t\t(sketchpadsonfab no)
\t\t\t(plotpadnumbers no)
\t\t\t(hidednponfab no)
\t\t\t(sketchdnponfab yes)
\t\t\t(crossoutdnponfab yes)
\t\t\t(subtractmaskfromsilk no)
\t\t\t(outputformat 1)
\t\t\t(mirror no)
\t\t\t(drillshape 1)
\t\t\t(scaleselection 1)
\t\t\t(outputdirectory "")
\t\t)
\t)
"""

# Compact 88.0 x 51.8 mm CAD-aligned placement for all 89 schematic components: ref -> (X_mm, Y_mm, rot_deg)
PLACEMENT = {
    # Mechanical mounting holes (Y <= 107.8 compact envelope)
    "MH1": (62.000, 62.000, 0),
    "MH2": (138.000, 62.000, 0),
    "MH3": (62.000, 100.000, 0),
    "MH4": (138.000, 100.000, 0),
    # USB_Interconnect (USB4085 origin is Pad A1; center X=+2.975, silk nose Y_local=8.73)
    "J7": (87.975, 64.790, 180),
    "J6": (117.975, 64.790, 180),
    "U502": (85.000, 69.700, -90),
    "C502": (88.000, 74.400, 0),
    "U501": (115.000, 69.200, -90),
    "U503": (100.050, 65.500, -90),
    "C501": (109.000, 73.600, 90),
    "R501": (123.000, 67.500, 0),
    "R502": (123.000, 70.000, 0),
    "R503": (84.800, 74.400, 0),
    "R504": (112.500, 73.600, 0),
    "R505": (117.000, 73.600, 0),
    # Power_PD
    "U101": (72.763, 64.300, 0),
    "C101": (80.750, 67.500, 0),
    "C102": (70.763, 58.300, 0),
    "C103": (74.763, 58.300, 0),
    "R101": (80.750, 70.000, 0),
    "R102": (80.750, 72.200, 0),
    "R103": (80.750, 74.400, 0),
    "R109": (80.750, 76.600, 0),
    "R110": (66.263, 64.300, 90),
    "R104": (68.263, 70.300, 0),
    "R108": (72.263, 70.300, 0),
    "R105": (76.263, 70.300, 0),
    "Q101": (68.763, 73.800, 0),
    "C104": (73.850, 73.400, 0),
    "C105": (73.500, 76.100, 0),
    "C106": (74.000, 86.200, 90),
    "U102": (80.000, 86.000, 180),
    "C107": (83.200, 82.500, 0),
    "L101": (88.800, 86.500, 0),
    "C108": (90.200, 91.500, 0),
    "C109": (86.700, 91.500, 0),
    "C110": (83.200, 91.500, 0),
    "R106": (79.000, 89.400, 0),
    "R107": (82.000, 89.400, 0),
    "U103": (112.200, 78.000, 0),
    "C111": (115.700, 79.800, 180),
    "C112": (112.200, 75.800, 0),
    "R111": (115.700, 77.600, 180),
    "U104": (111.800, 83.200, 0),
    "C113": (111.800, 86.600, 0),
    # Pressure_Sensors
    "U301": (58.975, 85.040, 90),
    "C301": (64.500, 76.800, 0),
    "U302": (137.625, 73.660, -90),
    "C302": (130.500, 71.050, 0),
    "R301": (89.200, 76.800, 0),
    "R302": (89.200, 78.800, 0),
    # MCU_STM32
    "U11": (98.750, 79.500, 90),
    "Y201": (98.800, 89.800, 0),
    "C209": (95.400, 90.200, 90),
    "C210": (102.200, 90.200, -90),
    "C208": (102.800, 87.500, 0),
    "R201": (89.200, 80.800, 0),
    "C201": (94.400, 86.200, 90),
    "C202": (104.500, 68.700, 0),
    "C203": (93.500, 68.500, 0),
    "C205": (107.250, 72.200, 90),
    "FB201": (107.750, 78.800, 90),
    "C204": (107.750, 75.600, 90),
    "C206": (107.750, 82.000, 90),
    "C207": (107.750, 84.800, 90),
    "J201": (109.500, 102.500, 90),
    "R202": (118.000, 75.500, 0),
    "R203": (118.000, 78.300, 0),
    "R204": (118.000, 81.100, 0),
    "R205": (118.000, 83.900, 0),
    "R206": (118.000, 86.700, 0),
    "D201": (121.600, 75.500, 180),
    "D202": (121.600, 78.300, 180),
    "D203": (121.600, 81.100, 180),
    "D204": (121.600, 83.900, 180),
    "D205": (121.600, 86.700, 180),
    # Motor_Drivers (Modular StepStick sockets and JST-XH headers)
    "MOD401": (87.000, 92.000, -90),
    "MOD402": (134.000, 92.000, -90),
    "J401": (74.300, 98.500, 0),
    "J402": (121.300, 98.500, 0),
    "C401": (89.500, 104.700, 90),
    "C402": (136.500, 104.700, 90),
    "C403": (90.000, 98.000, 0),
    "C404": (71.760, 106.500, 0),
    "C405": (118.760, 106.500, 0),
    "R401": (79.380, 95.000, 0),
    "R402": (74.300, 95.000, 0),
}

# Explicit world positions for silkscreen Reference fields that would otherwise touch neighbor silk/pads
REF_WORLD_POS = {
    "U102": (80.0, 83.5),
    "R106": (79.0, 91.2),
    "R107": (82.0, 91.2),
    "R110": (68.2, 64.3),
    "C105": (73.5, 77.9),
    "C108": (90.2, 93.2),
    "C109": (86.7, 93.2),
    "C110": (83.2, 93.2),
    "U103": (112.2, 80.5),
    "C111": (115.7, 81.3),
    "C112": (114.0, 75.0),
    "R111": (115.7, 76.3),
    "L101": (88.8, 86.5),
    "R301": (86.5, 76.8),
    "R302": (86.5, 78.8),
    "R201": (86.5, 80.8),
    "C201": (93.8, 83.8),
    "C209": (95.4, 92.5),
    "C210": (102.2, 92.5),
    "C204": (105.2, 75.6),
    "FB201": (105.2, 78.8),
    "C206": (105.2, 82.0),
    "C207": (105.2, 84.8),
    "C502": (88.0, 75.8),
    "C501": (109.0, 75.6),
    "R503": (84.8, 75.8),
    "C401": (74.5, 87.6),
    "C402": (71.5, 87.6),
    "J401": (73.75, 98.8),
    "U401": (129.8, 81.5),
    "C404": (130.0, 86.2),
    "C405": (130.0, 88.6),
    "R202": (118.0, 74.25),
    "R203": (118.0, 77.05),
    "R204": (118.0, 79.85),
    "R205": (118.0, 82.65),
    "R206": (118.0, 85.45),
    "D201": (121.6, 74.25),
    "D202": (121.6, 77.05),
    "D203": (121.6, 79.85),
    "D204": (121.6, 82.65),
    "D205": (121.6, 85.45),
    "J403": (96.25, 100.3),
    "J201": (114.5, 105.5),
}

ISLAND_POLYS = {
    "/Power_PD/+VBUS_PD": [(65.5, 57.5), (89.5, 57.5), (89.5, 71.5), (65.5, 71.5)],
    "/Power_PD/+5V_BUCK": [
        (84.0, 71.8), (89.0, 71.8), (89.0, 86.2),
        (93.0, 86.2), (93.0, 88.5), (108.0, 88.5),
        (108.0, 93.0), (84.0, 93.0),
    ],
    "/USB_Interconnect/+5V_MR1_CLEAN": [(109.2, 57.5), (125.5, 57.5), (125.5, 79.6), (109.2, 79.6)],
    "/MCU_STM32/+3V3": [
        (92.0, 64.5), (108.4, 64.5), (108.4, 80.3),
        (113.8, 80.3), (113.8, 87.8), (93.8, 87.8),
        (93.8, 85.6), (89.6, 85.6), (89.6, 75.5), (92.0, 75.5),
    ],
    "/Motor_Drivers/VMOTOR": [
        (65.5, 72.2), (83.2, 72.2), (83.2, 93.8),
        (119.0, 93.8), (119.0, 82.0), (133.5, 82.0),
        (133.5, 102.0), (65.5, 102.0),
    ],
}

ISLAND_BOXES = {
    "/Power_PD/+VBUS_PD": lambda x, y: 66.2 <= x <= 88.8 and 58.2 <= y <= 70.8,
    "/Power_PD/+5V_BUCK": lambda x, y: (
        (84.7 <= x <= 88.3 and 72.0 <= y <= 92.3)
        or (84.7 <= x <= 92.3 and 86.9 <= y <= 92.3)
        or (84.7 <= x <= 107.3 and 89.2 <= y <= 92.3)
    ),
    "/USB_Interconnect/+5V_MR1_CLEAN": lambda x, y: 109.8 <= x <= 124.8 and 58.2 <= y <= 78.9,
    "/MCU_STM32/+3V3": lambda x, y: (
        (92.7 <= x <= 108.0 and 65.2 <= y <= 75.0)
        or (94.5 <= x <= 108.0 and 65.2 <= y <= 87.1)
        or (106.5 <= x <= 113.1 and 81.0 <= y <= 87.1)
        or (90.3 <= x <= 94.6 and 76.2 <= y <= 84.9)
    ),
    "/Motor_Drivers/VMOTOR": lambda x, y: (
        (66.2 <= x <= 82.5 and 72.9 <= y <= 101.3)
        or (66.2 <= x <= 132.8 and 94.5 <= y <= 101.3)
        or (119.7 <= x <= 132.8 and 82.7 <= y <= 101.3)
    ),
}

FINE_ICS = ("U11", "U101", "U503")

IC_APRONS = [
    (98.75, 79.50, 6.0, 6.0),
    (72.763, 64.30, 3.6, 3.6),
    (100.05, 65.50, 3.3, 3.0),
]


def parse_sexpr(text: str):
    """Parse a KiCad S-expression document into nested Python lists/strings."""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            out = []
            while j < n:
                ch = text[j]
                if ch == "\\" and j + 1 < n:
                    out.append(text[j + 1])
                    j += 2
                elif ch == '"':
                    break
                else:
                    out.append(ch)
                    j += 1
            tokens.append(("STR", "".join(out)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            tokens.append(("ATOM", text[i:j]))
            i = j

    stack = [[]]
    for tok in tokens:
        if tok == "(":
            lst = []
            stack[-1].append(lst)
            stack.append(lst)
        elif tok == ")":
            stack.pop()
        else:
            stack[-1].append(tok[1])
    return stack[0][0]


def export_and_parse_netlist(sch_path: Path, tmp_dir: Path):
    """Run kicad-cli sch export netlist into tmp_dir and parse components & nets."""
    net_path = tmp_dir / "Pump.net"
    subprocess.run(
        [
            "kicad-cli",
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadsexpr",
            "-o",
            str(net_path),
            str(sch_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    tree = parse_sexpr(net_path.read_text(encoding="utf-8"))
    comps_node = next(x for x in tree[1:] if isinstance(x, list) and x[0] == "components")
    nets_node = next(x for x in tree[1:] if isinstance(x, list) and x[0] == "nets")
    return comps_node[1:], nets_node[1:]


def _in_ic_apron(vx: float, vy: float) -> bool:
    for cx, cy, hx, hy in IC_APRONS:
        if abs(vx - cx) <= hx and abs(vy - cy) <= hy:
            return True
    return False


def _route_board(all_pads, pad_objs, boost_nets):
    """Deterministic 4-layer fanout, power-via tie-ins, 90-ohm USB diff-pairs, and A* router."""
    grid_step = 0.25
    grid_x0, grid_y0 = 56.0, 56.0
    gw = int(round((144.0 - 56.0) / grid_step)) + 1
    gh = int(round((107.8 - 56.0) / grid_step)) + 1

    def to_g(x, y):
        return int(round((x - grid_x0) / grid_step)), int(round((y - grid_y0) / grid_step))

    def to_w(gx, gy):
        return grid_x0 + gx * grid_step, grid_y0 + gy * grid_step

    def snap025(v):
        return round(v * 4.0) / 4.0

    pad_lookup = {
        (ref, pnum): (wx, wy, p, is_pth, nname)
        for ref, pnum, wx, wy, p, is_pth, nname in all_pads
    }

    def pxy(ref, pnum):
        return pad_lookup[(ref, pnum)][0], pad_lookup[(ref, pnum)][1]

    tracks = []
    vias = []

    def add_seg(x1, y1, x2, y2, width, layer_name, net_name):
        if abs(x1 - x2) < 1e-4 and abs(y1 - y2) < 1e-4:
            return
        tracks.append((x1, y1, x2, y2, width, layer_name, net_name))

    def add_via(vx, vy, net_name, size=0.50, drill=0.30):
        vias.append((vx, vy, size, drill, net_name))

    # 1. Thermal & GND vias under exposed pads
    u11_cx, u11_cy, _ = PLACEMENT["U11"]
    for dx, dy in ((0.0, 0.0), (-1.4, -1.4), (-1.4, 1.4), (1.4, -1.4), (1.4, 1.4)):
        add_via(u11_cx + dx, u11_cy + dy, "GND", 0.60, 0.30)
    u101_cx, u101_cy, _ = PLACEMENT["U101"]
    for dx in (-0.5, 0.5):
        for dy in (-0.5, 0.5):
            add_via(u101_cx + dx, u101_cy + dy, "GND", 0.60, 0.30)

    # Direct inward GND ties for QFN/WSON perimeter GND pins to center EP
    for ref, ep, gpins in [
        ("U101", "25", ["10", "12", "13", "22"]),
    ]:
        ex, ey = pxy(ref, ep)
        for gp in gpins:
            gx, gy = pxy(ref, gp)
            if abs(gx - ex) > abs(gy - ey):
                add_seg(gx, gy, ex, gy, 0.20, "F.Cu", "GND")
            else:
                add_seg(gx, gy, gx, ey, 0.20, "F.Cu", "GND")

    # 2. Coupled, length-matched 90-ohm USB differential pairs (0.16 mm width, 0.18 mm gap -> 0.34 mm pitch)
    def add_poly(pts, width, layer_name, net_name):
        for idx in range(len(pts) - 1):
            add_seg(pts[idx][0], pts[idx][1], pts[idx + 1][0], pts[idx + 1][1], width, layer_name, net_name)

    def poly_len(pts):
        return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))

    USB_W = 0.16

    # Pair 1: /USB_Interconnect/HOST_D+ & HOST_D- (J7 <-> U502, 0 vias, F.Cu coupled run; J7.A7<->B7 THT bridge on B.Cu)
    add_poly([pxy("J7", "B6"), pxy("J7", "A6")], USB_W, "F.Cu", "/USB_Interconnect/HOST_D+")
    add_poly([pxy("J7", "B7"), pxy("J7", "A7")], USB_W, "B.Cu", "/USB_Interconnect/HOST_D-")
    add_poly(
        [pxy("J7", "A6"), (85.170, 65.045), (85.170, 66.700), pxy("U502", "1")],
        USB_W,
        "F.Cu",
        "/USB_Interconnect/HOST_D+",
    )
    add_poly(
        [pxy("J7", "A7"), (84.830, 65.045), (84.830, 66.700), pxy("U502", "3")],
        USB_W,
        "F.Cu",
        "/USB_Interconnect/HOST_D-",
    )

    # Pair 2: /USB_Interconnect/MR1_D+ & MR1_D- (J6 <-> U501, 0 vias, F.Cu coupled run; J6.A7<->B7 THT bridge on B.Cu)
    add_poly([pxy("J6", "B6"), pxy("J6", "A6")], USB_W, "F.Cu", "/USB_Interconnect/MR1_D+")
    add_poly([pxy("J6", "B7"), pxy("J6", "A7")], USB_W, "B.Cu", "/USB_Interconnect/MR1_D-")
    add_poly(
        [pxy("J6", "A6"), (115.170, 65.045), (115.170, 66.500), pxy("U501", "1")],
        USB_W,
        "F.Cu",
        "/USB_Interconnect/MR1_D+",
    )
    add_poly(
        [pxy("J6", "A7"), (114.830, 65.045), (114.830, 66.500), pxy("U501", "3")],
        USB_W,
        "F.Cu",
        "/USB_Interconnect/MR1_D-",
    )

    # Pair 3: /USB_Interconnect/HOST_MUX_D+ & HOST_MUX_D- (U503 <-> U502, 100% F.Cu, 0 vias, 0.34 mm coupled)
    # Use angled uncoupled pad exits at U503/U502 so KiCad diff_pair_gap only evaluates the 0.34 mm coupled run.
    host_mux_dp_pts = [
        pxy("U503", "4"),
        (99.550, 62.600),
        (98.900, 61.950),
        (98.000, 61.950),
        (97.500, 62.450),
        (97.500, 71.000),
        (88.359, 71.000),
        (86.659, 72.700),
        (85.170, 72.700),
        pxy("U502", "6"),
    ]
    lo, hi = 0.0, 3.5
    for _ in range(32):
        mid = 0.5 * (lo + hi)
        cand = [
            pxy("U503", "6"),
            (99.050, 68.400),
            (98.400 - mid, 69.050 + mid),
            (97.840, 69.610),
            (97.840, 71.340),
            (88.500, 71.340),
            (86.800, 73.040),
            (84.830, 73.040),
            pxy("U502", "4"),
        ]
        if poly_len(cand) < poly_len(host_mux_dp_pts):
            lo = mid
        else:
            hi = mid
    host_mux_dm_pts = cand
    add_poly(host_mux_dp_pts, USB_W, "F.Cu", "/USB_Interconnect/HOST_MUX_D+")
    add_poly(host_mux_dm_pts, USB_W, "F.Cu", "/USB_Interconnect/HOST_MUX_D-")

    # Pair 4: /USB_Interconnect/MR1_MUX_D+ & MR1_MUX_D- (U503 <-> U501, 100% F.Cu, 0 vias, 0.34 mm coupled)
    # D- runs TOP/INNER (70.16 -> 72.10) to U501.4 (114.05); D+ runs BOTTOM/OUTER (70.50 -> 72.44) to U501.6 (115.95).
    mr1_mux_dp_pts = [
        pxy("U503", "3"),
        (100.050, 62.600),
        (100.700, 61.950),
        (102.000, 61.950),
        (102.640, 62.590),
        (102.640, 70.500),
        (110.359, 70.500),
        (112.299, 72.440),
        (115.170, 72.440),
        pxy("U501", "6"),
    ]
    lo, hi = 0.0, 2.5
    for _ in range(32):
        mid = 0.5 * (lo + hi)
        cand = [
            pxy("U503", "7"),
            (99.550, 68.400),
            (99.900, 70.160),
            (100.400, 70.160 + mid),
            (100.900, 70.160),
            (101.400, 70.160 + mid),
            (102.000, 70.160),
            (110.500, 70.160),
            (112.440, 72.100),
            (114.830, 72.100),
            pxy("U501", "4"),
        ]
        if poly_len(cand) < poly_len(mr1_mux_dp_pts):
            lo = mid
        else:
            hi = mid
    mr1_mux_dm_pts = cand
    add_poly(mr1_mux_dp_pts, USB_W, "F.Cu", "/USB_Interconnect/MR1_MUX_D+")
    add_poly(mr1_mux_dm_pts, USB_W, "F.Cu", "/USB_Interconnect/MR1_MUX_D-")

    # Pair 5: /MCU_STM32/USB_MCU_D+ & USB_MCU_D- (U503.2/8 <-> U11.34/33)
    u503_vp_x, u503_vp_y = 100.550, 64.900
    u503_vn_x, u503_vn_y = 100.050, 66.150
    u11_vp_x, u11_vp_y = 96.875, 72.650
    u11_vn_x, u11_vn_y = 97.625, 72.650

    mcu_dp_f1 = [pxy("U503", "2"), (u503_vp_x, u503_vp_y)]
    mcu_dm_f1 = [pxy("U503", "8"), (u503_vn_x, u503_vn_y)]
    mcu_dp_f2 = [(u11_vp_x, u11_vp_y), (97.080, 72.855), (97.080, 75.700), pxy("U11", "34")]
    mcu_dm_f2 = [(u11_vn_x, u11_vn_y), (97.420, 72.855), (97.420, 75.700), pxy("U11", "33")]

    mcu_dp_b = [
        (u503_vp_x, u503_vp_y),
        (100.550, 65.500),
        (97.080, 65.500),
        (97.080, 72.445),
        (u11_vp_x, u11_vp_y),
    ]
    p_tot = poly_len(mcu_dp_f1) + poly_len(mcu_dp_b) + poly_len(mcu_dp_f2)
    lo, hi = 0.0, 2.0
    for _ in range(32):
        mid = 0.5 * (lo + hi)
        y_jog = 65.840 + mid
        cand_b = [
            (u503_vn_x, u503_vn_y),
            (100.050, y_jog),
            (99.200, y_jog),
            (99.200, 65.840),
            (97.420, 65.840),
            (97.420, 72.445),
            (u11_vn_x, u11_vn_y),
        ]
        if poly_len(mcu_dm_f1) + poly_len(cand_b) + poly_len(mcu_dm_f2) < p_tot:
            lo = mid
        else:
            hi = mid
    mcu_dm_b = cand_b

    add_poly(mcu_dp_f1, USB_W, "F.Cu", "/MCU_STM32/USB_MCU_D+")
    add_poly(mcu_dp_b, USB_W, "B.Cu", "/MCU_STM32/USB_MCU_D+")
    add_poly(mcu_dp_f2, USB_W, "F.Cu", "/MCU_STM32/USB_MCU_D+")
    add_via(u503_vp_x, u503_vp_y, "/MCU_STM32/USB_MCU_D+", 0.50, 0.30)
    add_via(u11_vp_x, u11_vp_y, "/MCU_STM32/USB_MCU_D+", 0.50, 0.30)

    add_poly(mcu_dm_f1, USB_W, "F.Cu", "/MCU_STM32/USB_MCU_D-")
    add_poly(mcu_dm_b, USB_W, "B.Cu", "/MCU_STM32/USB_MCU_D-")
    add_poly(mcu_dm_f2, USB_W, "F.Cu", "/MCU_STM32/USB_MCU_D-")
    add_via(u503_vn_x, u503_vn_y, "/MCU_STM32/USB_MCU_D-", 0.50, 0.30)
    add_via(u11_vn_x, u11_vn_y, "/MCU_STM32/USB_MCU_D-", 0.50, 0.30)

    # 2b. Short, symmetric HSE crystal routing on F.Cu (0 vias)
    add_poly([pxy("U11", "5"), (98.000, 86.400), (96.500, 87.900), (96.500, 90.650), pxy("Y201", "1")], 0.20, "F.Cu", "/MCU_STM32/HSE_IN")
    add_poly([pxy("Y201", "1"), pxy("C209", "1")], 0.20, "F.Cu", "/MCU_STM32/HSE_IN")
    add_poly([pxy("U11", "6"), (98.500, 86.400), (99.900, 87.800), pxy("Y201", "3")], 0.20, "F.Cu", "/MCU_STM32/HSE_OUT")
    add_poly([pxy("Y201", "3"), (101.400, 88.950), (102.200, 89.720), pxy("C210", "1")], 0.20, "F.Cu", "/MCU_STM32/HSE_OUT")

    # 2c. Direct short F.Cu bridges for LED series resistors, buck SW node, and clean analog VDDA bus
    for r_ref, d_ref in [("R202", "D201"), ("R203", "D202"), ("R204", "D203"), ("R205", "D204"), ("R206", "D205")]:
        add_poly([pxy(r_ref, "2"), pxy(d_ref, "2")], 0.20, "F.Cu", f"Net-({d_ref}-A)")
    add_poly([pxy("U102", "2"), (82.250, 86.000), (82.750, 86.500), pxy("L101", "1")], 0.50, "F.Cu", "Net-(U102-SW)")
    add_poly([pxy("C107", "2"), (83.680, 86.500)], 0.25, "F.Cu", "Net-(U102-SW)")
    add_poly([pxy("U11", "20"), pxy("U11", "21"), (105.000, 78.250)], 0.16, "F.Cu", "/MCU_STM32/VDDA")
    add_poly([(105.000, 78.250), (105.500, 78.010), pxy("FB201", "2")], 0.22, "F.Cu", "/MCU_STM32/VDDA")
    add_poly([pxy("FB201", "2"), (107.750, 77.000), pxy("C204", "1")], 0.22, "F.Cu", "/MCU_STM32/VDDA")
    add_poly([pxy("FB201", "2"), (106.500, 78.010)], 0.22, "F.Cu", "/MCU_STM32/VDDA")
    add_via(106.500, 78.010, "/MCU_STM32/VDDA", 0.50, 0.30)
    add_poly([(106.500, 78.010), (106.500, 82.480), (106.500, 85.280)], 0.22, "B.Cu", "/MCU_STM32/VDDA")
    add_via(106.500, 82.480, "/MCU_STM32/VDDA", 0.50, 0.30)
    add_poly([(106.500, 82.480), pxy("C206", "1")], 0.22, "F.Cu", "/MCU_STM32/VDDA")
    add_via(106.500, 85.280, "/MCU_STM32/VDDA", 0.50, 0.30)
    add_poly([(106.500, 85.280), pxy("C207", "1")], 0.22, "F.Cu", "/MCU_STM32/VDDA")
    add_poly([pxy("U103", "4"), (114.500, 78.950), (115.220, 79.800), pxy("C111", "2")], 0.20, "F.Cu", "/Power_PD/TPS_CT")
    add_poly([pxy("U103", "5"), (114.500, 78.000), (114.900, 77.600), pxy("R111", "2")], 0.20, "F.Cu", "Net-(U103-QOD)")
    add_poly([pxy("R102", "1"), pxy("R103", "1"), pxy("R109", "1")], 0.25, "F.Cu", "/MCU_STM32/+3V3")

    # 3. 4-way staggered perpendicular escape fanout for fine-pitch ICs & J6/J7 signal pins
    fanout_anchor = {}
    power_island_vias = defaultdict(list)
    connected_power_pads = set()

    # Dedicated clean vias for U503 GND/control/3V3 and U502/U501 power/GND so F.Cu USB corridors remain clear
    add_seg(*pxy("U503", "1"), 101.55, 64.90, 0.16, "F.Cu", "/MCU_STM32/USB_SEL_PASS")
    add_via(101.55, 64.90, "/MCU_STM32/USB_SEL_PASS", 0.50, 0.30)
    fanout_anchor[("U503", "1")] = (1, 101.55, 64.90)

    add_seg(*pxy("U503", "10"), 101.55, 66.10, 0.16, "F.Cu", "/MCU_STM32/+3V3")
    add_via(101.55, 66.10, "/MCU_STM32/+3V3", 0.50, 0.30)
    power_island_vias["/MCU_STM32/+3V3"].append((101.55, 66.10))
    connected_power_pads.add(("U503", "10"))
    fanout_anchor[("U503", "10")] = (1, 101.55, 66.10)

    add_seg(*pxy("U503", "5"), 99.05, 64.65, 0.16, "F.Cu", "GND")
    add_via(99.05, 64.65, "GND", 0.50, 0.30)
    add_seg(*pxy("U503", "9"), 100.55, 69.20, 0.16, "F.Cu", "GND")
    add_via(100.55, 69.20, "GND", 0.50, 0.30)

    u502_5v_x, u502_5v_y = pxy("U502", "5")
    add_seg(u502_5v_x, u502_5v_y, 85.00, 72.10, 0.25, "F.Cu", "/Power_PD/+5V_BUCK")
    add_via(85.00, 72.10, "/Power_PD/+5V_BUCK", 0.50, 0.30)
    power_island_vias["/Power_PD/+5V_BUCK"].append((85.00, 72.10))
    connected_power_pads.add(("U502", "5"))
    fanout_anchor[("U502", "5")] = (1, 85.00, 72.10)

    add_seg(*pxy("U502", "2"), 85.00, 69.70, 0.20, "F.Cu", "GND")
    add_via(85.00, 69.70, "GND", 0.50, 0.30)

    u501_5v_x, u501_5v_y = pxy("U501", "5")
    add_seg(u501_5v_x, u501_5v_y, 115.00, 71.10, 0.25, "F.Cu", "/USB_Interconnect/+5V_MR1_CLEAN")
    add_via(115.00, 71.10, "/USB_Interconnect/+5V_MR1_CLEAN", 0.50, 0.30)
    power_island_vias["/USB_Interconnect/+5V_MR1_CLEAN"].append((115.00, 71.10))
    connected_power_pads.add(("U501", "5"))
    fanout_anchor[("U501", "5")] = (1, 115.00, 71.10)

    add_seg(*pxy("U501", "2"), 115.00, 69.20, 0.20, "F.Cu", "GND")
    add_via(115.00, 69.20, "GND", 0.50, 0.30)

    # Dedicated +3V3 escape for U11.35 avoiding U11.34 USB via and U11.36 SWDIO via
    u35_x, u35_y = pxy("U11", "35")
    add_poly([(u35_x, u35_y), (96.50, 74.00), (95.50, 73.00), (95.50, 72.00)], 0.20, "F.Cu", "/MCU_STM32/+3V3")
    add_via(95.50, 72.00, "/MCU_STM32/+3V3", 0.50, 0.30)
    power_island_vias["/MCU_STM32/+3V3"].append((95.50, 72.00))
    connected_power_pads.add(("U11", "35"))
    fanout_anchor[("U11", "35")] = (1, 95.50, 72.00)

    for ref, pnum, wx, wy, _, _, nname in all_pads:
        if not nname or nname.startswith("unconnected-"):
            continue
        if ref in ("U501", "U502", "U503"):
            continue
        if ref == "U11" and pnum in ("5", "6", "20", "21", "33", "34", "35"):
            continue
        if ref in FINE_ICS:
            if (
                (ref in ("U11", "U101") and pnum in ("49", "25"))
                or (ref == "U101" and pnum in ("10", "12", "13", "22"))
            ):
                continue
            cx, cy, _ = PLACEMENT[ref]
            dx, dy = wx - cx, wy - cy
            p_int = int(pnum)
            is_via_pin = (p_int % 2 == 0) or (ref == "U11" and pnum == "19")
            via_ext = 1.25 if (ref == "U11" and pnum == "19") else (1.25 if ((p_int // 2) % 2 == 0) else 2.00)
            odd_ext = 2.75 if ref == "U11" else 2.50
            fan_w = 0.16
            if ref == "U503" or abs(dx) > abs(dy):
                sx = 1.0 if dx > 0 else -1.0
                if is_via_pin:
                    vx = snap025(wx + sx * via_ext)
                    vy = snap025(wy) if ref == "U11" else wy
                    add_seg(wx, wy, vx, vy, fan_w, "F.Cu", nname)
                    add_via(vx, vy, nname, 0.50, 0.30)
                    if ref == "U11" and via_ext < 1.50 and pnum != "48":
                        fx, fy = snap025(wx + sx * 2.00), snap025(wy)
                        add_seg(vx, vy, fx, fy, 0.20, "B.Cu", nname)
                    else:
                        fx, fy = vx, vy
                    fanout_anchor[(ref, pnum)] = (1, fx, fy)
                else:
                    fx = snap025(wx + sx * odd_ext)
                    fy = snap025(wy) if ref == "U11" else wy
                    add_seg(wx, wy, fx, fy, fan_w, "F.Cu", nname)
                    if nname in ISLAND_BOXES and ISLAND_BOXES[nname](fx, fy):
                        add_via(fx, fy, nname, 0.50, 0.30)
                        power_island_vias[nname].append((fx, fy))
                        connected_power_pads.add((ref, pnum))
                    fanout_anchor[(ref, pnum)] = (0, fx, fy)
            else:
                sy = 1.0 if dy > 0 else -1.0
                if is_via_pin:
                    vx = 98.15 if (ref == "U11" and pnum == "32") else (snap025(wx) if ref == "U11" else wx)
                    vy = snap025(wy + sy * via_ext)
                    if abs(vx - wx) > 1e-4:
                        add_poly([(wx, wy), (wx, wy + sy * 0.65), (vx, wy + sy * 0.80), (vx, vy)], fan_w, "F.Cu", nname)
                    else:
                        add_seg(wx, wy, vx, vy, fan_w, "F.Cu", nname)
                    add_via(vx, vy, nname, 0.50, 0.30)
                    if ref == "U11" and via_ext < 1.50 and pnum != "48":
                        fx, fy = vx, snap025(wy + sy * 2.00)
                        add_seg(vx, vy, fx, fy, 0.20, "B.Cu", nname)
                    else:
                        fx, fy = vx, vy
                    fanout_anchor[(ref, pnum)] = (1, fx, fy)
                else:
                    fx = snap025(wx) if ref == "U11" else wx
                    fy = snap025(wy + sy * odd_ext)
                    add_seg(wx, wy, fx, fy, fan_w, "F.Cu", nname)
                    if nname in ISLAND_BOXES and ISLAND_BOXES[nname](fx, fy):
                        add_via(fx, fy, nname, 0.50, 0.30)
                        power_island_vias[nname].append((fx, fy))
                        connected_power_pads.add((ref, pnum))
                    fanout_anchor[(ref, pnum)] = (0, fx, fy)
        elif ref in ("U102", "U103", "U104"):
            cx, _, _ = PLACEMENT[ref]
            sx = 1.0 if (wx - cx) > 0 else -1.0
            ext = 0.75 if ref == "U103" else 1.0
            fx, fy = snap025(wx + sx * ext), snap025(wy)
            add_seg(wx, wy, fx, fy, 0.20, "F.Cu", nname)
            fanout_anchor[(ref, pnum)] = (0, fx, fy)
        elif ref in ("U501", "U502"):
            _, cy, _ = PLACEMENT[ref]
            sy = 1.0 if (wy - cy) > 0 else -1.0
            fx, fy = snap025(wx), snap025(wy + sy * 1.0)
            add_seg(wx, wy, fx, fy, 0.20, "F.Cu", nname)
            fanout_anchor[(ref, pnum)] = (0, fx, fy)
        elif ref in ("J6", "J7") and pnum in ("A5", "A8", "B5", "B8"):
            if pnum.startswith("A"):
                fx, fy = snap025(wx), 66.0
                add_seg(wx, wy, fx, fy, 0.20, "B.Cu", nname)
                fanout_anchor[(ref, pnum)] = (1, fx, fy)
            else:
                fx, fy = snap025(wx), 58.75
                add_seg(wx, wy, fx, fy, 0.20, "B.Cu", nname)
                fanout_anchor[(ref, pnum)] = (1, fx, fy)

    # 4. Build obstacle & hole-clearance grid for F.Cu (0) and B.Cu (1)
    blocked = [[""] * gh for _ in range(gw)]
    blocked = [blocked, [[""] * gh for _ in range(gw)]]
    hole_buckets = defaultdict(list)

    for gx in range(gw):
        for gy in range(gh):
            wx, wy = to_w(gx, gy)
            if (
                wx < 56.7
                or wx > 143.3
                or wy < 56.7
                or wy > 107.1
                or (wx - 56.0) + (wy - 56.0) < 3.0
                or (144.0 - wx) + (wy - 56.0) < 3.0
                or (wx - 56.0) + (107.8 - wy) < 3.0
                or (144.0 - wx) + (107.8 - wy) < 3.0
            ):
                blocked[0][gx][gy] = "__WALL__"
                blocked[1][gx][gy] = "__WALL__"

    in_step6 = False

    def mark_circle(layer_idx, cx, cy, r_block, net_name):
        gx1, gy1 = to_g(cx - r_block, cy - r_block)
        gx2, gy2 = to_g(cx + r_block, cy + r_block)
        for gx in range(max(0, gx1), min(gw, gx2 + 1)):
            for gy in range(max(0, gy1), min(gh, gy2 + 1)):
                wx_c, wy_c = to_w(gx, gy)
                if math.hypot(wx_c - cx, wy_c - cy) <= r_block:
                    cur = blocked[layer_idx][gx][gy]
                    if cur == "__WALL__":
                        continue
                    if cur == "" or cur == net_name:
                        blocked[layer_idx][gx][gy] = net_name
                    elif not in_step6:
                        blocked[layer_idx][gx][gy] = "__CONFLICT__"

    def mark_rect(layer_idx, cx, cy, hw, hh, net_name, pad_clear=0.23):
        gx1, gy1 = to_g(cx - hw - pad_clear, cy - hh - pad_clear)
        gx2, gy2 = to_g(cx + hw + pad_clear, cy + hh + pad_clear)
        for gx in range(max(0, gx1), min(gw, gx2 + 1)):
            for gy in range(max(0, gy1), min(gh, gy2 + 1)):
                wx_c, wy_c = to_w(gx, gy)
                dx = max(abs(wx_c - cx) - hw, 0.0)
                dy = max(abs(wy_c - cy) - hh, 0.0)
                if math.hypot(dx, dy) <= pad_clear:
                    cur = blocked[layer_idx][gx][gy]
                    if cur == "__WALL__":
                        continue
                    if cur == "" or cur == net_name:
                        blocked[layer_idx][gx][gy] = net_name
                    else:
                        blocked[layer_idx][gx][gy] = "__CONFLICT__"

    def add_hole_bucket(hx, hy, hdr, net_name):
        bx, by = int(hx), int(hy)
        span = max(1, int(math.ceil(hdr / 2.0 + 0.60)))
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                hole_buckets[(bx + dx, by + dy)].append((hx, hy, hdr / 2.0, net_name))

    import pcbnew

    for _, _, wx, wy, p, is_pth, nname in all_pads:
        sz = p.GetSize()
        ang = p.GetOrientation().AsDegrees() % 180
        pw, ph = pcbnew.ToMM(sz.x) / 2.0, pcbnew.ToMM(sz.y) / 2.0
        if abs(ang - 90) < 1:
            pw, ph = ph, pw
        for l in ([0, 1] if is_pth else [0]):
            mark_rect(l, wx, wy, pw, ph, nname, pad_clear=0.23)
        if is_pth:
            add_hole_bucket(wx, wy, pcbnew.ToMM(p.GetDrillSize().x), nname)

    POWER_NETS = {
        "/Power_PD/+VBUS_PD",
        "/Power_PD/+5V_BUCK",
        "/USB_Interconnect/+5V_MR1_CLEAN",
        "/MCU_STM32/+3V3",
        "/Motor_Drivers/VMOTOR",
    }

    def mark_seg(x1, y1, x2, y2, w, layer_idx, net_name, clr=None):
        if clr is None:
            clr = 0.21 if (net_name in POWER_NETS or "D+" in net_name or "D-" in net_name) else 0.14
        steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / 0.1))
        r = w / 2.0 + clr + 0.08
        for s in range(steps + 1):
            t = s / steps
            mark_circle(layer_idx, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, net_name)

    for x1s, y1s, x2s, y2s, w, ln, nn in tracks:
        mark_seg(x1s, y1s, x2s, y2s, w, 0 if ln == "F.Cu" else 1, nn)
    for vx, vy, vsz, vdr, nn in vias:
        vclr = 0.24 if nn in POWER_NETS else 0.20
        for l in (0, 1):
            mark_circle(l, vx, vy, vsz / 2.0 + vclr, nn)
        add_hole_bucket(vx, vy, vdr, nn)

    for (ref, pnum), (l, fx, fy) in fanout_anchor.items():
        nn = pad_lookup[(ref, pnum)][4]
        gx, gy = to_g(fx, fy)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < gw and 0 <= ny < gh and blocked[l][nx][ny] == "":
                    blocked[l][nx][ny] = nn

    via_holes = [(vx, vy, vdr, nn) for vx, vy, _, vdr, nn in vias]
    for _, _, wx, wy, p, is_pth, nname in all_pads:
        if is_pth:
            via_holes.append((wx, wy, pcbnew.ToMM(p.GetDrillSize().x), nname))

    def cell_ok(l, gx, gy, net_name, track_w, ripup_nets=None):
        if not (0 <= gx < gw and 0 <= gy < gh):
            return False
        blk = blocked[l][gx][gy]
        if blk not in ("", net_name) and not (ripup_nets and blk in ripup_nets):
            return False
        wx, wy = to_w(gx, gy)
        req_hole_dist = 0.28 + track_w / 2.0
        for hx, hy, hr, hnet in hole_buckets.get((int(wx), int(wy)), ()):
            if hnet != net_name and not (ripup_nets and hnet in ripup_nets) and math.hypot(wx - hx, wy - hy) < hr + req_hole_dist:
                return False
        if track_w >= 0.38:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = gx + dx, gy + dy
                    if not (0 <= nx < gw and 0 <= ny < gh):
                        return False
                    nb = blocked[l][nx][ny]
                    if nb not in ("", net_name) and not (ripup_nets and nb in ripup_nets):
                        return False
        elif track_w > 0.21:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = gx + dx, gy + dy
                if not (0 <= nx < gw and 0 <= ny < gh):
                    return False
                nb = blocked[l][nx][ny]
                if nb not in ("", net_name) and not (ripup_nets and nb in ripup_nets):
                    return False
        return True

    def via_ok(vx, vy, net_name, ripup_nets=None):
        if _in_ic_apron(vx, vy):
            return False
        gx, gy = to_g(vx, vy)
        if not (0 <= gx < gw and 0 <= gy < gh):
            return False
        for l in (0, 1):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = gx + dx, gy + dy
                    if not (0 <= nx < gw and 0 <= ny < gh):
                        return False
                    nb = blocked[l][nx][ny]
                    if nb not in ("", net_name) and not (ripup_nets and nb in ripup_nets):
                        return False
        for hx, hy, hr, hnet in hole_buckets.get((int(vx), int(vy)), ()):
            if not (ripup_nets and hnet in ripup_nets):
                if math.hypot(vx - hx, vy - hy) < 0.15 + hr + 0.35:
                    return False
        return True

    # 5. Connect SMD GND pads to In1.Cu/B.Cu via local or routed GND vias
    gnd_vias = [(vx, vy) for vx, vy, _, _, nn in vias if nn == "GND"]
    gnd_todo = []
    for ref, pnum, wx, wy, _, is_pth in pad_objs["GND"]:
        if (
            is_pth
            or (ref in ("U11", "U101") and pnum in ("49", "25"))
            or (ref == "U101" and pnum in ("10", "12", "13", "22"))
            or (ref == "U503" and pnum in ("5", "9"))
            or (ref in ("U501", "U502") and pnum == "2")
        ):
            if is_pth:
                gnd_vias.append((wx, wy))
            continue
        if (
            ref in FINE_ICS
            and (ref, pnum) in fanout_anchor
            and fanout_anchor[(ref, pnum)][0] == 1
        ):
            _, fx, fy = fanout_anchor[(ref, pnum)]
            gnd_vias.append((fx, fy))
            continue
        if ref in FINE_ICS:
            gnd_todo.append((ref, pnum, wx, wy, is_pth))
            continue
        sx, sy = (
            fanout_anchor[(ref, pnum)][1:]
            if (ref, pnum) in fanout_anchor
            else (wx, wy)
        )
        best = None
        gx0, gy0 = to_g(sx, sy)
        for r in range(0, 10):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if r > 0 and abs(dx) != r and abs(dy) != r:
                        continue
                    vx, vy = to_w(gx0 + dx, gy0 + dy)
                    if via_ok(vx, vy, "GND"):
                        d = math.hypot(vx - sx, vy - sy)
                        if best is None or d < best[0]:
                            best = (d, vx, vy)
            if best is not None and best[0] <= 1.5:
                break
        if best:
            _, vx, vy = best
            add_seg(sx, sy, vx, vy, 0.20, "F.Cu", "GND")
            add_via(vx, vy, "GND", 0.50, 0.30)
            mark_seg(sx, sy, vx, vy, 0.20, 0, "GND")
            for l in (0, 1):
                mark_circle(l, vx, vy, 0.47, "GND")
            via_holes.append((vx, vy, 0.30, "GND"))
            add_hole_bucket(vx, vy, 0.30, "GND")
            gnd_vias.append((vx, vy))
        else:
            gnd_todo.append((ref, pnum, wx, wy, is_pth))

    debug_route = bool(os.environ.get("MR1_DEBUG_ROUTE"))
    hist_cost = defaultdict(float)

    def can_leave_set(pts, net_name, track_w, ripup_nets=None):
        if track_w <= 0.21 or len(pts) > 24:
            return True
        for pl, pgx, pgy in pts:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if cell_ok(pl, pgx + dx, pgy + dy, net_name, track_w, ripup_nets):
                        return True
        return False

    def _local_reachable(seed_pts, target_set, net_name, track_w, ripup_nets=None, limit=1500):
        """Fast bounded BFS to detect locally boxed-in endpoints without burning full A*."""
        if ripup_nets is not None or len(seed_pts) > 8:
            return True
        seen = set(seed_pts)
        q = list(seed_pts)
        qi = 0
        dirs4 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
        while qi < len(q):
            ul, ugx, ugy = q[qi]
            qi += 1
            if (ul, ugx, ugy) in target_set:
                return True
            if len(seen) >= limit:
                return True
            for dx, dy in dirs4:
                nx, ny = ugx + dx, ugy + dy
                v = (ul, nx, ny)
                if v in seen:
                    continue
                if v in target_set:
                    return True
                if not cell_ok(ul, nx, ny, net_name, track_w, ripup_nets):
                    continue
                if dx != 0 and dy != 0:
                    b1 = blocked[ul][ugx + dx][ugy]
                    b2 = blocked[ul][ugx][ugy + dy]
                    if b1 not in ("", net_name) or b2 not in ("", net_name):
                        continue
                seen.add(v)
                q.append(v)
            ol = 1 - ul
            v = (ol, ugx, ugy)
            if v not in seen:
                wx, wy = to_w(ugx, ugy)
                if via_ok(wx, wy, net_name, ripup_nets=ripup_nets):
                    seen.add(v)
                    q.append(v)
        return False

    def astar(start_pts, goal_pts, net_name, track_w=0.20, ripup_nets=None, max_iters_override=None):
        goal_set = set(goal_pts)
        start_set = set(start_pts)
        if not start_pts or not goal_pts:
            return None
        if not can_leave_set(start_pts, net_name, track_w, ripup_nets):
            return None
        if not can_leave_set(goal_pts, net_name, track_w, ripup_nets):
            return None
        if not _local_reachable(start_pts, goal_set, net_name, track_w, ripup_nets):
            return None
        if not _local_reachable(goal_pts, start_set, net_name, track_w, ripup_nets):
            return None
        pq = []
        dist = {}
        closed = set()
        parent = {}
        tx = sum(g[1] for g in goal_pts) / len(goal_pts)
        ty = sum(g[2] for g in goal_pts) / len(goal_pts)
        for st in start_pts:
            dist[st] = 0.0
            heapq.heappush(pq, (abs(st[1] - tx) + abs(st[2] - ty), 0.0, st))
        dirs = [
            (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
            (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414),
        ]
        iters = 0
        max_iters = max_iters_override if max_iters_override is not None else (200000 if ripup_nets else 120000)
        while pq and iters < max_iters:
            iters += 1
            _, g, u = heapq.heappop(pq)
            if u in closed or g > dist.get(u, 1e18):
                continue
            closed.add(u)
            if u in goal_set:
                path = []
                cur = u
                while cur in parent:
                    path.append(cur)
                    cur = parent[cur]
                path.append(cur)
                path.reverse()
                return path
            ul, ugx, ugy = u
            for dx, dy, step_cost in dirs:
                nx, ny = ugx + dx, ugy + dy
                if not cell_ok(ul, nx, ny, net_name, track_w, ripup_nets) and (ul, nx, ny) not in goal_set:
                    continue
                if dx != 0 and dy != 0:
                    b1 = blocked[ul][ugx + dx][ugy]
                    b2 = blocked[ul][ugx][ugy + dy]
                    if (b1 not in ("", net_name) and not (ripup_nets and b1 in ripup_nets)) or (
                        b2 not in ("", net_name) and not (ripup_nets and b2 in ripup_nets)
                    ):
                        continue
                v = (ul, nx, ny)
                pen = 0.0
                if ripup_nets:
                    bv = blocked[ul][nx][ny]
                    if bv in ripup_nets:
                        pen = 15.0
                ng = g + step_cost + pen + hist_cost.get(v, 0.0)
                if ng < dist.get(v, 1e18):
                    dist[v] = ng
                    parent[v] = u
                    heapq.heappush(pq, (ng + math.hypot(nx - tx, ny - ty) * 1.35, ng, v))
            ol = 1 - ul
            wx, wy = to_w(ugx, ugy)
            if via_ok(wx, wy, net_name, ripup_nets=ripup_nets):
                v = (ol, ugx, ugy)
                vpen = 0.0
                if ripup_nets:
                    for dxv in (-1, 0, 1):
                        for dyv in (-1, 0, 1):
                            for lv in (0, 1):
                                nxv, nyv = ugx + dxv, ugy + dyv
                                if 0 <= nxv < gw and 0 <= nyv < gh and blocked[lv][nxv][nyv] in ripup_nets:
                                    vpen = 15.0
                vhist = hist_cost.get((0, ugx, ugy), 0.0) + hist_cost.get((1, ugx, ugy), 0.0)
                ng = g + 6.0 + vpen + vhist
                if ng < dist.get(v, 1e18):
                    dist[v] = ng
                    parent[v] = u
                    heapq.heappush(pq, (ng + math.hypot(ugx - tx, ugy - ty) * 1.35, ng, v))
        if debug_route and iters >= max_iters:
            print(f"  [ASTAR MAX_ITERS {iters}] {net_name} rip={bool(ripup_nets)} st={len(start_pts)} gl={len(goal_pts)}", flush=True)
        elif debug_route and not pq:
            print(f"  [ASTAR EMPTY_PQ {iters}] {net_name} rip={bool(ripup_nets)} st={len(start_pts)} gl={len(goal_pts)}", flush=True)
        return None

    def get_node_anchor(ref, pnum, wx, wy, is_pth, net_name):
        if (ref, pnum) in fanout_anchor:
            l, fx, fy = fanout_anchor[(ref, pnum)]
            return fx, fy, [(l, *to_g(fx, fy))]
        gx, gy = to_g(wx, wy)
        pts = []
        for l in ([0, 1] if is_pth else [0]):
            if blocked[l][gx][gy] in ("", net_name):
                pts.append((l, gx, gy))
        if not pts:
            for l in ([0, 1] if is_pth else [0]):
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = gx + dx, gy + dy
                        if 0 <= nx < gw and 0 <= ny < gh and blocked[l][nx][ny] in ("", net_name):
                            pts.append((l, nx, ny))
        return wx, wy, pts

    net_tree_pts = defaultdict(set)

    # 6. Connect In2.Cu power island pads directly with local vias
    for pnet, in_fn in ISLAND_BOXES.items():
        for ref, pnum, wx, wy, _, is_pth in pad_objs[pnet]:
            if is_pth:
                if in_fn(wx, wy):
                    power_island_vias[pnet].append((wx, wy))
                    connected_power_pads.add((ref, pnum))
                continue
            if (ref, pnum) in connected_power_pads:
                continue
            if (
                ref in FINE_ICS
                and (ref, pnum) in fanout_anchor
                and fanout_anchor[(ref, pnum)][0] == 1
            ):
                _, fx, fy = fanout_anchor[(ref, pnum)]
                if in_fn(fx, fy):
                    power_island_vias[pnet].append((fx, fy))
                    connected_power_pads.add((ref, pnum))
                continue
            if ref in FINE_ICS:
                continue
            ax, ay, _ = get_node_anchor(ref, pnum, wx, wy, is_pth, pnet)
            if in_fn(ax, ay):
                gx0, gy0 = to_g(ax, ay)
                best = None
                for r in range(0, 10):
                    for dx in range(-r, r + 1):
                        for dy in range(-r, r + 1):
                            vx, vy = to_w(gx0 + dx, gy0 + dy)
                            if in_fn(vx, vy) and via_ok(vx, vy, pnet):
                                d = math.hypot(vx - ax, vy - ay)
                                if best is None or d < best[0]:
                                    best = (d, vx, vy)
                    if best and best[0] <= 1.5:
                        break
                if best:
                    _, vx, vy = best
                    add_seg(ax, ay, vx, vy, 0.25, "F.Cu", pnet)
                    add_via(vx, vy, pnet, 0.50, 0.30)
                    mark_seg(ax, ay, vx, vy, 0.25, 0, pnet)
                    for l in (0, 1):
                        mark_circle(l, vx, vy, 0.47, pnet)
                    via_holes.append((vx, vy, 0.30, pnet))
                    add_hole_bucket(vx, vy, 0.30, pnet)
                    power_island_vias[pnet].append((vx, vy))
                    connected_power_pads.add((ref, pnum))

    def emit_path(path, ax_start, ay_start, ax_end, ay_end, w_use, nname, tree_set=None, seg_rec=None, via_rec=None):
        def rec_seg(x1s, y1s, x2s, y2s, ws, ls):
            if abs(x1s - x2s) < 1e-4 and abs(y1s - y2s) < 1e-4:
                return
            add_seg(x1s, y1s, x2s, y2s, ws, ls, nname)
            if seg_rec is not None:
                seg_rec.append((x1s, y1s, x2s, y2s, ws, ls, nname))

        def rec_via(vx, vy):
            add_via(vx, vy, nname, 0.50, 0.30)
            if via_rec is not None:
                via_rec.append((vx, vy, 0.50, 0.30, nname))

        sx, sy = to_w(path[0][1], path[0][2])
        rec_seg(ax_start, ay_start, sx, sy, w_use, "F.Cu" if path[0][0] == 0 else "B.Cu")
        mark_seg(ax_start, ay_start, sx, sy, w_use, path[0][0], nname)
        if ax_end is not None:
            ex, ey = to_w(path[-1][1], path[-1][2])
            rec_seg(ex, ey, ax_end, ay_end, w_use, "F.Cu" if path[-1][0] == 0 else "B.Cu")
            mark_seg(ex, ey, ax_end, ay_end, w_use, path[-1][0], nname)
        for k in range(len(path) - 1):
            l1, gx1, gy1 = path[k]
            l2, gx2, gy2 = path[k + 1]
            x1w, y1w = to_w(gx1, gy1)
            x2w, y2w = to_w(gx2, gy2)
            if l1 != l2:
                rec_via(x1w, y1w)
                for l in (0, 1):
                    mark_circle(l, x1w, y1w, 0.47, nname)
                via_holes.append((x1w, y1w, 0.30, nname))
                add_hole_bucket(x1w, y1w, 0.30, nname)
            else:
                rec_seg(x1w, y1w, x2w, y2w, w_use, "F.Cu" if l1 == 0 else "B.Cu")
                mark_seg(x1w, y1w, x2w, y2w, w_use, l1, nname)
        if tree_set is not None:
            for pt in path:
                tree_set.add(pt)

    failed_nets = []
    for ref, pnum, wx, wy, is_pth in gnd_todo:
        ax, ay, st = get_node_anchor(ref, pnum, wx, wy, is_pth, "GND")
        nearest = sorted(gnd_vias, key=lambda v: math.hypot(v[0] - ax, v[1] - ay))[:8]
        gl = [(0, *to_g(vx, vy)) for vx, vy in nearest] + [
            (1, *to_g(vx, vy)) for vx, vy in nearest
        ]
        path = astar(st, gl, "GND", track_w=0.20)
        if path is None:
            failed_nets.append(("GND", f"{ref}.{pnum}"))
        else:
            gx_end, gy_end = path[-1][1], path[-1][2]
            ex_w, ey_w = to_w(gx_end, gy_end)
            exact_v = min(nearest, key=lambda v: math.hypot(v[0] - ex_w, v[1] - ey_w))
            emit_path(path, ax, ay, exact_v[0], exact_v[1], 0.20, "GND")

    boost_set = {n: i for i, n in enumerate(boost_nets)}

    def net_priority(item):
        nname = item
        if nname in boost_set:
            return (-1, boost_set[nname], nname)
        nodes = pad_objs[nname]
        if nname in ("/Motor_Drivers/VMOTOR", "/Power_PD/+5V_BUCK"):
            return (1, 0, nname)
        if nname in ISLAND_BOXES:
            return (3, len(nodes), nname)
        xs = [n[2] for n in nodes]
        ys = [n[3] for n in nodes]
        span = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        return (0 if span < 20 else 2, span, nname)

    skip_nets = {
        "",
        "GND",
        "/USB_Interconnect/HOST_D+",
        "/USB_Interconnect/HOST_D-",
        "/USB_Interconnect/HOST_MUX_D+",
        "/USB_Interconnect/HOST_MUX_D-",
        "/USB_Interconnect/MR1_D+",
        "/USB_Interconnect/MR1_D-",
        "/USB_Interconnect/MR1_MUX_D+",
        "/USB_Interconnect/MR1_MUX_D-",
        "/MCU_STM32/USB_MCU_D+",
        "/MCU_STM32/USB_MCU_D-",
        "/MCU_STM32/HSE_IN",
        "/MCU_STM32/HSE_OUT",
        "/MCU_STM32/VDDA",
        "/Power_PD/TPS_CT",
        "Net-(U103-QOD)",
        "Net-(U102-SW)",
        "Net-(D201-A)",
        "Net-(D202-A)",
        "Net-(D203-A)",
        "Net-(D204-A)",
        "Net-(D205-A)",
    }

    base_blocked = [[row[:] for row in layer] for layer in blocked]
    base_hole_buckets = {k: list(v) for k, v in hole_buckets.items()}
    base_via_holes = list(via_holes)
    base_tracks_len = len(tracks)
    base_vias_len = len(vias)

    routed_segs = {}
    routed_vias = {}

    def rebuild_routed():
        for li in (0, 1):
            for gxi in range(gw):
                blocked[li][gxi][:] = base_blocked[li][gxi]
        hole_buckets.clear()
        for k, v in base_hole_buckets.items():
            hole_buckets[k] = list(v)
        via_holes[:] = base_via_holes
        del tracks[base_tracks_len:]
        del vias[base_vias_len:]
        for r_net, segs in routed_segs.items():
            for x1s, y1s, x2s, y2s, ws, ls, nn in segs:
                tracks.append((x1s, y1s, x2s, y2s, ws, ls, nn))
                mark_seg(x1s, y1s, x2s, y2s, ws, 0 if ls == "F.Cu" else 1, nn)
        for r_net, vlist in routed_vias.items():
            for vx, vy, vsz, vdr, nn in vlist:
                vias.append((vx, vy, vsz, vdr, nn))
                for l in (0, 1):
                    mark_circle(l, vx, vy, 0.47, nn)
                via_holes.append((vx, vy, vdr, nn))
                add_hole_bucket(vx, vy, vdr, nn)

    def _collect_path_conflicts(path, ripup_nets, victims, conflict_cells):
        for k_p, (pl, pgx, pgy) in enumerate(path):
            is_via_step = k_p + 1 < len(path) and path[k_p + 1][0] != pl
            rad = 3 if is_via_step else 2
            layers_chk = (0, 1) if is_via_step else (pl,)
            for lchk in layers_chk:
                for dx in range(-rad, rad + 1):
                    for dy in range(-rad, rad + 1):
                        nx, ny = pgx + dx, pgy + dy
                        if 0 <= nx < gw and 0 <= ny < gh:
                            b = blocked[lchk][nx][ny]
                            if b in ripup_nets:
                                victims.add(b)
                                if abs(dx) <= 1 and abs(dy) <= 1:
                                    conflict_cells.add((lchk, nx, ny))
            wx_p, wy_p = to_w(pgx, pgy)
            for hx, hy, hr, hnet in hole_buckets.get((int(wx_p), int(wy_p)), ()):
                if hnet in ripup_nets:
                    lim = (0.15 + hr + 0.35) if is_via_step else (hr + 0.36)
                    if math.hypot(wx_p - hx, wy_p - hy) < lim:
                        victims.add(hnet)
                        conflict_cells.add((pl, pgx, pgy))

    def try_route_net(nname, ripup_nets=None, max_iters_override=None):
        nodes = pad_objs[nname]
        is_power_net = any(
            k in nname
            for k in ("VMOTOR", "+5V_", "+VBUS_PD", "PUMP1_OUT", "PUMP2_OUT", "U102-SW")
        )
        width_candidates = (0.50, 0.40, 0.28, 0.20) if is_power_net else (0.20,)
        segs_out = []
        vias_out = []
        victims = set()
        conflict_cells = set()
        net_tree_pts[nname].clear()

        if nname in ISLAND_BOXES:
            island_anchors_exact = list(power_island_vias[nname])
            island_pts = set()
            for vx, vy in island_anchors_exact:
                gx, gy = to_g(vx, vy)
                island_pts.add((0, gx, gy))
                island_pts.add((1, gx, gy))
            rem_nodes = [n for n in nodes if (n[0], n[1]) not in connected_power_pads]
            for ref, pnum, wx, wy, _, is_pth in rem_nodes:
                ax, ay, st = get_node_anchor(ref, pnum, wx, wy, is_pth, nname)
                gl = list(island_pts | net_tree_pts[nname])
                w_use = width_candidates[-1]
                path = None
                cands = (width_candidates[-1],) if ripup_nets is not None else width_candidates
                for cand_w in cands:
                    path = astar(st, gl, nname, track_w=cand_w, ripup_nets=ripup_nets, max_iters_override=max_iters_override)
                    if path is not None:
                        w_use = cand_w
                        break
                if path is None:
                    return False, f"{ref}.{pnum}->island", victims, conflict_cells
                if ripup_nets is not None:
                    _collect_path_conflicts(path, ripup_nets, victims, conflict_cells)
                    continue
                end_pt = path[-1]
                ex_w, ey_w = to_w(end_pt[1], end_pt[2])
                ax_end, ay_end = None, None
                if end_pt in island_pts:
                    exact_v = min(
                        island_anchors_exact,
                        key=lambda v: math.hypot(v[0] - ex_w, v[1] - ey_w),
                    )
                    if math.hypot(exact_v[0] - ex_w, exact_v[1] - ey_w) > 1e-3:
                        ax_end, ay_end = exact_v[0], exact_v[1]
                emit_path(path, ax, ay, ax_end, ay_end, w_use, nname, net_tree_pts[nname], segs_out, vias_out)
            if ripup_nets is not None:
                return True, None, victims, conflict_cells
            routed_segs[nname] = segs_out
            routed_vias[nname] = vias_out
            return True, None, victims, conflict_cells

        n_cnt = len(nodes)
        connected = {0}
        ax0, ay0, init_pts = get_node_anchor(
            nodes[0][0], nodes[0][1], nodes[0][2], nodes[0][3], nodes[0][5], nname
        )
        anchor_coords = {pt: (ax0, ay0) for pt in init_pts}
        tree_pts = set(init_pts)
        used_init0 = False
        remaining = set(range(1, n_cnt))
        while remaining:
            best_pair = None
            for u in connected:
                for v in remaining:
                    d = math.hypot(nodes[u][2] - nodes[v][2], nodes[u][3] - nodes[v][3])
                    if best_pair is None or d < best_pair[0]:
                        best_pair = (d, u, v)
            _, _, v = best_pair
            ref_v, pnum_v, wx_v, wy_v, _, is_pth_v = nodes[v]
            ax_v, ay_v, st = get_node_anchor(ref_v, pnum_v, wx_v, wy_v, is_pth_v, nname)
            w_use = width_candidates[-1]
            path = None
            cands = (width_candidates[-1],) if ripup_nets is not None else width_candidates
            for cand_w in cands:
                path = astar(st, list(tree_pts), nname, track_w=cand_w, ripup_nets=ripup_nets, max_iters_override=max_iters_override)
                if path is not None:
                    w_use = cand_w
                    break
            if path is None:
                return False, f"{ref_v}.{pnum_v}->tree", victims, conflict_cells
            if ripup_nets is not None:
                _collect_path_conflicts(path, ripup_nets, victims, conflict_cells)
                for pt in path:
                    tree_pts.add(pt)
            else:
                end_pt = path[-1]
                ax_end, ay_end = anchor_coords.get(end_pt, (None, None))
                emit_path(path, ax_v, ay_v, ax_end, ay_end, w_use, nname, tree_pts, segs_out, vias_out)
                if end_pt in init_pts and not used_init0:
                    used_init0 = True
                    for p0 in init_pts:
                        if p0 != end_pt:
                            tree_pts.discard(p0)
                            anchor_coords.pop(p0, None)
            connected.add(v)
            remaining.remove(v)
        if ripup_nets is None:
            routed_segs[nname] = segs_out
            routed_vias[nname] = vias_out
        return True, None, victims, conflict_cells

    in_step6 = True
    pending = [
        nname
        for nname in sorted(pad_objs, key=net_priority)
        if nname not in skip_nets and not nname.startswith("unconnected-") and len(pad_objs[nname]) > 1
    ]
    ripup_budget = 180
    rip_count = defaultdict(int)
    while pending:
        nname = pending.pop(0)
        ok, fail_msg, _, _ = try_route_net(nname, ripup_nets=None)
        if ok:
            continue
        rebuild_routed()
        if ripup_budget > 0 and rip_count[nname] < 25:
            ripup_budget -= 1
            rip_count[nname] += 1
            cand_rip = set(routed_segs.keys()) - {nname}
            if cand_rip:
                ok2, fail_msg2, victims, conflict_cells = try_route_net(nname, ripup_nets=cand_rip)
                if debug_route:
                    print(f"[RIP #{180-ripup_budget}] {nname} fail={fail_msg} ok2={ok2} fail2={fail_msg2} victims={sorted(victims)}", flush=True)
                if ok2 and victims:
                    for cl, cgx, cgy in conflict_cells:
                        hist_cost[(cl, cgx, cgy)] = min(16.0, hist_cost[(cl, cgx, cgy)] + 1.5)
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            if 0 <= cgx + dx < gw and 0 <= cgy + dy < gh:
                                hist_cost[(cl, cgx + dx, cgy + dy)] = min(16.0, hist_cost[(cl, cgx + dx, cgy + dy)] + 0.5)
                    saved_victims = {
                        vn: (routed_segs.pop(vn, None), routed_vias.pop(vn, None))
                        for vn in victims
                    }
                    rebuild_routed()
                    ok3, fail_msg3, _, _ = try_route_net(nname, ripup_nets=None, max_iters_override=200000)
                    if ok3:
                        for vn in sorted(victims):
                            if vn not in pending:
                                pending.append(vn)
                        continue
                    if debug_route:
                        print(f"  [OK3 FAIL] {nname} fail3={fail_msg3}", flush=True)
                    for vn, (sv_s, sv_v) in saved_victims.items():
                        if sv_s is not None:
                            routed_segs[vn] = sv_s
                        if sv_v is not None:
                            routed_vias[vn] = sv_v
                    rebuild_routed()
                    for cl, cgx, cgy in conflict_cells:
                        hist_cost[(cl, cgx, cgy)] = min(16.0, hist_cost[(cl, cgx, cgy)] + 2.0)
                    if rip_count[nname] < 25 and nname not in pending:
                        pending.append(nname)
                        continue
                    fail_msg = fail_msg3 or fail_msg
        if debug_route:
            print(f"[GIVEUP] {nname} budget={ripup_budget} count={rip_count[nname]} fail={fail_msg}", flush=True)
        failed_nets.append((nname, fail_msg or "failed"))
    in_step6 = False

    # 7. Post-route GND stitching vias on open 5mm grid within compact envelope
    gnd_stitch_pts = [(vx, vy) for vx, vy, _, _, nn in vias if nn == "GND"]
    for vx_c_i in range(58, 143, 5):
        for vy_c_i in range(58, 106, 5):
            vx_c, vy_c = float(vx_c_i), float(vy_c_i)
            if any(math.hypot(vx_c - gx, vy_c - gy) < 5.0 for gx, gy in gnd_stitch_pts):
                continue
            if via_ok(vx_c, vy_c, "GND"):
                add_via(vx_c, vy_c, "GND", 0.50, 0.30)
                for l in (0, 1):
                    mark_circle(l, vx_c, vy_c, 0.47, "GND")
                via_holes.append((vx_c, vy_c, 0.30, "GND"))
                add_hole_bucket(vx_c, vy_c, 0.30, "GND")
                gnd_stitch_pts.append((vx_c, vy_c))

    return tracks, vias, failed_nets


def build_pump_board(out_path: Path = PUMP_PCB_PATH) -> Path:
    """Build, route, zone-fill, and save Pump.kicad_pcb deterministically from Pump.kicad_sch."""
    pcbnew = _ensure_pcbnew()
    if not PUMP_SCH_PATH.exists():
        raise FileNotFoundError(f"Pump schematic not found: {PUMP_SCH_PATH}")

    with tempfile.TemporaryDirectory(prefix="pump_pcb_gen_") as td_str:
        td = Path(td_str)
        comps, nets = export_and_parse_netlist(PUMP_SCH_PATH, td)

        skel_pcb = td / "Pump.kicad_pcb"
        skel_pro = td / "Pump.kicad_pro"
        skel_dru = td / "Pump.kicad_dru"
        skel_pcb.write_text(PCB_HEADER_TEMPLATE + ")\n", encoding="utf-8")
        if PUMP_PRO_PATH.exists():
            shutil.copy2(PUMP_PRO_PATH, skel_pro)
        if (PUMP_DIR / "Pump.kicad_dru").exists():
            shutil.copy2(PUMP_DIR / "Pump.kicad_dru", skel_dru)

        board = pcbnew.LoadBoard(str(skel_pcb))

        # 1. Register all schematic nets (68 active + 27 unconnected)
        net_map = {}
        pad_net_map = {}
        for n in nets:
            nname = next(x[1] for x in n[1:] if isinstance(x, list) and x[0] == "name")
            ni = pcbnew.NETINFO_ITEM(board, nname)
            board.Add(ni)
            net_map[nname] = ni
            for node in n[1:]:
                if isinstance(node, list) and node[0] == "node":
                    ref = next(x[1] for x in node[1:] if isinstance(x, list) and x[0] == "ref")
                    pin = next(x[1] for x in node[1:] if isinstance(x, list) and x[0] == "pin")
                    pad_net_map[(ref, pin)] = nname

        # 2. Chamfered 88.0 x 51.8 mm Edge.Cuts outline (X=[56.0, 144.0], Y=[56.0, 107.8], 2.0 mm chamfers)
        x1, y1, x2, y2, ch = 56.0, 56.0, 144.0, 107.8, 2.0
        outline_pts = [
            (x1 + ch, y1), (x2 - ch, y1), (x2, y1 + ch), (x2, y2 - ch),
            (x2 - ch, y2), (x1 + ch, y2), (x1, y2 - ch), (x1, y1 + ch),
        ]
        for idx in range(len(outline_pts)):
            p1 = outline_pts[idx]
            p2 = outline_pts[(idx + 1) % len(outline_pts)]
            seg = pcbnew.PCB_SHAPE(board)
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(pcbnew.FromMM(0.15))
            seg.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(p1[0]), pcbnew.FromMM(p1[1])))
            seg.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(p2[0]), pcbnew.FromMM(p2[1])))
            board.Add(seg)

        # 3. Load all 89 KiCad 10 footprints unmodified and sync full parity metadata
        pad_objs = defaultdict(list)
        all_pads = []
        for c in comps:
            attrs = {x[0]: x[1:] for x in c[1:] if isinstance(x, list)}
            ref = attrs["ref"][0]
            val = attrs["value"][0]
            fp_full = attrs["footprint"][0]
            lib, fpname = fp_full.split(":", 1)
            fp_lib_dir = KICAD_FOOTPRINT_DIR / f"{lib}.pretty"
            fp = pcbnew.FootprintLoad(str(fp_lib_dir), fpname)
            if fp is None:
                raise RuntimeError(f"Failed to load footprint {fp_full} from {fp_lib_dir}")
            fp.SetFPID(pcbnew.LIB_ID(lib, fpname))
            fp.SetReference(ref)
            fp.SetValue(val)

            sp_node = next(x for x in c[1:] if isinstance(x, list) and x[0] == "sheetpath")
            sp_ts = next(x[1] for x in sp_node[1:] if x[0] == "tstamps")
            comp_ts = attrs["tstamps"][0]
            full_path = sp_ts + comp_ts if sp_ts.endswith("/") else sp_ts + "/" + comp_ts
            fp.SetPath(pcbnew.KIID_PATH(full_path))

            flags = set()
            props = {}
            for item in c[1:]:
                if isinstance(item, list) and item[0] == "property":
                    pname = next(x[1] for x in item[1:] if x[0] == "name")
                    pvals = [x[1] for x in item[1:] if x[0] == "value"]
                    if pvals:
                        props[pname] = pvals[0]
                    else:
                        flags.add(pname)
            fp.SetExcludedFromBOM("exclude_from_bom" in flags)
            fp.SetExcludedFromPosFiles("exclude_from_pos_files" in flags)
            fp.SetDNP("dnp" in flags)

            fields = {}
            for item in c[1:]:
                if isinstance(item, list) and item[0] == "fields":
                    for f in item[1:]:
                        fname = next(x[1] for x in f[1:] if x[0] == "name")
                        fval = f[2] if len(f) > 2 and isinstance(f[2], str) else ""
                        fields[fname] = fval
            for k, v in fields.items():
                if k == "Footprint":
                    continue
                if not fp.HasField(k):
                    fld = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, k)
                    fld.SetVisible(False)
                    fp.Add(fld)
                fp.SetField(k, v)
            if "Sheetname" in props:
                fp.SetSheetname(props["Sheetname"])
            if "Sheetfile" in props:
                fp.SetSheetfile(props["Sheetfile"])

            if ref not in PLACEMENT:
                raise KeyError(f"Missing placement entry for schematic component {ref}")
            px, py, prot = PLACEMENT[ref]
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)))
            fp.SetOrientationDegrees(prot)

            ref_txt = fp.Reference()
            ref_txt.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
            ref_txt.SetTextThickness(pcbnew.FromMM(0.12))
            if ref in REF_WORLD_POS:
                rx, ry = REF_WORLD_POS[ref]
                ref_txt.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(rx), pcbnew.FromMM(ry)))
                ref_txt.SetTextAngleDegrees(0)

            for p in fp.Pads():
                pnum = p.GetNumber()
                if pnum == "":
                    continue
                nname = pad_net_map.get((ref, pnum))
                if nname is not None:
                    p.SetNet(net_map[nname])
                pos = p.GetPosition()
                wx, wy = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
                is_pth = p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
                if (ref in ("U11", "U101") and pnum in ("49", "25")) or ref in (
                    "J6",
                    "J7",
                ):
                    p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
                pad_objs[nname or ""].append((ref, pnum, wx, wy, p, is_pth))
                all_pads.append((ref, pnum, wx, wy, p, is_pth, nname or ""))

            board.Add(fp)

        # 4. Add 4-layer copper zones (In1.Cu solid GND, B.Cu GND flood, In2.Cu 5 power islands)
        def add_zone(net_name, layer_name, poly_pts, clearance=0.25):
            z = pcbnew.ZONE(board)
            z.SetNet(net_map[net_name])
            z.SetLayer(board.GetLayerID(layer_name))
            z.SetAssignedPriority(0)
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            z.SetMinIslandArea(int(3.0 * 1e12))
            z.SetLocalClearance(pcbnew.FromMM(clearance))
            z.SetMinThickness(pcbnew.FromMM(0.20))
            z.SetThermalReliefGap(pcbnew.FromMM(0.25))
            z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.25))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            ol = z.Outline()
            ol.NewOutline()
            for px_z, py_z in poly_pts:
                ol.Append(pcbnew.FromMM(px_z), pcbnew.FromMM(py_z))
            board.Add(z)

        board_zone_pts = [
            (56.5, 59.0), (59.0, 56.5), (141.0, 56.5), (143.5, 59.0),
            (143.5, 104.8), (141.0, 107.3), (59.0, 107.3), (56.5, 104.8),
        ]
        add_zone("GND", "In1.Cu", board_zone_pts, clearance=0.25)
        add_zone("GND", "B.Cu", board_zone_pts, clearance=0.25)
        for pnet, pts_p in ISLAND_POLYS.items():
            add_zone(pnet, "In2.Cu", pts_p, clearance=0.25)

        # 5. Deterministic multi-layer routing with priority-boost retry
        boost = [
            "/MCU_STM32/PUMP1_STEP",
            "/MCU_STM32/PUMP2_STEP",
            "/MCU_STM32/PUMP_UART",
            "/Power_PD/PD_ALERT_",
            "/Power_PD/PD_I2C_SCL",
            "/USB_Interconnect/SBU_I2C_SCL",
            "/Motor_Drivers/ESTOP_TRIGGER_",
        ]
        tracks, vias, failed = _route_board(all_pads, pad_objs, boost)
        if failed:
            raise RuntimeError(f"Unrouted net connections remained: {failed}")

        for x1t, y1t, x2t, y2t, w, ln, nn in tracks:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1t), pcbnew.FromMM(y1t)))
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2t), pcbnew.FromMM(y2t)))
            t.SetWidth(pcbnew.FromMM(w))
            t.SetLayer(board.GetLayerID(ln))
            t.SetNet(net_map[nn])
            board.Add(t)

        for vx, vy, vsz, vdr, nn in vias:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(vx), pcbnew.FromMM(vy)))
            v.SetWidth(pcbnew.FromMM(vsz))
            v.SetDrill(pcbnew.FromMM(vdr))
            v.SetLayerPair(board.GetLayerID("F.Cu"), board.GetLayerID("B.Cu"))
            v.SetNet(net_map[nn])
            board.Add(v)

        # 6. Board-level F.SilkS labels in clear open regions within 88.0 x 51.8 mm
        silk_labels = [
            ("MR1 PUMP REV 1.0", 75.0, 105.0, 0.9, 0.14),
            ("HOST USB-PD", 61.5, 71.0, 0.85, 0.14),
            ("MR1 OUT", 127.0, 61.0, 0.85, 0.14),
            ("PUMP 1", 73.75, 101.2, 0.85, 0.14),
            ("PUMP 2", 123.75, 101.2, 0.85, 0.14),
            ("CIS PRESS", 63.0, 91.5, 0.8, 0.14),
            ("TRANS PRESS", 136.0, 86.5, 0.8, 0.14),
        ]
        for label_txt, lx, ly, lsz, lth in silk_labels:
            gt = pcbnew.PCB_TEXT(board)
            gt.SetText(label_txt)
            gt.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(lx), pcbnew.FromMM(ly)))
            gt.SetLayer(pcbnew.F_SilkS)
            gt.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(lsz), pcbnew.FromMM(lsz)))
            gt.SetTextThickness(pcbnew.FromMM(lth))
            board.Add(gt)

        # 7. Fill all copper zones and write output board
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(str(skel_pcb), board)
        out_path.write_text(skel_pcb.read_text(encoding="utf-8"), encoding="utf-8")
        return out_path


def generate_pump_clean() -> str:
    """Back-compat generator returning the full Pump.kicad_pcb S-expression text."""
    try:
        import pcbnew  # noqa: F401
        with tempfile.TemporaryDirectory(prefix="pump_pcb_out_") as td:
            out_tmp = Path(td) / "Pump.kicad_pcb"
            build_pump_board(out_tmp)
            return out_tmp.read_text(encoding="utf-8")
    except ModuleNotFoundError:
        with tempfile.TemporaryDirectory(prefix="pump_pcb_sub_") as td:
            out_tmp = Path(td) / "Pump.kicad_pcb"
            subprocess.run(
                ["/usr/bin/python3", str(Path(__file__).resolve()), "--output", str(out_tmp)],
                check=True,
            )
            return out_tmp.read_text(encoding="utf-8")


def generate_pcb() -> str:
    """Back-compat alias used by tests and export tooling."""
    return generate_pump_clean()


def main():
    _ensure_pcbnew()
    parser = argparse.ArgumentParser(description="Generate and route Pump/Pump.kicad_pcb from Pump.kicad_sch")
    parser.add_argument(
        "--output",
        type=Path,
        default=PUMP_PCB_PATH,
        help="Output .kicad_pcb path (default: Pump/Pump.kicad_pcb)",
    )
    parser.add_argument(
        "--keep-net",
        action="store_true",
        help="Do not delete stale Pump/Pump.net if present",
    )
    args = parser.parse_args()

    out_path = build_pump_board(args.output)
    if not args.keep_net and args.output.resolve() == PUMP_PCB_PATH.resolve() and PUMP_NET_PATH.exists():
        PUMP_NET_PATH.unlink()
        print(f"Removed stale {PUMP_NET_PATH}")
    size = out_path.stat().st_size
    print(f"Generated {out_path} ({size} bytes)")


if __name__ == "__main__":
    main()
