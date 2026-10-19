#ifndef CARDASH_CONFIG_H
#define CARDASH_CONFIG_H

#include "board_config.h"

#define FW_VERSION 2

// Pinagem, ADC e UART de GPS ficam em board_config.h.
// Ajustes gerais do veiculo:
#define INPUT_ACTIVE_LOW   1
#define DEBOUNCE_MS       25

#define BATT_DIVIDER      4.9
#define OIL_PSI_MIN_V     0.5
#define OIL_PSI_MAX_V     4.5
#define OIL_PSI_MAX       100.0
#define OILT_OFFSET_V     0.0
#define OILT_SCALE        50.0

#define CAN_CS_PIN        PIN_CS_CAN
#define CAN_CLOCK_16MHZ   1
#define CAN_SPEED_500K    1
#define DEMO_WITHOUT_CAN  1

#define SERIAL_BAUD       115200
#define JSON_INTERVAL_MS  100
#define ANALOG_INTERVAL_MS 250
#define OBD_SLOT_MS       120
#define OBD_TIMEOUT_MS    90
#define OBD_RETRY_MAX     3

#define GPS_ENABLED       1
#define GPS_BAUD          9600
#define GPS_TIMEOUT_MS    3000

#if defined(__AVR_ATmega328P__) || defined(__AVR_ATmega168__) || defined(__AVR_ATmega32U4__)
#define STATE_SIZE        540
#define RX_BUF_SIZE        80
#define GPS_BUF_SIZE       92
#define DTC_MAX             8
#define RX_DATA_SIZE       24
#else
#define STATE_SIZE        900
#define RX_BUF_SIZE       384
#define GPS_BUF_SIZE      120
#define DTC_MAX            16
#define RX_DATA_SIZE       64
#endif

#endif
