#ifndef CARDASH_CONFIG_H
#define CARDASH_CONFIG_H

#define FW_VERSION 1

#define PIN_CS_CAN        10
#define PIN_BUZZER        12
#define PIN_LED           13
#define PIN_RELAY_FAN     44
#define PIN_RELAY_AC      45

#define PIN_LEFT           2
#define PIN_RIGHT          3
#define PIN_HEADLIGHT      4
#define PIN_HIGHBEAM       5
#define PIN_HANDBRAKE      6
#define PIN_SEATBELT       7
#define PIN_DOOR           8
#define PIN_HAZARD         9
#define PIN_IGNITION      22
#define PIN_REVERSE       46   // sinal da marcha à ré (câmera de ré). Ativo conforme INPUT_ACTIVE_LOW.

#define INPUT_ACTIVE_LOW   1
#define DEBOUNCE_MS       25

#define PIN_OIL_PRESS     A0
#define PIN_FUEL_LEVEL    A1
#define PIN_OIL_TEMP      A2
#define PIN_BATT_SENSE    A3

#define ADC_VREF          5.0
#define BATT_DIVIDER      4.0
#define OIL_PSI_MIN_V     0.5
#define OIL_PSI_MAX_V     4.5
#define OIL_PSI_MAX       100.0
#define FUEL_ADC_EMPTY    80
#define FUEL_ADC_FULL     980
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

// GPS NMEA conectado ao Serial1 (Mega: RX1=pino 19, TX1=pino 18).
// Aceita NEO-6M / NEO-8M / NEO-M8N (9600 ou 38400 baud).
#define GPS_ENABLED       1
#define GPS_BAUD          9600
#define GPS_TIMEOUT_MS    3000

#define STATE_SIZE        900
#define RX_BUF_SIZE       384
#define GPS_BUF_SIZE      120

#endif
