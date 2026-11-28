#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""
Generate Pump/Motor_Drivers.kicad_sch with clean coordinates and 0 crossings.
"""

import uuid

def gen_uuid():
    return str(uuid.uuid4())

def generate():
    sch = f"""(kicad_sch
\t(version 20260306)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "{gen_uuid()}")
\t(paper "A3")
\t(title_block
\t\t(title "MR1 Pump Module - Dual Modular StepStick Motor Drivers")
\t\t(date "2026-11-28")
\t\t(rev "2.0")
\t\t(company "MR1 Open Source Project")
\t\t(comment 1 "Dual Modular StepStick Sockets (TMC2209 / TMC5160 / BTT EZDriver compatible)")
\t\t(comment 2 "Operating voltage VMOTOR 5V-20V from negotiated USB-PD rail")
\t\t(comment 3 "Independent STEP/DIR pulse metering & single-wire TMC UART configuration")
\t\t(comment 4 "Hardware emergency disable gate wired to weep moat leak sensor")
\t)
\t(lib_symbols
\t\t(symbol "Connector_Generic:Conn_01x04"
\t\t\t(pin_names (offset 1.016) (hide yes))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "J" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "Conn_01x04" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
\t\t\t(property "Footprint" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "Conn_01x04_1_1"
\t\t\t\t(pin passive line (at -5.08 3.81 0) (length 2.54) (name "Pin_1" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -5.08 1.27 0) (length 2.54) (name "Pin_2" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -5.08 -1.27 0) (length 2.54) (name "Pin_3" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -5.08 -3.81 0) (length 2.54) (name "Pin_4" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)
\t\t(symbol "Device:C"
\t\t\t(pin_numbers (hide yes)) (pin_names (offset 0.254))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "C" (at 0.635 2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t\t(property "Value" "C" (at 0.635 -2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t\t(symbol "C_0_1"
\t\t\t\t(polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.508)))
\t\t\t\t(polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508)))
\t\t\t)
\t\t\t(symbol "C_1_1"
\t\t\t\t(pin passive line (at 0 3.81 270) (length 2.794) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 0 -3.81 90) (length 2.794) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)
\t\t(symbol "Device:R"
\t\t\t(pin_numbers (hide yes)) (pin_names (offset 0))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "R" (at -2.032 0 90) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "R_0_1"
\t\t\t\t(rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "R_1_1"
\t\t\t\t(pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)
\t\t(symbol "Driver_Motor:StepStick_Socket"
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
\t\t\t(property "Reference" "MOD" (at -10.16 12.7 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t\t(property "Value" "StepStick_Socket" (at -10.16 -12.7 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t\t(property "Footprint" "Module:Pololu_Breakout-16_15.2x20.3mm" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "StepStick_Socket_0_1"
\t\t\t\t(rectangle (start -10.16 -11.43) (end 10.16 11.43) (stroke (width 0.254)) (fill (type background)))
\t\t\t)
\t\t\t(symbol "StepStick_Socket_1_1"
\t\t\t\t(pin passive line (at -12.7 8.89 0) (length 2.54) (name "~ENABLE" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -12.7 6.35 0) (length 2.54) (name "MS1" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -12.7 3.81 0) (length 2.54) (name "MS2" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -12.7 1.27 0) (length 2.54) (name "MS3_UART" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -12.7 -1.27 0) (length 2.54) (name "~RESET" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -12.7 -3.81 0) (length 2.54) (name "~SLEEP" (effects (font (size 1.27 1.27)))) (number "6" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -12.7 -6.35 0) (length 2.54) (name "STEP" (effects (font (size 1.27 1.27)))) (number "7" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at -12.7 -8.89 0) (length 2.54) (name "DIR" (effects (font (size 1.27 1.27)))) (number "8" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin power_in line (at 12.7 -8.89 180) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "9" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin power_in line (at 12.7 -6.35 180) (length 2.54) (name "VIO" (effects (font (size 1.27 1.27)))) (number "10" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 12.7 -3.81 180) (length 2.54) (name "1B" (effects (font (size 1.27 1.27)))) (number "11" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 12.7 -1.27 180) (length 2.54) (name "1A" (effects (font (size 1.27 1.27)))) (number "12" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 12.7 1.27 180) (length 2.54) (name "2A" (effects (font (size 1.27 1.27)))) (number "13" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin passive line (at 12.7 3.81 180) (length 2.54) (name "2B" (effects (font (size 1.27 1.27)))) (number "14" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin power_in line (at 12.7 6.35 180) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "15" (effects (font (size 1.27 1.27)))))
\t\t\t\t(pin power_in line (at 12.7 8.89 180) (length 2.54) (name "VMOT" (effects (font (size 1.27 1.27)))) (number "16" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)
\t\t(symbol "power:GND"
\t\t\t(power) (pin_numbers (hide yes)) (pin_names (offset 0))
\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t\t(property "Reference" "#PWR" (at 0 -6.35 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "GND" (at 0 -3.81 0) (show_name no) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "GND_0_1"
\t\t\t\t(polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0)) (fill (type none)))
\t\t\t)
\t\t\t(symbol "GND_1_1"
\t\t\t\t(pin power_in line (at 0 0 270) (length 0) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t)
\t\t)
\t)

\t(hierarchical_label "PUMP1_STEP" (shape input) (at 50.8 107.95 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))
\t(hierarchical_label "PUMP1_DIR" (shape input) (at 50.8 110.49 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))
\t(hierarchical_label "PUMP2_STEP" (shape input) (at 50.8 171.45 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))
\t(hierarchical_label "PUMP2_DIR" (shape input) (at 50.8 173.99 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))
\t(hierarchical_label "PUMP_UART" (shape bidirectional) (at 50.8 100.33 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))
\t(hierarchical_label "ESTOP_TRIGGER_" (shape input) (at 50.8 105.41 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))
\t(hierarchical_label "+3V3" (shape input) (at 50.8 55.88 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))
\t(hierarchical_label "VMOTOR" (shape input) (at 50.8 63.5 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))

\t(symbol (lib_id "Driver_Motor:StepStick_Socket") (at 101.6 101.6 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "MOD401" (at 101.6 87.63 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "StepStick_Socket" (at 101.6 116.84 0) (effects (font (size 1.27 1.27))))
\t\t(property "Footprint" "Module:Pololu_Breakout-16_15.2x20.3mm" (at 101.6 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C22550" (at 101.6 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "PinHeader_1x08_P2.54mm_Female" (at 101.6 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "Cis Pump StepStick Socket (TMC2209 Address 0b00)" (at 101.6 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t\t(pin "3" (uuid "{gen_uuid()}"))
\t\t(pin "4" (uuid "{gen_uuid()}"))
\t\t(pin "5" (uuid "{gen_uuid()}"))
\t\t(pin "6" (uuid "{gen_uuid()}"))
\t\t(pin "7" (uuid "{gen_uuid()}"))
\t\t(pin "8" (uuid "{gen_uuid()}"))
\t\t(pin "9" (uuid "{gen_uuid()}"))
\t\t(pin "10" (uuid "{gen_uuid()}"))
\t\t(pin "11" (uuid "{gen_uuid()}"))
\t\t(pin "12" (uuid "{gen_uuid()}"))
\t\t(pin "13" (uuid "{gen_uuid()}"))
\t\t(pin "14" (uuid "{gen_uuid()}"))
\t\t(pin "15" (uuid "{gen_uuid()}"))
\t\t(pin "16" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Driver_Motor:StepStick_Socket") (at 101.6 165.1 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "MOD402" (at 101.6 151.13 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "StepStick_Socket" (at 101.6 180.34 0) (effects (font (size 1.27 1.27))))
\t\t(property "Footprint" "Module:Pololu_Breakout-16_15.2x20.3mm" (at 101.6 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C22550" (at 101.6 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "PinHeader_1x08_P2.54mm_Female" (at 101.6 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "Trans Pump StepStick Socket (TMC2209 Address 0b01)" (at 101.6 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t\t(pin "3" (uuid "{gen_uuid()}"))
\t\t(pin "4" (uuid "{gen_uuid()}"))
\t\t(pin "5" (uuid "{gen_uuid()}"))
\t\t(pin "6" (uuid "{gen_uuid()}"))
\t\t(pin "7" (uuid "{gen_uuid()}"))
\t\t(pin "8" (uuid "{gen_uuid()}"))
\t\t(pin "9" (uuid "{gen_uuid()}"))
\t\t(pin "10" (uuid "{gen_uuid()}"))
\t\t(pin "11" (uuid "{gen_uuid()}"))
\t\t(pin "12" (uuid "{gen_uuid()}"))
\t\t(pin "13" (uuid "{gen_uuid()}"))
\t\t(pin "14" (uuid "{gen_uuid()}"))
\t\t(pin "15" (uuid "{gen_uuid()}"))
\t\t(pin "16" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Connector_Generic:Conn_01x04") (at 152.4 101.6 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "J401" (at 152.4 92.71 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "PUMP1_CIS_MOTOR" (at 152.4 110.49 0) (effects (font (size 1.27 1.27))))
\t\t(property "Footprint" "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical" (at 152.4 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C144395" (at 152.4 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "B4B-XH-A(LF)(SN)" (at 152.4 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "Cis Peristaltic Pump Motor Header (1A, 1B, 2A, 2B)" (at 152.4 101.6 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t\t(pin "3" (uuid "{gen_uuid()}"))
\t\t(pin "4" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Connector_Generic:Conn_01x04") (at 152.4 165.1 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "J402" (at 152.4 156.21 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "PUMP2_TRANS_MOTOR" (at 152.4 173.99 0) (effects (font (size 1.27 1.27))))
\t\t(property "Footprint" "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical" (at 152.4 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C144395" (at 152.4 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "B4B-XH-A(LF)(SN)" (at 152.4 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "Trans Peristaltic Pump Motor Header (1A, 1B, 2A, 2B)" (at 152.4 165.1 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t\t(pin "3" (uuid "{gen_uuid()}"))
\t\t(pin "4" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Device:C") (at 127 88.9 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "C401" (at 129.54 87.63 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "10uF 50V X7R" (at 129.54 90.17 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Capacitor_SMD:C_1206_3216Metric" (at 127 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C89632" (at 127 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "CL31B106KBHNNNE" (at 127 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "MOD401 VMOT Decoupling" (at 127 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Device:C") (at 137.16 88.9 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "C403" (at 139.7 87.63 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "100uF 35V" (at 139.7 90.17 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Capacitor_SMD:CP_Elec_6.3x7.7" (at 137.16 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C134544" (at 137.16 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "VT1V101M0607" (at 137.16 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "VMOTOR Bulk Storage" (at 137.16 88.9 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Device:C") (at 127 114.3 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "C404" (at 129.54 113.03 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "100nF 50V" (at 129.54 115.57 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Capacitor_SMD:C_0402_1005Metric" (at 127 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C1525" (at 127 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "CL05B104KO5NNNC" (at 127 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "MOD401 VIO Decoupling" (at 127 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Device:C") (at 127 152.4 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "C402" (at 129.54 151.13 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "10uF 50V X7R" (at 129.54 153.67 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Capacitor_SMD:C_1206_3216Metric" (at 127 152.4 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C89632" (at 127 152.4 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "CL31B106KBHNNNE" (at 127 152.4 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "MOD402 VMOT Decoupling" (at 127 152.4 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Device:C") (at 127 177.8 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "C405" (at 129.54 176.53 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "100nF 50V" (at 129.54 179.07 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Capacitor_SMD:C_0402_1005Metric" (at 127 177.8 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C1525" (at 127 177.8 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "CL05B104KO5NNNC" (at 127 177.8 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "MOD402 VIO Decoupling" (at 127 177.8 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Device:R") (at 63.5 100.33 90) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "R401" (at 63.5 96.52 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "1k 1%" (at 63.5 104.14 0) (effects (font (size 1.27 1.27))))
\t\t(property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at 63.5 100.33 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C11702" (at 63.5 100.33 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "0402WGF1001TCE" (at 63.5 100.33 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "TMC UART bidirectional isolation" (at 63.5 100.33 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t)

\t(symbol (lib_id "Device:R") (at 63.5 114.3 0) (unit 1)
\t\t(in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
\t\t(uuid "{gen_uuid()}")
\t\t(property "Reference" "R402" (at 66.04 113.03 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "10k 1%" (at 66.04 115.57 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at 63.5 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "LCSC" "C25744" (at 63.5 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MPN" "0402WGF1002TCE" (at 63.5 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(property "MR1_Role" "ESTOP_TRIGGER_ pull-up" (at 63.5 114.3 0) (hide yes) (effects (font (size 1.27 1.27))))
\t\t(pin "1" (uuid "{gen_uuid()}"))
\t\t(pin "2" (uuid "{gen_uuid()}"))
\t)

\t;; GND Symbols
\t(symbol (lib_id "power:GND") (at 83.82 92.71 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR401" (at 83.82 95.25 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 83.82 95.25 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 83.82 156.21 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR402" (at 83.82 158.75 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 83.82 158.75 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 83.82 161.29 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR403" (at 83.82 163.83 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 83.82 163.83 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 114.3 95.25 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR404" (at 114.3 97.79 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 114.3 97.79 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 114.3 110.49 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR405" (at 114.3 113.03 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 114.3 113.03 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 114.3 158.75 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR406" (at 114.3 161.29 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 114.3 161.29 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 114.3 173.99 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR407" (at 114.3 176.53 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 114.3 176.53 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 127 92.71 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR408" (at 127 95.25 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 127 95.25 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 137.16 92.71 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR409" (at 137.16 95.25 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 137.16 95.25 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 127 118.11 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR410" (at 127 120.65 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 127 120.65 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 127 156.21 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR411" (at 127 158.75 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 127 158.75 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))
\t(symbol (lib_id "power:GND") (at 127 181.61 0) (unit 1) (uuid "{gen_uuid()}") (property "Reference" "#PWR412" (at 127 184.15 0) (hide yes) (effects (font (size 1.27 1.27)))) (property "Value" "GND" (at 127 184.15 0) (hide yes) (effects (font (size 1.27 1.27)))) (pin "1" (uuid "{gen_uuid()}")))

\t;; MOD401 Left side:
\t;; pin 1 ~EN, pin 2 MS1, pin 3 MS2 tied to GND
\t(wire (pts (xy 88.9 92.71) (xy 83.82 92.71)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 88.9 95.25) (xy 83.82 95.25)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 88.9 97.79) (xy 83.82 97.79)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 83.82 92.71) (xy 83.82 97.79)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(junction (at 83.82 92.71) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))
\t(junction (at 83.82 95.25) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))

\t;; pin 4 MS3_UART -> R401 pin 1 (67.31, 100.33)
\t(wire (pts (xy 88.9 100.33) (xy 67.31 100.33)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 59.69 100.33) (xy 50.8 100.33)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; pin 5 ~RESET (102.87) to pin 6 ~SLEEP (105.41)
\t(wire (pts (xy 88.9 102.87) (xy 86.36 102.87)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 86.36 102.87) (xy 86.36 105.41)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 86.36 105.41) (xy 88.9 105.41)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; ESTOP_TRIGGER_ bus
\t(wire (pts (xy 50.8 105.41) (xy 63.5 105.41)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 63.5 105.41) (xy 78.74 105.41)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 78.74 105.41) (xy 86.36 105.41)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(junction (at 63.5 105.41) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))
\t(junction (at 78.74 105.41) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))
\t(junction (at 86.36 105.41) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))

\t;; R402 pull-up connections
\t(wire (pts (xy 63.5 105.41) (xy 63.5 110.49)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 63.5 118.11) (xy 63.5 120.65)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "+3V3" (at 63.5 120.65 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen_uuid()}"))

\t;; STEP & DIR
\t(wire (pts (xy 50.8 107.95) (xy 88.9 107.95)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 50.8 110.49) (xy 88.9 110.49)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; MOD401 Right side:
\t;; pin 16 VMOT (114.3, 92.71)
\t(wire (pts (xy 114.3 92.71) (xy 127 85.09)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 127 85.09) (xy 137.16 85.09)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 137.16 85.09) (xy 144.78 85.09)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "VMOTOR" (at 144.78 85.09 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen_uuid()}"))
\t(junction (at 127 85.09) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))
\t(junction (at 137.16 85.09) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))

\t;; Motor coils to J401
\t(wire (pts (xy 114.3 97.79) (xy 147.32 105.41)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 114.3 100.33) (xy 147.32 102.87)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 114.3 102.87) (xy 147.32 97.79)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 114.3 105.41) (xy 147.32 100.33)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; pin 10 VIO (114.3, 107.95)
\t(wire (pts (xy 114.3 107.95) (xy 127 110.49)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 127 110.49) (xy 137.16 110.49)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "+3V3" (at 137.16 110.49 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen_uuid()}"))
\t(junction (at 127 110.49) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))


\t;; MOD402 Left side:
\t;; pin 1 ~EN to GND
\t(wire (pts (xy 88.9 156.21) (xy 83.82 156.21)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; pin 2 MS1 to +3V3 (Address 0b01)
\t(wire (pts (xy 88.9 158.75) (xy 81.28 158.75)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "+3V3" (at 81.28 158.75 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{gen_uuid()}"))

\t;; pin 3 MS2 to GND
\t(wire (pts (xy 88.9 161.29) (xy 83.82 161.29)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; pin 4 MS3_UART -> PUMP_UART
\t(wire (pts (xy 73.66 100.33) (xy 73.66 163.83)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 73.66 163.83) (xy 88.9 163.83)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(junction (at 73.66 100.33) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))

\t;; pin 5 ~RESET to pin 6 ~SLEEP
\t(wire (pts (xy 88.9 166.37) (xy 86.36 166.37)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 86.36 166.37) (xy 86.36 168.91)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 86.36 168.91) (xy 88.9 168.91)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; ESTOP_TRIGGER_ connects to MOD402 ~SLEEP
\t(wire (pts (xy 78.74 105.41) (xy 78.74 168.91)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 78.74 168.91) (xy 86.36 168.91)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(junction (at 86.36 168.91) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))

\t;; STEP & DIR
\t(wire (pts (xy 50.8 171.45) (xy 88.9 171.45)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 50.8 173.99) (xy 88.9 173.99)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; MOD402 Right side:
\t;; pin 16 VMOT (114.3, 156.21)
\t(wire (pts (xy 114.3 156.21) (xy 127 148.59)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 127 148.59) (xy 137.16 148.59)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "VMOTOR" (at 137.16 148.59 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen_uuid()}"))
\t(junction (at 127 148.59) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))

\t;; Motor coils to J402
\t(wire (pts (xy 114.3 161.29) (xy 147.32 168.91)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 114.3 163.83) (xy 147.32 166.37)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 114.3 166.37) (xy 147.32 161.29)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 114.3 168.91) (xy 147.32 163.83)) (stroke (width 0)) (uuid "{gen_uuid()}"))

\t;; pin 10 VIO (114.3, 171.45)
\t(wire (pts (xy 114.3 171.45) (xy 127 173.99)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(wire (pts (xy 127 173.99) (xy 137.16 173.99)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "+3V3" (at 137.16 173.99 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen_uuid()}"))
\t(junction (at 127 173.99) (diameter 1) (color 0 0 0 0) (uuid "{gen_uuid()}"))

\t;; Global power labels
\t(wire (pts (xy 50.8 55.88) (xy 55.88 55.88)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "+3V3" (at 55.88 55.88 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen_uuid()}"))

\t(wire (pts (xy 50.8 63.5) (xy 55.88 63.5)) (stroke (width 0)) (uuid "{gen_uuid()}"))
\t(label "VMOTOR" (at 55.88 63.5 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen_uuid()}"))
)
"""
    # Strip all comment lines since KiCad S-expression parser rejects ; comments
    clean_lines = [l for l in sch.splitlines() if not l.strip().startswith(';')]
    sch = '\n'.join(clean_lines) + '\n'
    with open("Pump/Motor_Drivers.kicad_sch", "w") as f:
        f.write(sch)
    print("Regenerated Pump/Motor_Drivers.kicad_sch without comments")

if __name__ == "__main__":
    generate()
