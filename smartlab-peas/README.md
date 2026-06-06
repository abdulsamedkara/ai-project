# SmartLab Assistant — AI Agent (PEAS Framework)

**Course:** Artificial Intelligence — Final Project  
**University:** Recep Tayyip Erdoğan University, Computer Engineering  
**Lecturer:** Assoc. Prof. Yıldıran Yılmaz  
**Students:** Abdül Samed Kara (211401065) | Mert Abdullahoğlu (221401005)

---

## Files

| File | Description |
|---|---|
| `smartlab_agent.py` | Terminal simulation + real hardware mode |
| `smartlab_gui.py` | Tkinter GUI (simulation or real ESP32) |
| `peas_document.md` | Full PEAS framework documentation |
| `../esp32-firmware/` | ESP32 HTTP server firmware (for real mode) |

---

## Requirements

- Python 3.8+
- Standard library only: `tkinter`, `random`, `time`, `threading`, `urllib`, `json`, `math`, `os`
- No `pip install` needed.

---

## Run — Simulation Mode

No hardware needed. Works on any computer.

```bash
# Terminal
python -X utf8 smartlab_agent.py

# GUI
python -X utf8 smartlab_gui.py
```

---

## Run — Real Hardware Mode

Python connects **directly to the ESP32** via HTTP. No intermediate server needed.

### Step 1 — Flash ESP32 firmware

```bash
cd ../esp32-firmware
get_idf
idf.py -p COMX flash monitor
```

After boot, ESP32 prints its IP address to serial monitor. Update `ESP32_HOST` in `smartlab_agent.py` if it changed.

### Step 2 — Run AI agent

```bash
# Terminal
python -X utf8 smartlab_agent.py --real

# GUI
python -X utf8 smartlab_gui.py
# then press "Switch Real/Sim" button inside
```

If ESP32 is unreachable, agent automatically falls back to simulation mode.

### ESP32 HTTP Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/sensors` | temperature, humidity, smoke, ldr, pir, flame, vibration |
| GET | `/status` | RFID username + rfid_scanned flag |
| POST | `/fan` | `{"speed": 0-100}` |
| POST | `/led` | `{"brightness": 0-100}` |

### IP Configuration

Default: `ESP32_HOST = "10.162.138.176"` (near top of `smartlab_agent.py`)  
Update if DHCP assigns a different IP.

---

## Algorithm Flow

```
Step 1 — Initialize  : load config, ARMED/DISARMED mode, load learned_state.json
Step 2 — Perceive    : raw sensor readings (RFID, smoke ADC, temp, motion, flame, vib, light)
Step 3 — Preprocess  : clamp ADC, noise floor filter, apply learned thresholds
Step 4 — Analyze     : classify identity / smoke / thermal / security / environment
Step 5 — Decide      : priority rules (fire > smoke > temp > identity > LED)
Step 6 — Act         : fan PWM, TFT display, speaker alert, LED strip, web UI
Step 7 — Learn       : EMA adaptive threshold update, persist to learned_state.json
```

---

## PEAS Mapping

| Component | SmartLab |
|---|---|
| **Performance** | Correct detections, false alarms, missed detections, accuracy %, avg response time |
| **Environment** | Lab with authorized/unauthorized/none user, smoke, temperature, motion, flame, vibration, light |
| **Actuators** | Fan PWM (0/50/100%), TFT display, Speaker, LED strip, Web UI |
| **Sensors** | RFID (MFRC522), MQ135 smoke, DHT11 temp/humidity, PIR motion, Flame, SW-420 vibration, LDR light |

---

## Decision Priority

1. Flame detected → fan 100% + EVACUATE alert
2. Smoke dangerous (>1500 ADC) → fan 100% + smoke alert
3. Smoke moderate (800–1500 ADC) → fan 50%
4. Temperature high (>27°C) → fan 50%
5. Unauthorized RFID → ACCESS DENIED + web alert
6. Motion + unauthorized → speaker alert
7. Authorized RFID → welcome screen
8. Light level → LED proportional control

---

## Learning (Step 7)

Agent uses **Exponential Moving Average (EMA)** to learn the normal baseline for smoke and temperature:

- Thresholds = `mean + N×sigma` (adaptive, not fixed)
- Updates only on non-threat readings (avoids learning danger as normal)
- Persists to `learned_state.json` — survives restarts
- Safety floors: smoke moderate ≥ 800, dangerous ≥ 1500, temp high ≥ 27°C

---

## GUI Controls

| Button | Action |
|---|---|
| Run Step | Advance one step |
| Auto Run / Stop | Run automatically every 1.2 seconds |
| Reset | Reset agent and all metrics |
| Toggle ARMED/DISARMED | ARMED: full alerts \| DISARMED: monitor only |
| Switch Real/Sim | Toggle between live ESP32 data and simulation |
