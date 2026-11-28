/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#include "stusb4500_pd.h"
#include <string.h>

STUSB4500PD::STUSB4500PD(SoftI2C& i2c, uint8_t i2c_addr)
    : i2c_(i2c), addr_(i2c_addr), active_pdo_(PDO_UNKNOWN),
      contract_active_(false), device_id_(0), last_obj_pos_(0),
      ram_clamped_(false), renegotiated_after_clamp_(false),
      overvoltage_contract_(false), rdo_read_ok_(false),
      last_request_result_(REQ_NONE) {}

bool STUSB4500PD::readReg(uint8_t reg, uint8_t& val) {
    return i2c_.readRegister(addr_, reg, val);
}

bool STUSB4500PD::writeReg(uint8_t reg, uint8_t val) {
    return i2c_.writeRegister(addr_, reg, val);
}

bool STUSB4500PD::enforceMax9VPdos(uint8_t pdo_count) {
    ram_clamped_ = false;
    renegotiated_after_clamp_ = false;

    if (pdo_count < 1) {
        pdo_count = 1;
    }
    if (pdo_count > 2) {
        pdo_count = 2; // Strictly cap VMOTOR <= 9V (never PDO3 / 15V / 20V)
    }

    // Overwrite factory NVM PDO2 (15V) with 9V / 1.5A (0x0002D096, little-endian)
    const uint8_t pdo2_bytes[4] = {
        (uint8_t)(PDO2_9V_1A5_VALUE & 0xFF),
        (uint8_t)((PDO2_9V_1A5_VALUE >> 8) & 0xFF),
        (uint8_t)((PDO2_9V_1A5_VALUE >> 16) & 0xFF),
        (uint8_t)((PDO2_9V_1A5_VALUE >> 24) & 0xFF)
    };
    if (!i2c_.writeBytes(addr_, REG_DPM_SNK_PDO2, pdo2_bytes, sizeof(pdo2_bytes))) {
        return false;
    }

    // Zero out PDO3 in RAM so factory 20V NVM entry cannot be selected
    const uint8_t pdo3_zero[4] = {0x00, 0x00, 0x00, 0x00};
    if (!i2c_.writeBytes(addr_, REG_DPM_SNK_PDO3, pdo3_zero, sizeof(pdo3_zero))) {
        return false;
    }

    if (!writeReg(REG_DPM_PDO_NUMB, pdo_count)) {
        return false;
    }

    // Read back all three RAM PDO registers to confirm writes took effect
    uint8_t verify_num = 0;
    uint8_t verify_pdo2[4] = {0};
    uint8_t verify_pdo3[4] = {0};
    if (!readReg(REG_DPM_PDO_NUMB, verify_num) ||
        !i2c_.readBytes(addr_, REG_DPM_SNK_PDO2, verify_pdo2, sizeof(verify_pdo2)) ||
        !i2c_.readBytes(addr_, REG_DPM_SNK_PDO3, verify_pdo3, sizeof(verify_pdo3))) {
        return false;
    }

    if (verify_num != pdo_count ||
        memcmp(verify_pdo2, pdo2_bytes, sizeof(pdo2_bytes)) != 0 ||
        memcmp(verify_pdo3, pdo3_zero, sizeof(pdo3_zero)) != 0) {
        return false;
    }

    ram_clamped_ = true;
    return true;
}

bool STUSB4500PD::begin() {
    active_pdo_ = PDO_UNKNOWN;
    contract_active_ = false;
    last_obj_pos_ = 0;
    ram_clamped_ = false;
    renegotiated_after_clamp_ = false;
    overvoltage_contract_ = false;
    rdo_read_ok_ = false;
    last_request_result_ = REQ_NONE;

    uint8_t id = 0;
    if (!readReg(REG_DEVICE_ID, id) || id == 0x00 || id == 0xFF) {
        device_id_ = 0;
        return false;
    }
    device_id_ = id;

    // Immediately clamp RAM sink PDOs <= 9V before any further PD activity
    // (renegotiated_after_clamp_ stays false until SOFT_RESET completes)
    ram_clamped_ = enforceMax9VPdos(2);

    // Best-effort unmask PORT_STATUS_AL and PRT_STATUS_AL and clear stale alerts
    writeReg(REG_ALERT_STATUS_1_MASK, ALERT_MASK_PORT_AND_PRT);
    readAndClearAlerts();

    if (isAttached()) {
        getActiveContract();
        return true;
    }

    contract_active_ = false;
    active_pdo_ = PDO_UNKNOWN;
    last_obj_pos_ = 0;
    renegotiated_after_clamp_ = false;
    overvoltage_contract_ = false;
    rdo_read_ok_ = false;
    return false;
}

bool STUSB4500PD::checkChipPdosClamped() {
    uint8_t pdo_num = 0;
    if (!readReg(REG_DPM_PDO_NUMB, pdo_num) || pdo_num == 0 || pdo_num > 2) {
        ram_clamped_ = false;
        renegotiated_after_clamp_ = false;
        return false;
    }

    const uint8_t expected_pdo2[4] = {
        (uint8_t)(PDO2_9V_1A5_VALUE & 0xFF),
        (uint8_t)((PDO2_9V_1A5_VALUE >> 8) & 0xFF),
        (uint8_t)((PDO2_9V_1A5_VALUE >> 16) & 0xFF),
        (uint8_t)((PDO2_9V_1A5_VALUE >> 24) & 0xFF)
    };
    const uint8_t expected_pdo3[4] = {0x00, 0x00, 0x00, 0x00};

    uint8_t verify_pdo2[4] = {0};
    uint8_t verify_pdo3[4] = {0};
    if (!i2c_.readBytes(addr_, REG_DPM_SNK_PDO2, verify_pdo2, sizeof(verify_pdo2)) ||
        !i2c_.readBytes(addr_, REG_DPM_SNK_PDO3, verify_pdo3, sizeof(verify_pdo3)) ||
        memcmp(verify_pdo2, expected_pdo2, sizeof(expected_pdo2)) != 0 ||
        memcmp(verify_pdo3, expected_pdo3, sizeof(expected_pdo3)) != 0) {
        ram_clamped_ = false;
        renegotiated_after_clamp_ = false;
        return false;
    }

    return ram_clamped_;
}

bool STUSB4500PD::isAttached() {
    uint8_t port_status_1 = 0;
    if (!readReg(REG_PORT_STATUS_1, port_status_1)) {
        contract_active_ = false;
        active_pdo_ = PDO_UNKNOWN;
        last_obj_pos_ = 0;
        renegotiated_after_clamp_ = false;
        overvoltage_contract_ = false;
        rdo_read_ok_ = false;
        return false;
    }
    // Live PORT_STATUS_1 bit 0 = ATTACH
    bool attached = (port_status_1 & 0x01) != 0;
    if (!attached) {
        contract_active_ = false;
        active_pdo_ = PDO_UNKNOWN;
        last_obj_pos_ = 0;
        renegotiated_after_clamp_ = false;
        overvoltage_contract_ = false;
        rdo_read_ok_ = false;
    }
    return attached;
}

uint8_t STUSB4500PD::readAndClearAlerts() {
    uint8_t alert1 = 0;
    if (!readReg(REG_ALERT_STATUS_1, alert1)) {
        return 0;
    }
    uint8_t dummy = 0;
    readReg(REG_PORT_STATUS_0, dummy);
    if (alert1 & ALERT_TYPEC_MONITORING) {
        readReg(REG_TYPEC_MONITORING_STATUS_0, dummy);
    }
    if (alert1 & ALERT_CC_HW_FAULT) {
        readReg(REG_CC_HW_FAULT_STATUS_0, dummy);
    }
    if (alert1 & ALERT_PRT_STATUS) {
        readReg(REG_PRT_STATUS, dummy);
    }
    return alert1;
}

bool STUSB4500PD::requestProfile(PDOContract profile) {
    // Reject any profile outside {PDO_5V, PDO_9V} to enforce VMOTOR <= 9V
    if (profile != PDO_5V && profile != PDO_9V) {
        last_request_result_ = REQ_INVALID_PROFILE;
        return false;
    }

    renegotiated_after_clamp_ = false;
    uint8_t pdo_count = (profile == PDO_5V) ? 1 : 2;
    ram_clamped_ = enforceMax9VPdos(pdo_count);
    if (!ram_clamped_) {
        last_request_result_ = REQ_I2C_CLAMP_FAILED;
        getActiveContract();
        return false;
    }

    // Trigger USB-PD SOFT_RESET so source renegotiates against updated <=9V RAM PDOs
    if (!writeReg(REG_TX_HEADER_LOW, PD_HEADER_SOFT_RESET) ||
        !writeReg(REG_PD_COMMAND_CTRL, PD_CMD_SEND_COMMAND)) {
        renegotiated_after_clamp_ = false;
        last_request_result_ = REQ_SOFT_RESET_FAILED;
        getActiveContract();
        return false;
    }

    renegotiated_after_clamp_ = true;

    // Allow source Source_Capabilities -> Request -> Accept -> PS_RDY cycle to complete
    delay(100);
    readAndClearAlerts();

    if (!isAttached()) {
        last_request_result_ = REQ_DETACHED;
        return false;
    }

    PDOContract negotiated = getActiveContract();
    if (!rdo_read_ok_) {
        last_request_result_ = REQ_RDO_READ_FAILED;
        return false;
    }
    if (overvoltage_contract_) {
        last_request_result_ = REQ_OVERVOLTAGE;
        return false;
    }
    if (negotiated == PDO_5V || negotiated == PDO_9V) {
        contract_active_ = true;
        last_request_result_ = REQ_CONTRACT_ACTIVE;
        return true;
    }

    contract_active_ = false;
    last_request_result_ = REQ_NO_PD_CONTRACT;
    return false;
}

STUSB4500PD::PDOContract STUSB4500PD::getActiveContract() {
    uint8_t rdo3 = 0;
    if (!readReg(REG_RDO_REG_STATUS_3, rdo3)) {
        rdo_read_ok_ = false;
        active_pdo_ = PDO_UNKNOWN;
        contract_active_ = false;
        return active_pdo_;
    }

    rdo_read_ok_ = true;
    last_obj_pos_ = (rdo3 >> 4) & 0x07;
    switch (last_obj_pos_) {
        case 0:
            active_pdo_ = PDO_UNKNOWN;
            contract_active_ = false;
            overvoltage_contract_ = false;
            break;
        case 1:
            active_pdo_ = PDO_5V;
            contract_active_ = true;
            overvoltage_contract_ = false;
            break;
        case 2:
            if (ram_clamped_ && renegotiated_after_clamp_) {
                active_pdo_ = PDO_9V;
                contract_active_ = true;
                overvoltage_contract_ = false;
            } else {
                // Factory NVM PDO2 is 15V until RAM PDOs are clamped AND renegotiated
                active_pdo_ = PDO_UNKNOWN;
                contract_active_ = false;
                overvoltage_contract_ = true;
            }
            break;
        default:
            // Factory NVM PDO3 is 20V (or any out-of-range slot >= 3)
            active_pdo_ = PDO_UNKNOWN;
            contract_active_ = false;
            overvoltage_contract_ = true;
            break;
    }
    return active_pdo_;
}

float STUSB4500PD::getVbusVoltageMv() {
    if (overvoltage_contract_) {
        if (last_obj_pos_ == 2) {
            return 15000.0f;
        }
        return 20000.0f;
    }
    if (!contract_active_) {
        return 0.0f;
    }
    switch (active_pdo_) {
        case PDO_5V: return 5000.0f;
        case PDO_9V: return 9000.0f;
        default:     return 0.0f;
    }
}
