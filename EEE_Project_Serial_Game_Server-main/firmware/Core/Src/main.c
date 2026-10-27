/**
  * main.c - Serial Game Server (Stages 5 and 6).
  *
  * Main loop only: bytes arrive by USART1 interrupt into a ring buffer (uart.c);
  * this loop feeds them to the portable server (server.c + game.c), sends the one
  * reply, then updates the button and the status LED. The game UART carries
  * protocol replies ONLY. Nothing else is ever printed on it (see CLAUDE.md).
  */

#include "main.h"
#include "board.h"
#include "server.h"
#include "uart.h"
#ifdef BRINGUP
extern void bringup_run(void);   /* Stage 4 image only, never returns */
#endif

#define BTN_DEBOUNCE_MS   30u
#define LED_BLINK_HALF_MS 250u   /* 2 Hz: 250 ms on, 250 ms off */

void SystemClock_Config(void);

static server_t srv;

static void led_write(int red, int green)
{
    LED_RED_GPIO->BSRR   = red   ? (1UL << LED_RED_PIN)   : (1UL << (LED_RED_PIN + 16u));
    LED_GREEN_GPIO->BSRR = green ? (1UL << LED_GREEN_PIN) : (1UL << (LED_GREEN_PIN + 16u));
}

/* protocol.md section 9: IDLE off; IN_PROGRESS green = X to move, red = O to move;
 * GAME_OVER both blink together at 2 Hz. */
static void led_update(uint32_t now)
{
    switch (game_get_state(&srv.game)) {
    case GAME_IN_PROGRESS:
        if (game_side_to_move(&srv.game) == 'X') { led_write(0, 1); } else { led_write(1, 0); }
        break;
    case GAME_OVER: {
        int on = ((now / LED_BLINK_HALF_MS) & 1u) == 0u;
        led_write(on, on);
        break;
    }
    default:
        led_write(0, 0);
        break;
    }
}

/* SW0 (PA0, active low) debounced; a press is a local reset to IDLE, no message. */
static void button_poll(uint32_t now)
{
    static uint32_t since = 0;
    static uint8_t stable = 0;       /* debounced level: 1 = pressed */
    static uint8_t raw_prev = 0;
    uint8_t raw = (BTN_GPIO->IDR & (1UL << BTN_SW0_PIN)) == 0u;
    if (raw != raw_prev) { raw_prev = raw; since = now; }
    if (raw != stable && (uint32_t)(now - since) >= BTN_DEBOUNCE_MS) {
        stable = raw;
        if (stable) { server_reset(&srv); }
    }
}

static void gpio_init(void)
{
    RCC->AHBENR |= RCC_AHBENR_GPIOAEN | RCC_AHBENR_GPIOBEN;
    (void)RCC->AHBENR;
    /* PB10, PB11 push-pull outputs. */
    GPIOB->MODER = (GPIOB->MODER & ~((3UL << (2u * LED_RED_PIN)) | (3UL << (2u * LED_GREEN_PIN))))
                 | (1UL << (2u * LED_RED_PIN)) | (1UL << (2u * LED_GREEN_PIN));
    /* PA0 input, pull-up. */
    BTN_GPIO->MODER &= ~(3UL << (2u * BTN_SW0_PIN));
    BTN_GPIO->PUPDR  = (BTN_GPIO->PUPDR & ~(3UL << (2u * BTN_SW0_PIN))) | (1UL << (2u * BTN_SW0_PIN));
    led_write(0, 0);
}

int main(void)
{
    HAL_Init();               /* starts SysTick at 1 ms (HAL_GetTick) */
    SystemClock_Config();
#ifdef BRINGUP
    bringup_run();
#endif
    gpio_init();
    server_init(&srv);
    uart_init();

    char out[SERVER_REPLY_MAX];
    for (;;)
    {
        uint8_t b;
        while (uart_rx_pop(&b)) {                       /* never waits: drains what is there */
            size_t n = server_rx(&srv, b, HAL_GetTick(), out, sizeof out);
            if (n) { uart_tx(out, n); }
        }
        uint32_t now = HAL_GetTick();   /* read AFTER the drain so it is never older than last_ms */
        size_t n = server_tick(&srv, now, out, sizeof out);
        if (n) { uart_tx(out, n); }
        button_poll(now);
        led_update(now);
    }
}

/** System clock: HSI, no PLL, AHB /1, APB /1 (8 MHz). Same as the course base. */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    RCC_OscInitStruct.OscillatorType      = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState            = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState        = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                     | RCC_CLOCKTYPE_PCLK1;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_HSI;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
    {
        Error_Handler();
    }
}

void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}
