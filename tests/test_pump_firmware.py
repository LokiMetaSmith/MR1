# Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
# Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
# SPDX-License-Identifier: CC0-1.0

"""
Unit tests for MR1 Pump Controller firmware logic, packet framing,
ABP1 14-bit pressure conversion, flow rate calibration, overpressure safety,
and pure-Python schematic-to-firmware pinout consistency.
"""

import configparser
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent


def calculate_pump_checksum(sof: int, cmd: int, param: int) -> int:
    """Calculates XOR checksum matching SbuLink / pump_uart."""
    param_lsb = param & 0xFF
    param_msb = (param >> 8) & 0xFF
    return sof ^ cmd ^ param_lsb ^ param_msb


def raw_to_pressure_psi(raw_p: int, p_min: float, p_max: float) -> float:
    """Honeywell ABP1 14-bit transfer function A (10% to 90% of 2^14 counts)."""
    output_min = 1638   # 10% of 16384
    output_max = 14746  # 90% of 16384
    if raw_p <= output_min:
        return p_min
    if raw_p >= output_max:
        return p_max
    return ((raw_p - output_min) * (p_max - p_min) / (output_max - output_min)) + p_min


def decode_abp1_frame(raw16: int, p_min: float, p_max: float) -> tuple[int, float]:
    """Decode big-endian 16-bit ABP1 I2C response into (status_bits, pressure_psi)."""
    status_bits = (raw16 >> 14) & 0x03
    counts = raw16 & 0x3FFF
    return status_bits, raw_to_pressure_psi(counts, p_min, p_max)


def calculate_flow_duty(ul_per_min: float, ul_per_rev: float, max_rpm: float) -> float:
    """Calculates motor PWM duty percentage."""
    if ul_per_min <= 0.0:
        return 0.0
    rpm = ul_per_min / ul_per_rev
    duty = (rpm / max_rpm) * 100.0
    if 0.0 < duty < 15.0:
        duty = 15.0
    return min(100.0, duty)


def pack_telemetry_snapshot(
    status_flags: int,
    cis_psi: float,
    trans_psi: float,
    pump1_rate_ul_min: float,
    pump2_rate_ul_min: float,
    fault_code: int,
) -> bytes:
    """Pack 12-byte SbuLink::TelemetrySnapshot with XOR checksum."""
    cis_cp = int(round(max(-327.0, min(327.0, cis_psi)) * 100.0))
    trans_cp = int(round(max(-327.0, min(327.0, trans_psi)) * 100.0))
    r1 = int(round(max(0.0, min(6553.0, pump1_rate_ul_min)) * 10.0))
    r2 = int(round(max(0.0, min(6553.0, pump2_rate_ul_min)) * 10.0))
    payload = struct.pack(
        "<BBhhHHB",
        0xAA,
        status_flags & 0xFF,
        cis_cp,
        trans_cp,
        r1,
        r2,
        fault_code & 0xFF,
    )
    cs = 0
    for b in payload:
        cs ^= b
    return payload + bytes([cs])


def pack_pressure_only_frame(cis_psi: float, trans_psi: float) -> bytes:
    """Pack 6-byte SbuLink 0x11 pressure-only frame with both Cis and Trans psi."""
    cis_cp = int(round(max(-327.0, min(327.0, cis_psi)) * 100.0))
    trans_cp = int(round(max(-327.0, min(327.0, trans_psi)) * 100.0))
    payload = struct.pack("<Bhh", 0xAA, cis_cp, trans_cp)
    cs = 0
    for b in payload:
        cs ^= b
    return payload + bytes([cs])


def _parse_sexpr(text: str) -> list:
    """Lightweight S-expression parser for KiCad .kicad_sch files."""
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
            tokens.append(text[i:j])
            i = j

    stack: list = [[]]
    for tok in tokens:
        if tok == "(":
            lst: list = []
            stack[-1].append(lst)
            stack.append(lst)
        elif tok == ")":
            stack.pop()
        elif isinstance(tok, tuple):
            stack[-1].append(tok[1])
        else:
            stack[-1].append(tok)
    return stack[0][0]


def _find_all(node: list, tag: str) -> list:
    return [x for x in node if isinstance(x, list) and x and x[0] == tag]


def _find_one(node: list, tag: str):
    for x in node:
        if isinstance(x, list) and x and x[0] == tag:
            return x
    return None


def _extract_u11_pinout(sch_path: Path) -> dict[str, dict]:
    """Extract U11 (STM32G431CBU6) silicon pin -> {pin_num, labels, no_connect} from .kicad_sch."""
    sch = _parse_sexpr(sch_path.read_text(encoding="utf-8"))
    lib_syms = {}
    lib_sec = _find_one(sch, "lib_symbols")
    for ls in lib_sec[1:]:
        if isinstance(ls, list) and ls and ls[0] == "symbol":
            lib_syms[ls[1]] = ls

    u11 = None
    for sym in _find_all(sch, "symbol"):
        for prop in _find_all(sym, "property"):
            if prop[1] == "Reference" and prop[2] == "U11":
                u11 = sym
                break
        if u11 is not None:
            break
    if u11 is None:
        raise AssertionError("U11 not found in MCU_STM32.kicad_sch")

    at = _find_one(u11, "at")
    ux, uy = float(at[1]), float(at[2])
    urot = float(at[3]) if len(at) > 3 else 0.0
    mirror = _find_one(u11, "mirror")
    mx = mirror is not None and "x" in mirror[1:]
    my = mirror is not None and "y" in mirror[1:]

    lib_id = _find_one(u11, "lib_id")[1]
    lib_node = lib_syms[lib_id]
    raw_pins: list[tuple[str, str, float, float]] = []

    def collect_pins(node: list) -> None:
        for item in node:
            if isinstance(item, list) and item:
                if item[0] == "pin":
                    pat = _find_one(item, "at")
                    px, py = float(pat[1]), float(pat[2])
                    pname = _find_one(item, "name")[1]
                    pnum = _find_one(item, "number")[1]
                    raw_pins.append((pnum, pname, px, py))
                elif item[0] == "symbol":
                    collect_pins(item)

    collect_pins(lib_node)

    def xform(px: float, py: float) -> tuple[float, float]:
        if mx:
            py = -py
        if my:
            px = -px
        rad = math.radians(urot)
        rx = px * math.cos(rad) - py * math.sin(rad)
        ry = px * math.sin(rad) + py * math.cos(rad)
        return (round(ux + rx, 3), round(uy - ry, 3))

    wires: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for w in _find_all(sch, "wire"):
        pts = _find_all(_find_one(w, "pts"), "xy")
        a = (round(float(pts[0][1]), 3), round(float(pts[0][2]), 3))
        b = (round(float(pts[1][1]), 3), round(float(pts[1][2]), 3))
        wires.append((a, b))

    labels: dict[tuple[float, float], list[str]] = {}
    for tag in ("label", "global_label", "hierarchical_label"):
        for lbl in _find_all(sch, tag):
            lat = _find_one(lbl, "at")
            pt = (round(float(lat[1]), 3), round(float(lat[2]), 3))
            labels.setdefault(pt, []).append(lbl[1])

    ncs: set[tuple[float, float]] = set()
    for nc in _find_all(sch, "no_connect"):
        nat = _find_one(nc, "at")
        ncs.add((round(float(nat[1]), 3), round(float(nat[2]), 3)))

    def on_seg(pt: tuple[float, float], a: tuple[float, float], b: tuple[float, float], eps: float = 0.01) -> bool:
        x, y = pt
        x1, y1 = a
        x2, y2 = b
        if min(x1, x2) - eps <= x <= max(x1, x2) + eps and min(y1, y2) - eps <= y <= max(y1, y2) + eps:
            cross = abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1))
            return cross <= eps * max(abs(x2 - x1), abs(y2 - y1), 1.0)
        return False

    all_pts = set(labels.keys()) | ncs
    pin_pts: dict[str, tuple[str, tuple[float, float]]] = {}
    for pnum, pname, px, py in raw_pins:
        pt = xform(px, py)
        pin_pts[pnum] = (pname, pt)
        all_pts.add(pt)
    for a, b in wires:
        all_pts.add(a)
        all_pts.add(b)

    adj: dict[tuple[float, float], set[tuple[float, float]]] = {pt: set() for pt in all_pts}
    for a, b in wires:
        pts_on_w = [pt for pt in all_pts if on_seg(pt, a, b)]
        pts_on_w.sort()
        for i in range(len(pts_on_w) - 1):
            u, v = pts_on_w[i], pts_on_w[i + 1]
            adj[u].add(v)
            adj[v].add(u)

    result: dict[str, dict] = {}
    for pnum, (pname, start) in pin_pts.items():
        visited = {start}
        queue = [start]
        found_labels: list[str] = []
        is_nc = False
        while queue:
            cur = queue.pop(0)
            if cur in labels:
                found_labels.extend(labels[cur])
            if cur in ncs:
                is_nc = True
            for nxt in adj.get(cur, ()):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        # Silicon names like PA0, PB6, PC13, etc.
        result.setdefault(
            pname,
            {"pin_nums": [], "labels": found_labels, "no_connect": is_nc},
        )
        result[pname]["pin_nums"].append(pnum)
    return result


def _strip_c_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text


class TestPumpFirmware(unittest.TestCase):
    def test_sbu_packet_framing_and_checksum(self):
        sof = 0xAA
        cmd = 0x01  # CMD_RUN_FWD
        param = 150  # 150 uL/min
        expected_cs = sof ^ cmd ^ (150 & 0xFF) ^ 0
        self.assertEqual(calculate_pump_checksum(sof, cmd, param), expected_cs)

    def test_pressure_transducer_conversion(self):
        # Cis sensor: ABPDANN015PG2A3 (0..15 psi, 14-bit Transfer Function A)
        self.assertAlmostEqual(raw_to_pressure_psi(1638, 0.0, 15.0), 0.0, places=3)
        self.assertAlmostEqual(raw_to_pressure_psi(8192, 0.0, 15.0), 7.5, places=3)
        self.assertAlmostEqual(raw_to_pressure_psi(14746, 0.0, 15.0), 15.0, places=3)
        # Clamping out-of-range counts
        self.assertAlmostEqual(raw_to_pressure_psi(0, 0.0, 15.0), 0.0, places=3)
        self.assertAlmostEqual(raw_to_pressure_psi(16383, 0.0, 15.0), 15.0, places=3)

        # Trans sensor: ABPDANN005PG3A3 (0..5 psi, 14-bit Transfer Function A)
        self.assertAlmostEqual(raw_to_pressure_psi(1638, 0.0, 5.0), 0.0, places=3)
        self.assertAlmostEqual(raw_to_pressure_psi(8192, 0.0, 5.0), 2.5, places=3)
        self.assertAlmostEqual(raw_to_pressure_psi(14746, 0.0, 5.0), 5.0, places=3)
        self.assertAlmostEqual(raw_to_pressure_psi(1000, 0.0, 5.0), 0.0, places=3)
        self.assertAlmostEqual(raw_to_pressure_psi(16000, 0.0, 5.0), 5.0, places=3)

        # Status bits [15:14] + 14-bit counts [13:0] decoding
        st_ok, p_cis = decode_abp1_frame((0b00 << 14) | 8192, 0.0, 15.0)
        self.assertEqual(st_ok, 0)
        self.assertAlmostEqual(p_cis, 7.5, places=3)

        st_stale, p_trans = decode_abp1_frame((0b10 << 14) | 8192, 0.0, 5.0)
        self.assertEqual(st_stale, 2)
        self.assertAlmostEqual(p_trans, 2.5, places=3)

        st_diag, _ = decode_abp1_frame((0b11 << 14) | 0, 0.0, 15.0)
        self.assertEqual(st_diag, 3)

    def test_telemetry_snapshot_and_pressure_packing(self):
        # 12-byte full TelemetrySnapshot (must fit within twi.h 32-byte I2C_TXRX_BUFFER_SIZE)
        snap = pack_telemetry_snapshot(
            status_flags=0x19,  # ESTOP | PD_READY | PUMP1_RUN
            cis_psi=8.42,
            trans_psi=2.75,
            pump1_rate_ul_min=120.5,
            pump2_rate_ul_min=45.0,
            fault_code=0x02,
        )
        self.assertEqual(len(snap), 12)
        self.assertLessEqual(len(snap), 32)
        magic, flags, cis_cp, trans_cp, r1_x10, r2_x10, fault, rx_cs = struct.unpack("<BBhhHHBB", snap)
        self.assertEqual(magic, 0xAA)
        self.assertEqual(flags, 0x19)
        self.assertAlmostEqual(cis_cp / 100.0, 8.42, places=2)
        self.assertAlmostEqual(trans_cp / 100.0, 2.75, places=2)
        self.assertAlmostEqual(r1_x10 / 10.0, 120.5, places=1)
        self.assertAlmostEqual(r2_x10 / 10.0, 45.0, places=1)
        self.assertEqual(fault, 0x02)

        calc_cs = 0
        for b in snap[:-1]:
            calc_cs ^= b
        self.assertEqual(rx_cs, calc_cs)

        # 6-byte pressure-only frame carrying BOTH cis_psi and trans_psi
        p_frame = pack_pressure_only_frame(cis_psi=9.15, trans_psi=3.40)
        self.assertEqual(len(p_frame), 6)
        p_magic, p_cis_cp, p_trans_cp, p_cs = struct.unpack("<BhhB", p_frame)
        self.assertEqual(p_magic, 0xAA)
        self.assertAlmostEqual(p_cis_cp / 100.0, 9.15, places=2)
        self.assertAlmostEqual(p_trans_cp / 100.0, 3.40, places=2)
        p_calc = 0
        for b in p_frame[:-1]:
            p_calc ^= b
        self.assertEqual(p_cs, p_calc)

    def test_flow_rate_duty_calculation(self):
        ul_per_rev = 45.0
        max_rpm = 180.0
        # 45 uL/min -> 1 RPM -> (1/180)*100 = 0.55% -> clamped to starting threshold 15.0%
        self.assertEqual(calculate_flow_duty(45.0, ul_per_rev, max_rpm), 15.0)

        # 90 uL/min -> 2 RPM -> clamped to 15.0%
        self.assertEqual(calculate_flow_duty(90.0, ul_per_rev, max_rpm), 15.0)

        # 4500 uL/min -> 100 RPM -> (100/180)*100 = 55.55%
        duty = calculate_flow_duty(4500.0, ul_per_rev, max_rpm)
        self.assertAlmostEqual(duty, 55.555, places=2)

    def test_overpressure_detection(self):
        MAX_CIS = 10.0
        MAX_TRANS = 4.0

        def check_overpressure(p_cis: float, p_trans: float) -> bool:
            return p_cis > MAX_CIS or p_trans > MAX_TRANS

        self.assertFalse(check_overpressure(2.5, 1.2))
        self.assertTrue(check_overpressure(10.5, 1.2))  # Cis trip
        self.assertTrue(check_overpressure(3.0, 4.5))   # Trans trip


class TestPumpPinoutConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sch_path = REPO_ROOT / "Pump" / "MCU_STM32.kicad_sch"
        cls.pinout_path = REPO_ROOT / "Pump_firmware" / "include" / "pinout.h"
        cls.config_path = REPO_ROOT / "Pump_firmware" / "include" / "config.h"
        cls.pio_path = REPO_ROOT / "Pump_firmware" / "platformio.ini"
        cls.mr1_config_path = REPO_ROOT / "MR1_firmware" / "include" / "config.h"

        cls.u11_pins = _extract_u11_pinout(cls.sch_path)

        pinout_clean = _strip_c_comments(cls.pinout_path.read_text(encoding="utf-8"))
        cls.direct_pin_pairs = re.findall(r"#define\s+(PIN_\w+)\s+(P[A-Z]\d+)\b", pinout_clean)
        cls.alias_pin_pairs = re.findall(r"#define\s+(PIN_\w+)\s+(PIN_\w+)\b", pinout_clean)
        cls.all_pin_macros = re.findall(r"#define\s+(PIN_\w+)\b", pinout_clean)
        cls.direct_pins = dict(cls.direct_pin_pairs)
        cls.alias_pins = dict(cls.alias_pin_pairs)

        config_clean = _strip_c_comments(cls.config_path.read_text(encoding="utf-8"))
        cls.config_ints = {
            k: int(v, 0)
            for k, v in re.findall(r"#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)\b", config_clean)
        }

        mr1_clean = _strip_c_comments(cls.mr1_config_path.read_text(encoding="utf-8"))
        cls.mr1_config_ints = {
            k: int(v, 0)
            for k, v in re.findall(r"#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)\b", mr1_clean)
        }

        cp = configparser.ConfigParser()
        cp.read(cls.pio_path, encoding="utf-8")
        cls.build_flags = cp.get("env:stm32g431cb", "build_flags").split()

    def test_all_20_assigned_mcu_pins_match_schematic(self):
        expected_fw_to_sch_net = {
            "PIN_PRESS_I2C_SCL": "PRESS_I2C_SCL",
            "PIN_PRESS_I2C_SDA": "PRESS_I2C_SDA",
            "PIN_PD_I2C_SCL": "PD_I2C_SCL",
            "PIN_PD_I2C_SDA": "PD_I2C_SDA",
            "PIN_SBU_I2C_SCL": "SBU_I2C_SCL",
            "PIN_SBU_I2C_SDA": "SBU_I2C_SDA",
            "PIN_PUMP1_STEP": "PUMP1_STEP",
            "PIN_PUMP1_DIR": "PUMP1_DIR",
            "PIN_PUMP2_STEP": "PUMP2_STEP",
            "PIN_PUMP2_DIR": "PUMP2_DIR",
            "PIN_PUMP_UART": "PUMP_UART",
            "PIN_ESTOP_TRIGGER": "ESTOP_TRIGGER_",
            "PIN_MR1_PWR_EN": "MR1_PWR_EN",
            "PIN_USB_SEL_PASS": "USB_SEL_PASS",
            "PIN_PD_ALERT": "PD_ALERT_",
            "PIN_PRESS_ALERT": "PRESS_ALERT_",
            "PIN_LED_FAULT": "LED_FAULT",
            "PIN_LED_PUMP1": "LED_PUMP1",
            "PIN_LED_PUMP2": "LED_PUMP2",
            "PIN_LED_PD_READY": "LED_PD_READY",
            "PIN_LED_MR1_5V": "LED_MR1_5V",
        }
        self.assertEqual(len(expected_fw_to_sch_net), 21)
        self.assertEqual(set(self.direct_pins.keys()), set(expected_fw_to_sch_net.keys()))

        for fw_macro, expected_net in expected_fw_to_sch_net.items():
            mcu_pin = self.direct_pins[fw_macro]
            self.assertIn(mcu_pin, self.u11_pins, f"{fw_macro}={mcu_pin} missing from U11")
            sch_info = self.u11_pins[mcu_pin]
            self.assertFalse(sch_info["no_connect"], f"{fw_macro}={mcu_pin} is no_connect in schematic")
            self.assertIn(
                expected_net,
                sch_info["labels"],
                f"{fw_macro}={mcu_pin} schematic labels {sch_info['labels']} != {expected_net}",
            )

        # Optional PWM and I2C1 aliases resolve consistently
        self.assertEqual(self.alias_pins.get("PIN_PUMP1_PWM"), "PIN_PUMP1_STEP")
        self.assertEqual(self.alias_pins.get("PIN_PUMP2_PWM"), "PIN_PUMP2_STEP")
        self.assertEqual(self.alias_pins.get("PIN_I2C1_SCL"), "PIN_PRESS_I2C_SCL")
        self.assertEqual(self.alias_pins.get("PIN_I2C1_SDA"), "PIN_PRESS_I2C_SDA")

    def test_no_duplicate_or_forbidden_pins(self):
        # Zero duplicate PIN_* macro names in pinout.h
        self.assertEqual(
            len(self.all_pin_macros),
            len(set(self.all_pin_macros)),
            f"Duplicate PIN_* macro names found in pinout.h: {self.all_pin_macros}",
        )
        self.assertEqual(len(self.direct_pin_pairs), len(self.direct_pins))
        self.assertEqual(len(self.alias_pin_pairs), len(self.alias_pins))

        # Zero duplicate direct pin assignments across the 20 MCU pins
        assigned_values = list(self.direct_pins.values())
        self.assertEqual(len(assigned_values), len(set(assigned_values)))

        # Forbidden / no_connect / BOOT0 pins must remain unassigned in pinout.h
        self.assertIn("BOOT0", self.u11_pins["PB8"]["labels"])
        self.assertNotIn("PB8", assigned_values, "BOOT0 pin PB8 assigned in pinout.h")
        nc_pins = [p for p, info in self.u11_pins.items() if info["no_connect"]]
        self.assertGreaterEqual(len(nc_pins), 3)
        for nc_pin in nc_pins:
            self.assertNotIn(
                nc_pin,
                assigned_values,
                f"no_connect pin {nc_pin} assigned in pinout.h",
            )

        self.assertNotIn("PIN_SBU_UART_TX", self.all_pin_macros)
        self.assertNotIn("PIN_SBU_UART_RX", self.all_pin_macros)

    def test_platformio_flags_and_isolated_i2c_buses(self):
        self.assertNotIn("-DENABLE_HWSERIAL2", self.build_flags)
        self.assertIn("-DHWSERIAL_NONE", self.build_flags)
        self.assertIn("-DPIO_FRAMEWORK_ARDUINO_ENABLE_CDC", self.build_flags)

        scl_flags = [f for f in self.build_flags if f.startswith("-DPIN_WIRE_SCL=")]
        sda_flags = [f for f in self.build_flags if f.startswith("-DPIN_WIRE_SDA=")]
        self.assertEqual(scl_flags, ["-DPIN_WIRE_SCL=PA15"])
        self.assertEqual(sda_flags, ["-DPIN_WIRE_SDA=PB9"])
        self.assertEqual(
            scl_flags[0],
            f"-DPIN_WIRE_SCL={self.direct_pins['PIN_PRESS_I2C_SCL']}",
        )
        self.assertEqual(
            sda_flags[0],
            f"-DPIN_WIRE_SDA={self.direct_pins['PIN_PRESS_I2C_SDA']}",
        )

        # 3 completely isolated I2C buses (6 distinct MCU pins)
        press_bus = (self.direct_pins["PIN_PRESS_I2C_SCL"], self.direct_pins["PIN_PRESS_I2C_SDA"])
        pd_bus = (self.direct_pins["PIN_PD_I2C_SCL"], self.direct_pins["PIN_PD_I2C_SDA"])
        sbu_bus = (self.direct_pins["PIN_SBU_I2C_SCL"], self.direct_pins["PIN_SBU_I2C_SDA"])
        all_i2c_pins = list(press_bus + pd_bus + sbu_bus)
        self.assertEqual(len(all_i2c_pins), 6)
        self.assertEqual(len(set(all_i2c_pins)), 6)

    def test_config_i2c_addresses_and_stusb4500_voltage_cap(self):
        self.assertEqual(self.config_ints.get("I2C_ADDR_ABP1_CIS"), 0x28)
        self.assertEqual(self.config_ints.get("I2C_ADDR_ABP1_TRANS"), 0x38)
        self.assertEqual(self.config_ints.get("I2C_ADDR_STUSB4500"), 0x28)
        self.assertEqual(self.config_ints.get("I2C_ADDR_SBU_SLAVE"), 0x38)
        self.assertEqual(
            self.config_ints.get("I2C_ADDR_SBU_SLAVE"),
            self.mr1_config_ints.get("I2C_TARGET_PUMP_ADDR"),
        )
        max_mv = self.config_ints.get("STUSB4500_MAX_VOLTAGE_MV")
        self.assertIsNotNone(max_mv)
        self.assertLessEqual(max_mv, 9000)

    def test_main_and_stusb4500_safety_contracts(self):
        main_src = _strip_c_comments(
            (REPO_ROOT / "Pump_firmware" / "src" / "main.cpp").read_text(encoding="utf-8")
        )
        pd_src = _strip_c_comments(
            (REPO_ROOT / "Pump_firmware" / "src" / "hal" / "stusb4500_pd.cpp").read_text(encoding="utf-8")
        )
        # UCPD dead-battery Rd on PB6 must be disabled before pinMode(PIN_LED_FAULT, ...)
        ucpd_pos = main_src.find("HAL_PWREx_DisableUCPDDeadBattery()")
        pb6_pos = main_src.find("pinMode(PIN_LED_FAULT")
        self.assertNotEqual(ucpd_pos, -1)
        self.assertNotEqual(pb6_pos, -1)
        self.assertLess(ucpd_pos, pb6_pos)

        # Bus constructor / pin assignment contracts
        self.assertRegex(main_src, r"Wire\.setSCL\s*\(\s*PIN_PRESS_I2C_SCL\s*\)")
        self.assertRegex(main_src, r"Wire\.setSDA\s*\(\s*PIN_PRESS_I2C_SDA\s*\)")
        self.assertRegex(main_src, r"SoftI2C\s+pdWire\s*\(\s*PIN_PD_I2C_SDA\s*,\s*PIN_PD_I2C_SCL\b")
        self.assertRegex(main_src, r"TwoWire\s+sbuWire\s*\(\s*PIN_SBU_I2C_SDA\s*,\s*PIN_SBU_I2C_SCL\s*\)")

        # Overvoltage interlock, renegotiation separation, and unconditional 250 ms polling
        self.assertIn("isOvervoltageContract()", main_src)
        self.assertIn("isPdosClamped()", main_src)
        self.assertIn("isRenegotiatedAfterClamp()", main_src)
        self.assertIn("if (pd_alert || pd_periodic)", main_src)
        self.assertIn("checkChipPdosClamped()", main_src)
        self.assertIn("g_pd_initialized", main_src)
        self.assertIn("g_pd_overvoltage_fault", main_src)
        self.assertIn("ram_clamped_ = enforceMax9VPdos(", pd_src)
        self.assertIn("renegotiated_after_clamp_", pd_src)
        self.assertIn("overvoltage_contract_ = true", pd_src)
        self.assertIn("15000.0f", pd_src)
        self.assertIn("20000.0f", pd_src)


_MOCK_ARDUINO_H = r"""#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <string.h>
#include <algorithm>
#include <vector>

#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define OUTPUT_OPEN_DRAIN 2

enum MockStmPin : uint8_t {
    PA0 = 0, PA1, PA2, PA3, PA4, PA5, PA6, PA7,
    PA8, PA9, PA10, PA11, PA12, PA13, PA14, PA15,
    PB0, PB1, PB2, PB3, PB4, PB5, PB6, PB7,
    PB8, PB9, PB10, PB11, PB12, PB13, PB14, PB15,
    PC13,
    MOCK_PIN_COUNT
};

template <typename T, typename A, typename B>
inline T constrain(T x, A a, B b) {
    T lo = static_cast<T>(a);
    T hi = static_cast<T>(b);
    return (x < lo) ? lo : ((x > hi) ? hi : x);
}

class Stream {
public:
    virtual ~Stream() = default;
    virtual int available() = 0;
    virtual int read() = 0;
    virtual size_t write(const uint8_t* buf, size_t len) = 0;
    virtual int availableForWrite() = 0;
};

class MockSerial : public Stream {
public:
    std::vector<uint8_t> tx_bytes;
    std::vector<uint8_t> rx_bytes;
    size_t rx_pos = 0;

    void begin(uint32_t) {}
    int available() override { return static_cast<int>(rx_bytes.size() - rx_pos); }
    int read() override {
        if (rx_pos >= rx_bytes.size()) return -1;
        return rx_bytes[rx_pos++];
    }
    size_t write(const uint8_t* buf, size_t len) override {
        tx_bytes.insert(tx_bytes.end(), buf, buf + len);
        return len;
    }
    int availableForWrite() override { return 256; }
    void reset() { tx_bytes.clear(); rx_bytes.clear(); rx_pos = 0; }
};

extern MockSerial Serial;

void pinMode(uint8_t pin, uint8_t mode);
void digitalWrite(uint8_t pin, uint8_t val);
int digitalRead(uint8_t pin);
void analogWrite(uint8_t pin, uint32_t val);
void analogWriteResolution(uint32_t bits);
void analogWriteFrequency(uint32_t hz);
void delay(uint32_t ms);
void delayMicroseconds(uint32_t us);
uint32_t millis();
uint32_t micros();
"""

_MOCK_STM32_HAL_H = r"""#pragma once
#include <stdint.h>

#define __HAL_RCC_PWR_CLK_ENABLE() do {} while (0)
inline void HAL_PWREx_DisableUCPDDeadBattery() {}

typedef enum {
    HAL_OK = 0,
    HAL_ERROR = 1
} HAL_StatusTypeDef;

typedef enum {
    HAL_I2C_STATE_RESET = 0,
    HAL_I2C_STATE_READY = 1,
    HAL_I2C_STATE_LISTEN = 2
} HAL_I2C_StateTypeDef;

#define HAL_I2C_ERROR_NONE 0U
#define I2C_FLAG_BERR 0x01U
#define I2C_FLAG_ARLO 0x02U
#define I2C_FLAG_OVR  0x04U
#define I2C_FLAG_AF   0x08U

struct I2C_HandleTypeDef {
    uint32_t ErrorCode = HAL_I2C_ERROR_NONE;
    HAL_I2C_StateTypeDef State = HAL_I2C_STATE_LISTEN;
};

inline uint32_t HAL_I2C_GetError(I2C_HandleTypeDef* h) { return h ? h->ErrorCode : 0U; }
inline HAL_I2C_StateTypeDef HAL_I2C_GetState(I2C_HandleTypeDef* h) { return h ? h->State : HAL_I2C_STATE_RESET; }
#define __HAL_I2C_CLEAR_FLAG(h, f) do { (void)(h); (void)(f); } while (0)
inline HAL_StatusTypeDef HAL_I2C_EnableListen_IT(I2C_HandleTypeDef* h) {
    if (h) h->State = HAL_I2C_STATE_LISTEN;
    return HAL_OK;
}
inline void __disable_irq() {}
inline void __enable_irq() {}
"""

_MOCK_WIRE_H = r"""#pragma once
#include <stdint.h>
#include <stddef.h>
#include <vector>
#include "stm32g4xx_hal.h"

class TwoWire {
public:
    TwoWire() = default;
    TwoWire(uint8_t sda, uint8_t scl) : sda_(sda), scl_(scl) {}

    void setSCL(uint8_t scl) { scl_ = scl; }
    void setSDA(uint8_t sda) { sda_ = sda; }
    void begin() { is_slave_ = false; }
    void begin(uint8_t addr, bool = false, bool = false) {
        slave_addr_ = addr;
        is_slave_ = true;
        handle_.State = HAL_I2C_STATE_LISTEN;
    }
    void setClock(uint32_t) {}

    void beginTransmission(uint8_t addr) { tx_addr_ = addr; }
    uint8_t endTransmission();
    uint8_t requestFrom(uint8_t addr, uint8_t qty);
    int available() { return static_cast<int>(rx_buf_.size() - rx_pos_); }
    int read() {
        if (rx_pos_ >= rx_buf_.size()) return -1;
        return rx_buf_[rx_pos_++];
    }
    size_t write(const uint8_t* data, size_t len) {
        slave_tx_buf_.insert(slave_tx_buf_.end(), data, data + len);
        return len;
    }

    void onReceive(void (*cb)(int)) { on_receive_ = cb; }
    void onRequest(void (*cb)()) { on_request_ = cb; }
    I2C_HandleTypeDef* getHandle() { return is_slave_ ? &handle_ : nullptr; }

    // Test-harness helpers for simulating master -> slave I2C transactions
    void simMasterWrite(const std::vector<uint8_t>& bytes) {
        rx_buf_ = bytes;
        rx_pos_ = 0;
        if (on_receive_) on_receive_(static_cast<int>(bytes.size()));
    }
    std::vector<uint8_t> simMasterRead() {
        slave_tx_buf_.clear();
        if (on_request_) on_request_();
        return slave_tx_buf_;
    }

    uint8_t sda_ = 0;
    uint8_t scl_ = 0;
    uint8_t slave_addr_ = 0;
    bool is_slave_ = false;
    I2C_HandleTypeDef handle_;

private:
    uint8_t tx_addr_ = 0;
    std::vector<uint8_t> rx_buf_;
    size_t rx_pos_ = 0;
    std::vector<uint8_t> slave_tx_buf_;
    void (*on_receive_)(int) = nullptr;
    void (*on_request_)() = nullptr;
};

extern TwoWire Wire;
"""

_MOCK_HAL_AND_HARNESS_CPP = r"""#include <Arduino.h>
#include <Wire.h>
#include "pinout.h"
#include "config.h"
#include "hal/soft_i2c.h"
#include "hal/stusb4500_pd.h"
#include "hal/drv8837c_motor.h"
#include "comm/sbu_link.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>

MockSerial Serial;
TwoWire Wire;

// -----------------------------------------------------------------------------
// Bit-level STUSB4500QTR Open-Drain I2C Slave Simulator on PB10 (SCL) / PB11 (SDA)
// -----------------------------------------------------------------------------
struct Stusb4500Sim {
    enum State { ST_IDLE, ST_ADDR, ST_REG, ST_WRITE_DATA, ST_READ_DATA };

    bool powered = true;
    bool nack_soft_reset = false;
    bool nack_pdo_clamp = false;
    bool nack_rdo_read = false;
    bool nack_pdo_numb_read = false;
    int soft_reset_target_rdo3 = -1; // >= 0 updates RDO3 when SOFT_RESET command executes
    int soft_reset_count = 0;

    uint8_t regs[256] = {};

    // Open-drain bus lines
    bool master_scl = true;
    bool master_sda = true;
    bool prev_scl = true;
    bool prev_sda = true;
    bool slave_sda = true;

    State state = ST_IDLE;
    uint8_t bit_idx = 0;
    uint8_t shift_in = 0;
    uint8_t shift_out = 0;
    uint8_t cur_reg = 0;
    bool is_read = false;
    bool cur_ack_ok = false;
    bool wait_first_scl_fall = false;

    void resetFactoryNvm(bool attached, uint8_t rdo3_val) {
        memset(regs, 0, sizeof(regs));
        regs[0x2F] = 0x25; // DEVICE_ID
        regs[0x0E] = attached ? 0x01 : 0x00; // PORT_STATUS_1
        regs[0x70] = 0x03; // DPM_PDO_NUMB = 3 (factory NVM)
        // Factory NVM PDO2 = 15V (0x0004B096 LE)
        regs[0x89] = 0x96; regs[0x8A] = 0xB0; regs[0x8B] = 0x04; regs[0x8C] = 0x00;
        // Factory NVM PDO3 = 20V (0x00064096 LE)
        regs[0x8D] = 0x96; regs[0x8E] = 0x40; regs[0x8F] = 0x06; regs[0x90] = 0x00;
        regs[0x94] = rdo3_val;
    }

    void resetBusState() {
        master_scl = true;
        master_sda = true;
        prev_scl = true;
        prev_sda = true;
        slave_sda = true;
        state = ST_IDLE;
        bit_idx = 0;
        wait_first_scl_fall = false;
    }

    bool shouldAckRegWrite(uint8_t reg) const {
        if (nack_soft_reset && (reg == 0x51 || reg == 0x1A)) return false;
        if (nack_pdo_clamp && (reg == 0x70 || (reg >= 0x89 && reg <= 0x90))) return false;
        return true;
    }

    bool shouldAckRegRead(uint8_t reg) const {
        if (nack_rdo_read && reg == 0x94) return false;
        if (nack_pdo_numb_read && reg == 0x70) return false;
        return true;
    }

    void onRegWrite(uint8_t reg, uint8_t val) {
        regs[reg] = val;
        if (reg == 0x1A && val == 0x26 && regs[0x51] == 0x0D) {
            ++soft_reset_count;
            if (soft_reset_target_rdo3 >= 0) {
                regs[0x94] = static_cast<uint8_t>(soft_reset_target_rdo3);
            }
        }
    }

    void onBusChange() {
        bool scl = master_scl;
        bool sda = master_sda && slave_sda;

        // START or Repeated START: SDA falls while SCL is high
        if (prev_scl && scl && prev_sda && !sda) {
            state = ST_ADDR;
            bit_idx = 0;
            shift_in = 0;
            slave_sda = true;
            wait_first_scl_fall = true;
            prev_scl = scl;
            prev_sda = sda;
            return;
        }
        // STOP: SDA rises while SCL is high
        if (prev_scl && scl && !prev_sda && sda) {
            state = ST_IDLE;
            bit_idx = 0;
            slave_sda = true;
            wait_first_scl_fall = false;
            prev_scl = scl;
            prev_sda = sda;
            return;
        }

        // Rising edge of SCL: sample master bit (bits 0..7) or master ACK (bit 8 in read mode)
        if (!prev_scl && scl) {
            wait_first_scl_fall = false;
            if (state == ST_ADDR || state == ST_REG || state == ST_WRITE_DATA) {
                if (bit_idx < 8) {
                    shift_in = static_cast<uint8_t>((shift_in << 1) | (master_sda ? 1 : 0));
                }
            } else if (state == ST_READ_DATA) {
                if (bit_idx == 8) {
                    // Master ACK (0) -> advance to next register; Master NACK (1) -> stop
                    if (!master_sda) {
                        ++cur_reg;
                        shift_out = regs[cur_reg];
                    } else {
                        state = ST_IDLE;
                    }
                }
            }
        }

        // Falling edge of SCL: advance bit counter, drive ACK or read bit
        if (prev_scl && !scl) {
            if (wait_first_scl_fall) {
                wait_first_scl_fall = false;
            } else if (state == ST_ADDR || state == ST_REG || state == ST_WRITE_DATA) {
                if (bit_idx < 7) {
                    ++bit_idx;
                } else if (bit_idx == 7) {
                    // 8th clock fell -> drive ACK/NACK for 9th clock
                    bit_idx = 8;
                    cur_ack_ok = false;
                    if (state == ST_ADDR) {
                        uint8_t addr7 = shift_in >> 1;
                        is_read = (shift_in & 0x01) != 0;
                        if (powered && addr7 == I2C_ADDR_STUSB4500) {
                            if (!is_read || shouldAckRegRead(cur_reg)) {
                                cur_ack_ok = true;
                            }
                        }
                    } else if (state == ST_REG) {
                        cur_reg = shift_in;
                        cur_ack_ok = powered;
                    } else if (state == ST_WRITE_DATA) {
                        if (powered && shouldAckRegWrite(cur_reg)) {
                            onRegWrite(cur_reg, shift_in);
                            ++cur_reg;
                            cur_ack_ok = true;
                        }
                    }
                    slave_sda = !cur_ack_ok;
                } else {
                    // 9th clock fell -> release ACK and transition state
                    slave_sda = true;
                    bit_idx = 0;
                    if (!cur_ack_ok) {
                        state = ST_IDLE;
                    } else if (state == ST_ADDR) {
                        if (is_read) {
                            state = ST_READ_DATA;
                            shift_out = regs[cur_reg];
                            slave_sda = ((shift_out & 0x80) == 0) ? false : true;
                        } else {
                            state = ST_REG;
                        }
                    } else if (state == ST_REG) {
                        state = ST_WRITE_DATA;
                    }
                    shift_in = 0;
                }
            } else if (state == ST_READ_DATA) {
                if (bit_idx < 7) {
                    ++bit_idx;
                    shift_out <<= 1;
                    slave_sda = ((shift_out & 0x80) == 0) ? false : true;
                } else if (bit_idx == 7) {
                    // 8th bit fell -> release SDA for master ACK/NACK on 9th clock
                    bit_idx = 8;
                    slave_sda = true;
                } else {
                    // 9th clock fell -> start next byte if still in ST_READ_DATA
                    bit_idx = 0;
                    slave_sda = ((shift_out & 0x80) == 0) ? false : true;
                }
            }
        }

        prev_scl = scl;
        prev_sda = sda;
    }
};

static Stusb4500Sim g_pd_sim;
static uint8_t g_pin_modes[MOCK_PIN_COUNT] = {};
static uint8_t g_pin_levels[MOCK_PIN_COUNT] = {};
static uint32_t g_analog_vals[MOCK_PIN_COUNT] = {};
static uint64_t g_micros = 1000000ULL;
static uint16_t g_cis_raw_abp1 = 0x2000;   // Mid-scale (~7.5 psi)
static uint16_t g_trans_raw_abp1 = 0x2000; // Mid-scale (~2.5 psi)
static bool g_pressure_present = true;

void pinMode(uint8_t pin, uint8_t mode) {
    if (pin < MOCK_PIN_COUNT) {
        g_pin_modes[pin] = mode;
        if (pin == PIN_PD_ALERT) {
            g_pin_levels[pin] = HIGH;
        }
    }
}

void digitalWrite(uint8_t pin, uint8_t val) {
    if (pin >= MOCK_PIN_COUNT) return;
    g_pin_levels[pin] = val ? HIGH : LOW;
    if (pin == PIN_PD_I2C_SCL) {
        g_pd_sim.master_scl = (val != LOW);
        g_pd_sim.onBusChange();
    } else if (pin == PIN_PD_I2C_SDA) {
        g_pd_sim.master_sda = (val != LOW);
        g_pd_sim.onBusChange();
    }
}

int digitalRead(uint8_t pin) {
    if (pin >= MOCK_PIN_COUNT) return LOW;
    if (pin == PIN_PD_I2C_SCL) return g_pd_sim.master_scl ? HIGH : LOW;
    if (pin == PIN_PD_I2C_SDA) return (g_pd_sim.master_sda && g_pd_sim.slave_sda) ? HIGH : LOW;
    return g_pin_levels[pin];
}

void analogWrite(uint8_t pin, uint32_t val) {
    if (pin < MOCK_PIN_COUNT) g_analog_vals[pin] = val;
}
void analogWriteResolution(uint32_t) {}
void analogWriteFrequency(uint32_t) {}

void delay(uint32_t ms) {
    g_micros += static_cast<uint64_t>(ms) * 1000ULL;
}
void delayMicroseconds(uint32_t us) {
    g_micros += us;
}
uint32_t millis() { return static_cast<uint32_t>(g_micros / 1000ULL); }
uint32_t micros() { return static_cast<uint32_t>(g_micros); }

uint8_t TwoWire::endTransmission() {
    if (!g_pressure_present) return 2;
    if (tx_addr_ == I2C_ADDR_ABP1_CIS || tx_addr_ == I2C_ADDR_ABP1_TRANS) return 0;
    return 2;
}

uint8_t TwoWire::requestFrom(uint8_t addr, uint8_t qty) {
    rx_buf_.clear();
    rx_pos_ = 0;
    if (!g_pressure_present || qty != 2) return 0;
    uint16_t raw = (addr == I2C_ADDR_ABP1_CIS) ? g_cis_raw_abp1 : g_trans_raw_abp1;
    rx_buf_.push_back(static_cast<uint8_t>((raw >> 8) & 0xFF));
    rx_buf_.push_back(static_cast<uint8_t>(raw & 0xFF));
    return 2;
}

// Symbols from main.cpp (compiled with -Dsetup=pump_setup -Dloop=pump_loop)
extern bool g_estop_tripped;
extern bool g_overpressure_fault;
extern bool g_sensor_fault;
extern bool g_pd_overvoltage_fault;
extern bool g_pd_initialized;
extern uint8_t g_sensor_comm_errors;
extern STUSB4500PD pdController;
extern DRV8837CMotor pumpCis;
extern DRV8837CMotor pumpTrans;
extern SbuLink sbuLink;
extern TwoWire sbuWire;
extern uint32_t g_last_pressure_ms;
extern uint32_t g_last_telemetry_ms;
extern uint32_t g_last_heartbeat_ms;
extern uint32_t g_last_pd_check_ms;
extern uint32_t g_last_loop_ms;
void handleSbuCommand(uint8_t cmd, uint16_t param);
void pump_setup();
void pump_loop();

static void resetGlobals() {
    memset(g_pin_modes, 0, sizeof(g_pin_modes));
    memset(g_pin_levels, 0, sizeof(g_pin_levels));
    memset(g_analog_vals, 0, sizeof(g_analog_vals));
    g_pin_levels[PIN_PD_ALERT] = HIGH;
    g_pin_levels[PIN_PD_I2C_SCL] = HIGH;
    g_pin_levels[PIN_PD_I2C_SDA] = HIGH;
    g_micros = 1000000ULL;
    g_cis_raw_abp1 = 0x2000;
    g_trans_raw_abp1 = 0x2000;
    g_pressure_present = true;
    g_estop_tripped = false;
    g_overpressure_fault = false;
    g_sensor_fault = false;
    g_pd_overvoltage_fault = false;
    g_pd_initialized = false;
    g_sensor_comm_errors = 0;
    g_last_pressure_ms = 0;
    g_last_telemetry_ms = 0;
    g_last_heartbeat_ms = 0;
    g_last_pd_check_ms = 0;
    g_last_loop_ms = 0;
    Serial.reset();
    g_pd_sim = Stusb4500Sim{};
}

static void assertTrue(bool cond, const char* msg) {
    if (!cond) {
        std::fprintf(stderr, "ASSERTION FAILED: %s\n", msg);
        std::exit(1);
    }
}

static int runDriverSoftResetFail() {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x20); // Active 15V factory PDO2
    g_pd_sim.nack_soft_reset = true;

    SoftI2C i2c(PIN_PD_I2C_SDA, PIN_PD_I2C_SCL, 100000);
    i2c.begin();
    STUSB4500PD pd(i2c, I2C_ADDR_STUSB4500);

    assertTrue(pd.begin(), "begin() should succeed when attached");
    assertTrue(pd.isRamClamped(), "begin() should clamp RAM PDOs");
    assertTrue(!pd.isRenegotiatedAfterClamp(), "begin() must not set renegotiated");
    assertTrue(pd.isOvervoltageContract(), "15V PDO2 before SOFT_RESET must flag OV");
    assertTrue(pd.getVbusVoltageMv() == 15000.0f, "15V PDO2 must report 15000 mV");

    bool ok = pd.requestProfile(STUSB4500PD::PDO_9V);
    assertTrue(!ok, "requestProfile must fail when SOFT_RESET NACKs");
    assertTrue(pd.getLastRequestResult() == STUSB4500PD::REQ_SOFT_RESET_FAILED, "result=REQ_SOFT_RESET_FAILED");
    assertTrue(!pd.isRenegotiatedAfterClamp(), "renegotiated must stay false");
    assertTrue(pd.getActiveContract() != STUSB4500PD::PDO_9V, "must NOT spoof PDO_9V");
    assertTrue(pd.isOvervoltageContract(), "must remain overvoltage");
    assertTrue(pd.getVbusVoltageMv() == 15000.0f, "must report 15000.0f, never 9000.0f");

    // Check checkChipPdosClamped() I2C error clears ram_clamped_ and returns false
    g_pd_sim.nack_pdo_numb_read = true;
    assertTrue(!pd.checkChipPdosClamped(), "checkChipPdosClamped I2C error must return false");
    assertTrue(!pd.isRamClamped(), "ram_clamped_ must clear on I2C error");
    g_pd_sim.nack_pdo_numb_read = false;

    // Check RDO read error sets rdo_read_ok_ == false
    g_pd_sim.nack_rdo_read = true;
    pd.getActiveContract();
    assertTrue(!pd.isRdoReadOk(), "rdo_read_ok_ must be false on RDO read NACK");
    return 0;
}

static int runCase1NonPd5vBoot() {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x00); // Non-PD 5V host (Object_Pos = 0)
    g_pd_sim.soft_reset_target_rdo3 = 0x00;

    pump_setup();
    assertTrue(g_pd_initialized, "g_pd_initialized must be true");
    assertTrue(pdController.isPdosClamped(), "PDOs must be clamped");
    assertTrue(pdController.isRenegotiatedAfterClamp(), "SOFT_RESET succeeded");
    assertTrue(pdController.isRdoReadOk(), "RDO read succeeded");
    assertTrue(!g_pd_overvoltage_fault, "Non-PD 5V boot must NOT trip OV fault");
    assertTrue(!g_estop_tripped, "Non-PD 5V boot must NOT trip ESTOP");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED LOW without PD contract");

    handleSbuCommand(SbuLink::CMD_RUN_FWD, 100);
    assertTrue(pumpCis.isRunning(), "pumpCis must run on safe 5V non-PD host");

    int resets_after_setup = g_pd_sim.soft_reset_count;
    for (int i = 0; i < 4; ++i) {
        delay(300);
        pump_loop();
    }
    assertTrue(!g_pd_overvoltage_fault, "steady 5V non-PD must not fault in loop");
    assertTrue(pumpCis.isRunning(), "pumpCis must keep running");
    assertTrue(g_pd_sim.soft_reset_count == resets_after_setup, "must NOT spam SOFT_RESET every 250ms");
    return 0;
}

static int runCase1SlowPd() {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x00); // Slow PD still at 0x00 at t=100ms
    g_pd_sim.soft_reset_target_rdo3 = 0x00;

    pump_setup();
    assertTrue(!g_pd_overvoltage_fault, "slow PD must not fault in setup");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LOW while negotiating");

    // Source completes PS_RDY at 250ms -> RDO3 becomes 0x20 (9V)
    g_pd_sim.regs[0x94] = 0x20;
    delay(260);
    pump_loop();

    assertTrue(!g_pd_overvoltage_fault, "slow PD 9V transition must not fault");
    assertTrue(pdController.isContractActive(), "contract must become active");
    assertTrue(pdController.getVbusVoltageMv() == 9000.0f, "must negotiate 9000 mV");
    assertTrue(digitalRead(PIN_LED_PD_READY) == HIGH, "PD_READY LED must light on 9V");
    return 0;
}

static int runCase2Setup() {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x20); // Active 15V factory PDO2
    g_pd_sim.nack_soft_reset = true;

    pump_setup();
    assertTrue(g_pd_overvoltage_fault, "15V SOFT_RESET fail in setup must latch OV fault");
    assertTrue(g_estop_tripped, "must trigger ESTOP");
    assertTrue(pumpCis.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpCis must be MODE_ESTOP");
    assertTrue(pumpTrans.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpTrans must be MODE_ESTOP");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED must be LOW");
    return 0;
}

static int runCase2LoopHotplug() {
    resetGlobals();
    g_pd_sim.powered = false; // SWD-only bench boot (J7 unplugged)
    pump_setup();
    assertTrue(!g_pd_initialized, "unplugged boot leaves g_pd_initialized false");
    assertTrue(!g_pd_overvoltage_fault, "unplugged boot must not fault");

    // Hot-plug J7 with 15V active factory PDO2 and NACKing SOFT_RESET
    g_pd_sim.powered = true;
    g_pd_sim.resetFactoryNvm(true, 0x20);
    g_pd_sim.nack_soft_reset = true;
    delay(300);
    pump_loop();

    assertTrue(g_pd_overvoltage_fault, "hotplug 15V SOFT_RESET fail must latch OV fault");
    assertTrue(g_estop_tripped, "must trigger ESTOP");
    assertTrue(pumpCis.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpCis MODE_ESTOP");
    assertTrue(pumpTrans.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpTrans MODE_ESTOP");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED LOW");
    return 0;
}

static int runScenarioC5SilentBrownout() {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x20);
    g_pd_sim.soft_reset_target_rdo3 = 0x20; // Normal 9V boot
    pump_setup();
    assertTrue(!g_pd_overvoltage_fault, "9V boot must succeed");
    assertTrue(digitalRead(PIN_LED_PD_READY) == HIGH, "PD_READY LED HIGH at 9V");

    handleSbuCommand(SbuLink::CMD_RUN_FWD, 100);
    assertTrue(pumpCis.isRunning(), "pumpCis must run before brownout");

    // Silent POR / NVM brownout reset: 0x70=3, 0x94=0x30 (20V), PIN_PD_ALERT stays HIGH
    g_pd_sim.resetFactoryNvm(true, 0x30);
    g_pd_sim.soft_reset_target_rdo3 = 0x30;
    g_pin_levels[PIN_PD_ALERT] = HIGH;

    for (int i = 0; i < 4; ++i) {
        delay(300);
        pump_loop();
    }

    assertTrue(g_pd_overvoltage_fault, "silent brownout 20V must latch OV fault within 250ms");
    assertTrue(g_estop_tripped, "silent brownout must trigger ESTOP");
    assertTrue(!pumpCis.isRunning(), "pumpCis must halt");
    assertTrue(pumpCis.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpCis must be MODE_ESTOP");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED must be LOW");
    return 0;
}

static int runScenarioC5SilentBrownout15v(bool pdo_numb_two) {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x20);
    g_pd_sim.soft_reset_target_rdo3 = 0x20; // Normal 9V boot
    pump_setup();
    assertTrue(!g_pd_overvoltage_fault, "9V boot must succeed");
    assertTrue(!g_estop_tripped, "9V boot must not trip ESTOP");
    assertTrue(digitalRead(PIN_LED_PD_READY) == HIGH, "PD_READY LED HIGH at 9V");

    handleSbuCommand(SbuLink::CMD_RUN_FWD, 100);
    assertTrue(pumpCis.isRunning(), "pumpCis must run before 15V brownout");

    // Silent brownout / RAM PDO2 corruption back to 15V (0x0004B096 LE) with Object_Pos=2 (0x20)
    // and PIN_PD_ALERT remaining HIGH (caught only by 250ms periodic checkChipPdosClamped()).
    g_pd_sim.regs[0x70] = pdo_numb_two ? 0x02 : 0x03;
    g_pd_sim.regs[0x89] = 0x96;
    g_pd_sim.regs[0x8A] = 0xB0;
    g_pd_sim.regs[0x8B] = 0x04;
    g_pd_sim.regs[0x8C] = 0x00;
    if (pdo_numb_two) {
        // Subcase B: PDO_NUMB==2 and PDO3==0 so ONLY PDO2 (15V) differs from clamped 9V config
        g_pd_sim.regs[0x8D] = 0x00;
        g_pd_sim.regs[0x8E] = 0x00;
        g_pd_sim.regs[0x8F] = 0x00;
        g_pd_sim.regs[0x90] = 0x00;
    } else {
        // Subcase A: full factory NVM reset (PDO_NUMB=3, PDO2=15V, PDO3=20V)
        g_pd_sim.regs[0x8D] = 0x96;
        g_pd_sim.regs[0x8E] = 0x40;
        g_pd_sim.regs[0x8F] = 0x06;
        g_pd_sim.regs[0x90] = 0x00;
    }
    g_pd_sim.regs[0x94] = 0x20;
    g_pd_sim.soft_reset_target_rdo3 = 0x20;
    g_pin_levels[PIN_PD_ALERT] = HIGH;

    for (int i = 0; i < 4; ++i) {
        delay(300);
        pump_loop();
        assertTrue(g_pd_overvoltage_fault, "15V silent brownout must latch OV fault within 250ms");
        assertTrue(g_estop_tripped, "15V silent brownout must trigger ESTOP");
        assertTrue(!pumpCis.isRunning(), "pumpCis must halt on 15V brownout");
        assertTrue(pumpCis.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpCis must be MODE_ESTOP");
        assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED must be LOW");
    }
    return 0;
}

static int runRdoReadNackSetup() {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x20); // Attached STUSB4500, clamp & SOFT_RESET succeed
    g_pd_sim.soft_reset_target_rdo3 = 0x20;
    g_pd_sim.nack_rdo_read = true; // 0x94 RDO read NACKs

    pump_setup();
    assertTrue(g_pd_initialized, "g_pd_initialized must be true when attached");
    assertTrue(pdController.isPdosClamped(), "PDO clamp succeeded before RDO NACK");
    assertTrue(pdController.isRenegotiatedAfterClamp(), "SOFT_RESET succeeded before RDO NACK");
    assertTrue(!pdController.isRdoReadOk(), "isRdoReadOk() must be false on 0x94 NACK");
    assertTrue(g_pd_overvoltage_fault, "RDO read NACK in setup must latch OV fault");
    assertTrue(g_estop_tripped, "RDO read NACK in setup must trigger ESTOP");
    assertTrue(pumpCis.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpCis must be MODE_ESTOP");
    assertTrue(pumpTrans.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpTrans must be MODE_ESTOP");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED must be LOW");
    return 0;
}

static int runRdoReadNackLoop() {
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x20);
    g_pd_sim.soft_reset_target_rdo3 = 0x20; // Normal 9V boot
    pump_setup();
    assertTrue(!g_pd_overvoltage_fault, "9V boot must succeed");
    assertTrue(pdController.isRdoReadOk(), "RDO read ok on 9V boot");

    handleSbuCommand(SbuLink::CMD_RUN_FWD, 100);
    assertTrue(pumpCis.isRunning(), "pumpCis must run before RDO NACK");

    g_pd_sim.nack_rdo_read = true;
    g_pin_levels[PIN_PD_ALERT] = HIGH;
    delay(300); // >= 250ms periodic check
    pump_loop();

    assertTrue(!pdController.isRdoReadOk(), "isRdoReadOk() must be false after 0x94 NACK");
    assertTrue(g_pd_overvoltage_fault, "RDO read NACK in loop must latch OV fault");
    assertTrue(g_estop_tripped, "RDO read NACK in loop must trigger ESTOP");
    assertTrue(!pumpCis.isRunning(), "pumpCis must halt on RDO read NACK");
    assertTrue(pumpCis.getMode() == DRV8837CMotor::MODE_ESTOP, "pumpCis must be MODE_ESTOP");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED must be LOW");
    return 0;
}

static int runStuck20vAndUnclamped5vAndSafety() {
    // 1. Stuck 20V boot
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x30);
    g_pd_sim.soft_reset_target_rdo3 = 0x30;
    pump_setup();
    assertTrue(g_pd_overvoltage_fault, "stuck 20V boot must fault");
    assertTrue(pumpCis.getMode() == DRV8837CMotor::MODE_ESTOP, "stuck 20V MODE_ESTOP");
    handleSbuCommand(SbuLink::CMD_RUN_FWD, 100);
    assertTrue(!pumpCis.isRunning(), "CMD_RUN_FWD must be blocked on OV fault");

    // 2. Unclamped 5V (PDO write NACK)
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x10);
    g_pd_sim.nack_pdo_clamp = true;
    pump_setup();
    assertTrue(g_pd_overvoltage_fault, "unclamped 5V must fault");
    assertTrue(digitalRead(PIN_LED_PD_READY) == LOW, "PD_READY LED LOW when unclamped");
    std::vector<uint8_t> snap = sbuWire.simMasterRead();
    assertTrue(snap.size() == sizeof(SbuLink::TelemetrySnapshot), "12-byte telemetry snapshot");
    assertTrue((snap[1] & SbuLink::FLAG_PD_READY) == 0, "FLAG_PD_READY must be 0 on OV fault");

    // 3. DRV8837CMotor NaN/Inf/Clamp invariants
    DRV8837CMotor m(PIN_PUMP1_PWM, PIN_PUMP1_DIR, UL_PER_REVOLUTION);
    m.begin();
    m.setFlowRate(NAN, DRV8837CMotor::DIR_FORWARD);
    assertTrue(!m.isRunning() && m.getTargetRate() == 0.0f, "NaN flow stops motor");
    m.setFlowRate(-INFINITY, DRV8837CMotor::DIR_FORWARD);
    assertTrue(!m.isRunning() && m.getTargetRate() == 0.0f, "-Inf flow stops motor");
    m.setFlowRate(INFINITY, DRV8837CMotor::DIR_FORWARD);
    assertTrue(m.isRunning() && m.getTargetRate() == 8100.0f, "+Inf clamps to 8100 uL/min");
    m.setFlowRate(20000.0f, DRV8837CMotor::DIR_FORWARD);
    assertTrue(m.getTargetRate() == 8100.0f, "20000 clamps to 8100 uL/min");
    m.setPwmDuty(NAN);
    assertTrue(g_analog_vals[PIN_PUMP1_PWM] == 0, "NaN duty clamps to 0");

    // 4. SbuLink telemetry, tx_reg_ reset, and overpressure CMD_ESTOP deduplication
    resetGlobals();
    g_pd_sim.resetFactoryNvm(true, 0x20);
    g_pd_sim.soft_reset_target_rdo3 = 0x20;
    pump_setup();
    Serial.reset();
    sbuLink.sendPressureTelemetry(2.46f, 9.15f);
    assertTrue(Serial.tx_bytes.size() == 10, "2x 5-byte packets on aux_serial");
    assertTrue(Serial.tx_bytes[1] == SbuLink::CMD_REPORT_PRESS, "Cis packet cmd");
    int16_t cis_cp = static_cast<int16_t>(Serial.tx_bytes[2] | (Serial.tx_bytes[3] << 8));
    assertTrue(cis_cp == 246, "Cis centi-psi == 246");
    assertTrue(Serial.tx_bytes[6] == SbuLink::CMD_REPORT_PRESS_TRANS, "Trans packet cmd");
    int16_t trans_cp = static_cast<int16_t>(Serial.tx_bytes[7] | (Serial.tx_bytes[8] << 8));
    assertTrue(trans_cp == 915, "Trans centi-psi == 915");

    // Verify tx_reg_ selects 6-byte pressure frame then resets to 12-byte snapshot
    sbuWire.simMasterWrite({SbuLink::CMD_REPORT_PRESS});
    std::vector<uint8_t> pframe = sbuWire.simMasterRead();
    assertTrue(pframe.size() == 6 && pframe[0] == 0xAA, "6-byte pressure frame");
    std::vector<uint8_t> full_snap = sbuWire.simMasterRead();
    assertTrue(full_snap.size() == 12 && full_snap[0] == 0xAA, "tx_reg_ resets to 12-byte snapshot");
    // 5-byte CMD_PING also resets tx_reg_
    sbuWire.simMasterWrite({SbuLink::CMD_REPORT_PRESS});
    sbuWire.simMasterWrite({0xAA, SbuLink::CMD_PING, 0x00, 0x00, 0xAA ^ SbuLink::CMD_PING});
    std::vector<uint8_t> snap_after_cmd = sbuWire.simMasterRead();
    assertTrue(snap_after_cmd.size() == 12, "5-byte 0xAA cmd resets tx_reg_");

    // Verify overpressure emits CMD_ESTOP once across repeated 100 Hz ticks with fault_code==0x02
    Serial.reset();
    g_cis_raw_abp1 = 14000; // > 10 psi
    for (int i = 0; i < 4; ++i) {
        delay(15);
        pump_loop();
    }
    int estop_pkts = 0;
    for (size_t i = 0; i + 4 < Serial.tx_bytes.size(); i += 5) {
        if (Serial.tx_bytes[i] == 0xAA && Serial.tx_bytes[i + 1] == SbuLink::CMD_ESTOP) {
            ++estop_pkts;
        }
    }
    assertTrue(g_overpressure_fault && !g_estop_tripped, "overpressure keeps fault_code 0x02");
    assertTrue(estop_pkts == 1, "overpressure emits CMD_ESTOP exactly once on rising edge");
    return 0;
}

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    const char* mode = argv[1];
    if (std::strcmp(mode, "driver_soft_reset_fail") == 0) return runDriverSoftResetFail();
    if (std::strcmp(mode, "case1_nonpd_5v") == 0) return runCase1NonPd5vBoot();
    if (std::strcmp(mode, "case1_slow_pd") == 0) return runCase1SlowPd();
    if (std::strcmp(mode, "case2_setup") == 0) return runCase2Setup();
    if (std::strcmp(mode, "case2_loop_hotplug") == 0) return runCase2LoopHotplug();
    if (std::strcmp(mode, "scenario_c5") == 0) return runScenarioC5SilentBrownout();
    if (std::strcmp(mode, "scenario_c5_15v_pdo_numb3") == 0) return runScenarioC5SilentBrownout15v(false);
    if (std::strcmp(mode, "scenario_c5_15v_pdo_numb2") == 0) return runScenarioC5SilentBrownout15v(true);
    if (std::strcmp(mode, "rdo_read_nack_setup") == 0) return runRdoReadNackSetup();
    if (std::strcmp(mode, "rdo_read_nack_loop") == 0) return runRdoReadNackLoop();
    if (std::strcmp(mode, "stuck20v_unclamped5v_safety") == 0) return runStuck20vAndUnclamped5vAndSafety();
    return 2;
}
"""


class TestPumpFirmwareHostCpp(unittest.TestCase):
    """Host-compiled C++ behavioral tests exercising real Pump_firmware/src/**/*.cpp."""

    @classmethod
    def setUpClass(cls):
        gpp = shutil.which("g++")
        if gpp is None:
            raise unittest.SkipTest("g++ compiler not available")

        cls._tmpdir = tempfile.TemporaryDirectory(prefix="mr1_pump_fw_test_")
        tmp = Path(cls._tmpdir.name)
        inc_dir = tmp / "mock_inc"
        inc_dir.mkdir()
        (inc_dir / "Arduino.h").write_text(_MOCK_ARDUINO_H, encoding="utf-8")
        (inc_dir / "Wire.h").write_text(_MOCK_WIRE_H, encoding="utf-8")
        (inc_dir / "stm32g4xx_hal.h").write_text(_MOCK_STM32_HAL_H, encoding="utf-8")

        harness_cpp = tmp / "mock_harness.cpp"
        harness_cpp.write_text(_MOCK_HAL_AND_HARNESS_CPP, encoding="utf-8")

        fw_root = REPO_ROOT / "Pump_firmware"
        src_files = [
            fw_root / "src" / "hal" / "soft_i2c.cpp",
            fw_root / "src" / "hal" / "stusb4500_pd.cpp",
            fw_root / "src" / "hal" / "drv8837c_motor.cpp",
            fw_root / "src" / "hal" / "abp2_pressure.cpp",
            fw_root / "src" / "comm" / "sbu_link.cpp",
            fw_root / "src" / "main.cpp",
            harness_cpp,
        ]
        cls._exe = tmp / "pump_fw_host_test"
        cmd = [
            gpp,
            "-std=gnu++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Dsetup=pump_setup",
            "-Dloop=pump_loop",
            f"-I{inc_dir}",
            f"-I{fw_root / 'include'}",
            f"-I{fw_root / 'src'}",
            *[str(p) for p in src_files],
            "-o",
            str(cls._exe),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise AssertionError(
                f"Host C++ compilation failed (rc={proc.returncode}):\n{proc.stderr}\n{proc.stdout}"
            )
        cls._compile_stderr = proc.stderr

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_tmpdir"):
            cls._tmpdir.cleanup()

    def _run_scenario(self, scenario: str) -> None:
        proc = subprocess.run(
            [str(self._exe), scenario],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Scenario {scenario!r} failed (rc={proc.returncode}):\n{proc.stderr}\n{proc.stdout}",
        )

    def test_stusb4500_soft_reset_fail_does_not_spoof_9v(self):
        self._run_scenario("driver_soft_reset_fail")

    def test_main_case1_nonpd_5v_boot_and_slow_pd(self):
        self._run_scenario("case1_nonpd_5v")
        self._run_scenario("case1_slow_pd")

    def test_main_case2_15v_soft_reset_fail_latches_ov_fault(self):
        self._run_scenario("case2_setup")
        self._run_scenario("case2_loop_hotplug")

    def test_main_scenario_c5_silent_brownout_nvm_reset(self):
        self._run_scenario("scenario_c5")
        self._run_scenario("scenario_c5_15v_pdo_numb3")
        self._run_scenario("scenario_c5_15v_pdo_numb2")

    def test_main_rdo_read_nack_latches_ov_fault_and_estop(self):
        self._run_scenario("rdo_read_nack_setup")
        self._run_scenario("rdo_read_nack_loop")

    def test_main_stuck_20v_and_unclamped_5v_and_driver_safety_invariants(self):
        self._run_scenario("stuck20v_unclamped5v_safety")


if __name__ == "__main__":
    unittest.main()
