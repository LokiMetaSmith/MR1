/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#include "abp2_pressure.h"

ABP1Sensor::ABP1Sensor(TwoWire& wire, uint8_t i2c_addr, float p_min_psi, float p_max_psi)
    : wire_(wire), addr_(i2c_addr), p_min_(p_min_psi), p_max_(p_max_psi),
      pressure_psi_(0.0f), temperature_c_(NAN), tare_offset_psi_(0.0f),
      last_status_(STATUS_COMM_ERROR) {}

bool ABP1Sensor::begin() {
    wire_.beginTransmission(addr_);
    uint8_t err = wire_.endTransmission();
    if (err == 0) {
        last_status_ = STATUS_OK;
        return true;
    }
    last_status_ = STATUS_COMM_ERROR;
    return false;
}

ABP1Sensor::Status ABP1Sensor::read() {
    // Honeywell ABP1: direct 2-byte I2C read (no 0xAA trigger command, no conversion wait)
    uint8_t count = wire_.requestFrom(addr_, (uint8_t)2);
    if (count != 2) {
        while (wire_.available() > 0) {
            wire_.read();
        }
        last_status_ = STATUS_COMM_ERROR;
        return last_status_;
    }

    uint8_t msb = (uint8_t)wire_.read();
    uint8_t lsb = (uint8_t)wire_.read();
    uint16_t raw16 = ((uint16_t)msb << 8) | (uint16_t)lsb;

    // Bits [15:14] = status, Bits [13:0] = 14-bit bridge count
    uint8_t status_bits = (uint8_t)((raw16 >> 14) & 0x03);
    uint16_t counts = raw16 & 0x3FFF;

    if (status_bits == 0x01) {
        last_status_ = STATUS_COMMAND_MODE;
        return last_status_;
    }
    if (status_bits == 0x03) {
        last_status_ = STATUS_DIAGNOSTIC;
        return last_status_;
    }

    // Transfer Function A (10%..90% of 2^14 counts)
    if (counts <= OUTPUT_MIN) {
        pressure_psi_ = p_min_;
    } else if (counts >= OUTPUT_MAX) {
        pressure_psi_ = p_max_;
    } else {
        pressure_psi_ = (((float)(counts - OUTPUT_MIN) * (p_max_ - p_min_)) /
                         (float)(OUTPUT_MAX - OUTPUT_MIN)) + p_min_;
    }

    last_status_ = (status_bits == 0x02) ? STATUS_STALE_DATA : STATUS_OK;
    return last_status_;
}
