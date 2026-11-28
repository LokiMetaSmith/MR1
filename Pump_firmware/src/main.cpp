/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#include <Arduino.h>
#include <Wire.h>
#include "stm32g4xx_hal.h"
#include "pinout.h"
#include "config.h"
#include "hal/soft_i2c.h"
#include "hal/abp2_pressure.h"
#include "hal/drv8837c_motor.h"
#include "hal/stusb4500_pd.h"
#include "comm/sbu_link.h"

// Hardware & Bus Instances (3 completely isolated I2C buses)
// 1. PRESS_I2C: HW I2C1 (PA15 SCL / PB9 SDA)
ABP1Sensor sensorCis(Wire, I2C_ADDR_ABP1_CIS, 0.0f, 15.0f);
ABP1Sensor sensorTrans(Wire, I2C_ADDR_ABP1_TRANS, 0.0f, 5.0f);

// 2. Motor Drivers: DRV8837C on TIM2 (PA0/PA1 PWM, PB12/PB13 DIR, PB0 ~SLEEP)
DRV8837CMotor pumpCis(PIN_PUMP1_PWM, PIN_PUMP1_DIR, UL_PER_REVOLUTION);
DRV8837CMotor pumpTrans(PIN_PUMP2_PWM, PIN_PUMP2_DIR, UL_PER_REVOLUTION);

// 3. PD_I2C: SW-I2C (PB10 SCL / PB11 SDA -> U101 STUSB4500QTR @ 0x28)
SoftI2C pdWire(PIN_PD_I2C_SDA, PIN_PD_I2C_SCL, 100000);
STUSB4500PD pdController(pdWire, I2C_ADDR_STUSB4500);

// 4. SBU_I2C: HW I2C3 Slave @ 0x38 (PB5 SDA / PA8 SCL) + optional USB CDC Serial (PA11/PA12)
TwoWire sbuWire(PIN_SBU_I2C_SDA, PIN_SBU_I2C_SCL);
SbuLink sbuLink(sbuWire, I2C_ADDR_SBU_SLAVE, &Serial);

// Global State
bool g_estop_tripped = false;
bool g_overpressure_fault = false;
bool g_sensor_fault = false;
bool g_pd_overvoltage_fault = false;
bool g_pd_initialized = false;
uint8_t g_sensor_comm_errors = 0;

uint32_t g_last_pressure_ms = 0;
uint32_t g_last_telemetry_ms = 0;
uint32_t g_last_heartbeat_ms = 0;
uint32_t g_last_pd_check_ms = 0;
uint32_t g_last_loop_ms = 0;

static float clampCommandedFlow(uint16_t param) {
    if (param == 0) {
        return 0.0f;
    }
    return constrain((float)param, MIN_FLOW_RATE_UL_MIN, MAX_FLOW_RATE_UL_MIN);
}

static uint8_t buildStatusFlags() {
    uint8_t flags = 0;
    if (g_estop_tripped)                           flags |= SbuLink::FLAG_ESTOP;
    if (g_overpressure_fault)                      flags |= SbuLink::FLAG_OVERPRESSURE;
    if (g_sensor_fault || g_pd_overvoltage_fault)  flags |= SbuLink::FLAG_SENSOR_FAULT;
    if (!g_pd_overvoltage_fault && pdController.isContractActive()) flags |= SbuLink::FLAG_PD_READY;
    if (pumpCis.isRunning())                       flags |= SbuLink::FLAG_PUMP1_RUN;
    if (pumpTrans.isRunning())                     flags |= SbuLink::FLAG_PUMP2_RUN;
    return flags;
}

static uint8_t buildFaultCode() {
    uint8_t code = 0;
    if (g_estop_tripped)        code |= 0x01;
    if (g_overpressure_fault)   code |= 0x02;
    if (g_sensor_fault)         code |= 0x04;
    if (g_pd_overvoltage_fault) code |= 0x08;
    return code;
}

void triggerEmergencyStop() {
    bool already_tripped = g_estop_tripped;
    g_estop_tripped = true;
    // Active braking requires ~SLEEP (PB0) HIGH while IN1=1, IN2=1
    pumpCis.emergencyStop();
    pumpTrans.emergencyStop();
    digitalWrite(PIN_LED_FAULT, HIGH);
    if (!already_tripped) {
        sbuLink.sendPacket(SbuLink::CMD_ESTOP, 0x0001);
    }
}

void enterHardwareSleep() {
    // Follow DRV8837C §8.2.2.2: set IN1=0, IN2=0 before pulling ~SLEEP (PB0) LOW
    pumpCis.sleep();
    pumpTrans.sleep();
    digitalWrite(PIN_ESTOP_TRIGGER, LOW);
}

static bool isFaultAllowedToRun() {
    return !g_estop_tripped && !g_overpressure_fault && !g_sensor_fault && !g_pd_overvoltage_fault;
}

static bool checkPdSafetyFault() {
    if (pdController.isOvervoltageContract() ||
        pdController.getVbusVoltageMv() > (float)STUSB4500_MAX_VOLTAGE_MV) {
        return true;
    }
    if (g_pd_initialized) {
        if (!pdController.isPdosClamped() ||
            !pdController.isRenegotiatedAfterClamp() ||
            !pdController.isRdoReadOk()) {
            return true;
        }
    }
    return false;
}

static void updatePdReadyLed() {
    digitalWrite(PIN_LED_PD_READY,
                 (g_pd_initialized && !g_pd_overvoltage_fault && pdController.isContractActive())
                     ? HIGH
                     : LOW);
}

void handleSbuCommand(uint8_t cmd, uint16_t param) {
    switch (cmd) {
        case SbuLink::CMD_RUN_FWD:
            if (isFaultAllowedToRun()) {
                float rate = clampCommandedFlow(param);
                if (rate <= 0.0f) {
                    pumpCis.stop();
                } else {
                    pumpCis.setFlowRate(rate, DRV8837CMotor::DIR_FORWARD);
                }
            }
            break;

        case SbuLink::CMD_RUN_REV:
            if (isFaultAllowedToRun()) {
                float rate = clampCommandedFlow(param);
                if (rate <= 0.0f) {
                    pumpCis.stop();
                } else {
                    pumpCis.setFlowRate(rate, DRV8837CMotor::DIR_REVERSE);
                }
            }
            break;

        case SbuLink::CMD_SET_SPEED:
            if (isFaultAllowedToRun()) {
                float rate = clampCommandedFlow(param);
                if (rate <= 0.0f) {
                    pumpCis.stop();
                } else {
                    pumpCis.setFlowRate(rate, pumpCis.getDirection());
                }
            }
            break;

        case SbuLink::CMD_RUN_TRANS_FWD:
            if (isFaultAllowedToRun()) {
                float rate = clampCommandedFlow(param);
                if (rate <= 0.0f) {
                    pumpTrans.stop();
                } else {
                    pumpTrans.setFlowRate(rate, DRV8837CMotor::DIR_FORWARD);
                }
            }
            break;

        case SbuLink::CMD_RUN_TRANS_REV:
            if (isFaultAllowedToRun()) {
                float rate = clampCommandedFlow(param);
                if (rate <= 0.0f) {
                    pumpTrans.stop();
                } else {
                    pumpTrans.setFlowRate(rate, DRV8837CMotor::DIR_REVERSE);
                }
            }
            break;

        case SbuLink::CMD_SET_SPEED_TRANS:
            if (isFaultAllowedToRun()) {
                float rate = clampCommandedFlow(param);
                if (rate <= 0.0f) {
                    pumpTrans.stop();
                } else {
                    pumpTrans.setFlowRate(rate, pumpTrans.getDirection());
                }
            }
            break;

        case SbuLink::CMD_FLUSH_CIS:
            if (isFaultAllowedToRun()) {
                pumpCis.flush(param ? DRV8837CMotor::DIR_REVERSE : DRV8837CMotor::DIR_FORWARD);
            }
            break;

        case SbuLink::CMD_FLUSH_TRANS:
            if (isFaultAllowedToRun()) {
                pumpTrans.flush(param ? DRV8837CMotor::DIR_REVERSE : DRV8837CMotor::DIR_FORWARD);
            }
            break;

        case SbuLink::CMD_STOP_CIS:
            pumpCis.stop();
            break;

        case SbuLink::CMD_STOP_TRANS:
            pumpTrans.stop();
            break;

        case SbuLink::CMD_STOP:
            pumpCis.stop();
            pumpTrans.stop();
            break;

        case SbuLink::CMD_ESTOP:
            if (!g_estop_tripped) {
                triggerEmergencyStop();
            }
            break;

        case SbuLink::CMD_LEGACY_ESTOP:
            if (param == 0xDEAD && !g_estop_tripped) {
                triggerEmergencyStop();
            }
            break;

        case SbuLink::CMD_PING:
        case SbuLink::CMD_HEARTBEAT:
            sbuLink.sendPacket(cmd, 0);
            break;

        default:
            break;
    }
}

void setup() {
    // 0. Disable STM32G4 UCPD dead-battery Rd (~5.1k pull-down on PB6 / UCPD1_CC1)
    // before configuring PB6 as LED_FAULT output.
    __HAL_RCC_PWR_CLK_ENABLE();
    HAL_PWREx_DisableUCPDDeadBattery();

    // 1. Diagnostic LEDs (All 5x KT-0603G Green)
    pinMode(PIN_LED_FAULT, OUTPUT);
    pinMode(PIN_LED_PUMP1, OUTPUT);
    pinMode(PIN_LED_PUMP2, OUTPUT);
    pinMode(PIN_LED_PD_READY, OUTPUT);
    pinMode(PIN_LED_MR1_5V, OUTPUT);

    digitalWrite(PIN_LED_FAULT, LOW);
    digitalWrite(PIN_LED_PUMP1, LOW);
    digitalWrite(PIN_LED_PUMP2, LOW);
    digitalWrite(PIN_LED_PD_READY, LOW);
    digitalWrite(PIN_LED_MR1_5V, LOW);

    // 2. Power enables & USB Mux
    pinMode(PIN_MR1_PWR_EN, OUTPUT);
    pinMode(PIN_USB_SEL_PASS, OUTPUT);
    digitalWrite(PIN_MR1_PWR_EN, HIGH);    // Enable +5V_MR1_CLEAN buck rail
    digitalWrite(PIN_USB_SEL_PASS, HIGH);  // Route J7 USB D+/D- to J6 MR1 by default
    digitalWrite(PIN_LED_MR1_5V, HIGH);

    // 3. Alert / Data-Ready Inputs
    pinMode(PIN_PD_ALERT, INPUT);          // External 10k pull-up R102
    pinMode(PIN_PRESS_ALERT, INPUT);       // U301 INT active-HIGH data-ready

    // 4. DRV8837C ~SLEEP Control (PB0): Drive OUTPUT HIGH (never INPUT_PULLUP,
    // which creates a divider against two 100k internal pulldowns near V_IH=1.65V).
    pinMode(PIN_ESTOP_TRIGGER, OUTPUT);
    digitalWrite(PIN_ESTOP_TRIGGER, HIGH);
    delayMicroseconds(50);                 // DRV8837C t_wake >= 30 us

    // 5. Optional USB CDC Serial (active on PA11/PA12 when USB_SEL_PASS == LOW)
    Serial.begin(115200);

    // 6. Initialize PRESS_I2C (HW I2C1 on PA15 SCL / PB9 SDA)
    Wire.setSCL(PIN_PRESS_I2C_SCL);
    Wire.setSDA(PIN_PRESS_I2C_SDA);
    Wire.begin();
    Wire.setClock(400000); // 400 kHz Fast I2C (within Honeywell ABP1 100..400 kHz spec)

    bool cis_ok = sensorCis.begin();
    bool trans_ok = sensorTrans.begin();
    if (!cis_ok || !trans_ok) {
        g_sensor_fault = true;
        digitalWrite(PIN_LED_FAULT, HIGH);
    }

    // 7. Initialize PD_I2C (SW-I2C on PB10 SCL / PB11 SDA) and cap VMOTOR <= 9V
    pdWire.begin();
    if (pdController.begin()) {
        g_pd_initialized = true;
        pdController.requestProfile(STUSB4500PD::PDO_9V);
        if (pdController.isAttached()) {
            pdController.getActiveContract();
        } else {
            g_pd_initialized = false;
        }
        if (checkPdSafetyFault()) {
            g_pd_overvoltage_fault = true;
        }
    }
    updatePdReadyLed();

    // 8. Initialize Motors (20 kHz 12-bit PWM on TIM2 PA0/PA1)
    pumpCis.begin();
    pumpTrans.begin();

    // 9. Initialize SBU_I2C (HW I2C3 Slave @ 0x38 on PA8 SCL / PB5 SDA)
    sbuLink.setCommandHandler(handleSbuCommand);
    sbuLink.begin();

    if (g_pd_overvoltage_fault) {
        triggerEmergencyStop();
    }

    g_last_loop_ms = millis();
    g_last_pd_check_ms = g_last_loop_ms;

    sbuLink.setStatusTelemetry(buildStatusFlags(),
                               pumpCis.getTargetRate(),
                               pumpTrans.getTargetRate(),
                               buildFaultCode());
}

void loop() {
    uint32_t now = millis();
    uint32_t dt_ms = now - g_last_loop_ms;
    g_last_loop_ms = now;

    // 1. Service SBU I2C3 Slave & Command Queue (handle ISR ESTOP once before queue drain)
    if (sbuLink.consumeEstopRequest()) {
        triggerEmergencyStop();
    }
    sbuLink.update();

    // 2. Service STUSB4500 ALERT_ (PB1, active LOW) & unconditional 250 ms health check
    bool pd_alert = (digitalRead(PIN_PD_ALERT) == LOW);
    bool pd_periodic = (now - g_last_pd_check_ms >= 250UL);
    if (pd_alert || pd_periodic) {
        if (pd_periodic) {
            g_last_pd_check_ms = now;
        }
        if (g_pd_initialized && !pdController.isAttached()) {
            g_pd_initialized = false;
        }
        bool brownout_ov = false;
        if (g_pd_initialized) {
            if (!pdController.checkChipPdosClamped()) {
                pdController.getActiveContract();
                if (pdController.isOvervoltageContract() ||
                    pdController.getVbusVoltageMv() > (float)STUSB4500_MAX_VOLTAGE_MV) {
                    brownout_ov = true;
                }
            }
        }
        bool need_clamp = (!g_pd_initialized ||
                           !pdController.isPdosClamped() ||
                           !pdController.isRenegotiatedAfterClamp());
        if (!g_pd_initialized) {
            if (pdController.begin()) {
                g_pd_initialized = true;
                need_clamp = true;
            }
        }
        if (!g_pd_overvoltage_fault && g_pd_initialized && need_clamp) {
            pdController.requestProfile(STUSB4500PD::PDO_9V);
            if (!pdController.isAttached()) {
                g_pd_initialized = false;
            }
        }
        if (g_pd_initialized) {
            pdController.readAndClearAlerts();
            pdController.getActiveContract();
            if (brownout_ov || checkPdSafetyFault()) {
                g_pd_overvoltage_fault = true;
                triggerEmergencyStop();
            }
        } else if (brownout_ov ||
                   pdController.isOvervoltageContract() ||
                   pdController.getVbusVoltageMv() > (float)STUSB4500_MAX_VOLTAGE_MV) {
            g_pd_overvoltage_fault = true;
            triggerEmergencyStop();
        }
        updatePdReadyLed();
    }

    // 3. Pressure Monitoring Loop (100 Hz)
    if (now - g_last_pressure_ms >= (1000UL / PRESSURE_SAMPLE_RATE_HZ)) {
        g_last_pressure_ms = now;

        ABP1Sensor::Status stCis = sensorCis.read();
        ABP1Sensor::Status stTrans = sensorTrans.read();

        bool cis_valid = (stCis == ABP1Sensor::STATUS_OK || stCis == ABP1Sensor::STATUS_STALE_DATA);
        bool trans_valid = (stTrans == ABP1Sensor::STATUS_OK || stTrans == ABP1Sensor::STATUS_STALE_DATA);

        if (!cis_valid || !trans_valid) {
            if (stCis == ABP1Sensor::STATUS_DIAGNOSTIC || stTrans == ABP1Sensor::STATUS_DIAGNOSTIC ||
                stCis == ABP1Sensor::STATUS_COMMAND_MODE || stTrans == ABP1Sensor::STATUS_COMMAND_MODE) {
                g_sensor_fault = true;
            } else {
                if (g_sensor_comm_errors < 255) {
                    ++g_sensor_comm_errors;
                }
                if (g_sensor_comm_errors >= 3) {
                    g_sensor_fault = true;
                }
            }
            if (g_sensor_fault) {
                pumpCis.emergencyStop();
                pumpTrans.emergencyStop();
                digitalWrite(PIN_LED_FAULT, HIGH);
            }
        } else {
            g_sensor_comm_errors = 0;

            float p_cis = sensorCis.getPressurePsi();
            float p_trans = sensorTrans.getPressurePsi();

            // Safety overpressure check
            if (p_cis > MAX_PRESSURE_CIS_PSI || p_trans > MAX_PRESSURE_TRANS_PSI) {
                bool was_overpressure = g_overpressure_fault;
                g_overpressure_fault = true;
                pumpCis.emergencyStop();
                pumpTrans.emergencyStop();
                digitalWrite(PIN_LED_FAULT, HIGH);
                if (!was_overpressure) {
                    sbuLink.sendPacket(SbuLink::CMD_ESTOP, 0x0001);
                }
            }
        }
    }

    // 4. Motor Updates & LEDs
    pumpCis.update(dt_ms);
    pumpTrans.update(dt_ms);

    digitalWrite(PIN_LED_PUMP1, pumpCis.isRunning() ? HIGH : LOW);
    digitalWrite(PIN_LED_PUMP2, pumpTrans.isRunning() ? HIGH : LOW);

    // 5. SBU Telemetry Snapshot & Auxiliary Stream Transmission (20 Hz)
    if (now - g_last_telemetry_ms >= (1000UL / TELEMETRY_BROADCAST_HZ)) {
        g_last_telemetry_ms = now;
        sbuLink.setStatusTelemetry(buildStatusFlags(),
                                   pumpCis.getTargetRate(),
                                   pumpTrans.getTargetRate(),
                                   buildFaultCode());
        sbuLink.sendPressureTelemetry(sensorCis.getPressurePsi(), sensorTrans.getPressurePsi());
    }

    // 6. Heartbeat & LED Fault Indicator
    if (now - g_last_heartbeat_ms >= 500) {
        g_last_heartbeat_ms = now;
        if (g_estop_tripped || g_overpressure_fault || g_sensor_fault || g_pd_overvoltage_fault) {
            digitalWrite(PIN_LED_FAULT, !digitalRead(PIN_LED_FAULT));
        } else {
            digitalWrite(PIN_LED_FAULT, LOW);
        }
    }
}
