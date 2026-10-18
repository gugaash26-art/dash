# OpenDash no DietPi (Orange Pi Zero 3 em diante)

O OpenDash roda no **DietPi** em placas **Orange Pi Zero 3, Zero 3W, Zero 2W,
Orange Pi 3/3B/4/4 Pro/5/5 Pro** e modelos ARM equivalentes. O instalador detecta
o DietPi sozinho e troca o autostart de desktop pelo **`dietpi-autostart 17`**
(script custom com autologin), que funciona **sem desktop** e também em duas telas.

> DietPi é Debian enxuto para SBCs. Para as imagens oficiais e a lista atualizada
> de placas, veja <https://dietpi.com/#downloadinfo>. O DietPi **10.6+** traz
> imagens oficiais para Orange Pi Zero 3W e Orange Pi 4 Pro; Zero 3, Zero 2W e
> Orange Pi 3/4/5 já são suportados nas versões anteriores.

## 1. Gravar a imagem e primeiro boot

1. Baixe a imagem do DietPi para a sua placa e grave no cartão (Etcher, Rufus ou `dd`).
2. No primeiro boot, entre como `root` (senha inicial `dietpi`) e conclua o
   assistente. Ajuste fuso, locale, teclado e vídeo em `dietpi-config`.
3. Atualize o sistema e reinicie:

```bash
dietpi-update
sudo reboot
```

4. Conecte a rede. **Ethernet é o caminho mais simples**; para Wi-Fi use
   `dietpi-config` → Network Options → Wi-Fi (o DietPi usa `wpa_supplicant`,
   não o NetworkManager).

## 2. Instalar o OpenDash

```bash
sudo apt update
sudo apt install -y git
sudo git clone <este-repositorio> /opt/car-dash
cd /opt/car-dash

./install.sh --check          # diagnóstico: não altera nada
sudo ./install.sh             # servidor + serviço cardash.service

# escolha o modo do painel:
sudo ./install.sh --kiosk             # uma tela (Chromium)
sudo ./install.sh --app --kiosk       # uma tela (app nativo WebKitGTK)
sudo ./install.sh --app --duo         # duas telas: painel completo + cluster em barra
sudo ./install.sh --app --cluster     # duas telas: painel completo + velocímetro

sudo reboot
```

O instalador, quando detecta DietPi:

- instala **X11** (`dietpi-software install 6`) e, para navegador,
  **Chromium** (`dietpi-software install 113`) — ou as dependências do app
  nativo WebKitGTK;
- grava `/var/lib/dietpi/dietpi-autostart/custom.sh` apontando para
  `kiosk/dietpi-kiosk.sh`;
- ativa `dietpi-autostart 17` (custom script em foreground, com autologin);
- ajusta `AUTO_SETUP_AUTOSTART_LOGIN_USER` em `/boot/dietpi.txt` para o usuário
  que rodou o instalador (backup em `/boot/dietpi.txt.opendash.bak`);
- mantém o **`cardash.service`** (servidor) habilitado no boot.

> **Usuário do kiosk.** Se você clonar em `/root` e instalar como root, o kiosk
> roda como root (o Chromium usa `--no-sandbox` e o WebKit desativa o sandbox).
> O recomendado é clonar em `/opt/car-dash` e instalar com `sudo` a partir do
> usuário `dietpi`: o autologin e o kiosk ficam no usuário `dietpi`.
> Para forçar outro usuário: `sudo CARDASH_USER=dietpi ./install.sh --kiosk`.

Modos disponíveis (os mesmos das outras distros):

| Comando | Tela 1 | Tela 2 |
|---|---|---|
| `--kiosk` | painel completo (menus) | — |
| `--kiosk-bar` | — | cluster em barra |
| `--kiosk-cluster` | — | velocímetro (sem menus) |
| `--duo` | painel completo | cluster em barra |
| `--cluster` | painel completo | velocímetro |
| `--app` | usa WebKitGTK em vez do Chromium | idem |

## 3. Como o autostart funciona

```
dietpi-autostart 17
  └─ /var/lib/dietpi/dietpi-autostart/custom.sh
       └─ kiosk/dietpi-kiosk.sh        (espera o servidor, sobe o X11)
            └─ kiosk/dietpi-session.sh (abre 1 ou 2 telas)
                 └─ kiosk/kiosk.sh     (Chromium kiosk ou opendash.py)
```

- `data/dietpi.env` guarda o modo (`CARDASH_APP`, `CARDASH_DIETPI_FULL`,
  `CARDASH_DIETPI_SECOND`).
- `data/screens.env` guarda a geometria das duas telas.
- Log do autostart: **`/tmp/opendash-dietpi.log`**.
- Para trocar o modo, rode o instalador de novo com outro argumento ou edite
  `data/dietpi.env` e reinicie.
- Para desligar o autostart: `sudo dietpi-autostart 0`.
- Para ver/alterar: `sudo dietpi-autostart` (menu) ou
  `sudo dietpi-autostart 17`.

### Duas telas

A geometria é gravada em `data/screens.env`. Ajuste e reinicie:

```bash
CARDASH_TOUCH_SIZE=1024,600 CARDASH_TOUCH_POS=0,0 \
CARDASH_BAR_SIZE=1920,480  CARDASH_BAR_POS=1024,0 \
  sudo ./install.sh --app --duo
```

## 4. Diferenças em relação ao Armbian/Debian

| Item | DietPi | Armbian/Debian |
|---|---|---|
| Autostart | `dietpi-autostart 17` + `custom.sh` | systemd kiosk / autostart do desktop |
| X11/Chromium | `dietpi-software install 6 113` | `apt install chromium x11-xserver-utils` |
| Wi-Fi | `dietpi-config` (wpa_supplicant) | NetworkManager/`nmcli` (quando instalado) |
| Bluetooth | `dietpi-config` / `bluez` | BlueZ/`bluetoothctl` |
| Vídeo | `dietpi-config` → Display Options | `xrandr`/config do desktop |
| Boot/config | `/boot/dietpi.txt` | `/boot/armbianEnv.txt` ou `config.txt` |

### Wi-Fi na tela Ajustes

O DietPi **não usa NetworkManager por padrão**, então a aba Wi-Fi do painel fica
desativada (o diagnóstico mostra isso). O Wi-Fi continua funcionando pelo
`dietpi-config`. Se quiser a aba Wi-Fi do painel, instale o NetworkManager
**com cuidado** (pode derrubar o SSH; tenha Ethernet ou console serial à mão):

```bash
sudo apt install -y network-manager
sudo systemctl disable --now dhcpcd 2>/dev/null || true
sudo systemctl disable --now wpa_supplicant 2>/dev/null || true
sudo systemctl enable --now NetworkManager
nmcli device status
```

### Bluetooth

```bash
sudo apt install -y bluez
sudo systemctl enable --now bluetooth
```

Depois o painel usa `bluetoothctl` normalmente.

### GPS por UART (opcional)

O Arduino vai por **USB** (recomendado) e não precisa de UART. Para um GPS
ligado na UART da Orange Pi, habilite o overlay da UART na configuração da
placa (`/boot/dietpiEnv.txt` nas imagens Allwinner, ou `armbianEnv.txt` quando
presente) e garanta que o console serial não está usando a mesma UART. A fonte
do GPS é escolhida automaticamente pelo servidor.

### Câmera e áudio

```bash
sudo ./install.sh --camera     # ffmpeg + v4l-utils (webcam USB)
dietpi-config                  # Audio Options: escolha a saída HDMI/analógica
aplay -l                       # confirme a placa de som
```

Webcam USB é o caminho mais previsível na Orange Pi. Câmera CSI depende do
kernel/driver da imagem DietPi.

## 5. Desempenho na Orange Pi Zero 3 (H618)

- Use **1,5 GB de RAM ou mais** e uma tela **1024×600** para o painel completo.
- O Chromium em kiosk costuma ser mais leve que um desktop completo.
- Se houver engasgo/tearing no app nativo, desligue a aceleração do WebKit:

```bash
CARDASH_SOFTWARE=1 ./kiosk/kiosk.sh
```

  Para tornar permanente, acrescente `CARDASH_SOFTWARE=1` em `data/dietpi.env`
  (o `dietpi-session.sh` exporta o arquivo) ou no serviço do sistema.
- Swap/zram e overclock: `dietpi-config` → Performance Options (por sua conta e risco).

## 6. Solução de problemas

**Tela preta / não abre**
```bash
cat /tmp/opendash-dietpi.log
journalctl -u cardash -f
sudo systemctl status cardash
```
Confira o HDMI em `dietpi-config` → Display Options e rode o kiosk à mão num
console local (tty): `sudo /car-dash/kiosk/dietpi-kiosk.sh`.

**"X11 ausente" ou Chromium não encontrado**
```bash
sudo dietpi-software install 6 113
# app nativo:
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

**O autostart não inicia**
```bash
cat /boot/dietpi/.dietpi-autostart_index          # deve ser 17
cat /var/lib/dietpi/dietpi-autostart/custom.sh    # deve apontar para o repo
grep AUTO_SETUP_AUTOSTART_LOGIN_USER /boot/dietpi.txt
sudo reboot
```
O autostart 17 depende do **autologin no tty1**. Se você trocou o usuário ou
desativou o autologin, rode `sudo dietpi-autostart 17` novamente.

**Chromium reclamando de root**
O instalador já passa `--no-sandbox` quando necessário. Se preferir evitar,
rode o kiosk como `dietpi` (`CARDASH_USER=dietpi`).

**Wi-Fi não aparece no painel**
Comportamento esperado sem `nmcli`; use `dietpi-config`. Veja a seção 4.

**Atualizar o OpenDash**
Use **Ajustes → Atualizações** no painel ou:
```bash
cd /opt/car-dash && sudo git pull
sudo ./install.sh --no-apt     # reaplica serviços/autostart sem baixar pacotes
```
Se o repositório estiver em `/opt` (dono root) e o serviço rodar como `dietpi`,
o botão do painel pode não ter permissão para `git pull`; nesse caso use o comando
acima com `sudo`.

## 7. Reverter o autostart

```bash
sudo dietpi-autostart 0
sudo systemctl disable --now cardash.service
sudo rm -f /var/lib/dietpi/dietpi-autostart/custom.sh
```

Os dados (`data/`) e o código não são removidos.
