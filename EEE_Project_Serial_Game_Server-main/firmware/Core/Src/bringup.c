/**
  * bringup.c - Stage 4 hardware bring-up image. NOT part of the game firmware.
  *
  * Build:  make -C firmware BRINGUP=1      (output: firmware/build/bringup/BringUp.*)
  * This image deliberately prints on the UART; the game image never does.
  *
  * Tests (see docs/stages.md Stage 4 and docs/bringup-log.md):
  *   T1 LED   : red x3 then green x3 at start. Note which colour is which.
  *   T2 TX    : "BRINGUP TX n" once per second at 115200 8N1.
  *   T3 echo  : every received byte is sent straight back (polled).
  *   T4 SW0   : while SW0 (PA0, active low) is held the LED is red, and
  *              "SW0 DOWN"/"SW0 UP" is sent on each change.
  */
#include "board.h"

#ifndef UART_AF
#error "UART_AF is not set: read it from the STM32F051x8 datasheet Table 14 and define it in board.h"
#endif

#define BAUD        115200u
#define PCLK_HZ     8000000u    /* HSI, APB /1 (SystemClock_Config in main.c) */

static void delay_ms(uint32_t ms)
{
    uint32_t t0 = HAL_GetTick();
    while ((uint32_t)(HAL_GetTick() - t0) < ms) { }
}

static void led_set(int red, int green)
{
    LED_RED_GPIO->BSRR   = red   ? (1UL << LED_RED_PIN)   : (1UL << (LED_RED_PIN + 16u));
    LED_GREEN_GPIO->BSRR = green ? (1UL << LED_GREEN_PIN) : (1UL << (LED_GREEN_PIN + 16u));
}

static void uart_putc(char c)
{
    while (!(USART1->ISR & USART_ISR_TXE)) { }
    USART1->TDR = (uint8_t)c;
}

static void uart_puts(const char *s)
{
    while (*s) { uart_putc(*s++); }
}

static void uart_put_u32(uint32_t v)
{
    char buf[11];
    int n = 0;
    do { buf[n++] = (char)('0' + v % 10u); v /= 10u; } while (v);
    while (n) { uart_putc(buf[--n]); }
}

static void init_gpio_uart(void)
{
    RCC->AHBENR  |= RCC_AHBENR_GPIOAEN | RCC_AHBENR_GPIOBEN;
    RCC->APB2ENR |= RCC_APB2ENR_USART1EN;
    (void)RCC->APB2ENR;

    /* LEDs: PB10, PB11 outputs. */
    GPIOB->MODER = (GPIOB->MODER & ~((3UL << 20) | (3UL << 22))) | (1UL << 20) | (1UL << 22);

    /* SW0 PA0: input with pull-up. */
    GPIOA->MODER &= ~(3UL << (2u * BTN_SW0_PIN));
    GPIOA->PUPDR  = (GPIOA->PUPDR & ~(3UL << (2u * BTN_SW0_PIN))) | (1UL << (2u * BTN_SW0_PIN));

    /* PA9, PA10: alternate function UART_AF (AFR[1] holds pins 8..15). */
    GPIOA->MODER = (GPIOA->MODER & ~((3UL << 18) | (3UL << 20))) | (2UL << 18) | (2UL << 20);
    GPIOA->AFR[1] = (GPIOA->AFR[1] & ~((0xFUL << 4) | (0xFUL << 8)))
                  | ((uint32_t)UART_AF << 4) | ((uint32_t)UART_AF << 8);

    /* USART1: 8N1, oversampling by 16, polled. BRR = fPCLK / baud. */
    USART1->CR1 = 0;
    USART1->BRR = (PCLK_HZ + BAUD / 2u) / BAUD;
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
}

void bringup_run(void)
{
    init_gpio_uart();

    for (int i = 0; i < 3; i++) { led_set(1, 0); delay_ms(250); led_set(0, 0); delay_ms(250); }
    for (int i = 0; i < 3; i++) { led_set(0, 1); delay_ms(250); led_set(0, 0); delay_ms(250); }

    uint32_t last_tx = HAL_GetTick();
    uint32_t n = 0;
    int sw_prev = 0;

    for (;;)
    {
        /* T3 echo */
        uint32_t isr = USART1->ISR;
        if (isr & USART_ISR_ORE) { USART1->ICR = USART_ICR_ORECF; }
        if (isr & USART_ISR_RXNE) { uart_putc((char)USART1->RDR); }

        /* T4 button */
        int sw = !(BTN_GPIO->IDR & (1UL << BTN_SW0_PIN));
        if (sw != sw_prev)
        {
            sw_prev = sw;
            led_set(sw, 0);
            uart_puts(sw ? "SW0 DOWN\r\n" : "SW0 UP\r\n");
        }

        /* T2 transmit */
        if ((uint32_t)(HAL_GetTick() - last_tx) >= 1000u)
        {
            last_tx = HAL_GetTick();
            uart_puts("BRINGUP TX ");
            uart_put_u32(n++);
            uart_puts("\r\n");
        }
    }
}
