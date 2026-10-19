# Firmware OpenDash

O sketch `car_dash/car_dash.ino` le CAN/OBD-II, entradas digitais e sensores
analógicos e envia JSON pela serial a 115200 baud. A pinagem e o ADC são
selecionados em `car_dash/board_config.h` conforme a placa.

## Placas suportadas

| Placa | Perfil | Status | Observação |
|---|---|---|---|
| ESP32 DevKit clássico | `esp32` | completo | 3,3 V; pinagem direta; alvo principal |
| ESP32-S3 | `esp32s3` | experimental | 3,3 V; pinagem direta |
| ESP32-C3 | `esp32c3` | experimental | 3,3 V; exige expansor PCF8574 |
| Raspberry Pi Pico/RP2040 | `rp2040` | experimental | 3,3 V; pinagem direta |
| Teensy 4.0/4.1 | `teensy4` | experimental | 3,3 V; pinagem direta |
| Arduino Uno/Nano | `uno-nano` | legado | expansor PCF8574; GPS por SoftwareSerial |
| Arduino Leonardo/Micro | `leonardo` | legado | PCF8574; I2C em D2/D3; GPS em D8/D9 |
| Outra | `custom` | manual | defina `CARDASH_CUSTOM_PINS` e a pinagem |

> **Alvo do projeto: ESP32 DevKit clássico.** As demais placas continuam no
> `board_config.h` para compatibilidade, mas o tutorial e a montagem usam a
> pinagem do ESP32.

> **Placas de 3,3 V:** os sinais analógicos do carro chegam a 5 V. Use divisor
> de tensão (ou sensor 3,3 V) em GPIO34/35/36/39. Para a bateria, use **39 kΩ
> e 10 kΩ** (saída ≈2,45 V em 12 V e ≈2,94 V em 14,4 V) e ajuste
> `BATT_DIVIDER` para `4.9`. O MCP2515 também deve ser de 3,3 V ou ter level
> shifter.

## Bibliotecas

- **MCP_CAN** de coryjfowler (testado com 1.5.1).
- `SPI`, `Wire` e `SoftwareSerial` já vêm com as plataformas Arduino/ESP32/RP2040.
- Para ESP32, instale o core `esp32:esp32` (2.x ou 3.x).
- Para RP2040, use o core **Arduino-Pico** (Earle Philhower).

## Pinagem por placa

### ESP32 (DevKit clássico)

| Sinal | GPIO | Sinal | GPIO |
|---|---|---|---|
| CAN CS | 5 | Buzzer | 22 |
| CAN SCK | 18 | LED | 2 |
| CAN MISO | 19 | Relé ventilador | 12 |
| CAN MOSI | 23 | Relé A/C | 15 |
| Analógico óleo | 34 | Seta esquerda | 25 |
| Analógico combustível | 35 | Seta direita | 26 |
| Analógico temp. óleo | 36 | Farol baixo | 27 |
| Analógico bateria | 39 | Farol alto | 32 |
| GPS RX | 14 | Freio de mão | 33 |
| GPS TX | — | Cinto | 4 |
|  |  | Porta | 13 |
|  |  | Alerta | 16 |
|  |  | Ignição | 17 |
|  |  | Ré | 21 |

O módulo CAN deve ser alimentado em **3,3 V** (ou usar level shifter nos sinais
SPI). O GPS usa `GPIO14` como RX; o TX do ESP32 não é usado neste perfil.

### Arduino Uno/Nano (PCF8574 obrigatório)

| Sinal | Pino | Sinal | Pino |
|---|---|---|---|
| CAN CS | D10 | Buzzer | D7 |
| CAN SCK | D13 | LED | D8 |
| CAN MOSI | D11 | Relé ventilador | D5 |
| CAN MISO | D12 | Relé A/C | D6 |
| I2C SDA | A4 | Freio de mão | D4 |
| I2C SCL | A5 | Ré | D3 |
| GPS RX (SoftwareSerial) | D2 | GPS TX | D9 |
| Analógico óleo | A0 | Combustível | A1 |
| Temp. óleo | A2 | Bateria | A3 |

O PCF8574 (endereço `0x20`) fornece: seta esquerda, seta direita, farol baixo,
farol alto, cinto, porta, alerta e ignição (bits 0–7). As entradas são ativas
em LOW, com pull-up no módulo.

### ESP32-S3 / C3, RP2040 e Teensy

A pinagem está em `board_config.h`. Para variantes diferentes (ESP32-S2,
ESP32-S3 com outra placa, Pico W etc.), defina `CARDASH_CUSTOM_PINS` e os pinos
no topo de `config.h` antes do `#include "board_config.h"`, ou edite o perfil.

## Personalização

1. Abra `car_dash/config.h` para calibrar sensores, CAN e intervalos.
2. Para pinos diferentes, crie um bloco antes do include:
   ```cpp
   #define CARDASH_CUSTOM_PINS
   #define PIN_CS_CAN 10
   #define PIN_BUZZER 12
   // ... todos os PIN_*, ADC_*, GPS_* usados
   #include "board_config.h"
   ```
3. Para uma placa fora da lista, o build falha com mensagem pedindo
   `CARDASH_CUSTOM_PINS`; isso evita gravar uma pinagem errada por engano.

## Compilação de teste

```bash
arduino-cli core install esp32:esp32
arduino-cli lib install mcp_can
arduino-cli compile --fqbn esp32:esp32:esp32 arduino/car_dash
```

O alvo principal é o **ESP32 DevKit clássico**. As compilações AVR continuam
disponíveis para as placas legadas, mas não são o foco do projeto.

## JSON enviado

A versão 2 acrescenta `board` e `adc`:

```json
{"v":2,"board":"esp32","adc":12,"ms":12345,"obd":1,"speed":64, ...}
```

O servidor aceita chaves extras; a tela de diagnóstico mostra a placa e a
resolução do ADC.
