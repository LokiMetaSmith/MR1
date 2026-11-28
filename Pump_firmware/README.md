# MR1 Pump & USB-PD Hub Firmware

This directory contains the production C++ firmware for the **MR1 Pump & USB-PD Hub Board (`Pump/`)** targeting the **STM32G431CBU6** microcontroller (ARM Cortex-M4 @ 170 MHz).

---

## 1. Overview & Capabilities

The Pump Subsystem manages automated fluid delivery and power distribution for the MR1 Nanopore Reader:

- **Autonomous USB-PD Negotiation (`VMOTOR <= 9V`)**: Manages the `STUSB4500QTR` autonomous USB-PD sink controller (`0x28`) over a dedicated open-drain software I2C bus (`PB10/PB11`), strictly capping `VMOTOR <= 9V` (PDO1 5V / PDO2 9V; 12V/15V/20V disallowed via RAM PDO override + PD `SOFT_RESET`) to protect the `DRV8837C` motor drivers (11V recommended / 12V absolute max).
- **Ultra-Clean +5V Output**: Controls the high-efficiency step-down buck converter (`U102`) and clean +5V load switch (`U103` `TPS22917DBV`) supplying clean 5V power (`+5V_MR1_CLEAN`) to the MR1 Reader analog frontend.
- **Dual Peristaltic Motor Control**: Hardware `TIM2` 20 kHz 12-bit PWM (`PA0/PA1`) velocity control and `IN1/IN2` direction & PWM control (Fwd: fast-decay/coast, Rev: slow-decay/brake) for two TI `DRV8837C` motor drivers (`~SLEEP` on `PB0`):
  - **Pump 1 (`U12`)**: Cis chamber fluid feed ($210^\circ$).
  - **Pump 2 (`U401`)**: Trans chamber recirculation and waste drain ($330^\circ$).
- **Dual Pressure Transducers**: Real-time 400 kHz HW `I2C1` (`PA15/PB9`) telemetry from dual 3.3V Honeywell ABP1 14-bit direct-read sensors (`A`-option, no temperature output):
  - Sensor 1 (`U301` `ABPDANN015PG2A3`, `0x28`, 0–15 psi gauge): Monitors Cis chamber inlet pressure (`INT` -> `PB2`).
  - Sensor 2 (`U302` `ABPDANN005PG3A3`, `0x38`, 0–5 psi gauge): Monitors Trans chamber differential/recirculation pressure.
- **Driver `~SLEEP` & Active Braking**: Dedicated `PB0` (`PIN_ESTOP_TRIGGER` / `~SLEEP`) driven `OUTPUT HIGH` during normal run (with `HAL_PWREx_DisableUCPDDeadBattery()` called at startup so `PB6` `LED_FAULT` has no internal `Rd` pull-down) and active braking (`IN1=1, IN2=1`) upon overpressure, sensor fault, or SBU emergency stop.
- **SBU Inter-Board Link (`HW I2C3` Slave `0x38`)**: Communication back to the MR1 Reader over USB-C Sideband Use (`SBU1/SBU2`) pins (`PA8` SCL / `PB5` SDA @ 100 kHz), with optional USB CDC serial (`PA11/PA12`) when `USB_SEL_PASS` is `LOW`.
- **High-Speed USB 2.0 Pass-Through**: Directs the TI `TS3USB30EDGSR` (`U503`) multiplexer (`PA5`) to pass high-speed telemetry directly from MR1 (`J6`) to the host (`J7`) without MCU buffering.

---

## 2. Hardware Pinout

Pin mappings correspond directly to `Pump/MCU_STM32.kicad_sch` (`U11` `STM32G431CBU6`) and `include/pinout.h` (`PB8` is dedicated `BOOT0` via `R201` 10k pull-down to `GND`; `PC13`, `PA2`, `PA3` are `no_connect`):

| Signal Name | STM32 Pin | Function / Peripheral | Description |
| :--- | :--- | :--- | :--- |
| **PIN_PRESS_I2C_SCL** | PA15 | HW `I2C1_SCL` (`PRESS_I2C`) | Pressure transducers `U301` (`0x28`) & `U302` (`0x38`) clock |
| **PIN_PRESS_I2C_SDA** | PB9 | HW `I2C1_SDA` (`PRESS_I2C`) | Pressure transducers `U301` & `U302` data |
| **PIN_PD_I2C_SCL** | PB10 | SW-I2C SCL (`PD_I2C`) | `STUSB4500QTR` (`0x28`) open-drain bit-bang clock |
| **PIN_PD_I2C_SDA** | PB11 | SW-I2C SDA (`PD_I2C`) | `STUSB4500QTR` (`0x28`) open-drain bit-bang data |
| **PIN_SBU_I2C_SCL** | PA8 | HW `I2C3_SCL` (`SBU_I2C`) | Inter-board SBU `I2C3` slave (`0x38`) clock -> `J6.A8` (`SBU1`) |
| **PIN_SBU_I2C_SDA** | PB5 | HW `I2C3_SDA` (`SBU_I2C`) | Inter-board SBU `I2C3` slave (`0x38`) data -> `J6.B8` (`SBU2`) |
| **PIN_PUMP1_PWM** | PA0 | `TIM2_CH1` (20 kHz PWM) | Cis pump `U12` `IN1` speed control |
| **PIN_PUMP1_DIR** | PB12 | GPIO Output | Cis pump `U12` `IN2` direction / brake |
| **PIN_PUMP2_PWM** | PA1 | `TIM2_CH2` (20 kHz PWM) | Trans pump `U401` `IN1` speed control |
| **PIN_PUMP2_DIR** | PB13 | GPIO Output | Trans pump `U401` `IN2` direction / brake |
| **PIN_ESTOP_TRIGGER** | PB0 | GPIO Output (`~SLEEP`) | `DRV8837C` `~SLEEP` enable (`HIGH` run / `LOW` sleep) |
| **PIN_MR1_PWR_EN** | PA4 | GPIO Output | `U103` `TPS22917DBV` enable for `+5V_MR1_CLEAN` |
| **PIN_USB_SEL_PASS** | PA5 | GPIO Output | `U503` `TS3USB30EDGSR` mux (`HIGH`=MR1 `J6`, `LOW`=MCU USB) |
| **PIN_PD_ALERT** | PB1 | GPIO Input | `U101` `STUSB4500` `ALERT` (open-drain active LOW) |
| **PIN_PRESS_ALERT** | PB2 | GPIO Input | `U301` `ABPDANN015PG2A3` `INT` (active HIGH data-ready) |
| **PIN_LED_FAULT** | PB6 | GPIO Output (`D201` Green) | Fault / overpressure / ESTOP indicator (UCPD dead-battery disabled) |
| **PIN_LED_PUMP1** | PB14 | GPIO Output (`D202` Green) | Pump 1 Cis active indicator |
| **PIN_LED_PUMP2** | PB15 | GPIO Output (`D203` Green) | Pump 2 Trans active indicator |
| **PIN_LED_PD_READY** | PA10 | GPIO Output (`D204` Green) | USB-PD contract active indicator |
| **PIN_LED_MR1_5V** | PA6 | GPIO Output (`D205` Green) | `+5V_MR1_CLEAN` rail enabled indicator |
| **BOOT0** | PB8 | Dedicated `BOOT0` | 10k pull-down `R201` to `GND` (never assigned in firmware) |
| **USB_MCU_DM / DP** | PA11 / PA12 | Native USB FS CDC | USB CDC `Serial` when `USB_SEL_PASS == LOW` |

---

## 3. Build & Upload Instructions

The firmware is built using **PlatformIO Core**:

```bash
# Navigate to the pump firmware directory
cd Pump_firmware

# Compile the firmware
pio run

# Upload via ST-Link (SWD interface)
pio run --target upload
```

Configuration parameters (maximum allowable pressure limits, PWM base frequencies, and default flow rates) are defined in `include/config.h`.
