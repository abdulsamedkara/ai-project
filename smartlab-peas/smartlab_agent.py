"""
AI-Based SmartLab Security & Assistant System using PEAS Framework
===================================================================
Teaching simulation of an intelligent agent for laboratory security
using the PEAS model.

PEAS Mapping:
- Performance : Correct threat detection, low false alarms, fast response,
                user identification accuracy
- Environment : University laboratory with authorized/unauthorized users,
                smoke, temperature, motion, flame, vibration, light
- Actuators   : Fan (PWM), TFT Display, Speaker (alerts), LED Strip,
                Web UI Notification
- Sensors     : RFID reader, MQ135 smoke, DHT11 temp/humidity, PIR motion,
                Flame sensor, SW-420 vibration, LDR light

Algorithm Flow:
  Initialize → Perceive → Preprocess → Analyze → Decide → Act → Learn

Real Hardware: ESP32-S3 N16R8 (SmartLab Assistant — IoT project)

Students: Abdül Samed Kara  (211401065)
          Mert Abdullahoğlu (221401005)
Course  : Artificial Intelligence — RTEU Computer Engineering
"""

import random
import time
import sys
import io
import json
import math
import os
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── ESP32 config — update if DHCP IP changes ────────────────────────────────
# ESP32, HTTP sunucusu olarak çalışır; Python doğrudan buraya bağlanır.
# Endpoints: GET /sensors  GET /status  POST /fan  POST /led
ESP32_HOST         = "10.162.138.1"   # ESP32'nin WiFi IP'si
LEARNED_STATE_FILE = "learned_state.json"


# ─────────────────────────────────────────────
# ENVIRONMENT (E)
# ─────────────────────────────────────────────

class LabEnvironment:
    """
    Represents the university laboratory environment.

    Characteristics:
      - Partially observable : not all events visible at all times
      - Dynamic              : conditions change continuously
      - Stochastic           : uncertainty in sensor readings
      - Real-time            : requires immediate decision-making
    """

    AUTHORIZED_USERS = ["Abdulsamed Kara", "Mert Abdullahoglu", "Prof. Yilmaz"]

    def __init__(self):
        self.entities     = ["authorized_user", "unauthorized_user", "none"]
        self.smoke_levels = ["clean", "moderate", "dangerous"]
        self.temp_levels  = ["normal", "high"]
        self.light_levels = ["bright", "dim", "dark"]

    def get_state(self):
        """Simulate real-time lab environment state."""
        entity = random.choice(self.entities)
        user_name = (
            random.choice(self.AUTHORIZED_USERS) if entity == "authorized_user"
            else ("Unknown Person" if entity == "unauthorized_user" else "None")
        )
        return {
            "entity"      : entity,
            "user_name"   : user_name,
            "smoke_level" : random.choice(self.smoke_levels),
            "temperature" : random.choice(self.temp_levels),
            "flame"       : random.choices([True, False], weights=[1, 9])[0],
            "vibration"   : random.choice([True, False]),
            "light_level" : random.choice(self.light_levels),
        }


# ─────────────────────────────────────────────
# SENSORS (S)
# ─────────────────────────────────────────────

class Sensors:
    """
    Step 2 — PERCEIVE: Collects raw data from lab environment.

    Real hardware sensors (ESP32-S3):
      - MFRC522 RFID reader      -> user identity (biometric)
      - MQ135 gas/smoke (ADC)    -> smoke concentration
      - DHT11                    -> temperature & humidity
      - PIR HC-SR501             -> motion detection
      - Flame sensor (digital)   -> fire detection
      - SW-420 vibration         -> physical disturbance
      - LDR (ADC)                -> ambient light level
    """

    def sense(self, env_state):
        """Perceive environment and return raw sensor readings."""
        return {
            "rfid_raw"    : env_state["entity"],
            "user_name"   : env_state["user_name"],
            "smoke_adc"   : {"clean": 400, "moderate": 1100, "dangerous": 2200}
                            [env_state["smoke_level"]] + random.randint(-50, 50),
            "temperature_c": 28.5 if env_state["temperature"] == "high" else 22.0
                            + random.uniform(-0.5, 0.5),
            "flame_raw"   : env_state["flame"],
            "vibration"   : env_state["vibration"],
            "light_adc"   : {"bright": 3200, "dim": 2000, "dark": 800}
                            [env_state["light_level"]] + random.randint(-30, 30),
            "light_level" : env_state["light_level"],
        }


# ─────────────────────────────────────────────
# REAL SENSORS — fetches live data directly from ESP32
# ─────────────────────────────────────────────

class RealSensors:
    """
    Step 2 — PERCEIVE (Real Hardware Mode):
    Fetches live sensor data directly from the ESP32 HTTP server.
    No intermediate server — Python talks straight to the device.

    Endpoints used:
      GET /sensors  → {temperature, humidity, smoke, ldr, pir, flame, vib}
      GET /status   → {username, rfid_scanned}

    RFID identity:
      username == "Misafir"        → no card scanned  → none
      username starts "Bilinmeyen" → unknown card      → unauthorized_user
      otherwise                   → known card        → authorized_user

    Falls back to simulation if ESP32 is unreachable.
    """

    LDR_BRIGHT = 3000
    LDR_DIM    = 1500

    def __init__(self, host=ESP32_HOST):
        self.base_url = f"http://{host}"
        self._sim     = Sensors()
        self._sim_env = LabEnvironment()

    def _get(self, path, timeout=2):
        url = f"{self.base_url}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def sense(self, env_state=None):
        """
        Fetch live sensor data directly from ESP32.
        Returns same dict structure as Sensors.sense() plus '_source' key.
        """
        try:
            sensors = self._get("/sensors")
            status  = self._get("/status")

            username     = status.get("username", "Misafir")
            rfid_scanned = status.get("rfid_scanned", False)

            if not rfid_scanned or username == "Misafir":
                rfid_raw = "none"
            elif username.startswith("Bilinmeyen"):
                rfid_raw = "unauthorized_user"
            else:
                rfid_raw = "authorized_user"

            # flame sensor is active LOW: 0 = fire detected
            flame = (sensors.get("flame", 1) == 0)

            ldr = sensors.get("ldr", 2000)
            light_level = (
                "bright" if ldr > self.LDR_BRIGHT else
                "dim"    if ldr > self.LDR_DIM    else
                "dark"
            )

            return {
                "rfid_raw"     : rfid_raw,
                "user_name"    : username,
                "smoke_adc"    : sensors.get("smoke", 400),
                "temperature_c": float(sensors.get("temperature") or 22.0),
                "flame_raw"    : flame,
                "vibration"    : sensors.get("vib", 0) == 1,
                "light_adc"    : ldr,
                "light_level"  : light_level,
                "_source"      : "real",
            }

        except Exception as e:
            return self._fallback(str(e))

    def _fallback(self, reason=""):
        """Simulation fallback when ESP32 is unreachable."""
        raw = self._sim.sense(self._sim_env.get_state())
        raw["_source"] = f"simulated (fallback: {reason})"
        return raw


# ─────────────────────────────────────────────
# EMA LEARNER — Adaptive threshold learning
# ─────────────────────────────────────────────

class EMALearner:
    """
    Step 7 — LEARN: Exponential Moving Average based adaptive threshold learner.

    Learns the 'normal' baseline and variance for smoke and temperature
    from real observations. Thresholds are set at mean + N*std to detect
    anomalies relative to the current environment.

    Persists learned state to JSON so knowledge survives restarts.

    Why EMA instead of simple mean:
      - Adapts to gradual drift (e.g. colder season, dustier lab)
      - Recent samples matter more than old ones
      - No external libraries needed
    """

    ALPHA = 0.05   # learning rate: 0.05 → ~20 steps to adapt 63% to new level
    N_MOD = 2.0    # sigma multiplier for moderate smoke threshold
    N_DAN = 4.0    # sigma multiplier for dangerous smoke threshold
    N_TEMP = 2.0   # sigma multiplier for high temperature threshold

    # Safety floors — thresholds never drop below these values
    MIN_SMOKE_MOD  = 800
    MIN_SMOKE_DAN  = 1500
    MIN_TEMP_HIGH  = 27.0

    def __init__(self):
        self.means = {
            "smoke"       : 400.0,
            "temperature" : 22.0,
        }
        self.variances = {
            "smoke"       : 10000.0,  # initial std ≈ 100 ADC
            "temperature" : 4.0,      # initial std ≈ 2 °C
        }
        self.thresholds = {}
        self._update_thresholds()

    def update(self, smoke_adc, temperature_c):
        """Update EMA means and variances with new sensor readings."""
        for key, val in [("smoke", smoke_adc), ("temperature", temperature_c)]:
            old_mean = self.means[key]
            self.means[key] = (1 - self.ALPHA) * old_mean + self.ALPHA * val
            self.variances[key] = (
                (1 - self.ALPHA) * self.variances[key]
                + self.ALPHA * (val - old_mean) ** 2
            )
        self._update_thresholds()

    def _update_thresholds(self):
        smoke_std = math.sqrt(max(0.0, self.variances["smoke"]))
        temp_std  = math.sqrt(max(0.0, self.variances["temperature"]))
        self.thresholds["smoke_moderate"]  = max(
            self.MIN_SMOKE_MOD, self.means["smoke"] + self.N_MOD * smoke_std)
        self.thresholds["smoke_dangerous"] = max(
            self.MIN_SMOKE_DAN, self.means["smoke"] + self.N_DAN * smoke_std)
        self.thresholds["temp_high"]       = max(
            self.MIN_TEMP_HIGH, self.means["temperature"] + self.N_TEMP * temp_std)

    def save(self, path):
        """Persist learned state to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"means": self.means, "variances": self.variances}, f, indent=2)

    def load(self, path):
        """Load previously learned state from JSON file."""
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.means     = data.get("means", self.means)
            self.variances = data.get("variances", self.variances)
            self._update_thresholds()
        except Exception:
            pass  # keep defaults if file is corrupt


# ─────────────────────────────────────────────
# PREPROCESSOR
# ─────────────────────────────────────────────

class Preprocessor:
    """
    Step 3 — PREPROCESS: Cleans and normalizes raw sensor data.

    Operations:
      - Clamp ADC values to valid range (0–4095)
      - Apply noise floor filter to smoke ADC
      - Normalize temperature to Celsius
      - Debounce motion and flame readings

    If an EMALearner is provided, smoke and temperature thresholds
    are taken from its learned values instead of static defaults.
    """

    SMOKE_NOISE_FLOOR = 300    # below this = sensor noise, treat as clean
    SMOKE_MOD_THRESH  = 800    # static fallback: moderate smoke threshold
    SMOKE_DAN_THRESH  = 1500   # static fallback: dangerous smoke threshold
    TEMP_HIGH_THRESH  = 27.0   # static fallback: fan trigger temperature (°C)

    def process(self, raw, learner=None):
        """Clean and normalize raw sensor readings.

        Args:
            raw     : dict from Sensors.sense() or RealSensors.sense()
            learner : EMALearner instance — uses learned thresholds when provided
        """
        smoke_adc = max(0, min(4095, raw["smoke_adc"]))
        if smoke_adc < self.SMOKE_NOISE_FLOOR:
            smoke_adc = 0

        if learner is not None:
            mod_thresh  = learner.thresholds["smoke_moderate"]
            dan_thresh  = learner.thresholds["smoke_dangerous"]
            temp_thresh = learner.thresholds["temp_high"]
        else:
            mod_thresh  = self.SMOKE_MOD_THRESH
            dan_thresh  = self.SMOKE_DAN_THRESH
            temp_thresh = self.TEMP_HIGH_THRESH

        return {
            "rfid_identity"  : raw["rfid_raw"],
            "user_name"      : raw["user_name"],
            "smoke_adc"      : smoke_adc,
            "smoke_level"    : (
                "dangerous" if smoke_adc >= dan_thresh else
                "moderate"  if smoke_adc >= mod_thresh else
                "clean"
            ),
            "temperature_c"  : round(raw["temperature_c"], 1),
            "temp_high"      : raw["temperature_c"] >= temp_thresh,
            "flame"          : raw["flame_raw"],
            "vibration"      : raw["vibration"],
            "light_adc"      : max(0, min(4095, raw["light_adc"])),
            "light_level"    : raw["light_level"],
        }


# ─────────────────────────────────────────────
# ANALYZER
# ─────────────────────────────────────────────

class Analyzer:
    """
    Step 4 — ANALYZE: Classifies processed sensor data into meaningful events.

    Classifications:
      - Identity   : authorized / unauthorized / unknown
      - Smoke      : safe / warning / critical
      - Thermal    : normal / high_temperature
      - Security   : safe / suspicious / intrusion
      - Environment: stable / unstable
    """

    def analyze(self, processed):
        """Classify sensor data into events for decision making."""
        identity_class = processed["rfid_identity"]
        smoke_class    = processed["smoke_level"]
        thermal_class  = "high_temperature" if processed["temp_high"] else "normal"

        if processed["flame"]:
            security_class = "fire_emergency"
        elif identity_class == "unauthorized_user":
            security_class = "intrusion"
        elif smoke_class == "dangerous":
            security_class = "hazard"
        else:
            security_class = "safe"

        env_class = (
            "unstable" if processed["vibration"] or processed["flame"]
            else "stable"
        )

        return {
            "identity_class" : identity_class,
            "user_name"      : processed["user_name"],
            "smoke_class"    : smoke_class,
            "thermal_class"  : thermal_class,
            "security_class" : security_class,
            "env_class"      : env_class,
            "flame"          : processed["flame"],
            "light_level"    : processed["light_level"],
            "temp_high"      : processed["temp_high"],
        }


# ─────────────────────────────────────────────
# ACTUATORS (A)
# ─────────────────────────────────────────────

class Actuators:
    """
    Step 5 — ACT: Executes physical and digital actions.

    Real hardware actuators (ESP32-S3):
      - L298N + 5V DC fan   -> ventilation (PWM: 0%, 50%, 100%)
      - ILI9341 TFT display -> status screen (LVGL 8-state UI)
      - MAX98357A + speaker -> voice alerts
      - LED strip (L298N)   -> ambient lighting
      - Web UI (FastAPI)    -> remote monitoring & control
    """

    def fan_off(self):
        print("    [FAN]     Fan OFF (0% PWM)")

    def fan_moderate(self):
        print("    [FAN]     Fan ON — moderate speed (50% PWM)")

    def fan_full(self):
        print("    [FAN]  !! Fan ON — FULL SPEED (100% PWM)")

    def tft_alert(self, message):
        print(f"    [TFT]  !! ALERT: {message}")

    def tft_status(self, message):
        print(f"    [TFT]     Status: {message}")

    def speaker_alert(self, message):
        print(f"    [SPEAKER] !! VOICE ALERT: {message}")

    def led_auto(self, level):
        brightness = {"dark": 100, "dim": 50, "bright": 0}[level]
        print(f"    [LED]     LED brightness: {brightness}% (light={level})")

    def web_notify(self, message):
        print(f"    [WEB UI]  Notification sent: {message}")

    def access_granted(self, name):
        print(f"    [RFID]    Access GRANTED — Welcome, {name}!")

    def access_denied(self):
        print("    [RFID]  !! Access DENIED — Unauthorized user detected!")

    def do_nothing(self):
        print("    [OK]      All systems normal. No action required.")


class RealActuators(Actuators):
    """
    Actuators override for real hardware mode.
    Sends HTTP POST commands directly to ESP32.
    Falls back silently to Actuators (print-only) if ESP32 unreachable.
    """

    def __init__(self, host=ESP32_HOST):
        self.base_url = f"http://{host}"

    def _post(self, path, body: dict, timeout=2):
        data = json.dumps(body).encode()
        req  = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"    [HW ERR]  POST {path} failed: {e}")
            return None

    def fan_off(self):
        super().fan_off()
        self._post("/fan", {"speed": 0})

    def fan_moderate(self):
        super().fan_moderate()
        self._post("/fan", {"speed": 50})

    def fan_full(self):
        super().fan_full()
        self._post("/fan", {"speed": 100})

    def led_auto(self, level):
        super().led_auto(level)
        brightness = {"dark": 100, "dim": 50, "bright": 0}[level]
        self._post("/led", {"brightness": brightness})


# ─────────────────────────────────────────────
# AGENT — Decision Making + Learning (P)
# ─────────────────────────────────────────────

class SmartLabAgent:
    """
    Intelligent agent implementing the full PEAS model.

    Steps covered:
      Step 1 — Initialize   : load config, set mode, init EMA learner
      Step 6 — Decide       : rule-based decision from analysis results
      Step 7 — Learn        : EMA-based adaptive threshold adjustment + persist

    System Modes:
      ARMED    : full security active, all threats trigger alerts
      DISARMED : monitoring only, no alarms triggered

    Performance Measure (P):
      - correct_detections : threat present AND alert raised
      - false_alarms       : no threat BUT alert raised
      - missed_detections  : threat present BUT no alert raised
      - correct_ignores    : no threat AND no alert raised
    """

    def __init__(self):
        # Step 1 — INITIALIZE
        self.system_mode            = "ARMED"
        self.authorized_users       = LabEnvironment.AUTHORIZED_USERS
        self.false_alarm_streak     = 0
        self.temperature_fan_active = False

        # EMA-based adaptive learner — loads previous state if available
        self.learner = EMALearner()
        self.learner.load(LEARNED_STATE_FILE)

        # Performance tracking
        self.correct_detections = 0
        self.false_alarms       = 0
        self.missed_detections  = 0
        self.correct_ignores    = 0
        self.total_steps        = 0
        self.total_response_ms  = 0

    def set_mode(self, mode):
        """Switch between ARMED and DISARMED."""
        self.system_mode = mode

    def decide(self, analysis):
        """
        Step 6 — DECISION MAKING
        Priority: fire > smoke > temperature > identity > motion > LED
        """
        start   = time.time()
        actions = []
        threat  = False

        if self.system_mode == "DISARMED":
            actions.append(("tft_status", "System DISARMED — monitoring only"))
            actions.append(("led_auto", analysis["light_level"]))
            elapsed_ms = (time.time() - start) * 1000
            self.total_response_ms += elapsed_ms
            self.total_steps += 1
            return actions, False

        # Priority 1: Fire emergency
        if analysis["security_class"] == "fire_emergency":
            actions.append(("fan_full",))
            actions.append(("tft_alert", "FIRE DETECTED — EVACUATE!"))
            actions.append(("speaker_alert", "Fire detected! Please evacuate immediately!"))
            actions.append(("web_notify", "EMERGENCY: Flame sensor triggered"))
            threat = True

        # Priority 2: Dangerous smoke
        elif analysis["smoke_class"] == "dangerous":
            actions.append(("fan_full",))
            actions.append(("tft_alert", "DANGEROUS SMOKE LEVEL"))
            actions.append(("speaker_alert", "Dangerous smoke detected! Fan at full speed."))
            actions.append(("web_notify", "Critical smoke level detected"))
            threat = True

        # Priority 3: Moderate smoke
        elif analysis["smoke_class"] == "moderate":
            if not self.temperature_fan_active:
                actions.append(("fan_moderate",))
            actions.append(("tft_status", "Moderate smoke — fan activated"))
            threat = True

        else:
            # Priority 4: High temperature
            if analysis["temp_high"]:
                self.temperature_fan_active = True
                actions.append(("fan_moderate",))
                actions.append(("tft_status", "High temperature — fan activated"))
                threat = True
            else:
                self.temperature_fan_active = False
                actions.append(("fan_off",))

        # Priority 5: Identity check
        if analysis["identity_class"] == "authorized_user":
            actions.append(("access_granted", analysis["user_name"]))
        elif analysis["security_class"] in ("intrusion", "unauthorized_access"):
            actions.append(("access_denied",))
            actions.append(("tft_alert", "UNAUTHORIZED ACCESS ATTEMPT"))
            actions.append(("web_notify", f"Unauthorized user: {analysis['user_name']}"))
            threat = True

        # Priority 6: LED control
        actions.append(("led_auto", analysis["light_level"]))

        if not threat and len([a for a in actions if a[0] not in ("fan_off", "led_auto")]) == 0:
            actions.append(("do_nothing",))

        elapsed_ms = (time.time() - start) * 1000
        self.total_response_ms += elapsed_ms
        self.total_steps += 1
        return actions, threat

    def learn(self, analysis, threat_detected, processed=None):
        """
        Step 7 — LEARN: EMA-based adaptive threshold adjustment.

        On every step:
          - Update EMA means and variances for smoke and temperature
          - Recalculate dynamic thresholds (mean + N*sigma)
          - Persist learned state to JSON for next session

        On false alarm streak >= 3:
          - EMA naturally raises thresholds as 'normal' smoke/temp shifts up
          - Additionally resets streak counter so next real alert fires quickly

        On confirmed real threat:
          - Streak resets
          - EMA is NOT updated with threat-level readings (avoids threshold drift
            toward danger levels)

        Args:
            analysis       : dict from Analyzer.analyze()
            threat_detected: bool from decide()
            processed      : dict from Preprocessor.process() — provides raw ADC
                             values for EMA update; skipped if None
        """
        real_threat = (
            analysis["flame"]
            or analysis["smoke_class"] in ("moderate", "dangerous")
            or analysis["security_class"] in ("intrusion", "unauthorized_access", "fire_emergency")
            or analysis["temp_high"]
        )

        if not real_threat and threat_detected:
            self.false_alarm_streak += 1
            if self.false_alarm_streak >= 3:
                print(f"    [LEARN]   False alarm streak={self.false_alarm_streak} "
                      f"— EMA thresholds adjusting (smoke mod≥{self.learner.thresholds['smoke_moderate']:.0f} "
                      f"dan≥{self.learner.thresholds['smoke_dangerous']:.0f})")
        else:
            self.false_alarm_streak = 0

        # Update EMA only with non-threat readings to keep 'normal' baseline accurate
        if processed is not None and not real_threat:
            self.learner.update(processed["smoke_adc"], processed["temperature_c"])
            self.learner.save(LEARNED_STATE_FILE)

    def update_performance(self, analysis, threat_detected):
        """Track performance metrics (Performance Measure — P)."""
        real_threat = (
            analysis["flame"]
            or analysis["smoke_class"] in ("moderate", "dangerous")
            or analysis["security_class"] in ("intrusion", "unauthorized_access", "fire_emergency")
            or analysis["temp_high"]
        )
        if real_threat and threat_detected:
            self.correct_detections += 1
        elif real_threat and not threat_detected:
            self.missed_detections += 1
        elif not real_threat and threat_detected:
            self.false_alarms += 1
        else:
            self.correct_ignores += 1

    def performance_report(self):
        """Print PEAS performance summary including learned thresholds."""
        total    = self.total_steps
        avg_ms   = (self.total_response_ms / total) if total > 0 else 0
        accuracy = ((self.correct_detections + self.correct_ignores) / total * 100) if total > 0 else 0
        print("\n" + "=" * 60)
        print("         SMARTLAB AGENT — PERFORMANCE REPORT")
        print("=" * 60)
        print(f"  System Mode            : {self.system_mode}")
        print(f"  Total Steps            : {total}")
        print(f"  Correct Detections     : {self.correct_detections}")
        print(f"  False Alarms           : {self.false_alarms}")
        print(f"  Missed Detections      : {self.missed_detections}")
        print(f"  Correct Ignores        : {self.correct_ignores}")
        print(f"  Overall Accuracy       : {accuracy:.1f}%")
        print(f"  Avg Response Time      : {avg_ms:.2f} ms")
        print("─" * 60)
        print("  LEARNED THRESHOLDS (EMA-based adaptive):")
        print(f"  Smoke  baseline mean   : {self.learner.means['smoke']:.0f} ADC")
        print(f"  Smoke  moderate thresh : ≥ {self.learner.thresholds['smoke_moderate']:.0f} ADC")
        print(f"  Smoke  dangerous thresh: ≥ {self.learner.thresholds['smoke_dangerous']:.0f} ADC")
        print(f"  Temp   baseline mean   : {self.learner.means['temperature']:.1f} °C")
        print(f"  Temp   high thresh     : ≥ {self.learner.thresholds['temp_high']:.1f} °C")
        print("=" * 60)


# ─────────────────────────────────────────────
# SYSTEM INTEGRATION
# ─────────────────────────────────────────────

def run_simulation(steps=15, use_real=False):
    """
    Main simulation loop.
    Flow: Initialize → Perceive → Preprocess → Analyze → Decide → Act → Learn

    Args:
        steps    : number of simulation steps
        use_real : True = fetch from ESP32 server, False = random simulation
    """
    env          = LabEnvironment()
    sensors      = RealSensors()   if use_real else Sensors()
    preprocessor = Preprocessor()
    analyzer     = Analyzer()
    actuators    = RealActuators() if use_real else Actuators()
    agent        = SmartLabAgent()   # Step 1: Initialize (loads learned_state.json)

    mode_label = "REAL HARDWARE" if use_real else "SIMULATION"
    print("=" * 60)
    print("   SMARTLAB ASSISTANT — AI AGENT (PEAS)")
    print(f"   Data Source : {mode_label}")
    print(f"   System Mode : {agent.system_mode}")
    if use_real:
        print(f"   ESP32       : http://{ESP32_HOST}/sensors")
    print(f"   Learned state file: {LEARNED_STATE_FILE}")
    print("=" * 60)

    for step in range(1, steps + 1):
        print(f"\n{'─'*60}")
        print(f"  TIME STEP {step:02d}  [Mode: {agent.system_mode}]")
        print(f"{'─'*60}")

        # Step 2: PERCEIVE
        env_state  = env.get_state() if not use_real else {}
        raw        = sensors.sense(env_state)
        source_tag = f" [{raw.get('_source','sim')}]" if use_real else ""
        print(f"  [PERCEIVE{source_tag}] rfid={raw['rfid_raw']} | smoke={raw['smoke_adc']} | "
              f"temp={raw['temperature_c']:.1f}°C | motion={raw['motion_raw']} | flame={raw['flame_raw']}")

        # Step 3: PREPROCESS (uses learned thresholds)
        processed  = preprocessor.process(raw, agent.learner)
        print(f"  [PREPROCESS] smoke={processed['smoke_level']} (thresh mod≥{agent.learner.thresholds['smoke_moderate']:.0f}) | "
              f"temp_high={processed['temp_high']} (thresh≥{agent.learner.thresholds['temp_high']:.1f}°C) | flame={processed['flame']}")

        # Step 4: ANALYZE
        analysis   = analyzer.analyze(processed)
        print(f"  [ANALYZE] identity={analysis['identity_class']} | "
              f"security={analysis['security_class']} | smoke={analysis['smoke_class']}")

        # Step 5: DECIDE
        actions, threat = agent.decide(analysis)
        print(f"  [DECIDE] threat={threat} — {len(actions)} action(s):")

        # Step 6: ACT
        for action in actions:
            method = action[0]
            args   = action[1:]
            getattr(actuators, method)(*args)

        # Step 7: LEARN (EMA update + persist)
        agent.learn(analysis, threat, processed)

        # Update performance
        agent.update_performance(analysis, threat)

        time.sleep(0.3)

    agent.performance_report()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    use_real = "--real" in _sys.argv
    run_simulation(steps=15, use_real=use_real)
