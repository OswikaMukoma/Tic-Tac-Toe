/**
  * uart.c - USART1 driver, CMSIS registers (decision D-003). Pins and AF from board.h
  * (PA9/PA10, AF1: datasheet Table 14, decision D-016). Bring-up verified 21 Oct.
  */
#include "board.h"
#include "uart.h"

#define BAUD     115200u
#define PCLK_HZ  8000000u            /* HSI, APB /1: SystemClock_Config in main.c */
#define RING_SZ  128u                /* power of two */

static volatile uint8_t  ring[RING_SZ];
static volatile uint16_t head;       /* written by the ISR only  */
static volatile uint16_t tail;       /* written by the main loop */
static volatile uint32_t dropped;
static volatile uint32_t overruns;

void uart_init(void)
{
    RCC->AHBENR  |= RCC_AHBENR_GPIOAEN;
    RCC->APB2ENR |= RCC_APB2ENR_USART1EN;
    (void)RCC->APB2ENR;

    UART_GPIO->MODER = (UART_GPIO->MODER & ~((3UL << (2u * UART_TX_PIN)) | (3UL << (2u * UART_RX_PIN))))
                     | (2UL << (2u * UART_TX_PIN)) | (2UL << (2u * UART_RX_PIN));
    UART_GPIO->AFR[1] = (UART_GPIO->AFR[1] & ~((0xFUL << ((UART_TX_PIN - 8u) * 4u)) | (0xFUL << ((UART_RX_PIN - 8u) * 4u))))
                      | ((uint32_t)UART_AF << ((UART_TX_PIN - 8u) * 4u))
                      | ((uint32_t)UART_AF << ((UART_RX_PIN - 8u) * 4u));

    USART1->CR1 = 0;
    USART1->BRR = (PCLK_HZ + BAUD / 2u) / BAUD;                 /* 69 */
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_RXNEIE | USART_CR1_UE;
    NVIC_SetPriority(USART1_IRQn, 1);
    NVIC_EnableIRQ(USART1_IRQn);
}

void USART1_IRQHandler(void)
{
    uint32_t isr = USART1->ISR;
    if (isr & (USART_ISR_ORE | USART_ISR_FE | USART_ISR_NE)) {
        if (isr & USART_ISR_ORE) { overruns++; }
        USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NCF;
    }
    if (isr & USART_ISR_RXNE) {
        uint8_t b = (uint8_t)USART1->RDR;                       /* reading clears RXNE */
        uint16_t next = (uint16_t)((head + 1u) & (RING_SZ - 1u));
        if (next != tail) { ring[head] = b; head = next; } else { dropped++; }
    }
}

int uart_rx_pop(uint8_t *b)
{
    if (tail == head) { return 0; }
    *b = ring[tail];
    tail = (uint16_t)((tail + 1u) & (RING_SZ - 1u));
    return 1;
}

void uart_tx(const char *data, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        while (!(USART1->ISR & USART_ISR_TXE)) { }
        USART1->TDR = (uint8_t)data[i];
    }
    while (!(USART1->ISR & USART_ISR_TC)) { }
}

uint32_t uart_rx_dropped(void)  { return dropped; }
uint32_t uart_rx_overruns(void) { return overruns; }
