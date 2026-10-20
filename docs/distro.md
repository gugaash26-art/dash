# OpenDash OS — imagem pronta para Orange Pi e Raspberry Pi

Esta é a documentação da **distro**: uma imagem `.img.xz` que você grava no cartão
SD, liga na placa e o painel OpenDash abre sozinho. Não é preciso instalar Python,
navegador, X11 ou configurar autostart na mão.

> **Variante Armbian:** há uma segunda base, a **[Armbian](https://www.armbian.com/)**,
> recomendada para o **Orange Pi Zero 3 / Zero 3W (H618)** e outras placas onde o
> Wi‑Fi não sobe no DietPi. Veja [`armbian.md`](armbian.md). Esta página documenta
> a base DietPi (padrão histórico).

A base é o **[DietPi](https://dietpi.com/)** (Debian enxuto, mantido para SBCs),
com os seguintes ajustes:

- X11 + Chromium instalados no primeiro boot (IDs 6 e 113 do `dietpi-software`);
- OpenDash embutido em `/opt/opendash` (não precisa de internet para o código);
- autologin `root` + `dietpi-autostart 17` (script custom em foreground);
- kiosk em uma ou duas telas (`kiosk`, `duo`, `cluster`, `bar`, `cluster-only`);
- configuração amigável em `dietpi.txt`/`dietpi-wifi.txt` na partição FAT.

> **Licença/base:** a imagem redistribui o DietPi e pacotes Debian. O código do
> OpenDash é o deste repositório. Consulte as licenças do DietPi/Debian e mantenha
> os avisos originais.

## 1. Placas suportadas

A lista oficial fica em [`distro/boards.conf`](../distro/boards.conf). As imagens
com `1` são geradas no build padrão; as demais podem ser geradas sob demanda.

| Placa | ID | Base DietPi |
|---|---|---|
| Orange Pi Zero 3 | `zero3` | `DietPi_OrangePiZero3-ARMv8-Bookworm.img.xz` |
| Orange Pi Zero 3W | `zero3w` | `DietPi_OrangePiZero3W-ARMv8-Bookworm.img.xz` |
| Orange Pi Zero 2W | `zero2w` | `DietPi_OrangePiZero2W-ARMv8-Bookworm.img.xz` |
| Orange Pi 3 | `opi3` | `DietPi_OrangePi3-ARMv8-Bookworm.img.xz` |
| Orange Pi 3 LTS | `opi3lts` | `DietPi_OrangePi3LTS-ARMv8-Bookworm.img.xz` |
| Orange Pi 3B | `opi3b` | `DietPi_OrangePi3B-ARMv8-Bookworm.img.xz` |
| Orange Pi 4 LTS | `opi4lts` | `DietPi_OrangePi4LTS-ARMv8-Bookworm.img.xz` |
| Orange Pi 4 Pro | `opi4pro` | `DietPi_OrangePi4Pro-ARMv8-Bookworm.img.xz` |
| Orange Pi 5 | `opi5` | `DietPi_OrangePi5-ARMv8-Bookworm.img.xz` |
| Orange Pi 5B | `opi5b` | `DietPi_OrangePi5B-ARMv8-Bookworm.img.xz` |
| Orange Pi 5 Pro | `opi5pro` | `DietPi_OrangePi5Pro-ARMv8-Bookworm.img.xz` |
| Orange Pi 5 Plus | `opi5plus` | `DietPi_OrangePi5Plus-ARMv8-Bookworm.img.xz` |
| Orange Pi 5 Max | `opi5max` | `DietPi_OrangePi5Max-ARMv8-Bookworm.img.xz` |
| Orange Pi 5 Ultra | `opi5ultra` | `DietPi_OrangePi5Ultra-ARMv8-Bookworm.img.xz` |
| Orange Pi CM5 | `opicm5` | `DietPi_OrangePiCM5-ARMv8-Bookworm.img.xz` |
| Raspberry Pi 3/4/Zero 2 W / Pi 2 v1.2 (64-bit) | `rpi234` | `DietPi_RPi234-ARMv8-Bookworm.img.xz` |
| Raspberry Pi 2 v1.1 (32-bit) | `rpi2` | `DietPi_RPi2-ARMv7-Bookworm.img.xz` |
| Raspberry Pi 5 | `rpi5` | `DietPi_RPi5-ARMv8-Bookworm.img.xz` |

Requisitos mínimos: cartão SD de 8 GB (16 GB recomendado para mídia/câmera),
fonte estável e, no primeiro boot, **internet** (cabo ou Wi‑Fi configurado antes).

## 2. Gravar e ligar

1. Baixe `OpenDash-OS-<versao>-<placa>-arm64.img.xz` e o `.sha256` do Release.
2. Confira o SHA256 (opcional, mas recomendado):

   ```bash
   sha256sum -c OpenDash-OS-*.img.xz.sha256
   ```

3. Grave com **balenaEtcher**, **Raspberry Pi Imager** (Use custom image) ou
   `xz -dc arquivo.img.xz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress`.
4. Antes de ejetar, monte a partição FAT e configure Wi‑Fi/modo (seção 3).
5. Insira o cartão, conecte HDMI/touch e ligue. O primeiro boot instala X11,
   Chromium e dependências, instala o OpenDash e **reinicia** no painel.

O primeiro boot pode levar de 10 a 30 minutos no Orange Pi Zero 3 (atualização do
DietPi + Chromium). Nas placas RK3588/Raspberry Pi 5 é bem mais rápido.

## 3. Configuração antes do primeiro boot

A partição FAT aparece como `DIETPISETUP` (Orange Pi) ou `boot`/`bootfs`
(Raspberry Pi). Abra os arquivos em qualquer PC.

### 3.1 Wi‑Fi

`dietpi-wifi.txt`:

```
aWIFI_SSID[0]='minha-rede'
aWIFI_KEY[0]='minha-senha'
```

Se esses campos ficarem com os placeholders, o `firstboot.sh` abre o assistente
de Wi‑Fi (`nmtui`/`nmcli` ou `dietpi-config`) no console antes de instalar o
OpenDash. Também é possível configurar depois em `dietpi-config` → Network
Options → Wi‑Fi.

`dietpi.txt`:

```
AUTO_SETUP_NET_WIFI_ENABLED=1
AUTO_SETUP_NET_WIFI_COUNTRY_CODE=BR
```

Deixe `AUTO_SETUP_NET_ETHERNET_ENABLED=1` se for usar cabo.

### 3.2 Modo de tela (`dietpi.txt`)

```
OPENDASH_MODE=kiosk          # uma tela (padrão)
OPENDASH_MODE=duo            # painel completo + cluster em barra
OPENDASH_MODE=cluster        # painel completo + velocímetro redondo
OPENDASH_MODE=bar            # só cluster em barra (2ª tela)
OPENDASH_MODE=cluster-only   # só velocímetro redondo (2ª tela)

OPENDASH_TOUCH_SIZE=1024,600 # tela principal (largura,altura)
OPENDASH_BAR_SIZE=1920,480   # segunda tela
OPENDASH_TOUCH_POS=0,0
OPENDASH_BAR_POS=1024,0
```

Em `duo`/`cluster`, a segunda tela é posicionada ao lado da principal. Ajuste as
posições conforme o arranjo do `xrandr` (a soma de `TOUCH_POS` + largura deve bater
com o início da segunda tela).

Precedência: valores editados em `dietpi.txt` vencem; se a chave não existir, o
firstboot usa os padrões gravados em `/opt/opendash-image.conf` (na raiz do
sistema) e, por último, os padrões internos do script.

### 3.3 Outros ajustes

```
OPENDASH_BROWSER=chromium    # padrão
OPENDASH_BROWSER=app         # app nativo WebKitGTK (instala WebKit no boot)
OPENDASH_CAR_NAME=OpenDash   # nome exibido no painel
OPENDASH_REBOOT=1            # reinicia ao terminar o primeiro boot (0 = não)
OPENDASH_VERSION=0.1.0       # gravado em /etc/opendash-release
```

Também vale a pena revisar:

- `AUTO_SETUP_GLOBAL_PASSWORD=opendash` — troque depois com `passwd`;
- `AUTO_SETUP_SSH_SERVER_INDEX=0` — SSH desligado; use `-1` (Dropbear) ou `-2`
  (OpenSSH) se precisar;
- `AUTO_SETUP_TIMEZONE=America/Sao_Paulo`, `AUTO_SETUP_LOCALE=pt_BR.UTF-8`,
  `AUTO_SETUP_KEYBOARD_LAYOUT=br`;
- `AUTO_SETUP_NET_HOSTNAME=OpenDash` + `avahi-daemon`/`libnss-mdns` → acesso por `http://opendash.local:8080`.

## 4. Primeiro boot e acesso

Acompanhe pelo HDMI ou por SSH (se habilitado). O log fica em:

```
/var/lib/opendash/firstboot.log
```

O script executado é `/boot/Automation_Custom_Script.sh` (cópia de
`distro/firstboot.sh`). Ele:

1. lê as chaves `OPENDASH_*` de `/boot/dietpi.txt`;
2. valida o payload `/opt/opendash-runtime.tar.gz` pelo SHA256;
3. extrai para `/opt/opendash`, ajusta `car.name` e executa
   `install.sh --no-apt --kiosk|--duo|...` com `CARDASH_DEPS_READY=1`;
4. registra o serviço, configura o autostart e reinicia.

Depois do reboot:

- painel: `http://opendash.local:8080` ou `http://IP:8080`;
- usuário `root`, senha `opendash` (troque!);
- SSH desligado por padrão;
- log do serviço: `journalctl -u cardash -f`.

Se algo falhar, entre no console e rode novamente:

```bash
sudo /boot/Automation_Custom_Script.sh
# ou, depois do primeiro boot:
sudo /opt/opendash/firstboot.sh
```

O script é idempotente: reaplica a configuração sem apagar `/opt/opendash/data`.

## 5. Atualizar o sistema e o OpenDash

- **Painel:** Ajustes → Atualizações (faz `git pull` e reinicia).
- **Terminal:**

  ```bash
  cd /opt/opendash && sudo git pull
  sudo ./install.sh --no-apt --kiosk   # ou --duo/--cluster/...
  ```

- **DietPi:** `sudo dietpi-update`.
- Para trocar Wi‑Fi/modo depois do primeiro boot, edite `/boot/dietpi.txt` (ou use
  `dietpi-config`) e rode o firstboot de novo, ou ajuste direto em
  `/opt/opendash/data/screens.env` e `data/dietpi.env`.

> Se o repositório estiver em `/opt` como root e o serviço rodar como `root`
> (padrão), o botão de atualização funciona. Se você trocar para um usuário
> comum, garanta permissão de escrita no repositório ou use `sudo`.

## 6. Como a imagem é construída

`distro/build-image.sh <placa>`:

1. baixa a imagem oficial do DietPi e confere o `.sha256`;
2. descompacta e localiza, via `sfdisk`, a partição FAT que contém `dietpi.txt`
   (a última partição `DIETPISETUP` no Orange Pi; a primeira FAT no Raspberry Pi)
   e a maior partição Linux (rootfs);
3. gera `opendash-runtime.tar.gz` com `distro/make-runtime.sh` (sem `.git`, docs,
   hardware, dados ou `.venv`);
4. aplica `distro/patch-dietpi.py` no `dietpi.txt`, ativando
   `AUTO_SETUP_AUTOMATED=1`, autostart 17, X11/Chromium, pacotes e as chaves
   `OPENDASH_*`;
5. copia `Automation_Custom_Script.sh` e `README-OPENDASH.txt` para a FAT;
6. injeta o payload e o SHA256 na rootfs ext4 com `debugfs` (sem loop/mount);
7. verifica os arquivos, comprime em `.img.xz` e grava `.sha256` + `.info`.

Não é necessário root. Dependências do host:

```bash
sudo apt install mtools fdisk e2fsprogs xz-utils curl
```

Build local:

```bash
./distro/build-image.sh zero3
./distro/build-image.sh rpi234
# saída: distro/out/OpenDash-OS-<versao>-<placa>-<arch>.img.xz
```

Para uma placa nova, acrescente uma linha em `distro/boards.conf` com o nome exato
do arquivo `.img.xz` publicado pela DietPi.

### 6.1 GitHub Actions

O workflow de exemplo fica em `distro/github-workflow.yml`. Para ativar, copie para
`.github/workflows/distro.yml` e faça commit com um token que tenha o escopo
`workflow` (tokens clássicos sem esse escopo são recusados pelo GitHub).

Ele oferece:

- `workflow_dispatch` com `boards` (`default`, `all` ou IDs separados por vírgula),
  `version` e `release`;
- em tags `v*`, gera as placas padrão (`default`) e publica um Release com as
  imagens, checksums, manifesto e o `opendash-runtime.tar.gz`;
- cache dos downloads base e upload de artefatos por placa.

Para gerar uma prévia sem release: Actions → **OpenDash OS images** → Run workflow
→ `boards=zero3,rpi234` e `release=false`.

## 7. Solução de problemas

| Sintoma | O que verificar |
|---|---|
| Não liga / sem HDMI | fonte, cartão gravado corretamente, HDMI antes do boot, imagem da placa certa |
| Fica no console após o primeiro boot | `/var/lib/opendash/firstboot.log`; rode o firstboot de novo |
| Painel não abre | `systemctl status cardash`, `journalctl -u cardash -f`; `curl localhost:8080/health` |
| Tela preta no kiosk | X11 instalado? `dietpi-autostart` está em 17? `data/dietpi.env` existe? |
| Wi‑Fi não conecta | `dietpi-wifi.txt` (SSID/senha), `AUTO_SETUP_NET_WIFI_ENABLED=1`, país `BR`; se o adaptador nem aparecer (ex.: Orange Pi Zero 3/H618), use a variante Armbian em [`armbian.md`](armbian.md) |
| Chromium não abre como root | o kiosk já passa `--no-sandbox`; confira `kiosk/kiosk.sh` |
| Segunda tela no lugar errado | `OPENDASH_TOUCH_SIZE/POS` e `BAR_SIZE/POS`; veja `xrandr` |
| Atualização falha | repositório em `/opt` root; use `sudo git pull` |
| Payload corrompido | baixe a imagem de novo e confira o `.sha256` |

Logs úteis:

```bash
sudo tail -f /var/lib/opendash/firstboot.log
journalctl -u cardash -f
sudo dietpi-config        # vídeo, áudio, Wi-Fi, SSH, performance
```

## 8. Segurança

- Troque a senha padrão `opendash` (`passwd`) e mantenha SSH desligado se não usar.
- O kiosk roda como `root` (padrão do DietPi) para acessar serial/GPIO; se usar um
  usuário comum, ajuste grupos (`dialout`, `video`, `render`, `input`).
- Não exponha a porta 8080 na internet. Use a rede do carro/hotspot.
- Baixe imagens apenas do Release oficial e confira o SHA256.

## 9. Reverter para o DietPi puro

A imagem é uma imagem DietPi com arquivos extras. Para voltar ao DietPi:

```bash
sudo rm -rf /opt/opendash /opt/opendash-runtime.* /var/lib/opendash
sudo rm -f /boot/Automation_Custom_Script.sh /etc/opendash-release
sudo dietpi-autostart 0
sudo systemctl disable --now cardash
sudo reboot
```

Ou grave novamente a imagem oficial do DietPi para a sua placa.
