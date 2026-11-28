/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#pragma once
#include <stdint.h>

/**
 * MR1 Pump Controller - System Configuration & Safety Limits
 */

// Firmware Identification
#define PUMP_FW_VERSION_MAJOR   1
#define PUMP_FW_VERSION_MINOR   0
#define PUMP_FW_VERSION_PATCH   0

// I2C Device Addresses (across 3 isolated buses)
#define I2C_ADDR_ABP1_CIS       0x28    // PRESS_I2C (I2C1): Honeywell ABPDANN015PG2A3 (0..15 psi)
#define I2C_ADDR_ABP1_TRANS     0x38    // PRESS_I2C (I2C1): Honeywell ABPDANN005PG3A3 (0..5 psi)
#define I2C_ADDR_STUSB4500      0x28    // PD_I2C (SW-I2C): STUSB4500QTR USB-PD sink controller
#define I2C_ADDR_SBU_SLAVE      0x38    // SBU_I2C (I2C3 Slave): USB-C SBU link to MR1 Reader

// USB-PD Safety Limit (DRV8837C VM recommended max 11V, absolute max 12V)
#define STUSB4500_MAX_VOLTAGE_MV 9000   // Strictly cap VMOTOR <= 9V (never 12V/15V/20V)

// Fluidic Safety Thresholds
#define MAX_PRESSURE_CIS_PSI    10.0f   // Safety trip limit on Cis chamber (psi)
#define MAX_PRESSURE_TRANS_PSI  4.0f    // Safety trip limit on Trans chamber (psi)
#define PRESSURE_BURST_MBAR     750.0f  // Absolute maximum allowable pressure head

// Peristaltic Pump Flow Rate Calibrations (Ditao 1/8" ID silicone tubing)
// Note: Ungeared full-scale shaft speed (180 RPM * 45 uL/rev) is 8100 uL/min;
// the 15% minimum motor starting duty corresponds to 1215 uL/min effective floor.
// Incoming SBU flow commands are clamped to MAX_FLOW_RATE_UL_MIN (150 uL/min,
// which engages the 15% starting threshold), while DRV8837CMotor::flush()
// runs at 100% duty (8100 uL/min) for priming/purging.
#define UL_PER_REVOLUTION       45.0f   // Nominal displacement per motor shaft rev (uL)
#define MOTOR_PWM_FREQUENCY_HZ  20000   // 20 kHz ultrasonic PWM (silent operation)
#define MOTOR_PWM_RESOLUTION    12      // 12-bit PWM resolution (0..4095)
#define MAX_FLOW_RATE_UL_MIN    150.0f  // Maximum commanded flow rate (uL/min)
#define MIN_FLOW_RATE_UL_MIN    0.5f    // Minimum steady flow rate (uL/min)

// Hardware Watchdog & Sampling Timing
#define PRESSURE_SAMPLE_RATE_HZ 100     // 100 Hz pressure loop
#define TELEMETRY_BROADCAST_HZ  20      // 20 Hz SBU telemetry rate
#define WATCHDOG_TIMEOUT_MS     500     // Comms loss timeout
