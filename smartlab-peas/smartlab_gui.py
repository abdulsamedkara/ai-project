"""
SmartLab Assistant — AI Agent GUI (PEAS Framework)
===================================================
Tkinter GUI simulation of the intelligent lab agent.

Algorithm Flow:
  Initialize → Perceive → Preprocess → Analyze → Decide → Act → Learn

Features:
  - Live environment, sensor, analysis, decision, actuator panels
  - ARMED / DISARMED mode toggle
  - Step-by-step and Auto-run modes
  - Performance metrics with EMA-based learning indicator

Run: python smartlab_gui.py

Students: Abdül Samed Kara  (211401065)
          Mert Abdullahoğlu (221401005)
Course  : Artificial Intelligence — RTEU Computer Engineering
"""

import tkinter as tk
import random
import time
import threading

from smartlab_agent import (
    LabEnvironment, Sensors, RealSensors, RealActuators, Preprocessor,
    Analyzer, Actuators, SmartLabAgent, ESP32_HOST
)


# ─────────────────────────────────────────────
# GUI ACTUATORS
# ─────────────────────────────────────────────

class GUIActuators(Actuators):
    def __init__(self, gui):
        self.gui = gui

    def fan_off(self):
        self.gui.fan_var.set("Fan: OFF (0%)")
        self.gui.fan_label.config(fg="#6c7086")

    def fan_moderate(self):
        self.gui.fan_var.set("Fan: ON — 50% PWM")
        self.gui.fan_label.config(fg="#fab387")

    def fan_full(self):
        self.gui.fan_var.set("Fan: FULL SPEED — 100%")
        self.gui.fan_label.config(fg="#f38ba8")

    def tft_alert(self, message):
        self.gui.tft_var.set(f"TFT: !! {message}")
        self.gui.tft_label.config(fg="#f38ba8")

    def tft_status(self, message):
        self.gui.tft_var.set(f"TFT: {message}")
        self.gui.tft_label.config(fg="#fab387")

    def speaker_alert(self, message):
        self.gui.speaker_var.set(f"!! {message}")
        self.gui.speaker_label.config(fg="#f38ba8")

    def led_auto(self, level):
        brightness = {"dark": "100%", "dim": "50%", "bright": "0%"}[level]
        self.gui.led_var.set(f"LED: {brightness} (light={level})")
        self.gui.led_label.config(fg="#cba6f7")

    def web_notify(self, message):
        self.gui.web_var.set(f"Web: {message}")
        self.gui.web_label.config(fg="#89dceb")

    def access_granted(self, name):
        self.gui.rfid_var.set(f"RFID: GRANTED — {name}")
        self.gui.rfid_label.config(fg="#a6e3a1")

    def access_denied(self):
        self.gui.rfid_var.set("RFID: !! DENIED — Unauthorized!")
        self.gui.rfid_label.config(fg="#f38ba8")

    def do_nothing(self):
        self.gui.tft_var.set("TFT: All systems normal")
        self.gui.tft_label.config(fg="#a6e3a1")

    def reset_all(self):
        for var, lbl in [
            (self.gui.fan_var, self.gui.fan_label),
            (self.gui.tft_var, self.gui.tft_label),
            (self.gui.speaker_var, self.gui.speaker_label),
            (self.gui.led_var, self.gui.led_label),
            (self.gui.web_var, self.gui.web_label),
            (self.gui.rfid_var, self.gui.rfid_label),
        ]:
            var.set("—")
            lbl.config(fg="#6c7086")


# ─────────────────────────────────────────────
# MAIN GUI
# ─────────────────────────────────────────────

class SmartLabGUI:
    BG    = "#1e1e2e"
    BG2   = "#181825"
    FG    = "#cdd6f4"
    MUTED = "#6c7086"

    def __init__(self, root):
        self.root = root
        self.root.title("SmartLab Assistant — AI Agent (PEAS)")
        self.root.geometry("940x700")
        self.root.configure(bg=self.BG)
        self.root.resizable(True, True)

        self.env             = LabEnvironment()
        self.sensors         = Sensors()
        self.real_sensors    = RealSensors()
        self.real_actuators  = RealActuators()
        self.preprocessor    = Preprocessor()
        self.analyzer        = Analyzer()
        self.agent           = SmartLabAgent()
        self.actuators       = GUIActuators(self)

        self.step_count   = 0
        self.auto_running = False
        self.use_real     = False

        self._build_ui()

    def _frame(self, parent, title, color):
        return tk.LabelFrame(parent, text=f" {title} ",
                             font=("Consolas", 8, "bold"),
                             fg=color, bg=self.BG2,
                             bd=1, relief="solid",
                             labelanchor="n", padx=4, pady=1)

    def _row(self, parent, label, var, color):
        f = tk.Frame(parent, bg=self.BG2)
        f.pack(fill="x")
        tk.Label(f, text=f"{label:<20}", font=("Consolas", 8),
                 fg=self.MUTED, bg=self.BG2).pack(side="left")
        lbl = tk.Label(f, textvariable=var, font=("Consolas", 8, "bold"),
                       fg=color, bg=self.BG2, anchor="w", wraplength=300)
        lbl.pack(side="left", fill="x")
        return lbl

    def _build_ui(self):
        tk.Label(self.root,
                 text="SmartLab Assistant — AI Agent (PEAS Framework)",
                 font=("Consolas", 11, "bold"),
                 fg="#cba6f7", bg=self.BG).pack(pady=(5, 0))
        tk.Label(self.root,
                 text="Abdül Samed Kara  |  Mert Abdullahoğlu  |  RTEU Computer Engineering",
                 font=("Consolas", 8), fg=self.MUTED, bg=self.BG).pack(pady=(0, 3))

        # Control bar
        mode_bar = tk.Frame(self.root, bg=self.BG)
        mode_bar.pack(fill="x", padx=12, pady=(0, 2))

        tk.Label(mode_bar, text="System Mode:", font=("Consolas", 9, "bold"),
                 fg=self.FG, bg=self.BG).pack(side="left", padx=(0, 6))
        self.mode_var = tk.StringVar(value="ARMED")
        self.mode_lbl = tk.Label(mode_bar, textvariable=self.mode_var,
                                 font=("Consolas", 10, "bold"),
                                 fg="#f38ba8", bg=self.BG)
        self.mode_lbl.pack(side="left")
        tk.Button(mode_bar, text="Toggle ARMED/DISARMED",
                  font=("Consolas", 9), bg="#313244", fg=self.FG,
                  relief="flat", cursor="hand2",
                  command=self.toggle_mode).pack(side="left", padx=10)

        tk.Label(mode_bar, text="|", fg=self.MUTED, bg=self.BG).pack(side="left", padx=4)
        tk.Label(mode_bar, text="Data Source:", font=("Consolas", 9, "bold"),
                 fg=self.FG, bg=self.BG).pack(side="left", padx=(0, 6))
        self.source_var = tk.StringVar(value="SIMULATION")
        self.source_lbl = tk.Label(mode_bar, textvariable=self.source_var,
                                   font=("Consolas", 10, "bold"),
                                   fg="#89b4fa", bg=self.BG)
        self.source_lbl.pack(side="left")
        tk.Button(mode_bar, text="Switch Real/Sim",
                  font=("Consolas", 9), bg="#313244", fg=self.FG,
                  relief="flat", cursor="hand2",
                  command=self.toggle_source).pack(side="left", padx=10)

        main = tk.Frame(self.root, bg=self.BG)
        main.pack(fill="both", expand=True, padx=12)
        left  = tk.Frame(main, bg=self.BG)
        right = tk.Frame(main, bg=self.BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        right.pack(side="right", fill="both", expand=True)

        # ── PERCEIVE ──
        p = self._frame(left, "STEP 2 — PERCEIVE (Sensors)", "#89b4fa")
        p.pack(fill="x", pady=2)
        self.raw_rfid_var  = tk.StringVar(value="—")
        self.raw_smoke_var = tk.StringVar(value="—")
        self.raw_temp_var  = tk.StringVar(value="—")
        self.raw_flame_var = tk.StringVar(value="—")
        self.raw_ldr_var   = tk.StringVar(value="—")
        self.raw_vib_var   = tk.StringVar(value="—")
        for lbl, var in [("RFID raw",    self.raw_rfid_var),
                         ("Smoke ADC",   self.raw_smoke_var),
                         ("Temperature", self.raw_temp_var),
                         ("Flame raw",   self.raw_flame_var),
                         ("LDR (light)", self.raw_ldr_var),
                         ("Vibration",   self.raw_vib_var)]:
            self._row(p, lbl, var, "#89b4fa")

        # ── PREPROCESS ──
        pp = self._frame(left, "STEP 3 — PREPROCESS", "#89dceb")
        pp.pack(fill="x", pady=2)
        self.pp_smoke_var = tk.StringVar(value="—")
        self.pp_temp_var  = tk.StringVar(value="—")
        self.pp_flame_var = tk.StringVar(value="—")
        for lbl, var in [("Smoke level", self.pp_smoke_var),
                         ("Temp high", self.pp_temp_var),
                         ("Flame", self.pp_flame_var)]:
            self._row(pp, lbl, var, "#89dceb")

        # ── ANALYZE ──
        an = self._frame(left, "STEP 4 — ANALYZE", "#a6e3a1")
        an.pack(fill="x", pady=2)
        self.an_identity_var = tk.StringVar(value="—")
        self.an_security_var = tk.StringVar(value="—")
        self.an_smoke_var    = tk.StringVar(value="—")
        self.an_thermal_var  = tk.StringVar(value="—")
        for lbl, var in [("Identity class", self.an_identity_var),
                         ("Security class", self.an_security_var),
                         ("Smoke class", self.an_smoke_var),
                         ("Thermal class", self.an_thermal_var)]:
            self._row(an, lbl, var, "#a6e3a1")

        # ── DECIDE ──
        dc = self._frame(left, "STEP 5 — DECIDE", "#f38ba8")
        dc.pack(fill="x", pady=2)
        self.decision_var = tk.StringVar(value="—")
        self.threat_var   = tk.StringVar(value="—")
        self._row(dc, "Actions", self.decision_var, "#f38ba8")
        self.threat_lbl = self._row(dc, "Threat detected", self.threat_var, "#f38ba8")

        # ── ACTUATORS ──
        ac = self._frame(right, "STEP 6 — ACT (Actuators)", "#fab387")
        ac.pack(fill="x", pady=2)
        self.fan_var     = tk.StringVar(value="—")
        self.tft_var     = tk.StringVar(value="—")
        self.rfid_var    = tk.StringVar(value="—")
        self.speaker_var = tk.StringVar(value="—")
        self.led_var     = tk.StringVar(value="—")
        self.web_var     = tk.StringVar(value="—")
        self.fan_label     = self._row(ac, "Fan (PWM)", self.fan_var, "#6c7086")
        self.tft_label     = self._row(ac, "TFT Display", self.tft_var, "#6c7086")
        self.rfid_label    = self._row(ac, "RFID Gate", self.rfid_var, "#6c7086")
        self.speaker_label = self._row(ac, "Speaker", self.speaker_var, "#6c7086")
        self.led_label     = self._row(ac, "LED Strip", self.led_var, "#6c7086")
        self.web_label     = self._row(ac, "Web UI", self.web_var, "#6c7086")

        # ── LEARN ──
        lrn = self._frame(right, "STEP 7 — LEARN  (EMA Adaptive)", "#cba6f7")
        lrn.pack(fill="x", pady=2)
        self.learn_var        = tk.StringVar(value="No adjustments yet")
        self.streak_var       = tk.StringVar(value="0")
        self.smoke_mean_var   = tk.StringVar(value="—")
        self.smoke_mod_var    = tk.StringVar(value="—")
        self.smoke_dan_var    = tk.StringVar(value="—")
        self.temp_mean_var    = tk.StringVar(value="—")
        self.temp_thresh_var  = tk.StringVar(value="—")
        self._row(lrn, "Status",            self.learn_var,       "#cba6f7")
        self._row(lrn, "False alarm streak", self.streak_var,     "#fab387")
        self._row(lrn, "Smoke baseline",    self.smoke_mean_var,  "#89b4fa")
        self._row(lrn, "Smoke mod thresh",  self.smoke_mod_var,   "#fab387")
        self._row(lrn, "Smoke dan thresh",  self.smoke_dan_var,   "#f38ba8")
        self._row(lrn, "Temp baseline",     self.temp_mean_var,   "#89b4fa")
        self._row(lrn, "Temp high thresh",  self.temp_thresh_var, "#fab387")

        # ── PERFORMANCE ──
        pf = self._frame(right, "PERFORMANCE  (P)", "#f9e2af")
        pf.pack(fill="x", pady=2)
        self.perf_correct_var  = tk.StringVar(value="0")
        self.perf_false_var    = tk.StringVar(value="0")
        self.perf_missed_var   = tk.StringVar(value="0")
        self.perf_ignore_var   = tk.StringVar(value="0")
        self.perf_accuracy_var = tk.StringVar(value="0.0%")
        self._row(pf, "Correct detections", self.perf_correct_var, "#a6e3a1")
        self._row(pf, "False alarms",       self.perf_false_var,   "#f38ba8")
        self._row(pf, "Missed detections",  self.perf_missed_var,  "#fab387")
        self._row(pf, "Correct ignores",    self.perf_ignore_var,  "#89b4fa")
        self._row(pf, "Accuracy",           self.perf_accuracy_var,"#f9e2af")

        # ── BUTTONS ──
        self.step_var = tk.StringVar(value="Step: 0")
        tk.Label(self.root, textvariable=self.step_var,
                 font=("Consolas", 9, "bold"), fg="#cba6f7", bg=self.BG).pack(pady=(2, 0))

        btn_f = tk.Frame(self.root, bg=self.BG)
        btn_f.pack(pady=4)
        bs = {"font": ("Consolas", 9, "bold"), "width": 16,
              "relief": "flat", "cursor": "hand2", "pady": 3}

        tk.Button(btn_f, text="▶  Run Step", command=self.run_step,
                  bg="#313244", fg=self.FG, activebackground="#45475a", **bs
                  ).pack(side="left", padx=5)

        self.auto_btn = tk.Button(btn_f, text="⏵  Auto Run",
                                   command=self.toggle_auto,
                                   bg="#313244", fg=self.FG,
                                   activebackground="#45475a", **bs)
        self.auto_btn.pack(side="left", padx=5)

        tk.Button(btn_f, text="↺  Reset", command=self.reset,
                  bg="#313244", fg=self.FG, activebackground="#45475a", **bs
                  ).pack(side="left", padx=5)

        # Show initial learned thresholds (from loaded state)
        self._refresh_learn()

    def toggle_mode(self):
        mode = "DISARMED" if self.agent.system_mode == "ARMED" else "ARMED"
        self.agent.set_mode(mode)
        self.mode_var.set(mode)
        self.mode_lbl.config(fg="#f38ba8" if mode == "ARMED" else "#a6e3a1")

    def toggle_source(self):
        self.use_real = not self.use_real
        if self.use_real:
            self.source_var.set(f"REAL  ({ESP32_HOST})")
            self.source_lbl.config(fg="#a6e3a1")
        else:
            self.source_var.set("SIMULATION")
            self.source_lbl.config(fg="#89b4fa")

    def run_step(self):
        self.actuators.reset_all()
        self.step_count += 1
        self.step_var.set(f"Step: {self.step_count}")

        # Step 2: Perceive
        if self.use_real:
            raw = self.real_sensors.sense()
            src = raw.get("_source", "real")
            self.source_var.set(f"REAL [{src}]")
            self.source_lbl.config(fg="#a6e3a1" if src == "real" else "#fab387")
        else:
            env_state = self.env.get_state()
            raw       = self.sensors.sense(env_state)
        self.raw_rfid_var.set(raw["rfid_raw"])
        self.raw_smoke_var.set(str(raw["smoke_adc"]))
        self.raw_temp_var.set(f"{raw['temperature_c']:.1f}°C")
        self.raw_flame_var.set(str(raw["flame_raw"]))
        self.raw_ldr_var.set(f"{raw['light_adc']}  ({raw['light_level']})")
        self.raw_vib_var.set(str(raw["vibration"]))

        # Step 3: Preprocess (uses learned thresholds)
        processed = self.preprocessor.process(raw, self.agent.learner)
        self.pp_smoke_var.set(processed["smoke_level"])
        self.pp_temp_var.set(str(processed["temp_high"]))
        self.pp_flame_var.set(str(processed["flame"]))

        # Step 4: Analyze
        analysis = self.analyzer.analyze(processed)
        self.an_identity_var.set(analysis["identity_class"])
        self.an_security_var.set(analysis["security_class"])
        self.an_smoke_var.set(analysis["smoke_class"])
        self.an_thermal_var.set(analysis["thermal_class"])

        # Step 5: Decide
        actions, threat = self.agent.decide(analysis)
        names = ", ".join(a[0] for a in actions)
        self.decision_var.set(names[:55] + ("..." if len(names) > 55 else ""))
        self.threat_var.set("THREAT DETECTED" if threat else "Normal — No Threat")
        self.threat_lbl.config(fg="#f38ba8" if threat else "#a6e3a1")

        # Step 6: Act — GUI her zaman güncellenir; gerçek modda ESP32'ye de gönderilir
        for action in actions:
            getattr(self.actuators, action[0])(*action[1:])
            if self.use_real:
                hw_method = getattr(self.real_actuators, action[0], None)
                if hw_method:
                    hw_method(*action[1:])

        # Step 7: Learn (EMA update + persist)
        self.agent.learn(analysis, threat, processed)
        self._refresh_learn()

        # Performance
        self.agent.update_performance(analysis, threat)
        self._refresh_perf()

    def _refresh_learn(self):
        """Update the Learn panel with current EMA values."""
        lrn = self.agent.learner
        streak = self.agent.false_alarm_streak

        if lrn.thresholds:
            self.smoke_mean_var.set(f"{lrn.means['smoke']:.0f} ADC")
            self.smoke_mod_var.set(f"≥ {lrn.thresholds['smoke_moderate']:.0f} ADC")
            self.smoke_dan_var.set(f"≥ {lrn.thresholds['smoke_dangerous']:.0f} ADC")
            self.temp_mean_var.set(f"{lrn.means['temperature']:.1f} °C")
            self.temp_thresh_var.set(f"≥ {lrn.thresholds['temp_high']:.1f} °C")

        self.streak_var.set(str(streak))

        if streak >= 3:
            self.learn_var.set("Adjusting thresholds (false alarm streak)")
        elif streak > 0:
            self.learn_var.set(f"False alarm streak: {streak}")
        else:
            self.learn_var.set("EMA updating — no streak")

    def _refresh_perf(self):
        a   = self.agent
        t   = a.total_steps
        acc = ((a.correct_detections + a.correct_ignores) / t * 100) if t > 0 else 0
        self.perf_correct_var.set(str(a.correct_detections))
        self.perf_false_var.set(str(a.false_alarms))
        self.perf_missed_var.set(str(a.missed_detections))
        self.perf_ignore_var.set(str(a.correct_ignores))
        self.perf_accuracy_var.set(f"{acc:.1f}%")

    def toggle_auto(self):
        if self.auto_running:
            self.auto_running = False
            self.auto_btn.config(text="⏵  Auto Run", bg="#313244")
        else:
            self.auto_running = True
            self.auto_btn.config(text="⏹  Stop Auto", bg="#45475a")
            threading.Thread(target=self._auto_loop, daemon=True).start()

    def _auto_loop(self):
        while self.auto_running:
            self.root.after(0, self.run_step)
            time.sleep(1.2)

    def reset(self):
        self.auto_running = False
        self.auto_btn.config(text="⏵  Auto Run", bg="#313244")
        self.agent      = SmartLabAgent()
        self.step_count = 0
        self.step_var.set("Step: 0")
        self.mode_var.set("ARMED")
        self.mode_lbl.config(fg="#f38ba8")
        self.actuators.reset_all()
        for var in [self.raw_rfid_var, self.raw_smoke_var, self.raw_temp_var,
                    self.raw_flame_var, self.raw_ldr_var,
                    self.raw_vib_var, self.pp_smoke_var,
                    self.pp_temp_var, self.pp_flame_var, self.an_identity_var,
                    self.an_security_var, self.an_smoke_var, self.an_thermal_var,
                    self.decision_var, self.threat_var]:
            var.set("—")
        self._refresh_learn()
        self._refresh_perf()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = SmartLabGUI(root)
    root.mainloop()
