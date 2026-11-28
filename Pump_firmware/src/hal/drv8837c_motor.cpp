/*
 * Created by Lawrence R. Kincheloe III / Molecular Reality Corp (2026).
 * Dedicated to the public domain under CC0 1.0 Universal (CC0-1.0).
 * SPDX-License-Identifier: CC0-1.0
 */

#include "drv8837c_motor.h"
#include <math.h>

DRV8837CMotor::DRV8837CMotor(uint8_t pwm_pin, uint8_t dir_pin, float ul_per_rev)
    : pwm_pin_(pwm_pin), dir_pin_(dir_pin), ul_per_rev_(ul_per_rev),
      current_dir_(DIR_FORWARD), current_mode_(MODE_STOPPED),
      target_rate_ul_min_(0.0f), target_volume_ul_(0.0f),
      dispensed_ul_(0.0f), current_duty_(0.0f) {}

void DRV8837CMotor::begin() {
    pinMode(dir_pin_, OUTPUT);
    digitalWrite(dir_pin_, LOW); // IN2 = 0

    pinMode(pwm_pin_, OUTPUT);
    analogWriteResolution(MOTOR_PWM_RESOLUTION);
    analogWriteFrequency(MOTOR_PWM_FREQUENCY_HZ);
    analogWrite(pwm_pin_, 0); // IN1 = 0 -> (0,0) Coast

    current_dir_ = DIR_FORWARD;
    current_duty_ = 0.0f;
    current_mode_ = MODE_STOPPED;
}

void DRV8837CMotor::setDirection(Direction dir) {
    current_dir_ = dir;
    if (current_duty_ > 0.0f && isRunning()) {
        setPwmDuty(current_duty_);
    }
}

void DRV8837CMotor::setPwmDuty(float duty_pct) {
    if (!(duty_pct >= 0.0f)) duty_pct = 0.0f;
    if (duty_pct > 100.0f) duty_pct = 100.0f;
    current_duty_ = duty_pct;

    uint32_t val = (uint32_t)((duty_pct / 100.0f) * (float)PWM_MAX_COUNT);
    if (current_dir_ == DIR_FORWARD) {
        // DRV8837C Table 1: IN2=LOW, IN1=PWM -> Forward (1,0) / Coast (0,0)
        digitalWrite(dir_pin_, LOW);
        analogWrite(pwm_pin_, val);
    } else {
        // DRV8837C Table 1: IN2=HIGH, IN1=(MAX-PWM) -> Reverse (0,1) / Brake (1,1)
        digitalWrite(dir_pin_, HIGH);
        analogWrite(pwm_pin_, PWM_MAX_COUNT - val);
    }
}

void DRV8837CMotor::setFlowRate(float ul_per_min, Direction dir) {
    if (!(ul_per_min > 0.0f)) {
        stop();
        return;
    }

    float clamped_rate = fminf(ul_per_min, MAX_RPM * ul_per_rev_);
    current_dir_ = dir;
    target_rate_ul_min_ = clamped_rate;

    // Linear speed conversion based on displacement per rev:
    // RPM = Rate (uL/min) / (uL/rev)
    float rpm = clamped_rate / ul_per_rev_;
    float duty = (rpm / MAX_RPM) * 100.0f;

    // Minimum motor starting threshold ~ 15% duty
    if (duty > 0.0f && duty < 15.0f) {
        duty = 15.0f;
    }

    current_mode_ = MODE_CONTINUOUS;
    setPwmDuty(duty);
}

void DRV8837CMotor::dispenseVolume(float target_ul, float rate_ul_min) {
    if (!(target_ul > 0.0f)) {
        target_volume_ul_ = 0.0f;
        dispensed_ul_ = 0.0f;
        stop();
        return;
    }
    target_volume_ul_ = target_ul;
    dispensed_ul_ = 0.0f;
    setFlowRate(rate_ul_min, DIR_FORWARD);
    if (isRunning()) {
        current_mode_ = MODE_DISPENSE_VOLUME;
    }
}

void DRV8837CMotor::flush(Direction dir) {
    current_dir_ = dir;
    target_rate_ul_min_ = MAX_RPM * ul_per_rev_;
    current_mode_ = MODE_FLUSH;
    setPwmDuty(100.0f);
}

void DRV8837CMotor::stop() {
    // DRV8837C Table 1: (IN1=0, IN2=0) -> Coast (OUT1=Z, OUT2=Z)
    digitalWrite(dir_pin_, LOW);
    analogWrite(pwm_pin_, 0);
    current_duty_ = 0.0f;
    target_rate_ul_min_ = 0.0f;
    current_mode_ = MODE_STOPPED;
}

void DRV8837CMotor::emergencyStop() {
    // DRV8837C Table 1: (IN1=1, IN2=1, ~SLEEP=1) -> Active Brake (OUT1=L, OUT2=L)
    digitalWrite(dir_pin_, HIGH);
    analogWrite(pwm_pin_, PWM_MAX_COUNT);
    current_duty_ = 0.0f;
    target_rate_ul_min_ = 0.0f;
    current_mode_ = MODE_ESTOP;
}

void DRV8837CMotor::sleep() {
    // DRV8837C datasheet §8.2.2.2: set all inputs logic LOW before/when ~SLEEP goes LOW
    digitalWrite(dir_pin_, LOW);
    analogWrite(pwm_pin_, 0);
    current_duty_ = 0.0f;
    target_rate_ul_min_ = 0.0f;
    current_mode_ = MODE_ESTOP;
}

void DRV8837CMotor::update(uint32_t dt_ms) {
    if (current_mode_ == MODE_STOPPED || current_mode_ == MODE_ESTOP) {
        return;
    }

    // Integrate dispensed volume: dV = Rate (uL/min) * (dt_ms / 60000)
    float dv = target_rate_ul_min_ * ((float)dt_ms / 60000.0f);
    dispensed_ul_ += dv;

    if (current_mode_ == MODE_DISPENSE_VOLUME) {
        if (dispensed_ul_ >= target_volume_ul_) {
            stop();
        }
    }
}
