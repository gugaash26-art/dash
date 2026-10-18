#ifndef CARDASH_BOARD_CONFIG_H
#define CARDASH_BOARD_CONFIG_H

// Perfis de placa do OpenDash.
//
// O perfil e escolhido automaticamente pelas macros da plataforma Arduino.
// Para uma placa fora da lista, defina CARDASH_CUSTOM_PINS antes de incluir
// este arquivo e informe todos os pinos/macros usados pelo sketch.
//
// Aviso: placas de 3,3 V (ESP32, RP2040, Teensy) exigem divisores/adaptacao
// nos sinais analogicos de 5 V do carro. Veja arduino/README.md.

#if defined(CARDASH_CUSTOM_PINS)

#define BOARD_NAME "custom"
#ifndef ADC_BITS
#define ADC_BITS 10
#endif
#ifndef ADC_VREF
#define ADC_VREF 5.0
#endif
#ifndef ADC_MAX
#define ADC_MAX 1023.0
#endif
#ifndef HAS_ADC_RESOLUTION
#define HAS_ADC_RESOLUTION 0
#endif
#ifndef HAS_ADC_ATTENUATION
#define HAS_ADC_ATTENUATION 0
#endif
#ifndef INPUT_EXPANDER
#define INPUT_EXPANDER 0
#endif
#ifndef GPS_SOFTWARE
#define GPS_SOFTWARE 0
#endif


#define ADC_BITS 10
#define ADC_VREF 5.0
#define ADC_MAX 1023.0
#define HAS_ADC_RESOLUTION 0
#define HAS_ADC_ATTENUATION 0
#define INPUT_EXPANDER 0
#define GPS_SOFTWARE 0
#define GPS_RX_PIN 19
#define GPS_TX_PIN 18
#define FUEL_ADC_EMPTY 80
#define FUEL_ADC_FULL 980

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
#define PIN_REVERSE       46

#define PIN_OIL_PRESS     A0
#define PIN_FUEL_LEVEL    A1
#define PIN_OIL_TEMP      A2
#define PIN_BATT_SENSE    A3

#elif defined(ARDUINO_AVR_UNO) || defined(ARDUINO_AVR_NANO)

// Arduino Uno/Nano. Como faltam pinos para todos os sinais, as entradas
// digitais usam um expansor PCF8574 no barramento I2C (A4/A5).
// O GPS usa SoftwareSerial em D2 (RX) / D9 (TX).
#define BOARD_NAME "uno-nano"
#define ADC_BITS 10
#define ADC_VREF 5.0
#define ADC_MAX 1023.0
#define HAS_ADC_RESOLUTION 0
#define HAS_ADC_ATTENUATION 0
#define INPUT_EXPANDER 1
#define INPUT_EXPANDER_ADDR 0x20
#define EXPANDER_BASE 100
#define GPS_SOFTWARE 1
#define GPS_RX_PIN 2
#define GPS_TX_PIN 9
#define FUEL_ADC_EMPTY 80
#define FUEL_ADC_FULL 980

#define PIN_CS_CAN        10
#define PIN_BUZZER         7
#define PIN_LED            8
#define PIN_RELAY_FAN      5
#define PIN_RELAY_AC       6
#define PIN_HANDBRAKE      4
#define PIN_REVERSE        3

#define PIN_LEFT          (EXPANDER_BASE + 0)
#define PIN_RIGHT         (EXPANDER_BASE + 1)
#define PIN_HEADLIGHT     (EXPANDER_BASE + 2)
#define PIN_HIGHBEAM      (EXPANDER_BASE + 3)
#define PIN_SEATBELT      (EXPANDER_BASE + 4)
#define PIN_DOOR          (EXPANDER_BASE + 5)
#define PIN_HAZARD        (EXPANDER_BASE + 6)
#define PIN_IGNITION      (EXPANDER_BASE + 7)

#define PIN_OIL_PRESS     A0
#define PIN_FUEL_LEVEL    A1
#define PIN_OIL_TEMP      A2
#define PIN_BATT_SENSE    A3

#elif defined(ARDUINO_AVR_LEONARDO) || defined(ARDUINO_AVR_MICRO)

// Leonardo/Micro (ATmega32U4): I2C fica em D2/D3 e o SPI no conector ICSP.
// As entradas digitais tambem usam PCF8574; GPS por SoftwareSerial em D8/D9.
#define BOARD_NAME "leonardo"
#define ADC_BITS 10
#define ADC_VREF 5.0
#define ADC_MAX 1023.0
#define HAS_ADC_RESOLUTION 0
#define HAS_ADC_ATTENUATION 0
#define INPUT_EXPANDER 1
#define INPUT_EXPANDER_ADDR 0x20
#define EXPANDER_BASE 100
#define GPS_SOFTWARE 1
#define GPS_RX_PIN 8
#define GPS_TX_PIN 9
#define FUEL_ADC_EMPTY 80
#define FUEL_ADC_FULL 980

#define PIN_CS_CAN        10
#define PIN_BUZZER         7
#define PIN_LED           13
#define PIN_RELAY_FAN      5
#define PIN_RELAY_AC       6
#define PIN_HANDBRAKE      4
#define PIN_REVERSE       11

#define PIN_LEFT          (EXPANDER_BASE + 0)
#define PIN_RIGHT         (EXPANDER_BASE + 1)
#define PIN_HEADLIGHT     (EXPANDER_BASE + 2)
#define PIN_HIGHBEAM      (EXPANDER_BASE + 3)
#define PIN_SEATBELT      (EXPANDER_BASE + 4)
#define PIN_DOOR          (EXPANDER_BASE + 5)
#define PIN_HAZARD        (EXPANDER_BASE + 6)
#define PIN_IGNITION      (EXPANDER_BASE + 7)

#define PIN_OIL_PRESS     A0
#define PIN_FUEL_LEVEL    A1
#define PIN_OIL_TEMP      A2
#define PIN_BATT_SENSE    A3

#elif defined(ARDUINO_ARCH_ESP32)

#if defined(CONFIG_IDF_TARGET_ESP32S3) || defined(ARDUINO_ESP32S3_DEV)

#define BOARD_NAME "esp32s3"
#define ADC_BITS 12
#define ADC_VREF 3.3
#define ADC_MAX 4095.0
#define HAS_ADC_RESOLUTION 1
#define HAS_ADC_ATTENUATION 1
#define INPUT_EXPANDER 0
#define GPS_SOFTWARE 0
#define GPS_RX_PIN 44
#define GPS_TX_PIN 43
#define CARDASH_GPS_BEGIN() Serial1.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN)
#define FUEL_ADC_EMPTY 320
#define FUEL_ADC_FULL 3920

#define PIN_CS_CAN        10
#define PIN_BUZZER        40
#define PIN_LED           48
#define PIN_RELAY_FAN     38
#define PIN_RELAY_AC      39

#define PIN_LEFT           6
#define PIN_RIGHT          7
#define PIN_HEADLIGHT      8
#define PIN_HIGHBEAM       9
#define PIN_HANDBRAKE     15
#define PIN_SEATBELT      16
#define PIN_DOOR          17
#define PIN_HAZARD        18
#define PIN_IGNITION      21
#define PIN_REVERSE       47

#define PIN_OIL_PRESS      1
#define PIN_FUEL_LEVEL     2
#define PIN_OIL_TEMP       4
#define PIN_BATT_SENSE     5

#elif defined(CONFIG_IDF_TARGET_ESP32C3) || defined(ARDUINO_ESP32C3_DEV)

// ESP32-C3 tem poucos GPIOs; usa PCF8574 para as 8 entradas digitais.
#define BOARD_NAME "esp32c3"
#define ADC_BITS 12
#define ADC_VREF 3.3
#define ADC_MAX 4095.0
#define HAS_ADC_RESOLUTION 1
#define HAS_ADC_ATTENUATION 1
#define INPUT_EXPANDER 1
#define INPUT_EXPANDER_ADDR 0x20
#define EXPANDER_BASE 100
#define CARDASH_I2C_SDA 8
#define CARDASH_I2C_SCL 9
#define GPS_SOFTWARE 0
#define GPS_RX_PIN 20
#define GPS_TX_PIN 21
#define CARDASH_GPS_BEGIN() Serial1.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN)
#define FUEL_ADC_EMPTY 320
#define FUEL_ADC_FULL 3920

#define PIN_CS_CAN        10
#define PIN_BUZZER        15
#define PIN_LED           12
#define PIN_RELAY_FAN      4
#define PIN_RELAY_AC      14
#define PIN_HANDBRAKE     13
#define PIN_REVERSE       16

#define PIN_LEFT          (EXPANDER_BASE + 0)
#define PIN_RIGHT         (EXPANDER_BASE + 1)
#define PIN_HEADLIGHT     (EXPANDER_BASE + 2)
#define PIN_HIGHBEAM      (EXPANDER_BASE + 3)
#define PIN_SEATBELT      (EXPANDER_BASE + 4)
#define PIN_DOOR          (EXPANDER_BASE + 5)
#define PIN_HAZARD        (EXPANDER_BASE + 6)
#define PIN_IGNITION      (EXPANDER_BASE + 7)

#define PIN_OIL_PRESS      0
#define PIN_FUEL_LEVEL     1
#define PIN_OIL_TEMP       3
#define PIN_BATT_SENSE     4

#else

// ESP32 classico (DevKit/WROVER). Para ESP32-S2 ou variantes com pinagem
// diferente, use CARDASH_CUSTOM_PINS.
#define BOARD_NAME "esp32"
#define ADC_BITS 12
#define ADC_VREF 3.3
#define ADC_MAX 4095.0
#define HAS_ADC_RESOLUTION 1
#define HAS_ADC_ATTENUATION 1
#define INPUT_EXPANDER 0
#define GPS_SOFTWARE 0
#define GPS_RX_PIN 14
#define GPS_TX_PIN -1
#define CARDASH_GPS_BEGIN() Serial1.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN)
#define FUEL_ADC_EMPTY 320
#define FUEL_ADC_FULL 3920

#define PIN_CS_CAN         5
#define PIN_BUZZER        22
#define PIN_LED            2
#define PIN_RELAY_FAN     12
#define PIN_RELAY_AC      15

#define PIN_LEFT          25
#define PIN_RIGHT         26
#define PIN_HEADLIGHT     27
#define PIN_HIGHBEAM      32
#define PIN_HANDBRAKE     33
#define PIN_SEATBELT       4
#define PIN_DOOR          13
#define PIN_HAZARD        16
#define PIN_IGNITION      17
#define PIN_REVERSE       21

#define PIN_OIL_PRESS     34
#define PIN_FUEL_LEVEL    35
#define PIN_OIL_TEMP      36
#define PIN_BATT_SENSE    39

#endif

#elif defined(ARDUINO_ARCH_RP2040)

#define BOARD_NAME "rp2040"
#define ADC_BITS 12
#define ADC_VREF 3.3
#define ADC_MAX 4095.0
#define HAS_ADC_RESOLUTION 1
#define HAS_ADC_ATTENUATION 0
#define INPUT_EXPANDER 0
#define GPS_SOFTWARE 0
#define GPS_RX_PIN 1
#define GPS_TX_PIN 0
#define CARDASH_GPS_BEGIN() do { Serial1.setRX(GPS_RX_PIN); Serial1.setTX(GPS_TX_PIN); Serial1.begin(GPS_BAUD); } while (0)
#define FUEL_ADC_EMPTY 320
#define FUEL_ADC_FULL 3920

#define PIN_CS_CAN        17
#define PIN_BUZZER        12
#define PIN_LED           25
#define PIN_RELAY_FAN     13
#define PIN_RELAY_AC      14

#define PIN_LEFT           2
#define PIN_RIGHT          3
#define PIN_HEADLIGHT      4
#define PIN_HIGHBEAM       5
#define PIN_HANDBRAKE      6
#define PIN_SEATBELT       7
#define PIN_DOOR           8
#define PIN_HAZARD         9
#define PIN_IGNITION      10
#define PIN_REVERSE       11

#define PIN_OIL_PRESS     A0
#define PIN_FUEL_LEVEL    A1
#define PIN_OIL_TEMP      A2
#define PIN_BATT_SENSE    A3

#elif defined(ARDUINO_TEENSY40) || defined(ARDUINO_TEENSY41)

#define BOARD_NAME "teensy4"
#define ADC_BITS 12
#define ADC_VREF 3.3
#define ADC_MAX 4095.0
#define HAS_ADC_RESOLUTION 1
#define HAS_ADC_ATTENUATION 0
#define INPUT_EXPANDER 0
#define GPS_SOFTWARE 0
#define GPS_RX_PIN 0
#define GPS_TX_PIN 1
#define FUEL_ADC_EMPTY 320
#define FUEL_ADC_FULL 3920

#define PIN_CS_CAN        10
#define PIN_BUZZER        22
#define PIN_LED           23
#define PIN_RELAY_FAN     20
#define PIN_RELAY_AC      21

#define PIN_LEFT           2
#define PIN_RIGHT          3
#define PIN_HEADLIGHT      4
#define PIN_HIGHBEAM       5
#define PIN_HANDBRAKE      6
#define PIN_SEATBELT       7
#define PIN_DOOR           8
#define PIN_HAZARD         9
#define PIN_IGNITION      24
#define PIN_REVERSE       25

#define PIN_OIL_PRESS     A0
#define PIN_FUEL_LEVEL    A1
#define PIN_OIL_TEMP      A2
#define PIN_BATT_SENSE    A3

#else

#error "Placa nao suportada. Defina CARDASH_CUSTOM_PINS e a pinagem antes de incluir config.h."

#endif

#ifndef BOARD_NAME
#define BOARD_NAME "custom"
#endif
#ifndef ADC_BITS
#define ADC_BITS 10
#endif
#ifndef ADC_VREF
#define ADC_VREF 5.0
#endif
#ifndef ADC_MAX
#define ADC_MAX 1023.0
#endif
#ifndef HAS_ADC_RESOLUTION
#define HAS_ADC_RESOLUTION 0
#endif
#ifndef HAS_ADC_ATTENUATION
#define HAS_ADC_ATTENUATION 0
#endif
#ifndef INPUT_EXPANDER
#define INPUT_EXPANDER 0
#endif
#ifndef INPUT_EXPANDER_ADDR
#define INPUT_EXPANDER_ADDR 0x20
#endif
#ifndef EXPANDER_BASE
#define EXPANDER_BASE 100
#endif
#ifndef GPS_SOFTWARE
#define GPS_SOFTWARE 0
#endif
#ifndef GPS_RX_PIN
#define GPS_RX_PIN 19
#endif
#ifndef GPS_TX_PIN
#define GPS_TX_PIN 18
#endif
#ifndef FUEL_ADC_EMPTY
#define FUEL_ADC_EMPTY 80
#endif
#ifndef FUEL_ADC_FULL
#define FUEL_ADC_FULL 980
#endif

#endif
