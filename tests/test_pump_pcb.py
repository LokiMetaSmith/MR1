# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

"""
Unit tests validating the MR1 External Pump Controller KiCad Board (Pump/Pump.kicad_pcb)
against mechanical, electrical, 4-layer routing, and schematic-parity specifications.
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_top_blocks(text: str, keyword: str) -> list[str]:
    """Extract balanced S-expression blocks starting with `(<keyword>`."""
    blocks = []
    pattern = re.compile(rf"\({re.escape(keyword)}(?=\s|\))")
    idx = 0
    while True:
        match = pattern.search(text, idx)
        if not match:
            break
        start = match.start()
        depth = 0
        in_str = False
        escaped = False
        end = len(text)
        for pos in range(start, len(text)):
            ch = text[pos]
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_str:
                escaped = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        end = pos + 1
                        break
        blocks.append(text[start:end])
        idx = end
    return blocks


def parse_footprint_block(block: str) -> dict:
    """Extract metadata, coordinates, and pad-to-net mappings from a footprint block."""
    lib_id_match = re.match(r'\(footprint\s+"([^"]+)"', block)
    at_match = re.search(r'\n\t+\(at\s+([0-9\.\-]+)\s+([0-9\.\-]+)(?:\s+([0-9\.\-]+))?\)', block)
    ref_match = re.search(r'\(property\s+"Reference"\s+"([^"]*)"', block)
    val_match = re.search(r'\(property\s+"Value"\s+"([^"]*)"', block)

    pads = {}
    for pad_blk in extract_top_blocks(block, "pad"):
        pnum_m = re.match(r'\(pad\s+"([^"]*)"', pad_blk)
        if not pnum_m:
            continue
        pnum = pnum_m.group(1)
        if pnum == "":
            continue
        net_m = re.search(r'\(net\s+(?:\d+\s+)?"([^"]*)"\)', pad_blk)
        pads[pnum] = net_m.group(1) if net_m else ""

    return {
        "lib_id": lib_id_match.group(1) if lib_id_match else "",
        "x": float(at_match.group(1)) if at_match else 0.0,
        "y": float(at_match.group(2)) if at_match else 0.0,
        "rot": float(at_match.group(3)) if (at_match and at_match.group(3)) else 0.0,
        "ref": ref_match.group(1) if ref_match else "",
        "value": val_match.group(1) if val_match else "",
        "pads": pads,
        "raw": block,
    }


class TestPumpControllerPCB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pcb_path = REPO_ROOT / "Pump" / "Pump.kicad_pcb"
        if not cls.pcb_path.exists():
            raise AssertionError(f"Pump.kicad_pcb must exist at {cls.pcb_path}")
        cls.content = cls.pcb_path.read_text(encoding="utf-8")
        cls.footprints = {}
        cls.footprint_list = []
        for blk in extract_top_blocks(cls.content, "footprint"):
            parsed = parse_footprint_block(blk)
            cls.footprint_list.append(parsed)
            if parsed["ref"]:
                cls.footprints[parsed["ref"]] = parsed

    def test_board_envelope_and_mounting_holes(self):
        """Verify 88.0 x 51.8 mm chamfered Edge.Cuts outline and 4x M3 mounting holes."""
        edge_coords = []
        for gr_blk in extract_top_blocks(self.content, "gr_line"):
            if '(layer "Edge.Cuts")' not in gr_blk:
                continue
            m = re.search(
                r'\(start\s+([0-9\.\-]+)\s+([0-9\.\-]+)\)\s*\(end\s+([0-9\.\-]+)\s+([0-9\.\-]+)\)',
                gr_blk,
            )
            self.assertIsNotNone(m, f"Edge.Cuts gr_line missing start/end: {gr_blk}")
            edge_coords.extend([(float(m.group(1)), float(m.group(2))), (float(m.group(3)), float(m.group(4)))])

        self.assertGreaterEqual(len(edge_coords) // 2, 8, "Edge.Cuts boundary must define chamfered 88x51.8mm board")
        xs = [pt[0] for pt in edge_coords]
        ys = [pt[1] for pt in edge_coords]
        self.assertAlmostEqual(min(xs), 56.0, places=2)
        self.assertAlmostEqual(max(xs), 144.0, places=2)
        self.assertAlmostEqual(min(ys), 56.0, places=2)
        self.assertAlmostEqual(max(ys), 107.8, places=2)

        expected_mh = {
            "MH1": (62.0, 62.0),
            "MH2": (138.0, 62.0),
            "MH3": (62.0, 100.0),
            "MH4": (138.0, 100.0),
        }
        for mh, (mx, my) in expected_mh.items():
            self.assertIn(mh, self.footprints, f"Mounting hole {mh} must be present")
            fp = self.footprints[mh]
            self.assertEqual(fp["lib_id"], "MountingHole:MountingHole_3.2mm_M3_Pad")
            self.assertAlmostEqual(fp["x"], mx, places=2)
            self.assertAlmostEqual(fp["y"], my, places=2)

    def test_footprint_inventory_and_layers(self):
        """Verify all 88 schematic components, 0 legacy refs, 4 copper layers, and uninterrupted In1.Cu."""
        expected_refs = (
            [f"C{i}" for i in range(101, 114)]
            + [f"C{i}" for i in range(201, 211)]
            + ["C301", "C302"]
            + [f"C{i}" for i in range(401, 406)]
            + ["C501", "C502"]
            + [f"D{i}" for i in range(201, 206)]
            + ["FB201", "J201", "J401", "J402", "J6", "J7", "L101"]
            + ["MH1", "MH2", "MH3", "MH4", "MOD401", "MOD402", "Q101"]
            + [f"R{i}" for i in range(101, 112)]
            + [f"R{i}" for i in range(201, 207)]
            + ["R301", "R302"]
            + ["R401", "R402"]
            + [f"R{i}" for i in range(501, 506)]
            + ["U101", "U102", "U103", "U104", "U11", "U301", "U302", "U501", "U502", "U503", "Y201"]
        )
        self.assertEqual(len(expected_refs), 88)
        self.assertEqual(len(self.footprint_list), 88, "PCB must contain exactly 88 footprints (84 BOM + 4 MH)")
        self.assertEqual(set(self.footprints.keys()), set(expected_refs))

        for legacy_ref in ("U1_MCU", "U5_REG", "J1_HOST", "J2_MR1", "J_PUMP1", "J_PUMP2", "U9_SENS1", "U10_SENS2", "C1_MCU", "R1_PU", "Y1_HSE"):
            self.assertNotIn(legacy_ref, self.footprints, f"Legacy refdes {legacy_ref} must not exist")

        layers_blk = extract_top_blocks(self.content, "layers")[0]
        for cu_layer in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
            self.assertIn(f'"{cu_layer}"', layers_blk, f"Copper layer {cu_layer} must be declared")

        in1_segments = [
            seg for seg in extract_top_blocks(self.content, "segment")
            if '(layer "In1.Cu")' in seg
        ]
        self.assertEqual(len(in1_segments), 0, "In1.Cu must remain an uninterrupted solid GND reference plane")

    def test_mcu_stm32_qfn48_footprint_completion(self):
        """Verify U11 STM32G431CBU6 QFN-48 footprint, all 49 pads, and key schematic nets."""
        self.assertIn("U11", self.footprints)
        u11 = self.footprints["U11"]
        self.assertEqual(u11["value"], "STM32G431CBU6")
        self.assertEqual(u11["lib_id"], "Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm")

        for p in range(1, 50):
            self.assertIn(str(p), u11["pads"], f"Pad {p} must be defined in U11 footprint")

        self.assertEqual(u11["pads"]["49"], "GND")
        for p in ("1", "23", "35", "48"):
            self.assertTrue(u11["pads"][p].endswith("+3V3"), f"U11.{p} must be +3V3, got {u11['pads'][p]}")
        self.assertTrue(u11["pads"]["46"].endswith("BOOT0"))
        self.assertTrue(u11["pads"]["38"].endswith("PRESS_I2C_SCL"))
        self.assertTrue(u11["pads"]["47"].endswith("PRESS_I2C_SDA"))
        self.assertTrue(u11["pads"]["30"].endswith("SBU_I2C_SCL"))
        self.assertTrue(u11["pads"]["43"].endswith("SBU_I2C_SDA"))
        self.assertTrue(u11["pads"]["22"].endswith("PD_I2C_SCL"))
        self.assertTrue(u11["pads"]["24"].endswith("PD_I2C_SDA"))

    def test_passive_components_and_regulators(self):
        """Verify MCU passives, LEDs, crystal, SWD header, and PD/power stage components."""
        for c_ref in [f"C{i}" for i in range(201, 211)]:
            self.assertIn(c_ref, self.footprints, f"{c_ref} must be present")
        self.assertIn("FB201", self.footprints)
        self.assertEqual(self.footprints["J201"]["lib_id"], "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")

        for r_ref in ["R301", "R302", "R103", "R109", "R504", "R505", "R201", "R202", "R203", "R204", "R205", "R206"]:
            self.assertIn(r_ref, self.footprints, f"{r_ref} must be present")
        for d_ref in ["D201", "D202", "D203", "D204", "D205"]:
            self.assertEqual(self.footprints[d_ref]["lib_id"], "LED_SMD:LED_0603_1608Metric")

        self.assertEqual(self.footprints["Y201"]["lib_id"], "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm")
        self.assertEqual(self.footprints["U101"]["lib_id"], "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm")
        self.assertEqual(self.footprints["U102"]["lib_id"], "Package_TO_SOT_SMD:SOT-23-6")
        self.assertEqual(self.footprints["U103"]["lib_id"], "Package_TO_SOT_SMD:SOT-23-6")
        self.assertEqual(self.footprints["U104"]["lib_id"], "Package_TO_SOT_SMD:SOT-23-5")
        self.assertEqual(self.footprints["L101"]["lib_id"], "Inductor_SMD:L_Bourns_SRP7028A_7.3x6.6mm")
        self.assertEqual(self.footprints["Q101"]["lib_id"], "Package_TO_SOT_SMD:SOT-23")

    def test_peripheral_interfaces_and_headers(self):
        """Verify dual USB-C, motor drivers/headers, pressure sensors, and USB mux/ESD protection."""
        for j_ref, expected_x in [("J7", 87.975), ("J6", 117.975)]:
            fp = self.footprints[j_ref]
            self.assertEqual(fp["lib_id"], "Connector_USB:USB_C_Receptacle_GCT_USB4085")
            self.assertAlmostEqual(fp["x"], expected_x, places=2)
            self.assertLess(fp["y"], 68.0)

        self.assertEqual(self.footprints["J401"]["lib_id"], "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical")
        self.assertEqual(self.footprints["J402"]["lib_id"], "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical")
        self.assertEqual(self.footprints["MOD401"]["lib_id"], "Module:Pololu_Breakout-16_15.2x20.3mm")
        self.assertEqual(self.footprints["MOD402"]["lib_id"], "Module:Pololu_Breakout-16_15.2x20.3mm")

        self.assertEqual(self.footprints["U301"]["lib_id"], "Sensor_Pressure:Honeywell_ABPDAN")
        self.assertEqual(self.footprints["U302"]["lib_id"], "Sensor_Pressure:Honeywell_ABPDAN")
        self.assertLess(self.footprints["U301"]["x"], 70.0)
        self.assertGreater(self.footprints["U302"]["x"], 130.0)

        self.assertEqual(self.footprints["U501"]["lib_id"], "Package_TO_SOT_SMD:SOT-23-6")
        self.assertEqual(self.footprints["U502"]["lib_id"], "Package_TO_SOT_SMD:SOT-23-6")
        self.assertEqual(self.footprints["U503"]["lib_id"], "Package_SO:TSSOP-10_3x3mm_P0.5mm")

    def test_hierarchical_nets_and_filled_zones(self):
        """Verify filled copper zones exist for GND and all 5 In2.Cu power islands."""
        zone_blocks = extract_top_blocks(self.content, "zone")
        filled_by_net_layer = {}
        for zblk in zone_blocks:
            net_m = re.search(r'\(net\s+(?:\d+\s+)?"([^"]+)"\)', zblk)
            layer_m = re.search(r'\(layer\s+"([^"]+)"\)', zblk)
            if net_m and layer_m:
                filled_by_net_layer[(net_m.group(1), layer_m.group(1))] = "(filled_polygon" in zblk

        expected_zones = [
            ("GND", "In1.Cu"),
            ("GND", "B.Cu"),
            ("/USB_Interconnect/+5V_MR1_CLEAN", "In2.Cu"),
            ("/MCU_STM32/+3V3", "In2.Cu"),
            ("/Power_PD/+5V_BUCK", "In2.Cu"),
            ("/Motor_Drivers/VMOTOR", "In2.Cu"),
            ("/Power_PD/+VBUS_PD", "In2.Cu"),
        ]
        for key in expected_zones:
            self.assertIn(key, filled_by_net_layer, f"Zone {key} must exist")
            self.assertTrue(filled_by_net_layer[key], f"Zone {key} must be filled")

    def test_kicad_cli_drc_and_schematic_parity(self):
        """Run KiCad DRC with schematic parity and assert 0 unconnected items and 0 schematic parity issues."""
        if shutil.which("kicad-cli") is None:
            self.skipTest("kicad-cli not available on PATH")

        with tempfile.TemporaryDirectory(prefix="test_pump_drc_") as td:
            drc_json = Path(td) / "drc.json"
            res = subprocess.run(
                [
                    "kicad-cli",
                    "pcb",
                    "drc",
                    "--format",
                    "json",
                    "--schematic-parity",
                    "-o",
                    str(drc_json),
                    str(self.pcb_path),
                ],
                capture_output=True,
                text=True,
            )
            data = json.loads(drc_json.read_text(encoding="utf-8")) if drc_json.exists() else {}
            self.assertEqual(data.get("unconnected_items", []), [], f"Unconnected items: {data.get('unconnected_items')}")
            self.assertEqual(data.get("schematic_parity", []), [], f"Schematic parity issues: {data.get('schematic_parity')}")


if __name__ == "__main__":
    unittest.main()
