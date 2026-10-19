# OpenDash no Raspberry Pi

O painel roda igual em **Orange Pi**, **Raspberry Pi** e **DietPi**. Este guia cobre
o que muda no Raspberry Pi: sistema, serial (ESP32/GPS), câmera CSI de ré e tela
HDMI. Em DietPi (qualquer placa), veja também [`dietpi.md`](dietpi.md).

Testado em **Raspberry Pi 4 / 5** com **Raspberry Pi OS (Bookworm, 64 bits)**. Funciona
também em Pi 3 (mais lento) e no **Pi Zero 2 W** (use resolução modesta, ex. 1024×600).

## 1. Sistema

Instale o **Raspberry Pi OS com desktop (X11)** — evite o *Wayland/labwc* padrão, que
dificulta o kiosk; se ficar no Wayland, selecione a sessão **X11** no `raspi-config`
(6 → A6) ou rode `sudo raspi-config nonint do_wayland 0`.

```bash
sudo apt update && sudo apt full-upgrade -y
git clone <este-repositorio> car-dash
cd car-dash
./install.sh --check          # diagnóstico (não altera nada)
./install.sh --app --kiosk    # app nativo (WebKitGTK) + autostart do kiosk
```

O instalador **detecta o Raspberry Pi** e aplica sozinho (com backup do `config.txt`):

- `enable_uart=1` — habilita a UART de hardware (GPS NMEA);
- `camera_auto_detect=1` — habilita a câmera CSI;
- `hdmi_force_hotplug=1` — mantém a saída HDMI ativa mesmo sem detectar a tela na hora.

Para **não** aplicar isso, use `--no-rpi`. Depois, **reinicie** para valer.

> **DietPi no Raspberry Pi.** O instalador detecta o DietPi e configura o kiosk
> por `dietpi-autostart 17` (sem depender do desktop). O guia completo está em
> [`dietpi.md`](dietpi.md).

## 2. ESP32 (serial)

O microcontrolador (ESP32, ESP32, Pico/RP2040, Teensy ou Uno/Nano) se
conecta por **USB**. No Raspberry Pi ele aparece em `/dev/ttyACM0` (ou
`/dev/ttyUSB0`). Adicione seu usuário ao grupo `dialout` (o instalador já faz) e
selecione a porta em **Ajustes → Conexão**, ou deixe `serial.port: auto`.
A pinagem de cada placa está em [`../arduino/README.md`](../arduino/README.md).

Se preferir a **UART de hardware** (GPIO 14/15), desative o console serial
(`sudo raspi-config nonint do_serial_cons 1`) e ligue:

```
enable_uart=1
dtoverlay=disable-bt      # opcional: libera a UART boa no Pi 4/5
```

## 3. Câmera de ré

Duas opções:

- **Webcam USB** — ligue e pronto (V4L2). Instale as dependências com
  `./install.sh --camera` (`ffmpeg` + `v4l-utils`).
- **Câmera CSI (ribbon)** — habilitada pelo instalador no `/boot/firmware/config.txt`
  (`camera_auto_detect=1`). Instale `rpicam-apps` (Já vem no Pi OS atual): o servidor usa
  `rpicam-vid`/`libcamera-vid`.

No painel, **Ajustes → Câmera de ré** controla o disparo (`ao engatar a ré`, `manual`,
`sempre`, `desligado`), backend, resolução, linhas guia e espelhamento. Ao engatar a **ré**,
a imagem abre em **tela cheia** (via `/camera/stream`, MJPEG). No ESP32, o sinal de ré
entra em `PIN_REVERSE` (`arduino/car_dash/board_config.h`) e vira o campo `rev` no JSON.

Teste rápido (modo simulação):

```bash
curl -X POST localhost:8080/api/command -H 'Content-Type: application/json' -d '{"cmd":"reverse","on":true}'
```

## 4. Tela

O painel se adapta a **qualquer monitor**. Em **Ajustes → Tela e escala** você informa as
**polegadas** (ex.: `7`) e o servidor calcula a escala ideal; ou fixa `escala`/`largura ×
altura`/`orientação`. Para fixar a resolução no boot do kiosk: `./install.sh --screen=1024x600`.

## 5. Diferenças vs. Orange Pi

| Item | Raspberry Pi | Orange Pi |
|---|---|---|
| Placa | Pi 3/4/5, Zero 2 W | Zero 2 / 3 / outros ARM |
| Câmera CSI | `libcamera`/`rpicam-vid` (nativo) | depende do BSP |
| Kiosk | app nativo WebKitGTK ou Chromium | idem |
| Ajustes de boot | `/boot/firmware/config.txt` | `/boot/armbianEnv.txt` (não alterado) |

## 6. Solução de problemas

- **Tela preta no boot**: confira `hdmi_force_hotplug=1` e o cabo; teste
  `xrandr` no terminal do kiosk.
- **Sem serial**: `ls -l /dev/ttyACM*`, confirme o grupo `dialout` (relogine) e veja
  `journalctl -u cardash -f`.
- **Câmera**: `rpicam-hello` (ou `libcamera-hello`) deve mostrar imagem; se não, revise o
  cabo CSI e `dmesg | tail`. Webcam: `v4l2-ctl --list-devices`.
- **Kiosk não abre**: rode `/car-dash/kiosk/kiosk.sh` à mão e veja a mensagem;
  confirme `DISPLAY=:0` e a sessão **X11**.
