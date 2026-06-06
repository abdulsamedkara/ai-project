# AI-Based SmartLab Security & Assistant System
## PEAS Framework Analysis

**Course:** Artificial Intelligence — RTEU Computer Engineering  
**Students:** Abdül Samed Kara (211401065) | Mert Abdullahoğlu (221401005)  
**Lecturer:** Assoc. Prof. Yıldıran Yılmaz  

---

## Overview

SmartLab Assistant is an intelligent agent designed for university laboratory environments. It combines real-time security monitoring, automatic environmental control, and AI-powered voice assistance into a single integrated system. The agent is implemented on an ESP32-S3 microcontroller communicating with a local Python AI server over an AES-256-CBC encrypted WebSocket connection.

The system was designed and built using the PEAS framework to ensure goal-oriented, responsive, and intelligent behavior.

---

## 1. Performance Measure (P)

The performance measure defines how success is evaluated for the SmartLab agent. A well-performing system should:

- **Correctly identify threats:** Detect unauthorized users, dangerous smoke levels, and fire with a high true positive rate
- **Minimize false alarms:** Avoid unnecessary alerts caused by authorized users, pets, or normal environmental variation
- **Fast response time:** React to threats within 500ms of sensor detection
- **Accurate user identification:** RFID-based authentication should correctly identify authorized laboratory users
- **AI query accuracy:** Voice questions answered correctly using Retrieval-Augmented Generation (RAG) from lab documents
- **Continuous operation:** System must run 24/7 without failure or memory leaks
- **Energy efficiency:** Fan and LED strip activated only when necessary to minimize power consumption
- **Privacy preservation:** All audio data encrypted with AES-256-CBC; no data transmitted to external cloud services

### Performance Metrics Tracked

| Metric | Description |
|---|---|
| Correct Detections | Threat present AND alert raised |
| False Alarms | No threat present BUT alert raised |
| Missed Detections | Threat present BUT no alert raised |
| Correct Ignores | No threat AND no alert raised |
| Overall Accuracy | (Correct Detections + Correct Ignores) / Total Steps |
| Average Response Time | Mean time from perception to action (ms) |

---

## 2. Environment (E)

The environment in which the SmartLab agent operates is the university computer engineering laboratory. It includes:

- **Authorized users:** Students and faculty with registered RFID cards
- **Unauthorized persons:** Unregistered individuals who attempt to access the lab
- **Laboratory equipment:** Computers, electronic devices, power sources
- **Environmental conditions:** Temperature, humidity, smoke/gas concentration, ambient light
- **Physical hazards:** Fire, dangerous gas leaks, physical disturbances (vibration)

### Environment Characteristics

| Characteristic | Description |
|---|---|
| **Partially Observable** | Not all events are visible simultaneously; sensors cover different aspects |
| **Dynamic** | Conditions change continuously — users enter/leave, smoke levels vary |
| **Stochastic** | Uncertainty in sensor readings; PIR may trigger on non-human motion |
| **Real-Time** | Requires immediate decision-making; threats must be addressed within seconds |
| **Multi-Agent** | Multiple users may be present; agent must handle concurrent events |

---

## 3. Actuators (A)

Actuators are the components through which the agent takes action in the physical world.

| Actuator | Hardware | Action |
|---|---|---|
| **Fan (PWM)** | L298N motor driver + 5V DC fan | 0% off / 50% moderate / 100% full speed |
| **TFT Display** | ILI9341 240×320 (LVGL 8-state UI) | Shows system status, alerts, user name |
| **Speaker** | MAX98357A I2S amplifier + 3W speaker | Voice alerts and AI responses (Piper TTS) |
| **LED Strip** | L298N channel A + LED strip | Proportional brightness based on ambient light |
| **Web UI** | FastAPI server + HTML/JS dashboard | Remote monitoring, fan control, photo analysis |

### Actuator Actions by Threat Level

| Situation | Fan | TFT | Speaker | Web UI |
|---|---|---|---|---|
| Flame detected | 100% | FIRE ALERT | "Evacuate!" | Emergency push |
| Dangerous smoke | 100% | SMOKE ALERT | Voice warning | Notification |
| Moderate smoke | 50% | Status update | — | — |
| High temperature | 50% | Status update | — | — |
| Unauthorized user | — | ACCESS DENIED | — | Security alert |
| Authorized user | — | Welcome screen | — | Session start |
| Voice query | — | Processing | AI response | — |
| Normal state | 0% | Idle screen | — | — |

---

## 4. Sensors (S)

Sensors collect data from the environment for the agent's perception and decision-making.

| Sensor | Hardware | Data Collected |
|---|---|---|
| **RFID Reader** | MFRC522 SPI | User identity (4-byte UID → name lookup) |
| **Smoke/Gas Sensor** | MQ135 (ADC1_CH3, GPIO4) | Smoke concentration: <800 clean / 800-1500 moderate / >1500 dangerous |
| **Temperature/Humidity** | DHT11 (GPIO47) | Temperature °C, humidity % — fan triggers at >27°C |
| **Motion Sensor** | PIR HC-SR501 (GPIO5) | Presence detection in lab |
| **Flame Sensor** | Digital IR module (GPIO48) | Fire detection — LOW signal = flame |
| **Vibration Sensor** | SW-420 (GPIO1) | Physical disturbance or impact |
| **Light Sensor** | LDR (ADC1_CH5, GPIO6) | Ambient light level for LED control |
| **Microphone** | INMP441 I2S (SCK=42, WS=2, SD=41) | Voice input for AI assistant (PTT) |

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DEVICE LAYER (ESP32-S3)               │
│                                                          │
│  [MFRC522]  [INMP441]  [MQ135]  [DHT11]  [PIR]         │
│  [Flame]    [SW-420]   [LDR]    [Button]                │
│       │          │        │        │       │             │
│       └──────────┴────────┴────────┴───────┘             │
│                        ↓                                 │
│              [ESP32-S3 N16R8]                            │
│         FreeRTOS | AES-256-CBC | LVGL                    │
│                        ↓                                 │
│   [ILI9341 TFT]  [MAX98357A]  [L298N Fan]  [LED Strip]  │
└─────────────────────────────────────────────────────────┘
                          │
              AES-256-CBC WebSocket (LAN)
                          │
┌─────────────────────────────────────────────────────────┐
│                 APPLICATION LAYER (PC)                   │
│                                                          │
│  Faster-Whisper → ChromaDB RAG → Gemma3:4b → Piper TTS  │
│                   FastAPI + Web UI                       │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Agent Algorithm

```
BEGIN SMARTLAB_AGENT

1. INITIALIZE
   - Load authorized users database (RFID_USERS)
   - Generate AES-256-CBC session key (32 bytes, random)
   - Start sensor tasks (FreeRTOS, Core 0)
   - Start LVGL display task (Core 1)
   - Connect to WiFi and WebSocket server

2. LOOP forever

   2.1 PERCEIVE environment (Sensors)
       rfid_identity   ← read_rfid_sensor()
       smoke_level     ← read_mq135_adc_avg(32 samples)
       temperature     ← read_dht11()
       motion          ← read_pir_gpio()
       flame           ← read_flame_sensor()
       vibration       ← read_sw420()
       light_level     ← read_ldr_adc()
       voice_input     ← capture_i2s_mic() [on PTT press]

   2.2 PREPROCESS sensor data
       - Apply 3-sample debounce to smoke readings
       - Average 32 ADC samples for noise reduction
       - Check RFID UID validity (reject 00000000)

   2.3 DECISION MAKING (Priority Order)

       IF flame = TRUE THEN
           fan_speed ← 100%
           tft_state ← UI_SMOKE_ALERT
           speaker   ← "Fire detected! Evacuate!"
           web_ui    ← push_emergency_notification()

       ELSE IF smoke_level = dangerous (>1500) AND debounce >= 3 THEN
           fan_speed ← 100%
           tft_state ← UI_SMOKE_ALERT
           speaker   ← "Dangerous smoke detected!"

       ELSE IF smoke_level = moderate (800-1500) THEN
           IF NOT temperature_fan_active THEN
               fan_speed ← 50%

       IF temperature > 27°C THEN
           temperature_fan_active ← TRUE
           fan_speed ← 50%

       IF rfid_identity IN authorized_users THEN
           tft_state ← UI_READY
           display "Welcome, [name]"
       ELSE IF rfid_identity = unauthorized THEN
           tft_state ← UI_ERROR
           web_ui    ← push_security_alert()

       IF motion AND rfid_identity = unauthorized THEN
           speaker ← "Unauthorized motion detected!"

       IF voice_input (PTT released) THEN
           audio ← encrypt(pcm_data, AES256_CBC)
           send_to_server(audio)
           response ← receive_from_server()
           play_response(decrypt(response))

       led_brightness ← proportional_to_ldr()

   2.4 UPDATE PERFORMANCE
       - Track correct_detections, false_alarms, missed_detections
       - Log event to database

3. END LOOP

END SMARTLAB_AGENT
```

---

## 7. Agent Type

SmartLab Assistant is a **Goal-Based + Utility-Based Reactive Agent** with learning capability:

- **Goal-Based:** Has explicit goals (lab security, user assistance, environmental control)
- **Utility-Based:** Optimizes performance metrics (maximize detections, minimize false alarms)
- **Reactive:** Responds to sensor inputs in real-time without deliberation delays
- **Learning (partial):** RAG system updates knowledge base; false alarm patterns can improve threshold calibration

---

## 8. Comparison with Teacher's Example

| Feature | Smart Home Security (Example) | SmartLab Assistant (This Project) |
|---|---|---|
| Domain | Home security | University laboratory |
| Biometric sensor | Fingerprint (simulated) | RFID card reader (real hardware) |
| Motion detection | PIR (simulated) | PIR HC-SR501 (real hardware) |
| Environmental sensors | Light, time | Smoke, temperature, flame, vibration, light |
| AI component | Rule-based classifier | LLM (Gemma3:4b) + STT + TTS + RAG |
| Actuators | Alarm, lights, notification | Fan PWM, TFT display, speaker, LED, web UI |
| Implementation | Python simulation | Real ESP32-S3 + Python server |
| Communication | None | AES-256-CBC encrypted WebSocket |
| Voice interaction | None | Full STT → LLM → TTS pipeline |

---

## 9. Conclusion

Using the PEAS framework ensures the SmartLab Agent is goal-oriented, responsive, and intelligent. The framework allowed us to:

1. **Define clear success criteria** (Performance) — measurable accuracy and response time
2. **Model the real-world operating context** (Environment) — lab users, hazards, conditions
3. **Design appropriate output mechanisms** (Actuators) — graduated responses to threat levels
4. **Select optimal sensing modalities** (Sensors) — multi-sensor fusion for reliable detection

The SmartLab project extends the teacher's example by using **real physical hardware** rather than simulation, adding **genuine AI reasoning** via a local language model, and implementing **security** through encrypted communication. The Python simulation in this submission faithfully mirrors the decision logic running on the actual embedded system.
