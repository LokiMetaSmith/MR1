/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#pragma once
#include <Arduino.h>
#include "soft_i2c.h"
#include "config.h"

/**
 * STMicroelectronics STUSB4500 Autonomous USB-PD Sink Controller Driver
 * Communicates over SW-I2C (PD_I2C: PB10 SCL / PB11 SDA) at 0x28.
 * Strictly caps VMOTOR <= 9V (DRV8837C 11V rec / 12V abs max); 12V/15V/20V are disallowed.
 */
class STUSB4500PD {
public:
    enum PDOContract {
        PDO_UNKNOWN = 0,
        PDO_5V      = 1,
        PDO_9V      = 2
    };

    enum RequestResult {
        REQ_NONE = 0,
        REQ_CONTRACT_ACTIVE,
        REQ_NO_PD_CONTRACT,
        REQ_DETACHED,
        REQ_INVALID_PROFILE,
        REQ_I2C_CLAMP_FAILED,
        REQ_SOFT_RESET_FAILED,
        REQ_RDO_READ_FAILED,
        REQ_OVERVOLTAGE
    };

    STUSB4500PD(SoftI2C& i2c, uint8_t i2c_addr = I2C_ADDR_STUSB4500);

    bool begin();
    bool requestProfile(PDOContract profile);
    PDOContract getActiveContract();
    float getVbusVoltageMv();
    uint8_t readAndClearAlerts();
    bool isAttached();
    bool isContractActive() const { return contract_active_; }
    bool isPdosClamped() const { return ram_clamped_; }
    bool isRamClamped() const { return ram_clamped_; }
    bool isRenegotiatedAfterClamp() const { return renegotiated_after_clamp_; }
    bool isOvervoltageContract() const { return overvoltage_contract_; }
    bool isRdoReadOk() const { return rdo_read_ok_; }
    RequestResult getLastRequestResult() const { return last_request_result_; }
    uint8_t getLastObjPos() const { return last_obj_pos_; }
    bool checkChipPdosClamped();
    uint8_t getDeviceId() const { return device_id_; }

private:
    SoftI2C& i2c_;
    uint8_t addr_;
    PDOContract active_pdo_;
    bool contract_active_;
    uint8_t device_id_;
    uint8_t last_obj_pos_;
    bool ram_clamped_;
    bool renegotiated_after_clamp_;
    bool overvoltage_contract_;
    bool rdo_read_ok_;
    RequestResult last_request_result_;

    bool readReg(uint8_t reg, uint8_t& val);
    bool writeReg(uint8_t reg, uint8_t val);
    bool enforceMax9VPdos(uint8_t pdo_count);

    static constexpr uint8_t REG_ALERT_STATUS_1            = 0x0B;
    static constexpr uint8_t REG_ALERT_STATUS_1_MASK       = 0x0C;
    static constexpr uint8_t REG_PORT_STATUS_0             = 0x0D;
    static constexpr uint8_t REG_PORT_STATUS_1             = 0x0E;
    static constexpr uint8_t REG_TYPEC_MONITORING_STATUS_0 = 0x0F;
    static constexpr uint8_t REG_CC_HW_FAULT_STATUS_0      = 0x12;
    static constexpr uint8_t REG_PRT_STATUS                = 0x16;
    static constexpr uint8_t REG_PD_COMMAND_CTRL           = 0x1A;
    static constexpr uint8_t REG_DEVICE_ID                 = 0x2F;
    static constexpr uint8_t REG_TX_HEADER_LOW             = 0x51;
    static constexpr uint8_t REG_DPM_PDO_NUMB              = 0x70;
    static constexpr uint8_t REG_DPM_SNK_PDO2              = 0x89; // 0x89..0x8C (LE 32-bit)
    static constexpr uint8_t REG_DPM_SNK_PDO3              = 0x8D; // 0x8D..0x90 (LE 32-bit)
    static constexpr uint8_t REG_RDO_REG_STATUS_3          = 0x94; // Bits [6:4] = Object_Pos [30:28]

    static constexpr uint8_t ALERT_PRT_STATUS              = (1u << 1);
    static constexpr uint8_t ALERT_CC_HW_FAULT             = (1u << 4);
    static constexpr uint8_t ALERT_TYPEC_MONITORING        = (1u << 5);
    static constexpr uint8_t ALERT_PORT_STATUS             = (1u << 6);
    // Unmask PORT_STATUS_AL (bit 6) and PRT_STATUS_AL (bit 1); mask reserved/PHY bits
    static constexpr uint8_t ALERT_MASK_PORT_AND_PRT       =
        (uint8_t)~(ALERT_PORT_STATUS | ALERT_PRT_STATUS);

    static constexpr uint8_t PD_HEADER_SOFT_RESET  = 0x0D;
    static constexpr uint8_t PD_CMD_SEND_COMMAND   = 0x26;
    static constexpr uint32_t PDO2_9V_1A5_VALUE    = 0x0002D096UL; // 9000 mV (180*50mV), 1500 mA (150*10mA)
};
