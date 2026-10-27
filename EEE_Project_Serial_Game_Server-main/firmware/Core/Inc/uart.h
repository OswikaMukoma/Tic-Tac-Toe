/**
  * uart.h - USART1 (PA9 TX / PA10 RX, ST-Link VCP) 115200 8N1, register level.
  * RX: interrupt -> ring buffer; the main loop pops bytes. TX: polled, bounded
  * (a reply is at most 25 bytes, about 2.2 ms), while RX keeps filling the ring.
  */
#ifndef UART_H
#define UART_H

#include <stddef.h>
#include <stdint.h>

void     uart_init(void);
int      uart_rx_pop(uint8_t *b);              /* 1 if a byte was returned, 0 if empty */
void     uart_tx(const char *data, size_t n);
uint32_t uart_rx_dropped(void);                /* bytes lost to a full ring (should stay 0) */
uint32_t uart_rx_overruns(void);               /* hardware overrun events */

#endif
