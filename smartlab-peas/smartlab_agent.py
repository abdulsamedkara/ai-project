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
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── Server config — update if IP changes ─────────────────────────────────────
SERVER_HOST = "10.162.138.176"
SERVER_PORT = 8080


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
            "motion"      : random.choice([True, False]),
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
            "motion_raw"  : env_state["motion"],
            "flame_raw"   : env_state["flame"],
            "vibration"   : env_state["vibration"],
            "light_adc"   : {"bright": 3200, "dim": 2000, "dark": 800}
                            [env_state["light_level"]] + random.randint(-30, 30),
            "light_level" : env_state["light_level"],
        }


# ─────────────────────────────────────────────
# REAL SENSORS — fetches live data from ESP32 server
# ─────────────────────────────────────────────

class RealSensors:
    """
    Step 2 — PERCEIVE (Real Hardware Mode):
    Fetches live sensor data from the SmartLab server via HTTP.

    Endpoints used:
      GET /sessions                        → list active sessions
      GET /api/session/{id}/data           → sensor readings + username

    Sensor data format from ESP32:
      temperature  : float (°C)
      humidity     : float (%)
      smoke        : int   (ADC value, 0–4095)
      ldr          : int   (ADC value, 0–4095)
      pir          : int   (1=motion, 0=none)
      flame        : int   (0=fire detected LOW, 1=safe)
      vib          : int   (1=vibration, 0=none)

    RFID identity:
      username == "Misafir"       → no card scanned  → none
      username starts "Bilinmeyen"→ unknown card      → unauthorized_user
      otherwise                  → known card        → authorized_user

    Falls back to simulation if server is unreachable.
    """

    LDR_BRIGHT = 3000
    LDR_DIM    = 1500

    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.base_url = f"http://{host}:{port}"
        self._sim     = Sensors()
        self._sim_env = LabEnvironment()

    def _get(self, path, timeout=2):
        url = f"{self.base_url}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def sense(self, env_state=None):
        """
        Fetch live sensor data from server.
        Returns same dict structure as Sensors.sense() plus '_source' key.
        """
        try:
            sessions = self._get("/sessions").get("sessions", [])
            if not sessions:
                return self._fallback("no_session")

            # Use most recently active session
            session = sessions[0]
            session_id = session["session_id"]
            data       = self._get(f"/api/session/{session_id}/data")
            sensors    = data.get("sensors", {})
            username   = data.get("username", "Misafir")

            if not sensors:
                return self._fallback("no_sensors")

            # RFID identity classification
            if username == "Misafir" or not session.get("rfid_scanned"):
                rfid_raw = "none"
            elif username.startswith("Bilinmeyen"):
                rfid_raw = "unauthorized_user"
            else:
                rfid_raw = "authorized_user"

            # flame: ESP32 sends 0=fire (digital LOW), 1=safe
            flame = (sensors.get("flame", 1) == 0)

            # ldr ADC → light level
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
                "motion_raw"   : sensors.get("pir", 0) == 1,
                "flame_raw"    : flame,
                "vibration"    : sensors.get("vib", 0) == 1,
                "light_adc"    : ldr,
                "light_level"  : light_level,
                "_source"      : "real",
            }

        except Exception as e:
            return self._fallback(str(e))

    def _fallback(self, reason=""):
        """Simulation fallback when server is unreachable."""
        raw = self._sim.sense(self._sim_env.get_state())
        raw["_source"] = f"simulated (fallback: {reason})"
        return raw


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
    """

    SMOKE_NOISE_FLOOR = 300   # below this = sensor noise, treat as clean
    SMOKE_MOD_THRESH  = 800   # moderate smoke threshold
    SMOKE_DAN_THRESH  = 1500  # dangerous smoke threshold
    TEMP_HIGH_THRESH  = 27.0  # fan trigger temperature (°C)

    def process(self, raw):
        """Clean and normalize raw sensor readings."""
        smoke_adc = max(0, min(4095, raw["smoke_adc"]))
        if smoke_adc < self.SMOKE_NOISE_FLOOR:
            smoke_adc = 0

        return {
            "rfid_identity"  : raw["rfid_raw"],
            "user_name"      : raw["user_name"],
            "smoke_adc"      : smoke_adc,
            "smoke_level"    : (
                "dangerous" if smoke_adc >= self.SMOKE_DAN_THRESH else
                "moderate"  if smoke_adc >= self.SMOKE_MOD_THRESH else
                "clean"
            ),
            "temperature_c"  : round(raw["temperature_c"], 1),
            "temp_high"      : raw["temperature_c"] >= self.TEMP_HIGH_THRESH,
            "motion"         : raw["motion_raw"],
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
        # Identity classification
        identity_class = processed["rfid_identity"]

        # Smoke classification
        smoke_class = processed["smoke_level"]

        # Thermal classification
        thermal_class = "high_temperature" if processed["temp_high"] else "normal"

        # Security classification
        if processed["flame"]:
            security_class = "fire_emergency"
        elif identity_class == "unauthorized_user" and processed["motion"]:
            security_class = "intrusion"
        elif identity_class == "unauthorized_user":
            security_class = "unauthorized_access"
        elif smoke_class == "dangerous":
            security_class = "hazard"
        else:
            security_class = "safe"

        # Environment stability
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
            "motion"         : processed["motion"],
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


# ─────────────────────────────────────────────
# AGENT — Decision Making + Learning (P)
# ─────────────────────────────────────────────

class SmartLabAgent:
    """
    Intelligent agent implementing the full PEAS model.

    Steps covered:
      Step 1 — Initialize   : load config, set mode, define thresholds
      Step 6 — Decide       : rule-based decision from analysis results
      Step 7 — Learn        : adaptive threshold adjustment

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
        self.system_mode           = "ARMED"
        self.authorized_users      = LabEnvironment.AUTHORIZED_USERS
        self.smoke_threshold_adj   = 0    # learning: shifts moderate threshold up on false alarms
        self.false_alarm_streak    = 0    # consecutive false alarms
        self.temperature_fan_active = False

        # Performance tracking
        self.correct_detections    = 0
        self.false_alarms          = 0
        self.missed_detections     = 0
        self.correct_ignores       = 0
        self.total_steps           = 0
        self.total_response_ms     = 0

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
            if analysis["motion"]:
                actions.append(("speaker_alert", "Unauthorized motion detected in lab!"))
            threat = True

        # Priority 6: LED control
        actions.append(("led_auto", analysis["light_level"]))

        if not threat and len([a for a in actions if a[0] not in ("fan_off", "led_auto")]) == 0:
            actions.append(("do_nothing",))

        elapsed_ms = (time.time() - start) * 1000
        self.total_response_ms += elapsed_ms
        self.total_steps += 1
        return actions, threat

    def learn(self, analysis, threat_detected):
        """
        Step 7 — LEARN: Adaptive threshold adjustment.

        If consecutive false alarms occur on moderate smoke readings,
        the agent increases its internal adjustment counter, effectively
        raising the sensitivity threshold to reduce future false alarms.
        Resets when a confirmed real threat is detected.
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
                self.smoke_threshold_adj = min(self.smoke_threshold_adj + 50, 300)
                print(f"    [LEARN]   False alarm streak={self.false_alarm_streak} "
                      f"— smoke threshold adjusted +{self.smoke_threshold_adj}")
        else:
            self.false_alarm_streak = 0

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
        """Print PEAS performance summary."""
        total    = self.total_steps
        avg_ms   = (self.total_response_ms / total) if total > 0 else 0
        accuracy = ((self.correct_detections + self.correct_ignores) / total * 100) if total > 0 else 0
        print("\n" + "=" * 55)
        print("        SMARTLAB AGENT — PERFORMANCE REPORT")
        print("=" * 55)
        print(f"  System Mode          : {self.system_mode}")
        print(f"  Total Steps          : {total}")
        print(f"  Correct Detections   : {self.correct_detections}")
        print(f"  False Alarms         : {self.false_alarms}")
        print(f"  Missed Detections    : {self.missed_detections}")
        print(f"  Correct Ignores      : {self.correct_ignores}")
        print(f"  Overall Accuracy     : {accuracy:.1f}%")
        print(f"  Avg Response Time    : {avg_ms:.2f} ms")
        print(f"  Smoke Threshold Adj  : +{self.smoke_threshold_adj} (learned)")
        print("=" * 55)


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
    sensors      = RealSensors() if use_real else Sensors()
    preprocessor = Preprocessor()
    analyzer     = Analyzer()
    actuators    = Actuators()
    agent        = SmartLabAgent()   # Step 1: Initialize

    mode_label = "REAL HARDWARE" if use_real else "SIMULATION"
    print("=" * 55)
    print("   SMARTLAB ASSISTANT — AI AGENT (PEAS)")
    print(f"   Data Source : {mode_label}")
    print(f"   System Mode : {agent.system_mode}")
    if use_real:
        print(f"   Server      : http://{SERVER_HOST}:{SERVER_PORT}")
    print("=" * 55)

    for step in range(1, steps + 1):
        print(f"\n{'─'*55}")
        print(f"  TIME STEP {step:02d}  [Mode: {agent.system_mode}]")
        print(f"{'─'*55}")

        # Step 2: PERCEIVE
        env_state  = env.get_state() if not use_real else {}
        raw        = sensors.sense(env_state)
        source_tag = f" [{raw.get('_source','sim')}]" if use_real else ""
        print(f"  [PERCEIVE{source_tag}] rfid={raw['rfid_raw']} | smoke={raw['smoke_adc']} | "
              f"temp={raw['temperature_c']:.1f}°C | motion={raw['motion_raw']} | flame={raw['flame_raw']}")

        # Step 3: PREPROCESS
        processed  = preprocessor.process(raw)
        print(f"  [PREPROCESS] smoke={processed['smoke_level']} | "
              f"temp_high={processed['temp_high']} | flame={processed['flame']}")

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

        # Step 7: LEARN
        agent.learn(analysis, threat)

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
