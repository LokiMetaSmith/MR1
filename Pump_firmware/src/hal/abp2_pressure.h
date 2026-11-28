/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <math.h>

/**
 * Honeywell Basic Amplified (ABP1 Series) 14-bit Digital Pressure Transducer Driver
 * Supports direct 2-byte I2C readouts for ABPDANN015PG2A3 (0x28) and ABPDANN005PG3A3 (0x38).
 * Note: 'A' transfer-function SKUs do not provide temperature output (getTemperatureC() -> NAN).
 */
class ABP1Sensor {
public:
    enum Status {
        STATUS_OK           = 0, // 00: Normal operation, valid fresh data
        STATUS_COMMAND_MODE = 1, // 01: Device in command mode
        STATUS_STALE_DATA   = 2, // 10: Data already fetched since last ~2 kHz conversion
        STATUS_DIAGNOSTIC   = 3, // 11: Diagnostic fault condition
        STATUS_COMM_ERROR   = 4  // I2C bus / NACK communication error
    };

    ABP1Sensor(TwoWire& wire, uint8_t i2c_addr, float p_min_psi, float p_max_psi);

    bool begin();
    Status read();

    float getPressurePsi() const { return pressure_psi_ - tare_offset_psi_; }
    float getPressureMbar() const { return getPressurePsi() * 68.9476f; }
    float getRawPressurePsi() const { return pressure_psi_; }
    float getTemperatureC() const { return temperature_c_; }
    bool hasTemperature() const { return false; }
    Status getStatus() const { return last_status_; }

    void tare() { tare_offset_psi_ = pressure_psi_; }
    void resetTare() { tare_offset_psi_ = 0.0f; }

private:
    TwoWire& wire_;
    uint8_t addr_;
    float p_min_;
    float p_max_;
    float pressure_psi_;
    float temperature_c_;
    float tare_offset_psi_;
    Status last_status_;

    static constexpr uint16_t OUTPUT_MIN = 1638;   // 10% of 2^14 (16384)
    static constexpr uint16_t OUTPUT_MAX = 14746;  // 90% of 2^14 (16384)
};

// Backwards-compatible type alias for callers referencing ABP2Sensor
using ABP2Sensor = ABP1Sensor;
