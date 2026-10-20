# OpenDash OS (Armbian) — imagem pronta com Wi‑Fi funcionando

Variante da distro OpenDash OS baseada em **[Armbian](https://www.armbian.com/)**
em vez do DietPi. Serve para placas onde a imagem DietPi **não sobe o adaptador
Wi‑Fi** — em especial o **Orange Pi Zero 3 / Zero 3W (Allwinner H618)**, cujo
módulo Wi‑Fi (chip **AIC8800**, ou **XR829** em revisões antigas) precisa de
driver + firmware que o kernel do DietPi muitas vezes não traz.

A documentação da variante DietPi continua em [`distro.md`](distro.md). As duas
convivem: a DietPi é o caminho padrão/histórico, a Armbian é o caminho
recomendado para o H618.

> **Por que Armbian resolve o Wi‑Fi:** a Armbian mantém os kernels por família
> (sunxi/H618) e já empacota o driver `aic8800` e o firmware. Nas imagens
> `current` (kernel 6.18.x) o Wi‑Fi do Zero 3 sobe no primeiro boot; se ainda
> faltar firmware, o `firstboot-armbian.sh` tenta instalar os pacotes
> `aic8800`/`xr829` automaticamente.

## 1. Placas suportadas

A lista fica em [`distro/boards-armbian.conf`](../distro/boards-armbian.conf).
As placas com `1` entram no build padrão.

| Placa | ID | Slug Armbian | Release / branch |
|---|---|---|---|
| Orange Pi Zero 3 | `zero3` | `orangepizero3` | Trixie / current |
| Orange Pi Zero 3W | `zero3w` | `orangepizero3` | Trixie / current |
| Orange Pi Zero 2W | `zero2w` | `orangepizero2w` | Trixie / current |
| Orange Pi 5 | `opi5` | `orangepi5` | Trixie / current |
| Orange Pi 3 | `opi3` | `orangepi3` | Trixie / current |
| Orange Pi 3 LTS | `opi3lts` | `orangepi3-lts` | Trixie / current |
| Orange Pi 3B | `opi3b` | `orangepi3b` | Trixie / current |
| Orange Pi 4 LTS | `opi4lts` | `orangepi4-lts` | Trixie / current |
| Orange Pi 5 Plus | `opi5plus` | `orangepi5-plus` | Trixie / current |
| Raspberry Pi 3/4/Zero 2 W | `rpi234` | `raspberrypi4b` | Trixie / current |

Os nomes/slugs vêm do catálogo em <https://www.armbian.com/boards/>. O download
estável é `https://dl.armbian.com/<slug>/<Release>_current_minimal.img.xz`.

## 2. Gravar e ligar

1. Baixe `OpenDash-OS-Armbian-<versao>-<placa>-arm64.img.xz` + `.sha256`.
2. Confira o SHA256:

   ```bash
   sha256sum -c OpenDash-OS-Armbian-*.img.xz.sha256
   ```

3. Grave com **balenaEtcher**, **Armbian Imager** ou:

   ```bash
   xz -dc arquivo.img.xz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress
   ```

4. Insira o cartão e ligue. O primeiro boot da Armbian configura usuário, locale,
   Wi‑Fi e roda `/root/provisioning.sh`, que instala o OpenDash e **reinicia** no
   painel.

Credenciais padrão embutidas na imagem (preseed):

| Item | Valor |
|---|---|
| Usuário | `kiosk` |
| Senha | `opendash` |
| Root | senha `opendash` |
| Hostname | `OpenDash` (`http://opendash.local:8080`) |
| Locale / teclado / fuso | `pt_BR.UTF-8` / `br` / `America/Sao_Paulo` |
| Wi‑Fi (país) | `BR` |

> Troque as senhas depois (`passwd`, `passwd kiosk`).

## 3. Wi‑Fi no primeiro boot

O preseed em `/root/.not_logged_in_yet` habilita o Wi‑Fi mas **deixa SSID/senha
em branco**, para não gravar credenciais no repositório. Dois caminhos:

- **Console (HDMI):** no primeiro boot, se o Wi‑Fi não estiver configurado, o
  `wifi-setup.sh` (extraído do payload) abre `nmtui`/`nmcli`/`raspi-config` para
  você digitar o SSID e a senha.
- **Depois do boot:** `sudo nmtui` ou `sudo nmcli device wifi connect '<SSID>' password '<senha>'`.

Se o adaptador ainda não aparecer, verifique o diagnóstico na seção 7.

## 4. Configuração antes do primeiro boot (opcional)

A partição do sistema é uma **raiz ext4 única** (não há partição FAT). O
`armbianEnv.txt` fica em `/boot` dentro dessa raiz — edite-o por SSH/console se
precisar. As chaves `OPENDASH_*` **não ficam no boot** neste caminho: elas vêm de
`/opt/opendash-image.conf` (embutido na raiz ext4 no build). Para mudar o modo de
tela antes de gravar, edite esse arquivo na imagem, ou ajuste depois em
`/opt/opendash/data/screens.env`.

```
OPENDASH_MODE=kiosk          # uma tela (padrão)
OPENDASH_MODE=duo            # painel completo + cluster em barra
OPENDASH_MODE=cluster        # painel completo + velocímetro redondo
OPENDASH_MODE=bar            # só cluster em barra (2ª tela)
OPENDASH_MODE=cluster-only   # só velocímetro redondo (2ª tela)
OPENDASH_TOUCH_SIZE=1024,600
OPENDASH_BAR_SIZE=1920,480
OPENDASH_TOUCH_POS=0,0
OPENDASH_BAR_POS=1024,0
OPENDASH_BROWSER=chromium    # ou app (WebKitGTK)
OPENDASH_CAR_NAME=OpenDash
OPENDASH_REBOOT=1
```

## 5. Primeiro boot e acesso

Acompanhe pelo HDMI ou por SSH (`kiosk@opendash.local`, senha `opendash`). Log:

```
/var/lib/opendash/firstboot.log
```

O script de provisionamento é `/root/provisioning.sh` (cópia de
`distro/firstboot-armbian.sh`). Ele:

1. verifica/instala driver+firmware de Wi‑Fi (AIC8800/XR829) e NetworkManager;
2. valida o payload `/opt/opendash-runtime.tar.gz` pelo SHA256;
3. extrai para `/opt/opendash`, ajusta `car.name` e executa
   `install.sh --no-apt --kiosk|--duo|...` com `CARDASH_DEPS_READY=1`;
4. registra o serviço, configura o autostart e reinicia.

Depois do reboot:

- painel: `http://opendash.local:8080` ou `http://IP:8080`;
- log do serviço: `journalctl -u cardash -f`.

Para rodar de novo manualmente:

```bash
sudo /root/provisioning.sh
# ou, já extraído:
sudo /opt/opendash/firstboot.sh
```

## 6. Como a imagem é construída

`distro/build-image-armbian.sh <placa>`:

1. baixa a imagem oficial da Armbian de
   `https://dl.armbian.com/<slug>/<Release>_<branch>_<variant>.img.xz` e confere
   contra o `.sha` (que a Armbian publica como `<hash> <arquivo>`);
2. descompacta, localiza via `sfdisk` a raiz ext4 (maior partição Linux). As
   imagens Armbian para o H618 são de **partição única** — o `armbianEnv.txt`
   fica em `/boot` dentro da própria raiz (o script também suporta o layout com
   partição FAT de boot separada, quando existir);
3. gera `opendash-runtime.tar.gz` com `distro/make-runtime.sh`;
4. injeta na raiz ext4, com `debugfs` (sem loop/mount):
   - `/opt/opendash-runtime.tar.gz` + `.sha256` + `/opt/opendash-image.conf`;
   - `/root/.not_logged_in_yet` (preseed do primeiro boot);
   - `/root/provisioning.sh` (cópia de `firstboot-armbian.sh`, mode 0755);
5. verifica os arquivos, comprime em `.img.xz` e grava `.sha256` + `.info`.

Dependências do host (iguais às da variante DietPi):

```bash
sudo apt install mtools fdisk e2fsprogs xz-utils curl
```

Build local:

```bash
./distro/build-image-armbian.sh zero3
# saída: distro/out/OpenDash-OS-Armbian-<versao>-zero3-arm64.img.xz
```

Para uma placa nova, acrescente uma linha em `distro/boards-armbian.conf` no
formato `id|nome|slug|Release|branch|variant|enabled` e confirme o slug/URL em
`https://dl.armbian.com/<slug>/`.

## 7. Solução de problemas (Wi‑Fi)

| Sintoma | O que verificar |
|---|---|
| Sem interface Wi‑Fi (`wlan0`) | `lsusb`, `dmesg \| grep -iE "wifi\|aic\|xr829\|mmc"`; veja se o chip é AIC8800 ou XR829 |
| `aic8800` sem firmware | `sudo apt install firmware-aic8800 aic8800-firmware` (ou `aic8800-usb-dkms`); `dmesg` mostra "firmware not found" |
| Placa é Zero 3 **sem W** | não existe Wi‑Fi a bordo; use adaptador USB ou a variante 3W |
| Wi‑Fi aparece mas não conecta | `nmcli device status`, `nmcli device wifi list`, país `BR` (`iw reg set BR`), credenciais no `nmtui` |
| Sem rede no primeiro boot | conecte cabo Ethernet; o provisionamento baixa o payload se a imagem não tiver o runtime |
| LED/console sem vídeo | HDMI ligado antes de energizar; fonte 5V/2A estável |

Logs úteis:

```bash
sudo tail -f /var/lib/opendash/firstboot.log
sudo dmesg | grep -iE "wifi|aic|xr829|brcm|mmc"
journalctl -u cardash -f
```

## 8. Diff para a variante DietPi

| Aspecto | DietPi (`build-image.sh`) | Armbian (`build-image-armbian.sh`) |
|---|---|---|
| Base | `dietpi.com/downloads/images` | `dl.armbian.com/<slug>` |
| Partição de boot | FAT com `dietpi.txt` (`DIETPISETUP`) | raiz ext4 única; `armbianEnv.txt` em `/boot` (suporta também FAT separada) |
| Config do 1º boot | `dietpi.txt` + `dietpi-wifi.txt` na FAT | `/root/.not_logged_in_yet` (preseed) na rootfs |
| Script do 1º boot | `/boot/Automation_Custom_Script.sh` | `/root/provisioning.sh` |
| Wi‑Fi | `dietpi-config` / `dietpi-wifi.txt` | NetworkManager (`nmtui`/`nmcli`) + firmware AIC8800 |
| Chaves `OPENDASH_*` | na FAT (`dietpi.txt`) | em `/opt/opendash-image.conf` (rootfs) |

Ambas produzem um `.img.xz` com o OpenDash embutido e o mesmo `install.sh`.
