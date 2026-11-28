/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#pragma once
#include <Arduino.h>
#include <Wire.h>
#include "config.h"

/**
 * Pump Controller SBU I2C3 Slave Link Handler (0x38) + Optional Auxiliary Stream (USB CDC)
 * Communicates with MR1 Reader over USB-C SBU1/SBU2 (PA8 SCL / PB5 SDA) at 100 kHz.
 */
class SbuLink {
public:
    struct Packet {
        uint8_t  sof;
        uint8_t  cmd;
        uint16_t param;
        uint8_t  checksum;
    } __attribute__((packed));

    // 12-byte I2C Slave Telemetry Snapshot (<= 32-byte twi I2C_TXRX_BUFFER_SIZE)
    struct TelemetrySnapshot {
        uint8_t  magic;           // 0xAA
        uint8_t  status_flags;    // bit0:ESTOP, bit1:OVERPRESS, bit2:SENSOR_FLT, bit3:PD_OK, bit4:P1_RUN, bit5:P2_RUN
        int16_t  cis_centi_psi;   // Signed centi-psi (LE)
        int16_t  trans_centi_psi; // Signed centi-psi (LE)
        uint16_t pump1_rate_x10;  // Pump 1 flow rate in 0.1 uL/min (LE)
        uint16_t pump2_rate_x10;  // Pump 2 flow rate in 0.1 uL/min (LE)
        uint8_t  fault_code;      // Non-zero fault code
        uint8_t  checksum;        // XOR of bytes 0..10
    } __attribute__((packed));

    enum Command : uint8_t {
        CMD_PING               = 0x00,
        CMD_RUN_FWD            = 0x01,
        CMD_STOP               = 0x02,
        CMD_ESTOP              = 0x03,
        CMD_RUN_REV            = 0x04,
        CMD_SET_SPEED          = 0x05,
        CMD_HEARTBEAT          = 0x06,
        CMD_RUN_TRANS_FWD      = 0x07,
        CMD_RUN_TRANS_REV      = 0x08,
        CMD_STOP_TRANS         = 0x09,
        CMD_SET_SPEED_TRANS    = 0x0A,
        CMD_FLUSH_CIS          = 0x0B,
        CMD_FLUSH_TRANS        = 0x0C,
        CMD_STOP_CIS           = 0x0D,
        CMD_TELEMETRY          = 0x10,
        CMD_REPORT_PRESS       = 0x11,
        CMD_REPORT_PRESS_TRANS = 0x12,
        CMD_LEGACY_ESTOP       = 0xFF
    };

    enum StatusFlag : uint8_t {
        FLAG_ESTOP        = (1U << 0),
        FLAG_OVERPRESSURE = (1U << 1),
        FLAG_SENSOR_FAULT = (1U << 2),
        FLAG_PD_READY     = (1U << 3),
        FLAG_PUMP1_RUN    = (1U << 4),
        FLAG_PUMP2_RUN    = (1U << 5)
    };

    typedef void (*CommandHandler)(uint8_t cmd, uint16_t param);

    SbuLink(TwoWire& wire, uint8_t slave_addr = I2C_ADDR_SBU_SLAVE, Stream* aux_serial = nullptr);

    void begin();
    void setCommandHandler(CommandHandler handler) { cmd_handler_ = handler; }
    void update();

    void sendPacket(uint8_t cmd, uint16_t param);
    void sendPressureTelemetry(float cis_psi, float trans_psi);
    void setStatusTelemetry(uint8_t status_flags, float pump1_rate_ul_min,
                            float pump2_rate_ul_min, uint8_t fault_code);

    bool consumeEstopRequest();
    bool isConnected() const { return connected_; }
    uint32_t getLastPacketTimeMs() const { return last_rx_ms_; }

private:
    struct QueuedCommand {
        uint8_t  cmd;
        uint16_t param;
    };

    static constexpr uint8_t RX_QUEUE_CAP = 8;

    TwoWire& wire_;
    uint8_t slave_addr_;
    Stream* aux_serial_;
    CommandHandler cmd_handler_;
    volatile bool connected_;
    volatile uint32_t last_rx_ms_;
    volatile uint8_t tx_reg_;
    volatile bool estop_requested_;

    TelemetrySnapshot snapshot_;
    volatile QueuedCommand rx_queue_[RX_QUEUE_CAP];
    volatile uint8_t rx_head_;
    volatile uint8_t rx_tail_;

    // Auxiliary stream parser state machine
    uint8_t aux_rx_state_;
    uint8_t aux_rx_cmd_;
    uint16_t aux_rx_param_;
    uint8_t aux_rx_checksum_;

    static SbuLink* instance_;
    static void onReceiveThunk(int numBytes);
    static void onRequestThunk();

    void initSlaveInterface();
    void handleReceiveISR(int numBytes);
    void handleRequestISR();
    void enqueueCommandISR(uint8_t cmd, uint16_t param);
    void recomputeSnapshotChecksum();
    void processAuxByte(uint8_t b);
};
