/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#include "sbu_link.h"
#include <math.h>
#include <string.h>
#include "stm32g4xx_hal.h"

SbuLink* SbuLink::instance_ = nullptr;

SbuLink::SbuLink(TwoWire& wire, uint8_t slave_addr, Stream* aux_serial)
    : wire_(wire), slave_addr_(slave_addr), aux_serial_(aux_serial),
      cmd_handler_(nullptr), connected_(false), last_rx_ms_(0),
      tx_reg_(0x00), estop_requested_(false),
      rx_head_(0), rx_tail_(0),
      aux_rx_state_(0), aux_rx_cmd_(0), aux_rx_param_(0), aux_rx_checksum_(0) {
    memset(&snapshot_, 0, sizeof(snapshot_));
    snapshot_.magic = 0xAA;
    recomputeSnapshotChecksum();
}

void SbuLink::onReceiveThunk(int numBytes) {
    if (instance_ != nullptr) {
        instance_->handleReceiveISR(numBytes);
    }
}

void SbuLink::onRequestThunk() {
    if (instance_ != nullptr) {
        instance_->handleRequestISR();
    }
}

void SbuLink::initSlaveInterface() {
    // CRITICAL (Wire.cpp:82): begin(addr) clears user_onRequest, so callbacks MUST be registered AFTER begin().
    wire_.begin(slave_addr_, false, false);
    wire_.onReceive(onReceiveThunk);
    wire_.onRequest(onRequestThunk);
}

void SbuLink::begin() {
    instance_ = this;
    connected_ = false;
    last_rx_ms_ = millis();
    tx_reg_ = 0x00;
    estop_requested_ = false;
    rx_head_ = 0;
    rx_tail_ = 0;

    initSlaveInterface();
}

void SbuLink::recomputeSnapshotChecksum() {
    const uint8_t* raw = reinterpret_cast<const uint8_t*>(&snapshot_);
    uint8_t cs = 0;
    for (size_t i = 0; i < sizeof(TelemetrySnapshot) - 1; ++i) {
        cs ^= raw[i];
    }
    snapshot_.checksum = cs;
}

void SbuLink::enqueueCommandISR(uint8_t cmd, uint16_t param) {
    uint8_t next = (uint8_t)((rx_head_ + 1U) % RX_QUEUE_CAP);
    if (next != rx_tail_) {
        rx_queue_[rx_head_].cmd = cmd;
        rx_queue_[rx_head_].param = param;
        rx_head_ = next;
    }
}

void SbuLink::handleReceiveISR(int numBytes) {
    (void)numBytes;
    uint8_t buf[32];
    uint8_t len = 0;

    // CRITICAL (Wire.cpp:419): drain ALL bytes in rxBuffer or future onReceive calls are dropped.
    while (wire_.available() > 0) {
        int val = wire_.read();
        if (val < 0) {
            break;
        }
        if (len < sizeof(buf)) {
            buf[len++] = (uint8_t)val;
        }
    }

    if (len == 0) {
        return;
    }

    if (len == 1) {
        // Register selector for subsequent master read
        tx_reg_ = buf[0];
        connected_ = true;
        last_rx_ms_ = millis();
        return;
    }

    if (len == sizeof(Packet) && buf[0] == 0xAA) {
        uint8_t expected = (uint8_t)(buf[0] ^ buf[1] ^ buf[2] ^ buf[3]);
        if (buf[4] == expected) {
            uint8_t cmd = buf[1];
            uint16_t param = (uint16_t)buf[2] | ((uint16_t)buf[3] << 8);
            tx_reg_ = 0x00;
            connected_ = true;
            last_rx_ms_ = millis();
            if (cmd == CMD_ESTOP || (cmd == CMD_LEGACY_ESTOP && param == 0xDEAD)) {
                estop_requested_ = true;
            }
            enqueueCommandISR(cmd, param);
        }
    }
}

void SbuLink::handleRequestISR() {
    // Copy pre-staged snapshot on stack (I2C_TXRX_BUFFER_SIZE = 32 bytes)
    TelemetrySnapshot snap;
    memcpy(&snap, &snapshot_, sizeof(snap));

    if (tx_reg_ == CMD_REPORT_PRESS) {
        // 6-byte pressure-only frame containing BOTH cis_psi and trans_psi (centi-psi LE)
        uint8_t p_buf[6];
        p_buf[0] = 0xAA;
        p_buf[1] = (uint8_t)(snap.cis_centi_psi & 0xFF);
        p_buf[2] = (uint8_t)((snap.cis_centi_psi >> 8) & 0xFF);
        p_buf[3] = (uint8_t)(snap.trans_centi_psi & 0xFF);
        p_buf[4] = (uint8_t)((snap.trans_centi_psi >> 8) & 0xFF);
        p_buf[5] = (uint8_t)(p_buf[0] ^ p_buf[1] ^ p_buf[2] ^ p_buf[3] ^ p_buf[4]);
        tx_reg_ = 0x00;
        wire_.write(p_buf, sizeof(p_buf));
        return;
    }

    wire_.write(reinterpret_cast<const uint8_t*>(&snap), sizeof(snap));
}

void SbuLink::sendPacket(uint8_t cmd, uint16_t param) {
    if (aux_serial_ == nullptr) {
        return;
    }

    Packet pkt;
    pkt.sof = 0xAA;
    pkt.cmd = cmd;
    pkt.param = param;
    pkt.checksum = (uint8_t)(pkt.sof ^ pkt.cmd ^ (param & 0xFF) ^ ((param >> 8) & 0xFF));

    // Non-blocking guard: never stall if USB CDC host is detached or USB_SEL_PASS == HIGH
    if (aux_serial_->availableForWrite() >= (int)sizeof(pkt)) {
        aux_serial_->write(reinterpret_cast<const uint8_t*>(&pkt), sizeof(pkt));
    }
}

void SbuLink::sendPressureTelemetry(float cis_psi, float trans_psi) {
    float cis_c = isfinite(cis_psi) ? constrain(cis_psi, -327.0f, 327.0f) : 0.0f;
    float trans_c = isfinite(trans_psi) ? constrain(trans_psi, -327.0f, 327.0f) : 0.0f;
    int16_t cis_cp = (int16_t)lroundf(cis_c * 100.0f);
    int16_t trans_cp = (int16_t)lroundf(trans_c * 100.0f);

    __disable_irq();
    snapshot_.cis_centi_psi = cis_cp;
    snapshot_.trans_centi_psi = trans_cp;
    recomputeSnapshotChecksum();
    __enable_irq();

    if (aux_serial_ != nullptr && aux_serial_->availableForWrite() >= (int)(sizeof(Packet) * 2)) {
        sendPacket(CMD_REPORT_PRESS, (uint16_t)cis_cp);
        sendPacket(CMD_REPORT_PRESS_TRANS, (uint16_t)trans_cp);
    }
}

void SbuLink::setStatusTelemetry(uint8_t status_flags, float pump1_rate_ul_min,
                                 float pump2_rate_ul_min, uint8_t fault_code) {
    float p1 = isfinite(pump1_rate_ul_min) ? constrain(pump1_rate_ul_min, 0.0f, 6553.0f) : 0.0f;
    float p2 = isfinite(pump2_rate_ul_min) ? constrain(pump2_rate_ul_min, 0.0f, 6553.0f) : 0.0f;
    uint16_t r1 = (uint16_t)lroundf(p1 * 10.0f);
    uint16_t r2 = (uint16_t)lroundf(p2 * 10.0f);

    __disable_irq();
    snapshot_.status_flags = status_flags;
    snapshot_.pump1_rate_x10 = r1;
    snapshot_.pump2_rate_x10 = r2;
    snapshot_.fault_code = fault_code;
    recomputeSnapshotChecksum();
    __enable_irq();
}

bool SbuLink::consumeEstopRequest() {
    __disable_irq();
    bool req = estop_requested_;
    estop_requested_ = false;
    __enable_irq();
    return req;
}

void SbuLink::update() {
    // Workaround for stm32duino twi.c:1523 bug (HAL_I2C_ErrorCallback checks obj->isMaster
    // instead of !obj->isMaster, leaving I2C3 out of LISTEN mode after a bus error such as
    // MR1_firmware probing swapped SBU polarity on a flipped USB-C cable).
    I2C_HandleTypeDef* hi2c = wire_.getHandle();
    if (hi2c != nullptr) {
        uint32_t err = HAL_I2C_GetError(hi2c);
        HAL_I2C_StateTypeDef state = HAL_I2C_GetState(hi2c);
        if (state == HAL_I2C_STATE_READY || err != HAL_I2C_ERROR_NONE) {
            __disable_irq();
            __HAL_I2C_CLEAR_FLAG(hi2c, I2C_FLAG_BERR | I2C_FLAG_ARLO | I2C_FLAG_OVR | I2C_FLAG_AF);
            hi2c->ErrorCode = HAL_I2C_ERROR_NONE;
            __enable_irq();
            if (HAL_I2C_GetState(hi2c) == HAL_I2C_STATE_READY) {
                if (HAL_I2C_EnableListen_IT(hi2c) != HAL_OK) {
                    initSlaveInterface();
                }
            }
        }
    }

    // Drain queued I2C commands in main-loop context
    while (true) {
        QueuedCommand item{0, 0};
        bool has_item = false;

        __disable_irq();
        if (rx_tail_ != rx_head_) {
            item.cmd = rx_queue_[rx_tail_].cmd;
            item.param = rx_queue_[rx_tail_].param;
            rx_tail_ = (uint8_t)((rx_tail_ + 1U) % RX_QUEUE_CAP);
            has_item = true;
        }
        __enable_irq();

        if (!has_item) {
            break;
        }
        if (cmd_handler_ != nullptr) {
            cmd_handler_(item.cmd, item.param);
        }
    }

    // Optional non-blocking auxiliary serial stream (USB CDC when USB_SEL_PASS == LOW)
    if (aux_serial_ != nullptr) {
        while (aux_serial_->available() > 0) {
            int ch = aux_serial_->read();
            if (ch < 0) {
                break;
            }
            processAuxByte((uint8_t)ch);
        }
    }

    // Timeout check
    uint32_t last_rx;
    __disable_irq();
    last_rx = last_rx_ms_;
    __enable_irq();
    if (millis() - last_rx > 1500UL) {
        connected_ = false;
    }
}

void SbuLink::processAuxByte(uint8_t b) {
    switch (aux_rx_state_) {
        case 0: // Waiting for SOF (0xAA)
            if (b == 0xAA) {
                aux_rx_state_ = 1;
            }
            break;

        case 1: // CMD byte
            aux_rx_cmd_ = b;
            aux_rx_state_ = 2;
            break;

        case 2: // PARAM LSB
            aux_rx_param_ = b;
            aux_rx_state_ = 3;
            break;

        case 3: // PARAM MSB
            aux_rx_param_ |= ((uint16_t)b << 8);
            aux_rx_state_ = 4;
            break;

        case 4: { // CHECKSUM byte
            aux_rx_checksum_ = b;
            uint8_t expected = (uint8_t)(0xAA ^ aux_rx_cmd_ ^ (aux_rx_param_ & 0xFF) ^ ((aux_rx_param_ >> 8) & 0xFF));
            if (aux_rx_checksum_ == expected) {
                connected_ = true;
                last_rx_ms_ = millis();
                if (cmd_handler_ != nullptr) {
                    cmd_handler_(aux_rx_cmd_, aux_rx_param_);
                }
            }
            aux_rx_state_ = 0;
            break;
        }

        default:
            aux_rx_state_ = 0;
            break;
    }
}
