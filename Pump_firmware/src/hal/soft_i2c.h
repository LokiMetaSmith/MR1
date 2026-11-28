/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#pragma once
#include <Arduino.h>
#include <stddef.h>
#include <stdint.h>

/**
 * Self-contained open-drain Software I2C Master (~100 kHz).
 * Used for PD_I2C (PB10 SCL / PB11 SDA), which lack hardware I2C AF on STM32G431.
 */
class SoftI2C {
public:
    SoftI2C(uint8_t sda_pin, uint8_t scl_pin, uint32_t clock_hz = 100000);

    void begin();
    bool probe(uint8_t addr7);
    bool writeRegister(uint8_t addr7, uint8_t reg, uint8_t val);
    bool writeBytes(uint8_t addr7, uint8_t reg, const uint8_t* data, size_t len);
    bool readRegister(uint8_t addr7, uint8_t reg, uint8_t& val);
    bool readBytes(uint8_t addr7, uint8_t reg, uint8_t* data, size_t len);

private:
    uint8_t sda_pin_;
    uint8_t scl_pin_;
    uint32_t half_period_us_;

    static constexpr uint32_t CLOCK_STRETCH_TIMEOUT_US = 25000UL;

    bool sclHigh();
    void sclLow();
    void sdaHigh();
    void sdaLow();

    bool startCondition();
    bool stopCondition();
    bool writeByte(uint8_t byte, bool& ack);
    bool readByte(bool send_ack, uint8_t& byte);
};
