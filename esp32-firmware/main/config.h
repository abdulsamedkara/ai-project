#pragma once

// WiFi
#define WIFI_SSID           "Raspi"
#define WIFI_PASSWORD       "00000000"
#define WIFI_MAX_RETRY      10

// HTTP Server (Python bağlanır)
// Endpoint'ler: GET /sensors  GET /status  POST /fan  POST /led
#define HTTP_PORT           80

// SPI Bus (shared: MFRC522 + ILI9341)
#define SPI_MOSI_GPIO       11
#define SPI_MISO_GPIO       13
#define SPI_SCK_GPIO        12
#define SMARTLAB_SPI_HOST   SPI2_HOST

// MFRC522 RFID
#define RFID_CS_GPIO        10
#define RFID_RST_GPIO       (-1)
#define RFID_SPI_FREQ_HZ    (2 * 1000 * 1000)

// ILI9341 TFT Display
#define TFT_CS_GPIO         9
#define TFT_DC_GPIO         8
#define TFT_RST_GPIO        7
#define TFT_BL_GPIO         46
#define TFT_SPI_FREQ_HZ     (40 * 1000 * 1000)
#define TFT_WIDTH           240
#define TFT_HEIGHT          320
#define LVGL_BUF_LINES      40

// MQ135 Smoke / Gas Sensor
#define SMOKE_AOUT_GPIO     4
#define SMOKE_DOUT_GPIO     14
#define SMOKE_ADC_CHANNEL   ADC_CHANNEL_3
#define SMOKE_ADC_CLEAR     1000
#define SMOKE_ADC_HALF      1600
#define SMOKE_ADC_FULL      2300
#define SMOKE_WARMUP_MS     10000
#define SMOKE_SAMPLE_COUNT  32

// L298N Fan
#define FAN_IN4_GPIO        18
#define FAN_ENA_GPIO        21
#define FAN_LEDC_TIMER      LEDC_TIMER_1
#define FAN_LEDC_CHANNEL    LEDC_CHANNEL_1
#define FAN_PWM_FREQ_HZ     25000
#define FAN_DUTY_RES        LEDC_TIMER_8_BIT

// DHT11
#define DHT11_GPIO          47
#define DHT11_UPDATE_MS     2000

// LDR
#define LDR_AOUT_GPIO       6
#define LDR_ADC_CHANNEL     ADC_CHANNEL_5
#define LDR_LED_DARK_ADC    2200
#define LDR_LED_BRIGHT_ADC  3100

// PTT Button (BOOT butonu — GPIO 0, active LOW)
#define PTT_GPIO            0

// Flame Sensor
#define FLAME_GPIO          48

// SW-420 Vibration
#define VIB_GPIO            1

// Buzzer (aktif buzzer, GPIO HIGH = açık)
#define BUZZER_GPIO         2

// LED Strip
#define LED_ENB_GPIO        38
#define LED_LEDC_TIMER      LEDC_TIMER_2
#define LED_LEDC_CHANNEL    LEDC_CHANNEL_2
#define LED_PWM_FREQ_HZ     1000
#define LED_DUTY_RES        LEDC_TIMER_8_BIT
