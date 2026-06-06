# SmartLab PEAS — AI Course Project Context

## Project
Artificial Intelligence dersi final projesi (final yerine geçiyor).
RTEU Computer Engineering — Assoc. Prof. Yıldıran Yılmaz

Students:
- Abdül Samed Kara — 211401065 — abdulsamed_kara21@erdogan.edu.tr
- Mert Abdullahoğlu — 221401005 — mert_abdullahoglu22@erdogan.edu.tr

## Status: TAMAMLANDI ✅ (Gerçek donanım entegrasyonu dahil)
Tüm dosyalar yazıldı ve test edildi.

## Files
- `smartlab_agent.py` — terminal simülasyonu
- `smartlab_gui.py`   — Tkinter GUI (7 panel: Perceive/Preprocess/Analyze/Decide/Act/Learn/Performance)
- `peas_document.md`  — PEAS framework dokümanı
- `README.txt`        — nasıl çalıştırılır

## How to Run
```bash
python -X utf8 smartlab_agent.py          # terminal simulation
python -X utf8 smartlab_agent.py --real   # terminal real hardware
python -X utf8 smartlab_gui.py            # GUI (toggle real/sim inside)
```

## Real Hardware Config
- ESP32_HOST = "10.162.138.176" — ESP32'nin WiFi IP'si (config.h WIFI_SSID/PASSWORD ile aynı ağ)
- Değişirse smartlab_agent.py başındaki ESP32_HOST'u güncelle
- ARA SUNUCU YOK — Python doğrudan ESP32'ye bağlanır (port 80)
- ESP32 aynı WiFi'da olmalı; firmware yüklenmiş olmalı

## Mimari (Yeni — Ara Sunucu Yok)
```
ESP32 (HTTP server :80)
  GET  /sensors  → {temperature, humidity, smoke, ldr, pir, flame, vib}
  GET  /status   → {username, rfid_scanned}
  POST /fan      → {"speed": 0-100}
  POST /led      → {"brightness": 0-100}
      ↕ urllib.request (stdlib)
smartlab_agent.py / smartlab_gui.py
  RealSensors   — pollar /sensors + /status
  RealActuators — POST /fan + /led
```

## RealSensors Data Mapping (ESP32 → Agent)
| ESP32 field  | Agent field       | Notes                           |
|--------------|-------------------|---------------------------------|
| smoke        | smoke_adc         | raw ADC 0-4095                  |
| temperature  | temperature_c     | float °C                        |
| pir          | motion_raw        | 1=motion, 0=none                |
| flame        | flame_raw         | 0=fire (LOW=fire), 1=safe       |
| vib          | vibration         | 1=vibration, 0=none             |
| ldr          | light_adc         | >3000=bright >1500=dim else dark|
| username     | user_name+rfid_raw| "Misafir"→none, "Bilinmeyen"→unauth|

## Algorithm Flow (7 Steps — hocanın istediği)
1. Initialize  → authorized users, ARMED/DISARMED mode, thresholds
2. Perceive    → Sensors.sense() — raw ADC, RFID, motion, flame
3. Preprocess  → Preprocessor.process() — noise filter, normalize, threshold classify
4. Analyze     → Analyzer.analyze() — identity/smoke/thermal/security/env classification
5. Decide      → SmartLabAgent.decide() — priority-based rules, ARMED/DISARMED check
6. Act         → Actuators execute — fan, TFT, speaker, LED, web UI
7. Learn       → SmartLabAgent.learn() — false alarm streak → threshold adjustment

## PEAS Mapping
Performance : correct_detections, false_alarms, missed_detections, accuracy %, avg_response_ms
Environment : authorized_user/unauthorized_user/none, smoke (clean/moderate/dangerous),
              temperature (normal/high), motion, flame, vibration, light (bright/dim/dark)
Actuators   : Fan PWM (0/50/100%), TFT display, Speaker alerts, LED strip, Web UI
Sensors     : RFID (MFRC522), MQ135 smoke ADC, DHT11 temp, PIR motion,
              Flame, SW-420 vibration, LDR light

## Key Design Decisions
- LLM/voice assistant YOK — hocanın istediği sade PEAS agent
- ARMED/DISARMED mode var — hocanın algoritmasında vardı
- Preprocess ayrı class — gürültü filtresi + ADC normalizasyonu
- Analyze ayrı class — 5 farklı sınıflandırma kategorisi
- Learn: false alarm streak >= 3 → smoke_threshold_adj += 50 (max 300)
- No external packages — sadece stdlib (tkinter, random, time, threading)

## Hoca Dökümanları (referans)
Dosyalar IoT proje klasöründe:
D:\ceng\ceng\3-sinif-dersler\iot-project\iot-project-final\iot-project-final-v1\
- Practical Class (1).docx
- Python code for the practical (1).docx

## Beklenen Mail Cevabı
Hocaya şunları sorduk:
1. Simülasyon mu yeterli, yoksa gerçek donanım mı?
2. Hazır LLM kullanabilir miyiz?
Cevaba göre kodu güncellemek gerekebilir.

## Real Hardware (ayrı IoT projesi)
ESP32-S3 N16R8, ESP-IDF 5.5.3, AES-256-CBC WebSocket
IoT proje: D:\ceng\ceng\3-sinif-dersler\iot-project\iot-project-final\iot-project-final-v1
IoT GitHub: https://github.com/abdulsamedkara/iot-project-final-v1
