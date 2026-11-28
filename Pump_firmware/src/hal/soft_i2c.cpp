/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#include "soft_i2c.h"

SoftI2C::SoftI2C(uint8_t sda_pin, uint8_t scl_pin, uint32_t clock_hz)
    : sda_pin_(sda_pin), scl_pin_(scl_pin) {
    if (clock_hz == 0) {
        clock_hz = 100000;
    }
    uint32_t half = 500000UL / clock_hz;
    half_period_us_ = (half > 0) ? half : 1UL;
}

void SoftI2C::begin() {
    pinMode(scl_pin_, OUTPUT_OPEN_DRAIN);
    pinMode(sda_pin_, OUTPUT_OPEN_DRAIN);
    digitalWrite(scl_pin_, HIGH);
    digitalWrite(sda_pin_, HIGH);
    delayMicroseconds(half_period_us_);

    // Clock out up to 9 pulses if a slave is holding SDA low from an interrupted transaction
    if (digitalRead(sda_pin_) == LOW) {
        for (uint8_t i = 0; i < 9; ++i) {
            sclLow();
            delayMicroseconds(half_period_us_);
            if (!sclHigh()) {
                break;
            }
            delayMicroseconds(half_period_us_);
            if (digitalRead(sda_pin_) == HIGH) {
                break;
            }
        }
        stopCondition();
    }
}

bool SoftI2C::sclHigh() {
    digitalWrite(scl_pin_, HIGH);
    uint32_t start_us = micros();
    while (digitalRead(scl_pin_) == LOW) {
        if ((uint32_t)(micros() - start_us) >= CLOCK_STRETCH_TIMEOUT_US) {
            return false;
        }
    }
    return true;
}

void SoftI2C::sclLow() {
    digitalWrite(scl_pin_, LOW);
}

void SoftI2C::sdaHigh() {
    digitalWrite(sda_pin_, HIGH);
}

void SoftI2C::sdaLow() {
    digitalWrite(sda_pin_, LOW);
}

bool SoftI2C::startCondition() {
    sdaHigh();
    delayMicroseconds(half_period_us_);
    if (!sclHigh()) {
        return false;
    }
    delayMicroseconds(half_period_us_);
    sdaLow();
    delayMicroseconds(half_period_us_);
    sclLow();
    delayMicroseconds(half_period_us_);
    return true;
}

bool SoftI2C::stopCondition() {
    sdaLow();
    delayMicroseconds(half_period_us_);
    bool ok = sclHigh();
    delayMicroseconds(half_period_us_);
    sdaHigh();
    delayMicroseconds(half_period_us_);
    return ok;
}

bool SoftI2C::writeByte(uint8_t byte, bool& ack) {
    for (uint8_t bit = 0; bit < 8; ++bit) {
        if (byte & 0x80) {
            sdaHigh();
        } else {
            sdaLow();
        }
        delayMicroseconds(half_period_us_);
        if (!sclHigh()) {
            sdaHigh();
            return false;
        }
        delayMicroseconds(half_period_us_);
        sclLow();
        byte <<= 1;
    }

    // Release SDA and read ACK/NACK bit on 9th clock
    sdaHigh();
    delayMicroseconds(half_period_us_);
    if (!sclHigh()) {
        return false;
    }
    delayMicroseconds(half_period_us_);
    ack = (digitalRead(sda_pin_) == LOW);
    sclLow();
    delayMicroseconds(half_period_us_);
    return true;
}

bool SoftI2C::readByte(bool send_ack, uint8_t& byte) {
    uint8_t val = 0;
    sdaHigh();

    for (uint8_t bit = 0; bit < 8; ++bit) {
        val <<= 1;
        delayMicroseconds(half_period_us_);
        if (!sclHigh()) {
            return false;
        }
        delayMicroseconds(half_period_us_);
        if (digitalRead(sda_pin_) == HIGH) {
            val |= 0x01;
        }
        sclLow();
    }

    // Drive ACK (LOW) or NACK (HIGH) on 9th clock
    if (send_ack) {
        sdaLow();
    } else {
        sdaHigh();
    }
    delayMicroseconds(half_period_us_);
    if (!sclHigh()) {
        sdaHigh();
        return false;
    }
    delayMicroseconds(half_period_us_);
    sclLow();
    sdaHigh();
    delayMicroseconds(half_period_us_);

    byte = val;
    return true;
}

bool SoftI2C::probe(uint8_t addr7) {
    if (!startCondition()) {
        stopCondition();
        return false;
    }
    bool ack = false;
    bool ok = writeByte((uint8_t)(addr7 << 1), ack);
    stopCondition();
    return ok && ack;
}

bool SoftI2C::writeBytes(uint8_t addr7, uint8_t reg, const uint8_t* data, size_t len) {
    if (!startCondition()) {
        stopCondition();
        return false;
    }

    bool ack = false;
    if (!writeByte((uint8_t)(addr7 << 1), ack) || !ack) {
        stopCondition();
        return false;
    }

    if (!writeByte(reg, ack) || !ack) {
        stopCondition();
        return false;
    }

    for (size_t i = 0; i < len; ++i) {
        if (!writeByte(data[i], ack) || !ack) {
            stopCondition();
            return false;
        }
    }

    return stopCondition();
}

bool SoftI2C::writeRegister(uint8_t addr7, uint8_t reg, uint8_t val) {
    return writeBytes(addr7, reg, &val, 1);
}

bool SoftI2C::readBytes(uint8_t addr7, uint8_t reg, uint8_t* data, size_t len) {
    if (len == 0 || data == nullptr) {
        return false;
    }

    if (!startCondition()) {
        stopCondition();
        return false;
    }

    bool ack = false;
    if (!writeByte((uint8_t)(addr7 << 1), ack) || !ack) {
        stopCondition();
        return false;
    }

    if (!writeByte(reg, ack) || !ack) {
        stopCondition();
        return false;
    }

    // Repeated START for read phase
    if (!startCondition()) {
        stopCondition();
        return false;
    }

    if (!writeByte((uint8_t)((addr7 << 1) | 0x01), ack) || !ack) {
        stopCondition();
        return false;
    }

    for (size_t i = 0; i < len; ++i) {
        bool send_ack = (i + 1 < len);
        if (!readByte(send_ack, data[i])) {
            stopCondition();
            return false;
        }
    }

    return stopCondition();
}

bool SoftI2C::readRegister(uint8_t addr7, uint8_t reg, uint8_t& val) {
    return readBytes(addr7, reg, &val, 1);
}
