// SmartLab Assistant — ESP32 HTTP Server Firmware
//
// Python (smartlab_agent.py / smartlab_gui.py) doğrudan bu ESP32'ye bağlanır.
// Ara sunucu yok.
//
// HTTP Endpoint'leri:
//   GET  /sensors  → tüm sensör verisi (JSON)
//   GET  /status   → RFID kullanıcı adı + rfid_scanned (JSON)
//   POST /fan      → fan kontrolü  {"speed": 0-100}
//   POST /led      → LED kontrolü  {"brightness": 0-100}
//
// config.h içindeki WIFI_SSID / WIFI_PASSWORD güncellenmeli.
// Python tarafında ESP32_HOST = ESP32'nin DHCP IP'si.

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_http_server.h"

#include "config.h"
#include "rfid.h"
#include "smoke_sensor.h"
#include "fan_control.h"
#include "led_strip_ctrl.h"
#include "dht11.h"
#include "ui/display.h"

static const char *TAG = "main";

// ─── WiFi ─────────────────────────────────────────────────────────────────────

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

static EventGroupHandle_t s_wifi_eg;
static int s_retry = 0;

static void wifi_event_handler(void *arg, esp_event_base_t base,
                                int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry < WIFI_MAX_RETRY) {
            esp_wifi_connect();
            s_retry++;
        } else {
            xEventGroupSetBits(s_wifi_eg, WIFI_FAIL_BIT);
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *ev = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "IP: " IPSTR, IP2STR(&ev->ip_info.ip));
        s_retry = 0;
        xEventGroupSetBits(s_wifi_eg, WIFI_CONNECTED_BIT);
    }
}

static esp_err_t wifi_init(void)
{
    s_wifi_eg = xEventGroupCreate();
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t eh_wifi, eh_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &eh_wifi));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &eh_ip));

    wifi_config_t wc = {
        .sta = {
            .ssid     = WIFI_SSID,
            .password = WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    EventBits_t bits = xEventGroupWaitBits(s_wifi_eg,
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT, pdFALSE, pdFALSE, portMAX_DELAY);
    return (bits & WIFI_CONNECTED_BIT) ? ESP_OK : ESP_FAIL;
}

// ─── Paylaşılan Sensör Durumu ─────────────────────────────────────────────────
// Sensor task'ları buraya yazar, HTTP handler'lar buradan okur.

static volatile int  g_temp         = 0;
static volatile int  g_hum          = 0;
static volatile int  g_smoke        = 0;
static volatile int  g_ldr          = 0;
static volatile int  g_flame        = 1;   // 1 = güvenli (aktif LOW sensör)
static volatile int  g_vib          = 0;
static char          g_username[64] = "Misafir";
static volatile bool g_rfid_scanned = false;
static volatile int  g_led_auto     = 1;

// Aktif ekran takibi (PTT ile değiştirme için)
static volatile screen_id_t g_active_screen = SCREEN_IDLE;

// Sensör ekranını güncel verilerle çizer
static void refresh_sensors_screen(void)
{
    char msg[48];
    snprintf(msg, sizeof(msg), "%d %d %d %d %d %d",
             g_temp, g_hum, g_smoke, g_flame, g_ldr, g_vib);
    display_switch(SCREEN_SENSORS, msg);
    g_active_screen = SCREEN_SENSORS;
}

// ─── Sensor Tasks ─────────────────────────────────────────────────────────────

static void dht11_task(void *arg)
{
    dht11_reading_t d;
    while (1) {
        if (dht11_read(DHT11_GPIO, &d) == ESP_OK) {
            g_temp = d.temperature;
            g_hum  = d.humidity;
        }
        vTaskDelay(pdMS_TO_TICKS(DHT11_UPDATE_MS));
    }
}

static void smoke_task(void *arg)
{
    while (!smoke_sensor_warmup_done())
        vTaskDelay(pdMS_TO_TICKS(1000));

    int  alert_count = 0;
    bool in_alert    = false;

    while (1) {
        int adc = smoke_sensor_read_avg();
        if (adc < 0) { vTaskDelay(pdMS_TO_TICKS(500)); continue; }

        g_smoke = adc;

        if (adc >= SMOKE_ADC_FULL)      fan_full();
        else if (adc >= SMOKE_ADC_HALF) fan_half();

        if (adc >= SMOKE_ADC_HALF) {
            if (++alert_count >= 3 && !in_alert) {
                in_alert = true;
                char msg[32];
                snprintf(msg, sizeof(msg), "ADC: %d", adc);
                display_switch(SCREEN_SMOKE_ALERT, msg);
            }
        } else {
            if (alert_count > 0) alert_count--;
            if (in_alert && adc < SMOKE_ADC_CLEAR) {
                in_alert = false;
                display_switch(SCREEN_READY, NULL);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

static void ldr_task(void *arg)
{
    while (1) {
        int ldr = ldr_sensor_read_avg();
        if (ldr >= 0) {
            g_ldr = ldr;
            if (g_led_auto) {
                if (ldr <= LDR_LED_DARK_ADC) {
                    led_strip_set_brightness(255);
                } else if (ldr >= LDR_LED_BRIGHT_ADC) {
                    led_strip_off();
                } else {
                    int range = LDR_LED_BRIGHT_ADC - LDR_LED_DARK_ADC;
                    int diff  = ldr - LDR_LED_DARK_ADC;
                    led_strip_set_brightness((uint8_t)(255 - diff * 255 / range));
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

// Hızlı sensörleri (PIR, alev, titreşim) 200ms'de bir günceller
static void fast_sensor_task(void *arg)
{
    gpio_config_t io = {
        .mode         = GPIO_MODE_INPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    // VIB
    io.pin_bit_mask = 1ULL << VIB_GPIO;
    gpio_config(&io);
    // Flame — pull-up (aktif LOW)
    io.pin_bit_mask = 1ULL << FLAME_GPIO;
    io.pull_up_en   = GPIO_PULLUP_ENABLE;
    gpio_config(&io);
    // PTT — pull-up (aktif LOW, BOOT butonu)
    io.pin_bit_mask = 1ULL << PTT_GPIO;
    io.pull_up_en   = GPIO_PULLUP_ENABLE;
    gpio_config(&io);

    bool ptt_prev          = true;   // HIGH = basılmamış
    int  sensor_tick       = 0;      // periyodik ekran güncelleme sayacı

    while (1) {
        g_flame = gpio_get_level(FLAME_GPIO);
        g_vib   = gpio_get_level(VIB_GPIO);

        // Sıcaklığa göre otomatik fan (duman alarmı yoksa)
        if (g_smoke < SMOKE_ADC_HALF) {
            if (g_temp >= 27) {
                uint8_t duty = (g_temp >= 35) ? 255 : (uint8_t)((g_temp - 27) * 32);
                fan_set_duty(duty);
            } else if (g_temp < 25) {
                fan_off();
            }
        }

        // PTT butonu: falling edge = basıldı
        bool ptt_now = (bool)gpio_get_level(PTT_GPIO);
        if (ptt_prev && !ptt_now) {
            if (g_active_screen == SCREEN_SENSORS) {
                // Sensör ekranındayken PTT → karşılama ekranına dön
                display_switch(SCREEN_READY, g_username);
                g_active_screen = SCREEN_READY;
            } else if (g_active_screen == SCREEN_READY) {
                // Karşılama ekranındayken PTT → sensör ekranına geç
                refresh_sensors_screen();
            }
        }
        ptt_prev = ptt_now;

        // Her 2 saniyede bir (10 × 200ms) sensör ekranını güncelle
        if (g_active_screen == SCREEN_SENSORS) {
            if (++sensor_tick >= 10) {
                sensor_tick = 0;
                refresh_sensors_screen();
            }
        } else {
            sensor_tick = 0;
        }

        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

// ─── HTTP Handler'ları ────────────────────────────────────────────────────────

// GET /sensors
static esp_err_t h_sensors(httpd_req_t *req)
{
    char json[256];
    snprintf(json, sizeof(json),
        "{\"temperature\":%d,\"humidity\":%d,"
        "\"smoke\":%d,\"ldr\":%d,"
        "\"flame\":%d,\"vib\":%d}",
        g_temp, g_hum, g_smoke, g_ldr,
        g_flame, g_vib);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, json, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// GET /status
static esp_err_t h_status(httpd_req_t *req)
{
    char json[128];
    snprintf(json, sizeof(json),
        "{\"username\":\"%s\",\"rfid_scanned\":%s}",
        g_username, g_rfid_scanned ? "true" : "false");
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, json, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// POST /fan  {"speed": 0-100}
static esp_err_t h_fan(httpd_req_t *req)
{
    char buf[128] = {0};
    int  len      = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (len <= 0) { httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "No body"); return ESP_FAIL; }

    int speed = 0;
    const char *sp = strstr(buf, "\"speed\":");
    if (sp) {
        speed = atoi(sp + 8);
        if (speed < 0)   speed = 0;
        if (speed > 100) speed = 100;
    }

    if (speed == 0)        fan_off();
    else if (speed >= 100) fan_full();
    else                   fan_set_duty((uint8_t)(speed * 255 / 100));

    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, "{\"ok\":true}", HTTPD_RESP_USE_STRLEN);
    ESP_LOGI(TAG, "Fan -> %d%%", speed);
    return ESP_OK;
}

// POST /led  {"brightness": 0-100}
static esp_err_t h_led(httpd_req_t *req)
{
    char buf[128] = {0};
    int  len      = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (len <= 0) { httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "No body"); return ESP_FAIL; }

    int brightness = -1;
    const char *bp = strstr(buf, "\"brightness\":");
    if (bp) {
        brightness = atoi(bp + 13);
        if (brightness < 0)   brightness = 0;
        if (brightness > 100) brightness = 100;
    }

    if (brightness == 0) {
        g_led_auto = 0;
        led_strip_off();
    } else if (brightness > 0) {
        g_led_auto = 0;
        led_strip_set_brightness((uint8_t)(brightness * 255 / 100));
    } else {
        // brightness belirtilmemişse otomatik moda geç
        g_led_auto = 1;
    }

    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, "{\"ok\":true}", HTTPD_RESP_USE_STRLEN);
    ESP_LOGI(TAG, "LED -> %d%%", brightness);
    return ESP_OK;
}

static httpd_handle_t start_http_server(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port    = HTTP_PORT;

    httpd_handle_t server = NULL;
    if (httpd_start(&server, &cfg) != ESP_OK) return NULL;

    httpd_uri_t routes[] = {
        { .uri = "/sensors", .method = HTTP_GET,  .handler = h_sensors },
        { .uri = "/status",  .method = HTTP_GET,  .handler = h_status  },
        { .uri = "/fan",     .method = HTTP_POST, .handler = h_fan     },
        { .uri = "/led",     .method = HTTP_POST, .handler = h_led     },
    };
    for (int i = 0; i < 4; i++)
        httpd_register_uri_handler(server, &routes[i]);

    ESP_LOGI(TAG, "HTTP server başlatıldı: port %d", HTTP_PORT);
    return server;
}

// ─── SPI Bus ──────────────────────────────────────────────────────────────────

static void spi_bus_init(void)
{
    spi_bus_config_t bus = {
        .mosi_io_num     = SPI_MOSI_GPIO,
        .miso_io_num     = SPI_MISO_GPIO,
        .sclk_io_num     = SPI_SCK_GPIO,
        .quadwp_io_num   = -1,
        .quadhd_io_num   = -1,
        .max_transfer_sz = TFT_WIDTH * LVGL_BUF_LINES * 2 + 8,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(SMARTLAB_SPI_HOST, &bus, SPI_DMA_CH_AUTO));
}

// ─── app_main ─────────────────────────────────────────────────────────────────

void app_main(void)
{
    // NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    spi_bus_init();

    ESP_ERROR_CHECK(display_init());
    display_switch(SCREEN_IDLE, "Initializing...");

    // WiFi
    display_switch(SCREEN_IDLE, "Connecting WiFi...");
    if (wifi_init() != ESP_OK) {
        display_switch(SCREEN_ERROR, "WiFi error!");
        return;
    }

    // Sensors & actuators
    ESP_ERROR_CHECK(rfid_init());
    ESP_ERROR_CHECK(smoke_sensor_init());
    ESP_ERROR_CHECK(ldr_sensor_init());
    ESP_ERROR_CHECK(fan_control_init());
    ESP_ERROR_CHECK(led_strip_init());

    // Sensor tasks
    xTaskCreatePinnedToCore(dht11_task,       "dht11",  4096, NULL, 3, NULL, 0);
    xTaskCreatePinnedToCore(smoke_task,       "smoke",  8192, NULL, 3, NULL, 0);
    xTaskCreatePinnedToCore(ldr_task,         "ldr",    4096, NULL, 3, NULL, 0);
    xTaskCreatePinnedToCore(fast_sensor_task, "fast",   4096, NULL, 3, NULL, 1);

    // HTTP server
    if (!start_http_server()) {
        display_switch(SCREEN_ERROR, "HTTP server error!");
        return;
    }

    display_switch(SCREEN_IDLE, "Swipe RFID card");
    ESP_LOGI(TAG, "Hazır — RFID bekleniyor");

    // Ana döngü: RFID tarama
    rfid_card_t last_card  = {0};
    int         rfid_fails = 0;

    while (1) {
        rfid_card_t card;
        if (rfid_poll(&card)) {
            rfid_fails = 0;
            if (!rfid_uid_equal(&card, &last_card)) {
                last_card = card;
                char uid[32];
                rfid_uid_to_str(&card, uid, sizeof(uid));
                ESP_LOGI(TAG, "Kart: %s", uid);

                // Bilinen kartlar burada eşleştirilebilir
                // Şimdilik UID'yi doğrudan kullanıcı adı olarak sakla
                snprintf(g_username, sizeof(g_username), "%s", uid);
                g_rfid_scanned = true;

                // 1) Kart okundu ekranı
                char msg[80];
                snprintf(msg, sizeof(msg), "Welcome!\n%s", uid);
                display_switch(SCREEN_RFID_READ, msg);
                g_active_screen = SCREEN_RFID_READ;
                vTaskDelay(pdMS_TO_TICKS(2000));

                // 2) Karşılama ekranı (kullanıcı adıyla)
                display_switch(SCREEN_READY, g_username);
                g_active_screen = SCREEN_READY;
            }
        } else {
            if (++rfid_fails >= 5) { rfid_fails = 0; rfid_init(); }
        }
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}
