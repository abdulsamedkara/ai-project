#include "buzzer.h"
#include "config.h"
#include "driver/gpio.h"

esp_err_t buzzer_init(void)
{
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << BUZZER_GPIO,
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&io);
    if (err == ESP_OK)
        gpio_set_level(BUZZER_GPIO, 0);
    return err;
}

void buzzer_on(void)  { gpio_set_level(BUZZER_GPIO, 1); }
void buzzer_off(void) { gpio_set_level(BUZZER_GPIO, 0); }
