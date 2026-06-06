SmartLab Assistant — AI Agent (PEAS Framework)
================================================
Artificial Intelligence Course — Final Project
Recep Tayyip Erdogan University, Computer Engineering

Students:
  Abdül Samed Kara   — 211401065
  Mert Abdullahoğlu  — 221401005

Lecturer: Assoc. Prof. Yıldıran Yılmaz

─────────────────────────────────────────────
FILES
─────────────────────────────────────────────
smartlab_agent.py   — Terminal simulation + real hardware mode
smartlab_gui.py     — Tkinter GUI (simulation or real, toggle inside)
peas_document.md    — Full PEAS framework documentation
README.txt          — This file

─────────────────────────────────────────────
REQUIREMENTS
─────────────────────────────────────────────
Python 3.8+
Standard library only (tkinter, random, time, threading, urllib, json)
No pip install needed.

─────────────────────────────────────────────
HOW TO RUN — SIMULATION MODE
─────────────────────────────────────────────
No hardware needed. Works on any computer.

Terminal:
    python -X utf8 smartlab_agent.py

GUI:
    python -X utf8 smartlab_gui.py

─────────────────────────────────────────────
HOW TO RUN — REAL HARDWARE MODE
─────────────────────────────────────────────
IMPORTANT: No ESP32 flash needed. The ESP32 already has
the SmartLab IoT firmware installed. This AI project
only reads sensor data from the running server via HTTP.
Do NOT flash or modify the ESP32.

Step 1 — Power on the ESP32-S3 SmartLab device.
         It will connect to WiFi automatically.

Step 2 — Start the SmartLab server on the host PC:
         (from the iot-project-final-v1 folder)

         cd server
         uvicorn main:app --host 0.0.0.0 --port 8080

Step 3 — Run the AI agent in real hardware mode:

         Terminal:
             python -X utf8 smartlab_agent.py --real

         GUI:
             python -X utf8 smartlab_gui.py
             then press "Switch Real/Sim" button inside

Step 4 — Tap an RFID card on the ESP32 device.
         The AI agent will read the live sensor data
         and show real-time decisions.

If the server is unreachable, the agent automatically
falls back to simulation mode.

─────────────────────────────────────────────
SERVER IP CONFIGURATION
─────────────────────────────────────────────
Default server IP: 10.162.138.176 (port 8080)

If the PC IP address changes, update this line in
smartlab_agent.py (near the top of the file):

    SERVER_HOST = "10.162.138.176"

─────────────────────────────────────────────
ALGORITHM FLOW
─────────────────────────────────────────────
Step 1 — Initialize  : authorized users, ARMED/DISARMED mode, thresholds
Step 2 — Perceive    : raw sensor readings (RFID, smoke ADC, temp, motion,
                       flame, vibration, light)
Step 3 — Preprocess  : clamp ADC, filter noise floor, normalize temperature
Step 4 — Analyze     : classify identity / smoke / thermal / security / env
Step 5 — Decide      : priority rules (fire > smoke > temp > identity > LED)
Step 6 — Act         : fan PWM, TFT display, speaker alert, LED, web UI
Step 7 — Learn       : false alarm streak → adaptive threshold adjustment

─────────────────────────────────────────────
PEAS MAPPING
─────────────────────────────────────────────
Performance : Correct detections, false alarms, missed detections,
              accuracy %, average response time (ms)

Environment : Lab with authorized_user / unauthorized_user / none,
              smoke (clean/moderate/dangerous), temperature (normal/high),
              motion, flame, vibration, light (bright/dim/dark)

Actuators   : Fan PWM (0/50/100%), TFT display, Speaker alerts,
              LED strip, Web UI notifications

Sensors     : RFID (biometric), MQ135 smoke ADC, DHT11 temperature,
              PIR motion, Flame sensor, SW-420 vibration, LDR light

─────────────────────────────────────────────
GUI CONTROLS
─────────────────────────────────────────────
Run Step              — advance one step
Auto Run / Stop Auto  — run automatically every 1.2 seconds
Reset                 — reset agent and all metrics
Toggle ARMED/DISARMED — ARMED: full alerts | DISARMED: monitor only
Switch Real/Sim       — toggle between live ESP32 data and simulation
