/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#pragma once
#include <Arduino.h>

/**
 * MR1 Pump & USB-PD Hub - Hardware Pinout Definitions
 * Target MCU: STM32G431CBU6 (UFQFPN-48, 170 MHz ARM Cortex-M4)
 * Schematic Reference: Pump/MCU_STM32.kicad_sch
 */

// =============================================================================
// Isolated I2C Buses (3 Buses — Zero Address Collisions)
// =============================================================================
// PRESS_I2C (HW I2C1): Pressure Transducers U301 (0x28) & U302 (0x38)
// Note: PB8 is dedicated BOOT0 (R201 10k pull-down to GND) — NEVER assign PB8.
#define PIN_PRESS_I2C_SCL       PA15    // HW I2C1_SCL (AF4)
#define PIN_PRESS_I2C_SDA       PB9     // HW I2C1_SDA (AF4)
#define PIN_I2C1_SCL            PIN_PRESS_I2C_SCL
#define PIN_I2C1_SDA            PIN_PRESS_I2C_SDA

// PD_I2C (SW-I2C): STUSB4500QTR USB-PD Controller U101 (0x28)
// Note: PB10/PB11 have no HW I2C AF on STM32G431; driven via open-drain SoftI2C.
#define PIN_PD_I2C_SCL          PB10    // SW-I2C SCL (4.7k pull-up R103)
#define PIN_PD_I2C_SDA          PB11    // SW-I2C SDA (4.7k pull-up R109)

// SBU_I2C (HW I2C3 Slave @ 0x38): USB-C SBU1/SBU2 Inter-Board Link to MR1
// Note: PA2/PA3 are no_connect in Pump/MCU_STM32.kicad_sch; USB CDC uses PA11/PA12.
#define PIN_SBU_I2C_SCL         PA8     // HW I2C3_SCL (AF2) -> J6.A8 (SBU1)
#define PIN_SBU_I2C_SDA         PB5     // HW I2C3_SDA (AF8) -> J6.B8 (SBU2)

// =============================================================================
// Motor Drivers (Modular StepStick / TMC2209 / TMC5160 / Pololu)
// =============================================================================
// Pump 1: Cis Chamber Feed Line (MOD401)
#define PIN_PUMP1_STEP          PA0     // TIM2_CH1 -> MOD401.7 STEP (microstep pulse output)
#define PIN_PUMP1_DIR           PB12    // GPIO     -> MOD401.8 DIR (direction)
#define PIN_PUMP1_PWM           PIN_PUMP1_STEP  // Legacy alias for PWM/STEP control

// Pump 2: Trans Chamber Recirculation / Waste Line (MOD402)
#define PIN_PUMP2_STEP          PA1     // TIM2_CH2 -> MOD402.7 STEP (microstep pulse output)
#define PIN_PUMP2_DIR           PB13    // GPIO     -> MOD402.8 DIR (direction)
#define PIN_PUMP2_PWM           PIN_PUMP2_STEP  // Legacy alias for PWM/STEP control

// Single-wire Half-Duplex TMC UART bus (USART2_TX)
#define PIN_PUMP_UART           PA2     // USART2_TX -> MOD401.4 / MOD402.4 via 1k R401

// Driver ~SLEEP / Hardware ESTOP Line (U12.7 & U401.7, 2x 100k internal pulldowns)
// Configured as OUTPUT HIGH in normal operation; driven LOW only when entering sleep.
#define PIN_ESTOP_TRIGGER       PB0

// =============================================================================
// Power Management & Multiplexer Control
// =============================================================================
#define PIN_MR1_PWR_EN          PA4     // U103 TPS22917DBV ON (active HIGH for +5V_MR1_CLEAN)
#define PIN_USB_SEL_PASS        PA5     // U503 TS3USB30EDGSR S (HIGH=J6 MR1 pass-through, LOW=MCU PA11/PA12)

// External Alert / Data-Ready Lines
#define PIN_PD_ALERT            PB1     // U101 STUSB4500 ALERT (open-drain active LOW, 10k R102)
#define PIN_PRESS_ALERT         PB2     // U301 ABPDANN015PG2A3 INT (active HIGH data-ready)

// =============================================================================
// Diagnostic Status LEDs (All 5x D201..D205 Green KT-0603G via 330R)
// =============================================================================
// Note: Call HAL_PWREx_DisableUCPDDeadBattery() in setup() before driving PB6.
// Note: PC13 is no_connect in Pump/MCU_STM32.kicad_sch.
#define PIN_LED_FAULT           PB6     // D201 Green KT-0603G (Fault / Overpressure / ESTOP)
#define PIN_LED_PUMP1           PB14    // D202 Green KT-0603G (Pump 1 Cis active)
#define PIN_LED_PUMP2           PB15    // D203 Green KT-0603G (Pump 2 Trans active)
#define PIN_LED_PD_READY        PA10    // D204 Green KT-0603G (Negotiated PD contract active)
#define PIN_LED_MR1_5V          PA6     // D205 Green KT-0603G (+5V_MR1_CLEAN rail enabled)
